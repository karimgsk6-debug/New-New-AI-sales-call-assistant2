# app.py
import streamlit as st
from io import BytesIO
import re, tempfile, base64, os
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
    text = re.sub(r'[{},*]', '', text)
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        if ELEVENLABS_AVAILABLE:
            audio_stream = elevenlabs.generate(text=text, voice=ELEVENLABS_VOICE_ID, stream=True)
            with open(tmp_file.name, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
        else:
            raise Exception("ElevenLabs unavailable, falling back to gTTS")
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
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state: st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state: st.session_state.pdf_summary = ""
if "voice_pref" not in st.session_state: st.session_state.voice_pref = "Normal"
if "language" not in st.session_state: st.session_state.language = "English"
if "pdf_summary_size" not in st.session_state: st.session_state.pdf_summary_size = "Normal"

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
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10010;
  background: rgba(255,255,255,0.9);
  padding: 12px 18px;
  border-radius: 5px;
  text-align:center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.7);
}}
.disclaimer-fixed .text {{ font-weight: 700; font-size: 30px; color: #FF6600; }}
.title-box {{
  background: rgba(230,230,230,0.7);
  padding: 5px;
  border-radius: 15px;
  text-align: left;
  margin: 50px auto 12px;
  width: 1500px;
  position: relative;
}}
.title-box img.ai-logo {{ position: absolute; top: 5px; right: 10px; width: 150px; }}
.pdf-summary-box {{ background: #E6F0FF; padding: 12px; border-radius: 14px; margin-bottom: 12px; white-space: pre-line; }}
.chat-container {{ max-height: 55vh; overflow-y: auto; padding: 12px; border-radius: 10px; background: rgba(255,255,255,0.6); margin-bottom: 12px; }}
.chat-bubble-user, .chat-bubble-ai, .chat-bubble-audio {{
  display:block; padding:12px; border-radius:12px; margin:12px 0; max-width: 86%; word-wrap: break-word;
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
.fixed-chat-input textarea {{ width: 100%; min-height: 60px; max-height: 180px; resize: vertical; }}
.send-button {{ position: fixed; bottom: 20px; right: 30px; z-index: 10003; height: 40px; width: 100px; }}
.call-flow-box {{
  background: rgba(255,255,255,0.95);
  padding: 10px;
  border-radius: 10px;
  margin-bottom: 8px;
}}
.footer-space {{ height: 160px; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ client ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
if not GROQ_API_KEY:
    st.warning("⚠️ Missing GROQ_API_KEY in Streamlit Secrets")
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Brands & Call flows ----------------------------
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

SHINGRIX_CALL_FLOW = {
    "Prepare": "Plan the call, identify persona and objectives, select patient types.",
    "Engage": "Open conversation, set context using insights.",
    "Create Opportunities": "Identify gaps, present tailored solutions.",
    "Influence": "Present evidence, handle objections.",
    "Impact GSO": "Clarify next steps, link to Good Sell Outcome.",
    "Post-Call Analysis": "Record insights and update CRM."
}

JEMPERLI_CALL_FLOW = {
    "COCO": "Pre-call planning using customer insights.",
    "Anchor": "Open with patient-focused narrative aligned with call objective.",
    "Engage": "Two-way dialogue connecting data and messages.",
    "Close": "Gain agreement, define next steps and record insights."
}

specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Rheumatologist", "Internal medicine", "Oncologist"]
objectives = ["Awareness", "Adoption", "Retention"]

# ---------------------------- Sidebar filters & external URLs ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", list(brand_data.keys()), index=0)
    selected_brand = brand_data[brand]
    segment = st.selectbox("Segment", selected_brand["segments"])
    persona = st.selectbox("HCP Persona", selected_brand["personas"])
    barrier = st.multiselect("Doctor Barrier", selected_brand["barriers"])
    specialty = st.selectbox("Specialty", specialties)
    objective = st.selectbox("Objective", objectives)
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])
    st.session_state.language = st.radio("Language", ["English", "Arabic"], horizontal=True)
    # External medical URLs
    external_urls_input = st.text_area("Add external medical reference URLs (one per line)", height=120)
    external_urls = [u.strip() for u in (external_urls_input or "").splitlines() if u.strip()]

# ---------------------------- Disclaimer ----------------------------
st.markdown(f'''
<div class="disclaimer-fixed">
    <div class="text">⚠️ AI Assistant for <strong>{brand}</strong></div>
</div>
''', unsafe_allow_html=True)

# ---------------------------- PDF Summary ----------------------------
st.markdown("### 📄 Uploaded PDF Summary (always visible)")
st.text_area("PDF Summary", st.session_state.pdf_summary or "No PDF uploaded.", height=140)

# ---------------------------- Chat container ----------------------------
st.markdown('<div class="chat-container" id="chat-container">', unsafe_allow_html=True)

# Chat input fixed at bottom
st.markdown('<div class="fixed-chat-input">', unsafe_allow_html=True)
with st.form("chat_form", clear_on_submit=True):
    chat_input = st.text_area("Your Message", key="chat_input", placeholder="Type your question here...")
    send = st.form_submit_button("Send")
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Helpers: call flow ----------------------------
def build_call_flow_html(brand_name):
    if brand_name.upper() == "JEMPERLI":
        steps = JEMPERLI_CALL_FLOW
    else:
        steps = SHINGRIX_CALL_FLOW
    html = '<details class="call-flow-box"><summary><strong>🧩 Sales Call Steps</strong></summary>'
    for i, (step, desc) in enumerate(steps.items(), 1):
        html += f'<p><strong>{i}. {escape(step)}:</strong> {escape(desc)}</p>'
    html += '</details>'
    return html

# ---------------------------- AI response generator ----------------------------
def generate_ai_response(user_input):
    """Generate AI response text (plain)"""
    # Placeholder for demonstration (replace with GROQ call)
    steps_html = build_call_flow_html(brand)
    example_text = f"Sample AI response for {brand}, persona {persona}, segment {segment}, barrier {barrier}"
    return f"{example_text}<br>{steps_html}"

# ---------------------------- Display chat history ----------------------------
for entry in st.session_state.chat_history:
    sender, msg = entry
    if sender == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(msg)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {msg}</div>', unsafe_allow_html=True)
        # Generate audio
        audio_b64 = generate_audio(msg)
        st.markdown(f'''
            <div class="chat-bubble-audio">
            🔊 <audio controls><source src="data:audio/mp3;base64,{audio_b64}" type="audio/mp3"></audio>
            </div>
        ''', unsafe_allow_html=True)

# ---------------------------- Handle sending ----------------------------
if 'send' in locals() and send and chat_input.strip():
    ai_text = generate_ai_response(chat_input.strip())
    st.session_state.chat_history.append(("user", chat_input.strip()))
    st.session_state.chat_history.append(("ai", ai_text))
    try:
        st.session_state.chat_input = ""
    except:
        pass

# ---------------------------- Auto-scroll ----------------------------
st.components.v1.html("""
<script>
const container = document.getElementById('chat-container');
if(container){ container.scrollTop = container.scrollHeight; }
</script>
""", height=0, width=0)

# ---------------------------- Footer space ----------------------------
st.markdown('<div class="footer-space"></div>', unsafe_allow_html=True)
# ---------------------------- Download chat & steps ----------------------------
def export_chat_to_word():
    if not DOCX_AVAILABLE:
        st.warning("⚠️ python-docx not installed. Word export unavailable.")
        return

    doc = Document()
    doc.add_heading(f"{brand} AI Sales Call Assistant Chat Export", 0)

    # Add chat history
    for sender, msg in st.session_state.chat_history:
        if sender == "user":
            doc.add_paragraph(f"You: {msg}", style='Intense Quote')
        else:
            doc.add_paragraph(f"AI: {msg}", style='Normal')

    # Add Sales Call Steps
    doc.add_heading("Sales Call Steps", level=1)
    if brand.upper() == "JEMPERLI":
        steps = JEMPERLI_CALL_FLOW
    else:
        steps = SHINGRIX_CALL_FLOW
    for i, (step, desc) in enumerate(steps.items(), 1):
        doc.add_paragraph(f"{i}. {step}: {desc}")

    # Add external URLs
    if external_urls:
        doc.add_heading("External Medical Reference URLs", level=2)
        for url in external_urls:
            doc.add_paragraph(url)

    # Save to BytesIO
    file_stream = BytesIO()
    doc.save(file_stream)
    file_stream.seek(0)
    return file_stream

st.markdown("---")
word_file = export_chat_to_word()
if word_file:
    st.download_button(
        label="📥 Download Full Chat & Call Steps (Word)",
        data=word_file,
        file_name=f"{brand}_sales_call_export.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
