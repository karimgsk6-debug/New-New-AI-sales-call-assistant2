# app.py
import streamlit as st
from io import BytesIO
import re
import tempfile
import base64
import os
from groq import Groq
from html import escape
try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False
from gtts import gTTS
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except ModuleNotFoundError:
    ELEVENLABS_AVAILABLE = False

# ---------------------------- ElevenLabs TTS Setup ----------------------------
ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "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")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "EXAMPLE_VOICE_ID")  # updated
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    elevenlabs.api_key = ELEVENLABS_API_KEY
else:
    ELEVENLABS_AVAILABLE = False

def generate_audio(text):
    """Generate TTS audio for AI response"""
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    if ELEVENLABS_AVAILABLE:
        audio_stream = elevenlabs.generate(text=text, voice=ELEVENLABS_VOICE_ID, stream=True)
        with open(tmp_file.name, "wb") as f:
            for chunk in audio_stream:
                f.write(chunk)
    else:
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(tmp_file.name)
    with open(tmp_file.name, "rb") as f:
        audio_bytes = f.read()
        audio_base64 = base64.b64encode(audio_bytes).decode()
    return audio_base64

# ---------------------------- App Config ----------------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- Session Defaults ----------------------------
session_defaults = {
    "chat_history": [],
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "voice_pref": "Old Male",
    "language": "English",
    "pdf_summary_size": "Normal",
    "chat_input": ""
}
for key, value in session_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

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
  background: rgba(240,240,240,0.7);
  padding: 10px 18px;
  border-radius: 5px;
  text-align:center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.7);
  color: black;
  font-weight: bold;
  font-size: 30px;
}}
.title-box {{
  background: rgba(230,230,230,0.7);
  padding: 5px;
  border-radius: 15px;
  text-align: left;
  margin: 80px auto 12px;
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
.chat-bubble-ai {{ background: #FFF3E0; margin-right:auto; color:#000; }}
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

# ---------------------------- Brands and Call Flows ----------------------------
brand_data = {
    "Shingrix": {
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"]
    },
    "JEMPERLI": {
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited patient eligibility", "Access/reimbursement issues"]
    }
}
SHINGRIX_CALL_FLOW = {
    "Prepare": "Plan the call: identify persona, call objectives and select patient types; gather insights.",
    "Engage": "Open the conversation to connect and capture attention; set context using insights.",
    "Create Opportunities": "Identify gaps/unmet needs and present tailored clinical/product data.",
    "Influence": "Present evidence, handle objections, and highlight value.",
    "Impact GSO": "Clarify next steps and link to incremental steps that achieve Good Sell Outcome.",
    "Post-Call Analysis": "Record insights, update CRM and evaluate success metrics."
}
JEMPERLI_CALL_FLOW = {
    "COCO": "Pre-call planning using customer insights to identify persona and call objective.",
    "Anchor": "Open the conversation using COCO insights; create a patient-focused narrative.",
    "Engage": "Build two-way dialogue; connect clinical data and product messages.",
    "Close": "Gain agreement, set clear next steps, consider omni-channel follow-up."
}

# ---------------------------- Sidebar Filters ----------------------------
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Rheumatologist", "Internal medicine", "Oncologist"]
objectives = ["Awareness", "Adoption", "Retention"]

with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", list(brand_data.keys()))
    selected_brand = brand_data[brand]
    segment = st.selectbox("Segment", selected_brand["segments"])
    persona = st.selectbox("HCP Persona", selected_brand["personas"])
    barrier = st.multiselect("Doctor Barrier", selected_brand["barriers"])
    specialty = st.selectbox("Specialty", specialties)
    objective = st.selectbox("Objective", objectives)
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])
    response_length = st.selectbox("Response Length", ["Short", "Medium", "Long"])
    st.session_state.language = st.radio("Language", ["English", "Arabic"], horizontal=True)

# ---------------------------- Fixed top disclaimer ----------------------------
st.markdown(f'''
<div class="disclaimer-fixed">
⚠️ AI Assistant for <strong>{escape(brand)}</strong><br>
AI can make mistakes. Validate all responses against GSK-approved materials.
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

# ---------------------------- PDF summary ----------------------------
st.markdown("### 📄 Uploaded PDF Summary")
st.text_area("PDF Summary", st.session_state.pdf_summary or "No PDF uploaded.", height=140)

# ---------------------------- Collapsible call steps + references ----------------------------
def build_call_flow_html(brand_name, include_apact=False):
    steps = SHINGRIX_CALL_FLOW.items() if brand_name=="Shingrix" else JEMPERLI_CALL_FLOW.items()
    html = '<details open><summary><strong>🧩 Call Steps & Resources</strong></summary>'
    for idx, (step_name, desc) in enumerate(steps, start=1):
        html += f'<p>🔹 <strong>{idx}. {escape(step_name)}:</strong> {escape(desc)}</p>'
    if include_apact:
        apact_steps = [
            ("Acknowledge", "Acknowledge the HCP's concern."),
            ("Probing", "Ask clarifying questions."),
            ("Action", "Provide concise response."),
            ("Confirm", "Confirm understanding/agreement."),
            ("Transition", "Transition to next steps.")
        ]
        html += "<hr><p><strong>APACT – Objection Handling:</strong></p>"
        for name, desc in apact_steps:
            html += f'<p>🔹 <strong>{escape(name)}:</strong> {escape(desc)}</p>'
    # Add collapsible Medical References & SalesModule
    html += '<details><summary><strong>📚 Medical References</strong></summary>'
    html += '<p>Link to GSK-approved references or example content here...</p>'
    html += '</details>'
    html += '<details><summary><strong>💼 Sales Module</strong></summary>'
    html += '<p>Segmented sales modules with call scripts, messages, and templates.</p>'
    html += '</details>'
    html += '</details>'
    return html

# ---------------------------- AI Response ----------------------------
def generate_ai_response(user_input):
    include_apact = bool(re.search(r'\b(objection|concern|handle|apact|how to respond|how to handle)\b', user_input, re.IGNORECASE))
    html_response = build_call_flow_html(brand, include_apact)
    plain_text = re.sub(r'<[^>]+>', '', html_response)
    return html_response, plain_text

# ---------------------------- Chat Container ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for item in st.session_state.chat_history:
    user_msg, ai_html, audio_b64 = item
    st.markdown(f'<div class="chat-bubble-user">{escape(user_msg)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="chat-bubble-ai">{ai_html}</div>', unsafe_allow_html=True)
    st.markdown(f'''
        <div class="chat-bubble-audio">
        🔊 AI Voice:<br>
        <audio controls src="data:audio/mp3;base64,{audio_b64}"></audio>
        </div>
    ''', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Fixed Chat Input ----------------------------
chat_input = st.text_area("💬 Type your question...", st.session_state.chat_input, key="chat_input", height=80)
if st.button("Send") and chat_input.strip():
    ai_html, ai_plain = generate_ai_response(chat_input.strip())
    audio_b64 = generate_audio(ai_plain)
    st.session_state.chat_history.append((chat_input.strip(), ai_html, audio_b64))
    st.session_state.chat_input = ""

# ---------------------------- Footer spacing ----------------------------
st.markdown('<div class="footer-space"></div>', unsafe_allow_html=True)

# ---------------------------- Export Chat to Word ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("📥 Export Chat to Word"):
        doc = Document()
        doc.add_heading("AI Sales Call Assistant Chat Export", 0)
        for user_msg, ai_html, audio in st.session_state.chat_history:
            plain_ai = re.sub(r'<[^>]+>', '', ai_html)
            doc.add_paragraph(f"User: {user_msg}")
            doc.add_paragraph(f"AI: {plain_ai}\n")
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            bytes_data = f.read()
            b64 = base64.b64encode(bytes_data).decode()
            href = f'<a href="data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{b64}" download="AI_Chat.docx">Click to download Word file</a>'
            st.markdown(href, unsafe_allow_html=True)
