import os
import json
import uuid
import hashlib
from datetime import datetime
from typing import List

import streamlit as st
from groq import Groq

import faiss
import numpy as np
import pdfplumber
import docx
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer

# =========================
# CONFIG
# =========================
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 120
MIN_SCORE = 0.35

SALES_MODULE_ROOT = ".devcontainer/SalesModule"
REFERENCE_ROOT = ".devcontainer/references"

LLM_MODEL = "llama-3.1-70b-versatile"

DISCLAIMER = "AI-generated; for training only; verified against approved sources."

# =========================
# GROQ CLIENT
# =========================
client = Groq(api_key=os.getenv("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"))

# =========================
# VECTOR STORE
# =========================
class VectorStore:
    def __init__(self, dim):
        self.index = faiss.IndexFlatIP(dim)
        self.meta = []

    def add(self, embeddings, metadata):
        self.index.add(np.array(embeddings).astype("float32"))
        self.meta.extend(metadata)

    def search(self, emb, k=6):
        scores, idxs = self.index.search(np.array([emb]).astype("float32"), k)
        results = []
        for s, i in zip(scores[0], idxs[0]):
            if i != -1:
                results.append((float(s), self.meta[i]))
        return results

# =========================
# INGESTION
# =========================
@st.cache_resource
def build_store():
    model = SentenceTransformer(EMBED_MODEL)
    store = VectorStore(model.get_sentence_embedding_dimension())

    def extract_text(path):
        if path.endswith(".pdf"):
            with pdfplumber.open(path) as pdf:
                return "\n".join(p.page.extract_text() or "" for p in pdf.pages)
        elif path.endswith(".docx"):
            d = docx.Document(path)
            return "\n".join(p.text for p in d.paragraphs)
        elif path.endswith(".html"):
            return BeautifulSoup(open(path), "html.parser").get_text()
        return ""

    def chunk(txt):
        chunks = []
        i = 0
        while i < len(txt):
            chunks.append(txt[i:i + CHUNK_SIZE])
            i += CHUNK_SIZE - CHUNK_OVERLAP
        return chunks

    def ingest(root, brand, doc_type):
        for r, _, files in os.walk(root):
            for f in files:
                if not f.lower().endswith((".pdf", ".docx", ".html")):
                    continue
                text = extract_text(os.path.join(r, f))
                for c in chunk(text):
                    emb = model.encode(c, normalize_embeddings=True)
                    store.add(
                        [emb],
                        [{
                            "id": str(uuid.uuid4()),
                            "brand": brand.lower(),
                            "document_type": doc_type,
                            "doc_name": f,
                            "version": "1.0",
                            "effective_date": "2024-01-01",
                            "text": c
                        }]
                    )

    for brand in ["shingrix", "jemperli", "trelegy"]:
        ingest(f"{SALES_MODULE_ROOT}/{brand}", brand, "selling_module")
        ingest(f"{REFERENCE_ROOT}/{brand}", brand, "medical_reference")

    return store, model

# =========================
# RETRIEVAL
# =========================
def retrieve(store, model, query, brand, doc_type=None):
    emb = model.encode(query, normalize_embeddings=True)
    results = store.search(emb)
    filtered = []
    for score, m in results:
        if score < MIN_SCORE:
            continue
        if m["brand"] != brand.lower():
            continue
        if doc_type and m["document_type"] != doc_type:
            continue
        filtered.append((score, m))
    return filtered

# =========================
# POLICY
# =========================
def enforce_sources(chunks):
    return len(chunks) > 0

def decline():
    return "⚠️ I cannot answer based on approved sources."

# =========================
# AUDIT
# =========================
def audit_log(input_payload, sources, output):
    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "input": input_payload,
        "sources": [s[1]["id"] for s in sources],
        "hash": hashlib.sha256(output.encode()).hexdigest()
    }
    with open("audit.log", "a") as f:
        f.write(json.dumps(record) + "\n")

# =========================
# LLM CALL
# =========================
def generate(prompt):
    r = client.chat.completions.create(
        model=LLM_MODEL,
        temperature=0.2,
        top_p=0.9,
        messages=[
            {"role": "system", "content":
             "You are a compliance-first assistant. "
             "You MUST ONLY use retrieved text. "
             "If not grounded in citations, decline."},
            {"role": "user", "content": prompt}
        ]
    )
    return r.choices[0].message.content

# =========================
# PERSONA-ADAPTIVE OBJECTION TREE
# =========================
def adapt_objections(barriers: List[str], persona: str):
    tree = []
    for b in barriers:
        if persona.lower() == "evidence-driven":
            tree.append(f"Barrier: {b} → Respond with clinical evidence and approved citations.")
        elif persona.lower() == "emotional":
            tree.append(f"Barrier: {b} → Respond empathetically and reference patient stories.")
        else:
            tree.append(f"Barrier: {b} → Respond with standard approved messaging.")
    return "\n".join(tree)

# =========================
# STREAMLIT UI
# =========================
st.set_page_config(page_title="AI Sales Assistant", layout="wide")

# Sidebar
with st.sidebar:
    st.title("🧠 MR Assistant Sidebar")
    st.markdown("""
    **Instructions:**
    1. Select Brand
    2. Choose Mode: Sales-Call or Q&A
    3. Enter Persona / Question / Barriers
    4. Click Generate
    """)
    st.markdown("---")
    st.selectbox("Language", ["English", "French", "Spanish"], key="lang")

st.title("AI Sales Assistant (Groq + Llama-3)")

# Load vector store
store, embed_model = build_store()

# Tabs
tab1, tab2 = st.tabs(["Sales Call", "Medical / Product Q&A"])

# =========================
# SALES CALL TAB
# =========================
with tab1:
    brand = st.selectbox("Brand", ["Shingrix", "Jemperli", "Trelegy"], key="brand_call")
    persona = st.text_input("HCP Persona", "Evidence-driven", key="persona")
    segment = st.text_input("HCP Segment", "GP", key="segment")
    barriers = st.text_input("Barriers (comma-separated)", "safety", key="barriers")
    style = st.text_input("Personal Style", "consultative", key="style")

    if st.button("Generate Sales Call"):
        barrier_list = [b.strip() for b in barriers.split(",")]
        chunks = retrieve(store, embed_model, "sales call key messages", brand, "selling_module")

        if not enforce_sources(chunks):
            st.error(decline())
        else:
            context = "\n\n".join(
                f"[{c['doc_name']} | v{c['version']} | {c['effective_date']}]\n{c['text']}"
                for _, c in chunks
            )
            objection_tree = adapt_objections(barrier_list, persona)

            prompt = f"""
Using ONLY the content below, generate a compliant sales-call script with:
Opening, Discovery, On-label Key Messages, Objection Handling, Next Steps.

Persona: {persona}
Segment: {segment}
Barriers: {barriers}
Personal Style: {style}
Objection Tree:
{objection_tree}

Approved Content:
{context}
"""
            out = generate(prompt)
            audit_log(prompt, chunks, out)
            st.success(out)
            st.caption(DISCLAIMER)

# =========================
# Q&A TAB
# =========================
with tab2:
    brand_q = st.selectbox("Brand", ["Shingrix", "Jemperli", "Trelegy"], key="brand_qa")
    question = st.text_input("Medical / Product Question", key="question")

    if st.button("Ask Question"):
        chunks = retrieve(store, embed_model, question, brand_q, "medical_reference")
        if not enforce_sources(chunks):
            st.error(decline())
        else:
            context = "\n\n".join(
                f"[{c['doc_name']} | v{c['version']} | {c['effective_date']}]\n{c['text']}"
                for _, c in chunks
            )
            prompt = f"""
Answer ONLY using the approved content below.
Include citations after each statement.

Question: {question}

Approved Content:
{context}
"""
            out = generate(prompt)
            audit_log(question, chunks, out)
            st.success(out)
            st.caption(DISCLAIMER)

# =========================
# FOOTER
# =========================
st.markdown("---")
st.markdown(
    f"<div style='text-align:center; font-size:12px'>"
    f"AI Sales Assistant | Version 1.0 | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    f"</div>", unsafe_allow_html=True
)
