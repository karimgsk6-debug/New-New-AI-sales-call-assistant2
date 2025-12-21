# ============================================================
# app.py — AI Medical Rep Sales Call Assistant (ENTERPRISE)
# Brand-governed | SalesModule-driven | Human Voice | Coaching Scripts
# ============================================================

import streamlit as st
import os, tempfile

# ============================================================
# 🔐 GROQ API KEY (USE STREAMLIT SECRETS IN CLOUD)
# ============================================================
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")

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
# PATH CONFIG
# ============================================================
BASE_PATH = ".devcontainer"
SALES_MODULE_PATH = os.path.join(BASE_PATH, "SalesModule")
REFERENCE_PATH = os.path.join(BASE_PATH, "references")

AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# BRAND DATA — SINGLE SOURCE OF TRUTH
# ============================================================
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "personas": [
            "Uncommitted Vaccinator",
            "Reluctant Efficiency",
            "Patient Influenced",
            "Committed Vaccinator",
        ],
        "specialties": ["GP", "Immunology", "Internal Medicine"],
        "segments": ["Reach", "Acquire", "Convert", "Engage"],
        "references_path": os.path.join(REFERENCE_PATH, "shingrix"),
        "sales_path": os.path.join(SALES_MODULE_PATH, "shingrix"),
        "call_flow": [
            "Prepare",
            "Engage",
            "Explore Unmet Need",
            "Position Value",
            "Handle Objections",
            "Close & Commit",
        ],
        "objections": {
            "efficacy": "Durable protection across age groups.",
            "safety": "Known AE profile vs shingles complications.",
            "cost": "Prevention reduces downstream burden.",
        },
    },
    "jemperli": {
        "display": "Jemperli",
        "personas": [
            "Data-Driven Oncologist",
            "Skeptical Specialist",
            "Innovator Prescriber",
        ],
        "specialties": ["Oncology"],
        "segments": ["Identify", "Trial", "Routine", "Advocacy"],
        "references_path": os.path.join(REFERENCE_PATH, "jemperli"),
        "sales_path": os.path.join(SALES_MODULE_PATH, "jemperli"),
        "call_flow": ["COCO", "Anchor", "Engage", "Close"],
        "objections": {
            "efficacy": "Durable responses in dMMR/MSI-H.",
            "safety": "Predictable immune AE management.",
            "access": "Reimbursement pathways available.",
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
        "tone": "coaching",
        "temperature": 0.4,
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
    if not GROQ_API_KEY:
        st.warning("⚠️ GROQ API key not set")
        return None
    if Groq is None:
        st.warning("⚠️ groq package missing")
        return None
    try:
        return Groq(api_key=GROQ_API_KEY)
    except:
        st.error("❌ GROQ authentication failed")
        return None

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
# CORE GENERATION — COACHING & SCRIPTED
# ============================================================
def generate_sales_call(user_input):
    brand = st.session_state.selected_brand
    bconf = brand_data[brand]

    sales_module = load_folder(bconf["sales_path"])
    references = load_folder(bconf["references_path"])

    st.session_state.sales_summary = sales_module[:2500]
    st.session_state.medical_summary = references[:2500]

    if not sales_module or not references:
        return "❌ Approved Sales Module or References are missing."

    client = get_client()
    if not client:
        return "⚠️ GROQ API unavailable."

    system_prompt = f"""
You are an elite pharmaceutical sales coach.

STRICT RULES:
- Use ONLY the provided Sales Module and Medical References
- Follow this call flow exactly: {bconf['call_flow']}
- Do NOT add external knowledge
- Do NOT mention other brands
- Write spoken, field-ready language

VOICE STYLE:
- Conversational
- Coaching tone
- Short sentences
- No symbols, no bullets, no markdown

Brand: {bconf['display']}
Persona: {st.session_state.hcp_persona}
Tone: {st.session_state.tone}
"""

    user_prompt = f"""
SALES MODULE:
{sales_module}

MEDICAL REFERENCES:
{references}

TASK:
Generate a STEP-BY-STEP sales call.

For EACH step in the call flow, provide:
- What the medical rep says (verbatim script)
- Alternative wording (shorter)
- A question to ask the HCP
- Likely HCP response
- How the rep should follow up

Use first-person, real field language.
Provide multiple examples of what to say.
Avoid formatting symbols.

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
# TEXT → HUMAN VOICE (CLEANED)
# ============================================================
def clean_for_voice(text):
    bad = ["###", "**", "*", "-", "•"]
    for b in bad:
        text = text.replace(b, "")
    text = text.replace("\n\n", ". ").replace("\n", ". ")
    return text

def text_to_voice(text):
    if not gTTS:
        return None
    cleaned = clean_for_voice(text)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    gTTS(text=cleaned[:1200], lang="en", slow=False).save(tmp.name)
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
    st.selectbox("Segment", bconf["segments"])
    st.session_state.tone = st.selectbox("Tone", ["coaching", "executive", "clinical"])
    st.session_state.temperature = st.slider("Creativity", 0.0, 1.0, 0.4)

# ============================================================
# HEADER
# ============================================================
st.markdown(
    f"""
    <h2>🧠 AI Sales Call Coach — {bconf['display']}</h2>
    <img src="{AI_AVATAR}" width="70" style="float:right;border-radius:50%;box-shadow:0 0 14px cyan;">
    """,
    unsafe_allow_html=True,
)

# ============================================================
# MAIN UI
# ============================================================
scenario = st.text_area("Visit objective / patient profile / objection", height=140)

if st.button("Generate Sales Call Coaching"):
    output = generate_sales_call(scenario)

    st.markdown(output)

    audio = text_to_voice(output)
    if audio:
        st.audio(audio, format="audio/mp3")

# ============================================================
# SUMMARIES (RAG OUTPUT)
# ============================================================
with st.expander("📚 Medical References Summary"):
    st.text_area(
        "Medical",
        st.session_state.medical_summary,
        height=160,
        key="med_sum",
        disabled=True,
    )

with st.expander("📊 Sales Module Summary"):
    st.text_area(
        "Sales",
        st.session_state.sales_summary,
        height=160,
        key="sales_sum",
        disabled=True,
    )

# ============================================================
# FOOTER DISCLAIMER
# ============================================================
st.markdown(
    """
    <div style="position:fixed;bottom:6px;left:10px;font-size:12px;color:#9aa;">
    Internal use only. Content generated strictly from approved materials.
    </div>
    """,
    unsafe_allow_html=True,
)
