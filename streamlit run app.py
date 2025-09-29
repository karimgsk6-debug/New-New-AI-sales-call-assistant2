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
if not GROQ_API_KEY:
    st.warning("GROQ_API_KEY not found in environment. Set GROQ_API_KEY in env or Streamlit Secrets.")
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
  background-attachment: fixed;
}}
.stSidebar {{
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
  position: flixed;
  top: 80px;
  left: 12px;
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
  border-radius: 999px;
  border: 1px solid #ddd;
  outline: none;
}}
.bottom-input button {{
  width:50px;
  height:50px;
  border-radius:50%;
  border:none;
  background:#10a37f;
  color:white;
  font-size:24px;
  display:flex;
  align-items:center;
  justify-content:center;
}}
@media (max-width: 430px) {{
  .title-box h1 {{ font-size:26px; }}
  .gsk-logo img {{ width: 90px; }}
  .bottom-input {{ left:8px; right:8px; bottom:8px; padding:8px; }}
}}
.highlight-step {{ font-weight:700; color:#000; }}
.highlight-figure {{ font-weight:700; color:#d35400; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

SCROLL_JS = """
<script>
function scrollChat() {
  const el = document.getElementById('chat-area');
  if (el) el.scrollTop = el.scrollHeight;
}
setTimeout(scrollChat, 200);
</script>
"""
st.markdown(f'<div class="gsk-logo"><img src="{GSK_LOGO_URL}" width="140"></div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="title-box">
      <h1>💡 AI Sales Call Assistant</h1>
      <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown('<p style="text-align:center;font-weight:600;">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

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
sales_call_flow = ["Prepare", "Engage", "Create opportunity", "Influence", "Impact GSO", "Analyze / Post call analysis"]
APACT_STEPS = ["Acknowledge", "Probing", "Action", "Confirm", "Transition"]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = [
    "GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist",
    "Rheumatologist", "Internal Medicine", "Diabetologist", "Neurologist", "Pneumologist"
]

# ----------------------------
# Sidebar filters
# ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown('<div style="font-weight:800; margin-bottom:8px;">Filters & Options</div>', unsafe_allow_html=True)
    brand = st.selectbox("Select Brand", options=list(gsk_brands.keys()))
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try:
            resp = requests.get(img_path, timeout=6)
            img = Image.open(BytesIO(resp.content))
            st.image(img, width=180)
        except Exception:
            st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=180)
    segment = st.selectbox("Select RACE Segment", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty", options=specialties)
    persona = st.selectbox("Select HCP Persona", options=personas)
    response_length = st.selectbox("Response Length", ["Short", "Medium", "Long"])
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])
    interface_mode = st.radio("Interface Mode", ["Chatbot", "Card Dashboard", "Flow Visualization"])
    st.session_state.language = st.selectbox("Language", ["English", "العربية", "French"])

# ----------------------------
# PDF upload & summarization
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
# Chat area
# ----------------------------
st.markdown("<h3>💬 Chat</h3>", unsafe_allow_html=True)
st.markdown('<div id="chat-area" style="height:56vh; overflow:auto; padding:12px; border-radius:8px; background: rgba(255,255,255,0.6);">', unsafe_allow_html=True)

# Render previous messages
for msg in st.session_state.chat_history:
    cls = "chat-bubble-user" if msg["sender"]=="user" else "chat-bubble-ai"
    st.markdown(f'<div class="{cls}">{msg["content"]}</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
st.markdown(SCROLL_JS, unsafe_allow_html=True)

# ----------------------------
# Bottom input & send button
# ----------------------------
def send_message():
    user_input = st.session_state.user_input.strip()
    if not user_input:
        return
    # Append user
    st.session_state.chat_history.append({"sender":"user","content":user_input})
    st.session_state.user_input = ""
    # Dummy AI response (replace with Groq API call + TTS)
    ai_reply = f"🤖 [AI Response]: You said '{user_input}' for brand {brand} and specialty {specialty}."
    st.session_state.chat_history.append({"sender":"ai","content":ai_reply})
    st.experimental_rerun()

st.text_input("Type your message...", key="user_input", on_change=send_message)
st.markdown("""
<div class="bottom-input">
  <input type="text" id="user_input_field" placeholder="Type your message..."/>
  <button onclick="document.getElementById('user_input_field').dispatchEvent(new KeyboardEvent('keydown', {'key':'Enter'}));">➤</button>
</div>
""", unsafe_allow_html=True)

# ----------------------------
# Clear history & Download
# ----------------------------
col1, col2 = st.columns(2)
with col1:
    if st.button("🧹 Clear History"):
        st.session_state.chat_history = []
        st.experimental_rerun()
with col2:
    if DOCX_AVAILABLE and st.button("📥 Download Chat as Word"):
        doc = Document()
        for msg in st.session_state.chat_history:
            doc.add_paragraph(f"{msg['sender'].upper()}: {msg['content']}")
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            st.download_button("Download", f, file_name="chat.docx")
