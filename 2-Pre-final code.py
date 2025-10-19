# app.py
import streamlit as st
from PIL import Image
from io import BytesIO
import re, tempfile, base64, os, requests
from datetime import datetime
from groq import Groq
from PyPDF2 import PdfReader
from html import escape

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
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state: st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state: st.session_state.pdf_summary = ""
if "voice_pref" not in st.session_state: st.session_state.voice_pref = "Old Male"
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
.title-box {{
  background: rgba(230,230,230,0.7);
  padding: 10px;
  border-radius: 15px;
  text-align: left;
  margin: 12px auto;
  width: 1300px;
  position: relative;
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
  max-height: 55vh;
  overflow-y: auto;
  padding: 12px;
  border-radius: 10px;
  background: rgba(240,240,240,0.7);
  margin-bottom: 70px;
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
    bottom: 40px;
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
    bottom: 40px;
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
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ Client ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
if not GROQ_API_KEY: st.warning("⚠️ Missing GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Sidebar ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", ["shingrix", "jemperli"], key="select_brand")
    segment = st.selectbox("Segment", ["Segment A", "Segment B"], key="select_segment")
    persona = st.selectbox("HCP Persona", ["Persona 1", "Persona 2"], key="select_persona")
    barrier = st.multiselect("Doctor Barrier", ["Barrier 1", "Barrier 2"], key="select_barrier")
    specialty = st.selectbox("Specialty", ["GP","Cardiologist"], key="select_specialty")
    objective = st.selectbox("Objective", ["Awareness","Adoption"], key="select_objective")
    response_tone = st.selectbox("Response Tone", ["Formal","Casual"], key="select_tone")
    st.session_state.language = st.radio("Language", ["English", "Arabic"], horizontal=True, key="select_language")

# ---------------------------- Title ----------------------------
st.markdown(f'''
<div class="title-box">
    <img src="{GSK_LOGO_URL}" width="140">
    <img src="{AI_LOGO_URL}" class="ai-logo">
    <h1>💡 AI Sales Call Assistant</h1>
    <p>Empowering reps for smarter <b style="color:#FF6F00;">{brand.upper()}</b> conversations</p>
    <button onclick="window.location.reload();" style="position:absolute;top:10px;right:10px;">🔄 Reset</button>
</div>
''', unsafe_allow_html=True)

# ---------------------------- Chat Container ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for item in st.session_state.chat_history:
    if item["role"]=="user": st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(item["content"])}</div>', unsafe_allow_html=True)
    elif item["role"]=="assistant":
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(item["content"])}<br>'
                    '<button>👍</button> <button>👎</button> <button>✍️ Need more</button></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Chat Input ----------------------------
user_input = st.chat_input("Ask or continue your sales dialogue...")
if user_input:
    st.session_state.chat_history.append({"role":"user","content":user_input})
    # Placeholder AI response
    ai_resp = f"(AI Response for {user_input})"
    st.session_state.chat_history.append({"role":"assistant","content":ai_resp})
    st.rerun()

# ---------------------------- Export ----------------------------
if st.session_state.chat_history:
    with st.expander("💾 Export / Download Chat", expanded=False):
        text_export = "\n\n".join([f"{e['role'].capitalize()}: {e['content']}" for e in st.session_state.chat_history])
        st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{brand}_chat.txt")
        if DOCX_AVAILABLE:
            doc = Document()
            doc.add_heading("AI Sales Call Assistant Export",0)
            doc.add_paragraph(text_export)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            doc.save(tmp.name)
            st.download_button("⬇️ Download DOCX", open(tmp.name,"rb"), file_name=f"{brand}_chat.docx")

# ---------------------------- Disclaimer ----------------------------
st.markdown(f'''
<div class="fixed-disclaimer">
<b>Disclaimer:</b> Please remember that "AI" can make mistakes. 
This AI assistant provides medical and product educational approved content by GSK for informational purposes only and should not replace professional judgment.
</div>
''', unsafe_allow_html=True)
