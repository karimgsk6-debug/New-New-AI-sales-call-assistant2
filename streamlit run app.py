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
for key, default in [("chat_history", []), ("uploaded_pdf_text", ""), ("pdf_summary", ""), 
                     ("voice_pref", "Old Male"), ("language", "English"), ("pdf_summary_size", "Normal"),
                     ("chat_input","")]:
    if key not in st.session_state:
        st.session_state[key] = default

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
}}
.prompt-suggestions {{
  display: flex;
  overflow-x: auto;
  gap: 8px;
  padding: 6px 0;
  margin-bottom: 10px;
}}
.prompt-suggestion-btn {{
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0078D7;
  color: white;
  padding: 6px 14px;
  border-radius: 20px;
  cursor: pointer;
  white-space: nowrap;
  font-size: 13px;
  transition: all 0.2s;
  border: none;
}}
.prompt-suggestion-btn:hover {{
  background: #005a9e;
}}
.prompt-icon {{
  margin-right: 6px;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ Client ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    st.warning("⚠️ Missing GROQ_API_KEY in Streamlit Secrets")
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Brand Config ----------------------------
def safe_makedirs(path):
    try: os.makedirs(path, exist_ok=True)
    except: pass

brand_data = {
    "shingrix": {"references_path": ".devcontainer/references/shingrix/", "segments":["R","A"], "personas":["Uncommitted"]},
    "jemperli": {"references_path": ".devcontainer/references/jemperli/", "segments":["Target"], "personas":["Data-Driven"]}
}

specialties = ["GP","Oncologist"]
objectives = ["Awareness","Adoption"]

# ---------------------------- Helper: Load References ----------------------------
def load_local_references(folder_path):
    text_all=""
    if not os.path.exists(folder_path): return "", f"⚠️ Folder not found: {folder_path}"
    for file in os.listdir(folder_path):
        try:
            fp=os.path.join(folder_path,file)
            if file.lower().endswith(".pdf"):
                reader=PdfReader(fp)
                text_all+="".join([p.extract_text() or "" for p in reader.pages])
            elif file.lower().endswith(".txt"):
                text_all+=open(fp,"r",encoding="utf-8").read()
        except: text_all+=f"\n[Error reading {file}]"
    return text_all.strip(), None

def load_external_references(url_list):
    all_text=""
    for url in url_list:
        try:
            r=requests.get(url,timeout=8)
            if r.status_code==200: all_text+=r.text+"\n"
        except: all_text+=f"\n[Error fetching {url}]"
    return all_text

# ---------------------------- Sidebar ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand=st.selectbox("Brand",list(brand_data.keys()))
    segment=st.selectbox("Segment",brand_data[brand]["segments"])
    persona=st.selectbox("HCP Persona",brand_data[brand]["personas"])
    specialty=st.selectbox("Specialty",specialties)
    objective=st.selectbox("Objective",objectives)
    st.session_state.language=st.radio("Language", ["English","Arabic"],horizontal=True)

with st.sidebar.expander("Add External Reference URLs", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

# ---------------------------- Title ----------------------------
st.markdown(f'''
<div class="title-box">
    <img src="{GSK_LOGO_URL}" width="140">
    <img src="{AI_LOGO_URL}" class="ai-logo">
    <h1>💡 AI Sales Call Assistant</h1>
    <p>Empowering reps for smarter <b style="color:#FF6F00;">{brand.upper()}</b> conversations</p>
</div>
''', unsafe_allow_html=True)

# ---------------------------- Load References ----------------------------
local_ref_text,_ = load_local_references(brand_data[brand]["references_path"])
external_text=load_external_references([u for u in external_urls if u.strip()])

# ---------------------------- Prompt Suggestions (Copilot Style Fixed) ----------------------------
PROMPT_SUGGESTIONS = [
    {"icon":"💬","text":"Generate call flow for this HCP"},
    {"icon":"🧾","text":"Specify patient profile"},
    {"icon":"❓","text":"Add probing questions for barriers"},
    {"icon":"💉","text":"Emotive vaccination value"},
    {"icon":"✅","text":"Assertive questions to gain commitment"},
    {"icon":"👥","text":"Patient-oriented engagement"},
    {"icon":"💰","text":"Cost-benefit value approach"},
    {"icon":"🚫","text":"Handle barrier for patient profile"}
]

st.markdown("### Prompt Suggestions")

cols = st.columns(len(PROMPT_SUGGESTIONS))
for i, item in enumerate(PROMPT_SUGGESTIONS):
    if cols[i].button(f"{item['icon']} {item['text']}", key=f"prompt_{i}"):
        st.session_state.chat_input = item['text']

# ---------------------------- AI Response ----------------------------
def sanitize_user_input(text): return escape(text.strip())
def is_safe_content(text): return not any(w in text.lower() for w in ["sex","violence","attack","terror"])
def log_interaction(u,a): pass

def enhance_text_for_tts(text):
    text=re.sub(r',',', ',text)
    text=re.sub(r'\.', '. ', text)
    text=re.sub(r'\?', '? ', text)
    text=re.sub(r'!', '! ', text)
    text=re.sub(r'\s+',' ',text)
    return text

def generate_audio(text):
    if len(text)>2000: text=text[:2000]+"..."
    if not is_safe_content(text): return ""
    tmp_file=tempfile.NamedTemporaryFile(delete=False,suffix=".mp3")
    text_for_tts=enhance_text_for_tts(text)
    try:
        if ELEVENLABS_AVAILABLE:
            audio_stream=elevenlabs.generate(text=text_for_tts,voice=ELEVENLABS_VOICE_ID,stream=True)
            with open(tmp_file.name,"wb") as f:
                for chunk in audio_stream: f.write(chunk)
        else:
            tts=gTTS(text=text_for_tts,lang="en",slow=True)
            tts.save(tmp_file.name)
        return base64.b64encode(open(tmp_file.name,"rb").read()).decode()
    except: return ""

def generate_ai_response(user_input):
    safe_prompt=sanitize_user_input(user_input)
    if not is_safe_content(safe_prompt): return "(⚠️ Unsafe prompt blocked)"
    context="\n".join([local_ref_text,external_text,st.session_state.uploaded_pdf_text])[:15000]
    final_prompt=f"{safe_prompt}\n\nContext:\n{context}"
    ai_resp=f"{safe_prompt}\n\n[Using context snippet: {context[:500]}...]"
    log_interaction(safe_prompt,ai_resp)
    return ai_resp

# ---------------------------- Chat Container ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for entry in st.session_state.chat_history:
    role_class="chat-bubble-user" if entry["role"]=="user" else "chat-bubble-ai"
    st.markdown(f'<div class="{role_class}">{entry["content"]}</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Chat Input ----------------------------
chat_input=st.text_area("Ask or continue dialogue:",st.session_state.chat_input,key="chat_input",height=60)
if st.button("Send"):
    if chat_input.strip():
        ai_reply=generate_ai_response(chat_input.strip())
        audio_base64=generate_audio(ai_reply)
        st.session_state.chat_history.append({"role":"user","content":chat_input.strip()})
        st.session_state.chat_history.append({"role":"assistant","content":ai_reply,"audio":audio_base64})
        st.session_state.chat_input=""
        st.experimental_rerun()

# ---------------------------- Enhanced Export ----------------------------
if st.button("Export Medical References"):
    medical_refs = [
        {"title": "Study on HCP engagement", "url": "https://example.com/study1", "context": "Highlights best practices for engagement"},
        {"title": "Vaccination barriers report", "url": "https://example.com/study2", "context": "Analyzes common patient objections"},
        {"title": "Cost-benefit analysis guide", "url": "https://example.com/study3", "context": "Provides financial justification for treatment"}
    ]
    export_text = "### Medical References Export\n\n"
    for ref in medical_refs:
        export_text += f"- **{ref['title']}**\n  - URL: {ref['url']}\n  - Context: {ref['context']}\n\n"
    st.download_button("Download Medical References", data=export_text, file_name="medical_references.md", mime="text/markdown")

if st.button("Export Sales Call Module"):
    sales_module = {
        "HCP Persona": "Data-Driven Oncologist",
        "Key Barriers": ["Limited patient eligibility", "Concerns about cost"],
        "Suggested Approach": ["Emphasize patient eligibility criteria", "Highlight cost-benefit outcomes"],
        "Sample Call Flow": ["Intro -> Probe -> Objection Handling -> Commitment -> Close"]
    }
    export_text = "### Sales Call Module Export\n\n"
    for key, value in sales_module.items():
        export_text += f"- **{key}**: {', '.join(value) if isinstance(value, list) else value}\n"
    st.download_button("Download Sales Call Module", data=export_text, file_name="sales_call_module.md", mime="text/markdown")

# ---------------------------- Disclaimer ----------------------------
st.markdown("""
<div class="fixed-disclaimer">
⚠️ This AI Sales Call Assistant is for educational purposes only. Verify all info with official medical references.
</div>
""", unsafe_allow_html=True)
