# app.py - Full AI Sales Call Assistant with Enhanced Features
import streamlit as st
import os, re, tempfile, base64
from datetime import datetime
from html import escape

# -------------------------
# Optional Libraries
# -------------------------
try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

try:
    from gtts import gTTS
except Exception:
    gTTS = None

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except Exception:
    PYTTSX3_AVAILABLE = False

try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except Exception:
    ELEVENLABS_AVAILABLE = False

try:
    from groq import Groq
except Exception:
    Groq = None

# -------------------------
# Page Config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_BLOB_BASE = f"https://github.com/{REPO_USER}/{REPO_NAME}/blob/{COMMIT}/.devcontainer"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
BACKGROUND_URL = REPO_RAW_BASE + "/background1.png"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# -------------------------
# Session Defaults
# -------------------------
defaults = {
    "chat_history": [],
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.6,
    "search_mode": "deep",
    "medical_summary": "",
    "sales_summary": "",
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "followup_state": None,
    "language": "English"
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# -------------------------
# CSS & Background
# -------------------------
CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}}
.title-box {{
  background: rgba(255,255,255,0.95);
  padding: 12px;
  border-radius: 10px;
  margin-bottom: 12px;
  position: relative;
  display:flex;
  align-items:center;
  justify-content:center;
}}
.title-box img.left-logo {{ position:absolute; left:12px; height:64px; }}
.title-box img.right-logo {{ position:absolute; right:12px; height:64px; }}
.chat-container {{ max-height: 62vh; overflow-y:auto; padding:12px; background: rgba(255,255,255,0.95); border-radius:8px; margin-bottom:140px; }}
.chat-bubble-user {{ background:#0078D7; color:white; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto; }}
.chat-bubble-ai {{ background:#eef9ff; color:#000; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }}
.suggestion-pill {{ background:#fff; border:1px solid #ddd; padding:8px 12px; border-radius:20px; margin:6px; cursor:pointer; display:inline-block; }}
.suggestion-pill:hover {{ background:#f0f8ff; }}
.citation-box {{ background:#fbfbff; border-left:4px solid #0078D7; padding:8px; margin-top:8px; border-radius:6px; font-size:13px; white-space:pre-wrap; }}
.input-area {{ position: fixed; left:20px; right:20px; bottom:18px; z-index:9999; display:flex; gap:8px; align-items:flex-end; }}
.input-area textarea {{ width:100%; min-height:72px; max-height:250px; padding:10px; border-radius:8px; border:1px solid #ccc; resize:vertical; }}
.send-button {{ height:44px; padding:0 14px; border-radius:8px; border:none; background:#FF6F00; color:white; cursor:pointer; font-weight:600; }}
.fixed-disclaimer {{ position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# -------------------------
# Initialize GROQ Client
# -------------------------
GROQ_API_KEY = "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"
client = None
if Groq and GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

# -------------------------
# Brand Data (Updated)
# -------------------------
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "specialties": ["GP", "Dermatologist", "Geriatrician"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/",
        "sales_module": ["Pre-call Planning", "Prepare", "Engage", "Create Opportunities", "Influence", "Impact GSO", "Post-call Analysis"]
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited eligibility", "Access/reimbursement issues"],
        "specialties": ["Oncologist", "Medical Oncologist"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli/",
        "sales_module": ["COCO", "Anchor", "Engage", "Close"]
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Side effect concerns", "Cost/coverage"],
        "specialties": ["GP", "Pulmonologist", "Respiratory Specialist"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy/",
        "sales_module": ["Prepare", "Engage", "Demonstrate", "Address Access", "Close"]
    }
}

# -------------------------
# Helper Functions
# -------------------------
def read_file_text(path):
    if not os.path.exists(path): return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except: return ""

def simple_summary(text, bullets=6):
    sents = re.split(r'(?<=[.!?])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- " + s for s in selected])

def tts_preprocess(text):
    sents = re.split(r'(?<=[.!?])\s+', text.strip())
    clean = []
    for s in sents:
        s2 = re.sub(r'[\[\]\(\)\{\}<>\"*_:;=\\/]', '', s)
        clean.append(s2.strip())
    return " ... ".join(clean)

def generate_audio(text):
    t = tts_preprocess(text)
    if ELEVENLABS_AVAILABLE and st.secrets.get("ELEVENLABS_API_KEY") and st.secrets.get("ELEVENLABS_VOICE_ID"):
        try:
            elevenlabs.api_key = st.secrets.get("ELEVENLABS_API_KEY")
            audio_stream = elevenlabs.generate(text=t, voice=st.secrets.get("ELEVENLABS_VOICE_ID"), stream=True)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            with open(tmp.name,"wb") as f:
                for chunk in audio_stream: f.write(chunk)
            return base64.b64encode(open(tmp.name,"rb").read()).decode()
        except: pass
    if gTTS:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            gTTS(text=t, lang="en", slow=False).save(tmp.name)
            return base64.b64encode(open(tmp.name,"rb").read()).decode()
        except: pass
    return ""

# -------------------------
# Sidebar Filters / Selections
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    st.session_state.selected_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    bconf = brand_data[st.session_state.selected_brand]

    segment = st.selectbox("Segment", bconf["segments"])
    persona = st.selectbox("HCP Persona", bconf["personas"])
    barrier = st.multiselect("Doctor Barrier", bconf["barriers"])
    specialty = st.selectbox("Specialty", bconf["specialties"])
    objective = st.selectbox("Objective", ["Awareness","Adoption","Retention"])
    st.session_state.temperature = st.slider("Temperature", 0.0, 1.0, st.session_state.temperature, 0.05)
    st.session_state.search_mode = st.selectbox("Search Mode", ["deep","shallow"], index=0 if st.session_state.search_mode=="deep" else 1)
    st.session_state.language = st.radio("Language", ["English","Arabic"])
    st.caption("Summaries below are auto-generated from brand files.")
    if st.button("🗑️ Clear Chat"): st.session_state.chat_history = []

# -------------------------
# Title Box
# -------------------------
st.markdown(f"""
<div class="title-box">
  <img src="{GSK_LOGO_RAW}" class="left-logo">
  <h2>💡 AI Sales Call Assistant — {bconf['display']}</h2>
  <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# -------------------------
# Chat Input / Suggestions
# -------------------------
sugg_texts = [
    f"Generate call flow for {persona} focused on {objective}.",
    f"Handle objection: {', '.join(barrier) if barrier else 'None'} for {persona}.",
    f"Summarize HCP persona insights for {persona}.",
    f"Key talking points for {bconf['display']} in {segment}.",
    f"Draft a short adoption message for {bconf['display']} to a {specialty}."
]

st.markdown('<div style="margin-bottom:10px;">', unsafe_allow_html=True)
cols = st.columns(len(sugg_texts))
for i, s in enumerate(sugg_texts):
    if cols[i].button(s, key=f"sugg_{i}"):
        st.session_state.main_input = s
st.markdown('</div>', unsafe_allow_html=True)

user_text = st.text_area("", value=st.session_state.get("main_input",""), key="main_input_area", placeholder="Type your message here...")
send_clicked = st.button("Send", key="send_main")

# -------------------------
# Generate AI Response
# -------------------------
if send_clicked and user_text.strip():
    st.session_state.chat_history.append({"role":"user","content":user_text.strip()})

    # Build AI sales call response dynamically
    bmod = bconf["sales_module"]
    response_text = f"**💼 Sales Call Script for {bconf['display']}**\n\n"
    if st.session_state.pdf_summary:
        response_text += f"**📄 Relevant Document Summary:**\n{st.session_state.pdf_summary}\n\n"
    response_text += f"**🎯 Target Persona:** {persona}\n**👨‍⚕️ Relevant Specialties:** {specialty}\n**⚠️ Key Barriers:** {', '.join(barrier) or 'None'}\n\n"
    response_text += "**📝 Sales Call Flow:**\n"
    for i, mod in enumerate(bmod,1):
        response_text += f"- **{mod}**: Talking points tailored to {persona}, addressing barriers and benefits of {bconf['display']}.\n"
    response_text += f"\n**💡 User Prompt:** {user_text.strip()}"

    st.session_state.chat_history.append({"role":"assistant","content":response_text, "audio":generate_audio(response_text)})
    st.session_state.main_input = ""

# -------------------------
# Display Chat
# -------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for idx, msg in enumerate(st.session_state.chat_history):
    role = msg["role"]
    content = escape(msg["content"])
    if role=="user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {content}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {content}</div>', unsafe_allow_html=True)
        if msg.get("audio"):
            st.audio(base64.b64decode(msg["audio"]), format="audio/mp3")
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# PDF Upload Expander
# -------------------------
with st.expander("📄 Upload PDF/DOCX for AI Context", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
    size_option = st.selectbox("Summary Size", ["Concise","Normal","Long"], index=1)
    bullets_map = {"Concise":4,"Normal":6,"Long":10}

    if uploaded_pdf:
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp.write(uploaded_pdf.getvalue())
        tmp.close()
        text = read_file_text(tmp.name)
        st.session_state.uploaded_pdf_text = text
        st.session_state.pdf_summary = simple_summary(text, bullets=bullets_map[size_option])
        st.success("PDF processed and summarized!")

# -------------------------
# Footer
# -------------------------
st.markdown('<div class="fixed-disclaimer">© 2025 AI Sales Call Assistant | For internal use only. All rights reserved.</div>', unsafe_allow_html=True)
