# app.py
import os
import re
import asyncio
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
except Exception:
    Groq = None

# ----------------------------
# Groq API key directly in code
# ----------------------------
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY) if Groq is not None else None

# ----------------------------
# Session state defaults
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "language" not in st.session_state:
    st.session_state.language = "English"

# ----------------------------
# Assets & styling
# ----------------------------
BACKGROUND_URL = "https://drive.google.com/file/d/1WlvNx4MqufxuGUw9ilLxGJLsuozbX17b/view"
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

# Updated CSS for larger bubbles and highlighted bold steps
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
.chat-container {{
  height: 60vh;
  overflow:auto;
  padding:16px;
  border-radius:12px;
  background: rgba(255,255,255,0.85);
}}
.chat-bubble-user, .chat-bubble-ai {{
  display:block;
  padding:16px 20px;
  border-radius:16px;
  margin:10px 0;
  max-width: 80%;
  word-wrap: break-word;
  font-size:16px;
}}
.chat-bubble-user {{
  background: #e0f7e9;
  margin-left: auto;
  border: 2px solid #a8d5ba;
}}
.chat-bubble-ai {{
  background: #f0f4ff;
  margin-right: auto;
  border: 2px solid #90b5ff;
}}
.pdf-summary-box {{
  background: #f9f9f9;
  padding: 14px;
  border-radius: 12px;
  margin-bottom: 12px;
  border: 1px solid #eee;
}}
.pdf-summary-inline {{
  margin-top:8px;
  background: #f9f9f9;
  padding:12px;
  border-radius:10px;
  border: 1px solid #ddd;
}}
.bottom-bar {{
  position: fixed;
  bottom: 12px;
  left: 16px;
  right: 16px;
  z-index: 1200;
  background: rgba(255,255,255,0.98);
  padding:12px;
  border-radius:12px;
  box-shadow: 0 6px 20px rgba(0,0,0,0.06);
  display:flex;
  gap:12px;
  align-items:center;
}}
.bottom-bar input[type="text"] {{
  flex:1;
  padding:12px 14px;
  border-radius:10px;
  border:1px solid #ddd;
  outline:none;
  font-size:16px;
}}
.bottom-bar button {{
  min-width:100px;
  padding:10px 14px;
  border-radius:10px;
  background:#ff8c00;
  color:white;
  border:none;
  font-weight:600;
  cursor:pointer;
  font-size:16px;
}}
.highlight-step {{ font-weight:700; color:#d35400; }}
.highlight-apact {{ font-weight:700; color:#2c3e50; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
SCROLL_JS = """<script>function scrollChat(){const el=document.querySelector('.chat-container');if(el) el.scrollTop=el.scrollHeight;}setTimeout(scrollChat,200);</script>"""

st.markdown(f'<div style="position:auto; right:30px; top:80px; z-index:1200;"><img src="{GSK_LOGO_URL}" width="140" /></div>', unsafe_allow_html=True)
st.markdown('<div class="title-box"><h1>💡 AI Sales Call Assistant</h1><p>Powered by AI to equip reps for smarter HCP conversations</p></div>', unsafe_allow_html=True)
st.markdown('<p style="text-align:center;font-weight:600;">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Sidebar filters (same as before)
# ----------------------------
gsk_brands = {"Shingrix": "https://www.shingrix.com/", "Trelegy": "https://www.trelegy.com/", "Zejula": "https://www.zejula.com/"}
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = [
    "HCP does not consider HZ a risk", "No time for discussion", "Cost concerns",
    "Not convinced of efficacy", "Accessibility/Logistics", "Patient reluctance",
    "Other clinical doubts"
]
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist",
               "Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"]
sales_call_steps = ["1-Prepare","2-Engage","3-Create Opportunities","4-Impact GSO","5-Influence","6-Analyze & Post-call Analysis"]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]

with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
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
# PDF upload & bullet-point summary
# ----------------------------
st.markdown("### 📄 Upload Medical Reference PDF (Optional)")
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text

        # Summarize using Groq
        if client:
            summary_prompt = f"Summarize the following medical text into concise, **bullet points**, highlighting key points useful for pharmaceutical sales reps. Bold and highlight GSK sales call steps and APACT steps:\n\n{full_text[:4000]}"
            resp = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {"role":"system","content":"You are a medical summarizer for pharmaceutical sales reps."},
                    {"role":"user","content":summary_prompt}
                ],
                temperature=0.2
            )
            summary = resp.choices[0].message.content.strip()
            # Highlight steps in AI output
            for step in sales_call_steps:
                summary = summary.replace(step, f'<span class="highlight-step">{step}</span>')
            for apact in APACT_STEPS:
                summary = summary.replace(apact, f'<span class="highlight-apact">{apact}</span>')
            st.session_state.pdf_summary = summary

        if st.session_state.pdf_summary:
            with st.expander("📄 PDF Summary (expand/collapse)", expanded=False):
                st.markdown(f'<div class="pdf-summary-box">{st.session_state.pdf_summary.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

    except Exception as e:
        st.error("PDF error: " + str(e))

# ----------------------------
# AI response generation
# ----------------------------
def generate_ai_response(prompt, pdf_text=""):
    if client is None:
        return "Groq API not configured. AI response unavailable."
    user_content = f"{prompt}\n\nReference info:\n{pdf_text}" if pdf_text else prompt
    try:
        resp = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role":"system","content":"You are a helpful sales call assistant for pharmaceutical reps. Highlight all GSK sales call steps and APACT steps in bold and colored text."},
                {"role":"user","content":user_content}
            ],
            temperature=0.5
        )
        content = resp.choices[0].message.content.strip()
        # Highlight steps in AI response
        for step in sales_call_steps:
            content = content.replace(step, f'<span class="highlight-step">{step}</span>')
        for apact in APACT_STEPS:
            content = content.replace(apact, f'<span class="highlight-apact">{apact}</span>')
        return content
    except Exception as e:
        return f"Error generating AI response: {e}"

# ----------------------------
# Render chat
# ----------------------------
def render_chat_history():
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for entry in st.session_state.chat_history:
        role = entry.get("role","user")
        content = entry.get("content","")
        bubble_class = "chat-bubble-user" if role=="user" else "chat-bubble-ai"
        st.markdown(f'<div class="{bubble_class}">{content.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)
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
        ai_resp = generate_ai_response(user_input, st.session_state.pdf_summary)
        st.session_state.chat_history.append({"role":"ai","content":ai_resp})
        render_chat_history()
st.markdown('</div>', unsafe_allow_html=True)
