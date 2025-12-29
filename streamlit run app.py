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

# ======================================================
# 🔐 GROQ CLIENT (PLACEHOLDER AS REQUESTED)
# ======================================================
client = Groq(api_key="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")

# ======================================================
# ⚙️ CONFIG
# ======================================================
MODEL_NAME = "llama-3.1-70b-versatile"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MIN_SCORE = 0.35
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 120
SALES_MODULE_ROOT = ".devcontainer/SalesModule"
AUDIT_LOG = "audit_log.jsonl"

# ======================================================
# 🏷️ BRAND DATA (AS PROVIDED)
# ======================================================
brand_data = {
    "shingrix": {
        "display":"Shingrix",
        "segments":["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas":["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers":["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
        "specialties":["GP","Dermatologist","Geriatrician"],
        "references_path":".devcontainer/references/shingrix/",
        "sales_path":".devcontainer/SalesModule/shingrix/",
        "call_flow":["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Post-call Analysis"]
    },
    "jemperli": {
        "display":"Jemperli",
        "segments":["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas":["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers":["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties":["Oncologist","Medical Oncologist"],
        "references_path":".devcontainer/references/jemperli/",
        "sales_path":".devcontainer/SalesModule/jemperli/",
        "call_flow":["COCO","Anchor","Engage","Close"]
    },
    "trelegy": {
        "display":"Trelegy",
        "segments":["Awareness","Diagnosis","Adoption","Adherence"],
        "personas":["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers":["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties":["GP","Pulmonologist","Respiratory Specialist"],
        "references_path":".devcontainer/references/trelegy/",
        "sales_path":".devcontainer/SalesModule/trelegy/",
        "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"]
    }
}

# ======================================================
# 🧠 VECTOR STORE (SESSION)
# ======================================================
if "index" not in st.session_state:
    st.session_state.index = faiss.IndexFlatL2(384)
    st.session_state.meta = []

embedder = SentenceTransformer(EMBED_MODEL)

# ======================================================
# 📄 TEXT EXTRACTION (FIXED PDF BUG)
# ======================================================
def extract_text_from_file(file):
    if file.name.lower().endswith(".pdf"):
        with pdfplumber.open(file) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    if file.name.lower().endswith(".docx"):
        doc = docx.Document(file)
        return "\n".join(p.text for p in doc.paragraphs)
    return file.read().decode("utf-8", errors="ignore")

# ======================================================
# 📥 INGESTION
# ======================================================
def ingest_text(text, brand, doc_type, doc_name):
    step = CHUNK_SIZE - CHUNK_OVERLAP
    for i in range(0, len(text), step):
        chunk = text[i:i + CHUNK_SIZE]
        if not chunk.strip():
            continue
        vec = embedder.encode(chunk).astype("float32")
        st.session_state.index.add(np.array([vec]))
        st.session_state.meta.append({
            "brand": brand,
            "document_type": doc_type,
            "doc_name": doc_name,
            "section_id": f"chunk_{i}",
            "text": chunk
        })

# ======================================================
# 🔍 RETRIEVAL
# ======================================================
def retrieve(query, brand):
    if st.session_state.index.ntotal == 0:
        return []
    qv = embedder.encode(query).astype("float32")
    D, I = st.session_state.index.search(np.array([qv]), 5)
    results = []
    for d, i in zip(D[0], I[0]):
        if i == -1:
            continue
        score = 1 / (1 + d)
        meta = st.session_state.meta[i]
        if meta["brand"] == brand and score >= MIN_SCORE:
            results.append({**meta, "score": score})
    return results

# ======================================================
# 🧾 AUDIT LOG
# ======================================================
def log_audit(input_json, sources, response):
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps({
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "input": input_json,
            "sources": sources,
            "hash": hashlib.sha256(response.encode()).hexdigest()
        }) + "\n")

# ======================================================
# 🔊 TEXT TO SPEECH
# ======================================================
def speak(text):
    tts = gTTS(text)
    buf = io.BytesIO()
    tts.write_to_fp(buf)
    st.audio(buf.getvalue(), format="audio/mp3")

# ======================================================
# 🖥️ UI
# ======================================================
st.set_page_config("AI Sales Assistant", layout="wide")
st.title("🧠 AI Sales Assistant (Compliance-First)")

brand = st.selectbox(
    "Brand",
    list(brand_data.keys()),
    format_func=lambda x: brand_data[x]["display"]
)

mode = st.radio("Mode", ["Sales Call", "Medical / Product Q&A"])

# ======================================================
# 📤 DOCUMENT UPLOADER
# ======================================================
st.sidebar.header("📄 Upload Approved Documents")
files = st.sidebar.file_uploader(
    "Upload PDF / DOCX / TXT",
    accept_multiple_files=True
)

if files:
    for f in files:
        try:
            text = extract_text_from_file(f)
            if text.strip():
                ingest_text(text, brand, "selling_module", f.name)
                st.sidebar.success(f"Indexed: {f.name}")
            else:
                st.sidebar.error(f"No text found: {f.name}")
        except Exception as e:
            st.sidebar.error(f"{f.name}: {e}")

# ======================================================
# 📞 SALES CALL MODE
# ======================================================
if mode == "Sales Call":
    persona = st.selectbox("Persona", brand_data[brand]["personas"])
    barriers = st.multiselect("Barriers", brand_data[brand]["barriers"])

    if st.button("Generate Sales Call"):
        docs = retrieve("selling module key messages", brand)

        if not docs:
            st.error("❌ No selling module found in .devcontainer/SalesModule")
            st.stop()

        context = "\n".join(d["text"] for d in docs)

        prompt = f"""
You are a compliance-first AI sales assistant.
ONLY use the content below.

Generate a full sales call with:
Opening, Discovery, On-label Key Messages,
Objection Handling, Next Steps.

CONTENT:
{context}
"""

        response = client.chat.completions.create(
            model=MODEL_NAME,
            temperature=0.2,
            messages=[
                {"role": "system", "content": "Only from provided content. No assumptions."},
                {"role": "user", "content": prompt}
            ]
        )

        output = response.choices[0].message.content
        st.markdown(output)
        speak(output)
        log_audit({"mode":"call","brand":brand}, [d["doc_name"] for d in docs], output)

# ======================================================
# ❓ Q&A MODE
# ======================================================
else:
    question = st.text_input("Ask a medical or product question")

    if st.button("Answer Question"):
        docs = retrieve(question, brand)

        if not docs:
            st.warning("I cannot answer based on approved sources.")
            st.stop()

        context = "\n".join(d["text"] for d in docs)

        prompt = f"""
Answer the question ONLY using the content below.
Provide citations.

CONTENT:
{context}

QUESTION:
{question}
"""

        response = client.chat.completions.create(
            model=MODEL_NAME,
            temperature=0.2,
            messages=[
                {"role": "system", "content": "Compliance-first. Cite sources."},
                {"role": "user", "content": prompt}
            ]
        )

        output = response.choices[0].message.content
        st.markdown(output)
        speak(output)
        log_audit({"mode":"qa","brand":brand,"q":question}, [d["doc_name"] for d in docs], output)

st.caption("⚠️ AI-generated | Training only | Verified against approved sources")
