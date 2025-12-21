# ============================================================
# app.py — AI Medical Rep Sales Call Assistant (ENTERPRISE)
# Brand-governed | SalesModule-driven | Hologram UI
# ============================================================

import streamlit as st
import os, tempfile, base64

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
HCP_AVATAR = ".devcontainer/Visuals/HCP.gif"
SALES_REP_AVATAR = ".devcontainer/Visuals/sales rep.gif"
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
st.set_page_config(page_title="AI Sales Call Assistant",
                   layout="wide",
                   initial_sidebar_state="expanded")

# ============================================================
# BRAND DATA
# ============================================================
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
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
if "messages" not in st.session_state:
    st.session_state.messages = []
if "user_input" not in st.session_state:
    st.session_state.user_input = ""
if "selected_brand" not in st.session_state:
    st.session_state.selected_brand = "shingrix"
if "hcp_persona" not in st.session_state:
    st.session_state.hcp_persona = ""

bconf = brand_data[st.session_state.selected_brand]

# ============================================================
# TITLE BOX
# ============================================================
st.markdown(
    f"""
    <div class="title-box" style="background: rgba(255,255,255,0.85); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; position:relative; margin-bottom:12px;">
        <img src="{GSK_LOGO_RAW}" style="position:absolute; left:12px; height:48px;">
        <h2>💡 AI Sales Call Assistant — {bconf['display']}</h2>
        <img src="{AI_LOGO_RAW}" style="position:absolute; right:12px; height:48px;">
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# LOAD REFERENCES & SALES MODULES
# ============================================================
refs_folder = bconf.get("references_path", "")
sales_folder = bconf.get("sales_path", "")

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
# OBJECTION HANDLING
# ============================================================
def objection_response(product_key, objection_key, persona):
    product = brand_data.get(product_key, {})
    base = product.get("objections", {})
    reply = base.get(objection_key, "Acknowledge the concern, offer concise evidence, and propose a low-effort next step.")
    prof = persona_profile(persona)
    return f"{reply} (Tailored suggestion: {prof['quick_win']})"

# ============================================================
# CORE GENERATION
# ============================================================
def generate_sales_call(user_input):
    sales_module = load_folder(sales_folder)
    references = load_folder(refs_folder)

    if not sales_module or not references:
        return "❌ Missing approved materials"

    client = get_client()
    if not client:
        return "⚠️ GROQ API unavailable"

    system_prompt = f"""
You are a pharmaceutical sales excellence coach.
RULES:
- Use ONLY the provided Sales Module
- Use ONLY the provided References
- Follow call flow: {bconf['call_flow']}
- Do NOT introduce external knowledge
- Do NOT cross-reference other brands
Brand: {bconf['display']}
HCP Persona: {st.session_state.hcp_persona}
Tone: executive
"""
    user_prompt = f"""
SALES MODULE:
{sales_module}

MEDICAL REFERENCES:
{references}

TASK:
Generate a full sales call aligned to the defined call flow.
Scenario:
{user_input}

Include:
- Persona-adapted HCP questions
- 1–2 objections
- Clear next-step close
- Example sentences a sales rep can say
"""

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
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
    st.session_state.selected_brand = st.selectbox("Brand", list(brand_data.keys()))
    bconf = brand_data[st.session_state.selected_brand]
    st.session_state.hcp_persona = st.selectbox("HCP Persona", bconf["personas"])
    st.selectbox("Specialty", bconf["specialties"])
    st.selectbox("Segment", bconf["segments"])
    st.session_state.tone = st.selectbox("Tone", ["executive", "clinical", "coaching"])
    st.session_state.temperature = st.slider("Creativity", 0.0, 1.0, 0.3)

# ============================================================
# PROMPT SUGGESTIONS COLLAPSIBLE
# ============================================================
with st.expander("💡 Suggested lines to say to HCP"):
    st.markdown(
        """
        - “Based on clinical evidence, this product offers durable protection…”
        - “Many patients benefit from a simplified administration schedule…”
        - “One practical way to integrate this therapy is…”
        - “Addressing cost concerns: highlight long-term savings…”
        """
    )

# ============================================================
# CHAT INTERFACE
# ============================================================
st.markdown("<h2>💬 Conversation</h2>", unsafe_allow_html=True)

# Display previous messages
for role, text in st.session_state.messages:
    avatar = SALES_REP_AVATAR if role == "AI" else HCP_AVATAR
    st.markdown(
        f"""
        <div style="display:flex; align-items:flex-start; gap:10px; margin-bottom:8px;">
            <img src="{avatar}" width="48" style="border-radius:50%"/>
            <div style="background:rgba(0,255,255,0.1) if role=='AI' else rgba(255,255,255,0.06); padding:10px; border-radius:10px; max-width:80%;">
                {text}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# User input box at bottom
st.session_state.user_input = st.text_area("Type HCP scenario...", st.session_state.user_input, height=100, key="chat_input")
send = st.button("SEND")

if send and st.session_state.user_input.strip():
    output = generate_sales_call(st.session_state.user_input)
    st.session_state.messages.append(("HCP", st.session_state.user_input))
    st.session_state.messages.append(("AI", output))
    audio = text_to_voice(output)
    if audio:
        st.audio(audio, format="audio/mp3")
    st.session_state.user_input = ""

# ============================================================
# FOOTER
# ============================================================
st.markdown(
    "<small>Internal use only. Generated content limited to approved materials.</small>",
    unsafe_allow_html=True
)
