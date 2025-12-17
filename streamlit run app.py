# ============================================================
# app.py — AI Medical Rep Sales Call Assistant (FINAL FIXED)
# Model: llama-3.3-70b-versatile (GROQ)
# ============================================================

import streamlit as st
import os, re, tempfile

# ============================================================
# 🔐 GROQ API KEY (REPLACE OR USE ENV)
# ============================================================
GROQ_API_KEY = "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"  # replace with gsk_...

# ============================================================
# SAFE OPTIONAL IMPORTS
# ============================================================
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
# STREAMLIT CONFIG
# ============================================================
st.set_page_config(
    page_title="AI Medical Rep Sales Assistant",
    layout="wide",
)

# ============================================================
# SESSION STATE
# ============================================================
def init_state():
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

init_state()

# ============================================================
# GROQ CLIENT (SAFE & EXPLICIT)
# ============================================================
def get_groq_client():
    if Groq is None:
        st.warning("⚠️ Groq SDK not installed. Run: pip install groq")
        return None

    if not GROQ_API_KEY or GROQ_API_KEY.startswith("Add_"):
        st.warning("⚠️ GROQ API is not set. Text generation disabled.")
        return None

    try:
        return Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        st.error(f"❌ GROQ init failed: {e}")
        return None

# ============================================================
# BRAND CONFIG
# ============================================================
BRANDS = {
    "shingrix": {
        "name": "Shingrix",
        "gsl": ["Prepare", "Engage", "Create Opportunity", "Influence", "Close"],
    },
    "jemperli": {
        "name": "Jemperli",
        "gsl": ["Context", "Evidence", "Patient Selection", "Access", "Close"],
    },
}

# ============================================================
# RAG HELPERS
# ============================================================
def read_document(file):
    if file.name.endswith(".pdf") and PdfReader:
        reader = PdfReader(file)
        return "".join(p.extract_text() or "" for p in reader.pages)
    return file.read().decode("utf-8", errors="ignore")

def chunk_text(text, size=3):
    sents = re.split(r'(?<=[.!?])\s+', text)
    return [" ".join(sents[i:i+size]) for i in range(0, len(sents), size)]

def search_chunks(query, chunks, top_k=4):
    if not SKLEARN_AVAILABLE or not chunks:
        return []
    vect = TfidfVectorizer(stop_words="english")
    X = vect.fit_transform(chunks + [query])
    scores = linear_kernel(X[-1], X[:-1]).flatten()
    idx = scores.argsort()[::-1][:top_k]
    return [chunks[i] for i in idx if scores[i] > 0]

# ============================================================
# LLM CALL
# ============================================================
def call_llm(prompt, context=""):
    client = get_groq_client()
    if not client:
        return "⚠️ GROQ API not available. Please set the API key."

    messages = [
        {"role": "system", "content": "You are a compliant pharmaceutical sales coach."},
        {"role": "user", "content": context + "\n\n" + prompt},
    ]

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=st.session_state.temperature,
    )

    return response.choices[0].message.content

# ============================================================
# SALES CALL GENERATOR
# ============================================================
def generate_sales_call(scenario):
    brand = BRANDS[st.session_state.brand]
    refs = search_chunks(scenario, st.session_state.chunks)

    context = "APPROVED REFERENCES:\n" + "\n".join(refs[:3]) if refs else ""

    prompt = f"""
Generate a structured sales call.

Brand: {brand['name']}
GSL Steps: {', '.join(brand['gsl'])}
HCP Persona: {st.session_state.persona}
Tone: {st.session_state.tone}

Include:
1. Opening
2. Insightful discovery questions
3. Feature → Benefit → Patient value
4. Likely objections + responses
5. Close & next step

Field-ready, compliant, concise.
"""

    return call_llm(prompt, context)

# ============================================================
# ROLE PLAY
# ============================================================
def role_play(rep_input):
    prompt = f"""
You are a {st.session_state.persona} healthcare professional.
Respond realistically and challenge the rep.
"""
    return call_llm(rep_input)

# ============================================================
# TEXT → VOICE
# ============================================================
def text_to_voice(text):
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
        ["Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"],
    )
    st.session_state.tone = st.selectbox(
        "Tone",
        ["executive", "clinical", "coaching", "persuasive"],
    )
    st.session_state.temperature = st.slider("Creativity", 0.0, 1.0, 0.4)

    doc = st.file_uploader("Upload approved PDF / TXT", type=["pdf", "txt"])
    if doc:
        text = read_document(doc)
        st.session_state.chunks = chunk_text(text)
        st.success("Smart library ready")

# ============================================================
# MAIN UI
# ============================================================
st.title("💡 AI Medical Rep Sales Call Assistant")

scenario = st.text_area(
    "Enter visit objective, patient profile, or question",
    height=120,
)

col1, col2 = st.columns(2)

if col1.button("🧠 Generate Sales Call"):
    result = generate_sales_call(scenario)

    # ✅ TEXT FIRST
    st.markdown("### 🧠 Generated Sales Call")
    st.write(result)

    # ✅ VOICE BELOW TEXT
    audio = text_to_voice(result)
    if audio:
        st.markdown("### 🔊 Voice Output")
        st.audio(audio, format="audio/mp3")

if col2.button("🩺 Role Play with HCP"):
    result = role_play(scenario)
    st.markdown("### 🩺 HCP Response")
    st.write(result)

# ============================================================
# FOOTER
# ============================================================
st.markdown(
    "<small>Internal training use only. No off-label promotion.</small>",
    unsafe_allow_html=True,
)
