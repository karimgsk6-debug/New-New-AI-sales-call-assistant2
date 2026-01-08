# =========================================================
# app_final_merged.py
# AI Sales Assistant for Medical Rep Training
# Groq + llama-3.1-70b-versatile + Local Secure RAG
# =========================================================

import os
import re
import io
import base64
import tempfile
from datetime import datetime
from html import escape
from typing import List, Dict

import streamlit as st

# -------------------------
# Optional / soft imports
# -------------------------
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

try:
    from gtts import gTTS
except Exception:
    gTTS = None


# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# GROQ CLIENT
# =========================================================
def load_groq_client():
    api_key = (
        os.getenv("GROQ_API_KEY")
        or st.secrets.get("GROQ_API_KEY", "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")
    )
    if not api_key or Groq is None:
        return None
    return Groq(api_key=api_key)


# =========================================================
# BRAND CONFIG
# =========================================================
BRANDS = {
    "shingrix": {
        "display": "Shingrix",
        "references_path": ".devcontainer/references/shingrix",
        "sales_path": ".devcontainer/SalesModule/shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": [
            "Uncommitted Vaccinator",
            "Reluctant Efficiency",
            "Patient Influenced",
            "Committed Vaccinator",
        ],
        "barriers": [
            "HZ not considered a risk",
            "Time constraints",
            "Cost concerns",
            "Efficacy doubts",
        ],
    },
    "jemperli": {
        "display": "Jemperli",
        "references_path": ".devcontainer/references/jemperli",
        "sales_path": ".devcontainer/SalesModule/jemperli",
        "segments": ["Target ID", "Trial", "Routine Use", "Advocacy"],
        "personas": [
            "Data-Driven Oncologist",
            "Skeptical Specialist",
            "Innovator",
            "Late Adopter",
        ],
        "barriers": [
            "Safety concerns",
            "Eligibility uncertainty",
            "Access issues",
        ],
    },
    "trelegy": {
        "display": "Trelegy",
        "references_path": ".devcontainer/references/trelegy",
        "sales_path": ".devcontainer/SalesModule/trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": [
            "Primary Care Prescriber",
            "Pulmonologist",
            "Respiratory Nurse",
        ],
        "barriers": [
            "Inhaler technique",
            "Formulary access",
            "Coverage",
        ],
    },
}


# =========================================================
# SESSION STATE
# =========================================================
def init_session():
    defaults = {
        "chat": [],
        "brand": "shingrix",
        "mode": "Sales Call Generation",
        "persona": "",
        "segment": "",
        "barriers": [],
        "tone": "Executive",
        "temperature": 0.2,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_session()


# =========================================================
# FILE INGESTION
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


def load_documents(brand_key: str, doc_type: str) -> List[Dict]:
    """
    doc_type: 'medical' or 'sales'
    """
    base_path = (
        BRANDS[brand_key]["references_path"]
        if doc_type == "medical"
        else BRANDS[brand_key]["sales_path"]
    )

    docs = []
    if not os.path.exists(base_path):
        return docs

    for fname in os.listdir(base_path):
        if fname.lower().endswith((".pdf", ".txt")):
            text = read_file(os.path.join(base_path, fname))
            if text.strip():
                docs.append({
                    "text": text,
                    "source": fname,
                    "brand": brand_key,
                    "type": doc_type,
                })
    return docs


# =========================================================
# LOCAL RAG (TF-IDF)
# =========================================================
def retrieve(query: str, docs: List[Dict], top_k: int = 5):
    if not docs:
        return []

    corpus = [d["text"] for d in docs]
    if SKLEARN_AVAILABLE:
        vectorizer = TfidfVectorizer(stop_words="english")
        X = vectorizer.fit_transform(corpus + [query])
        scores = cosine_similarity(X[-1], X[:-1]).flatten()
        idxs = scores.argsort()[::-1][:top_k]
        return [docs[i] for i in idxs if scores[i] > 0]

    # fallback
    return docs[:top_k]


# =========================================================
# LLM CALL
# =========================================================
def groq_generate(system_prompt: str, user_prompt: str) -> str:
    client = load_groq_client()
    if not client:
        return "❌ Groq client not available."

    resp = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content


# =========================================================
# SALES CALL GENERATION
# =========================================================
def generate_sales_call(context: Dict, docs: List[Dict]) -> str:
    evidence = "\n\n".join(
        f"[{d['source']}]\n{d['text'][:1500]}"
        for d in docs
    )

    system = (
        "You are a compliant pharmaceutical sales-training assistant.\n"
        "You MUST only use the provided documents.\n"
        "Do NOT add external medical knowledge.\n"
        "Generate a realistic sales-call roleplay."
    )

    user = f"""
Brand: {context['brand']}
Segment: {context['segment']}
Persona: {context['persona']}
Barriers: {", ".join(context['barriers'])}
Tone: {context['tone']}

Approved Content:
{evidence}

Generate:
• Opening
• Discovery
• Value articulation
• Objection handling
• Close
"""

    return groq_generate(system, user)


# =========================================================
# MEDICAL / PRODUCT Q&A (STRICT RAG)
# =========================================================
def answer_question(question: str, docs: List[Dict]) -> str:
    evidence_blocks = []
    for d in docs:
        evidence_blocks.append(
            f"Source: {d['source']}\n{d['text'][:1200]}"
        )

    system = (
        "You are a medical information assistant.\n"
        "Answer ONLY using the provided sources.\n"
        "If the answer is not present, say: "
        "'The provided documents do not contain this information.'\n"
        "Always cite sources."
    )

    user = f"""
Question:
{question}

Sources:
{chr(10).join(evidence_blocks)}

Answer with citations.
"""

    return groq_generate(system, user)


# =========================================================
# SIDEBAR
# =========================================================
with st.sidebar:
    st.header("Configuration")

    st.session_state.brand = st.selectbox(
        "Brand",
        list(BRANDS.keys()),
        format_func=lambda x: BRANDS[x]["display"],
    )

    st.session_state.mode = st.radio(
        "Mode",
        ["Sales Call Generation", "Medical / Product Q&A"],
    )

    b = BRANDS[st.session_state.brand]

    st.session_state.segment = st.selectbox("Segment", b["segments"])
    st.session_state.persona = st.selectbox("Persona", b["personas"])
    st.session_state.barriers = st.multiselect("Barriers", b["barriers"])
    st.session_state.tone = st.selectbox(
        "Tone", ["Executive", "Coaching", "Persuasive", "Clinical"]
    )

    if st.button("Clear Chat"):
        st.session_state.chat = []


# =========================================================
# MAIN UI
# =========================================================
st.title("💡 AI Sales Call Assistant")

query = st.text_area("Your input", height=120)
send = st.button("Send")

if send and query.strip():
    st.session_state.chat.append({"role": "user", "content": query})

    if st.session_state.mode == "Sales Call Generation":
        docs = (
            load_documents(st.session_state.brand, "medical")
            + load_documents(st.session_state.brand, "sales")
        )
        retrieved = retrieve(query, docs)

        answer = generate_sales_call(
            {
                "brand": BRANDS[st.session_state.brand]["display"],
                "segment": st.session_state.segment,
                "persona": st.session_state.persona,
                "barriers": st.session_state.barriers,
                "tone": st.session_state.tone,
            },
            retrieved,
        )

    else:
        docs = load_documents(st.session_state.brand, "medical")
        retrieved = retrieve(query, docs)
        answer = answer_question(query, retrieved)

    st.session_state.chat.append({"role": "assistant", "content": answer})


# =========================================================
# CHAT RENDER
# =========================================================
for m in st.session_state.chat:
    if m["role"] == "user":
        st.markdown(f"**You:** {escape(m['content'])}")
    else:
        st.markdown(f"**AI:**\n\n{m['content']}")

st.caption(
    "⚠️ Internal training tool. Responses limited to approved documents only."
)
