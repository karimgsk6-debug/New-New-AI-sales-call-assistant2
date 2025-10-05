# app.py
import streamlit as st
from io import BytesIO
import re
import tempfile
import base64
import os
from groq import Groq
from PyPDF2 import PdfReader
from html import escape
import requests

# Optional docx export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False

# ---------------------------- TTS Setup ----------------------------
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except ModuleNotFoundError:
    ELEVENLABS_AVAILABLE = False

from gtts import gTTS

ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "EXAMPLE_VOICE_ID")  # <-- update to your new voice ID
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    elevenlabs.api_key = ELEVENLABS_API_KEY
else:
    ELEVENLABS_AVAILABLE = False

def generate_audio(text):
    """Generate TTS audio for the AI response"""
    text = re.sub(r'[{}*]', '', text)
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        if ELEVENLABS_AVAILABLE:
            audio_stream = elevenlabs.generate(text=text, voice=ELEVENLABS_VOICE_ID, stream=True)
            with open(tmp_file.name, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
        else:
            raise Exception("ElevenLabs unavailable")
    except Exception:
        # fallback to gTTS
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(tmp_file.name)
    with open(tmp_file.name, "rb") as f:
        audio_bytes = f.read()
        audio_base64 = base64.b64encode(audio_bytes).decode()
    return audio_base64

# ---------------------------- App config ----------------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- Session defaults ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "voice_pref" not in st.session_state:
    st.session_state.voice_pref = "Normal"
if "language" not in st.session_state:
    st.session_state.language = "English"
if "chat_input" not in st.session_state:
    st.session_state.chat_input = ""

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Background1.jpeg"
GSK_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/GSK-logo.png"
AI_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/AURA.png"

# ---------------------------- CSS ----------------------------
CSS = f"""
<style>
/* Background */
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-attachment: fixed;
  background-size: auto 130%;
}}

/* Fixed disclaimer top-center */
.disclaimer-fixed {{
  position: fixed;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10010;
  background: rgba(255,255,255,0.9);
  padding: 12px 20px;
  border-radius: 8px;
  text-align:center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.7);
}}
.disclaimer-fixed .text {{ font-weight: 700; font-size: 15px; color: black; }}

/* Title box */
.title-box {{
  background: rgba(230,230,230,0.7);
  padding: 5px;
  border-radius: 15px;
  text-align: left;
  margin: 50px auto 12px;
  width: 1500px;
  position: relative;
}}
.title-box img.ai-logo {{
    position: absolute;
    top: 5px;
    right: 10px;
    width: 150px;
}}

/* PDF summary box (permanent) */
.pdf-summary-box {{
  background: #E6F0FF; 
  padding: 12px; 
  border-radius: 14px; 
  margin-bottom: 12px;
  white-space: pre-line;
}}

/* Chat area */
.chat-container {{
  max-height: 55vh;
  overflow-y: auto;
  padding: 12px;
  border-radius: 10px;
  background: rgba(255,255,255,0.6);
  margin-bottom: 12px;
}}
.chat-bubble-user, .chat-bubble-ai, .chat-bubble-audio {{
  display:block;
  padding:12px;
  border-radius:12px;
  margin:12px 0;
  max-width: 86%;
  word-wrap: break-word;
}}
.chat-bubble-user {{ background: #0078D7; color:white; margin-left:auto; }}
.chat-bubble-ai {{ background: #FFA500; margin-right:auto; color:#000; }} /* orange GSK color */
.chat-bubble-audio {{ background: #e2e2e2; margin-right:auto; font-size:0.9em; padding:10px; margin-top:12px; }}

/* Fixed chat input at bottom */
.fixed-chat-input {{
    position: fixed;
    bottom: 110px; 
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
    bottom: 110px;
    right: 30px;
    z-index: 10003;
    height: 40px;
    width: 100px;
}}

/* Call flow collapsible */
.call-flow-box {{
  background: rgba(255,255,255,0.95);
  padding: 10px;
  border-radius: 10px;
  margin-bottom: 8px;
  border:2px solid #FFA500;
}}

/* Permanent footer spacing */
.footer-space {{
  height: 160px;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ client ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
if not GROQ_API_KEY:
    st.warning("⚠️ Missing GROQ_API_KEY in Streamlit Secrets")
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Helpers ----------------------------
def safe_makedirs(path):
    try:
        if os.path.exists(path):
            if not os.path.isdir(path):
                st.warning(f"⚠️ Path exists but is not a directory: {path}")
                return False
            return True
        os.makedirs(path, exist_ok=True)
        return True
    except Exception as e:
        st.warning(f"⚠️ Could not create folder {path}: {e}")
        return False

def load_local_references(folder_path):
    text_all = ""
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
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text_all += f.read()
        except Exception as e:
            text_all += f"\n[Error reading {file}: {e}]"
    return text_all.strip(), None

def load_external_references(url_list):
    all_text = ""
    for url in url_list:
        url = url.strip()
        if not url:
            continue
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            content_type = r.headers.get("Content-Type", "").lower()
            if "pdf" in content_type or url.lower().endswith(".pdf"):
                try:
                    reader = PdfReader(BytesIO(r.content))
                    for page in reader.pages:
                        all_text += page.extract_text() or ""
                except:
                    all_text += f"\n[Could not extract PDF text from {url}]"
            else:
                all_text += r.text + "\n"
        except Exception as e:
            all_text += f"\n[Error fetching {url}: {e}]"
    return all_text

# ---------------------------- Brand config & call flows ----------------------------
brand_data = {
    "Shingrix": {
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "references_path": ".devcontainer/references/shingrix/"
    },
    "JEMPERLI": {
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited patient eligibility", "Access/reimbursement issues"],
        "references_path": ".devcontainer/references/jemperli/"
    }
}

JEMPERLI_CALL_FLOW = {
    "COCO": "Pre-call planning using customer insights to identify persona and call objective.",
    "Anchor": "Open conversation using COCO insights; patient-focused narrative.",
    "Engage": "Two-way dialogue; connect clinical data and handle objections.",
    "Close": "Gain agreement, set next steps, record insights."
}

SHINGRIX_CALL_FLOW = {
    "Prepare": "Plan call: identify persona, objectives, patient types.",
    "Engage": "Open conversation, connect & capture attention.",
    "Create Opportunities": "Identify gaps, present solutions.",
    "Influence": "Present evidence, handle objections.",
    "Impact GSO": "Clarify next steps to achieve GSO.",
    "Post-Call Analysis": "Record insights, update CRM, evaluate."
}

specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Rheumatologist", "Internal medicine", "Oncologist"]
objectives = ["Awareness", "Adoption", "Retention"]

# ---------------------------- Sidebar filters ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", list(brand_data.keys()), index=0)
    selected_brand = brand_data[brand]
    segment = st.selectbox("Segment", selected_brand["segments"])
    persona = st.selectbox("HCP Persona", selected_brand["personas"])
    barrier = st.multiselect("Doctor Barrier", selected_brand["barriers"])
    specialty = st.selectbox("Specialty", specialties)
    objective = st.selectbox("Objective", objectives)
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"])
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"])
    st.session_state.language = st.radio("Language", ["English","Arabic"], horizontal=True)

# ---------------------------- Fixed disclaimer ----------------------------
st.markdown(f'''
<div class="disclaimer-fixed">
  <div class="brand">⚠️ AI Assistant for <strong style="color:#FFA500">{escape(brand)}</strong></div>
  <div class="text">AI can make mistakes. Validate responses against GSK-approved materials.</div>
</div>
''', unsafe_allow_html=True)

# ---------------------------- Title ----------------------------
st.markdown(f'''
<div class="title-box">
    <img src="{GSK_LOGO_URL}" width="150">
    <img src="{AI_LOGO_URL}" class="ai-logo">
    <h1>💡 AI Sales Call Assistant</h1>
    <p>Empowering reps for smarter {brand} conversations</p>
</div>
''', unsafe_allow_html=True)

# ---------------------------- Load references ----------------------------
local_ref_text, local_warning = load_local_references(selected_brand["references_path"])
external_urls_input = st.text_area("Add external medical reference URLs (one per line)", height=120)
external_urls = [u.strip() for u in (external_urls_input or "").splitlines() if u.strip()]
external_text = load_external_references(external_urls) if external_urls else ""

# PDF summary (permanent)
st.markdown("### 📄 Uploaded PDF Summary (always visible)")
st.text_area("PDF Summary", st.session_state.pdf_summary or "No PDF uploaded.", height=140)

# ---------------------------- Collapsible Sales Call Steps ----------------------------
with st.expander("🟧 Sales Call Flow & APACT Steps", expanded=False):
    def build_call_html(brand_name):
        html = '<div class="call-flow-box">'
        html += "<p><em>Structured sales call flow for selected brand:</em></p>"
        if brand_name.upper() == "JEMPERLI":
            for step, desc in JEMPERLI_CALL_FLOW.items():
                html += f"<b>{escape(step)}:</b> {escape(desc)}<br>"
        else:
            for step, desc in SHINGRIX_CALL_FLOW.items():
                html += f"<b>{escape(step)}:</b> {escape(desc)}<br>"
        html += "</div>"
        return html
    st.markdown(build_call_html(brand), unsafe_allow_html=True)

# ---------------------------- Chat box ----------------------------
with st.form("chat_form", clear_on_submit=False):
    chat_input = st.text_area("Type your question or objection...", value=st.session_state.chat_input)
    submitted = st.form_submit_button("Send")
    
    if submitted and chat_input.strip():
        # Build AI response
        ai_plain = f"Sample AI response for {brand}, persona {persona}, segment {segment}, barrier {barrier}"
        ai_html = f'<div class="chat-bubble-ai">{escape(ai_plain)}</div>'
        audio_b64 = generate_audio(ai_plain)
        st.session_state.chat_history.append((chat_input.strip(), ai_html, audio_b64))
        st.session_state.chat_input = ""  # safe reset

# ---------------------------- Display chat history ----------------------------
st.markdown("### 💬 Chat History")
for user_text, ai_html, audio_b64 in st.session_state.chat_history:
    st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(user_text)}</div>', unsafe_allow_html=True)
    st.markdown(ai_html, unsafe_allow_html=True)
    st.markdown(f'''
    <audio controls class="chat-bubble-audio">
        <source src="data:audio/mp3;base64,{audio_b64}" type="audio/mpeg">
    </audio>
    ''', unsafe_allow_html=True)

# ---------------------------- Download chat to Word ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("📥 Download Chat to Word"):
        doc = Document()
        for user_text, ai_html, _ in st.session_state.chat_history:
            doc.add_paragraph("You: " + user_text)
            doc.add_paragraph("AI: " + re.sub("<[^<]+?>", "", ai_html))
        tmp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".docx").name
        doc.save(tmp_path)
        with open(tmp_path, "rb") as f:
            bytes_data = f.read()
        b64 = base64.b64encode(bytes_data).decode()
        st.markdown(f'<a href="data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{b64}" download="chat.docx">Download Word file</a>', unsafe_allow_html=True)

# ---------------------------- Footer spacing ----------------------------
st.markdown('<div class="footer-space"></div>', unsafe_allow_html=True)
