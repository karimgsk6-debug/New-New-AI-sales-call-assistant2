# ============================================================
# AI Sales Call Assistant — LIVE ROLE PLAY
# Repo: New-New-AI-sales-call-assistant2
# ============================================================

import streamlit as st
import os, base64, tempfile

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

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
# Assets
# -------------------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"

GSK_LOGO = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AURA_LOGO = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

SALES_REP_AVATAR = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/Visuals/sales%20rep.gif"
HCP_AVATAR = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/Visuals/HCP.gif"
AI_AVATAR = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"

# ============================================================
# SESSION STATE
# ============================================================
def init_session():
    defaults = {
        "messages": [],
        "suggestions": [],
        "audio": None,
        "brand": "Shingrix",
        "persona": "",
        "specialty": "",
        "segment": "",
        "objective": "",
        "temperature": 0.3,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_session()

# ============================================================
# BRAND DATA
# ============================================================
BRANDS = {
    "Shingrix": {
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Committed Vaccinator"],
        "specialties": ["GP", "Internal Medicine"],
        "segments": ["Reach", "Convert"],
        "objectives": ["Raise risk awareness", "Simplify vaccination"]
    },
    "Jemperli": {
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist"],
        "specialties": ["Medical Oncology"],
        "segments": ["Trial", "Routine"],
        "objectives": ["Identify dMMR patients", "Discuss efficacy"]
    },
    "Trelegy": {
        "personas": ["Primary Care Prescriber", "Pulmonologist"],
        "specialties": ["GP", "Pulmonology"],
        "segments": ["Adoption", "Adherence"],
        "objectives": ["Simplify triple therapy", "Improve control"]
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
# PARSE DIALOGUE
# ============================================================
def parse_dialogue(text):
    blocks = []
    role = None
    buffer = []

    for line in text.splitlines():
        line = line.strip()
        if line.lower().startswith("hcp says"):
            if buffer and role:
                blocks.append((role, "\n".join(buffer)))
            role = "HCP"
            buffer = []
        elif line.lower().startswith("sales rep says"):
            if buffer and role:
                blocks.append((role, "\n".join(buffer)))
            role = "AI"
            buffer = []
        else:
            if line:
                buffer.append(line)

    if buffer and role:
        blocks.append((role, "\n".join(buffer)))

    return blocks

# ============================================================
# AI RESPONSE (LIVE ROLE PLAY)
# ============================================================
def generate_roleplay(rep_text):
    client = get_client()
    if not client:
        return "⚠️ API not configured."

    prompt = f"""
You are acting as BOTH:
1) An HCP responding realistically
2) A sales excellence coach suggesting what the rep should say next

Context:
Brand: {st.session_state.brand}
Persona: {st.session_state.persona}
Specialty: {st.session_state.specialty}
Segment: {st.session_state.segment}
Objective: {st.session_state.objective}

Rules:
- Spoken field language
- No bullets, no markdown
- Natural dialogue
- Coaching tone

Format EXACTLY like this:

HCP says:
(one realistic sentence)

Sales Rep says:
(what the rep should say next)

Then provide exactly 3 short alternative phrases.
"""

    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": rep_text}
        ],
        temperature=st.session_state.temperature
    )

    output = r.choices[0].message.content

    # Extract suggestions (last 3 lines)
    st.session_state.suggestions = output.splitlines()[-3:]

    # Voice
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

    st.session_state.brand = st.selectbox("Brand", BRANDS.keys())
    b = BRANDS[st.session_state.brand]

    st.session_state.persona = st.selectbox("Persona", b["personas"])
    st.session_state.specialty = st.selectbox("Specialty", b["specialties"])
    st.session_state.segment = st.selectbox("Segment", b["segments"])
    st.session_state.objective = st.selectbox("Objective", b["objectives"])

    st.session_state.temperature = st.slider("Creativity", 0.0, 1.0, 0.3)

# ============================================================
# TITLE
# ============================================================
st.markdown(
    f"""
    <div style="display:flex;align-items:center;justify-content:space-between;
                background:rgba(255,255,255,0.85);padding:10px;border-radius:12px;">
        <img src="{GSK_LOGO}" height="28">
        <h3>AI Sales Call Assistant — Live Role Play</h3>
        <img src="{AURA_LOGO}" height="28">
    </div>
    """,
    unsafe_allow_html=True
)

# ============================================================
# CHAT WINDOW
# ============================================================
for role, msg in st.session_state.messages:

    if role == "Sales Rep":
        st.markdown(
            f"""
            <div style="display:flex;gap:12px;margin:10px 0;">
                <img src="{SALES_REP_AVATAR}" width="48">
                <div><b>Sales Rep:</b><br>{msg}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    elif role == "AI":
        for speaker, text in parse_dialogue(msg):
            avatar = HCP_AVATAR if speaker == "HCP" else AI_AVATAR
            label = "HCP says" if speaker == "HCP" else "Sales Rep says"

            st.markdown(
                f"""
                <div style="display:flex;gap:12px;margin:10px 0;">
                    <img src="{avatar}" width="48">
                    <div><b>{label}:</b><br>{text}</div>
                </div>
                """,
                unsafe_allow_html=True
            )

# ============================================================
# SUGGESTIONS (CLICK → AUTO SEND)
# ============================================================
if st.session_state.suggestions:
    st.markdown("### Suggested phrases")
    for s in st.session_state.suggestions:
        if st.button(s):
            st.session_state.messages.append(("Sales Rep", s))
            ai = generate_roleplay(s)
            st.session_state.messages.append(("AI", ai))

# Voice
if st.session_state.audio:
    st.audio(st.session_state.audio)

# ============================================================
# INPUT (LIVE ROLE PLAY)
# ============================================================
rep_input = st.text_area("What do you say next?", height=90)

if st.button("SEND"):
    if rep_input.strip():
        st.session_state.messages.append(("Sales Rep", rep_input))
        ai = generate_roleplay(rep_input)
        st.session_state.messages.append(("AI", ai))

# ============================================================
# FOOTER
# ============================================================
st.markdown(
    "<small>Internal use only — Live AI role-play training</small>",
    unsafe_allow_html=True
)
