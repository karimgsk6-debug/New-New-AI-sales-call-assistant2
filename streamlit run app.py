# =====================================================
# app_final_merged.py — FULL MERGED ENTERPRISE VERSION
# =====================================================
# AI-generated; for training; verified against approved sources.
# =====================================================

import streamlit as st
import os, re, json, io, base64, tempfile, hashlib
from datetime import datetime
from html import escape

# ===============================
# CONFIG — COMPLIANCE FIRST
# ===============================
GROQ_API_KEY = "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"
MODEL_NAME = "llama-3.1-70b-versatile"
MIN_SCORE = 0.35
AUDIT_LOG = "./audit_log.jsonl"

# ===============================
# OPTIONAL IMPORTS
# ===============================
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
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

try:
    from gtts import gTTS
except Exception:
    gTTS = None

# ===============================
# SYSTEM PROMPT (LOCKED)
# ===============================
SYSTEM_PROMPT = """
You are a compliance-first pharmaceutical AI assistant.

STRICT RULES:
- Use ONLY retrieved approved text.
- Every medical or product statement MUST be grounded.
- NO off-label claims.
- If evidence is insufficient, explicitly decline.

Tone: professional, compliant, concise.

Always append:
"AI-generated; for training; verified against approved sources."
"""

# ===============================
# GROQ CLIENT
# ===============================
def load_groq():
    if not GROQ_API_KEY or Groq is None:
        return None
    return Groq(api_key=GROQ_API_KEY)

groq_client = load_groq()

# ===============================
# AUDIT LOGGING
# ===============================
def audit_log(user_input, sources, response):
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "input": user_input,
        "sources": sources,
        "response_hash": hashlib.sha256(response.encode()).hexdigest()
    }
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")

# ===============================
# LOCAL SEARCH (ON-LABEL RAG)
# ===============================
def local_search(query, chunks, metas, top_n=6):
    if not chunks:
        return []

    if SKLEARN_AVAILABLE:
        vectorizer = TfidfVectorizer(stop_words="english")
        X = vectorizer.fit_transform(chunks + [query])
        sims = linear_kernel(X[-1], X[:-1]).flatten()
        idxs = sims.argsort()[::-1][:top_n]

        results = []
        for i in idxs:
            if sims[i] < MIN_SCORE:
                continue
            results.append({
                "score": float(sims[i]),
                "text": chunks[i],
                "meta": metas[i]
            })
        return results
    return []

# ===============================
# COMPLIANCE ENFORCEMENT
# ===============================
def enforce_only_from_rag(snippets):
    if not snippets:
        raise ValueError("I cannot answer based on approved sources.")

def enforce_citations(text):
    if "[" not in text or "]" not in text:
        raise ValueError("Blocked: Missing citations.")

def off_label_block(text, snippets):
    approved = " ".join(s["text"] for s in snippets)
    for sent in re.split(r"[.!?]", text):
        if sent.strip() and sent.strip() not in approved:
            raise ValueError("Blocked: Potential off-label or hallucinated content.")

# ===============================
# GROQ COMPLETION (SAFE)
# ===============================
def groq_generate(prompt):
    if not groq_client:
        return "Groq client not available."

    resp = groq_client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0.2,
        top_p=0.9,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )
    return resp.choices[0].message.content

# ===============================
# SALES CALL GENERATION
# ===============================
def generate_sales_call(user_prompt, persona, tone, chunks, metas):
    snippets = local_search(user_prompt, chunks, metas)
    enforce_only_from_rag(snippets)

    context = "\n".join(
        f"[{s['meta']['filename']} | section {s['meta']['start']}]\n{s['text']}"
        for s in snippets
    )

    prompt = f"""
Generate a full compliant sales call with sections:
Opening
Discovery
On-label Key Messages
Objection Handling
Next Steps

Persona: {persona}
Tone: {tone}

USE ONLY THE TEXT BELOW.

{context}
"""

    answer = groq_generate(prompt)
    enforce_citations(answer)
    off_label_block(answer, snippets)

    audit_log(user_prompt, snippets, answer)

    return answer + "\n\nAI-generated; for training; verified against approved sources."

# ===============================
# STREAMLIT UI (UNCHANGED CORE)
# ===============================
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")
st.title("🧠 AI Sales Call Assistant")
st.caption("AI-generated; for training; verified against approved sources.")

# ===============================
# LOAD BRAND FILES
# ===============================
def read_files(folder):
    texts, metas = [], []
    if not folder or not os.path.exists(folder):
        return texts, metas

    for f in os.listdir(folder):
        if f.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(os.path.join(folder, f))
            txt = "".join(p.extract_text() or "" for p in reader.pages)
        else:
            try:
                txt = open(os.path.join(folder, f), encoding="utf-8", errors="ignore").read()
            except Exception:
                continue

        sentences = re.split(r"(?<=[.!?])\s+", txt)
        for i, s in enumerate(sentences):
            if s.strip():
                texts.append(s.strip())
                metas.append({"filename": f, "start": i})
    return texts, metas

brand = st.selectbox("Brand", ["shingrix", "jemperli", "trelegy"])
persona = st.selectbox("Persona", ["Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"])
tone = st.selectbox("Tone", ["executive", "coaching", "persuasive", "clinical"])

refs_path = f".devcontainer/references/{brand}"
sales_path = f".devcontainer/SalesModule/{brand}"

chunks_r, metas_r = read_files(refs_path)
chunks_s, metas_s = read_files(sales_path)

chunks = chunks_r + chunks_s
metas = metas_r + metas_s

user_input = st.text_area("Ask or request a sales call")

if st.button("Generate"):
    try:
        result = generate_sales_call(user_input, persona, tone, chunks, metas)
        st.markdown(result)
    except Exception as e:
        st.error(str(e))

st.markdown(
    "<hr><small>Internal training tool. Medical content must be verified against approved sources.</small>",
    unsafe_allow_html=True,
)
