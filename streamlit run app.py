# app.py
import os
import re
import time
import base64
import tempfile
import asyncio
from typing import Optional
from datetime import datetime
from io import BytesIO, BytesIO as io_bytes

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
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
if not GROQ_API_KEY:
    st.warning("GROQ_API_KEY not found in environment. Set GROQ_API_KEY in env or Streamlit Secrets.")

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
    st.session_state.language = "English"  # default

# ----------------------------
# Assets
# ----------------------------
BACKGROUND_URL = (
    "https://sdmntprpolandcentral.oaiusercontent.com/files/00000000-3084-620a-86c7-d2b56a91e7ce/raw?se=2025-09-29T10%3A48%3A44Z&sp=r&sv=2024-08-04&sr=b&scid=493e9f02-6d12-5738-8854-4f71fad23f4d&skoid=82a3371f-2f6c-4f81-8a78-2701b362559b&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-29T04%3A09%3A33Z&ske=2025-09-30T04%3A09%3A33Z&sks=b&skv=2024-08-04&sig=3r/IAqgZzWnGJMc9bLlu7lFL9W%2BEQDiv8JDybU7y71w%3D"
)
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

# ----------------------------
# CSS: dynamic background & chat styling
# ----------------------------
CSS = f"""
<style>
:root {{
  --sidebar-width: 300px;
}}
.stApp {{
  background: url('{BACKGROUND_URL}') no-repeat top right;
  background-size: calc(100% - var(--sidebar-width)) auto;
  min-height: 100vh;
  transition: background-size 0.3s ease;
}}
.stSidebar {{
  width: var(--sidebar-width) !important;
  transition: width 0.3s ease;
  background-color: #dddd;
  padding: 14px;
}}
.stSidebar .stSelectbox, .stSidebar .stMultiselect, .stSidebar .stRadio, .stSidebar .stCheckbox, .stSidebar .stFileUploader {{
  border: 1px solid #ddd;
  border-radius: 10px;
  padding: 8px;
  margin-bottom: 12px;
  background-color: #fff;
}}
.gsk-logo {{
  position: absolute;
  top: 80px;
  left: 16px;
  z-index: 1200;
}}
.title-box {{
  background: rgba(255,255,255,0.6);
  padding: 28px;
  border-radius: 14px;
  text-align: center;
  max-width: 85%;
  margin: 12px auto;
}}
.title-box h1 {{ margin: 0; font-size: 38px; font-weight: 800; }}
.title-box p {{ margin: 8px 0 0 0; font-size: 18px; font-weight: 500; }}
.pdf-summary-box {{
  background: rgba(255,255,255,0.6);
  padding: 16px;
  border-radius: 12px;
  margin-bottom: 12px;
}}
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
.pdf-summary-inline {{
  margin-top:8px;
  background: rgba(255,255,255,0.6);
  padding:10px;
  border-radius:10px;
}}
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
  box-shadow: 0 6px 18px rgba(0,0,0,0.08);
}}
.bottom-input input[type="text"] {{
  width: 100%;
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid #ddd;
  outline: none;
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
@media (max-width: 430px) {{
  .title-box h1 {{ font-size:26px; }}
  .gsk-logo img {{ width: 90px; }}
  .bottom-input {{ left:8px; right:8px; bottom:8px; padding:8px; }}
}}
.highlight-step {{ font-weight:700; color:#000; }}
.highlight-figure {{ font-weight:700; color:#d35400; }}
</style>

<script>
// Dynamic background resizing based on sidebar width
const observer = new ResizeObserver(entries => {{
  for (let entry of entries) {{
    const width = entry.contentRect.width;
    document.documentElement.style.setProperty('--sidebar-width', width + 'px');
  }}
}});
const sidebar = document.querySelector('.css-1d391kg');
if (sidebar) observer.observe(sidebar);
</script>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------
# Logo and Title
# ----------------------------
st.markdown(f'<div class="gsk-logo"><img src="{GSK_LOGO_URL}" width="140"></div>', unsafe_allow_html=True)
st.markdown("""
<div class="title-box">
  <h1>💡 AI Sales Call Assistant</h1>
  <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
</div>
""", unsafe_allow_html=True)
st.markdown('<p style="text-align:center;font-weight:600;">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Sidebar filters
# ----------------------------
gsk_brands = {
    "Shingrix": "https://www.shingrix.com/",
    "Trelegy": "https://www.trelegy.com/",
    "Zejula": "https://www.zejula.com/"
}
gsk_brands_images = {
    "Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Trelegy": "https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
    "Zejula": "https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png",
}
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = [
    "HCP does not consider HZ a risk",
    "No time for discussion",
    "Cost concerns",
    "Not convinced of efficacy",
    "Accessibility/Logistics",
    "Patient reluctance",
    "Other clinical doubts"
]
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = [
    "GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist",
    "Rheumatologist", "Internal Medicine", "Diabetologist", "Neurologist", "Pneumologist"
]

with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown('<div style="font-weight:800; margin-bottom:8px;">Filters & Options</div>', unsafe_allow_html=True)
    brand = st.selectbox("Select Brand", options=list(gsk_brands.keys()))
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try:
            resp = requests.get(img_path, timeout=6)
            img = Image.open(BytesIO(resp.content))
            st.image(img, width=180)
        except:
            st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=180)
    segment = st.selectbox("Select RACE Segment", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty", options=specialties)
    persona = st.selectbox("Select HCP Persona", options=personas)
    response_length = st.selectbox("Response Length", ["Short", "Medium", "Long"])
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])
    interface_mode = st.radio("Interface Mode", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# ----------------------------
# PDF Upload
# ----------------------------
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:2000] + "..." if len(full_text) > 2000 else full_text
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"
        st.success("✅ PDF processed")
    except Exception as e:
        st.error("PDF error: " + str(e))

# ----------------------------
# --- MISSING FUNCTIONS FILLED ---
# ----------------------------

def build_prompt(user_input: str) -> str:
    pdf_ref = st.session_state.extracted_medical_ref
    pdf_text = st.session_state.uploaded_pdf_text
    prompt = f"""
You are an AI sales assistant. Provide a sales call response for the user input.
Brand: {brand}, RACE Segment: {segment}, Objective: {objective}, Specialty: {specialty}, Persona: {persona}
Doctor barriers: {', '.join(barrier)}
Response tone: {response_tone}, Response length: {response_length}
PDF References: {pdf_ref}
PDF Text Summary: {pdf_text}
User query: {user_input}
Highlight APACT steps and key figures using <span class='highlight-step'> and <span class='highlight-figure'> tags.
"""
    return prompt

def call_groq_with_retry(prompt: str, max_retries=3) -> str:
    if not client:
        return "GROQ client not initialized."
    retries = 0
    while retries < max_retries:
        try:
            resp = client.query(prompt, max_output_tokens=700)
            return resp
        except Exception as e:
            retries += 1
            time.sleep(1)
    return "AI call failed after retries."

def build_ai_bubble_content(user_input: str) -> str:
    prompt = build_prompt(user_input)
    ai_resp = call_groq_with_retry(prompt)
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    st.session_state.chat_history.append({"role": "ai", "content": ai_resp})
    return ai_resp

def render_chat_history():
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-ai">{msg["content"]}</div>', unsafe_allow_html=True)

async def synthesize_tts_base64(text: str, voice: str = "en-US-JennyNeural") -> str:
    with tempfile.NamedTemporaryFile(delete=True, suffix=".mp3") as tmpfile:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(tmpfile.name)
        tmpfile.seek(0)
        audio_bytes = tmpfile.read()
        return base64.b64encode(audio_bytes).decode("utf-8")

# ----------------------------
# Chat input
# ----------------------------
user_input = st.text_input("Type your question here...")
if st.button("Send") and user_input:
    build_ai_bubble_content(user_input)
render_chat_history()

# ----------------------------
# Clear chat + download Word
# ----------------------------
cols = st.columns([1, 1])
with cols[0]:
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []
        st.session_state.uploaded_pdf_text = ""
        st.session_state.extracted_medical_ref = ""
        st.session_state.pdf_summary = ""
        st.experimental_rerun()
with cols[1]:
    if DOCX_AVAILABLE and st.session_state.chat_history:
        latest_ai = [m["content"] for m in st.session_state.chat_history if m["role"] == "ai"]
        if latest_ai:
            doc = Document()
            doc.add_heading("AI Sales Call Responses", 0)
            for idx, txt in enumerate(latest_ai, 1):
                doc.add_heading(f"Response {idx}", level=1)
                doc.add_paragraph(txt)
            word_buffer = io_bytes()
            doc.save(word_buffer)
            st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Responses.docx")

# ----------------------------
# Brand leaflet link
# ----------------------------
st.markdown(f"[📄 Brand Leaflet - {brand}]({gsk_brands[brand]})")
