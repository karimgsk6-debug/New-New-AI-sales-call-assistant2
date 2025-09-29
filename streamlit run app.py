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
# Groq API key
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

# ----------------------------
# Assets & styling
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

CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-attachment: fixed;
  background-size: auto 150%;
  transition: background-size 0.18s ease;
}}
[data-testid="stSidebar"] > div:first-child {{
  background: #ffffff;
  padding: 10px;
  border-left: 0;
}}
[data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stMultiselect,
[data-testid="stSidebar"] .stRadio, [data-testid="stSidebar"] .stCheckbox,
[data-testid="stSidebar"] .stFileUploader {{
  border: 1px solid #e6e6e6;
  border-radius: 10px;
  padding: 8px;
  margin-bottom: 10px;
  background-color: #dddd;
}}
.title-box {{
  background: rgba(240,240,240,0.6);
  padding: 20px;
  border-radius: 14px;
  text-align: center;
  max-width: 75%;
  margin: 12px auto;
}}
.title-box h1 {{ margin:0; font-size:36px; font-weight:800; color:#000; }}
.title-box p {{ margin:6px 0 0 0; font-size:20px; color:#000; }}
.pdf-summary-box {{
  background: #f9f9f9;
  padding: 14px;
  border-radius: 12px;
  margin-bottom: 12px;
  border: 1px solid #eee;
}}
.chat-container {{
  height: 56vh;
  overflow:auto;
  padding:12px;
  border-radius:10px;
  background: rgba(255,255,255,0.8);
}}
.chat-bubble-user, .chat-bubble-ai {{
  display:block;
  padding:12px;
  border-radius:12px;
  margin:8px 0;
  max-width: 90%;
  word-wrap: break-word;
  color: black;
}}
.chat-bubble-user {{ background: #eef9e6; margin-left: auto; }}
.chat-bubble-ai {{ background: #f5f7fa; margin-right: auto; }}
.pdf-summary-inline {{
  margin-top:8px;
  background: #f9f9f9;
  padding:10px;
  border-radius:8px;
  border: 1px solid #eee;
}}
.bottom-bar {{
  position: fixed;
  bottom: 12px;
  left: 16px;
  right: 16px;
  z-index: 1200;
  background: rgba(255,255,255,0.98);
  padding:10px;
  border-radius:10px;
  box-shadow: 0 6px 20px rgba(0,0,0,0.06);
  display:flex;
  gap:12px;
  align-items:center;
}}
.bottom-bar input[type="text"] {{
  flex:1;
  padding:10px 12px;
  border-radius:8px;
  border:1px solid #ddd;
  outline:none;
}}
.bottom-bar button {{
  min-width:100px;
  padding:8px 12px;
  border-radius:8px;
  background:#ff8c00;
  color:white;
  border:none;
  font-weight:600;
  cursor:pointer;
}}
@media (max-width: 430px) {{
  .title-box h1 {{ font-size:24px; }}
  .chat-container {{ height:48vh; }}
  .bottom-bar {{ left:8px; right:8px; bottom:8px; padding:8px; }}
}}
.highlight-step {{ font-weight:700; color:#000; }}
.highlight-figure {{ font-weight:700; color:#d35400; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
SCROLL_JS = """<script>function scrollChat(){const el=document.querySelector('.chat-container');if(el) el.scrollTop=el.scrollHeight;}setTimeout(scrollChat,200);</script>"""

st.markdown(f'<div style="position:auto; right:30px; top:80px; z-index:1200;"><img src="{GSK_LOGO_URL}" width="140" /></div>', unsafe_allow_html=True)
st.markdown('<div class="title-box"><h1>💡 AI Sales Call Assistant</h1><p>Powered by AI to equip reps for smarter HCP conversations</p></div>', unsafe_allow_html=True)
st.markdown('<p style="text-align:center;font-weight:600;">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Sidebar: GSK filters
# ----------------------------
gsk_brands = {"Shingrix": "https://www.shingrix.com/", "Trelegy": "https://www.trelegy.com/", "Zejula": "https://www.zejula.com/"}
gsk_brands_images = {
    "Shingrix":"https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Trelegy":"https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
    "Zejula":"https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png"
}
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = [
    "HCP does not consider HZ a risk", "No time for discussion", "Cost concerns",
    "Not convinced of efficacy", "Accessibility/Logistics", "Patient reluctance",
    "Other clinical doubts"
]
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
sales_call_flow = ["Prepare the call","Engage","Create opportunities","Impact GSO","Influence","Analyze and post call analysis"]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist",
               "Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"]

with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try:
            resp = requests.get(img_path, timeout=6)
            img = Image.open(BytesIO(resp.content))
            st.image(img, width=180)
        except:
            st.image("https://via.placeholder.com/180x90.png?text=No+Image", width=180)
    segment = st.selectbox("Select RACE Segment / اختر شريحة RACE", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective / اختر الهدف", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", options=specialties)
    persona = st.selectbox("Select HCP Persona / اختر شخصية الطبيب", options=personas)
    response_length = st.selectbox("Response Length / اختر طول الرد", ["Short","Medium","Long"])
    response_tone = st.selectbox("Response Tone / اختر نبرة الرد", ["Formal","Casual","Friendly","Persuasive"])
    interface_mode = st.radio("Interface Mode / اختر واجهة", ["Chatbot","Card Dashboard","Flow Visualization"])
    tts_lang = st.radio("Voice / الصوت", ["English", "العربية"], index=0)

# ----------------------------
# PDF upload & summarization
# ----------------------------
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:2000] + "..." if len(full_text) > 2000 else full_text

        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"
        st.success("✅ PDF processed")

        # Chunk summarization
        chunk_size = 2000
        chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        summaries = []
        if client is None:
            st.warning("Groq client not configured: PDF auto-summarize unavailable. Set GROQ_API_KEY.")
            st.session_state.pdf_summary = ""
        else:
            for i, chunk in enumerate(chunks):
                summary_prompt = "Concise medical summary for sales reps. Bullet points only.\n\n" + chunk[:2000]
                try:
                    resp = client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        messages=[{"role":"system","content":"You are a concise medical summarizer."},
                                  {"role":"user","content":summary_prompt}],
                        temperature=0.2
                    )
                    summaries.append(resp.choices[0].message.content)
                except Exception as e:
                    err_msg = str(e).lower()
                    if "rate_limit" in err_msg or "429" in err_msg:
                        st.warning(f"Chunk {i+1} skipped due to rate limit.")
                        continue
                    else:
                        st.warning(f"Chunk {i+1} summarization error: {e}")
            st.session_state.pdf_summary = "\n".join(summaries).strip()

        # Show summary in off-white bubble
        if st.session_state.pdf_summary:
            st.markdown(f'<div class="pdf-summary-box">{st.session_state.pdf_summary.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
        if st.session_state.extracted_medical_ref:
            st.info(f"📚 Extracted references: {st.session_state.extracted_medical_ref}")

    except Exception as e:
        st.error("PDF error: " + str(e))

# ----------------------------
# TTS helper
# ----------------------------
async def speak_text(text: str, lang="en"):
    clean_text = re.sub(r"[^a-zA-Z0-9 .,؟!?]", "", text)
    if not clean_text.strip():
        return
    communicate = edge_tts.Communicate(clean_text, voice="en-US-AriaNeural" if lang=="en" else "ar-EG-SalmaNeural")
    await communicate.save("tts_output.mp3")
    os.system("start tts_output.mp3" if os.name=="nt" else "afplay tts_output.mp3")

# ----------------------------
# Render chat & PDF summaries
# ----------------------------
def render_chat_history():
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for entry in st.session_state.chat_history:
        role = entry.get("role","user")
        content = entry.get("content","")
        bubble_class = "chat-bubble-user" if role=="user" else "chat-bubble-ai"
        st.markdown(f'<div class="{bubble_class}">{content.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
    if st.session_state.pdf_summary:
        st.markdown(f'<div class="pdf-summary-inline">{st.session_state.pdf_summary.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown(SCROLL_JS, unsafe_allow_html=True)

render_chat_history()

# ----------------------------
# Bottom input bar
# ----------------------------
st.markdown('<div class="bottom-bar">', unsafe_allow_html=True)
user_input = st.text_input("Type your question...", key="bottom_input")
if st.button("Send"):
    if user_input.strip():
        st.session_state.chat_history.append({"role":"user","content":user_input})
        render_chat_history()
st.markdown('</div>', unsafe_allow_html=True)
