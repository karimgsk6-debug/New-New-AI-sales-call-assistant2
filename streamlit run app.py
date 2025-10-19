import streamlit as st
from PIL import Image
from io import BytesIO
import re
import tempfile
import base64
import os
from datetime import datetime
from groq import Groq
from PyPDF2 import PdfReader
from html import escape
import requests

# Optional DOCX export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ModuleNotFoundError:
    DOCX_AVAILABLE = False

# TTS
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except ModuleNotFoundError:
    ELEVENLABS_AVAILABLE = False

from gtts import gTTS

# ---------------------------- Secrets ----------------------------
ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    elevenlabs.api_key = ELEVENLABS_API_KEY

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ---------------------------- Page Config ----------------------------
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
GSK_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/gsk-logo.png"
AI_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/ai-logo.png"

CSS = f"""
<style>
body {{
    background-image: url('{BACKGROUND_URL}');
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
 margin:5px 0;
 border-radius:12px;
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
.prompt-suggestions {{
  background: rgba(255,255,255,0.9);
  border-radius: 10px;
  padding: 8px;
  margin-bottom: 10px;
  font-size: 14px;
  cursor: pointer;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- Brand Data ----------------------------
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
def safe_makedirs(path):
    try: os.makedirs(path, exist_ok=True)
    except: pass

def load_local_references(folder_path):
    text_all = ""
    if not os.path.exists(folder_path):
        return ""
    for f in os.listdir(folder_path):
        if f.lower().endswith(".pdf"):
            reader = PdfReader(os.path.join(folder_path, f))
            text_all += "".join([p.extract_text() or "" for p in reader.pages])
        elif f.lower().endswith(".txt"):
            with open(os.path.join(folder_path, f), "r", encoding="utf-8") as ftxt:
                text_all += ftxt.read()
    return text_all

def load_external_references(url_list):
    all_text = ""
    for url in url_list:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                all_text += r.text + "\n"
        except:
            continue
    return all_text

def generate_audio(text):
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        if ELEVENLABS_AVAILABLE:
            audio_stream = elevenlabs.generate(text=text, voice=ELEVENLABS_VOICE_ID, stream=True)
            with open(tmp_file.name, "wb") as f:
                for chunk in audio_stream: f.write(chunk)
        else:
            tts = gTTS(text=text, lang="en", slow=True)
            tts.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return ""

def generate_ai_response(user_input, context):
    if not client: return "⚠️ Missing GROQ API key"
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "You are a helpful pharma AI assistant."},
                      {"role": "user", "content": f"{user_input}\nContext:\n{context[:5000]}"}],
            temperature=0.4
        )
        return response.choices[0].message.content
    except:
        return "⚠️ AI Error generating response"

# ---------------------------- Sidebar Filters ----------------------------
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

# ---------------------------- Title ----------------------------
st.markdown(f'''
<div class="title-box">
   <img src="{GSK_LOGO_URL}" width="140">
   <img src="{AI_LOGO_URL}" class="ai-logo">
   <h1>💡 AI Sales Call Assistant</h1>
   <p>Empowering reps for smarter <b style="color:#FF6F00;">{brand.upper()}</b> conversations</p>
</div>
''', unsafe_allow_html=True)

# ---------------------------- Chat Container ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for msg in st.session_state.chat_history:
    role_class = "chat-bubble-user" if msg["role"]=="user" else "chat-bubble-ai"
    st.markdown(f'<div class="{role_class}">{escape(msg["content"])}</div>', unsafe_allow_html=True)
    if "audio" in msg and msg["audio"]:
        st.markdown(f'<div class="chat-bubble-audio"><audio controls><source src="data:audio/mp3;base64,{msg["audio"]}" type="audio/mpeg"></audio></div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Dynamic Prompt Suggestions ----------------------------
context_preview = f"Brand:{brand}, Persona:{persona}, Segment:{segment}, Specialty:{specialty}, Objective:{objective}, Barriers:{', '.join(barrier) if barrier else 'None'}"
suggestions = [
    f"Generate a call flow for {persona} with focus on {objective}.",
    f"Handle objections: {', '.join(barrier)} for {persona}.",
    f"Use latest medical references and summarize key points for {segment}.",
]

# Make suggestions clickable
for s in suggestions:
    if st.button(s):
        st.session_state.prefill_input = s

# ---------------------------- Chat Input ----------------------------
user_input = st.text_area("Ask your AI sales question or continue dialogue...", st.session_state.get("prefill_input", ""))
if st.button("Send"):
    if user_input.strip():
        st.session_state.chat_history.append({"role":"user","content":user_input})
        st.session_state.prefill_input = ""  # reset
        combined_context = load_local_references(selected_brand["references_path"]) + "\n" + load_external_references([])
        ai_resp = generate_ai_response(user_input, combined_context)
        audio_base64 = generate_audio(ai_resp)
        st.session_state.chat_history.append({"role":"assistant","content":ai_resp,"audio":audio_base64})
        st.experimental_rerun()  # safe rerun

# ---------------------------- Disclaimer ----------------------------
st.markdown('<div class="fixed-disclaimer">⚠️ This AI tool provides sales guidance. Verify all medical content before use. All interactions are logged.</div>', unsafe_allow_html=True)
