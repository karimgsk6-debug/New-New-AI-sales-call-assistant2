# ============================================================
# app.py — AI Medical Rep Sales Call Assistant (FINAL)
# Groq + llama-3.3-70b-versatile
# ============================================================

import streamlit as st
import os, re, tempfile, base64, io
from html import escape

# ============================================================
# 🔐 GROQ API KEY (REPLACE THIS)
# ============================================================
GROQ_API_KEY = "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"

# -------------------------
# Optional imports
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

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# SESSION STATE
# ============================================================
def init_session():
    defaults = {
        "chat": [],
        "brand": "shingrix",
        "persona": "Evidence-led",
        "tone": "executive",
        "temperature": 0.4,
        "chunks": [],
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_session()

# ============================================================
# GROQ CLIENT
# ============================================================
def get_groq():
    if not GROQ_API_KEY or GROQ_API_KEY == "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":
        return None
    if Groq is None:
        return None
    return Groq(api_key=GROQ_API_KEY)

# ============================================================
# BRAND CONFIG
# ============================================================
BRANDS = {
    "shingrix": {
        "display": "Shingrix",
        "flow": ["Prepare", "Engage", "Create Opportunity", "Influence", "Close"],
        "objections": {
            "efficacy": "Durable protection across age groups",
            "safety": "Expected reactogenicity vs disease burden",
            "cost": "Prevention of downstream complications",
        },
    },
    "jemperli": {
        "display": "Jemperli",
        "flow": ["Context", "Evidence", "Patient Selection", "Access", "Close"],
        "objections": {
            "efficacy": "Durable response in dMMR/MSI-H",
            "safety": "Manageable immune-related AEs",
            "access": "Eligibility & reimbursement pathways",
        },
    },
}

# ============================================================
# RAG HELPERS (LOCAL)
# ============================================================
def read_text(file):
    if file.name.endswith(".pdf") and PdfReader:
        reader = PdfReader(file)
        return "".join(p.extract_text() or "" for p in reader.pages)
    return file.read().decode("utf-8", errors="ignore")

def build_chunks(text, size=3):
    sents = re.split(r'(?<=[.!?])\s+', text)
    return [" ".join(sents[i:i+size]) for i in range(0, len(sents), size)]

def local_search(query, chunks, top_k=4):
    if not SKLEARN_AVAILABLE or not chunks:
        return []
    vect = TfidfVectorizer(stop_words="english")
    X = vect.fit_transform(chunks + [query])
    sims = linear_kernel(X[-1], X[:-1]).flatten()
    idx = sims.argsort()[::-1][:top_k]
    return [chunks[i] for i in idx if sims[i] > 0]

# ============================================================
# LLM CALL
# ============================================================
def llm(prompt, context=""):
    client = get_groq()
    if not client:
        return "⚠️ GROQ API key not set. Please add your key."

    messages = [
        {"role": "system", "content": "You are a compliant pharmaceutical sales coach."},
        {"role": "user", "content": context + "\n\n" + prompt},
    ]

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=st.session_state.temperature,
    )

    return resp.choices[0].message.content

# ============================================================
# SALES CALL FLOW GENERATOR
# ============================================================
def generate_sales_call(user_prompt):
    brand = BRANDS[st.session_state.brand]
    persona = st.session_state.persona
    tone = st.session_state.tone

    refs = local_search(user_prompt, st.session_state.chunks)
    context = "REFERENCE MATERIAL:\n" + "\n".join(refs[:3]) if refs else ""

    prompt = f"""
Generate a structured sales call for {brand['display']}.

HCP persona: {persona}
Tone: {tone}

Include:
1. Opening
2. Insightful discovery questions
3. Feature → benefit → patient value
4. Likely objections + handling
5. Close with next step

Be concise and field-ready.
"""

    return llm(prompt, context)

# ============================================================
# ROLE PLAY ENGINE
# ============================================================
def role_play(rep_input):
    persona = st.session_state.persona
    prompt = f"""
You are a {persona} healthcare professional.
Respond realistically and challenge weak selling points.
"""
    return llm(rep_input, prompt)

# ============================================================
# AUDIO (OPTIONAL)
# ============================================================
def speak(text):
    if not gTTS:
        return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    gTTS(text=text[:1000], lang="en").save(tmp.name)
    with open(tmp.name, "rb") as f:
        return f.read()

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("Configuration")

    st.session_state.brand = st.selectbox("Brand", BRANDS.keys())
    st.session_state.persona = st.selectbox(
        "HCP Persona",
        ["Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"]
    )
    st.session_state.tone = st.selectbox(
        "Tone", ["executive", "coaching", "persuasive", "clinical"]
    )
    st.session_state.temperature = st.slider("Creativity", 0.0, 1.0, 0.4)

    uploaded = st.file_uploader("Upload approved PDF / TXT", type=["pdf", "txt"])
    if uploaded:
        text = read_text(uploaded)
        st.session_state.chunks = build_chunks(text)
        st.success("Reference material loaded")

# ============================================================
# MAIN UI
# ============================================================
st.title("💡 AI Medical Rep Sales Call Assistant")

for msg in st.session_state.chat:
    st.markdown(msg, unsafe_allow_html=True)

user_input = st.text_area("Enter your question or scenario")

col1, col2 = st.columns(2)

if col1.button("🧠 Generate Sales Call"):
    reply = generate_sales_call(user_input)
    st.session_state.chat.append(f"### AI Coach\n{reply}")
    audio = speak(reply)
    if audio:
        st.audio(audio, format="audio/mp3")

if col2.button("🩺 Role Play"):
    reply = role_play(user_input)
    st.session_state.chat.append(f"### HCP\n{reply}")

# ============================================================
# DISCLAIMER
# ============================================================
st.markdown(
    "<small>For internal sales training and selling excellence support only. "
    "No off-label or promotional misuse.</small>",
    unsafe_allow_html=True,
)
