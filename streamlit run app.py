# app.py
import os
import re
import base64
import asyncio
from io import BytesIO
from datetime import datetime

import streamlit as st
from PIL import Image, ImageStat
import requests
import PyPDF2
import edge_tts

# Groq client
try:
    import groq
    from groq import Groq
    GROQ_API_KEY = "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"
    client = Groq(api_key=GROQ_API_KEY)
except Exception:
    client = None

# Optional docx export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", page_icon="💡", layout="wide")

# ----------------------------
# Session state defaults
# ----------------------------
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state: st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state: st.session_state.pdf_summary = ""
if "language" not in st.session_state: st.session_state.language = "English"

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
    except:
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
  padding:14px;
  border-radius:16px;
  margin:8px 0;
  word-wrap: break-word;
}}
.chat-bubble-user {{ background: #eef9e6; margin-left: auto; border:1px solid #c2e0b0; max-width:40%; }}
.chat-bubble-ai {{ background: #f5f7fa; margin-right: auto; border:1px solid #a0c4ff; max-width:100%; }}
.pdf-summary-inline {{
  margin-top:8px;
  background: #f9f9f9;
  padding:10px;
  border-radius:8px;
  border: 1px solid #eee;
}}
.highlight-step {{ font-weight:700; color:#d35400; }}
.highlight-apact {{ font-weight:700; color:#2980b9; }}
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
  align-items:center;
}}
.bottom-bar input[type="text"] {{ flex:1; padding:10px 12px; border-radius:8px; border:1px solid #ddd; }}
.bottom-bar button {{ min-width:100px; padding:8px 12px; border-radius:8px; background:#ff8c00; color:white; border:none; font-weight:600; cursor:pointer; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
SCROLL_JS = """<script>function scrollChat(){const el=document.querySelector('.chat-container');if(el) el.scrollTop=el.scrollHeight;}setTimeout(scrollChat,200);</script>"""
st.markdown(f'<div style="position:auto; right:30px; top:80px; z-index:1200;"><img src="{GSK_LOGO_URL}" width="140" /></div>', unsafe_allow_html=True)
st.markdown('<div class="title-box"><h1>💡 AI Sales Call Assistant</h1><p>Powered by AI to equip reps for smarter HCP conversations</p></div>', unsafe_allow_html=True)
st.markdown('<p style="text-align:center;font-weight:600;">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Filters & selections sidebar
# ----------------------------
gsk_brands = {"Shingrix": "https://www.shingrix.com/", "Trelegy": "https://www.trelegy.com/", "Zejula": "https://www.zejula.com/"}
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns",
                   "Not convinced of efficacy", "Accessibility/Logistics", "Patient reluctance", "Other clinical doubts"]
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist",
               "Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"]

with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
    segment = st.selectbox("Select RACE Segment / اختر شريحة RACE", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective / اختر الهدف", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", options=specialties)
    persona = st.selectbox("Select HCP Persona / اختر شخصية الطبيب", options=personas)
    response_length = st.selectbox("Response Length / اختر طول الرد", ["Short","Medium","Long"])
    response_tone = st.selectbox("Response Tone / اختر نبرة الرد", ["Formal","Casual","Friendly","Persuasive"])
    tts_lang = st.radio("Voice / الصوت", ["English", "العربية"], index=0)

# ----------------------------
# Sales Call & APACT Steps
# ----------------------------
sales_call_steps = [
    "1-Prepare", "2-Engage", "3-Create opportunities", "4-Impact GSO_good sell out come",
    "5-Influence", "6-Poast call analysis"
]
APACT_STEPS = ["Acknowledge", "Probing", "Confirm", "Action", "Transition to next step"]

# ----------------------------
# PDF upload & bullet-point summary
# ----------------------------
st.markdown("### 📄 Upload Medical Reference PDF (Optional)")
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])

if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text

        if client:
            summary_prompt = f"Summarize the following medical text into concise bullet points, highlighting key points for pharmaceutical sales reps. Bold and highlight GSK sales call steps and APACT steps:\n\n{full_text[:4000]}"
            resp = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role":"system","content":"You are a medical summarizer for sales reps."},
                          {"role":"user","content":summary_prompt}],
                temperature=0.2
            )
            summary = resp.choices[0].message.content.strip()
            # Highlight steps
            for step in sales_call_steps: summary = summary.replace(step, f'<span class="highlight-step">{step}</span>')
            for apact in APACT_STEPS: summary = summary.replace(apact, f'<span class="highlight-apact">{apact}</span>')
            st.session_state.pdf_summary = summary

        if st.session_state.pdf_summary:
            with st.expander("📄 PDF Summary (expand/collapse)", expanded=False):
                st.markdown(f'<div class="pdf-summary-box">{st.session_state.pdf_summary.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

    except Exception as e:
        st.error("PDF error: " + str(e))

# ----------------------------
# TTS helper (humanized)
# ----------------------------
async def speak_text(text: str, lang="en"):
    clean_text = re.sub(r"[^a-zA-Z0-9 .,؟!?]", "", text)
    if not clean_text.strip(): return
    communicate = edge_tts.Communicate(clean_text, voice="en-US-AriaNeural" if lang=="en" else "ar-EG-SalmaNeural")
    await communicate.save("tts_output.mp3")
    os.system("start tts_output.mp3" if os.name=="nt" else "afplay tts_output.mp3")

# ----------------------------
# Render chat & PDF summary
# ----------------------------
def render_chat_history(show_user=True):
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for entry in st.session_state.chat_history:
        role = entry.get("role","user")
        content = entry.get("content","")
        if role=="user" and not show_user: continue
        bubble_class = "chat-bubble-user" if role=="user" else "chat-bubble-ai"
        st.markdown(f'<div class="{bubble_class}">{content.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown(SCROLL_JS, unsafe_allow_html=True)

render_chat_history(show_user=False)

# ----------------------------
# Bottom input bar
# ----------------------------
st.markdown('<div class="bottom-bar">', unsafe_allow_html=True)
col1, col2, col3 = st.columns([6,1,1])
with col1:
    user_input = st.text_input("Type your question...", key="bottom_input")
with col2:
    if st.button("Send"):
        if user_input.strip():
            st.session_state.chat_history.append({"role":"user","content":user_input})
            if client:
                ai_prompt = f"Answer this question for pharmaceutical sales reps: {user_input}\nReference PDF:\n{st.session_state.uploaded_pdf_text}"
                resp = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{"role":"system","content":"You are a helpful pharma sales AI."},
                              {"role":"user","content":ai_prompt}],
                    temperature=0.2
                )
                ai_resp = resp.choices[0].message.content.strip()
                for step in sales_call_steps: ai_resp = ai_resp.replace(step, f'<span class="highlight-step">{step}</span>')
                for apact in APACT_STEPS: ai_resp = ai_resp.replace(apact, f'<span class="highlight-apact">{apact}</span>')
                st.session_state.chat_history.append({"role":"ai","content":ai_resp})
            render_chat_history(show_user=False)
with col3:
    if st.button("Clear Chat"):
        st.session_state.chat_history = []
        render_chat_history(show_user=False)
st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------
# Download AI response as Word
# ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    last_ai = next((c["content"] for c in reversed(st.session_state.chat_history) if c["role"]=="ai"), None)
    if last_ai:
        if st.button("Download AI Response as Word"):
            doc = Document()
            doc.add_paragraph(last_ai)
            doc_name = f"AI_Response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
            doc.save(doc_name)
            with open(doc_name, "rb") as f:
                st.download_button("Download Word", f.read(), file_name=doc_name)
