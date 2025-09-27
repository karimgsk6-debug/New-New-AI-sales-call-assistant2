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

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", page_icon="💡", layout="wide")

# ----------------------------
# Optional Word download (docx)
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
BACKGROUND_URL = ("https://sdmntprsouthcentralus.oaiusercontent.com/files/00000000-a9b4-61f7-b2cf-05a782087038/raw?se=2025-09-27T15%3A35%3A52Z&sp=r&sv=2024-08-04&sr=b&scid=134c6041-1913-5d1b-9974-a2aba92201a7&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-27T05%3A09%3A07Z&ske=2025-09-28T05%3A09%3A07Z&sks=b&skv=2024-08-04&sig=7aQFm5RhZ9epNykQFKn7PqPerMyorga4a47YrmyCvo8%3D")
GSK_LOGO_URL = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
GSK_ORANGE = "#FF7F00"

def get_brightness(url):
    try:
        r = requests.get(url, timeout=8)
        img = Image.open(BytesIO(r.content)).convert("L")
        stat = ImageStat.Stat(img)
        return stat.mean[0]
    except Exception:
        return 255

brightness = get_brightness(BACKGROUND_URL)
text_color = "black" if brightness > 130 else "white"
button_bg = "#FFA500" if brightness > 130 else "#FF8C00"

# ----------------------------
# CSS
# ----------------------------
CSS = f"""
<style>
/* Main background */
.stApp {{
    background: url('{BACKGROUND_URL}') no-repeat top right;
    background-size: auto 200%;
    background-attachment: fixed;
    transition: background-size 0.3s ease;
}}
[data-testid="stSidebar"][aria-expanded="true"] ~ .stApp {{
    background-size: auto 100%;
}}
[data-testid="stSidebar"][aria-expanded="false"] ~ .stApp {{
    background-size: auto 100%;
}}

/* Sidebar background White */
[data-testid="stSidebar"] {{
    background-color: {White};
    color:white;
}}

/* GSK logo */
.gsk-logo {{
    position: fixed;
    top: 60px;
    right: 16px;
    z-index: 1000;
}}

/* Title box */
.title-box {{
    background: rgba(255,255,255,0.92);
    padding: 35px;
    border-radius: 18px;
    text-align: center;
    max-width: 80%;
    margin: 12px auto;
}}
.title-box h1 {{
    margin: 0;
    font-size: 42px;
    font-weight: 800;
}}
.title-box p {{
    margin: 8px 0 0 0;
    font-size: 20px;
    font-weight: 500;
}}
.disclaimer {{
    text-align: center;
    padding: 12px;
    font-size: 15px;
    font-weight: 500;
    margin-bottom: 10px;
}}

/* Chat bubbles */
.chat-bubble-user {{
    text-align: right;
    background: rgba(220,248,198,0.95);
    padding: 12px;
    border-radius: 15px 15px 0px 15px;
    margin: 6px;
    display: inline-block;
    max-width: 80%;
    color: {text_color};
}}
.chat-bubble-ai {{
    text-align: left;
    background: rgba(240,242,246,0.95);
    padding: 12px;
    border-radius: 15px 15px 15px 0px;
    margin: 6px;
    display: inline-block;
    max-width: 80%;
    color: {text_color};
}}
.highlight {{
    font-weight: bold;
    background-color: yellow;
    color: black;
    padding: 2px 4px;
    border-radius: 4px;
}}
.chat-input-container {{
    display:flex;
    margin-top:10px;
    width: 100%;
}}
.chat-input-container input {{
    flex:1;
    padding:12px;
    border-radius:20px;
    border:none;
    outline:none;
    backdrop-filter: blur(8px);
    background-color: rgba(255,255,255,0.4);
    color: {text_color};
}}
.chat-input-container button {{
    margin-left:5px;
    border:none;
    border-radius:50%;
    width:45px;
    height:45px;
    cursor:pointer;
    font-weight:bold;
    background-color: {button_bg};
    color: white;
}}
.bottom-bar {{
    position: fixed;
    bottom: 10px;
    width: 95%;
    left: 2.5%;
    z-index: 1000;
    display:flex;
    justify-content: space-between;
    align-items: center;
}}
.sidebar-bold {{
    font-weight:700;
    margin-bottom:8px;
    color:white;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------
# Header
# ----------------------------
st.markdown(f"""<div class="gsk-logo"><img src="{GSK_LOGO_URL}" width="140"></div>""", unsafe_allow_html=True)
st.markdown("""
<div class="title-box">
  <h1>💡 AI Sales Call Assistant</h1>
  <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
</div>
""", unsafe_allow_html=True)
st.markdown('<p class="disclaimer">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Language selector
# ----------------------------
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"], horizontal=True)

# ----------------------------
# Data definitions
# ----------------------------
gsk_brands = {
    "Shingrix": "https://www.shingrix.com/",
    "Trelegy": "https://www.trelegy.com/",
    "Zejula": "https://www.zejula.com/"
}
gsk_brands_images = {
    "Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Trelegy": "https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
    "Zejula": "https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png"
}
race_segments = [
    "R – Reach: Not prescribing yet; doesn't see vaccination responsibility.",
    "A – Acquisition: Prescribes when patient asks; convinced by data.",
    "C – Conversion: Initiates for specific profiles; not across all profiles.",
    "E – Engagement: Proactively prescribes across multiple patient profiles."
]
doctor_barriers = [
    "HCP does not consider HZ a risk",
    "No time for discussion",
    "Cost concerns",
    "Not convinced of efficacy",
    "Accessibility/Logistics",
    "Patient reluctance",
    "Other clinical doubts"
]
personas = [
    "Uncommitted Vaccinator",
    "Reluctant Efficiency",
    "Patient Influenced",
    "Committed Vaccinator"
]
gsk_approaches = [
    "Use data-driven evidence (local + global studies)",
    "Focus on patient outcomes & quality of life",
    "Leverage brief storytelling and peer endorsement",
    "Address practical barriers (access, scheduling, cost solutions)"
]
sales_call_flow = [
    "Prepare: Data & patient profiles",
    "Engage: Opening question & rapport",
    "Create Opportunities: Identify eligible patients",
    "Influence: Present tailored evidence & handle objections",
    "Drive Impact: Secure next steps (prescription/scheduling)",
    "Post Call Analysis: Document & follow up"
]
APACT_STEPS = ["Acknowledge", "Probing", "Action", "Confirm", "Transition"]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]

# ----------------------------
# Sidebar: Brand + filters
# ----------------------------
with st.sidebar:
    st.markdown('<div class="sidebar-bold">Brand & Filters</div>', unsafe_allow_html=True)
    brand = st.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try:
            resp = requests.get(img_path, timeout=8)
            img = Image.open(BytesIO(resp.content))
            st.image(img, width=200)
        except:
            st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)
    segment = st.selectbox("RACE Segment", options=race_segments)
    barrier = st.multiselect("Doctor Barrier", options=doctor_barriers, default=[])
    objective = st.selectbox("Objective", options=objectives)
    specialty = st.selectbox("Doctor Specialty", options=specialties)
    persona = st.selectbox("HCP Persona", options=personas)
    response_length = st.selectbox("Response Length", ["Short", "Medium", "Long"])
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])
    interface_mode = st.radio("Interface Mode", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# ----------------------------
# Main Interface: PDF Upload above chat
# ----------------------------
st.subheader("📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = ""
        for p in reader.pages:
            full_text += (p.extract_text() or "") + "\n"
        st.session_state.uploaded_pdf_text = full_text[:1000] + "..."
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else ""
        st.success("✅ PDF processed")
    except Exception as e:
        st.error(f"PDF error: {e}")
st.markdown("### PDF Preview / Summary")
st.write(st.session_state.uploaded_pdf_text)

# ----------------------------
# Chat interface placeholder
# ----------------------------
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()

def display_chat():
    html = ""
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n", "<br>")
        for step in APACT_STEPS:
            content = content.replace(step, f"<span class='highlight'>{step}</span>")
        ts = msg.get("time", "")
        audio_html = ""
        if msg.get("audio"):
            audio_html = f"<br><audio controls style='margin-top:8px;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
        if msg["role"] == "user":
            html += f"<div class='chat-bubble-user'>{content}<br><span style='font-size:10px;color:gray'>{ts}</span></div>"
        else:
            html += f"<div class='chat-bubble-ai'>{content}<br><span style='font-size:10px;color:gray'>{ts}</span>{audio_html}</div>"
    chat_placeholder.markdown(html, unsafe_allow_html=True)

display_chat()

# ----------------------------
# Bottom bar: prompt input, clear, download
# ----------------------------
with st.container():
    st.markdown('<div class="bottom-bar">', unsafe_allow_html=True)
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("Type your message here...", key="user_input_box")
        submitted = st.form_submit_button("➤")
    col1, col2 = st.columns([1,1])
    with col1:
        clear_clicked = st.button("🗑️ Clear Chat")
        if clear_clicked:
            st.session_state.chat_history = []
            st.session_state.uploaded_pdf_text = ""
            st.session_state.extracted_medical_ref = ""
            st.session_state.pdf_summary = ""
            st.experimental_rerun()
    with col2:
        if DOCX_AVAILABLE and st.session_state.chat_history:
            latest_ai = [m["content"] for m in st.session_state.chat_history if m["role"]=="ai"]
            if latest_ai:
                doc = Document()
                doc.add_heading("AI Sales Call Response", 0)
                doc.add_paragraph("\n\n".join(latest_ai))
                tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
                doc.save(tmp_file.name)
                with open(tmp_file.name, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                    st.markdown(f'<a href="data:application/octet-stream;base64,{b64}" download="AI_Response.docx">💾 Download Word</a>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
