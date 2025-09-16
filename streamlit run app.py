import os
import io
import streamlit as st
import requests
from PIL import Image
from docx import Document
import pdfplumber
import PyPDF2
from pptx import Presentation
from gtts import gTTS
from groq import Groq
from datetime import datetime
import speech_recognition as sr

# ----------------------------
# App Configuration
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ----------------------------
# Groq API Setup
# ----------------------------
GROQ_API_KEY = "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"  # Replace with your key
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

def generate_tts(text, filename="output.mp3"):
    """Convert text to speech using gTTS."""
    try:
        tts = gTTS(text=text, lang="en")
        tts.save(filename)
        return filename
    except Exception:
        return None

def ask_ai(prompt):
    """Send a query to Groq model with fallback."""
    try:
        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "system", "content": "You are a helpful AI medical sales assistant."},
                      {"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
    except Exception:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": "You are a helpful AI medical sales assistant."},
                      {"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
    return response.choices[0].message.content

def transcribe_audio(file):
    recognizer = sr.Recognizer()
    audio = sr.AudioFile(file)
    with audio as source:
        audio_data = recognizer.record(source)
    try:
        text = recognizer.recognize_google(audio_data)
    except sr.UnknownValueError:
        text = "[Could not understand audio]"
    except sr.RequestError:
        text = "[Speech recognition service failed]"
    return text

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
# Upload Documents or Audio
# ----------------------------
st.subheader("📤 Upload Supporting Documents or Audio")
uploaded_file = st.file_uploader("PDF, DOCX, PPTX, MP3, WAV, M4A", type=["pdf","docx","pptx","mp3","wav","m4a"])
extracted_text = ""
if uploaded_file:
    file_ext = uploaded_file.name.split(".")[-1].lower()
    if file_ext in ["docx"]:
        extracted_text = extract_text_from_docx(uploaded_file)
    elif file_ext in ["pdf"]:
        extracted_text = extract_text_from_pdf(uploaded_file)
    elif file_ext in ["pptx"]:
        extracted_text = extract_text_from_pptx(uploaded_file)
    elif file_ext in ["mp3","wav","m4a"]:
        extracted_text = transcribe_audio(uploaded_file)
    st.session_state.uploaded_docs = extracted_text[:8000]
    st.subheader("📄 Extracted / Transcribed Text")
    st.write(extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else ""))

# ----------------------------
# Chat Interface (Bottom Box)
# ----------------------------
st.subheader("💬 Chat with AI")
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    audio_input = st.file_uploader("Or upload voice message (mp3/wav/m4a) → will be transcribed", type=["mp3","wav","m4a"], key="audio_upload")
    submitted = st.form_submit_button("Send ➤")
    
if submitted:
    if audio_input:
        user_text = transcribe_audio(audio_input)
    else:
        user_text = user_input.strip()
    if user_text:
        st.session_state.chat_history.append({"role":"user", "content":user_text, "time":datetime.now().strftime("%H:%M")})
        # AI Prompt
        references = (
            "1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information.\n"
            "2. CDC Shingrix Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html\n"
            "3. Strezova et al., 2022. Long-term Protection Against Herpes Zoster: https://doi.org/10.1093/ofid/ofac485\n"
            "4. CDC Clinical Overview of Shingles: https://www.cdc.gov/shingles/hcp/clinical-overview/index.html"
        )
        prompt = f"Language: {language}\nUser input: {user_text}\nReferences:\n{references}"
        ai_output = ask_ai(prompt)
        st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M")})

# ----------------------------
# Display Chat (WhatsApp-like)
# ----------------------------
chat_placeholder = st.empty()
def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time","")
        content = msg["content"].replace("\n","<br>")
        if msg["role"]=="user":
            chat_html += f"<div style='text-align:right; background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; margin:5px; display:inline-block; max-width:80%;'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>"
        else:
            chat_html += f"<div style='text-align:left; background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; margin:5px; display:inline-block; max-width:80%;'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)
display_chat()

# ----------------------------
# Voice Response
# ----------------------------
if st.session_state.chat_history:
    latest_ai = [m["content"] for m in st.session_state.chat_history if m["role"]=="ai"]
    if latest_ai:
        st.subheader("🎙️ AI Voice Response")
        audio_file = generate_tts(latest_ai[-1])
        if audio_file:
            st.audio(audio_file, format="audio/mp3")
        else:
            st.warning("⚠️ gTTS not available")

# ----------------------------
# Word Download
# ----------------------------
if st.session_state.chat_history:
    latest_ai = [m["content"] for m in st.session_state.chat_history if m["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io.BytesIO()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")
