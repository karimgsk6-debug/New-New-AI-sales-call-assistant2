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

# Groq client (optional)
try:
    import groq
    from groq import Groq
except Exception:
    Groq = None

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
# Replace with your key or set environment variable GROQ_API_KEY
# ----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
client = Groq(api_key=GROQ_API_KEY) if (GROQ_API_KEY and Groq is not None) else None

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
if "voice_pref" not in st.session_state:
    st.session_state.voice_pref = "Default"

# ----------------------------
# Assets & styling variables
# ----------------------------
BACKGROUND_URL = (
    "https://www.shutterstock.com/image-photo/excited-girl-white-shirt-using-260nw-708132598.jpg"
)
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"

def get_brightness(url: str) -> int:
    try:
        r = requests.get(url, timeout=6)
        img = Image.open(BytesIO(r.content)).convert("L")
        stat = ImageStat.Stat(img)
        return int(stat.mean[0])
    except Exception:
        return 255

brightness = get_brightness(BACKGROUND_URL)
text_color = "black" if brightness > 130 else "white"

# ----------------------------
# CSS + JS
# ----------------------------
CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-attachment: fixed;
  background-size: auto 150%;
}}
[data-testid="stSidebar"] > div:first-child {{
  background: #ffffff;
  padding: 10px;
}}
.title-box {{
  background: rgba(240,240,240,0.6);
  padding: 20px;
  border-radius: 14px;
  text-align: center;
  max-width: 75%;
  margin: 12px auto;
}}
.chat-container {{
  height: 56vh;
  overflow:auto;
  padding:12px;
  border-radius:10px;
  background: rgba(255,255,255,0.8);
}}
.chat-bubble-user, .chat-bubble-ai {{
  padding:12px;
  border-radius:12px;
  margin:8px 0;
  max-width: 90%;
  word-wrap: break-word;
}}
.chat-bubble-user {{ background: #eef9e6; margin-left: auto; }}
.chat-bubble-ai {{ background: #f5f7fa; margin-right: auto; }}
.pdf-summary-inline {{
  margin-top:8px;
  background: rgba(255,255,255,0.97);
  padding:10px;
  border-radius:8px;
  border: 1px solid #eee;
}}
.bottom-bar {{
  position: fixed;
  bottom: 12px;
  left: 16px;
  right: 16px;
  background: rgba(255,255,255,0.98);
  padding:10px;
  border-radius:10px;
  display:flex;
  gap:12px;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

SCROLL_JS = """
<script>
function scrollChat(){
  const el = document.querySelector('.chat-container');
  if (el) el.scrollTop = el.scrollHeight;
}
setTimeout(scrollChat, 200);
</script>
"""

# ----------------------------
# GSK data
# ----------------------------
gsk_brands = {
    "Shingrix": "https://www.shingrix.com/",
    "Trelegy": "https://www.trelegy.com/",
    "Zejula": "https://www.zejula.com/"
}
gsk_brands_images = {
    "Shingrix":"https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Trelegy":"https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
    "Zejula":"https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png"
}
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = [
    "HCP does not consider HZ a risk","No time for discussion","Cost concerns",
    "Not convinced of efficacy","Accessibility/Logistics","Patient reluctance","Other clinical doubts"
]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
sales_call_flow = ["Prepare the call","Engage","Create opportunities","Impact GSO","Influence","Analyze and post call analysis"]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist","Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"]

# ----------------------------
# Sidebar: Filters & Options
# ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Select Brand", options=list(gsk_brands.keys()))
    img_path = gsk_brands_images.get(brand)
    if img_path:
        st.image(img_path, width=180)

    segment = st.selectbox("Select RACE Segment", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier", options=doctor_barriers)
    objective = st.selectbox("Select Objective", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty", options=specialties)
    persona = st.selectbox("Select HCP Persona", options=personas)
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"])
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"])
    st.session_state.voice_pref = st.radio("Voice Preference", ["Default","English Neural","Arabic Neural"])

# ----------------------------
# PDF Upload & Summarization
# ----------------------------
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:2000] + "..." if len(full_text) > 2000 else full_text
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"

        if client:
            summary_prompt = "Summarize in short bullet points for medical reps:\n\n" + full_text[:6000]
            resp = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role":"system","content":"You are a summarizer."},{"role":"user","content":summary_prompt}],
                temperature=0.2
            )
            st.session_state.pdf_summary = resp.choices[0].message.content
        st.success("✅ PDF processed")
    except Exception as e:
        st.error("PDF error: " + str(e))

if st.session_state.pdf_summary:
    with st.expander("📑 PDF Summary", expanded=False):
        st.markdown(st.session_state.pdf_summary)

# ----------------------------
# Helper functions
# ----------------------------
def build_ai_bubble_content(ai_text: str) -> str:
    content = ai_text.replace("\n", "<br>")
    if st.session_state.pdf_summary:
        pdf_html = "<div class='pdf-summary-inline'>" + st.session_state.pdf_summary[:500] + "...</div>"
        return f"{content}{pdf_html}"
    return content

def render_chat_history():
    html = ""
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            html += f"<div class='chat-bubble-user'>{msg['content']}</div>"
        else:
            ai_content = build_ai_bubble_content(msg["content"])
            audio_html = ""
            if msg.get("audio"):
                audio_html = f"<br><audio controls><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
            html += f"<div class='chat-bubble-ai'>{ai_content}{audio_html}</div>"
    st.markdown(f'<div class="chat-container">{html}</div>', unsafe_allow_html=True)
    st.markdown(SCROLL_JS, unsafe_allow_html=True)

# ----------------------------
# TTS
# ----------------------------
async def _edge_save_async(ssml_text: str, voice: str, outpath: str):
    comm = edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts(text: str) -> Optional[str]:
    if not text.strip():
        return None
    text = re.sub(r'[;:{}\[\]\*\^<>@#\$%&\|~_/\\]+', '', text)
    voice = "en-US-AriaNeural"
    if st.session_state.voice_pref == "Arabic Neural":
        voice = "ar-EG-SalmaNeural"
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        asyncio.run(_edge_save_async(f"<speak>{text}</speak>", voice, tmp_name))
        with open(tmp_name, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)

# ----------------------------
# Prompt builder
# ----------------------------
def build_prompt(user_input: str) -> str:
    return f"User input: {user_input}\nBrand: {brand}\nPersona: {persona}\nPDF Summary: {st.session_state.pdf_summary}"

# ----------------------------
# Chat UI
# ----------------------------
st.markdown("<h3>💬 Chat</h3>", unsafe_allow_html=True)
render_chat_history()

with st.form("chat_form", clear_on_submit=True):
    user_text = st.text_input("Type your message...", key="user_input")
    submitted = st.form_submit_button("Send")

if submitted and user_text:
    st.session_state.chat_history.append({"role":"user","content":user_text})
    prompt = build_prompt(user_text)
    ai_output = call_groq_with_retry(prompt)
    audio_b64 = synthesize_tts(ai_output)
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"audio":audio_b64})
    render_chat_history()

# ----------------------------
# AI call
# ----------------------------
def call_groq_with_retry(prompt: str, max_retries: int = 3):
    if client is None:
        return "⚠️ AI not configured."
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role":"system","content":"Helpful assistant"},{"role":"user","content":prompt}],
                temperature=0.7
            )
            return resp.choices[0].message.content
        except Exception as e:
            time.sleep(2)
    return "⚠️ AI call failed."

# ----------------------------
# Export & Clear
# ----------------------------
cols = st.columns([1,1])
with cols[0]:
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []
        st.experimental_rerun()
with cols[1]:
    if DOCX_AVAILABLE and st.session_state.chat_history:
        if st.button("📥 Export Chat (.docx)"):

            doc = Document()
            doc.add_heading("Chat History", 0)
            for msg in st.session_state.chat_history:
                role = "User" if msg["role"]=="user" else "AI"
                text_content = re.sub(r'<.*?>', '', msg["content"])
                doc.add_paragraph(f"{role}: {text_content}")
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            doc.save(tmp.name)
            with open(tmp.name, "rb") as f:
                data = f.read()
            st.download_button("⬇️ Download .docx", data=data, file_name="chat_history.docx")
