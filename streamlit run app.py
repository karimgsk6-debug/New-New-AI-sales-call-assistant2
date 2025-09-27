# app.py
import streamlit as st
from PIL import Image, ImageStat
import requests
from io import BytesIO, BytesIO as io_bytes
import groq
from groq import Groq
from datetime import datetime
import PyPDF2
import asyncio
import edge_tts
import base64
import re
import os
import tempfile
import time
from typing import Optional

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", page_icon="💡", layout="wide")

# ----------------------------
# Optional Word download
# ----------------------------
try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# ----------------------------
# GROQ client
# ----------------------------
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

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

# ----------------------------
# Assets & styling
# ----------------------------
BACKGROUND_URL = "https://sdmntprukwest.oaiusercontent.com/files/00000000-abd4-6243-82cf-168367664603/raw?se=2025-09-27T20%3A50%3A12Z&sp=r&sv=2024-08-04&sr=b&scid=ecda9bff-da85-5e32-ac41-b08c14ba28cf&skoid=d9a3f0e9-8380-4267-a144-3f27388a5c5d&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-27T12%3A41%3A14Z&ske=2025-09-28T12%3A41%3A14Z&sks=b&skv=2024-08-04&sig=oXICxZIQ74jEr/fZxSZH/TmBnN8eb/3bsNRGRUHTsf0%3D"
GSK_LOGO_URL = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"

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

# ----------------------------
# CSS Styling
# ----------------------------
CSS = f"""
<style>
.stApp {{
    background: url('{BACKGROUND_URL}') no-repeat top right;
    background-size: cover;
    background-attachment: fixed;
}}

.stSidebar {{
    background-color: #fff;
    padding: 14px;
}}

.stSidebar .stSelectbox, .stSidebar .stMultiselect, .stSidebar .stRadio, .stSidebar .stCheckbox, .stSidebar .stFileUploader {{
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 8px;
    margin-bottom: 12px;
    background-color: #fff;
}}

.title-box {{
    background: rgba(255,255,255,0.96);
    padding: 28px;
    border-radius: 14px;
    text-align: center;
    max-width: 85%;
    margin: 12px auto;
}}

.chat-bubble-user {{
    text-align: right;
    background: rgba(220,248,198,0.95);
    padding: 12px;
    border-radius: 15px 15px 0 15px;
    margin: 6px;
    display: inline-block;
    max-width: 80%;
    word-wrap: break-word;
    color: {text_color};
}}

.chat-bubble-ai {{
    text-align: left;
    background: rgba(240,242,246,0.95);
    padding: 12px;
    border-radius: 15px 15px 15px 0;
    margin: 6px;
    display: inline-block;
    max-width: 80%;
    word-wrap: break-word;
    color: {text_color};
}}

.highlight {{
    font-weight: bold;
    background-color: yellow;
    color: black;
    padding: 2px 4px;
    border-radius: 4px;
}}

@media (max-width: 430px) {{
    .title-box h1 {{ font-size: 24px; }}
    .chat-bubble-user, .chat-bubble-ai {{ max-width: 95%; }}
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------
# Top-right logo + title
# ----------------------------
st.markdown(f'<div style="position:fixed;top:10px;right:16px;z-index:1000;"><img src="{GSK_LOGO_URL}" width="120" /></div>', unsafe_allow_html=True)
st.markdown("""
<div class="title-box">
<h1>💡 AI Sales Call Assistant</h1>
<p>Powered by AI to equip sales reps for smarter HCP conversations</p>
</div>
""", unsafe_allow_html=True)

# ----------------------------
# Language Selector
# ----------------------------
language = st.radio("", options=["English", "العربية"], horizontal=True, label_visibility="collapsed")

# ----------------------------
# Sidebar Filters
# ----------------------------
gsk_brands = {
    "Shingrix": "https://www.shingrix.com/",
    "Trelegy": "https://www.trelegy.com/",
    "Zejula": "https://www.zejula.com/",
}
gsk_brands_images = {
    "Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Trelegy": "https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
    "Zejula": "https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png",
}

race_segments = [
    "R – Reach: Not prescribing yet; doesn't see vaccination responsibility.",
    "A – Acquisition: Prescribes when patient asks; convinced by data.",
    "C – Conversion: Initiates for specific profiles; not across all profiles.",
    "E – Engagement: Proactively prescribes across multiple patient profiles.",
]

doctor_barriers = [
    "HCP does not consider HZ a risk",
    "No time for discussion",
    "Cost concerns",
    "Not convinced of efficacy",
    "Accessibility/Logistics",
    "Patient reluctance",
    "Other clinical doubts",
]

personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]

specialties = ["GP", "Cardiologist", "Dermatologist", "Rheumatologist", "Internal Medicine",
               "Diabetologist", "Endocrinologist", "Pneumologist", "Neurologists"]

with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown('<div style="font-weight:800; margin-bottom:8px;">Filters & Options</div>', unsafe_allow_html=True)
    brand = st.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try:
            resp = requests.get(img_path, timeout=8)
            img = Image.open(BytesIO(resp.content))
            st.image(img, width=200)
        except Exception:
            st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)
    segment = st.selectbox("Select RACE Segment / اختر شريحة RACE", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", options=doctor_barriers, default=[])
    persona = st.selectbox("Select HCP Persona / اختر شخصية الطبيب", options=personas)
    objective = st.selectbox("Select Objective / اختر الهدف", options=["Awareness","Adoption","Retention"])
    specialty = st.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", options=specialties)
    response_length = st.selectbox("Response Length / اختر طول الرد", ["Short", "Medium", "Long"])
    response_tone = st.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])
    interface_mode = st.radio("Interface Mode / اختر واجهة", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# ----------------------------
# PDF Upload & Bullet Summary
# ----------------------------
st.subheader("📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:1000]+"..."
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else ""
        bullets = [line.strip() for line in full_text.splitlines() if line.strip()][:10]
        with st.expander("📑 PDF Summary (Top Points)"):
            st.markdown("<ul>", unsafe_allow_html=True)
            for b in bullets:
                st.markdown(f"<li>{b}</li>", unsafe_allow_html=True)
            st.markdown("</ul>", unsafe_allow_html=True)
    except Exception as e:
        st.error(f"PDF error: {e}")

# ----------------------------
# Chat Interface
# ----------------------------
st.subheader("💬 Chat Interface")
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message... / اكتب رسالتك هنا", key="user_input_box")
    submitted = st.form_submit_button("➤")

# ----------------------------
# TTS
# ----------------------------
def synthesize_tts_base64(text: str, lang: str) -> Optional[str]:
    text = (text or "").strip()
    if not text:
        return None
    clean_text = re.sub(r'([;:{}\[\]\*\^<>@#\$%&\|~_=/\\\+])', '', text)
    clean_text = re.sub(r'\s+', ' ', clean_text)
    voice = "ar-EG-SalmaNeural" if lang == "العربية" else "en-US-JennyNeural"
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        async def _save():
            comm = edge_tts.Communicate(clean_text, voice=voice)
            await comm.save(tmp_name)
        asyncio.run(_save())
        with open(tmp_name, "rb") as f:
            b = f.read()
        return base64.b64encode(b).decode("utf-8")
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)

# ----------------------------
# Handle chat submission
# ----------------------------
APACT_STEPS = ["Acknowledge", "Probing", "Action", "Confirm", "Transition"]
if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})
    prompt = f"""Language: {language}
User input: {user_input}
Brand: {brand}
RACE Segment: {segment}
Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}
HCP Persona: {persona}
Doctor Specialty: {specialty}
Objective: {objective}
PDF Preview: {st.session_state.uploaded_pdf_text or "No PDF uploaded."}
Approved Sales Approaches: Use data-driven evidence, Focus on patient outcomes, Leverage storytelling, Address practical barriers
Sales Call Flow Steps: Prepare → Engage → Create Opportunities → Influence → Drive Impact → Post Call Analysis
Use APACT ({' → '.join(APACT_STEPS)}) technique for objections.
Provide actionable sales-call suggestions and a short 3–6 line script."""
    
    # Mocked AI response (replace with Groq call)
    ai_output = "Here's a sample AI response highlighting APACT steps."
    audio_b64 = synthesize_tts_base64(ai_output, language)
    st.session_state.chat_history.append({"role": "ai", "content": ai_output, "time": datetime.now().strftime("%H:%M"), "audio": audio_b64})

# ----------------------------
# Render chat bubbles
# ----------------------------
for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        st.markdown(f"<div class='chat-bubble-user'>{msg['content']}<br><span style='font-size:10px;color:gray'>{msg['time']}</span></div>", unsafe_allow_html=True)
    else:
        audio_html = f"<br><audio controls style='margin-top:8px;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>" if msg.get("audio") else ""
        st.markdown(f"<div class='chat-bubble-ai'>{msg['content']}<br><span style='font-size:10px;color:gray'>{msg['time']}</span>{audio_html}</div>", unsafe_allow_html=True)
