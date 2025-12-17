# ============================================================
# app.py — AI Medical Rep Sales Call Assistant (FINAL MERGED)
# Model: llama-3.3-70b-versatile (GROQ)
# ============================================================

import streamlit as st
import os, re, tempfile
from html import escape

# ============================================================
# 🔐 GROQ API KEY (REPLACE VALUE)
# ============================================================
GROQ_API_KEY = "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"  # <-- replace with gsk_...

# ============================================================
# OPTIONAL IMPORTS (SAFE)
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
    initial_sidebar_state="expanded",
)

# ============================================================
# SESSION STATE INIT
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
# GROQ CLIENT (ROBUST)
# ============================================================
def get_groq_client():
    if Groq is None:
        st.error("❌ Groq SDK not installed. Run: pip install groq")
        return None

    if not GROQ_API_KEY or GROQ_API_KEY.startswith("Add_"):
        st.error("❌ GROQ API key is missing. Please add your key.")
        return None

    try:
        return Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        st.error(f"❌ GROQ initialization failed: {e}")
        return None

# ============================================================
# BRAND CONFIG (EXTENDABLE)
# ============================================================
BRANDS = {
    "shingrix": {
        "name": "Shingrix",
        "gsl": ["Prepare", "Engage", "Create Opportunity", "Influence", "Close"],
        "objections": {
            "efficacy": "Long-term protection against herpes zoster",
            "safety": "Expected reactogenicity vs disease burden",
            "cost": "Prevention of PHN and complications",
        },
    },
    "jemperli": {
        "name": "Jemperli",
        "gsl": ["Context", "Evidence", "Patient Identification", "Access", "Close"],
        "objections": {
            "efficacy": "Durable response in dMMR/MSI-H patients",
            "safety": "Manageable immune-related AEs",
            "access": "Clear eligibility pathways",
        },
    },
}

# ============================================================
# RAG — DOCUMENT HANDLING
# ============================================================
def read_document(file):
    if file.name.endswith(".pdf") and PdfReader:
        reader = PdfReader(file)
        return "".join(page.extract_text() or "" for page in reader.pages)
    return file.read().decode("utf-8", errors="ignore")

def chunk_text(text, size=3):
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [" ".join(sentences[i:i+size]) for i in range(0, len(sentences), size)]

def search_chunks(query, chunks, top_k=4):
    if not SKLEARN_AVAILABLE or not chunks:
        return []
    vectorizer = TfidfVectorizer(stop_words="english")
    X = vectorizer.fit_transform(chunks + [query])
    scores = linear_kernel(X[-1], X[:-1]).flatten()
    best = scores.argsort()[::-1][:top_k]
    return [chunks[i] for i in best if scores[i] > 0]

# ============================================================
# LLM CORE FUNCTION
# ============================================================
def call_llm(user_prompt, context=""):
    client = get_groq_client()
    if not client:
        return "⚠️ LLM unavailable. Fix API key or installation."

    messages = [
        {"role": "system", "content": "You are a compliant pharmaceutical sales excellence coach."},
        {"role": "user", "content": context + "\n\n" + user_prompt},
    ]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=st.session_state.temperature,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"❌ LLM call failed: {e}"

# ============================================================
# SALES CALL FLOW GENERATOR
# ============================================================
def generate_sales_call(scenario):
    brand = BRANDS[st.session_state.brand]
    refs = search_chunks(scenario, st.session_state.chunks)

    context = "APPROVED REFERENCES:\n" + "\n".join(refs[:3]) if refs else ""

    prompt = f"""
Generate a structured medical sales call.

Brand: {brand['name']}
GSL Steps: {', '.join(brand['gsl'])}
HCP Persona: {st.session_state.persona}
Tone: {st.session_state.tone}

Include:
1. Opening aligned to persona
2. Insightful discovery questions (unmet needs)
3. Feature → Benefit → Patient value
4. Anticipated objections with responses
5. Strong close & next action

Field-ready. No off-label claims.
"""

    return call_llm(prompt, context)

# ============================================================
# ROLE PLAY ENGINE
# ============================================================
def role_play(rep_input):
    prompt = f"""
You are a {st.session_state.persona} healthcare professional.
Respond realistically. Challenge weak selling.
"""
    return call_llm(rep_input, prompt)

# ============================================================
# TEXT TO SPEECH (OPTIONAL)
# ============================================================
def text_to_speech(text):
    if not gTTS:
        return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    gTTS(text=text[:1000], lang="en").save(tmp.name)
    with open(tmp.name, "rb") as f:
        return f.read()

# ============================================================
# SIDEBAR UI
# ============================================================
with st.sidebar:
    st.header("🔧 Configuration")

    st.session_state.brand = st.selectbox("Brand", BRANDS.keys())
    st.session_state.persona = st.selectbox(
        "HCP Persona",
        ["Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"]
    )
    st.session_state.tone = st.selectbox(
        "Conversation Tone",
        ["executive", "clinical", "coaching", "persuasive"]
    )
    st.session_state.temperature = st.slider("Creativity", 0.0, 1.0, 0.4)

    doc = st.file_uploader("Upload approved PDF / TXT", type=["pdf", "txt"])
    if doc:
        text = read_document(doc)
        st.session_state.chunks = chunk_text(text)
        st.success("📚 Smart library ready")

    if st.button("🔌 Test GROQ Connection"):
        test = call_llm("Reply only with OK")
        st.info(test)

# ============================================================
# MAIN UI
# ============================================================
st.title("💡 AI Medical Rep Sales Call Assistant")

for msg in st.session_state.chat:
    st.markdown(msg, unsafe_allow_html=True)

scenario = st.text_area(
    "Enter visit objective, patient profile, or question",
    height=120,
)

col1, col2 = st.columns(2)

if col1.button("🧠 Generate Sales Call"):
    response = generate_sales_call(scenario)
    st.session_state.chat.append(f"### 🧠 AI Coach\n{escape(response)}")
    audio = text_to_speech(response)
    if audio:
        st.audio(audio, format="audio/mp3")

if col2.button("🩺 Role Play with HCP"):
    response = role_play(scenario)
    st.session_state.chat.append(f"### 🩺 HCP\n{escape(response)}")

# ============================================================
# FOOTER
# ============================================================
st.markdown(
    "<small>Internal use only. For training and selling excellence support. "
    "No promotional or off-label usage.</small>",
    unsafe_allow_html=True,
)
