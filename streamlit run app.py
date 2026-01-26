# ==========================================================
# AI SALES CALL ASSISTANT – FINAL ENTERPRISE VERSION
# ==========================================================

import streamlit as st
import os, base64, io
from groq import Groq
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from gtts import gTTS

# ==========================================================
# PAGE CONFIG
# ==========================================================
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ==========================================================
# ADMIN CONTROLS
# ==========================================================
AURA_LOGO_WIDTH = 140
GSK_LOGO_WIDTH = 120

# ==========================================================
# GROQ CLIENT
# ==========================================================
client = Groq(api_key=os.getenv("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"))

# ==========================================================
# ASSETS
# ==========================================================
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"
AURA_PATH = ".devcontainer/Visuals/AURA.png"
GSK_PATH = ".devcontainer/Visuals/GSK-logo.png"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

def img_b64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

AURA_B64 = img_b64(AURA_PATH)
GSK_B64 = img_b64(GSK_PATH)

# ==========================================================
# BACKGROUND
# ==========================================================
if os.path.exists(BACKGROUND_PATH):
    with open(BACKGROUND_PATH, "rb") as f:
        bg = base64.b64encode(f.read()).decode()
    st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background: url("data:image/png;base64,{bg}");
        background-size: cover;
    }}
    </style>
    """, unsafe_allow_html=True)

# ==========================================================
# CSS
# ==========================================================
st.markdown("""
<style>
.ai-box {background:white;padding:16px;border-radius:16px;border:1px solid #ddd;margin-bottom:8px}
.user-box {background:#f2f2f2;padding:12px;border-radius:12px;margin-bottom:6px}
.citation-box {background:white;padding:16px;border-radius:16px;border:1px solid #ddd}
.avatar {width:60px;border-radius:50%;margin-bottom:6px}
.title {display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.fixed-prompts {
    position:fixed;
    bottom:70px;
    left:0;
    right:0;
    background:white;
    border-top:1px solid #ddd;
    padding:10px;
    z-index:999;
    display:flex;
    justify-content:center;
    gap:10px;
}
.fixed-prompts button {
    border-radius:20px;
    padding:6px 14px;
}
.disclaimer {
    position:fixed;
    bottom:0;
    width:100%;
    background:#f5f5f5;
    font-size:12px;
    padding:6px;
    border-top:1px solid #ccc;
}
</style>
""", unsafe_allow_html=True)

# ==========================================================
# BRAND DATA + CONTEXT AWARE PROMPTS
# ==========================================================
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "references_path": ".devcontainer/references/shingrix/",
        "call_flow": ["Prepare","Engage","Create Opportunity","Influence","Impact GSO","Post-Call Review"],
        "prompts": [
            "Generate a Shingrix sales call for an Uncommitted Vaccinator",
            "Address HZ risk underestimation using Shingrix data",
            "Handle cost objections for Shingrix",
            "Explain why Shingrix is recommended for adults 50+"
        ]
    },
    "jemperli": {
        "display": "Jemperli",
        "references_path": ".devcontainer/references/jemperli/",
        "call_flow": ["COCO Framework","Scientific Anchor","Eligibility Confirmation","Clinical Confidence","Access Alignment"],
        "prompts": [
            "Generate a Jemperli COCO-based sales call",
            "Explain patient eligibility for Jemperli",
            "Handle IO safety concerns",
            "Position Jemperli in treatment sequencing"
        ]
    },
    "trelegy": {
        "display": "Trelegy",
        "references_path": ".devcontainer/references/trelegy/",
        "call_flow": ["Prepare","Engage","Demonstrate Value","Address Access","Close & Commit"],
        "prompts": [
            "Generate Trelegy adoption-focused sales call",
            "Handle ICS safety concerns",
            "Explain Trelegy triple therapy value",
            "Address inhaler technique objections"
        ]
    }
}

# ==========================================================
# SESSION STATE
# ==========================================================
st.session_state.setdefault("chat", [])
st.session_state.setdefault("citations", [])
st.session_state.setdefault("selected_citation", None)
st.session_state.setdefault("input_text", "")
st.session_state.setdefault("last_audio", None)
st.session_state.setdefault("tts_speed", "Normal")

# ==========================================================
# SIDEBAR
# ==========================================================
brand_key = st.sidebar.selectbox("Brand", list(brand_data.keys()),
                                 format_func=lambda x: brand_data[x]["display"])
brand = brand_data[brand_key]

# ==========================================================
# TITLE
# ==========================================================
st.markdown(f"""
<div class="title">
    <img src="data:image/png;base64,{AURA_B64}" style="width:{AURA_LOGO_WIDTH}px">
    <h1>🧠 AI Sales Call Assistant</h1>
    <img src="data:image/png;base64,{GSK_B64}" style="width:{GSK_LOGO_WIDTH}px">
</div>
""", unsafe_allow_html=True)

# ==========================================================
# GUIDELINE VIEWER
# ==========================================================
if st.session_state.selected_citation:
    p = st.session_state.selected_citation
    with st.expander(f"📖 {p['source']} – Page {p['page']}", expanded=True):
        st.markdown(f"<div class='citation-box'>{p['text']}</div>", unsafe_allow_html=True)

# ==========================================================
# CHAT
# ==========================================================
st.markdown("### 💬 Sales Conversation")

for msg in st.session_state.chat:
    if msg["role"] == "user":
        st.markdown(f"<div class='user-box'>{msg['content']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            f"<div class='ai-box'><img src='{AI_AVATAR}' class='avatar'><br>{msg['content']}</div>",
            unsafe_allow_html=True
        )

# ================= VOICE OUTPUT =================
if st.session_state.last_audio:
    col1, col2 = st.columns([1,2])
    with col1:
        if st.button("🔁 Replay Voice"):
            st.audio(st.session_state.last_audio, format="audio/mp3")
    with col2:
        st.audio(st.session_state.last_audio, format="audio/mp3")

# ==========================================================
# CHAT INPUT
# ==========================================================
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Ask a medical question or generate a sales call…",
                               value=st.session_state.input_text)
    st.session_state.tts_speed = st.radio("Voice speed", ["Normal", "Slow"], horizontal=True)
    submit = st.form_submit_button("Generate")

if submit and user_input:
    st.session_state.chat.append({"role": "user", "content": user_input})

    prompt = f"""
STRICT COMPLIANCE RULES:
- Use approved guideline language only
- Follow brand call flow: {', '.join(brand['call_flow'])}

QUESTION:
{user_input}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"system","content":"You are a compliant pharmaceutical sales AI."},
                  {"role":"user","content":prompt}],
        temperature=0.2
    )

    answer = response.choices[0].message.content
    st.session_state.chat.append({"role": "ai", "content": answer})

    # ===== TTS =====
    slow_flag = True if st.session_state.tts_speed == "Slow" else False
    tts = gTTS(text=answer, lang="en", slow=slow_flag)
    audio_bytes = io.BytesIO()
    tts.write_to_fp(audio_bytes)
    st.session_state.last_audio = audio_bytes.getvalue()
    st.session_state.input_text = ""

    st.rerun()

# ==========================================================
# FIXED CONTEXT-AWARE PROMPTS
# ==========================================================
st.markdown('<div class="fixed-prompts">', unsafe_allow_html=True)

for i, p in enumerate(brand["prompts"]):
    if st.button(p, key=f"prompt_{brand_key}_{i}"):
        st.session_state.input_text = p

st.markdown("</div>", unsafe_allow_html=True)

# ==========================================================
# DISCLAIMER
# ==========================================================
st.markdown("""
<div class="disclaimer">
⚠️ Internal training use only. Non-promotional. Must comply with local regulations.
</div>
""", unsafe_allow_html=True)
