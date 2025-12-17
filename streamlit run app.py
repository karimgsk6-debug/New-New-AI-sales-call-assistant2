# ============================================================
# app.py — AI Medical Rep Sales Call Assistant (ENTERPRISE)
# Brand-governed | SalesModule-driven | Hologram UI
# ============================================================

import streamlit as st
import os, re, tempfile, base64

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
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# BRAND DATA (SOURCE OF TRUTH)
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
# SESSION STATE
# ============================================================
def init_session():
    defaults = {
        "chat_history": [],
        "selected_brand": "shingrix",
        "hcp_persona": "",
        "tone": "executive",
        "temperature": 0.3,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_session()

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
# PERSONA PROFILE (for objections)
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
# Objection handling per product & persona
# ============================================================
def objection_response(product_key, objection_key, persona):
    product = brand_data.get(product_key, {})
    base = product.get("objections", {})
    reply = base.get(objection_key, "Acknowledge the concern, offer concise evidence, and propose a low-effort next step.")
    prof = persona_profile(persona)

    if "evidence" in persona.lower():
        return f"Answer (Evidence-led): {reply} Provide trial highlights and one quick citation; offer to share a 1-page evidence summary."
    if "time" in persona.lower():
        return f"Answer (Time-pressured): {reply} Then offer a single-sentence script and a nurse checklist to make adoption painless."
    if "skeptical" in persona.lower():
        return f"Answer (Skeptical): {reply} Start by acknowledging, then show safety data and a monitoring plan; propose a conservative pilot."
    if "early" in persona.lower():
        return f"Answer (Early-adopter): {reply} Highlight differentiation and offer to co-design a small pilot with outcome monitoring."
    return f"{reply} (Tailored suggestion: {prof['quick_win']})"

# ============================================================
# CORE GENERATION (BRAND-GOVERNED)
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

RULES (MANDATORY):
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
SALES MODULE (PRIMARY SOURCE):
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
# SIDEBAR (DYNAMIC FROM BRAND DATA)
# ============================================================
with st.sidebar:
    st.header("Call Configuration")

    brand = st.selectbox("Brand", list(brand_data.keys()))
    st.session_state.selected_brand = brand
    bconf = brand_data[brand]

    st.session_state.hcp_persona = st.selectbox(
        "HCP Persona",
        bconf["personas"]
    )

    st.selectbox("Specialty", bconf["specialties"])
    st.selectbox("Segment", bconf["segments"])

    st.session_state.tone = st.selectbox(
        "Tone", ["executive", "clinical", "coaching"]
    )

    st.session_state.temperature = st.slider(
        "Creativity", 0.0, 1.0, 0.3
    )

# ============================================================
# HEADER
# ============================================================
st.markdown(
    f"""
    <h2>💡 AI Sales Call Assistant — {brand_data[st.session_state.selected_brand]['display']}</h2>
    <img src="{AI_AVATAR}" width="64" style="float:right; border-radius:50%; box-shadow:0 0 12px rgba(0,255,255,0.6);"/>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# MAIN UI
# ============================================================
scenario = st.text_area(
    "Visit objective / patient profile / objection",
    height=140,
)

if st.button("🧠 Generate Brand-Specific Sales Call"):
    output = generate_sales_call(scenario)

    st.markdown(output)  # TEXT FIRST

    audio = text_to_voice(output)
    if audio:
        st.audio(audio, format="audio/mp3")

# ============================================================
# DISCLAIMER
# ============================================================
st.markdown(
    "<small>Internal use only. Generated content limited to approved materials.</small>",
    unsafe_allow_html=True,
)
