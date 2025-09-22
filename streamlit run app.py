import os
import io
import streamlit as st
import requests
from PIL import Image
from docx import Document
import pdfplumber
from pptx import Presentation
from gtts import gTTS
from groq import Groq
from datetime import datetime

# ----------------------------
# App Configuration
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ----------------------------
# Groq API Setup
# ----------------------------
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# ----------------------------
# Helper Functions
# ----------------------------
def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join([p.text for p in doc.paragraphs])

def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

def extract_text_from_pptx(file):
    prs = Presentation(file)
    text_runs = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text_runs.append(shape.text)
    return "\n".join(text_runs)


def generate_tts(text, filename="output.mp3", lang='en'):
    try:
        tts = gTTS(text=text, lang=lang)
        tts.save(filename)
        return filename
    except Exception:
        return None


def ask_ai(prompt):
    response = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a helpful AI medical sales assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1000
    )
    return response.choices[0].message.content

# ----------------------------
# Session State
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = ""

# ----------------------------
# Language
# ----------------------------
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])

# ----------------------------
# GSK Logo
# ----------------------------
logo_local_path = "images/gsk_logo.png"
logo_fallback_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
col1, col2 = st.columns([1,5])
with col1:
    try:
        logo_img = Image.open(logo_local_path)
        st.image(logo_img, width=120)
    except:
        st.image(logo_fallback_url, width=120)
with col2:
    st.title("🧠 AI Sales Call Assistant")

# ----------------------------
# Brand & Product Data
# ----------------------------
gsk_brands = {
    "Shingrix": "https://example.com/shingrix-leaflet",
    "Trelegy": "https://example.com/trelegy-leaflet",
    "Zejula": "https://example.com/zejula-leaflet",
}

# ----------------------------
# Filters
# ----------------------------
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = ["HCP does not consider HZ as risk", "No time to discuss preventive measures", "Cost considerations", "Not convinced HZ Vx effective", "Accessibility issues"]
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
thinking_styles = ["Analytical", "Skeptic", "Emotional", "Pragmatic"]
tones = ["Formal", "Casual", "Friendly", "Persuasive"]

# ----------------------------
# Sidebar Filters
# ----------------------------
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand", options=list(gsk_brands.keys()))
segment = st.sidebar.multiselect("Select RACE Segment", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barrier", doctor_barriers)
persona = st.sidebar.multiselect("Select HCP Persona", personas)
thinking_style = st.sidebar.selectbox("Select HCP Thinking Style", thinking_styles)
tone = st.sidebar.selectbox("Response Tone", tones)

# ----------------------------
# Upload Documents
# ----------------------------
st.subheader("📤 Upload Supporting Documents")
uploaded_file = st.file_uploader("Upload PDF, DOCX, PPTX", type=["pdf","docx","pptx"])
if uploaded_file:
    file_ext = uploaded_file.name.split('.')[-1].lower()
    if file_ext == 'docx':
        st.session_state.uploaded_docs = extract_text_from_docx(uploaded_file)
    elif file_ext == 'pdf':
        st.session_state.uploaded_docs = extract_text_from_pdf(uploaded_file)
    elif file_ext == 'pptx':
        st.session_state.uploaded_docs = extract_text_from_pptx(uploaded_file)
    st.subheader("📄 Extracted Text")
    st.write(st.session_state.uploaded_docs[:2000] + ("..." if len(st.session_state.uploaded_docs) > 2000 else ""))

# ----------------------------
# Chat Interface (Sticky Bottom Input)
# ----------------------------
chat_placeholder = st.container()
with st.container():
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("Type your message...", key="user_input_box")
        submitted = st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})
    prompt = f"Brand: {brand}\nSegment: {', '.join(segment)}\nPersona: {', '.join(persona)}\nThinking Style: {thinking_style}\nTone: {tone}\nDoctor Barrier: {', '.join(barrier)}\nUploaded Docs: {st.session_state.uploaded_docs[:1000]}\nUser Input: {user_input}"
    ai_output = ask_ai(prompt)
    st.session_state.chat_history.append({"role": "ai", "content": ai_output, "time": datetime.now().strftime("%H:%M")})

# ----------------------------
# Display Chat with Per-message Voice
# ----------------------------
def display_chat():
    for msg in st.session_state.chat_history:
        content = msg['content'].replace('\n', '<br>')
        if msg['role'] == 'user':
            st.markdown(f"<div style='text-align:right;background:#dcf8c6;padding:10px;border-radius:15px 15px 0px 15px;margin:5px;max-width:80%'>{content}<br><span style='font-size:10px;color:gray'>{msg['time']}</span></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='text-align:left;background:#f0f2f6;padding:10px;border-radius:15px 15px 15px 0px;margin:5px;max-width:80%'>{content}<br><span style='font-size:10px;color:gray'>{msg['time']}</span></div>", unsafe_allow_html=True)
            audio_file = generate_tts(msg['content'], filename=f"ai_{msg['time'].replace(':','')}.mp3", lang='ar' if language=='العربية' else 'en')
            if audio_file:
                st.audio(audio_file, format="audio/mp3")

display_chat()
