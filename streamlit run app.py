# ============================================
# AI Sales Call Assistant - Production Ready
# Structure: /rag, /llm, /ui
# Author: Karim Salah
# ============================================

import os
import re
import io
import base64
import tempfile
from html import escape
from datetime import datetime

import streamlit as st

# -------------------------
# Optional dependencies
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
    from gtts import gTTS
except Exception:
    gTTS = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except Exception:
    ELEVENLABS_AVAILABLE = False

# ============================================
# -------------------------
# Constants
# -------------------------
MAX_CONTEXT_CHARS = 12_000
MAX_DOC_CHARS = 2_000
MAX_OUTPUT_TOKENS = 700

REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"

GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"

# ============================================
# -------------------------
# GROQ Client Loader
# -------------------------
def load_groq_client():
    api_key = "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"  # <--- Paste your Groq API key here
    if not api_key or Groq is None:
        return None
    try:
        return Groq(api_key=api_key)
    except Exception:
        return None

# -------------------------
# LLM module: Groq safe generate
# -------------------------
def groq_generate(system_prompt: str, user_prompt: str) -> str:
    client = load_groq_client()
    if not client:
        return "❌ Groq client not available."

    try:
        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            temperature=0.2,
            max_tokens=MAX_OUTPUT_TOKENS,
            messages=[
                {"role": "system", "content": system_prompt[:2000]},
                {"role": "user", "content": user_prompt[:MAX_CONTEXT_CHARS]},
            ],
        )
        return response.choices[0].message.content
    except Exception:
        return (
            "⚠️ Unable to generate a response. Check document size or refine your question."
        )

# ============================================
# -------------------------
# /rag module: File reading & Local Search
# -------------------------
def read_file_text(path):
    if not os.path.exists(path):
        return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()
    except Exception:
        return ""

def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas = [], []
    for folder in folders:
        if not folder or not os.path.exists(folder):
            continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf", ".txt"))]
        for fname in files:
            p = os.path.join(folder, fname)
            text = read_file_text(p)
            if not text:
                continue
            sents = re.split(r'(?<=[\.\?\!])\s+', text)
            for i in range(0, max(1, len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i:i + chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename": fname, "folder": folder, "start": i})
    return chunks, metas

def local_search_snippets(query, chunks, metas, top_n=3):
    if not chunks:
        return []
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks + [query])
            chunk_vecs = vectorizer.transform(chunks)
            q_vec = vectorizer.transform([query])
            sims = linear_kernel(q_vec, chunk_vecs).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            results = []
            for idx in top_idxs:
                if sims[idx] <= 0:
                    continue
                results.append({"score": float(sims[idx]), "text": chunks[idx], "meta": metas[idx]})
            return results
        except Exception:
            pass
    out = []
    q = query.lower()
    for i, c in enumerate(chunks):
        if q in c.lower():
            out.append({"score": 1.0, "text": c, "meta": metas[i]})
            if len(out) >= top_n:
                break
    return out

def build_safe_context(docs):
    context = ""
    for d in docs:
        snippet = d["text"][:MAX_DOC_CHARS]
        block = f"\nSOURCE: {d['meta']['filename']}\n{snippet}\n"
        if len(context) + len(block) > MAX_CONTEXT_CHARS:
            break
        context += block
    return context

# ============================================
# -------------------------
# Audio Generation Helper
# -------------------------
def generate_audio(text):
    if not text:
        return ""
    if ELEVENLABS_AVAILABLE:
        try:
            elevenlabs.api_key = st.secrets.get("ELEVENLABS_API_KEY", "")
            audio_stream = elevenlabs.generate(
                text=text, voice="alloy", model="eleven_multilingual_v1", stream=True
            )
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            with open(tmp.name, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
            with open(tmp.name, "rb") as fh:
                return base64.b64encode(fh.read()).decode()
        except Exception:
            pass
    if gTTS:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            gTTS(text=text, lang="en", slow=False).save(tmp.name)
            with open(tmp.name, "rb") as fh:
                return base64.b64encode(fh.read()).decode()
        except Exception:
            pass
    return ""

# ============================================
# -------------------------
# Streamlit UI
# ---------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# Session defaults
# -------------------------
def _init_session():
    defaults = {
        "chat_history": [],
        "main_input": "",
        "selected_brand": "shingrix",
        "temperature": 0.2,
        "search_mode": "deep",
        "medical_summary": "",
        "sales_summary": "",
        "uploaded_pdf_text": "",
        "pdf_summary": "",
        "feedback": {},
        "hcp_persona": "Friendly",
        "tone": "executive",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

_init_session()

# -------------------------
# Background image
# -------------------------
def set_dynamic_background(image_path):
    if not os.path.exists(image_path):
        return
    try:
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
        st.markdown(
            f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background: linear-gradient(90deg, rgba(255,140,0,0.06), rgba(255,165,0,0.02)),
                            url("data:image/png;base64,{encoded}");
                background-repeat: no-repeat;
                background-position: right top;
                background-size: cover;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass

set_dynamic_background(BACKGROUND_PATH)

# -------------------------
# Sidebar (Brand / Persona / Filters)
# -------------------------
brand_data = {
    "shingrix": {"display":"Shingrix","segments":["R","A","C","E"],"personas":["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
                 "barriers":["HCP does not consider HZ a risk","No time","Cost concerns","Not convinced"],"specialties":["GP","Derm"],"references_path":".devcontainer/references/shingrix/","sales_path":".devcontainer/SalesModule/shingrix/","call_flow":["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Analyze"],"objections":{"efficacy":"Focus on durable protection.","safety":"Acknowledge AEs then contrast risk.","cost":"Frame cost as prevention."}},
    "jemperli": {"display":"Jemperli","segments":["Target","Trial","Routine","Advocacy"],"personas":["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
                 "barriers":["Unfamiliar immunotherapy","Safety concerns","Limited eligibility","Access issues"],"specialties":["Oncologist"],"references_path":".devcontainer/references/jemperli/","sales_path":".devcontainer/SalesModule/jemperli/","call_flow":["COCO","Anchor","Engage","Close"],"objections":{"efficacy":"Discuss durable responses.","safety":"Share safety profile.","access":"Offer starter kits."}},
    "trelegy": {"display":"Trelegy","segments":["Awareness","Diagnosis","Adoption","Adherence"],"personas":["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
                "barriers":["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],"specialties":["GP","Pulmonologist"],"references_path":".devcontainer/references/trelegy/","sales_path":".devcontainer/SalesModule/trelegy/","call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"],"objections":{"device":"Offer coaching.","coverage":"Explain access options.","effectiveness":"Share comparative outcomes."}}
}

sel_brand = st.sidebar.selectbox("Brand", list(brand_data.keys()), index=list(brand_data.keys()).index(st.session_state.selected_brand))
st.session_state.selected_brand = sel_brand
bconf = brand_data[sel_brand]

persona_sel = st.sidebar.selectbox("HCP Persona", bconf["personas"])
st.session_state.hcp_persona = persona_sel

st.session_state.tone = st.sidebar.selectbox("Tone", ["executive","coaching","persuasive","clinical"], index=0)

# ============================================
# -------------------------
# Build Corpus
# ---------------------------
refs_folder = bconf.get("references_path","")
sales_folder = bconf.get("sales_path","")
chunks, chunk_meta = build_corpus_for_folders([refs_folder,sales_folder])

# -------------------------
# Main Input
# -------------------------
def generate_sales_call(prompt: str):
    # Local RAG retrieval
    retrieved = local_search_snippets(prompt, chunks, chunk_meta, top_n=6)
    context = build_safe_context(retrieved)

    system_prompt = f"You are a medical sales assistant for {sel_brand}. Use only the approved context."
    user_prompt = f"{prompt}\n\n{context}"

    return groq_generate(system_prompt, user_prompt)

with st.form("input_form", clear_on_submit=True):
    user_input = st.text_area("Ask your question / generate sales call:", height=96)
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role":"user","content":user_input.strip()})
        ai_response = generate_sales_call(user_input.strip())
        st.session_state.chat_history.append({"role":"assistant","content":ai_response})

# -------------------------
# Chat Display
# -------------------------
for entry in st.session_state.chat_history:
    if entry["role"] == "user":
        st.markdown(f'<div class="user-bubble">{escape(entry["content"])}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="ai-bubble">{entry["content"]}</div>', unsafe_allow_html=True)
        # Audio
        plain = re.sub(r"<[^>]+>", "", entry.get("content",""))[:1500]
        audio_b64 = generate_audio(plain)
        if audio_b64:
            st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")
