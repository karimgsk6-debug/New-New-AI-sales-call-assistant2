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
    """Generate TTS audio with safe fallback to gTTS"""
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        if ELEVENLABS_AVAILABLE:
            audio_bytes = elevenlabs.text_to_speech(text=text, voice=ELEVENLABS_VOICE_ID)
            with open(tmp_file.name, "wb") as f:
                f.write(audio_bytes)
        else:
            raise Exception("ElevenLabs unavailable")
    except Exception as e:
        st.warning(f"ElevenLabs TTS error: {e}. Falling back to gTTS.")
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(tmp_file.name)
    with open(tmp_file.name, "rb") as f:
        audio_bytes = f.read()
        audio_base64 = base64.b64encode(audio_bytes).decode()
    return audio_base64

# ---------------------------- App config ----------------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- Session defaults ----------------------------
st.session_state.setdefault("chat_history", [])
st.session_state.setdefault("uploaded_pdf_text", "")
st.session_state.setdefault("pdf_summary", "")
st.session_state.setdefault("voice_pref", "Normal")
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
  top: 5px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10010;
  background: rgba(240,240,240,0.7);
  padding: 10px 18px;
  border-radius: 5px;
  text-align:center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.7);
}}
.disclaimer-fixed .text {{ font-weight: bold; font-size: 30px; color: orange; display:block; margin-top:4px; }}

/* Title box */
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
.chat-bubble-ai {{ background: #d9f0ff; margin-right:auto; color:#000; }}
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

/* Call flow box */
.call-flow-box {{
  background: rgba(255,255,255,0.95);
  padding: 10px;
  border-radius: 10px;
  margin-bottom: 8px;
}}

/* Permanent footer area to hold PDF summary export and spacing */
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

# ---------------------------- Safe folder creation ----------------------------
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

safe_makedirs(".devcontainer/references/shingrix")
safe_makedirs(".devcontainer/references/jemperli")
safe_makedirs(".devcontainer/SalesModule/SHINGRIX")
safe_makedirs(".devcontainer/SalesModule/JEMPERLI")

# ---------------------------- Brand & call flows ----------------------------
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
    brand = st.selectbox("Brand", list(brand_data.keys()), index=0)
    selected_brand = brand_data[brand]
    segment = st.selectbox("Segment", selected_brand["segments"])
    persona = st.selectbox("HCP Persona", selected_brand["personas"])
    barrier = st.multiselect("Doctor Barrier", selected_brand["barriers"])
    specialty = st.selectbox("Specialty", specialties)
    objective = st.selectbox("Objective", objectives)
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])
    response_length = st.selectbox("Response Length", ["Short", "Medium", "Long"])
    st.session_state.language = st.radio("Language", ["English", "Arabic"], horizontal=True)

# ---------------------------- Disclaimer ----------------------------
st.markdown(f'''
<div class="disclaimer-fixed">
  <div class="brand">⚠️ AI Assistant for <strong>{escape(brand)}</strong></div>
  <div class="text">AI can make mistakes, validate responses against GSK-approved materials</div>
</div>
''', unsafe_allow_html=True)

# ---------------------------- Title ----------------------------
st.markdown(f'''
<div class="title-box">
    <img src="{GSK_LOGO_URL}" width="150">
    <img src="{AI_LOGO_URL}" class="ai-logo">
    <h1>💡 AI Sales Call Assistant</h1>
    <p>Empowering reps for smarter <strong>{brand}</strong> conversations</p>
</div>
''', unsafe_allow_html=True)

# ---------------------------- Helper functions ----------------------------
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
                reader = PdfReader(BytesIO(r.content))
                for page in reader.pages:
                    all_text += page.extract_text() or ""
            else:
                all_text += r.text + "\n"
        except Exception as e:
            all_text += f"\n[Error fetching {url}: {e}]"
    return all_text

# Load references
local_ref_text, local_warning = load_local_references(selected_brand["references_path"])
sales_folder = f".devcontainer/SalesModule/{brand.upper()}"
safe_makedirs(sales_folder)
sales_module_text, sales_warning = load_local_references(sales_folder)

# ---------------------------- Collapsible panels ----------------------------
with st.expander("📚 Medical References (local + external)", expanded=False):
    st.write("Local folder:", selected_brand["references_path"])
    if local_warning: st.info(local_warning)
    if local_ref_text:
        with st.expander("🔍 Preview Local Medical References", expanded=False):
            st.text_area("Local Medical Reference Preview", local_ref_text[:4000] + ("..." if len(local_ref_text) > 4000 else ""), height=240)
    external_urls_input = st.text_area("Add external medical reference URLs (one per line)", height=120)
    external_urls = [u.strip() for u in (external_urls_input or "").splitlines() if u.strip()]
    external_text = load_external_references(external_urls) if external_urls else ""
    if external_text:
        with st.expander("🔍 Preview External Medical References", expanded=False):
            st.text_area("External Medical Reference Preview", external_text[:4000] + ("..." if len(external_text) > 4000 else ""), height=240)

# PDF summary (always visible)
st.markdown("### 📄 Uploaded PDF Summary (always visible)")
st.text_area("PDF Summary", st.session_state.pdf_summary or "No PDF uploaded or no summary available.", height=140)

# SalesModule panel (collapsible)
with st.expander("🧩 Sales Call Module (local + external)", expanded=False):
    st.write("SalesModule folder:", sales_folder)
    if sales_warning:
        st.info(sales_warning + " — default call flow will be used when files are missing.")
    if sales_module_text:
        with st.expander("🔍 Preview SalesModule Documents", expanded=False):
            st.text_area("SalesModule Preview", sales_module_text[:4000] + ("..." if len(sales_module_text) > 4000 else ""), height=260)
    sales_urls_input = st.text_area("Optional: Add external SalesModule URLs (one per line)", height=100)
    sales_urls = [u.strip() for u in (sales_urls_input or "").splitlines() if u.strip()]
    sales_external_text = load_external_references(sales_urls) if sales_urls else ""
    if sales_external_text:
        with st.expander("🔍 Preview External SalesModule Content", expanded=False):
            st.text_area("SalesModule External Preview", sales_external_text[:4000] + ("..." if len(sales_external_text) > 4000 else ""), height=240)

# ---------------------------- Generate AI Response ----------------------------
def generate_ai_response(chat_input):
    """Simulate AI response generation using all gathered references"""
    base_text = f"""
Brand: {brand}
Segment: {segment}
Persona: {persona}
Barriers: {', '.join(barrier)}
Specialty: {specialty}
Objective: {objective}
Tone: {response_tone}
References: {local_ref_text[:2000]} + {external_text[:2000]} + {sales_module_text[:2000]} + {sales_external_text[:2000]}
Chat input: {chat_input}
"""
    ai_html = f"<b>AI:</b> {escape(chat_input)}"  # placeholder for demo
    ai_plain = chat_input
    return ai_html, ai_plain

# ---------------------------- Collapsible call steps ----------------------------
CALL_FLOW = SHINGRIX_CALL_FLOW if brand == "Shingrix" else JEMPERLI_CALL_FLOW

# ---------------------------- Chat input & display ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for i, (user_text, ai_html, audio_b64) in enumerate(st.session_state.chat_history):
    st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(user_text)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="chat-bubble-ai">{ai_html}</div>', unsafe_allow_html=True)
    if audio_b64:
        st.markdown(f'''
        <div class="chat-bubble-audio">
        <audio controls src="data:audio/mp3;base64,{audio_b64}"></audio>
        </div>
        ''', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Fixed chat input at bottom ----------------------------
with st.container():
    chat_input = st.text_area("Type your question here...", key="chat_input", height=80)
    if st.button("Send"):
        if chat_input.strip():
            ai_html, ai_plain = generate_ai_response(chat_input.strip())
            audio_b64 = generate_audio(ai_plain)
            st.session_state.chat_history.append((chat_input.strip(), ai_html, audio_b64))
            st.session_state.chat_input = ""  # safe reset
            st.experimental_rerun()

# ---------------------------- Display call steps (collapsible) ----------------------------
st.markdown("### 🗂️ Call Steps")
for step_title, step_text in CALL_FLOW.items():
    with st.expander(step_title, expanded=False):
        st.markdown(f"{step_text}")

# ---------------------------- Export to Word ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    doc = Document()
    doc.add_heading(f"{brand} AI Sales Call Assistant", 0)
    for user_text, ai_html, _ in st.session_state.chat_history:
        doc.add_paragraph(f"You: {user_text}")
        doc.add_paragraph(f"AI: {ai_html}")
    tmp_doc = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    doc.save(tmp_doc.name)
    with open(tmp_doc.name, "rb") as f:
        st.download_button("📥 Download Word Summary", f, file_name=f"{brand}_AI_Call.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

# ---------------------------- Footer spacing ----------------------------
st.markdown('<div class="footer-space"></div>', unsafe_allow_html=True)
