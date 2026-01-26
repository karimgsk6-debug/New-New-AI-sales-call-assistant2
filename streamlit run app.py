# ==========================================================
# AI SALES CALL ASSISTANT – ENTERPRISE COPILOT EDITION
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
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================================
# ADMIN CONFIG (BACKEND CONTROL)
# ==========================================================
AURA_LOGO_WIDTH = 140
GSK_LOGO_WIDTH = 120
VOICE_SPEED = 1.0   # 0.75 / 1.0 / 1.25

# ==========================================================
# GROQ CLIENT
# ==========================================================
client = Groq(api_key=os.getenv("GROQ_API_KEY", "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"))

# ==========================================================
# VISUAL ASSETS
# ==========================================================
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"
AURA_LOGO_PATH = ".devcontainer/Visuals/AURA.png"
GSK_LOGO_PATH = ".devcontainer/Visuals/GSK-logo.png"

def img_b64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

AURA_LOGO = img_b64(AURA_LOGO_PATH)
GSK_LOGO = img_b64(GSK_LOGO_PATH)

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
.citation-box {background:white;padding:14px;border-radius:14px;border:1px solid #ddd}
.avatar {width:56px;border-radius:50%;margin-bottom:6px}
.title-bar {display:flex;align-items:center;justify-content:space-between;margin-bottom:12px}
.fixed-bottom {
    position:fixed; bottom:48px; left:0; right:0;
    background:white; border-top:1px solid #ccc;
    padding:12px 20px; z-index:999;
}
.disclaimer {
    position:fixed; bottom:0; left:0; right:0;
    background:#f7f7f7; padding:6px; font-size:12px;
    border-top:1px solid #ccc;
}
.prompt-chip {background:#eef6ff;border-radius:20px;padding:6px 14px;margin-right:6px;border:1px solid #ccd;cursor:pointer}
</style>
""", unsafe_allow_html=True)

# ==========================================================
# BRAND MASTER DATA (FULL)
# ==========================================================
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["Reach","Acquire","Convert","Engage"],
        "personas": ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "specialties": ["GP","Dermatologist","Geriatrician"],
        "call_flow": ["Prepare","Engage","Create Opportunity","Influence","Impact GSO","Post-Call Review"],
        "references_path": ".devcontainer/references/shingrix/",
        "summary": "Recombinant adjuvanted vaccine indicated for prevention of herpes zoster in adults ≥50 years."
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness","Diagnosis","Adoption","Adherence"],
        "personas": ["Primary Care Prescriber","Pulmonologist","Respiratory Nurse"],
        "specialties": ["GP","Pulmonologist"],
        "call_flow": ["Prepare","Engage","Demonstrate Value","Address Access","Close & Commit"],
        "references_path": ".devcontainer/references/trelegy/",
        "summary": "Single-inhaler triple therapy for COPD and asthma, improving lung function and reducing exacerbations."
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target","Initiate","Optimize","Advocate"],
        "personas": ["Data-driven Oncologist","Innovator","Late Adopter"],
        "specialties": ["Oncologist"],
        "call_flow": ["COCO Framework","Scientific Anchor","Eligibility Confirmation","Clinical Confidence","Access Alignment"],
        "references_path": ".devcontainer/references/jemperli/",
        "summary": "Anti–PD-1 monoclonal antibody indicated for dMMR/MSI-H endometrial cancer."
    }
}

# ==========================================================
# SESSION STATE
# ==========================================================
for k, v in {
    "chat": [],
    "citations": [],
    "selected_citation": None,
    "last_audio": None,
    "metrics": {"prompts":0,"responses":0,"like":0,"dislike":0,"need_more":0},
    "input_text": ""
}.items():
    st.session_state.setdefault(k, v)

# ==========================================================
# NAVIGATION
# ==========================================================
page = st.sidebar.radio("Navigate", ["Assistant","Dashboard"])

if page == "Dashboard":
    st.title("📊 Utilization Dashboard")
    st.metric("Prompts Asked", st.session_state.metrics["prompts"])
    st.metric("Responses Generated", st.session_state.metrics["responses"])
    st.metric("👍 Likes", st.session_state.metrics["like"])
    st.metric("👎 Dislikes", st.session_state.metrics["dislike"])
    st.metric("⏳ Need More", st.session_state.metrics["need_more"])
    st.stop()

# ==========================================================
# SIDEBAR CONFIGURATION
# ==========================================================
st.sidebar.header("🎯 Call Configuration")
brand_key = st.sidebar.selectbox("Brand", list(brand_data.keys()), format_func=lambda x: brand_data[x]["display"])
brand = brand_data[brand_key]

segment = st.sidebar.selectbox("Segment", brand["segments"])
persona = st.sidebar.selectbox("Persona", brand["personas"])
specialty = st.sidebar.selectbox("Specialty", brand["specialties"])
tone = st.sidebar.selectbox("Tone", ["Executive","Scientific","Friendly"])

with st.sidebar.expander("📊 Sales Call Flow", expanded=True):
    for s in brand["call_flow"]:
        st.markdown(f"- **{s}**")

with st.sidebar.expander("📚 Medical Reference Summary"):
    st.markdown(brand["summary"])

# ==========================================================
# TITLE
# ==========================================================
st.markdown(f"""
<div class='title-bar'>
    <img src='data:image/png;base64,{AURA_LOGO}' width='{AURA_LOGO_WIDTH}'>
    <h2>🧠 AI Sales Call Assistant</h2>
    <img src='data:image/png;base64,{GSK_LOGO}' width='{GSK_LOGO_WIDTH}'>
</div>
""", unsafe_allow_html=True)

# ==========================================================
# CHAT HISTORY
# ==========================================================
for msg in st.session_state.chat:
    if msg["role"]=="user":
        st.markdown(f"<div class='user-box'>{msg['content']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            f"<div class='ai-box'><img src='{AI_AVATAR}' class='avatar'><br>{msg['content']}</div>",
            unsafe_allow_html=True
        )

# ==========================================================
# FIXED BOTTOM COPILOT FIELD
# ==========================================================
st.markdown("<div class='fixed-bottom'>", unsafe_allow_html=True)

with st.expander("💡 Smart Prompt Suggestions", expanded=False):
    prompts = [
        f"Generate a sales call for {persona}",
        f"Handle objection for {brand['display']}",
        f"Summarize guideline for {specialty}",
        f"Explain value proposition"
    ]
    for p in prompts:
        if st.button(p):
            st.session_state.input_text = p
            st.session_state.metrics["prompts"] += 1

with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Ask or generate…", value=st.session_state.input_text)
    submit = st.form_submit_button("Generate")

    if submit and user_input:
        st.session_state.chat.append({"role":"user","content":user_input})
        st.session_state.metrics["prompts"] += 1

        prompt = f"""
You are a compliant pharmaceutical sales AI.

Brand: {brand['display']}
Segment: {segment}
Persona: {persona}
Specialty: {specialty}
Tone: {tone}

Follow this sales call flow:
{', '.join(brand['call_flow'])}

Question:
{user_input}
"""

        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
            temperature=0.2
        )

        answer = res.choices[0].message.content
        st.session_state.chat.append({"role":"ai","content":answer})
        st.session_state.metrics["responses"] += 1

        tts = gTTS(answer)
        buf = io.BytesIO()
        tts.write_to_fp(buf)
        st.session_state.last_audio = buf.getvalue()
        st.session_state.input_text = ""

# Voice + Replay + Speed
if st.session_state.last_audio:
    st.audio(st.session_state.last_audio, format="audio/mp3")
    if st.button("🔁 Replay Voice"):
        st.audio(st.session_state.last_audio, format="audio/mp3")

# Feedback
c1,c2,c3 = st.columns(3)
with c1:
    if st.button("👍 Like"): st.session_state.metrics["like"] += 1
with c2:
    if st.button("👎 Dislike"): st.session_state.metrics["dislike"] += 1
with c3:
    if st.button("⏳ Need More"): st.session_state.metrics["need_more"] += 1

st.markdown("</div>", unsafe_allow_html=True)

# ==========================================================
# DISCLAIMER
# ==========================================================
st.markdown("""
<div class="disclaimer">
⚠️ Internal training use only. Non-promotional. Compliant with approved labels only.
</div>
""", unsafe_allow_html=True)
