# ============================================================
# app.py — Brand-Locked AI Medical Rep Sales Assistant
# ============================================================

import streamlit as st
import os, re, tempfile

# =========================
# 🔐 GROQ API KEY
# =========================
GROQ_API_KEY = "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"

# =========================
# SAFE IMPORTS
# =========================
try:
    from groq import Groq
except:
    Groq = None

try:
    from PyPDF2 import PdfReader
except:
    PdfReader = None

try:
    from gtts import gTTS
except:
    gTTS = None

# =========================
# CONFIG
# =========================
BASE_PATH = ".devcontainer"
SALES_MODULE_PATH = os.path.join(BASE_PATH, "SalesModule")
REFERENCE_PATH = os.path.join(BASE_PATH, "references")

# =========================
# STREAMLIT
# =========================
st.set_page_config(page_title="AI Medical Rep Assistant", layout="wide")

# =========================
# SESSION STATE
# =========================
st.session_state.setdefault("brand", "shingrix")
st.session_state.setdefault("persona", "Evidence-led")
st.session_state.setdefault("tone", "executive")
st.session_state.setdefault("temperature", 0.3)

# =========================
# GROQ CLIENT
# =========================
def get_client():
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("Add_"):
        st.warning("⚠️ GROQ API is not set")
        return None
    if Groq is None:
        st.warning("⚠️ Groq SDK not installed")
        return None
    return Groq(api_key=GROQ_API_KEY)

# =========================
# FILE LOADERS
# =========================
def read_file(path):
    if path.endswith(".pdf") and PdfReader:
        reader = PdfReader(path)
        return "".join(p.extract_text() or "" for p in reader.pages)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def load_folder(folder):
    content = []
    if not os.path.exists(folder):
        return ""
    for file in os.listdir(folder):
        full = os.path.join(folder, file)
        if file.endswith((".txt", ".pdf")):
            content.append(read_file(full))
    return "\n".join(content)

# =========================
# CORE LLM CALL (LOCKED)
# =========================
def generate_sales_call(user_input):
    brand = st.session_state.brand

    sales_module = load_folder(os.path.join(SALES_MODULE_PATH, brand))
    references = load_folder(os.path.join(REFERENCE_PATH, brand))

    if not sales_module:
        return f"❌ No SalesModule content found for brand: {brand}"
    if not references:
        return f"❌ No reference content found for brand: {brand}"

    client = get_client()
    if not client:
        return "⚠️ GROQ API not available"

    system_prompt = f"""
You are a pharmaceutical sales excellence coach.

STRICT RULES:
- Use ONLY the provided Sales Module structure
- Use ONLY the provided References for claims
- Do NOT add any external knowledge
- Do NOT generalize across brands
- Follow the selling flow exactly

Brand: {brand}
HCP Persona: {st.session_state.persona}
Tone: {st.session_state.tone}
"""

    user_prompt = f"""
SALES MODULE (MANDATORY):
{sales_module}

APPROVED REFERENCES:
{references}

TASK:
Generate a complete sales call using the Sales Module.
Address the following visit scenario:
{user_input}

Structure the output exactly by Sales Module steps.
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=st.session_state.temperature,
    )

    return response.choices[0].message.content

# =========================
# TEXT → VOICE
# =========================
def text_to_voice(text):
    if not gTTS:
        return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    gTTS(text=text[:1200], lang="en").save(tmp.name)
    return open(tmp.name, "rb").read()

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.header("Configuration")

    st.session_state.brand = st.selectbox(
        "Brand",
        ["shingrix", "jemperli", "trelegy"]
    )

    st.session_state.persona = st.selectbox(
        "HCP Persona",
        ["Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"]
    )

    st.session_state.tone = st.selectbox(
        "Tone",
        ["executive", "clinical", "coaching"]
    )

    st.session_state.temperature = st.slider(
        "Creativity",
        0.0, 1.0, 0.3
    )

# =========================
# MAIN UI
# =========================
st.title("💡 Brand-Locked AI Sales Call Assistant")

scenario = st.text_area(
    "Enter visit objective / patient profile / objection",
    height=130
)

if st.button("🧠 Generate Brand-Specific Sales Call"):
    result = generate_sales_call(scenario)

    st.markdown("### 🧠 Generated Sales Call")
    st.write(result)

    audio = text_to_voice(result)
    if audio:
        st.markdown("### 🔊 Voice Output")
        st.audio(audio, format="audio/mp3")

# =========================
# FOOTER
# =========================
st.markdown(
    "<small>Internal use only. Generated content is strictly limited to approved brand materials.</small>",
    unsafe_allow_html=True
)
