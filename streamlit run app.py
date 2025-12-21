# ============================================================
# app.py — AI Medical Rep Sales Call Assistant (ENTERPRISE)
# Enhanced UI: Color-coded chat bubbles + Clickable prompts + Voice
# ============================================================

import streamlit as st
import os, base64, tempfile, re

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
        "suggestions": [],
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_session()

# ============================================================
# BRAND DATA (Shingrix, Jemperli, Trelegy)
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
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited eligibility", "Access/reimbursement issues"],
        "specialties": ["Oncologist", "Medical Oncologist"],
        "references_path": os.path.join(REFERENCE_PATH, "jemperli"),
        "sales_path": os.path.join(SALES_MODULE_PATH, "jemperli"),
        "call_flow": ["COCO", "Anchor", "Engage", "Close"],
        "objections": {
            "efficacy": "Discuss durable responses in dMMR/MSI-H and appropriate patient selection.",
            "safety": "Share safety profile and monitoring guidance to reduce perceived risk.",
            "access": "Offer starter kits or initiation support and reimbursement pathways."
        }
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Side effect concerns", "Cost/coverage"],
        "specialties": ["GP", "Pulmonologist", "Internal Medicine", "Respiratory Specialist"],
        "references_path": os.path.join(REFERENCE_PATH, "trelegy"),
        "sales_path": os.path.join(SALES_MODULE_PATH, "trelegy"),
        "call_flow": ["Prepare", "Engage", "Demonstrate", "Address Access", "Close"],
        "objections": {
            "device": "Offer quick practical coaching and demo materials.",
            "coverage": "Explain access options and patient support programs.",
            "effectiveness": "Share comparative outcomes framed for real-world practice."
        }
    }
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
    }
    return profiles.get(persona, {"quick_win": "Offer concise actionable next step."})

# ============================================================
# OBJECTION HANDLER
# ============================================================
def objection_response(product_key, objection_key, persona):
    product = brand_data.get(product_key, {})
    base = product.get("objections", {})
    reply = base.get(objection_key, "Acknowledge concern and propose next step.")
    prof = persona_profile(persona)
    return f"{reply} (Tailored: {prof['quick_win']})"

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
Generate a full sales call aligned to the call flow.
Scenario:
{user_input}

Include:
- Persona-adapted questions
- 1–2 objections
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

    output = resp.choices[0].message.content
    suggestions = re.findall(r"- (.+)", output)
    st.session_state.suggestions = suggestions[:3]
    return output

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
# TITLE BOX
# ============================================================
st.markdown(
    f"""
    <div style='background: rgba(255,255,255,0.15); padding:10px; border-radius:12px; display:flex; align-items:center; justify-content:space-between;'>
        <img src="{GSK_LOGO_RAW}" style="height:28px;">
        <h3 style="margin:0;">💡 AI Sales Call Assistant — {bconf['display']}</h3>
        <img src="{AI_LOGO_RAW}" style="height:28px;">
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# CHAT DISPLAY (color-coded)
# ============================================================
for role, msg in st.session_state.messages:
    if role == "HCP":
        bg = "rgba(173,216,230,0.3)"  # light blue
        avatar = HCP_AVATAR
    else:
        bg = "rgba(144,238,144,0.3)"  # light green
        avatar = SALES_AVATAR
    st.markdown(
        f"""
        <div style="display:flex; align-items:flex-start; gap:12px; margin:6px 0;">
            <img src="{avatar}" width="48" style="border-radius:50%;">
            <div style="background:{bg}; padding:10px; border-radius:12px; max-width:75%; white-space:pre-wrap;">
                <b>{role}:</b> {msg}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# BOTTOM INPUT
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
    st.session_state.user_input = ""

# ============================================================
# CLICKABLE SUGGESTIONS
# ============================================================
if st.session_state.suggestions:
    st.markdown("<b>Suggested phrases for Sales Rep:</b>", unsafe_allow_html=True)
    for s in st.session_state.suggestions:
        st.button(s, key=s)

# ============================================================
# FOOTER DISCLAIMER
# ============================================================
st.markdown(
    "<div style='position:fixed; bottom:0; width:100%; text-align:center; font-size:12px; color:#aaa;'>Internal use only. Generated content limited to approved materials.</div>",
    unsafe_allow_html=True,
)
