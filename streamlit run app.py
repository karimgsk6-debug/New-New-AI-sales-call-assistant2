# app.py
import streamlit as st
from PIL import Image
from io import BytesIO
import re
import tempfile
import base64
import os
from groq import Groq
from PyPDF2 import PdfReader
from html import escape
import requests
from datetime import datetime
import json

# Optional DOCX export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

# ---------------------------- TTS Setup ----------------------------
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except ModuleNotFoundError:
    ELEVENLABS_AVAILABLE = False

from gtts import gTTS  # gTTS fallback

ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")

if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    try:
        elevenlabs.api_key = ELEVENLABS_API_KEY
    except Exception:
        ELEVENLABS_AVAILABLE = False
else:
    ELEVENLABS_AVAILABLE = False

# ---------------------------- CONFIG ----------------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- Session Defaults ----------------------------
if "chat_history" not in st.session_state or not isinstance(st.session_state.chat_history, list):
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "voice_pref" not in st.session_state:
    st.session_state.voice_pref = "Old Male"
if "language" not in st.session_state:
    st.session_state.language = "English"
if "pdf_summary_size" not in st.session_state:
    st.session_state.pdf_summary_size = "Normal"
if "chat_key" not in st.session_state:
    st.session_state.chat_key = 0
if "user_id" not in st.session_state:
    st.session_state.user_id = "anonymous"

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Background1.jpeg"
GSK_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/GSK-logo.png"
AI_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/AURA.png"

# ---------------------------- CSS ----------------------------
CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-attachment: fixed;
  background-size: auto 130%;
}}

@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(-10px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.title-box {{
  background: rgba(230,230,230,0.7);
  padding: 10px;
  border-radius: 15px;
  text-align: left;
  margin: 12px auto;
  width: 1100px;
  position: relative;
  animation: fadeIn 1.0s ease-in-out;
}}

.title-box img.ai-logo {{
    position: absolute;
    top: 10px;
    right: 15px;
    width: 120px;
}}

.pdf-summary-box {{
  background: #E6F0FF; 
  padding: 12px; 
  border-radius: 14px; 
  margin-bottom: 12px;
  white-space: pre-line;
  color: #012a4a;
}}

.chat-container {{
  max-height: 60vh;
  overflow-y: auto;
  padding: 12px;
  border-radius: 10px;
  background: rgba(240,240,240,0.7);
  margin-bottom: 20px;
}}

.chat-bubble-user, .chat-bubble-ai, .chat-bubble-audio {{
  display:block;
  padding:12px;
  border-radius:12px;
  margin:12px 0;
  max-width: 90%;
  word-wrap: break-word;
}}

.chat-bubble-user {{ background: #0078D7; color:white; margin-left:auto; }}
.chat-bubble-ai {{ background: #d9f0ff; margin-right:auto; color:#000; }}
.chat-bubble-audio {{ background: #e2e2e2; margin-right:auto; font-size:0.95em; padding:10px; margin-top:12px; }}

.fixed-chat-input {{
    position: fixed;
    bottom: 20px;
    left: 20px;
    right: 20px;
    z-index: 10002;
}}

.fixed-chat-input textarea {{
    width: 100%;
    min-height: 60px;
    max-height: 180px;
    resize: vertical;
}}

.send-button {{
    position: fixed;
    bottom: 20px;
    right: 30px;
    z-index: 10003;
    height: 40px;
    width: 100px;
}}

.fixed-disclaimer {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: rgba(255, 255, 255, 0.95);
    color: #444;
    text-align: center;
    font-size: 13px;
    padding: 8px;
    border-top: 2px solid #FF6F00;
    z-index: 9999;
    animation: fadeIn 1.5s ease-in-out;
}}

section[data-testid="stSidebar"] .st-expanderHeader {{
    color: #FF6F00 !important;
    font-weight: 700;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ Client ----------------------------
GROQ_API_KEY = "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"  # <--- Hardcoded Groq API Key
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Brand Configurations ----------------------------
def safe_makedirs(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        st.warning(f"⚠️ Could not create folder {path}: {e}")

safe_makedirs(".devcontainer/references/shingrix")
safe_makedirs(".devcontainer/references/jemperli")
safe_makedirs(".devcontainer/SalesModule/shingrix")
safe_makedirs(".devcontainer/SalesModule/jemperli")

brand_data = {
    "shingrix": {
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "references_path": ".devcontainer/references/shingrix/"
    },
    "jemperli": {
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited patient eligibility", "Access/reimbursement issues"],
        "references_path": ".devcontainer/references/jemperli/"
    }
}

specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Rheumatologist", "Internal medicine", "Oncologist"]
objectives = ["Awareness", "Adoption", "Retention"]

# ---------------------------- Moderation Module ----------------------------
AUDIT_LOG = ".prompt_audit_log.jsonl"

BLACKLIST_TERMS = [
    r"\boff-?label\b", r"\bunapproved\b", r"\bunauthoriz(?:ed|ed)\b",
    r"\bcure\b", r"\bmiracle\b", r"\bfree trial\b", r"\bdiscount\b",
    r"\bprice\b", r"\bcompare\b.*\bcompetitor\b", r"\bdosage\b", r"\bprescribe\b",
]

SENSITIVE_PATIENT_PATTERNS = [
    r"\bdiagnos(?:e|is|ing)\b", r"\bprescrib(?:e|ing|ed)\b",
    r"\bpatient\b", r"\bunder-?\d+\b", r"\bchild(?:ren)?\b", r"\bage\b"
]

BYPASS_PATTERNS = [
    r"ignore (?:previous|earlier) instructions",
    r"disregard (?:rules|policy)",
    r"bypass (?:filter|moderation)",
    r"act as if you are"
]

ALLOWED_STARTS = [
    "Explain the approved indications for",
    "Summarise approved clinical evidence for",
    "List contraindications for",
    "Provide the approved dosing guidance for"
]

REWRITE_TEMPLATES = {
    "age_question": "Provide approved age indications and age-related safety info for {drug}.",
    "dose_question": "Provide approved dosing information for {drug}.",
}

def moderate_prompt(prompt: str) -> bool:
    # Blacklist check
    for term in BLACKLIST_TERMS:
        if re.search(term, prompt, re.I):
            return False
    return True

# ---------------------------- Sidebar ----------------------------
with st.sidebar:
    st.header("Filters & Settings")
    selected_brand = st.selectbox("Select Brand", ["shingrix", "jemperli"])
    selected_specialty = st.selectbox("Specialty", ["All"] + specialties)
    selected_objective = st.selectbox("Objective", ["All"] + objectives)
    st.markdown("---")
    st.subheader("Voice & Language")
    st.session_state.voice_pref = st.selectbox("Voice", ["Old Male", "Young Female"])
    st.session_state.language = st.selectbox("Language", ["English", "Arabic"])

# ---------------------------- PDF Upload ----------------------------
uploaded_file = st.file_uploader("Upload PDF reference", type=["pdf"])
if uploaded_file:
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    st.session_state.uploaded_pdf_text = text
    st.session_state.pdf_summary = f"PDF uploaded: {uploaded_file.name} | {len(text.split())} words"

# ---------------------------- Chat Interface ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for i, entry in enumerate(st.session_state.chat_history):
    if entry["role"] == "user":
        st.markdown(f'<div class="chat-bubble-user">{escape(entry["content"])}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">{escape(entry["content"])}</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

user_input = st.text_area("Type your question here...", key="chat_input")
if st.button("Send"):
    if not moderate_prompt(user_input):
        st.warning("⚠️ Your prompt contains restricted content.")
    else:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        # Dummy Groq response, replace with actual client call
        response_text = f"AI Response for: {user_input}"
        st.session_state.chat_history.append({"role": "assistant", "content": response_text})
        st.experimental_rerun()

# ---------------------------- Disclaimer ----------------------------
st.markdown(
    '<div class="fixed-disclaimer">'
    'This AI assistant provides **approved medical content only**. Do not rely on it for off-label or patient-specific advice.'
    '</div>', unsafe_allow_html=True
)
