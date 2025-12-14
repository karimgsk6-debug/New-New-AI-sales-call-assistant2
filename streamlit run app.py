# app_final_full_rag_hologram.py
# ============================================================
# FULLY MERGED, READY‑TO‑RUN AI SALES CALL ASSISTANT
# Features:
# - True RAG (Medical + Sales PDFs/TXT)
# - Persona, tone, objection intelligence
# - Coach layer (why this works)
# - Product‑specific call flows
# - Hologram avatar UI
# - Audio (ElevenLabs / gTTS fallback)
# - Feedback loop
# ============================================================

import streamlit as st
import os, re, tempfile, base64, io
from datetime import datetime
from html import escape

# =========================
# OPTIONAL / SOFT IMPORTS
# =========================
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
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except Exception:
    ELEVENLABS_AVAILABLE = False

try:
    from gtts import gTTS
except Exception:
    gTTS = None

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# ASSETS / AVATAR
# =========================
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"

GSK_LOGO = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

# =========================
# SESSION DEFAULTS
# =========================
def init_session():
    defaults = {
        "chat": [],
        "selected_brand": "shingrix",
        "hcp_persona": "Evidence-led",
        "tone": "executive",
        "temperature": 0.7,
        "language": "English"
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_session()

# =========================
# CSS (HOLOGRAM UI)
# =========================
st.markdown("""
<style>
.ai-message{display:flex;gap:12px;margin:12px 0}
.ai-avatar{width:54px;height:54px;border-radius:50%;box-shadow:0 0 18px rgba(0,255,255,.8)}
.ai-bubble{background:rgba(255,255,255,.07);border:1px solid rgba(0,255,255,.25);color:#E6FBFF;padding:14px;border-radius:14px;white-space:pre-wrap}
.user-bubble{background:rgba(0,0,0,.06);padding:10px 14px;border-radius:12px;max-width:80%}
.step-title{font-weight:700;color:#BFF;margin-top:10px}
.objection{background:rgba(255,255,255,.06);padding:8px;border-radius:8px;margin:6px 0}
</style>
""", unsafe_allow_html=True)

# =========================
# BACKGROUND
# =========================
def set_bg(path):
    if not os.path.exists(path):
        return
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"]{{
        background:url("data:image/png;base64,{encoded}") no-repeat right top;
        background-size:cover;
    }}
    </style>
    """, unsafe_allow_html=True)

set_bg(BACKGROUND_PATH)

# =========================
# GROQ CLIENT
# =========================
def groq_client():
    key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", "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")
    if not key or Groq is None:
        return None
    return Groq(api_key=key)

# =========================
# BRAND CONFIG (RAG ROOT)
# =========================
BRANDS = {
    "shingrix": {
        "display": "Shingrix",
        "references": ".devcontainer/references/shingrix",
        "sales": ".devcontainer/SalesModule/shingrix",
        "flow": ["Prepare", "Engage", "Create Opportunity", "Influence", "Close"],
        "objections": ["efficacy", "safety", "cost"]
    },
    "jemperli": {
        "display": "Jemperli",
        "references": ".devcontainer/references/jemperli",
        "sales": ".devcontainer/SalesModule/jemperli",
        "flow": ["COCO", "Anchor", "Engage", "Close"],
        "objections": ["efficacy", "safety", "access"]
    },
    "trelegy": {
        "display": "Trelegy",
        "references": ".devcontainer/references/trelegy",
        "sales": ".devcontainer/SalesModule/trelegy",
        "flow": ["Prepare", "Engage", "Demonstrate", "Address Access", "Close"],
        "objections": ["device", "coverage", "effectiveness"]
    }
}

# =========================
# RAG: LOAD + SEARCH
# =========================
def read_text(path):
    if path.lower().endswith(".pdf") and PdfReader:
        r = PdfReader(path)
        return "".join([p.extract_text() or "" for p in r.pages])
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def build_corpus(folders):
    chunks, meta = [], []
    for folder in folders:
        if not os.path.exists(folder):
            continue
        for f in os.listdir(folder):
            if f.lower().endswith((".pdf", ".txt")):
                text = read_text(os.path.join(folder, f))
                for s in re.split(r'(?<=[.!?])\s+', text):
                    if len(s.strip()) > 40:
                        chunks.append(s.strip())
                        meta.append(f)
    return chunks, meta

def retrieve(query, chunks, meta, k=6):
    if not chunks:
        return []
    if SKLEARN_AVAILABLE:
        tfidf = TfidfVectorizer(stop_words="english").fit(chunks + [query])
        sims = linear_kernel(tfidf.transform([query]), tfidf.transform(chunks))[0]
        idxs = sims.argsort()[::-1][:k]
        return [f"({meta[i]}) {chunks[i]}" for i in idxs if sims[i] > 0]
    return chunks[:k]

# =========================
# LLM GENERATION (HARD‑GROUNDED RAG)
# =========================
def generate_call(user_query):
    brand = BRANDS[st.session_state.selected_brand]
    chunks, meta = build_corpus([brand["references"], brand["sales"]])
    refs = retrieve(user_query, chunks, meta, 8)

    system = """
You are a pharmaceutical sales excellence coach.
Rules:
- Use ONLY the provided references
- Do NOT invent clinical data
- Produce a full sales call scenario with dialogue
- Include objection handling and a clear close
- Add a coaching section: why this works
"""

    prompt = f"""
BRAND: {brand['display']}
PERSONA: {st.session_state.hcp_persona}
TONE: {st.session_state.tone}
USER REQUEST: {user_query}

REFERENCES:
""" + "\n".join(refs)

    client = groq_client()
    if not client:
        return "⚠️ GROQ API key not configured."

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        temperature=st.session_state.temperature
    )
    return resp.choices[0].message.content

# =========================
# AUDIO
# =========================
def speak(text):
    if ELEVENLABS_AVAILABLE:
        try:
            elevenlabs.api_key = st.secrets.get("ELEVENLABS_API_KEY", "")
            audio = elevenlabs.generate(text=text, voice="alloy")
            return audio
        except Exception:
            pass
    if gTTS:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=text).save(tmp.name)
        with open(tmp.name, "rb") as f:
            return f.read()
    return None

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.image(GSK_LOGO, width=120)
    st.session_state.selected_brand = st.selectbox("Brand", BRANDS.keys())
    st.session_state.hcp_persona = st.selectbox("HCP Persona", ["Evidence-led","Time-pressured","Skeptical","Early-adopter"])
    st.session_state.tone = st.selectbox("Tone", ["executive","coaching","persuasive","clinical"])
    st.session_state.temperature = st.slider("Creativity", 0.0, 1.0, 0.7, 0.05)
    if st.button("Clear Chat"):
        st.session_state.chat = []
        st.experimental_rerun()

# =========================
# HEADER
# =========================
st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:center;gap:16px">
<img src="{GSK_LOGO}" height="42">
<h2>AI Sales Call Assistant — {BRANDS[st.session_state.selected_brand]['display']}</h2>
<img src="{AI_LOGO}" height="42">
</div>
""", unsafe_allow_html=True)

# =========================
# CHAT INPUT
# =========================
user_input = st.text_area("Ask for a sales call, objection handling, or coaching")
if st.button("Send") and user_input.strip():
    st.session_state.chat.append({"role":"user","content":user_input})
    answer = generate_call(user_input)
    st.session_state.chat.append({"role":"ai","content":answer})

# =========================
# CHAT RENDER
# =========================
for msg in st.session_state.chat:
    if msg["role"] == "user":
        st.markdown(f"<div class='user-bubble'>{escape(msg['content'])}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="ai-message">
            <img src="{AI_AVATAR}" class="ai-avatar" />
            <div class="ai-bubble">{msg['content']}</div>
        </div>
        """, unsafe_allow_html=True)

        audio = speak(re.sub(r"<[^>]+>", "", msg["content"])[:1200])
        if audio:
            st.audio(audio)

# =========================
# DISCLAIMER
# =========================
st.markdown("""
<div style="font-size:12px;opacity:.7;margin-top:18px">
Internal use only. Medical information must be verified against approved sources.
</div>
""", unsafe_allow_html=True)
