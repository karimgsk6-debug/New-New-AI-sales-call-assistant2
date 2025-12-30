import os
import json
import hashlib
import datetime
from pathlib import Path

import streamlit as st
import numpy as np
import faiss
import pdfplumber
import docx
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from groq import Groq

# =========================================================
# CONFIGURATION
# =========================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
RAG_PATH = "./rag_index"
EMBED_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MIN_SCORE = 0.35
LANGUAGES = ["English", "Arabic", "French"]

DISCLAIMER = "⚠️ AI-generated; for training only; verified against approved sources."

# =========================================================
# CLIENTS
# =========================================================
embedder = SentenceTransformer(EMBED_MODEL_NAME)
groq_client = Groq(api_key=GROQ_API_KEY)

# =========================================================
# UTILITIES
# =========================================================
def extract_text(file_path):
    if file_path.endswith(".pdf"):
        with pdfplumber.open(file_path) as pdf:
            return "\n".join(p.page.extract_text() or "" for p in pdf.pages)
    elif file_path.endswith(".docx"):
        doc = docx.Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    elif file_path.endswith(".html"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return BeautifulSoup(f.read(), "html.parser").get_text()
    return ""

def chunk_text(text, size=1200, overlap=120):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + size])
        start += size - overlap
    return chunks

# =========================================================
# RAG INGESTION
# =========================================================
def ingest_documents():
    docs = []
    base_paths = {
        "sales_module": ".devcontainer/SalesModule",
        "medical_reference": ".devcontainer/references"
    }

    for doc_type, base in base_paths.items():
        for brand in ["shingrix", "jemperli", "trelegy"]:
            folder = Path(base) / brand
            if not folder.exists():
                continue
            for file in folder.glob("*"):
                text = extract_text(str(file))
                for idx, chunk in enumerate(chunk_text(text)):
                    docs.append({
                        "text": chunk,
                        "brand": brand.capitalize(),
                        "document_type": doc_type,
                        "doc_name": file.name,
                        "section_id": f"{file.name}_chunk_{idx}",
                        "version": "1.0",
                        "effective_date": "2025-01-01"
                    })

    if not docs:
        return None, []

    embeddings = embedder.encode([d["text"] for d in docs], show_progress_bar=True)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    faiss.normalize_L2(embeddings)
    index.add(np.array(embeddings))

    os.makedirs(RAG_PATH, exist_ok=True)
    faiss.write_index(index, f"{RAG_PATH}/index.faiss")
    with open(f"{RAG_PATH}/meta.json", "w") as f:
        json.dump(docs, f)

    return index, docs

def load_index():
    index = faiss.read_index(f"{RAG_PATH}/index.faiss")
    with open(f"{RAG_PATH}/meta.json") as f:
        meta = json.load(f)
    return index, meta

# =========================================================
# RETRIEVAL
# =========================================================
def retrieve(query, brand, doc_type, top_k=6):
    index, meta = load_index()
    q_emb = embedder.encode([query])
    faiss.normalize_L2(q_emb)
    scores, ids = index.search(q_emb, top_k)

    results = []
    for score, idx in zip(scores[0], ids[0]):
        if score >= MIN_SCORE:
            m = meta[idx]
            if m["brand"] == brand and m["document_type"] == doc_type:
                m["score"] = float(score)
                results.append(m)
    return results

# =========================================================
# POLICY / GUARDRAILS
# =========================================================
def enforce_sources(chunks):
    return len(chunks) > 0

def decline():
    return "❌ I cannot answer based on approved sources."

# =========================================================
# LLM CALL
# =========================================================
def generate(prompt):
    response = groq_client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a compliance-first medical sales training assistant. ONLY use retrieved content."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2,
        top_p=0.9
    )
    return response.choices[0].message.content

# =========================================================
# AUDIT LOG
# =========================================================
def audit_log(input_data, sources, output):
    record = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "input": input_data,
        "sources": [s["section_id"] for s in sources],
        "response_hash": hashlib.sha256(output.encode()).hexdigest()
    }
    with open("audit.log", "a") as f:
        f.write(json.dumps(record) + "\n")

# =========================================================
# STREAMLIT UI
# =========================================================
st.set_page_config(layout="wide", page_title="AI MR Sales Assistant")

st.sidebar.title("📊 Configuration")
language = st.sidebar.selectbox("Language", LANGUAGES)
brand = st.sidebar.selectbox("Brand", ["Shingrix", "Jemperli", "Trelegy"])
mode = st.sidebar.radio("Mode", ["Sales Call", "Medical Q&A"])

st.title("🤖 AI Sales Assistant for Medical Representatives")

if st.sidebar.button("📥 Ingest / Refresh Documents"):
    ingest_documents()
    st.sidebar.success("Documents ingested successfully")

# =========================================================
# SALES CALL MODE
# =========================================================
if mode == "Sales Call":
    persona = st.selectbox("HCP Persona", ["Skeptic", "Advocate", "Data-driven"])
    barriers = st.multiselect("Barriers", ["Safety", "Efficacy", "Cost", "Access"])
    style = st.selectbox("Personal Style", ["Consultative", "Concise", "Scientific"])

    if st.button("Generate Sales Call"):
        chunks = retrieve("selling module", brand, "sales_module")
        if not enforce_sources(chunks):
            st.error("❌ Selling module not found. Please upload it.")
        else:
            context = "\n\n".join(
                f"[{c['doc_name']} | {c['section_id']} | v{c['version']} | {c['effective_date']}]\n{c['text']}"
                for c in chunks
            )

            prompt = f"""
Create a compliant sales-call script in {language}.

Persona: {persona}
Barriers: {barriers}
Style: {style}

STRICT RULES:
- Use ONLY approved content below
- No off-label statements
- Cite after each section

Approved Content:
{context}

Sections:
1. Opening
2. Discovery
3. On-label Key Messages
4. Objection Handling
5. Next Steps
"""
            output = generate(prompt)
            audit_log(prompt, chunks, output)
            st.success(output)
            st.caption(DISCLAIMER)

# =========================================================
# MEDICAL Q&A MODE
# =========================================================
if mode == "Medical Q&A":
    question = st.text_input("Ask a medical or product question")

    if st.button("Ask"):
        chunks = retrieve(question, brand, "medical_reference")
        if not enforce_sources(chunks):
            st.error(decline())
        else:
            context = "\n\n".join(
                f"[{c['doc_name']} | {c['section_id']} | v{c['version']} | {c['effective_date']}]\n{c['text']}"
                for c in chunks
            )

            prompt = f"""
Answer the question ONLY using the approved content.
Cite every statement.

Question:
{question}

Approved Content:
{context}
"""
            output = generate(prompt)
            audit_log(question, chunks, output)
            st.success(output)
            st.caption(DISCLAIMER)

# =========================================================
# FOOTER
# =========================================================
st.markdown("---")
st.markdown("© 2025 AI MR Training Platform | Compliance-first | CRM-ready")
