# ==========================================================
# app_final_enterprise_sales_ai_v2.py
# Enterprise AI Sales Coach – Multi-Rep Benchmarking Edition
# ==========================================================
# ADDED IN THIS VERSION ("NEXT")
# - Multi-rep call history storage (local JSON)
# - Rep benchmarking & leaderboard
# - Manager excellence thresholds
# - All previous features preserved
# ==========================================================

import streamlit as st
import os
import re
import json
from typing import List, Dict
from datetime import datetime

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from PyPDF2 import PdfReader

try:
    from groq import Groq
except Exception:
    Groq = None

# ======================= CONFIG ============================

BASE_PATH = ".devcontainer"
DATA_PATH = "data"
CALL_LOG = f"{DATA_PATH}/call_history.json"

REF_PATH = "references"
SALES_PATH = "SalesModule"
PI_PATH = "PI"

BRANDS = ["Shingrix", "Jemperli"]

EXCELLENCE_THRESHOLD = 4.0

# ======================= STORAGE ===========================

def ensure_storage():
    os.makedirs(DATA_PATH, exist_ok=True)
    if not os.path.exists(CALL_LOG):
        with open(CALL_LOG, "w") as f:
            json.dump([], f)


def save_call(record: Dict):
    ensure_storage()
    with open(CALL_LOG, "r") as f:
        data = json.load(f)
    data.append(record)
    with open(CALL_LOG, "w") as f:
        json.dump(data, f, indent=2)


def load_calls():
    ensure_storage()
    with open(CALL_LOG, "r") as f:
        return json.load(f)

# ======================= FILE READERS ======================

def read_txt(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def read_pdf(path: str) -> str:
    reader = PdfReader(path)
    return "\n".join([p.extract_text() or "" for p in reader.pages])


def sentence_chunk(text: str) -> List[str]:
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if len(s.strip()) > 40]

# ======================= CORPUS ============================

def build_corpus(brand: str):
    chunks, meta = [], []

    def ingest(folder, tag):
        if not os.path.exists(folder): return
        for f in os.listdir(folder):
            path = os.path.join(folder, f)
            if f.lower().endswith('.pdf'):
                text = read_pdf(path)
            elif f.lower().endswith('.txt'):
                text = read_txt(path)
            else:
                continue
            for s in sentence_chunk(text):
                chunks.append(s)
                meta.append({"source": f, "tag": tag})

    ingest(f"{BASE_PATH}/{REF_PATH}/{brand}", "Medical")
    ingest(f"{BASE_PATH}/{SALES_PATH}/{brand}", "Sales")
    ingest(f"{BASE_PATH}/{PI_PATH}/{brand}", "PI")
    return chunks, meta

# ======================= RETRIEVAL =========================

def retrieve(query, chunks, meta, k=10):
    if not chunks: return []
    vec = TfidfVectorizer(stop_words="english")
    X = vec.fit_transform(chunks)
    q = vec.transform([query])
    sims = cosine_similarity(q, X)[0]
    idx = sims.argsort()[-k:][::-1]
    return [(chunks[i], meta[i]) for i in idx]

# ======================= SCORING ===========================

def score_call(text: str) -> Dict:
    criteria = {
        "Clinical Accuracy": ["indication", "efficacy", "safety", "population"],
        "Persona Alignment": ["time", "evidence", "concern"],
        "Value Communication": ["benefit", "outcome", "impact"],
        "Close & Commitment": ["next step", "follow", "commit"]
    }

    scores = {}
    lower = text.lower()
    for k, kws in criteria.items():
        scores[k] = min(5, sum(1 for w in kws if w in lower))

    scores["Total"] = round(sum(scores.values()) / len(criteria), 1)
    return scores

# ======================= NBA ===============================

def next_best_action(scores: Dict) -> str:
    if scores["Clinical Accuracy"] < 3:
        return "Reinforce PI-specific indication, efficacy, and safety."
    if scores["Persona Alignment"] < 3:
        return "Adapt message depth to HCP persona."
    if scores["Close & Commitment"] < 3:
        return "Secure a concrete next step."
    return "Progress toward adoption discussion."

# ======================= PROMPT ============================

def build_prompt(query, brand, persona, tone, retrieved):
    refs = "\n".join([f"• ({m['tag']} | {m['source']}) {c}" for c, m in retrieved])

    return f"""
You are an enterprise pharmaceutical sales excellence AI.

RULES:
- Use ONLY provided PI, medical, and sales references
- Be indication-specific
- No placeholders or generalizations

Brand: {brand}
Persona: {persona}
Tone: {tone}

=== APPROVED REFERENCES ===
{refs}

Generate a complete sales call including:
- Objective
- Rep dialogue
- HCP responses
- PI-grounded objections
- Close & commitment
- Coaching: why this works

User request: {query}
"""

# ======================= UI ================================

st.set_page_config("Enterprise AI Sales Coach", layout="wide")

st.sidebar.title("Configuration")
rep_name = st.sidebar.text_input("Rep Name", "Rep A")
brand = st.sidebar.selectbox("Brand", BRANDS)
persona = st.sidebar.selectbox("HCP Persona", ["Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"])
tone = st.sidebar.selectbox("Tone", ["Executive", "Coaching", "Persuasive", "Clinical"])

query = st.text_area("Sales Call Request")

# ======================= GENERATE ==========================

if st.button("Generate Sales Call"):
    chunks, meta = build_corpus(brand)
    retrieved = retrieve(query, chunks, meta)
    prompt = build_prompt(query, brand, persona, tone, retrieved)

    if Groq and os.getenv("GROQ_API_KEY"):
        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        res = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "user", "content": prompt}]
        )
        output = res.choices[0].message.content
    else:
        output = "LLM not connected."

    scores = score_call(output)

    save_call({
        "timestamp": datetime.now().isoformat(),
        "rep": rep_name,
        "brand": brand,
        "scores": scores
    })

    st.markdown("## AI-Generated Sales Call")
    st.write(output)

    st.markdown("## Rep Call Scoring")
    st.json(scores)

    st.markdown("## Next Best Action")
    st.success(next_best_action(scores))

# ======================= MANAGER DASHBOARD =================

st.markdown("---")
st.markdown("## Selling Excellence Manager Dashboard")

calls = load_calls()

if calls:
    reps = {}
    for c in calls:
        reps.setdefault(c["rep"], []).append(c["scores"]["Total"])

    leaderboard = sorted(
        [(r, round(sum(v)/len(v), 2)) for r, v in reps.items()],
        key=lambda x: x[1], reverse=True
    )

    st.markdown("### Rep Leaderboard")
    for r, avg in leaderboard:
        badge = "✅" if avg >= EXCELLENCE_THRESHOLD else "⚠️"
        st.write(f"{badge} **{r}** — Avg Score: {avg}/5")

    st.markdown("### Excellence Benchmark")
    st.metric("Excellence Threshold", EXCELLENCE_THRESHOLD)
else:
    st.info("No calls logged yet.")

st.caption("Enterprise AI Sales Coach • Benchmarking Enabled")
