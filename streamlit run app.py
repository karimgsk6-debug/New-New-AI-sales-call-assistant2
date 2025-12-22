# ============================================================
# AI Sales Call Assistant — ENTERPRISE FINAL
# Repo: New-New-AI-sales-call-assistant2
# ============================================================

import streamlit as st
import os, base64, tempfile, re

# -------------------------
# Page config
# -------------------------
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# API KEY
# ============================================================
GROQ_API_KEY = "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"

# -------------------------
# Safe imports
# -------------------------
try:
    from groq import Groq
except:
    Groq = None

try:
    from gtts import gTTS
except:
    gTTS = None

# -------------------------
# Resources & Avatar
# -------------------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"

GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

AI_AVATAR = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"
HCP_AVATAR = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/Visuals/HCP.gif"

BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

# -------------------------
# Session defaults
# -------------------------
def _init_session():
    defaults = {
        "messages": [],
        "suggestions": [],
        "audio": None,
        "temperature": 0.3,
        "tone": "Executive",
        "selected_brand": "Shingrix",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

_init_session()

# -------------------------
# CSS for UI
# -------------------------
st.markdown(
    """
    <style>
    .title-box{
        background: rgba(255,255,255,0.75);
        padding:10px 14px;
        border-radius:14px;
        display:flex;
        align-items:center;
        justify-content:space-between;
        margin-bottom:14px;
    }
    .title-box img{ height:28px; }

    .chat-row{ display:flex; gap:12px; margin:10px 0; }
    .chat-avatar{ width:48px; height:48px; border-radius:50%; }
    .chat-bubble{
        background: rgba(255,255,255,0.12);
        padding:12px;
        border-radius:14px;
        max-width:85%;
        white-space:pre-wrap;
    }

    .fixed-input{
        position:fixed;
        bottom:40px;
        left:0;
        right:0;
        padding:10px;
        background:#0e1117;
    }

    .footer{
        position:fixed;
        bottom:0;
        left:0;
        right:0;
        text-align:center;
        font-size:12px;
        color:#aaa;
        background:#0e1117;
        padding:6px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# -------------------------
# Background
# -------------------------
def set_dynamic_background(image_path):
    if not os.path.exists(image_path):
        return
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background: url("data:image/png;base64,{encoded}");
            background-size: cover;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

set_dynamic_background(BACKGROUND_PATH)

# ============================================================
# BRAND DATA (UPDATED)
# ============================================================
BRANDS = {
    "Shingrix": {
        "specialties": ["GP", "Internal Medicine", "Immunology"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Committed Vaccinator"],
        "segments": ["Reach", "Acquire", "Convert"],
        "objectives": ["Raise shingles risk", "Address hesitancy", "Simplify vaccination flow"],
        "guardrail": "Reassuring, preventive, public health focused"
    },
    "Jemperli": {
        "specialties": ["Medical Oncology", "Gynecologic Oncology"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber"],
        "segments": ["Trial", "Routine", "Advocacy"],
        "objectives": ["Identify dMMR patients", "Discuss efficacy", "Address safety"],
        "guardrail": "Scientific, evidence-based, precise"
    },
    "Trelegy": {
        "specialties": ["GP", "Pulmonologist", "Respiratory Nurse"],
        "personas": ["Primary Care Prescriber", "Pulmonologist", "Nurse Advocate"],
        "segments": ["Awareness", "Adoption", "Adherence"],
        "objectives": ["Simplify regimen", "Improve control", "Reduce exacerbations"],
        "guardrail": "Practical, outcomes-driven"
    }
}

# ============================================================
# GROQ CLIENT
# ============================================================
def get_client():
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("Add_") or Groq is None:
        return None
    return Groq(api_key=GROQ_API_KEY)

# ============================================================
# AI GENERATION
# ============================================================
def generate_reply(text, brand, persona, specialty, segment, objective):
    client = get_client()
    if not client:
        return "⚠️ GROQ API not configured."

    b = BRANDS[brand]

    prompt = f"""
You are a pharmaceutical sales representative.

Brand: {brand}
Specialty: {specialty}
Persona: {persona}
Segment: {segment}
Objective: {objective}

Tone guardrail: {b['guardrail']}

Rules:
- Natural spoken language
- No markdown or symbols
- Dialogue format only

Format exactly:

HCP says:
(one sentence)

Sales Rep says:
(response)

Then give 3 short example phrases the sales rep can use next.
"""

    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": text}
        ],
        temperature=st.session_state.temperature
    )

    output = r.choices[0].message.content

    st.session_state.suggestions = output.split("\n")[-3:]

    if gTTS:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=output[:1200]).save(tmp.name)
        st.session_state.audio = tmp.name

    return output

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("Call Setup")

    brand = st.selectbox("Brand", BRANDS.keys())
    st.session_state.selected_brand = brand
    b = BRANDS[brand]

    specialty = st.selectbox("Specialty", b["specialties"])
    persona = st.selectbox("Persona", b["personas"])
    segment = st.selectbox("Segment", b["segments"])
    objective = st.selectbox("Objective", b["objectives"])

    st.session_state.tone = st.selectbox("Tone", ["Executive", "Clinical", "Coaching"])
    st.session_state.temperature = st.slider("Creativity", 0.0, 1.0, 0.3)

# ============================================================
# TITLE
# ============================================================
st.markdown(
    f"""
    <div class="title-box">
        <img src="{GSK_LOGO_RAW}">
        <h3>💡 AI Sales Call Assistant — {brand}</h3>
        <img src="{AI_LOGO_RAW}">
    </div>
    """,
    unsafe_allow_html=True
)

# ============================================================
# CHAT DISPLAY
# ============================================================
for role, msg in st.session_state.messages:
    avatar = HCP_AVATAR if role == "HCP" else AI_AVATAR
    st.markdown(
        f"""
        <div class="chat-row">
            <img src="{avatar}" class="chat-avatar">
            <div class="chat-bubble"><b>{role}:</b><br>{msg}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

# ============================================================
# SUGGESTIONS + VOICE
# ============================================================
if st.session_state.suggestions:
    st.markdown("**Suggested phrases:**")
    for s in st.session_state.suggestions:
        st.button(s)

if st.session_state.audio:
    st.audio(st.session_state.audio)

# ============================================================
# INPUT (FIXED BOTTOM)
# ============================================================
st.markdown('<div class="fixed-input">', unsafe_allow_html=True)

user_input = st.text_area("Type what the HCP says…", height=80, key="input_box")

if st.button("SEND"):
    if user_input.strip():
        st.session_state.messages.append(("HCP", user_input))
        reply = generate_reply(user_input, brand, persona, specialty, segment, objective)
        st.session_state.messages.append(("Sales Rep", reply))

st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# FOOTER
# ============================================================
st.markdown(
    '<div class="footer">Internal use only – Generated coaching content</div>',
    unsafe_allow_html=True
)
