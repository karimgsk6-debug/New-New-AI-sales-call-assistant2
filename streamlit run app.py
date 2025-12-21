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
def load_img_base64(path):
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

GSK_LOGO_RAW = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/AURA1.png"
AI_AVATAR = load_img_base64(".devcontainer/Visuals/futuristic_hologram_ai.gif")
HCP_AVATAR = load_img_base64(".devcontainer/Visuals/HCP.gif")
SALES_REP_AVATAR = load_img_base64(".devcontainer/Visuals/sales rep.gif")
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

# ============================================================
# BRAND DATA
# ============================================================
BASE_PATH = ".devcontainer"
SALES_MODULE_PATH = os.path.join(BASE_PATH, "SalesModule")
REFERENCE_PATH = os.path.join(BASE_PATH, "references")

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
    }
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
    <div style="background: rgba(255,255,255,0.85); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; margin-bottom:12px;">
        <img src="{GSK_LOGO_RAW}" style="position:absolute; left:12px; height:48px;">
        <h2>💡 AI Sales Call Assistant — {bconf['display']}</h2>
        <img src="{AI_LOGO_RAW}" style="position:absolute; right:12px; height:48px;">
    </div>
    """,
    unsafe_allow_html=True,
)

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
# GENERATE SALES CALL
# ============================================================
def generate_sales_call(user_input):
    sales_module = load_folder(bconf["sales_path"])
    references = load_folder(bconf["references_path"])
    client = get_client()
    if not client:
        return "⚠️ GROQ API unavailable"
    if not sales_module or not references:
        return "❌ Missing approved materials"

    system_prompt = f"""
You are a pharmaceutical sales coach.
Use ONLY provided Sales Module & References.
Call flow: {bconf['call_flow']}
Brand: {bconf['display']}
HCP Persona: {st.session_state.hcp_persona}
"""
    user_prompt = f"""
Scenario:
{user_input}

Include:
- Persona-adapted HCP questions
- 1–2 objections
- Example sentences for sales rep
- Clear next-step close
"""
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": user_prompt}],
        temperature=0.7
    )
    return resp.choices[0].message.content

# ============================================================
# TEXT TO VOICE
# ============================================================
def text_to_voice(text):
    if not gTTS:
        return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    gTTS(text=text[:1200], lang="en").save(tmp.name)
    return open(tmp.name, "rb").read()

# ============================================================
# SIDEBAR CONFIG
# ============================================================
with st.sidebar:
    st.header("Call Config")
    st.session_state.selected_brand = st.selectbox("Brand", list(brand_data.keys()))
    bconf = brand_data[st.session_state.selected_brand]
    st.session_state.hcp_persona = st.selectbox("HCP Persona", bconf["personas"])
    st.selectbox("Specialty", bconf["specialties"])
    st.selectbox("Segment", bconf["segments"])
    st.session_state.tone = st.selectbox("Tone", ["executive", "clinical", "coaching"])
    st.session_state.temperature = st.slider("Creativity", 0.0, 1.0, 0.3)

# ============================================================
# CHAT INTERFACE
# ============================================================
st.markdown("<h2>💬 Conversation</h2>", unsafe_allow_html=True)

# Display messages
for role, text in st.session_state.messages:
    avatar = SALES_REP_AVATAR if role == "AI" else HCP_AVATAR
    st.markdown(
        f"""
        <div style="display:flex; align-items:flex-start; gap:10px; margin-bottom:8px;">
            <img src="data:image/gif;base64,{avatar}" width="48" style="border-radius:50%;"/>
            <div style="background:rgba(0,255,255,0.1); padding:10px; border-radius:10px; max-width:80%;">
                {text}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# Bottom input
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
    st.experimental_rerun()

# ============================================================
# FOOTER
# ============================================================
st.markdown("<small>Internal use only. Generated content limited to approved materials.</small>", unsafe_allow_html=True)
