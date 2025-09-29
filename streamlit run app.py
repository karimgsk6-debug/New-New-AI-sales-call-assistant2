# app.py
import os
import re
import time
import base64
import tempfile
import asyncio
from typing import Optional
from datetime import datetime
from io import BytesIO

import streamlit as st
from PIL import Image, ImageStat
import requests
import PyPDF2
import edge_tts

# Groq client
try:
    from groq import Groq
except Exception as e:
    st.error("groq package not found. Install groq to enable AI. Error: " + str(e))
    raise

# Optional docx export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", page_icon="💡", layout="wide")

# ----------------------------
# Load GROQ API key
# ----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    st.warning("⚠️ GROQ_API_KEY not found. Set it in environment or Streamlit Secrets.")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ----------------------------
# Session state
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "extracted_medical_ref" not in st.session_state:
    st.session_state.extracted_medical_ref = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "language" not in st.session_state:
    st.session_state.language = "English"

# ----------------------------
# Assets & styling
# ----------------------------
BACKGROUND_URL = "https://www.shutterstock.com/image-photo/excited-girl-white-shirt-using-260nw-708132598.jpg"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"

def get_brightness(url: str) -> int:
    try:
        r = requests.get(url, timeout=8)
        img = Image.open(BytesIO(r.content)).convert("L")
        stat = ImageStat.Stat(img)
        return int(stat.mean[0])
    except Exception:
        return 255

brightness = get_brightness(BACKGROUND_URL)
text_color = "black" if brightness > 130 else "white"

CSS = f"""
<style>
.stApp {{
    background: url('{BACKGROUND_URL}') no-repeat top right;
  background-size: calc(120% - 280px) auto;
  background-attachment: flix;
  transition: background-size 0.3s ease;
}}
.stSidebar {{
  background-color: rgba(255,255,255,0.9);
}}
.chat-bubble-user {{
  background:#f1f8e9;
  padding:10px;
  border-radius:10px;
  margin:5px 0;
}}
.chat-bubble-ai {{
  background:#f5f7fa;
  padding:10px;
  border-radius:10px;
  margin:5px 0;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(f'<img src="{GSK_LOGO_URL}" width="140">', unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center'>💡 AI Sales Call Assistant</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center;font-weight:600;'>⚠️ For training and educational purposes only.</p>", unsafe_allow_html=True)

# ----------------------------
# Data
# ----------------------------
sales_call_flow = [
    "Prepare the call",
    "Engage",
    "Create opportunities",
    "Impact GSO (Good Sell Outcome)",
    "Influence",
    "Analyze and post call analysis"
]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]

# ----------------------------
# PDF Upload & Summarization
# ----------------------------
uploaded_pdf = st.file_uploader("📄 Upload Medical Reference PDF", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:2000]+"..." if len(full_text)>2000 else full_text
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"
        st.session_state.pdf_summary = "\n".join(full_text.split(".")[:5])
        with st.expander("📑 PDF Summary", expanded=False):
            st.markdown(st.session_state.pdf_summary)
    except Exception as e:
        st.error("PDF error: "+str(e))

# ----------------------------
# TTS: humanized voice
# ----------------------------
async def _edge_save_async(ssml_text: str, voice: str, outpath: str):
    comm = edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts_base64(text: str, lang: str) -> Optional[str]:
    if not text or not text.strip():
        return None
    text = re.sub(r'[.,;:\-]', '', text)
    text = re.sub(r'(\d+)[\.\-:]', r'\1', text)
    sentences = re.split(r'(?<=[.?!])\s+', text)
    ssml_parts = []
    for s in sentences:
        if s.strip():
            ssml_parts.append(f"<prosody rate='slow'>{s}<break time='0.7s'/></prosody>")
    ssml_text = "<speak>"+" ".join(ssml_parts)+"</speak>"
    voice = "ar-EG-SalmaNeural" if lang=="Arabic" else "en-US-AriaNeural"
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        asyncio.run(_edge_save_async(ssml_text, voice, tmp_name))
        with open(tmp_name, "rb") as f:
            b = f.read()
        return base64.b64encode(b).decode("utf-8")
    except Exception as e:
        st.warning("TTS generation failed: "+str(e))
        return None
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)

# ----------------------------
# Prompt builder
# ----------------------------
def build_prompt(user_input:str, language:str)->str:
    pdf_summary = st.session_state.pdf_summary or ""
    refs = st.session_state.extracted_medical_ref or "None"
    instructions = [
        "- Use uploaded PDF summary and references as primary sources.",
        "- Provide actionable sales suggestions and 3–6 line sample script.",
        "- Use bold call steps and APACT framework where relevant.",
        f"- Sales Call Flow: {', '.join([f'**{s}**' for s in sales_call_flow])}",
        f"- APACT: {', '.join([f'**{s}**' for s in APACT_STEPS])}"
    ]
    return "\n".join([
        f"Language: {language}",
        f"User input: {user_input}",
        "",
        "Instructions:",
        *instructions,
        "",
        "PDF Summary:", pdf_summary,
        "References:", refs
    ])

# ----------------------------
# Groq call
# ----------------------------
def call_groq_with_retry(prompt:str, language:str, max_retries:int=3, base_delay:int=2):
    if client is None: return "⚠️ AI not configured."
    last_err = None
    for attempt in range(1,max_retries+1):
        try:
            resp = client.chat.completions.create(
                model="meta-llama/llama-3.1-8b-instruct",
                messages=[
                    {"role":"system","content":f"You are a helpful sales assistant in {language}."},
                    {"role":"user","content":prompt}
                ],
                temperature=0.7
            )
            return resp.choices[0].message.content
        except Exception as e:
            last_err=e
            wait = base_delay*(2**(attempt-1))
            st.warning(f"Retrying in {wait}s (attempt {attempt}/{max_retries})...")
            time.sleep(wait)
    return f"⚠️ AI call failed after retries. Last error: {last_err}"

# ----------------------------
# Render chat
# ----------------------------
def render_chat_history():
    for msg in st.session_state.chat_history:
        if msg["role"]=="user":
            st.markdown(f"<div class='chat-bubble-user'>{msg['content']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='chat-bubble-ai'>{msg['content']}</div>", unsafe_allow_html=True)
            if msg.get("audio"):
                st.audio(base64.b64decode(msg["audio"]), format="audio/mp3")

render_chat_history()

# ----------------------------
# Bottom input
# ----------------------------
user_text = st.text_input("💬 Type your query here…", key="user_input")
if st.button("Send") and user_text.strip():
    st.session_state.chat_history.append({"role":"user","content":user_text,"time":datetime.now().strftime("%H:%M")})
    prompt = build_prompt(user_text, st.session_state.language)
    ai_output = call_groq_with_retry(prompt, st.session_state.language)
    audio_b64 = synthesize_tts_base64(ai_output, st.session_state.language)
    st.session_state.chat_history.append({
        "role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M"),"audio":audio_b64
    })
    st.experimental_rerun()

# ----------------------------
# Clear + Export
# ----------------------------
if st.button("Clear Chat History"):
    st.session_state.chat_history = []
    st.experimental_rerun()

if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("📄 Export Chat to Word"):
        doc = Document()
        doc.add_heading("AI Sales Call Assistant Chat History", 0)
        for msg in st.session_state.chat_history:
            role = "User" if msg["role"]=="user" else "AI"
            doc.add_paragraph(f"{role} [{msg['time']}]: {msg['content']}")
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        href = f'<a href="data:application/octet-stream;base64,{b64}" download="chat_history.docx">⬇️ Download Chat</a>'
        st.markdown(href, unsafe_allow_html=True)
