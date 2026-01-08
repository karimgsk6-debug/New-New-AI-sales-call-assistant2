# =========================
# AI SALES CALL ASSISTANT
# FULL STABLE VERSION
# =========================

import streamlit as st
import os, re, base64, tempfile
from html import escape
from io import BytesIO

# -------------------------
# Optional imports
# -------------------------
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

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN = True
except:
    SKLEARN = False

# -------------------------
# PAGE CONFIG
# -------------------------
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------
# VISUAL ASSETS (UNCHANGED)
# -------------------------
BACKGROUND_IMAGE = ".devcontainer/Visuals/MR mentor final1.png"
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"

# -------------------------
# CSS
# -------------------------
st.markdown("""
<style>
.user-bubble { background:#f2f2f2;padding:10px;border-radius:10px;margin:8px 0;max-width:80%; }
.ai-message { display:flex;gap:12px;margin:10px 0; }
.ai-avatar { width:48px;border-radius:50%; }
.ai-bubble { background:rgba(0,0,0,0.75);color:#E6FBFF;padding:14px;border-radius:14px;max-width:90%; }
.audio-btn { margin-top:6px; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# BACKGROUND
# -------------------------
if os.path.exists(BACKGROUND_IMAGE):
    with open(BACKGROUND_IMAGE, "rb") as f:
        bg = base64.b64encode(f.read()).decode()
    st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background:url("data:image/png;base64,{bg}") no-repeat right top;
        background-size:cover;
    }}
    </style>
    """, unsafe_allow_html=True)

# -------------------------
# SESSION INIT
# -------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "product" not in st.session_state:
    st.session_state.product = "Shingrix"

# -------------------------
# GROQ CLIENT
# -------------------------
def load_groq():
    api_key = "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"
    if not api_key or "ADD_GROQ" in api_key or Groq is None:
        return None
    return Groq(api_key=api_key)

# -------------------------
# PRODUCT DATA
# -------------------------
PRODUCTS = {
    "Shingrix": {
        "segments": ["Reach","Acquire","Convert","Engage"],
        "personas": ["Evidence-led","Time-pressured","Skeptical","Early-adopter"],
        "barriers": ["HZ not priority","Time constraints","Safety concerns","Cost"],
        "refs": ".devcontainer/references/shingrix",
        "sales": ".devcontainer/SalesModule/shingrix"
    },
    "Jemperli": {
        "segments": ["Identify","Trial","Adopt","Advocate"],
        "personas": ["Data-driven","Innovator","Skeptical","Late adopter"],
        "barriers": ["Eligibility","Safety","Access"],
        "refs": ".devcontainer/references/jemperli",
        "sales": ".devcontainer/SalesModule/jemperli"
    },
    "Trelegy": {
        "segments": ["Awareness","Diagnosis","Adoption","Adherence"],
        "personas": ["GP","Pulmonologist","Nurse"],
        "barriers": ["Technique","Coverage","Side effects"],
        "refs": ".devcontainer/references/trelegy",
        "sales": ".devcontainer/SalesModule/trelegy"
    }
}

# -------------------------
# SIDEBAR
# -------------------------
with st.sidebar:
    st.header("🔧 Call Setup")
    product = st.selectbox("Product", PRODUCTS.keys())
    st.session_state.product = product
    pdata = PRODUCTS[product]

    persona = st.selectbox("HCP Persona", pdata["personas"])
    barrier = st.selectbox("Primary Barrier", pdata["barriers"])
    tone = st.selectbox("Tone", ["Executive","Coaching","Persuasive","Clinical"])

# -------------------------
# SAFE FILE READ
# -------------------------
def read_folder(folder):
    text = ""
    if os.path.exists(folder):
        for f in os.listdir(folder):
            p = os.path.join(folder, f)
            if f.lower().endswith(".pdf") and PdfReader:
                r = PdfReader(p)
                text += " ".join(pg.extract_text() or "" for pg in r.pages)
            elif f.lower().endswith(".txt"):
                text += open(p,encoding="utf-8",errors="ignore").read()
    return text

# -------------------------
# COLLAPSIBLE SUMMARIES
# -------------------------
with st.expander("📚 Medical References Summary"):
    st.write(read_folder(pdata["refs"])[:2000] or "No references found.")

with st.expander("💼 Sales Module Summary"):
    st.write(read_folder(pdata["sales"])[:2000] or "No sales modules found.")

# -------------------------
# DYNAMIC OBJECTION HANDLING
# -------------------------
def objection_reply(barrier, persona):
    if persona.lower().startswith("evidence"):
        return f"Acknowledge {barrier}, share 1 trial endpoint, propose pilot."
    if persona.lower().startswith("time"):
        return f"Acknowledge {barrier}, give 1 sentence script, nurse checklist."
    if persona.lower().startswith("skeptical"):
        return f"Acknowledge concern, safety data, conservative start."
    return f"Reframe {barrier} with patient benefit and workflow ease."

# -------------------------
# ROLEPLAY (GUARDED)
# -------------------------
def roleplay(user_input):
    client = load_groq()
    guardrail = f"""
Use ONLY information aligned with {st.session_state.product}
Sales Modules and Medical References.
If unsure, say you need approved material.
"""

    prompt = f"""
You are a pharma sales rep role-playing with an HCP.

Persona: {persona}
Barrier: {barrier}
Tone: {tone}

HCP says:
{user_input}

Respond with:
- Clear answer
- Example phrasing (2 options)
- Objection handling

{guardrail}
"""

    if not client:
        return "[API NOT SET] Replace ADD_GROQ_API_here"

    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":prompt}],
        temperature=0.3
    )
    return r.choices[0].message.content

# -------------------------
# TTS
# -------------------------
def tts_audio(text):
    if not gTTS:
        return None
    t = gTTS(text=text)
    buf = BytesIO()
    t.write_to_fp(buf)
    buf.seek(0)
    return buf

# -------------------------
# CHAT INPUT (SAFE)
# -------------------------
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_area("💬 Simulate the HCP or ask a question", height=100)
    send = st.form_submit_button("Send")

if send and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input})
    ai = roleplay(user_input)
    st.session_state.chat_history.append({"role":"assistant","content":ai})

# -------------------------
# CHAT RENDER
# -------------------------
for i, msg in enumerate(st.session_state.chat_history):
    if msg["role"]=="user":
        st.markdown(f'<div class="user-bubble">{escape(msg["content"])}</div>',unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="ai-message">
            <img src="{AI_AVATAR}" class="ai-avatar">
            <div class="ai-bubble">{escape(msg["content"])}</div>
        </div>
        """, unsafe_allow_html=True)

        audio = tts_audio(msg["content"])
        if audio:
            st.audio(audio, format="audio/mp3")

# -------------------------
# FOOTER
# -------------------------
st.markdown(
    "<small>Internal training tool. Medical decisions require approved sources.</small>",
    unsafe_allow_html=True
)
