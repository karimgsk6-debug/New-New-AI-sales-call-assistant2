# ==========================================================
# AI SALES ASSISTANT – STREAMLIT (COMPLIANCE-FIRST)
# Groq + Llama 3.1 + Local RAG + Personas + Voice
# ==========================================================
# AI-generated; for training; verified against approved sources
# ==========================================================

import os
import json
import uuid
import hashlib
from datetime import datetime
import streamlit as st
from groq import Groq

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

import pdfplumber
import docx
from gtts import gTTS
import tempfile

# ==========================================================
# CONFIG
# ==========================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
RAG_PATH = "./rag_index"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MIN_SCORE = 0.35

SALES_MODULE_ROOT = ".devcontainer/SalesModule"

os.makedirs(RAG_PATH, exist_ok=True)

# ==========================================================
# BRAND DATA
# ==========================================================
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas": ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
        "specialties": ["GP","Dermatologist","Geriatrician"],
        "call_flow": ["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Post-call Analysis"]
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas": ["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties": ["Oncologist","Medical Oncologist"],
        "call_flow": ["COCO","Anchor","Engage","Close"]
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness","Diagnosis","Adoption","Adherence"],
        "personas": ["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers": ["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties": ["GP","Pulmonologist","Respiratory Specialist"],
        "call_flow": ["Prepare","Engage","Demonstrate","Address Access","Close"]
    }
}

# ==========================================================
# INIT MODELS
# ==========================================================
client = Groq(api_key=GROQ_API_KEY)
embedder = SentenceTransformer(EMBED_MODEL)

INDEX_FILE = f"{RAG_PATH}/index.faiss"
META_FILE = f"{RAG_PATH}/meta.json"

if os.path.exists(INDEX_FILE):
    index = faiss.read_index(INDEX_FILE)
    metadata = json.load(open(META_FILE))
else:
    index = faiss.IndexFlatIP(384)
    metadata = []

# ==========================================================
# CORE UTILITIES
# ==========================================================
def save_index():
    faiss.write_index(index, INDEX_FILE)
    json.dump(metadata, open(META_FILE, "w"))

def audit_log(user, payload, sources, response):
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "user": user,
        "input": payload,
        "sources": sources,
        "hash": hashlib.sha256(response.encode()).hexdigest()
    }
    with open("audit.log", "a") as f:
        f.write(json.dumps(record) + "\n")

def extract_text_from_file(path):
    try:
        if path.lower().endswith(".pdf"):
            text = ""
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += t + "\n"
            return text.strip()

        elif path.lower().endswith(".docx"):
            d = docx.Document(path)
            return "\n".join(p.text for p in d.paragraphs if p.text.strip())

        elif path.lower().endswith(".txt"):
            return open(path, encoding="utf-8").read()

    except Exception:
        return ""

    return ""

def ingest_text(text, brand, doc_type, doc_name):
    if not text.strip():
        return
    emb = embedder.encode([text], normalize_embeddings=True)
    index.add(np.array(emb).astype("float32"))
    metadata.append({
        "id": str(uuid.uuid4()),
        "text": text,
        "brand": brand,
        "document_type": doc_type,
        "doc_name": doc_name,
        "version": "1.0",
        "effective_date": "2024-01-01"
    })
    save_index()

def retrieve(query, brand, doc_type=None, top_k=6):
    q = embedder.encode([query], normalize_embeddings=True)
    scores, idxs = index.search(np.array(q).astype("float32"), top_k)
    results = []
    for s, i in zip(scores[0], idxs[0]):
        if i == -1 or s < MIN_SCORE:
            continue
        m = metadata[i]
        if m["brand"] != brand:
            continue
        if doc_type and m["document_type"] != doc_type:
            continue
        results.append(m)
    return results

def tts_play(text):
    tts = gTTS(text)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
        tts.save(f.name)
        st.audio(f.name)

# ==========================================================
# AUTO-INGEST SELLING MODULES FROM .devcontainer/SalesModule
# ==========================================================
def ingest_selling_modules():
    existing = {(m["doc_name"], m["brand"]) for m in metadata if m["document_type"] == "selling_module"}

    for brand_key in brand_data:
        brand_folder = os.path.join(SALES_MODULE_ROOT, brand_key)
        if not os.path.exists(brand_folder):
            continue

        for file in os.listdir(brand_folder):
            path = os.path.join(brand_folder, file)
            if (file, brand_key) in existing:
                continue
            text = extract_text_from_file(path)
            ingest_text(text, brand_key, "selling_module", file)

ingest_selling_modules()

# ==========================================================
# PROMPT
# ==========================================================
SYSTEM_PROMPT = """
You are a compliance-first AI sales assistant.
ONLY use retrieved approved text.
If unsupported, decline.
No off-label content.
Cite sources explicitly.
"""

# ==========================================================
# STREAMLIT UI
# ==========================================================
st.set_page_config("AI Sales Assistant", layout="wide")
st.title("🧠 AI Sales Assistant")

user_id = st.sidebar.text_input("User ID", "mr_001")
brand_key = st.sidebar.selectbox("Brand", list(brand_data.keys()))
brand = brand_data[brand_key]

mode = st.sidebar.radio("Mode", ["Sales Call", "Medical Q&A"])
st.sidebar.caption("AI-generated; for training only")

# ==========================================================
# SALES CALL MODE (STRICTLY FROM .devcontainer/SalesModule)
# ==========================================================
if mode == "Sales Call":
    segment = st.selectbox("Segment", brand["segments"])
    persona = st.selectbox("Persona", brand["personas"])
    barriers = st.multiselect("Barriers", brand["barriers"])
    specialty = st.selectbox("Specialty", brand["specialties"])

    st.markdown("### Call Flow")
    st.write(" → ".join(brand["call_flow"]))

    if st.button("Generate Sales Call"):
        chunks = retrieve(
            query="selling module key messages",
            brand=brand_key,
            doc_type="selling_module"
        )

        if not chunks:
            st.error("❌ No selling module found in .devcontainer/SalesModule")
            st.stop()

        context = "\n\n".join(
            f"[{c['doc_name']} | v{c['version']} | {c['effective_date']}]\n{c['text']}"
            for c in chunks
        )

        prompt = f"""
Generate a compliant sales call using ONLY the content below.

Segment: {segment}
Persona: {persona}
Barriers: {", ".join(barriers)}
Specialty: {specialty}

Follow this call flow:
{brand['call_flow']}

Context:
{context}
"""

        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )

        text = response.choices[0].message.content
        audit_log(user_id, prompt, [c["doc_name"] for c in chunks], text)
        st.markdown(text)
        tts_play(text)

# ==========================================================
# MEDICAL Q&A MODE
# ==========================================================
if mode == "Medical Q&A":
    question = st.text_input("Medical / Product Question")

    if st.button("Ask"):
        chunks = retrieve(question, brand_key)

        if not chunks:
            st.error("❌ I cannot answer based on approved sources.")
            st.stop()

        context = "\n\n".join(
            f"[{c['doc_name']} | v{c['version']} | {c['effective_date']}]\n{c['text']}"
            for c in chunks
        )

        prompt = f"Question: {question}\n\nContext:\n{context}"

        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            temperature=0.2,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )

        text = response.choices[0].message.content
        audit_log(user_id, question, [c["doc_name"] for c in chunks], text)
        st.markdown(text)
        tts_play(text)
