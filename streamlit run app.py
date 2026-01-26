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
# GROQ CLIENT
# ==========================================================
client = Groq(api_key=os.getenv("GROQ_API_KEY", "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"))

# ==========================================================
# ADMIN CONTROLS
# ==========================================================
AURA_LOGO_WIDTH = 140
GSK_LOGO_WIDTH = 120

# ==========================================================
# VISUAL ASSETS
# ==========================================================
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"
AURA_LOGO_PATH = ".devcontainer/Visuals/AURA.png"
GSK_LOGO_PATH = ".devcontainer/Visuals/GSK-logo.png"

def image_to_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

AURA_LOGO = image_to_base64(AURA_LOGO_PATH)
GSK_LOGO = image_to_base64(GSK_LOGO_PATH)

# ==========================================================
# CSS
# ==========================================================
st.markdown("""
<style>
.ai-box, .citation-box {
    background:white;
    padding:16px;
    border-radius:16px;
    border:1px solid #ddd;
    margin-bottom:10px;
}
.user-box {
    background:#f2f2f2;
    padding:12px;
    border-radius:12px;
}
.avatar {
    width:56px;
    border-radius:50%;
    margin-bottom:8px;
}
.title-container {
    display:flex;
    align-items:center;
    justify-content:space-between;
}
.prompt-chip {
    background:#f0f8ff;
    border-radius:20px;
    padding:6px 14px;
    border:1px solid #cce;
}
.disclaimer {
    position:fixed;
    bottom:0;
    width:100%;
    background:#fafafa;
    font-size:12px;
    padding:8px;
    border-top:1px solid #ddd;
}
</style>
""", unsafe_allow_html=True)

# ==========================================================
# BRAND DATA (FULL)
# ==========================================================
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "specialties": ["GP","Dermatologist","Geriatrician"],
        "barriers": ["Low HZ risk perception","Time","Cost","Vaccine necessity doubts"],
        "call_flow": ["Prepare","Engage","Create Opportunity","Influence","Impact GSO","Post-Call Review"],
        "prompts": [
            "Generate full Shingrix sales call for this HCP",
            "Address HZ low-risk perception objection",
            "Explain Shingrix efficacy and durability",
            "Position Shingrix for eligible patients"
        ],
        "references_path": ".devcontainer/references/shingrix/"
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Targeting","Initiation","Optimization","Advocacy"],
        "personas": ["Innovator","Data-Driven Oncologist","Skeptical Prescriber","Late Adopter"],
        "specialties": ["Medical Oncologist","Gynecologic Oncologist"],
        "barriers": ["Eligibility clarity","Safety","Access","IO experience"],
        "call_flow": ["COCO Framework","Scientific Anchor","Eligibility Confirmation","Clinical Confidence","Access Alignment"],
        "prompts": [
            "Generate Jemperli COCO-based sales call",
            "Clarify dMMR/MSI-H eligibility",
            "Handle IO safety concerns",
            "Position Jemperli vs competitors"
        ],
        "references_path": ".devcontainer/references/jemperli/"
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness","Diagnosis","Adoption","Adherence"],
        "personas": ["Primary Care Prescriber","Pulmonologist","Respiratory Nurse"],
        "specialties": ["GP","Pulmonologist","Respiratory Specialist"],
        "barriers": ["Formulary","ICS safety","Technique","Cost"],
        "call_flow": ["Prepare","Engage","Demonstrate Value","Address Access","Close & Commit"],
        "prompts": [
            "Generate Trelegy adoption call",
            "Handle ICS safety concerns",
            "Position single-inhaler therapy",
            "Support adherence discussion"
        ],
        "references_path": ".devcontainer/references/trelegy/"
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
st.session_state.setdefault("metrics", {"prompts":0,"responses":0,"like":0,"dislike":0,"need_more":0})

# ==========================================================
# NAVIGATION
# ==========================================================
page = st.sidebar.radio("Navigate", ["Chat Assistant","Utilization Dashboard"])

if page == "Utilization Dashboard":
    st.markdown("## 📊 Utilization Dashboard")
    m = st.session_state.metrics
    st.metric("Prompts", m["prompts"])
    st.metric("AI Responses", m["responses"])
    st.metric("👍 Likes", m["like"])
    st.metric("👎 Dislikes", m["dislike"])
    st.metric("⏳ Need More", m["need_more"])
    st.stop()

# ==========================================================
# SIDEBAR CONFIG
# ==========================================================
st.sidebar.header("🎯 Call Configuration")

brand_key = st.sidebar.selectbox("Brand", brand_data.keys(), format_func=lambda x: brand_data[x]["display"])
brand = brand_data[brand_key]

segment = st.sidebar.selectbox("Segment", brand["segments"])
persona = st.sidebar.selectbox("Persona", brand["personas"])
specialty = st.sidebar.selectbox("Specialty", brand["specialties"])
barriers = st.sidebar.multiselect("Barriers", brand["barriers"])
objective = st.sidebar.selectbox("Objective", ["Awareness","Adoption","Retention"])
tone = st.sidebar.selectbox("Tone", ["Executive","Scientific","Friendly"])

with st.sidebar.expander("📊 Sales Call Flow", expanded=True):
    for step in brand["call_flow"]:
        st.markdown(f"- **{step}**")

# ==========================================================
# TITLE
# ==========================================================
st.markdown(f"""
<div class="title-container">
    <img src="data:image/png;base64,{AURA_LOGO}" style="width:{AURA_LOGO_WIDTH}px;">
    <h1>🧠 AI Sales Call Assistant</h1>
    <img src="data:image/png;base64,{GSK_LOGO}" style="width:{GSK_LOGO_WIDTH}px;">
</div>
""", unsafe_allow_html=True)

# ==========================================================
# PROMPT SUGGESTIONS (COPILOT STYLE)
# ==========================================================
with st.expander("💡 Smart Prompt Suggestions", expanded=True):
    cols = st.columns(len(brand["prompts"]))
    for i, p in enumerate(brand["prompts"]):
        with cols[i]:
            if st.button(p):
                st.session_state.input_text = p
                st.session_state.metrics["prompts"] += 1

# ==========================================================
# CHAT
# ==========================================================
st.markdown("### 💬 Sales Conversation")

for msg in st.session_state.chat:
    if msg["role"] == "user":
        st.markdown(f"<div class='user-box'>{msg['content']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='ai-box'><img src='{AI_AVATAR}' class='avatar'><br>{msg['content']}</div>", unsafe_allow_html=True)

# ==========================================================
# INPUT
# ==========================================================
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Ask a question or generate a sales call…", value=st.session_state.input_text)
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
Objective: {objective}
Barriers: {', '.join(barriers) if barriers else 'None'}
Tone: {tone}

Follow these steps strictly:
{', '.join(brand['call_flow'])}

Question:
{user_input}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":prompt}],
        temperature=0.2
    )

    answer = response.choices[0].message.content
    st.session_state.chat.append({"role":"ai","content":answer})
    st.session_state.metrics["responses"] += 1
    st.session_state.input_text = ""

    tts = gTTS(text=answer)
    audio = io.BytesIO()
    tts.write_to_fp(audio)
    st.session_state.last_audio = audio.getvalue()

# ==========================================================
# VOICE CONTROLS
# ==========================================================
if st.session_state.last_audio:
    st.markdown("#### 🔊 Voice Response")
    speed = st.selectbox("Playback speed", ["0.75×","1×","1.25×"])
    st.audio(st.session_state.last_audio, format="audio/mp3")
    if st.button("🔁 Replay Voice"):
        st.audio(st.session_state.last_audio, format="audio/mp3")

# ==========================================================
# FEEDBACK
# ==========================================================
st.markdown("### Feedback")
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("👍 Like"):
        st.session_state.metrics["like"] += 1
with c2:
    if st.button("👎 Dislike"):
        st.session_state.metrics["dislike"] += 1
with c3:
    if st.button("⏳ Need More"):
        st.session_state.metrics["need_more"] += 1

# ==========================================================
# DISCLAIMER
# ==========================================================
st.markdown("""
<div class="disclaimer">
⚠️ Internal training use only. Content must comply with approved product labels.
</div>
""", unsafe_allow_html=True)
