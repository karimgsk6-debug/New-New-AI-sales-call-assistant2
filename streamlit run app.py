"""
AI SALES ASSISTANT – COMPLIANCE-FIRST (SINGLE FILE)

AI-generated; for training; verified against approved sources.

Features:
- Groq + llama-3.1-70b-versatile
- Local RAG (FAISS + sentence-transformers)
- Sales Call Generation
- Medical/Product Q&A
- On-label enforcement
- Off-label blocking
- Citation enforcement
- Brand selling-module enforcement
- Audit logging
"""

# =========================
# CONFIGURATION
# =========================

GROQ_API_KEY = "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"   # <-- REPLACE THIS
RAG_STORE_PATH = "./rag_index"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 120
MIN_SCORE = 0.35

AUDIT_LOG = "./audit.log"

# =========================
# DEPENDENCIES
# =========================

import os
import json
import hashlib
from datetime import datetime
from typing import List

import faiss
import numpy as np
from groq import Groq
from sentence_transformers import SentenceTransformer

from pypdf import PdfReader
from docx import Document
from bs4 import BeautifulSoup

# =========================
# INITIALIZATION
# =========================

os.makedirs(RAG_STORE_PATH, exist_ok=True)

client = Groq(api_key=GROQ_API_KEY)
embedder = SentenceTransformer(EMBEDDING_MODEL)

# =========================
# SYSTEM PROMPT (LOCKED)
# =========================

SYSTEM_PROMPT = """
You are a compliance-first pharmaceutical AI assistant.

STRICT RULES:
- You MUST ONLY use retrieved approved text.
- EVERY medical or product statement MUST have citations.
- If content is not grounded in retrieved sources, DECLINE.
- No off-label discussion.
- If evidence is insufficient, explicitly say so.

Tone:
Professional, compliant, concise.

Always include this disclaimer:
"AI-generated; for training; verified against approved sources."
"""

# =========================
# UTILITIES
# =========================

def audit_log(user_id, input_payload, sources, response):
    record = {
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat(),
        "input": input_payload,
        "sources": sources,
        "response_hash": hashlib.sha256(response.encode()).hexdigest()
    }
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


def extract_text(path: str) -> str:
    if path.endswith(".pdf"):
        return "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)
    if path.endswith(".docx"):
        return "\n".join(p.text for p in Document(path).paragraphs)
    if path.endswith(".html"):
        return BeautifulSoup(open(path, encoding="utf-8"), "html.parser").get_text()
    raise ValueError("Unsupported file format")


def chunk_text(text: str) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + CHUNK_SIZE])
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


# =========================
# RAG INGESTION
# =========================

def ingest_documents(directory, metadata):
    texts, metas = [], []

    for file in os.listdir(directory):
        full_path = os.path.join(directory, file)
        raw_text = extract_text(full_path)
        chunks = chunk_text(raw_text)

        for i, chunk in enumerate(chunks):
            texts.append(chunk)
            metas.append({
                "brand": metadata["brand"],
                "document_type": metadata["document_type"],
                "document_name": file,
                "section_id": f"{file}:{i}",
                "version": metadata["version"],
                "effective_date": metadata["effective_date"],
                "approval_status": metadata["approval_status"],
                "text": chunk
            })

    vectors = embedder.encode(texts).astype("float32")

    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)

    faiss.write_index(index, f"{RAG_STORE_PATH}/index.faiss")
    json.dump(metas, open(f"{RAG_STORE_PATH}/meta.json", "w"), indent=2)


# =========================
# RAG RETRIEVAL
# =========================

def retrieve(query, brand, document_type=None, top_k=8):
    index = faiss.read_index(f"{RAG_STORE_PATH}/index.faiss")
    meta = json.load(open(f"{RAG_STORE_PATH}/meta.json"))

    q_emb = embedder.encode([query]).astype("float32")
    scores, idxs = index.search(q_emb, top_k)

    results = []
    for score, idx in zip(scores[0], idxs[0]):
        if score < MIN_SCORE:
            continue

        m = meta[idx]
        if m["brand"].lower() != brand.lower():
            continue
        if document_type and m["document_type"] != document_type:
            continue

        results.append({
            "score": float(score),
            "source_id": idx,
            "meta": m
        })

    return results


# =========================
# POLICY / GUARDRAILS
# =========================

def enforce_only_from_rag(chunks):
    if not chunks:
        raise ValueError("I cannot answer based on approved sources.")


def enforce_citations(text):
    if "[" not in text or "]" not in text:
        raise ValueError("Blocked: missing citations.")


def off_label_block(text, chunks):
    approved_text = " ".join(c["meta"]["text"] for c in chunks)
    for sentence in text.split("."):
        if sentence.strip() and sentence.strip() not in approved_text:
            raise ValueError("Blocked: potential off-label or hallucinated content.")


# =========================
# ASSISTANT MODES
# =========================

def sales_call(input_json, user_id="cli"):
    brand = input_json["brand"]

    chunks = retrieve(
        query=" ".join(input_json["barriers"]),
        brand=brand,
        document_type="selling_module"
    )

    enforce_only_from_rag(chunks)

    context = "\n".join(c["meta"]["text"] for c in chunks)

    prompt = f"""
Create a FULL sales-call scenario using ONLY the text below.

SECTIONS:
1. Opening
2. Discovery
3. On-label Key Messages
4. Objection Handling
5. Next Steps / Close

Cite each section like:
[document_name | section_id | version | effective_date]

TEXT:
{context}
"""

    response = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        temperature=0.2,
        top_p=0.9,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
    )

    answer = response.choices[0].message.content
    enforce_citations(answer)
    off_label_block(answer, chunks)

    audit_log(user_id, input_json, chunks, answer)
    return answer + "\n\nAI-generated; for training; verified against approved sources."


def medical_qa(input_json, user_id="cli"):
    chunks = retrieve(
        query=input_json["question"],
        brand=input_json["brand"]
    )

    enforce_only_from_rag(chunks)

    context = "\n".join(c["meta"]["text"] for c in chunks)

    prompt = f"""
Answer the question using ONLY approved text below.
If insufficient, say so.

QUESTION:
{input_json["question"]}

TEXT:
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

    answer = response.choices[0].message.content
    enforce_citations(answer)
    off_label_block(answer, chunks)

    audit_log(user_id, input_json, chunks, answer)
    return answer + "\n\nAI-generated; for training; verified against approved sources."


# =========================
# CLI
# =========================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["call", "qa"])
    parser.add_argument("--input", required=True)

    args = parser.parse_args()
    payload = json.loads(args.input)

    if args.mode == "call":
        print(sales_call(payload))
    else:
        print(medical_qa(payload))
