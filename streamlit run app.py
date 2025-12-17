# ============================================================
# app.py — AI Medical Rep Sales Call Assistant (ENTERPRISE)
# Brand-locked | SalesModule-driven | Hologram UI
# ============================================================

import streamlit as st
import os, re, tempfile, base64

# ============================================================
# 🔐 GROQ API KEY
# ============================================================
GROQ_API_KEY = "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"  # replace with gsk_...

# ============================================================
# SAFE IMPORTS
# ============================================================
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

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# REPO ASSETS
# ============================================================
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"

GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"
AI_AVATAR = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

# ============================================================
# PATH CONFIG (CRITICAL)
# ============================================================
BASE_PATH = ".devcontainer"
SALES_MODULE_PATH = os.path.join(BASE_PATH, "SalesModule")
REFERENCE_PATH = os.path.join(BASE_PATH, "references")

# ============================================================
# SESSION STATE (MERGED & CLEAN)
# ============================================================
def init_session():
    defaults = {
        "chat_history": [],
        "main_input": "",
        "selected_brand": "shingrix",
        "temperature": 0.3,
        "hcp_persona": "Evidence-led",
        "hcp_personality": "Friendly",
        "tone": "executive",
        "language": "English",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_session()

# ============================================================
# CSS (HOLOGRAM + CHAT)
# ============================================================
st.markdown(
    """
    <style>
    .title-box{ background: rgba(255,255,255,0.85); padding:12px; border-radius:10px;
        display:flex; align-items:center; justify-content:center; position:relative; margin-bottom:12px; }
    .title-box img.left-logo{ position:absolute; left:12px; height:48px; }
    .title-box img.right-logo{ position:absolute; right:12px; height:48px; }

    .chat-bubble-user{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px;
        border-radius:12px; margin:8px 0; max-width:80%; }

    .ai-message { display:flex; align-items:flex-start; gap:12px; margin:10px 0; }
    .ai-avatar { width:52px; height:52px; border-radius:50%;
        box-shadow: 0 0 12px rgba(0,255,255,0.6); animation:holoPulse 2.5s infinite ease-in-out; }
    @keyframes holoPulse { 0% { box-shadow:0 0 8px rgba(0,255,255,0.35);}
        50% { box-shadow:0 0 22px rgba(0,255,255,0.9);}
        100% { box-shadow:0 0 8px rgba(0,255,255,0.35);} }

    .ai-bubble { background: rgba(255,255,255,0.06); border:1px solid rgba(0,255,255,0.18);
        color:#E6FBFF; padding:14px; border-radius:14px; max-width:90%; white-space:pre-wrap; }

    .fixed-disclaimer{ font-size:12px; color:#aac; margin-top:16px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# BACKGROUND
# ============================================================
def set_dynamic_background(image_path):
    if not os.path.exists(image_path):
        return
    try:
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        st.markdown(
            f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background: linear-gradient(90deg, rgba(255,140,0,0.06), rgba(255,165,0,0.02)),
                url("data:image/png;base64,{encoded}");
                background-size: cover;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
    except:
        pass

set_dynamic_background(BACKGROUND_PATH)

# ============================================================
# GROQ CLIENT
# ============================================================
def get_client():
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("Add_"):
        st.warning("⚠️ GROQ API is not set")
        return None
    if Groq is None:
        st.warning("⚠️ Groq SDK not installed")
        return None
    return Groq(api_key=GROQ_API_KEY)

# ============================================================
# FILE LOADERS (BRAND-LOCKED)
# ============================================================
def read_file(path):
    if path.endswith(".pdf") and PdfReader:
        reader = PdfReader(path)
        return "".join(p.extract_text() or "" for p in reader.pages)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def load_folder(folder):
    if not os.path.exists(folder):
        return ""
    content = []
    for file in os.listdir(folder):
        if file.endswith((".txt", ".pdf")):
            content.append(read_file(os.path.join(folder, file)))
    return "\n".join(content)

# ============================================================
# CORE GENERATION (STRICT)
# ============================================================
def generate_sales_call(user_input):
    brand = st.session_state.selected_brand

    sales_module = load_folder(os.path.join(SALES_MODULE_PATH, brand))
    references = load_folder(os.path.join(REFERENCE_PATH, brand))

    if not sales_module:
        return f"❌ Missing SalesModule for brand: {brand}"
    if not references:
        return f"❌ Missing References for brand: {brand}"

    client = get_client()
    if not client:
        return "⚠️ GROQ API not available"

    system_prompt = f"""
You are a pharmaceutical sales excellence coach.

STRICT RULES:
- Use ONLY the provided Sales Module
- Use ONLY the provided References
- Follow the selling steps exactly
- No external knowledge
- No cross-brand content

Brand: {brand}
HCP Persona: {st.session_state.hcp_persona}
Tone: {st.session_state.tone}
"""

    user_prompt = f"""
SALES MODULE:
{sales_module}

APPROVED REFERENCES:
{references}

TASK:
Generate a complete sales call for the following visit scenario:
{user_input}

Structure strictly by the Sales Module steps.
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

# ============================================================
# TEXT → VOICE
# ============================================================
def text_to_voice(text):
    if not gTTS:
        return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    gTTS(text=text[:1200], lang="en").save(tmp.name)
    return open(tmp.name, "rb").read()

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("Configuration")

    st.session_state.selected_brand = st.selectbox(
        "Brand",
        ["shingrix", "jemperli", "trelegy"]
    )

    st.session_state.hcp_persona = st.selectbox(
        "HCP Persona",
        ["Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"]
    )

    st.session_state.tone = st.selectbox(
        "Tone",
        ["executive", "clinical", "coaching"]
    )

    st.session_state.temperature = st.slider("Creativity", 0.0, 1.0, 0.3)

# ============================================================
# HEADER
# ============================================================
st.markdown(
    f"""
    <div class="title-box">
        <img src="{GSK_LOGO_RAW}" class="left-logo">
        <strong>AI Medical Rep Sales Assistant</strong>
        <img src="{AI_LOGO_RAW}" class="right-logo">
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# MAIN UI
# ============================================================
scenario = st.text_area(
    "Enter visit objective / patient profile / objection",
    height=140,
)

if st.button("🧠 Generate Brand-Specific Sales Call"):
    result = generate_sales_call(scenario)

    st.markdown(
        f"""
        <div class="ai-message">
            <img src="{AI_AVATAR}" class="ai-avatar">
            <div class="ai-bubble">{result}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    audio = text_to_voice(result)
    if audio:
        st.audio(audio, format="audio/mp3")

# ============================================================
# DISCLAIMER
# ============================================================
st.markdown(
    "<div class='fixed-disclaimer'>Internal use only. Content strictly limited to approved brand materials.</div>",
    unsafe_allow_html=True,
)
