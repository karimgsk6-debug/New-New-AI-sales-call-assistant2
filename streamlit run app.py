# ============================================================
# app.py — AI Medical Rep Sales Call Assistant (ENTERPRISE)
# Enhanced UI: Chat Simulator with Voice + Brand-governed content
# ============================================================

import streamlit as st
import os, base64, tempfile

# ============================================================
# 🔐 GROQ API KEY
# ============================================================
GROQ_API_KEY = "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"  # <-- replace with your key

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
# ASSETS
# ============================================================
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"

GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"
AI_AVATAR = ".devcontainer/Visuals/futuristic_hologram_ai.gif"
HCP_AVATAR = ".devcontainer/Visuals/HCP.gif"
SALES_AVATAR = ".devcontainer/Visuals/sales rep.gif"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

# ============================================================
# PATH CONFIG
# ============================================================
BASE_PATH = ".devcontainer"
SALES_MODULE_PATH = os.path.join(BASE_PATH, "SalesModule")
REFERENCE_PATH = os.path.join(BASE_PATH, "references")

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# ============================================================
# SESSION STATE INIT
# ============================================================
def init_session():
    defaults = {
        "messages": [],
        "user_input": "",
        "selected_brand": "shingrix",
        "hcp_persona": "",
        "tone": "executive",
        "temperature": 0.3,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_session()

# ============================================================
# BRAND DATA
# ============================================================
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HZ risk not perceived", "No time", "Cost concerns", "Efficacy doubts"],
        "specialties": ["GP", "Dermatology", "Cardiology", "Immunology", "Internal Medicine"],
        "references_path": os.path.join(REFERENCE_PATH, "shingrix"),
        "sales_path": os.path.join(SALES_MODULE_PATH, "shingrix"),
        "call_flow": ["Prepare", "Engage", "Create Opportunities", "Influence", "Impact GSO", "Analyze"],
        "objections": {
            "efficacy": "Focus on durable protection and age-agnostic efficacy evidence.",
            "safety": "Acknowledge common AEs, then contrast with risk of complications from shingles.",
            "cost": "Frame cost as prevention of downstream complications and reduce clinic workload."
        },
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target ID", "Trial", "Routine", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber"],
        "barriers": ["Eligibility", "Safety", "Access"],
        "specialties": ["Oncologist", "Medical Oncologist"],
        "references_path": os.path.join(REFERENCE_PATH, "jemperli"),
        "sales_path": os.path.join(SALES_MODULE_PATH, "jemperli"),
        "call_flow": ["COCO", "Anchor", "Engage", "Close"],
        "objections": {
            "efficacy": "Discuss durable responses in dMMR/MSI-H and appropriate patient selection.",
            "safety": "Share safety profile and monitoring guidance to reduce perceived risk.",
            "access": "Offer starter kits or initiation support and reimbursement pathways."
        },
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["PCP Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Inhaler", "Access", "Coverage"],
        "specialties": ["GP", "Pulmonologist"],
        "references_path": os.path.join(REFERENCE_PATH, "trelegy"),
        "sales_path": os.path.join(SALES_MODULE_PATH, "trelegy"),
        "call_flow": ["Prepare", "Engage", "Demonstrate", "Address Access", "Close"],
        "objections": {
            "device": "Offer quick practical coaching and demo materials.",
            "coverage": "Explain access options and patient support programs.",
            "effectiveness": "Share comparative outcomes framed for real-world practice."
        },
    },
}

# ============================================================
# GROQ CLIENT
# ============================================================
def get_client():
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("Add_"):
        st.warning("⚠️ GROQ API is not set")
        return None
    if Groq is None:
        st.warning("⚠️ groq package not installed")
        return None
    return Groq(api_key=GROQ_API_KEY)

# ============================================================
# FILE HELPERS
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
    for f in os.listdir(folder):
        if f.endswith((".txt", ".pdf")):
            content.append(read_file(os.path.join(folder, f)))
    return "\n".join(content)

# ============================================================
# PERSONA PROFILE
# ============================================================
def persona_profile(persona):
    profiles = {
        "Uncommitted Vaccinator": {"quick_win": "Focus on 1-step vaccination script."},
        "Reluctant Efficiency": {"quick_win": "Offer concise adoption checklist."},
        "Patient Influenced": {"quick_win": "Provide patient-facing summary."},
        "Committed Vaccinator": {"quick_win": "Highlight long-term impact data."},
        "Data-Driven Oncologist": {"quick_win": "Share key trial metrics."},
        "Skeptical Specialist": {"quick_win": "Provide monitoring protocols."},
        "Innovator Prescriber": {"quick_win": "Show new workflow pilots."},
        "PCP Prescriber": {"quick_win": "Demonstrate simple inhaler use."},
        "Pulmonologist": {"quick_win": "Share comparative outcomes."},
        "Respiratory Nurse": {"quick_win": "Provide patient coaching sheets."},
    }
    return profiles.get(persona, {"quick_win": "Offer concise actionable next step."})

# ============================================================
# OBJECTION HANDLER
# ============================================================
def objection_response(product_key, objection_key, persona):
    product = brand_data.get(product_key, {})
    base = product.get("objections", {})
    reply = base.get(objection_key, "Acknowledge the concern, offer concise evidence, propose a low-effort next step.")
    prof = persona_profile(persona)
    return f"{reply} (Tailored suggestion: {prof['quick_win']})"

# ============================================================
# GENERATE SALES CALL
# ============================================================
def generate_sales_call(user_input):
    brand = st.session_state.selected_brand
    bconf = brand_data[brand]

    sales_module = load_folder(bconf["sales_path"])
    references = load_folder(bconf["references_path"])

    if not sales_module or not references:
        return f"❌ Missing approved materials for {bconf['display']}"

    client = get_client()
    if not client:
        return "⚠️ GROQ API unavailable"

    system_prompt = f"""
You are a pharmaceutical sales excellence coach.
RULES:
- Use ONLY the provided Sales Module
- Use ONLY the provided References
- Follow this call flow exactly: {bconf['call_flow']}
- Do NOT introduce external knowledge
- Do NOT cross-reference other brands

Brand: {bconf['display']}
HCP Persona: {st.session_state.hcp_persona}
Tone: {st.session_state.tone}
"""

    user_prompt = f"""
SALES MODULE:
{sales_module}

APPROVED MEDICAL REFERENCES:
{references}

TASK:
Generate a full sales call aligned to the defined call flow.
Scenario:
{user_input}

Include:
- Persona-adapted questions
- 1–2 objections from: {bconf['objections'].keys()}
- Clear next-step close
- Provide 3 suggested phrases for the sales rep to say
"""

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=st.session_state.temperature,
    )

    return resp.choices[0].message.content

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
    st.header("Call Configuration")
    brand = st.selectbox("Brand", list(brand_data.keys()))
    st.session_state.selected_brand = brand
    bconf = brand_data[brand]

    st.session_state.hcp_persona = st.selectbox("HCP Persona", bconf["personas"])
    st.selectbox("Specialty", bconf["specialties"])
    st.selectbox("Segment", bconf["segments"])
    st.session_state.tone = st.selectbox("Tone", ["executive", "clinical", "coaching"])
    st.session_state.temperature = st.slider("Creativity", 0.0, 1.0, 0.3)

# ============================================================
# TITLE BOX (minimized logos)
# ============================================================
st.markdown(
    f"""
    <div class="title-box">
        <img src="{GSK_LOGO_RAW}" class="left-logo" style="height:320px;">
        <h2 style="display:inline-block; margin:0 12px;">💡 AI Sales Call Assistant — {bconf['display']}</h2>
        <img src="{AI_LOGO_RAW}" class="right-logo" style="height:320px;">
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# BACKGROUND
# ============================================================
if os.path.exists(BACKGROUND_PATH):
    with open(BACKGROUND_PATH, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background: url("data:image/png;base64,{encoded}");
            background-size: cover;
            background-repeat: no-repeat;
            background-position: right top;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# CHAT DISPLAY
# ============================================================
for role, msg in st.session_state.messages:
    avatar = SALES_AVATAR if role == "AI" else HCP_AVATAR
    st.markdown(
        f"""
        <div style="display:flex; align-items:flex-start; gap:12px; margin:8px 0;">
            <img src="{avatar}" width="48" style="border-radius:50%;"/>
            <div style="background:rgba(255,255,255,0.08); padding:10px; border-radius:12px; max-width:75%; white-space:pre-wrap;">
                <b>{role}:</b> {msg}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# BOTTOM CHAT INPUT
# ============================================================
st.session_state.user_input = st.text_area(
    "Type HCP scenario...",
    st.session_state.user_input,
    height=100,
    key="chat_input"
)

send = st.button("SEND")

if send and st.session_state.user_input.strip():
    st.session_state.messages.append(("HCP", st.session_state.user_input))
    output = generate_sales_call(st.session_state.user_input)
    st.session_state.messages.append(("AI", output))
    audio = text_to_voice(output)
    if audio:
        st.audio(audio, format="audio/mp3")
    st.session_state.user_input = ""  # Clear input

# ============================================================
# SHOW LATEST GENERATED RESPONSE
# ============================================================
if st.session_state.messages:
    last_role, last_msg = st.session_state.messages[-1]
    if last_role == "AI":
        st.markdown(
            f"""
            <div style="background:rgba(255,255,255,0.1); padding:12px; border-radius:12px; margin-top:8px;">
                <b>Latest AI Response:</b><br>{last_msg}
            </div>
            """,
            unsafe_allow_html=True,
        )

# ============================================================
# FOOTER DISCLAIMER
# ============================================================
st.markdown(
    "<div style='position:fixed; bottom:0; width:100%; text-align:center; font-size:12px; color:#aaa;'>Internal use only. Generated content limited to approved materials.</div>",
    unsafe_allow_html=True,
)
