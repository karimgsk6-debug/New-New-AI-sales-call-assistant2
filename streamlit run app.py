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

from gtts import gTTS

ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    elevenlabs.api_key = ELEVENLABS_API_KEY
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
# Copilot prefill
if "prefilled_prompt" not in st.session_state or st.session_state.prefilled_prompt is None:
    st.session_state.prefilled_prompt = ""

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
  width: 1300px;
  position: relative;
  animation: fadeIn 1.2s ease-in-out;
}}

.title-box img.ai-logo {{
    position: absolute;
    top: 10px;
    right: 15px;
    width: 150px;
}}

.pdf-summary-box {{
  background: #E6F0FF; 
  padding: 12px; 
  border-radius: 14px; 
  margin-bottom: 12px;
  white-space: pre-line;
}}

.chat-container {{
  max-height: 65vh;
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
.chat-bubble-audio {{ background: #e2e2e2; margin-right:auto; font-size:0.9em; padding:10px; margin-top:12px; }}

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
    font-size: 14px;
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
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    st.warning("⚠️ Missing GROQ_API_KEY in Streamlit Secrets")
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

# ---------------------------- Helper Functions ----------------------------
def load_local_references(folder_path):
    text_all = ""
    warning = None
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return "", f"⚠️ Folder does not exist: {folder_path}"
    files = [f for f in os.listdir(folder_path) if f.lower().endswith((".pdf", ".txt"))]
    if not files:
        return "", f"ℹ️ No files found in {folder_path}"
    for file in files:
        file_path = os.path.join(folder_path, file)
        try:
            if file.lower().endswith(".pdf"):
                reader = PdfReader(file_path)
                for page in reader.pages:
                    text_all += page.extract_text() or ""
            elif file.lower().endswith(".txt"):
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text_all += f.read()
        except Exception as e:
            text_all += f"\n[Error reading {file}: {e}]"
    return text_all.strip(), None

def load_external_references(url_list):
    all_text = ""
    for url in url_list:
        try:
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                all_text += r.text + "\n"
            else:
                all_text += f"\n[Could not fetch {url} (status {r.status_code})]"
        except Exception as e:
            all_text += f"\n[Error fetching {url}: {e}]"
    return all_text

# ---------------------------- Sidebar ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", list(brand_data.keys()), key="select_brand")
    selected_brand = brand_data[brand]
    segment = st.selectbox("Segment", selected_brand["segments"], key="select_segment")
    persona = st.selectbox("HCP Persona", selected_brand["personas"], key="select_persona")
    barrier = st.multiselect("Doctor Barrier", selected_brand["barriers"], key="select_barrier")
    specialty = st.selectbox("Specialty", specialties, key="select_specialty")
    objective = st.selectbox("Objective", objectives, key="select_objective")
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"], key="select_tone")
    st.session_state.language = st.radio("Language", ["English", "Arabic"], horizontal=True, key="select_language")

with st.sidebar.expander("🌐 Add External Reference URLs", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT", "DOCX"], horizontal=True)
    if st.button("💾 Export Chat"):
        text_export = "\n\n".join([f"{e['role'].capitalize()}: {e['content']}" for e in st.session_state.chat_history])
        if export_format == "DOCX" and DOCX_AVAILABLE:
            doc = Document()
            doc.add_heading("AI Sales Call Assistant Export", 0)
            doc.add_paragraph(f"Brand: {brand.upper()} | Date: {datetime.now().strftime('%Y-%m-%d')}")
            doc.add_paragraph(text_export)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            doc.save(tmp.name)
            st.download_button("⬇️ Download DOCX", open(tmp.name, "rb"), file_name=f"{brand}_chat.docx")
        else:
            st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{brand}_chat.txt")

if st.sidebar.button("🗑️ Clear Chat"):
    st.session_state.chat_history = []
    st.rerun()

# ---------------------------- Title ----------------------------
st.markdown(f'''
<div class="title-box">
    <img src="{GSK_LOGO_URL}" width="140">
    <img src="{AI_LOGO_URL}" class="ai-logo">
    <h1>💡 AI Sales Call Assistant</h1>
    <p>Empowering reps for smarter <b style="color:#FF6F00;">{brand.upper()}</b> conversations</p>
</div>
''', unsafe_allow_html=True)

# ---------------------------- PDF Upload ----------------------------
uploaded_file = st.file_uploader("📄 Upload PDF for reference", type=["pdf"])
if uploaded_file is not None:
    reader = PdfReader(uploaded_file)
    pdf_text = ""
    for page in reader.pages:
        pdf_text += page.extract_text() or ""
    st.session_state.uploaded_pdf_text = pdf_text
    st.session_state.pdf_summary = pdf_text[:1500]  # short summary

if st.session_state.pdf_summary:
    st.markdown(f'<div class="pdf-summary-box"><b>PDF Summary:</b>\n{st.session_state.pdf_summary}</div>', unsafe_allow_html=True)

# ---------------------------- Chat UI ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        st.markdown(f'<div class="chat-bubble-user">{escape(msg["content"])}</div>', unsafe_allow_html=True)
    elif msg["role"] == "assistant":
        st.markdown(f'<div class="chat-bubble-ai">{escape(msg["content"])}</div>', unsafe_allow_html=True)
        if "audio" in msg and msg["audio"]:
            st.audio(base64.b64decode(msg["audio"]))
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Fixed Chat Input ----------------------------
user_input = st.chat_input(
    "Ask or continue your sales dialogue...",
    value=st.session_state.prefilled_prompt
)

if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    # Generate AI response placeholder
    ai_resp = f"Simulated AI response for '{user_input}' (brand: {brand})"  # Replace with actual AI call
    # Optional audio
    audio_base64 = None
    if ELEVENLABS_AVAILABLE:
        try:
            audio_data = elevenlabs.generate(
                text=ai_resp,
                voice=ELEVENLABS_VOICE_ID,
                model="eleven_multilingual_v1"
            )
            audio_base64 = base64.b64encode(audio_data).decode("utf-8")
        except Exception:
            audio_base64 = None
    st.session_state.chat_history.append({"role": "assistant", "content": ai_resp, "audio": audio_base64})
    st.session_state.prefilled_prompt = ""
    st.rerun()


# ---------------------------- Export / Download ----------------------------
if st.session_state.chat_history:
    with st.expander("Export / Download Chat", expanded=False):
        text_export = "\n\n".join([f"{e['role'].capitalize()}: {e['content']}" for e in st.session_state.chat_history])
        if DOCX_AVAILABLE and st.button("Export as DOCX"):
            doc = Document()
            doc.add_heading("AI Sales Call Assistant Export", 0)
            doc.add_paragraph(f"Brand: {brand.upper()} | Date: {datetime.now().strftime('%Y-%m-%d')}")
            doc.add_paragraph(text_export)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            doc.save(tmp.name)
            st.download_button("⬇️ Download DOCX", open(tmp.name, "rb"), file_name=f"{brand}_chat.docx")
        st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{brand}_chat.txt")

# ---------------------------- Disclaimer ----------------------------
st.markdown(f"""
<div class="fixed-disclaimer">
<b>Disclaimer:</b> ⚠️This AI Sales Call Assistant is intended for educational and informational purposes only. 
It does not replace official medical references, product labeling, or company-approved materials. 
Always verify with the latest approved product information and compliance guidance before use.
</div>
""", unsafe_allow_html=True)

