# ============================================================
# AI Sales Call Assistant — FINAL ENTERPRISE VERSION
# Repo: New-New-AI-sales-call-assistant2
# ============================================================

import streamlit as st
import os, base64, tempfile, re

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# =========================
# API KEY
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
    from gtts import gTTS
except:
    gTTS = None

# =========================
# HELPERS
# =========================
def img_to_base64(path):
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# =========================
# ASSETS
# =========================
GSK_LOGO = img_to_base64(".devcontainer/GSK1-logo.png")
AURA_LOGO = img_to_base64(".devcontainer/AURA1.png")
HCP_GIF = img_to_base64(".devcontainer/Visuals/HCP.gif")
AI_GIF = img_to_base64(".devcontainer/Visuals/futuristic_hologram_ai.gif")

# =========================
# BRAND DATA (UPDATED)
# =========================
BRANDS = {
    "Shingrix": {
        "display": "Shingrix",
        "specialties": ["GP", "Internal Medicine", "Immunology"],
        "segments": ["Reach", "Acquire", "Convert", "Engage"],
        "personas": [
            "Uncommitted Vaccinator",
            "Reluctant Efficiency",
            "Committed Vaccinator"
        ],
        "objectives": [
            "Raise shingles risk awareness",
            "Address vaccination hesitancy",
            "Optimize clinic workflow"
        ],
        "objections": [
            "Low perceived shingles risk",
            "Time constraints",
            "Cost concerns"
        ],
        "tone_guardrail": "Vaccination confidence, reassurance, public health impact"
    },
    "Jemperli": {
        "display": "Jemperli",
        "specialties": ["Medical Oncology", "Gynecologic Oncology"],
        "segments": ["Target", "Trial", "Routine", "Advocacy"],
        "personas": [
            "Data-Driven Oncologist",
            "Skeptical Specialist",
            "Innovator Prescriber"
        ],
        "objectives": [
            "Identify eligible dMMR patients",
            "Discuss efficacy data",
            "Address safety monitoring"
        ],
        "objections": [
            "Eligibility clarity",
            "Safety concerns",
            "Access and reimbursement"
        ],
        "tone_guardrail": "Scientific precision, confidence in evidence"
    },
    "Trelegy": {
        "display": "Trelegy",
        "specialties": ["GP", "Pulmonology", "Respiratory Nurse"],
        "segments": ["Awareness", "Adoption", "Adherence"],
        "personas": [
            "Primary Care COPD Prescriber",
            "Pulmonologist",
            "Respiratory Nurse Advocate"
        ],
        "objectives": [
            "Simplify inhaler regimen",
            "Improve symptom control",
            "Reduce exacerbations"
        ],
        "objections": [
            "Inhaler technique",
            "Coverage concerns",
            "Perceived clinical benefit"
        ],
        "tone_guardrail": "Practical outcomes, simplicity, patient benefit"
    }
}

# =========================
# SESSION STATE
# =========================
for k, v in {
    "messages": [],
    "suggestions": [],
    "audio": None
}.items():
    st.session_state.setdefault(k, v)

# =========================
# GROQ CLIENT
# =========================
def get_client():
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("Add_") or Groq is None:
        return None
    return Groq(api_key=GROQ_API_KEY)

# =========================
# AI GENERATION
# =========================
def generate_reply(user_text, brand, persona, specialty, segment, objective, tone, temp):
    client = get_client()
    if not client:
        return "⚠️ GROQ API is not configured."

    b = BRANDS[brand]

    prompt = f"""
You are a highly skilled pharmaceutical sales representative.

Brand: {b['display']}
HCP Specialty: {specialty}
HCP Persona: {persona}
Segment: {segment}
Visit Objective: {objective}

Tone guidance:
{b['tone_guardrail']} | Selected tone: {tone}

STRICT RULES:
- Write naturally, like a real conversation
- No markdown symbols
- No bullet formatting characters
- Use spoken language
- Provide concrete example phrasing

FORMAT EXACTLY:

HCP says:
(one or two realistic sentences)

Sales Rep says:
(empathetic, confident response)

Then provide 3 short example phrases the sales rep can say next.
"""

    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_text}
        ],
        temperature=temp
    )

    text = r.choices[0].message.content

    st.session_state.suggestions = re.findall(r"(?:^|\n)(?:Example|Phrase)?[:\-]?\s*(.+)", text)[-3:]

    if gTTS:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=text[:1200]).save(tmp.name)
        st.session_state.audio = tmp.name

    return text

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.header("Call Configuration")

    brand = st.selectbox("Brand", BRANDS.keys())
    b = BRANDS[brand]

    specialty = st.selectbox("Specialty", b["specialties"])
    persona = st.selectbox("HCP Persona", b["personas"])
    segment = st.selectbox("Segment", b["segments"])
    objective = st.selectbox("Visit Objective", b["objectives"])
    tone = st.selectbox("Tone", ["Executive", "Clinical", "Coaching"])
    temp = st.slider("Creativity", 0.0, 1.0, 0.3)

# =========================
# HEADER
# =========================
st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;
background:rgba(255,255,255,0.12);padding:12px;border-radius:16px;">
<img src="data:image/png;base64,{GSK_LOGO}" height="26">
<h3 style="margin:0;">💡 AI Sales Call Assistant — {b['display']}</h3>
<img src="data:image/png;base64,{AURA_LOGO}" height="26">
</div>
""", unsafe_allow_html=True)

# =========================
# CHAT
# =========================
for role, msg in st.session_state.messages:
    avatar = HCP_GIF if role == "HCP" else AI_GIF
    label = "HCP" if role == "HCP" else "Sales Rep"

    st.markdown(f"""
    <div style="display:flex;gap:12px;margin:10px 0;">
        <img src="data:image/gif;base64,{avatar}" width="48">
        <div style="background:rgba(255,255,255,0.15);
        padding:12px;border-radius:12px;white-space:pre-wrap;">
        <b>{label}:</b><br>{msg}
        </div>
    </div>
    """, unsafe_allow_html=True)

# =========================
# SUGGESTIONS + VOICE
# =========================
if st.session_state.suggestions:
    st.markdown("**Suggested Sales Rep Phrases:**")
    for s in st.session_state.suggestions:
        st.button(s)

if st.session_state.audio:
    st.audio(st.session_state.audio)

# =========================
# INPUT
# =========================
user_input = st.text_area("Type what the HCP says…", height=90)
if st.button("SEND") and user_input.strip():
    st.session_state.messages.append(("HCP", user_input))
    reply = generate_reply(
        user_input, brand, persona, specialty,
        segment, objective, tone, temp
    )
    st.session_state.messages.append(("AI", reply))

# =========================
# FOOTER
# =========================
st.markdown("""
<div style="position:fixed;bottom:0;width:100%;
text-align:center;font-size:12px;color:#aaa;">
Internal use only – Generated coaching content
</div>
""", unsafe_allow_html=True)
