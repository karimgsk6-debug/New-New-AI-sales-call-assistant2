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

# CSS styling (same as before)
CSS = """..."""  # Keep your previous CSS
st.markdown(CSS, unsafe_allow_html=True)
SCROLL_JS = """<script>function scrollChat(){const el=document.querySelector('.chat-container');if(el) el.scrollTop=el.scrollHeight;}setTimeout(scrollChat,200);</script>"""

st.markdown(f'<div style="position:auto; right:30px; top:80px; z-index:1200;"><img src="{GSK_LOGO_URL}" width="140" /></div>', unsafe_allow_html=True)
st.markdown('<div class="title-box"><h1>💡 AI Sales Call Assistant</h1><p>Powered by AI to equip reps for smarter HCP conversations</p></div>', unsafe_allow_html=True)
st.markdown('<p style="text-align:center;font-weight:600;">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Sidebar filters
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
# PDF upload & informative bullet-point summary using Groq
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
            summary_prompt = f"Summarize the following medical text into concise, **bullet points**, highlighting key points useful for pharmaceutical sales reps. Include APACT steps and sales call relevance:\n\n{full_text[:4000]}"
            resp = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {"role":"system","content":"You are a medical summarizer for pharmaceutical sales reps."},
                    {"role":"user","content":summary_prompt}
                ],
                temperature=0.2
            )
            st.session_state.pdf_summary = resp.choices[0].message.content.strip()
        else:
            st.warning("Groq client not configured. PDF summary unavailable.")

        if st.session_state.pdf_summary:
            with st.expander("📄 PDF Summary (expand/collapse)", expanded=False):
                st.markdown(f'<div class="pdf-summary-box">{st.session_state.pdf_summary.replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

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
# AI response using Groq
# ----------------------------
def generate_ai_response(prompt, pdf_text=""):
    if client is None:
        return "Groq API not configured. AI response unavailable."
    user_content = f"{prompt}\n\nReference info:\n{pdf_text}" if pdf_text else prompt
    try:
        resp = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role":"system","content":"You are a helpful sales call assistant for pharmaceutical reps."},
                {"role":"user","content":user_content}
            ],
            temperature=0.5
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Error generating AI response: {e}"

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
