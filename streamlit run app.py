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
import html

# Groq client
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
# GROQ API Key
# ----------------------------
# <-- Insert your GROQ API Key here -->
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY) if (GROQ_API_KEY and Groq is not None) else None
if client is None:
    st.info("Groq AI client not configured. Set GROQ_API_KEY to enable AI summarization/answers.")

# ----------------------------
# Session defaults
# ----------------------------
for key, default in [("chat_history", []), ("uploaded_pdf_text", ""), ("extracted_medical_ref", ""),
                     ("pdf_summary", ""), ("language", "English"), ("voice_pref", "English Neural")]:
    if key not in st.session_state:
        st.session_state[key] = default

# ----------------------------
# Assets & Styling
# ----------------------------
BACKGROUND_URL = "https://www.shutterstock.com/image-photo/excited-girl-white-shirt-using-260nw-708132598.jpg"
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
# CSS Styling
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
.chat-bubble-user {{ background: #eef9e6; margin-left:auto; padding:12px; border-radius:12px; max-width:86%; word-wrap:break-word; }}
.chat-bubble-ai {{ background: #f5f7fa; margin-right:auto; padding:12px; border-radius:12px; max-width:86%; word-wrap:break-word; }}
.pdf-summary-inline {{ margin-top:8px; background: rgba(245,245,245,0.7); padding:10px; border-radius:8px; border:1px solid #1111; }}
.bottom-bar {{ position: fixed; bottom: 12px; left: 16px; right: 16px; z-index: 1200; background: rgba(255,255,255,0.98); padding:10px; border-radius:12px; display:flex; gap:12px; align-items:center; }}
.bottom-bar input[type="text"] {{ flex:1; padding:10px 12px; border-radius:8px; border:1px solid #ddd; outline:none; }}
.bottom-bar button {{ min-width:110px; padding:8px 12px; border-radius:8px; background:#ff8c00; color:white; border:none; font-weight:600; cursor:pointer; }}
.highlight-step {{ font-weight:700; color:#000; }}
.highlight-figure {{ font-weight:700; color:#d35400; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------
# Top Logo & Title
# ----------------------------
st.markdown(f'<div style="position:auto; top:80px; left:18px; z-index:1200;"><img src="{GSK_LOGO_URL}" width="140" /></div>', unsafe_allow_html=True)
st.markdown('<div style="background: rgba(245,245,245,0.6); padding:22px; border-radius:14px; text-align:center;"><h1>💡 AI Sales Call Assistant</h1><p>Powered by AI to equip sales reps for smarter HCP conversations</p></div>', unsafe_allow_html=True)

# ----------------------------
# Data lists
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
doctor_barriers = ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy","Accessibility/Logistics","Patient reluctance","Other clinical doubts"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
sales_call_flow = ["Prepare the call","Engage","Create opportunities","Impact GSO (Good sell outcome)","Influence","Analyze and post call analysis"]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist","Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"]

# ----------------------------
# Sidebar Filters
# ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown('<div style="font-weight:800; margin-bottom:8px;">Filters & Options</div>', unsafe_allow_html=True)
    brand = st.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try:
            resp = requests.get(img_path, timeout=6)
            img = Image.open(BytesIO(resp.content))
            st.image(img, width=160)
        except Exception:
            st.image("https://via.placeholder.com/160x90.png?text=No+Image", width=160)
    segment = st.selectbox("Select RACE Segment / اختر شريحة RACE", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective / اختر الهدف", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", options=specialties)
    persona = st.selectbox("Select HCP Persona / اختر شخصية الطبيب", options=personas)
    response_length = st.selectbox("Response Length / اختر طول الرد", ["Short", "Medium", "Long"])
    response_tone = st.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])
    st.session_state.language = st.radio("Language / اختر اللغة", options=["English", "العربية"], index=0, horizontal=True)
    st.session_state.voice_pref = st.selectbox("Voice preference", ["English Neural", "Arabic Neural", "Default"])

# ----------------------------
# PDF Upload
# ----------------------------
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:2000] + "..." if len(full_text) > 2000 else full_text
        # extract references
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"
        st.success("✅ PDF processed (extracted text and references).")
    except Exception as e:
        st.error("PDF error: " + str(e))

# ----------------------------
# Helper Functions
# ----------------------------
def highlight_content_for_display(content: str) -> str:
    for step in sales_call_flow + APACT_STEPS:
        content = re.sub(rf"\b{re.escape(step)}\b", f"<span class='highlight-step'>{step}</span>", content)
    for fig in re.findall(r"\d+\.?\d*%", content):
        content = content.replace(fig, f"<span class='highlight-figure'>{fig}</span>")
    return content

def build_ai_bubble_content(ai_text: str, inject_pdf_lines: int = 6) -> str:
    text = highlight_content_for_display(ai_text.replace("\n", "<br>"))
    pdf_html = ""
    if st.session_state.pdf_summary:
        pdf_lines = [ln.strip() for ln in st.session_state.pdf_summary.splitlines() if ln.strip()]
        sample = pdf_lines[:inject_pdf_lines]
        if sample:
            pdf_html = "<div class='pdf-summary-inline'>" + "<br>".join([f"- {ln}" for ln in sample]) + ( "<br>..." if len(pdf_lines) > inject_pdf_lines else "" ) + "</div>"
    return f"{text}{pdf_html}"

def render_chat_history():
    html_out = ""
    for msg in st.session_state.chat_history:
        content = html.escape(msg["content"])
        if msg["role"] == "user":
            html_out += f"<div class='chat-bubble-user'>{content}</div>"
        else:
            ai_bubble = build_ai_bubble_content(msg["content"])
            audio_html = ""
            if msg.get("audio"):
                audio_html = f"<br><audio controls style='margin-top:8px;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
            html_out += f"<div class='chat-bubble-ai'>{ai_bubble}{audio_html}</div>"
    st.markdown(html_out, unsafe_allow_html=True)
