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
from fpdf import FPDF

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
for key, default in [
    ("chat_history", []),
    ("uploaded_pdf_text", ""),
    ("pdf_summary", ""),
    ("voice_pref", "Old Male"),
    ("language", "English"),
    ("pdf_summary_size", "Normal"),
    ("chat_input",""),
    ("prompt_index", 0),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = "https://images.unsplash.com/photo-1592928306923-47e982b99e60?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w5MTIyfDB8MHwxfHNlYXJjaHwxfHxtZWRpY2FsJTIwZ3JhZGllbnR8ZW58MHx8fHwxNjk4NjU0MTU5&ixlib=rb-4.0.3&q=80&w=1080"
GSK_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/GSK-logo.png"
AI_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/AURA.png"

# ---------------------------- CSS ----------------------------
CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: center top;
  background-attachment: fixed;
  background-size: cover;
}}
.title-box {{
  background: rgba(255,255,255,0.95);
  padding: 12px;
  border-radius: 12px;
  text-align: left;
  margin: 10px auto;
  width: 95%;
  position: relative;
}}
.title-box img.ai-logo {{
    position: absolute;
    top: 12px;
    right: 15px;
    width: 130px;
}}
.chat-container {{
  max-height: 60vh;
  overflow-y: auto;
  padding: 12px;
  border-radius: 10px;
  background: rgba(240,240,240,0.7);
  margin-bottom: 20px;
}}
.chat-bubble-user, .chat-bubble-ai {{
  display:block;
  padding:12px;
  border-radius:12px;
  margin:8px 0;
  max-width: 90%;
  word-wrap: break-word;
}}
.chat-bubble-user {{ background: #0078D7; color:white; margin-left:auto; }}
.chat-bubble-ai {{ background: #d9f0ff; margin-right:auto; color:#000; }}
.feedback-icons {{
  display:flex;
  gap:12px;
  margin-top:4px;
}}
.fixed-chat-input {{
    position: fixed;
    bottom: 60px;
    left: 20px;
    right: 20px;
    z-index: 10002;
    display:flex;
}}
.fixed-chat-input input {{
    width: 100%;
    padding: 12px;
    border-radius: 8px 0 0 8px;
    border: 1px solid #ccc;
}}
.fixed-chat-input button {{
    width: 80px;
    border-radius: 0 8px 8px 0;
    border:none;
    background:#0078D7;
    color:white;
}}
.fixed-disclaimer {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    color: #444;
    text-align: center;
    font-size: 14px;
    padding: 10px;
    border-top: 2px solid #FF6F00;
    z-index: 9999;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ Client ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
if not GROQ_API_KEY:
    st.warning("⚠️ Missing GROQ_API_KEY in Streamlit Secrets")
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Brand Config ----------------------------
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
specialties = ["GP", "Oncologist", "Dermatologist", "Cardiologist"]
objectives = ["Awareness","Adoption"]

# ---------------------------- Helper Functions ----------------------------
def load_local_references(folder_path):
    text_all=""
    if not os.path.exists(folder_path): return ""
    for file in os.listdir(folder_path):
        fp=os.path.join(folder_path,file)
        try:
            if file.lower().endswith(".pdf"):
                reader=PdfReader(fp)
                text_all+="".join([p.extract_text() or "" for p in reader.pages])
            elif file.lower().endswith(".txt"):
                text_all+=open(fp,"r",encoding="utf-8").read()
        except: pass
    return text_all.strip()

def load_external_references(url_list):
    all_text=""
    for url in url_list:
        try:
            r=requests.get(url,timeout=8)
            if r.status_code==200: all_text+=r.text+"\n"
        except: pass
    return all_text

# ---------------------------- Sidebar ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand=st.selectbox("Brand",list(brand_data.keys()))
    segment=st.selectbox("Segment",brand_data[brand]["segments"])
    persona=st.selectbox("HCP Persona",brand_data[brand]["personas"])
    barrier=st.multiselect("Doctor Barrier",brand_data[brand]["barriers"])
    specialty=st.selectbox("Specialty",specialties)
    objective=st.selectbox("Objective",objectives)
    st.session_state.language=st.radio("Language", ["English","Arabic"],horizontal=True)
with st.sidebar.expander("External References"):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

# ---------------------------- Title & Reset ----------------------------
cols = st.columns([9,1])
with cols[0]:
    st.markdown(f'''
    <div class="title-box">
        <img src="{GSK_LOGO_URL}" width="140">
        <img src="{AI_LOGO_URL}" class="ai-logo">
        <h1>💡 AI Sales Call Assistant</h1>
        <p>Empowering reps for smarter <b style="color:#FF6F00;">{brand.upper()}</b> conversations</p>
    </div>
    ''', unsafe_allow_html=True)
with cols[1]:
    if st.button("🔄 Reset Conversation"):
        st.session_state.chat_history=[]
        st.session_state.prompt_index=0
        st.experimental_rerun()

# ---------------------------- Medical & Sales Summary ----------------------------
local_ref_text = load_local_references(brand_data[brand]["references_path"])
external_text = load_external_references([u for u in external_urls if u.strip()])
combined_refs = (local_ref_text + "\n" + external_text).strip()
st.markdown("### 📚 Medical References & Sales Module")
if combined_refs:
    st.text_area("Preview:", combined_refs[:3000], height=200)

# ---------------------------- Prompt Suggestions ----------------------------
PROMPTS = [
    "Generate call flow for this HCP",
    "Specify patient profile",
    "Add probing questions for barriers",
    "Emotive vaccination value",
    "Assertive questions to gain commitment",
    "Patient-oriented engagement",
    "Cost-benefit value approach",
    "Handle barrier for patient profile"
]
def get_next_prompts():
    idx = st.session_state.prompt_index
    prompts = PROMPTS[idx:idx+2]
    return prompts
next_prompts = get_next_prompts()

# ---------------------------- AI Generation ----------------------------
def generate_ai_response(user_input):
    context = combined_refs[:15000]
    system_prompt = f"You are a pharma AI assistant for {brand}, persona {persona}, segment {segment}, specialty {specialty}, objective {objective}. Context:\n{context}"
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_input}],
            temperature=0.65
        )
        return response.choices[0].message.content
    except:
        return f"(Fallback) Based on brand {brand}, persona {persona}: {user_input}"

def generate_audio(text):
    tmp_file=tempfile.NamedTemporaryFile(delete=False,suffix=".mp3")
    try:
        if ELEVENLABS_AVAILABLE:
            audio_stream=elevenlabs.generate(text=text,voice=ELEVENLABS_VOICE_ID,stream=True)
            with open(tmp_file.name,"wb") as f:
                for chunk in audio_stream: f.write(chunk)
        else:
            gTTS(text=text,lang="en",slow=True).save(tmp_file.name)
        return base64.b64encode(open(tmp_file.name,"rb").read()).decode()
    except: return ""

# ---------------------------- Chat UI ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for item in st.session_state.chat_history:
    if item["role"]=="user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(item["content"])}</div>', unsafe_allow_html=True)
    elif item["role"]=="assistant":
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(item["content"])}</div>', unsafe_allow_html=True)
        if item.get("audio"): st.audio(base64.b64decode(item["audio"]),format="audio/mp3")
        # Feedback icons
        cols=st.columns(4)
        if cols[0].button("👍", key=f"like_{item['content']}"): st.session_state.prompt_index+=1
        if cols[1].button("👎", key=f"dislike_{item['content']}"): st.session_state.prompt_index+=1
        if cols[2].button("🔄", key=f"more_{item['content']}"): st.session_state.prompt_index+=1
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Chat Input with Send ----------------------------
st.markdown('<div class="fixed-chat-input">', unsafe_allow_html=True)
chat_input = st.text_input("Ask or continue your sales dialogue...", key="chat_input")
send_pressed = st.button("Send")
if chat_input and send_pressed:
    st.session_state.chat_history.append({"role":"user","content":chat_input})
    ai_resp = generate_ai_response(chat_input)
    audio_base64 = generate_audio(ai_resp)
    st.session_state.chat_history.append({"role":"assistant","content":ai_resp,"audio":audio_base64})
    st.session_state.prompt_index+=1
    st.session_state.chat_input=""
    st.experimental_rerun()
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Disclaimer ----------------------------
st.markdown(f"""
<div class="fixed-disclaimer">
⚠️ Disclaimer: Please remember that "AI" can make mistakes. This AI assistant provides medical and product educational approved content by GSK for informational purposes only and should not replace professional judgment.
</div>
""", unsafe_allow_html=True)

# ---------------------------- Export ----------------------------
if st.session_state.chat_history:
    with st.expander("Export Chat", expanded=False):
        text_export = "\n\n".join([f"{e['role'].capitalize()}: {e['content']}" for e in st.session_state.chat_history])
        # Word
        if DOCX_AVAILABLE and st.button("Export Word (.docx)"):
            doc = Document()
            doc.add_heading("AI Sales Call Assistant Export",0)
            for e in st.session_state.chat_history:
                doc.add_paragraph(f"{e['role'].capitalize()}: {e['content']}")
            tmp=tempfile.NamedTemporaryFile(delete=False,suffix=".docx")
            doc.save(tmp.name)
            st.download_button("⬇️ Download Word",open(tmp.name,"rb"),file_name=f"{brand}_chat.docx")
        # PDF
        if st.button("Export PDF"):
            pdf=FPDF()
            pdf.add_page()
            pdf.set_font("Arial",size=12)
            for e in st.session_state.chat_history:
                pdf.multi_cell(0,6,f"{e['role'].capitalize()}: {e['content']}\n")
            tmp=tempfile.NamedTemporaryFile(delete=False,suffix=".pdf")
            pdf.output(tmp.name)
            st.download_button("⬇️ Download PDF",open(tmp.name,"rb"),file_name=f"{brand}_chat.pdf")
