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
# CONFIG
# =========================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
RAG_PATH = "./rag_index"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MIN_SCORE = 0.35

BRANDS = ["Shingrix", "Jemperli", "Trelegy"]
LANGUAGES = ["English", "Arabic", "French"]

DISCLAIMER = "⚠️ AI-generated; for training only; verified against approved sources."

# =========================================================
# CLIENTS
# =========================================================
embedder = SentenceTransformer(EMBED_MODEL)
groq = Groq(api_key=GROQ_API_KEY)

# =========================================================
# FILE UTILITIES
# =========================================================
def extract_text(path):
    if path.endswith(".pdf"):
        with pdfplumber.open(path) as pdf:
            return "\n".join(p.page.extract_text() or "" for p in pdf.pages)
    if path.endswith(".docx"):
        doc = docx.Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    if path.endswith(".html"):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
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
# INGESTION
# =========================================================
def ingest():
    docs = []

    sources = {
        "sales_module": ".devcontainer/SalesModule",
        "medical_reference": ".devcontainer/references"
    }

    for doc_type, base in sources.items():
        for brand in ["shingrix", "jemperli", "trelegy"]:
            folder = Path(base) / brand
            if not folder.exists():
                continue

            for file in folder.glob("*"):
                text = extract_text(str(file))
                if not text.strip():
                    continue

                for i, chunk in enumerate(chunk_text(text)):
                    docs.append({
                        "text": chunk,
                        "brand": brand.capitalize(),
                        "document_type": doc_type,
                        "doc_name": file.name,
                        "section_id": f"{file.name}_{i}",
                        "version": "1.0",
                        "effective_date": "2025-01-01"
                    })

    if not docs:
        return False

    embeddings = embedder.encode([d["text"] for d in docs])
    faiss.normalize_L2(embeddings)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(np.array(embeddings))

    os.makedirs(RAG_PATH, exist_ok=True)
    faiss.write_index(index, f"{RAG_PATH}/index.faiss")

    with open(f"{RAG_PATH}/meta.json", "w") as f:
        json.dump(docs, f)

    return True

# =========================================================
# SAFE LOAD
# =========================================================
def index_exists():
    return (
        os.path.exists(f"{RAG_PATH}/index.faiss")
        and os.path.exists(f"{RAG_PATH}/meta.json")
    )

def load_index():
    index = faiss.read_index(f"{RAG_PATH}/index.faiss")
    with open(f"{RAG_PATH}/meta.json") as f:
        meta = json.load(f)
    return index, meta

# =========================================================
# RETRIEVAL
# =========================================================
def retrieve(query, brand, doc_type):
    if not index_exists():
        return []

    index, meta = load_index()

    q_emb = embedder.encode([query])
    faiss.normalize_L2(q_emb)

    scores, ids = index.search(q_emb, 6)

    results = []
    for score, idx in zip(scores[0], ids[0]):
        if score >= MIN_SCORE:
            m = meta[idx]
            if m["brand"] == brand and m["document_type"] == doc_type:
                m["score"] = float(score)
                results.append(m)
    return results

# =========================================================
# LLM
# =========================================================
def llm(prompt):
    res = groq.chat.completions.create(
        model="llama-3.1-70b-versatile",
        temperature=0.2,
        top_p=0.9,
        messages=[
            {"role": "system", "content": "Compliance-first assistant. Use ONLY approved content."},
            {"role": "user", "content": prompt}
        ]
    )
    return res.choices[0].message.content

# =========================================================
# AUDIT
# =========================================================
def audit(input_data, sources, output):
    record = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "input": input_data,
        "sources": [s["section_id"] for s in sources],
        "hash": hashlib.sha256(output.encode()).hexdigest()
    }
    with open("audit.log", "a") as f:
        f.write(json.dumps(record) + "\n")

# =========================================================
# UI
# =========================================================
st.set_page_config(page_title="AI MR Sales Assistant", layout="wide")

st.sidebar.title("⚙️ Setup")
brand = st.sidebar.selectbox("Brand", BRANDS)
language = st.sidebar.selectbox("Language", LANGUAGES)
mode = st.sidebar.radio("Mode", ["Sales Call", "Medical Q&A"])

if st.sidebar.button("📥 Ingest / Refresh Documents"):
    ok = ingest()
    if ok:
        st.sidebar.success("Documents indexed successfully")
    else:
        st.sidebar.error("No documents found")

st.title("🤖 AI Sales Assistant")

if not index_exists():
    st.warning("⚠️ No index found. Please ingest documents from the sidebar.")

# =========================================================
# SALES CALL
# =========================================================
if mode == "Sales Call":
    persona = st.selectbox("HCP Persona", ["Skeptic", "Advocate", "Data-driven"])
    barriers = st.multiselect("Barriers", ["Safety", "Efficacy", "Cost", "Access"])
    style = st.selectbox("Personal Style", ["Consultative", "Concise", "Scientific"])

    if st.button("Generate Sales Call"):
        chunks = retrieve("selling module", brand, "sales_module")

        if not chunks:
            st.error("❌ Brand selling module not found or not indexed.")
        else:
            context = "\n\n".join(
                f"[{c['doc_name']} | {c['section_id']} | v{c['version']} | {c['effective_date']}]\n{c['text']}"
                for c in chunks
            )

            prompt = f"""
Create a compliant sales-call in {language}.

Persona: {persona}
Barriers: {barriers}
Style: {style}

RULES:
- Use ONLY approved content
- Cite after every section
- No off-label claims

Approved Content:
{context}

Sections:
Opening
Discovery
On-label Key Messages
Objection Handling
Next Steps
"""
            out = llm(prompt)
            audit(prompt, chunks, out)
            st.success(out)
            st.caption(DISCLAIMER)

# =========================================================
# MEDICAL Q&A
# =========================================================
if mode == "Medical Q&A":
    q = st.text_input("Ask a medical/product question")

    if st.button("Ask"):
        chunks = retrieve(q, brand, "medical_reference")

        if not chunks:
            st.error("❌ I cannot answer based on approved sources.")
        else:
            context = "\n\n".join(
                f"[{c['doc_name']} | {c['section_id']} | v{c['version']} | {c['effective_date']}]\n{c['text']}"
                for c in chunks
            )

            prompt = f"""
Answer ONLY using approved content.
Cite every statement.

Question:
{q}

Approved Content:
{context}
"""
            out = llm(prompt)
            audit(q, chunks, out)
            st.success(out)
            st.caption(DISCLAIMER)

# =========================================================
# FOOTER
# =========================================================
st.markdown("---")
st.markdown("© 2025 AI MR Training Platform | Compliance-first | CRM-ready")
