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
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    elevenlabs.api_key = ELEVENLABS_API_KEY
else:
    ELEVENLABS_AVAILABLE = False

def generate_audio(text):
    """Generate TTS audio safely using ElevenLabs or fallback to gTTS"""
    try:
        if ELEVENLABS_AVAILABLE:
            audio_stream = elevenlabs.generate(text=text, voice=ELEVENLABS_VOICE_ID, stream=True)
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            with open(tmp_file.name, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
            with open(tmp_file.name, "rb") as f:
                audio_bytes = f.read()
        else:
            raise Exception("ElevenLabs unavailable")
    except Exception:
        try:
            tts = gTTS(text=text, lang="en", slow=False)
            tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            tts.save(tmp_file.name)
            with open(tmp_file.name, "rb") as f:
                audio_bytes = f.read()
        except Exception as e:
            st.warning(f"TTS failed: {e}")
            return None
    return base64.b64encode(audio_bytes).decode()

# ---------------------------- App config ----------------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- Session defaults ----------------------------
st.session_state.setdefault("chat_history", [])
st.session_state.setdefault("uploaded_pdf_text", "")
st.session_state.setdefault("pdf_summary", "")
st.session_state.setdefault("voice_pref", "Old Male")
st.session_state.setdefault("language", "English")
st.session_state.setdefault("pdf_summary_size", "Normal")
st.session_state.setdefault("chat_input", "")

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
.disclaimer-fixed {{
  position: fixed;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10010;
  background: rgba(255,255,255,0.9);
  padding: 10px 18px;
  border-radius: 5px;
  text-align:center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.7);
  font-size: 30px;
  font-weight: bold;
  color: #FF8000;
}}
.title-box {{
  background: rgba(230,230,230,0.7);
  padding: 5px;
  border-radius: 15px;
  text-align: left;
  margin: 60px auto 12px;
  width: 1500px;
  position: relative;
}}
.title-box img.ai-logo {{
    position: absolute;
    top: 5px;
    right: 10px;
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
.chat-bubble-ai {{ background: #d9f0ff; margin-right:auto; color:#000; }}
.chat-bubble-audio {{ background: #e2e2e2; margin-right:auto; font-size:0.9em; padding:10px; margin-top:12px; }}
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
.call-flow-box {{
  background: rgba(255,255,255,0.95);
  padding: 10px;
  border-radius: 10px;
  margin-bottom: 8px;
}}
.footer-space {{
  height: 160px;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ client ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ---------------------------- Safe folder creation ----------------------------
def safe_makedirs(path):
    if os.path.exists(path) and not os.path.isdir(path):
        st.warning(f"⚠️ Path exists but is not a directory: {path}")
        return False
    os.makedirs(path, exist_ok=True)
    return True

safe_makedirs(".devcontainer/references/shingrix")
safe_makedirs(".devcontainer/references/jemperli")
safe_makedirs(".devcontainer/SalesModule/SHINGRIX")
safe_makedirs(".devcontainer/SalesModule/JEMPERLI")

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
    "COCO": "Pre-call planning using customer insights to identify persona and call objective. Select a patient type and prepare thought-provoking questions.",
    "Anchor": "Open the conversation using COCO insights; create a patient-focused narrative and align on the call objective.",
    "Engage": "Build two-way dialogue; connect clinical data and product messages and handle objections.",
    "Close": "Gain agreement, set clear next steps, consider omni-channel follow-up and record insights."
}

SHINGRIX_CALL_FLOW = {
    "Prepare": "Plan the call: identify persona, call objectives and select patient types; gather insights to inform messaging.",
    "Engage": "Open the conversation to connect and capture attention; set context using insights.",
    "Create Opportunities": "Identify gaps/unmet needs and present tailored clinical/product data as solutions.",
    "Influence": "Present evidence, handle objections, and highlight value and outcomes.",
    "Impact GSO": "Clarify next steps and link to incremental steps that achieve the Good Sell Outcome.",
    "Post-Call Analysis": "Record insights, update CRM and evaluate success metrics to inform future calls."
}

specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Rheumatologist", "Internal medicine", "Oncologist"]
objectives = ["Awareness", "Adoption", "Retention"]

# ---------------------------- Sidebar filters ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", list(brand_data.keys()), index=0, key="select_brand")
    selected_brand = brand_data[brand]
    segment = st.selectbox("Segment", selected_brand["segments"], key="select_segment")
    persona = st.selectbox("HCP Persona", selected_brand["personas"], key="select_persona")
    barrier = st.multiselect("Doctor Barrier", selected_brand["barriers"], key="select_barrier")
    specialty = st.selectbox("Specialty", specialties, key="select_specialty")
    objective = st.selectbox("Objective", objectives, key="select_objective")
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"], key="select_tone")
    response_length = st.selectbox("Response Length", ["Short", "Medium", "Long"], key="select_length")
    st.session_state.language = st.radio("Language", ["English", "Arabic"], horizontal=True, key="select_language")

# ---------------------------- Dynamic top-center disclaimer ----------------------------
st.markdown(f'''
<div class="disclaimer-fixed">
AI Assistant for <strong>{brand}</strong> — AI can make mistakes. Validate responses against GSK-approved materials.
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

# ---------------------------- Helpers: load references ----------------------------
def load_local_references(folder_path):
    text_all = ""
    warning = None
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return "", f"⚠️ Folder does not exist: {folder_path}"
    files = [f for f in os.listdir(folder_path) if f.lower().endswith((".pdf", ".txt"))]
    if not files:
        warning = f"ℹ️ No files found in {folder_path}"
    for file in files:
        try:
            file_path = os.path.join(folder_path, file)
            if file.lower().endswith(".pdf"):
                reader = PdfReader(file_path)
                for page in reader.pages:
                    text_all += page.extract_text() or ""
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text_all += f.read()
        except Exception as e:
            text_all += f"\n[Error reading {file}: {e}]"
    return text_all.strip(), warning

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
                reader = PdfReader(BytesIO(r.content))
                for page in reader.pages:
                    all_text += page.extract_text() or ""
            else:
                all_text += r.text + "\n"
        except Exception as e:
            all_text += f"\n[Error fetching {url}: {e}]"
    return all_text

# Load local references
local_ref_text, local_warning = load_local_references(selected_brand["references_path"])

# ---------------------------- Collapsible panels ----------------------------
# Medical references
with st.expander("📚 Medical References (local + external)", expanded=False):
    st.write("Local folder:", selected_brand["references_path"])
    if local_warning:
        st.info(local_warning)
    if local_ref_text:
        with st.expander("🔍 Preview Local Medical References", expanded=False):
            st.text_area("Preview", local_ref_text[:4000] + ("..." if len(local_ref_text) > 4000 else ""), height=240)
    external_urls_input = st.text_area("Add external medical reference URLs (one per line)", height=120)
    external_urls = [u.strip() for u in (external_urls_input or "").splitlines() if u.strip()]
    external_text = load_external_references(external_urls) if external_urls else ""
    if external_text:
        with st.expander("🔍 Preview External Medical References", expanded=False):
            st.text_area("Preview", external_text[:4000] + ("..." if len(external_text) > 4000 else ""), height=240)

# ---------------------------- Chat and AI response ----------------------------
def generate_ai_response(chat_input):
    """Generate AI HTML and plain text response (simulate for now)"""
    ai_html = f"<b>AI ({brand}):</b> Response for persona <i>{persona}</i> regarding barrier {barrier}."
    ai_plain = f"AI ({brand}) response for {persona}: {chat_input}"
    # Embed call steps collapsible
    if brand == "Shingrix":
        steps = SHINGRIX_CALL_FLOW
    else:
        steps = JEMPERLI_CALL_FLOW
    call_steps_html = "<details><summary>🧩 Call Steps</summary><ol>"
    for k, v in steps.items():
        call_steps_html += f"<li><b>{k}</b>: {escape(v)}</li>"
    call_steps_html += "</ol></details>"
    ai_html += "<br>" + call_steps_html
    return ai_html, ai_plain

# ---------------------------- Chat UI ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for msg_user, msg_ai, audio_b64 in st.session_state.chat_history:
    st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(msg_user)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="chat-bubble-ai">{msg_ai}</div>', unsafe_allow_html=True)
    if audio_b64:
        st.audio(base64.b64decode(audio_b64))
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Chat input ----------------------------
with st.form("chat_form", clear_on_submit=False):
    chat_input = st.text_area("Type your question or objection...", value=st.session_state.chat_input)
    submitted = st.form_submit_button("Send")
    if submitted and chat_input.strip():
        st.session_state.chat_input = chat_input
        ai_html, ai_plain = generate_ai_response(chat_input.strip())
        audio_b64 = generate_audio(ai_plain)
        st.session_state.chat_history.append((chat_input.strip(), ai_html, audio_b64))
        st.session_state.chat_input = ""  # safe reset
        st.experimental_rerun()

# ---------------------------- Footer spacing ----------------------------
st.markdown('<div class="footer-space"></div>', unsafe_allow_html=True)

# ---------------------------- Download chat as Word ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("💾 Download Conversation (Word)"):
        doc = Document()
        for u, ai, audio_b64 in st.session_state.chat_history:
            doc.add_paragraph(f"You: {u}")
            doc.add_paragraph(f"AI Response: {re.sub('<[^<]+?>', '', ai)}\n")
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            st.download_button("Download .docx", f, file_name="chat_conversation.docx")
