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
    """Generate TTS audio for the AI response"""
    text = re.sub(r'[{},*]', '', text)  # clean text for TTS
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        if ELEVENLABS_AVAILABLE:
            audio_stream = elevenlabs.generate(text=text, voice=ELEVENLABS_VOICE_ID, stream=True)
            with open(tmp_file.name, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
        else:
            raise Exception("ElevenLabs unavailable")
    except:
        tts = gTTS(text=text, lang="en", slow=True)
        tts.save(tmp_file.name)
    with open(tmp_file.name, "rb") as f:
        audio_bytes = f.read()
        audio_base64 = base64.b64encode(audio_bytes).decode()
    return audio_base64

# ---------------------------- App config ----------------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- Session defaults ----------------------------
if "chat_history" not in st.session_state or not isinstance(st.session_state.chat_history, list):
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "voice_pref" not in st.session_state:
    st.session_state.voice_pref = "Normal"
if "language" not in st.session_state:
    st.session_state.language = "English"

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
  padding: 10px 18px;
  text-align:center;
}}
.disclaimer-fixed .brand {{ font-weight:900; font-size:30px; color:orange; }}
.disclaimer-fixed .text {{ font-weight:600; font-size:15px; color:black; }}

/* Title box */
.title-box {{
  background: rgba(230,230,230,0.7);
  padding: 5px;
  border-radius: 15px;
  text-align: left;
  margin: 70px auto 12px;
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

/* Call flow box collapsible */
.call-flow-box {{
  background: rgba(255,255,255,0.95);
  padding: 10px;
  border-radius: 10px;
  margin-bottom: 8px;
}}

/* Permanent footer area to hold PDF summary export and disclaimer spacing */
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
    # External medical URLs now in sidebar
    external_urls_input = st.text_area("Add external medical reference URLs (one per line)", height=100)
    external_urls = [u.strip() for u in (external_urls_input or "").splitlines() if u.strip()]

# ---------------------------- Top-center disclaimer ----------------------------
st.markdown(f'''
<div class="disclaimer-fixed">
  <div class="brand">{escape(brand)}</div>
  <div class="text">AI can make mistakes. Validate all generated responses against GSK-approved materials.</div>
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

local_ref_text, local_warning = load_local_references(selected_brand["references_path"])

# Load external references if provided
def load_external_references(url_list):
    all_text = ""
    for url in url_list:
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

external_text = load_external_references(external_urls) if external_urls else ""

# ---------------------------- PDF summary (always visible) ----------------------------
st.markdown("### 📄 Uploaded PDF Summary")
st.text_area("PDF Summary", st.session_state.pdf_summary or "No PDF uploaded or no summary available.", height=140)

# ---------------------------- Helpers for building unified call-flow HTML ----------------------------
def build_call_flow_html(brand_name):
    """Returns collapsible HTML block of brand call flow + APACT integrated"""
    html = '<details class="call-flow-box"><summary><strong>🧩 Sales Call Steps</strong></summary>'
    html += '<p><em>Structured sales call flow for selected brand:</em></p>'
    if brand_name.upper() == "JEMPERLI":
        steps = list(JEMPERLI_CALL_FLOW.items())
        emoji_map = {"COCO":"🟩","Anchor":"🟦","Engage":"🟨","Close":"🟥"}
    else:
        steps = list(SHINGRIX_CALL_FLOW.items())
        ems = ["🟩","🟦","🟨","🟧","🟥","🟪"]
        emoji_map = {k:v for k,v in zip(SHINGRIX_CALL_FLOW.keys(), ems)}
    for step, desc in steps:
        html += f'<p>{emoji_map.get(step,"🔹")} <strong>{escape(step)}</strong>: {escape(desc)}</p>'
        html += f'<p style="margin-left:20px;"><em>Example:</em> Use patient data and insights to illustrate points during conversation.</p>'
    html += '</details>'
    return html

# ---------------------------- AI response generation ----------------------------
def generate_ai_response(prompt):
    """Call GROQ API to get AI response"""
    try:
        context_text = local_ref_text + "\n" + external_text
        full_prompt = f"Brand: {brand}\nSegment: {segment}\nPersona: {persona}\nBarrier: {barrier}\nObjective: {objective}\nSpecialty: {specialty}\nTone: {response_tone}\nLength: {response_length}\nContext:\n{context_text}\nUser Question:\n{prompt}"
        response = client.completions.create(
            model="gpt-4.1-mini",
            prompt=full_prompt,
            max_tokens=600
        )
        ai_text = response.choices[0].text.strip()
    except Exception as e:
        ai_text = f"⚠️ AI generation error: {e}\n\n[Sample AI response fallback]\nBrand: {brand}, Persona: {persona}, Segment: {segment}, Barrier: {barrier}"
    return ai_text

# ---------------------------- Chat input & display ----------------------------
st.markdown('<div class="chat-container" id="chat-container">', unsafe_allow_html=True)

chat_input = st.text_area("Ask AI Sales Assistant", height=80, key="chat_input", placeholder="Type your question here...")

send_clicked = st.button("Send", key="send_button")

if send_clicked and chat_input.strip():
    # Generate AI response
    ai_response = generate_ai_response(chat_input.strip())
    st.session_state.chat_history.append(("user", chat_input.strip()))
    st.session_state.chat_history.append(("ai", ai_response))
    # Reset input safely
    try:
        st.session_state.chat_input = ""
    except:
        pass

# Display chat bubbles
for sender, msg in st.session_state.chat_history:
    if sender == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(msg)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(msg)}</div>', unsafe_allow_html=True)
        # Display call flow for last AI response
        st.markdown(build_call_flow_html(brand), unsafe_allow_html=True)
        # Generate TTS audio
        audio_b64 = generate_audio(msg)
        audio_html = f'''
        <div class="chat-bubble-audio">
            🔊 <audio controls><source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3"></audio>
        </div>
        '''
        st.markdown(audio_html, unsafe_allow_html=True)

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('<div class="footer-space"></div>', unsafe_allow_html=True)

# ---------------------------- Word export ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("Download Chat as Word Document"):
        doc = Document()
        doc.add_heading(f"AI Sales Call Assistant - {brand}", 0)
        for sender, msg in st.session_state.chat_history:
            doc.add_paragraph(f"{sender.upper()}: {msg}")
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            st.download_button("Download DOCX", f, file_name=f"{brand}_chat.docx")
