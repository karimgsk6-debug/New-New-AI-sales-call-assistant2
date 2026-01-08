# =========================================================
# AI Sales Assistant – Clean RAG / LLM / UI Architecture
# Groq + llama-3.1-70b-versatile
# =========================================================

import os
import re
from typing import List, Dict
import streamlit as st

# =============================
# CONFIG (GLOBAL SAFETY)
# =============================
MAX_CONTEXT_CHARS = 12_000
MAX_DOC_CHARS = 2_000
MAX_OUTPUT_TOKENS = 700
TEMPERATURE = 0.2

# =============================
# OPTIONAL IMPORTS
# =============================
try:
    from groq import Groq
except Exception:
    Groq = None

try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

# =========================================================
# BRAND CONFIG
# =========================================================
BRANDS = {
    "shingrix": {
        "display": "Shingrix",
        "references": ".devcontainer/references/shingrix",
        "sales": ".devcontainer/SalesModule/shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Committed Vaccinator"],
        "barriers": ["Risk not perceived", "Time", "Cost", "Efficacy doubts"],
    },
    "jemperli": {
        "display": "Jemperli",
        "references": ".devcontainer/references/jemperli",
        "sales": ".devcontainer/SalesModule/jemperli",
        "segments": ["Target ID", "Trial", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist"],
        "barriers": ["Safety", "Eligibility", "Access"],
    },
    "trelegy": {
        "display": "Trelegy",
        "references": ".devcontainer/references/trelegy",
        "sales": ".devcontainer/SalesModule/trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption"],
        "personas": ["Primary Care Prescriber", "Pulmonologist"],
        "barriers": ["Inhaler technique", "Coverage"],
    },
}

# =========================================================
# =========================
# RAG / INGESTION
# =========================
# =========================================================

def read_file(path: str) -> str:
    if not os.path.exists(path):
        return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""

def load_documents(brand: str, doc_type: str) -> List[Dict]:
    base = BRANDS[brand][doc_type]
    docs = []
    if not os.path.exists(base):
        return docs

    for f in os.listdir(base):
        if f.lower().endswith((".pdf", ".txt")):
            text = read_file(os.path.join(base, f))
            if text.strip():
                docs.append({
                    "text": text,
                    "source": f,
                    "brand": brand,
                    "type": doc_type,
                })
    return docs

# =========================
# RAG / RETRIEVAL
# =========================

def retrieve(query: str, docs: List[Dict], top_k=5) -> List[Dict]:
    if not docs:
        return []

    corpus = [d["text"] for d in docs]

    if SKLEARN_AVAILABLE:
        vect = TfidfVectorizer(stop_words="english")
        X = vect.fit_transform(corpus + [query])
        sims = cosine_similarity(X[-1], X[:-1]).flatten()
        idxs = sims.argsort()[::-1][:top_k]
        return [docs[i] for i in idxs if sims[i] > 0]

    return docs[:top_k]

# =========================
# RAG / CONTEXT BUILDER
# =========================

def build_context(docs: List[Dict]) -> str:
    ctx = ""
    for d in docs:
        block = f"\nSOURCE: {d['source']}\n{d['text'][:MAX_DOC_CHARS]}\n"
        if len(ctx) + len(block) > MAX_CONTEXT_CHARS:
            break
        ctx += block
    return ctx

# =========================================================
# =========================
# LLM / CLIENT
# =========================
# =========================================================

def load_groq():
    key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", "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")
    if not key or Groq is None:
        return None
    return Groq(api_key=key)

def call_llm(system: str, user: str) -> str:
    client = load_groq()
    if not client:
        return "❌ Groq client unavailable."

    try:
        res = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            temperature=TEMPERATURE,
            max_tokens=MAX_OUTPUT_TOKENS,
            messages=[
                {"role": "system", "content": system[:2000]},
                {"role": "user", "content": user[:MAX_CONTEXT_CHARS]},
            ],
        )
        return res.choices[0].message.content
    except Exception:
        return (
            "⚠️ Unable to generate response using approved content.\n"
            "Please refine your question or reduce scope."
        )

# =========================================================
# =========================
# LLM / TASKS
# =========================
# =========================================================

def sales_call_llm(context: Dict, docs: List[Dict]) -> str:
    evidence = build_context(docs)

    system = (
        "You are a pharmaceutical sales training assistant.\n"
        "Use ONLY the provided documents.\n"
        "No external medical knowledge."
    )

    user = f"""
Brand: {context['brand']}
Segment: {context['segment']}
Persona: {context['persona']}
Barriers: {", ".join(context['barriers'])}
Tone: {context['tone']}

Approved Content:
{evidence}

Generate a structured sales call:
• Opening
• Discovery
• Value articulation
• Objection handling
• Close
"""

    return call_llm(system, user)

def medical_qa_llm(question: str, docs: List[Dict]) -> str:
    evidence = build_context(docs)

    system = (
        "You are a medical information assistant.\n"
        "Answer ONLY from the provided sources.\n"
        "If not present, say the information is not available.\n"
        "Always cite sources."
    )

    user = f"""
Question:
{question}

Sources:
{evidence}

Answer with citations.
"""
    return call_llm(system, user)

# =========================================================
# =========================
# UI
# =========================
# =========================================================

st.set_page_config("AI Sales Call Assistant", layout="wide")
st.title("💡 AI Sales Call Assistant")

# ---- Session
if "chat" not in st.session_state:
    st.session_state.chat = []

# ---- Sidebar
with st.sidebar:
    brand = st.selectbox(
        "Brand",
        BRANDS.keys(),
        format_func=lambda x: BRANDS[x]["display"],
    )

    mode = st.radio("Mode", ["Sales Call Generation", "Medical / Product Q&A"])

    segment = st.selectbox("Segment", BRANDS[brand]["segments"])
    persona = st.selectbox("Persona", BRANDS[brand]["personas"])
    barriers = st.multiselect("Barriers", BRANDS[brand]["barriers"])
    tone = st.selectbox("Tone", ["Executive", "Coaching", "Persuasive", "Clinical"])

    if st.button("Clear Chat"):
        st.session_state.chat = []

# ---- Input
query = st.text_area("Your input")
if st.button("Send") and query.strip():
    st.session_state.chat.append(("user", query))

    if mode == "Sales Call Generation":
        docs = (
            load_documents(brand, "references")
            + load_documents(brand, "sales")
        )
        retrieved = retrieve(query, docs)
        answer = sales_call_llm(
            {
                "brand": BRANDS[brand]["display"],
                "segment": segment,
                "persona": persona,
                "barriers": barriers,
                "tone": tone,
            },
            retrieved,
        )
    else:
        docs = load_documents(brand, "references")
        retrieved = retrieve(query, docs)
        answer = medical_qa_llm(query, retrieved)

    st.session_state.chat.append(("assistant", answer))

# ---- Chat render
for role, msg in st.session_state.chat:
    if role == "user":
        st.markdown(f"**You:** {msg}")
    else:
        st.markdown(f"**AI:**\n\n{msg}")

st.caption("⚠️ Internal training tool. Approved content only.")
