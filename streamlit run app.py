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
    import groq
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
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
if not GROQ_API_KEY:
    st.warning("⚠️ GROQ_API_KEY not found in environment.")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ----------------------------
# Session state defaults
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
  transition: background-size 0.3s ease;
}}
[data-testid="stSidebar"][aria-expanded="true"] ~ .main .stApp {{
  background-size: calc(100% - 280px) auto;
}}
[data-testid="stSidebar"][aria-expanded="false"] ~ .main .stApp {{
  background-size: calc(120% - 80px) auto;
}}
.gsk-logo {{
  position: absolute;
  top: 60px;
  left: 10px;
  z-index: 1200;
}}
.title-box {{
  background: rgba(235,240,240,0.6);
  padding: 25px;
  border-radius: 12px;
  text-align: center;
  max-width: 75%;
  margin: 12px auto;
}}
.title-box h1 {{ font-size: 38px; font-weight: 800; margin: 0; }}
.title-box p {{ font-size: 18px; margin: 6px 0 0 0; }}
.chat-bubble-user, .chat-bubble-ai {{
  padding: 12px;
  border-radius: 12px;
  margin: 8px 0;
  display: block;
  max-width: 95%;
  word-wrap: break-word;
  color: black;
}}
.chat-bubble-user {{ background:#f1f8e9; margin-left: auto; }}
.chat-bubble-ai {{ background:#f5f7fa; margin-right: auto; }}
.bottom-input {{
  position: fixed;
  bottom: 12px;
  left: 16px;
  right: 16px;
  z-index: 2000;
  display:flex;
  gap:12px;
  align-items:center;
  background: rgba(255,255,255,0.6);
  padding:10px;
  border-radius:12px;
}}
.bottom-input input[type="text"] {{
  width: 100%;
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid #ddd;
}}
.bottom-input button {{
  min-width:120px;
  padding: 8px 14px;
  border-radius: 8px;
  border: none;
  background: #ff8c00;
  color: white;
  font-weight:600;
}}
.highlight-step {{ font-weight:700; color:#000; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(f'<div class="gsk-logo"><img src="{GSK_LOGO_URL}" width="140"></div>', unsafe_allow_html=True)

st.markdown("""
<div class="title-box">
  <h1>💡 AI Sales Call Assistant</h1>
  <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
</div>
""", unsafe_allow_html=True)
st.markdown('<p style="text-align:center;font-weight:600;">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Data definitions
# ----------------------------
gsk_brands = {"Shingrix":"https://www.shingrix.com/","Trelegy":"https://www.trelegy.com/","Zejula":"https://www.zejula.com/"}
race_segments = ["R – Reach","A – Acquisition","C – Conversion","E – Engagement"]
doctor_barriers = ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy","Accessibility/Logistics","Patient reluctance","Other clinical doubts"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
sales_call_flow = ["1- Prepare the call","2- Engage","3- Create opportunities","4- Impact GSO (Good sell outcome)","5- Influence","6- Analyze and post call analysis"]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist","Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"]

# ----------------------------
# Sidebar
# ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Select Brand", options=list(gsk_brands.keys()))
    segment = st.selectbox("Select RACE Segment", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty", options=specialties)
    persona = st.selectbox("Select HCP Persona", options=personas)
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"])
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"])

# ----------------------------
# PDF Upload & Summarization
# ----------------------------
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:2000]+"..." if len(full_text)>2000 else full_text

        # Extract references
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"

        # Summarize in chunks
        chunk_size = 2000
        chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        summaries = []
        for chunk in chunks[:3]:  # limit to 3 chunks to avoid heavy cost
            if client:
                try:
                    resp = client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        messages=[{"role":"system","content":"Summarize medical reference text in clear bullet points."},
                                  {"role":"user","content":chunk}],
                        temperature=0.3
                    )
                    summaries.append(resp.choices[0].message.content.strip())
                except Exception:
                    continue
        st.session_state.pdf_summary = "\n".join(summaries) if summaries else ""
        st.success("✅ PDF processed and summarized.")
    except Exception as e:
        st.error("PDF error: "+str(e))

# ----------------------------
# Humanized TTS
# ----------------------------
async def _edge_save_async(ssml_text: str, voice: str, outpath: str):
    comm = edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts_humanized(text: str, lang: str) -> Optional[str]:
    if not text or not text.strip():
        return None
    text = re.sub(r'[.,;:\-]', '', text)
    text = re.sub(r'(\d+)[\.\-:]', r'\1', text)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    ssml_parts = []
    for s in sentences:
        if s.strip():
            ssml_parts.append(f"<prosody rate='slow'>{s.strip()}<break time='0.8s'/></prosody>")
    ssml_text = "<speak>"+" ".join(ssml_parts)+"</speak>"
    voice = "ar-EG-SalmaNeural" if lang=="العربية" else "en-US-AriaNeural"
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        asyncio.run(_edge_save_async(ssml_text, voice, tmp_name))
        with open(tmp_name, "rb") as f:
            b = f.read()
        return base64.b64encode(b).decode("utf-8")
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
        "- Provide actionable sales suggestions and short 3–6 line sample script.",
        "- Output in professional language matching tone and length."
    ]
    if re.search(r"\b(sales call flow|call flow|sales flow|sales steps)\b", user_input, flags=re.I):
        instructions.append("Return call steps as bold bullet points with 1-2 sentences actionable guidance: " + ", ".join([f"**{s}**" for s in sales_call_flow]))
    if re.search(r"\b(objection|concern|barrier|hesitat|not convinced|resist)\b", user_input, flags=re.I):
        instructions.append("Use APACT structure: **Acknowledge**, **Probing**, **Action**, **Confirm**, **Transition**.")
    return "\n".join([
        f"Language: {language}",
        f"User input: {user_input}",
        f"Brand: {brand}",
        f"RACE Segment: {segment}",
        f"Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}",
        f"Objective: {objective}",
        f"Doctor Specialty: {specialty}",
        f"HCP Persona: {persona}",
        "",
        "Instructions:",
        *instructions,
        "References:", refs,
        "Summary:", pdf_summary
    ])

# ----------------------------
# Groq AI call
# ----------------------------
def call_groq_with_retry(prompt:str, language:str, max_retries:int=3):
    if client is None: return "⚠️ AI service not configured."
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role":"system","content":f"You are a helpful sales assistant in {language}."},{"role":"user","content":prompt}],
                temperature=0.7
            )
            return resp.choices[0].message.content
        except Exception as e:
            if attempt < max_retries-1:
                time.sleep(2*(attempt+1))
            else:
                return f"⚠️ AI call failed after retries. {e}"

# ----------------------------
# Chat interface
# ----------------------------
st.markdown("### 💬 Chat")
for msg in st.session_state.chat_history:
    if msg["role"]=="user":
        st.markdown(f"<div class='chat-bubble-user'>{msg['content']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='chat-bubble-ai'>{msg['content']}</div>", unsafe_allow_html=True)
        if msg.get("audio"):
            st.audio(base64.b64decode(msg["audio"]), format="audio/mp3")

with st.container():
    col1, col2 = st.columns([5,1])
    with col1:
        user_text = st.text_input("Type your query here…", key="user_input", placeholder="Ask about sales call steps, objections handling, sample scripts…")
    with col2:
        send_button = st.button("Send")

if send_button and user_text.strip():
    st.session_state.chat_history.append({"role":"user","content":user_text})
    prompt = build_prompt(user_text, st.session_state.language)
    ai_output = call_groq_with_retry(prompt, st.session_state.language)
    audio_b64 = synthesize_tts_humanized(ai_output, st.session_state.language)
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"audio":audio_b64})
    st.experimental_rerun()

if st.button("Clear Chat History"):
    st.session_state.chat_history = []
    st.experimental_rerun()
