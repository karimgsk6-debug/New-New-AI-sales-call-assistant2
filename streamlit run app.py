# ============================================================
# app.py — AI Medical Rep Sales Call Assistant (ENTERPRISE)
# Brand-governed | SalesModule-driven | Voice-enabled | Hologram UI
# ============================================================

import streamlit as st
import os, tempfile, base64

# ============================================================
# 🔐 GROQ API KEY
# ============================================================
GROQ_API_KEY = "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"

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

AI_AVATAR = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"
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
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# BRAND DATA — SOURCE OF TRUTH
# ============================================================
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["Reach", "Acquire", "Convert", "Engage"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "specialties": ["GP", "Immunology", "Internal Medicine"],
        "references_path": os.path.join(REFERENCE_PATH, "shingrix"),
        "sales_path": os.path.join(SALES_MODULE_PATH, "shingrix"),
        "call_flow": ["Prepare", "Engage", "Create Opportunity", "Influence", "Close"],
        "objections": {
            "efficacy": "Durable protection across age groups.",
            "safety": "Known AE profile vs shingles complications.",
            "cost": "Prevention reduces downstream burden."
        },
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Identify", "Trial", "Routine", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber"],
        "specialties": ["Oncology"],
        "references_path": os.path.join(REFERENCE_PATH, "jemperli"),
        "sales_path": os.path.join(SALES_MODULE_PATH, "jemperli"),
        "call_flow": ["COCO", "Anchor", "Engage", "Close"],
        "objections": {
            "efficacy": "Durable responses in dMMR/MSI-H.",
            "safety": "Predictable immune AE management.",
            "access": "Reimbursement pathways available."
        },
    },
}

# ============================================================
# SESSION STATE
# ============================================================
def init_session():
    defaults = {
        "selected_brand": "shingrix",
        "hcp_persona": "",
        "tone": "executive",
        "temperature": 0.3,
        "medical_summary": "",
        "sales_summary": "",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_session()

# ============================================================
# GROQ CLIENT (SAFE)
# ============================================================
def get_client():
    if not GROQ_API_KEY or Groq is None:
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
# CORE GENERATION — GOVERNED
# ============================================================
def generate_sales_call(user_input):
    brand = st.session_state.selected_brand
    bconf = brand_data[brand]

    sales_module = load_folder(bconf["sales_path"])
    references = load_folder(bconf["references_path"])

    st.session_state.sales_summary = sales_module[:2500]
    st.session_state.medical_summary = references[:2500]

    if not sales_module or not references:
        return "❌ Approved materials missing."

    client = get_client()
    if not client:
        return "⚠️ GROQ API unavailable."

    system_prompt = f"""
You are a pharmaceutical sales excellence coach.

STRICT RULES:
- Use ONLY provided Sales Module and References
- Follow call flow: {bconf['call_flow']}
- No external knowledge
- Brand: {bconf['display']}
Persona: {st.session_state.hcp_persona}
Tone: {st.session_state.tone}
"""

    user_prompt = f"""
SALES MODULE:
{sales_module}

REFERENCES:
{references}

TASK:
Generate a compliant sales call.
Scenario:
{user_input}
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
    brand = st.selectbox("Brand", list(brand_data.keys()))
    st.session_state.selected_brand = brand
    bconf = brand_data[brand]

    st.session_state.hcp_persona = st.selectbox("HCP Persona", bconf["personas"])
    st.selectbox("Specialty", bconf["specialties"])
    st.session_state.tone = st.selectbox("Tone", ["executive", "clinical", "coaching"])
    st.session_state.temperature = st.slider("Creativity", 0.0, 1.0, 0.3)

# ============================================================
# HEADER
# ============================================================
st.markdown(
    f"""
    <h2>🧠 AI Sales Call Assistant — {bconf['display']}</h2>
    <img src="{AI_AVATAR}" width="70" style="float:right;border-radius:50%;box-shadow:0 0 14px cyan;">
    """,
    unsafe_allow_html=True,
)

# ============================================================
# MAIN UI
# ============================================================
scenario = st.text_area("Visit objective / objection / patient profile", height=140)

if st.button("Generate Brand-Specific Sales Call"):
    output = generate_sales_call(scenario)

    # ✅ TEXT FIRST
    st.markdown(output)

    # ✅ VOICE BELOW TEXT
    audio = text_to_voice(output)
    if audio:
        st.audio(audio, format="audio/mp3")

# ============================================================
# SUMMARIES
# ============================================================
with st.expander("📚 Medical References Summary"):
    st.text_area("", st.session_state.medical_summary, height=160)

with st.expander("📊 Sales Module Summary"):
    st.text_area("", st.session_state.sales_summary, height=160)

# ============================================================
# FOOTER DISCLAIMER (FIXED)
# ============================================================
st.markdown(
    """
    <div style="position:fixed;bottom:6px;left:10px;font-size:12px;color:#9aa;">
    ⚠️ Internal use only. Generated content restricted to approved materials.
    </div>
    """,
    unsafe_allow_html=True,
)
