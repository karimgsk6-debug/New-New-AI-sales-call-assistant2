import os
import io
import json
import hashlib
import datetime
import numpy as np
import streamlit as st
import pdfplumber
import docx
from gtts import gTTS
from groq import Groq
from sentence_transformers import SentenceTransformer
import faiss

# ================= CONFIG =================
MODEL_NAME = "llama-3.1-70b-versatile"
MIN_SCORE = 0.35
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
SALES_ROOT = ".devcontainer/SalesModule"
AUDIT_FILE = "audit_log.jsonl"

client = Groq(api_key=os.getenv("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"))
embedder = SentenceTransformer(EMBED_MODEL)

# ================= BRAND DATA =================
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HZ not considered a risk", "No time", "Cost concerns", "Efficacy doubts"],
        "call_flow": ["Prepare", "Engage", "Create Opportunity", "Influence", "Close"]
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target", "Trial", "Routine", "Advocacy"],
        "personas": ["Data-Driven", "Skeptical", "Innovator", "Late Adopter"],
        "barriers": ["Safety", "Eligibility", "Access"],
        "call_flow": ["COCO", "Anchor", "Engage", "Close"]
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["COPD GP", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Access", "Technique", "Side effects"],
        "call_flow": ["Prepare", "Engage", "Demonstrate", "Close"]
    }
}

# ================= STORAGE =================
if "vectors" not in st.session_state:
    st.session_state.vectors = []
    st.session_state.meta = []
    st.session_state.index = faiss.IndexFlatL2(384)

# ================= UTILS =================
def extract_text(file):
    if file.name.endswith(".pdf"):
        with pdfplumber.open(file) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    elif file.name.endswith(".docx"):
        doc = docx.Document(file)
        return "\n".join(p.text for p in doc.paragraphs)
    else:
        return file.read().decode("utf-8")

def ingest(text, brand, doc_type, doc_name):
    chunks = [text[i:i+1200] for i in range(0, len(text), 1000)]
    for i, chunk in enumerate(chunks):
        vec = embedder.encode(chunk)
        st.session_state.index.add(np.array([vec]).astype("float32"))
        st.session_state.vectors.append(vec)
        st.session_state.meta.append({
            "brand": brand,
            "doc_type": doc_type,
            "doc": doc_name,
            "section": f"chunk_{i}",
            "text": chunk
        })

def retrieve(query, brand):
    qv = embedder.encode(query)
    D, I = st.session_state.index.search(np.array([qv]).astype("float32"), 5)
    results = []
    for d, i in zip(D[0], I[0]):
        if i == -1:
            continue
        score = 1 / (1 + d)
        meta = st.session_state.meta[i]
        if meta["brand"] == brand and score >= MIN_SCORE:
            results.append({**meta, "score": score})
    return results

def audit_log(input_json, sources, response):
    with open(AUDIT_FILE, "a") as f:
        f.write(json.dumps({
            "time": str(datetime.datetime.utcnow()),
            "input": input_json,
            "sources": sources,
            "hash": hashlib.sha256(response.encode()).hexdigest()
        }) + "\n")

def tts(text):
    audio = gTTS(text)
    buf = io.BytesIO()
    audio.write_to_fp(buf)
    st.audio(buf.getvalue(), format="audio/mp3")

# ================= UI =================
st.set_page_config("AI Sales Assistant", layout="wide")
st.title("🧠 AI Sales Assistant (Compliance-First)")

brand = st.selectbox("Brand", list(brand_data.keys()), format_func=lambda x: brand_data[x]["display"])
mode = st.radio("Mode", ["Sales Call", "Medical Q&A"])

# ================= UPLOADER =================
st.sidebar.header("📄 Upload Approved Documents")
uploaded = st.sidebar.file_uploader("Upload PDF / DOCX / TXT", accept_multiple_files=True)

if uploaded:
    for f in uploaded:
        try:
            text = extract_text(f)
            if text.strip():
                ingest(text, brand, "selling_module", f.name)
                st.sidebar.success(f"Ingested {f.name}")
            else:
                st.sidebar.error(f"No text in {f.name}")
        except Exception as e:
            st.sidebar.error(f"{f.name}: {e}")

# ================= SALES CALL =================
if mode == "Sales Call":
    persona = st.selectbox("Persona", brand_data[brand]["personas"])
    barrier = st.multiselect("Barriers", brand_data[brand]["barriers"])

    if st.button("Generate Call"):
        query = f"{brand} selling module key messages"
        docs = retrieve(query, brand)

        if not docs:
            st.error("❌ No approved selling module found")
            st.stop()

        context = "\n".join(d["text"] for d in docs)

        prompt = f"""
You are a compliance-first assistant.
ONLY use the content below.

Create a sales call with sections:
Opening, Discovery, Key Messages, Objection Handling, Close.

Content:
{context}
"""

        resp = client.chat.completions.create(
            model=MODEL_NAME,
            temperature=0.2,
            messages=[{"role":"system","content":"ONLY from provided text."},
                      {"role":"user","content":prompt}]
        )

        answer = resp.choices[0].message.content
        st.markdown(answer)
        tts(answer)
        audit_log({"mode":"call","brand":brand}, [d["doc"] for d in docs], answer)

# ================= Q&A =================
else:
    q = st.text_input("Ask medical / product question")

    if st.button("Answer"):
        docs = retrieve(q, brand)
        if not docs:
            st.warning("I cannot answer based on approved sources.")
            st.stop()

        context = "\n".join(d["text"] for d in docs)

        prompt = f"""
Answer ONLY using the content below.
Provide citations.

Content:
{context}
"""

        resp = client.chat.completions.create(
            model=MODEL_NAME,
            temperature=0.2,
            messages=[{"role":"system","content":"Compliance only."},
                      {"role":"user","content":prompt}]
        )

        answer = resp.choices[0].message.content
        st.markdown(answer)
        tts(answer)
        audit_log({"mode":"qa","brand":brand,"q":q}, [d["doc"] for d in docs], answer)

st.caption("⚠️ AI-generated | Training use only | Verified against approved sources")
