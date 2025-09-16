import os
import io
import streamlit as st
import requests
from PIL import Image
from docx import Document
import fitz  # PyMuPDF
import pdfplumber
from pptx import Presentation
from gtts import gTTS
from groq import Groq
from datetime import datetime
from streamlit_mic_recorder import mic_recorder

# ----------------------------
# App Configuration
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ----------------------------
# Groq API Setup
# ----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
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

def extract_images_from_pdf(file):
    images = []
    pdf = fitz.open(file)
    for page_num in range(len(pdf)):
        for img_index, img in enumerate(pdf[page_num].get_images()):
            xref = img[0]
            base_image = pdf.extract_image(xref)
            image_bytes = base_image["image"]
            images.append(Image.open(io.BytesIO(image_bytes)))
    return images

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
        lang = "ar" if any("\u0600" <= c <= "\u06FF" for c in text) else "en"
        tts = gTTS(text=text, lang=lang)
        tts.save(filename)
        return filename
    except Exception:
        return None

def ask_ai(prompt):
    """Send a query to Groq model with fallback."""
    try:
        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful AI medical sales assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
    except Exception:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
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
gsk_brands_images = {
    "Trelegy": "https://www.example.com/trelegy.png",
    "Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Zejula": "https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png",
}

# ----------------------------
# Upload Documents
# ----------------------------
st.subheader("📤 Upload Supporting Documents")
uploaded_file = st.file_uploader("Upload PDF, DOCX, PPTX, or Audio", type=["pdf", "docx", "pptx"])
if uploaded_file:
    file_ext = uploaded_file.name.split(".")[-1].lower()
    extracted_text = ""
    extracted_images = []

    if file_ext == "docx":
        extracted_text = extract_text_from_docx(uploaded_file)
    elif file_ext == "pdf":
        extracted_text = extract_text_from_pdf(uploaded_file)
        extracted_images = extract_images_from_pdf(uploaded_file)
    elif file_ext == "pptx":
        extracted_text = extract_text_from_pptx(uploaded_file)

    st.session_state.uploaded_docs = extracted_text[:8000]

    if extracted_text:
        st.subheader("📄 Extracted Text")
        st.write(extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else ""))

    if extracted_images:
        st.subheader("🖼️ Extracted Images")
        for img in extracted_images:
            st.image(img, use_container_width=True)

# ----------------------------
# Chat Interface
# ----------------------------
st.subheader("💬 Chat with AI")

# Mic Recorder
st.markdown("🎤 Speak instead of typing:")
audio_data = mic_recorder(start_prompt="Start Recording", stop_prompt="Stop Recording", key="recorder")

user_input = st.text_input("Type your message...")

if audio_data:
    st.success("Voice message recorded ✅ (transcription placeholder)")
    user_input = "🔊 Voice message transcription (placeholder)"  # You can integrate ASR later

if st.button("➤ Send") and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})

    # Call AI
    ai_output = ask_ai(user_input)
    st.session_state.chat_history.append({"role": "ai", "content": ai_output, "time": datetime.now().strftime("%H:%M")})

# ----------------------------
# Display Chat
# ----------------------------
chat_placeholder = st.empty()
def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time", "")
        content = msg["content"].replace('\n', '<br>')
        if msg["role"] == "user":
            chat_html += f"<div style='text-align:right; background:#dcf8c6; padding:10px; border-radius:15px; margin:5px; display:inline-block; max-width:80%;'>👤 {content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>"
        else:
            chat_html += f"<div style='text-align:left; background:#f0f2f6; padding:10px; border-radius:15px; margin:5px; display:inline-block; max-width:80%;'>🤖 {content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# ----------------------------
# Voice Generation
# ----------------------------
if st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
    if latest_ai:
        st.subheader("🎙️ AI Voice Response")
        audio_file = generate_tts(latest_ai[-1])
        if audio_file:
            st.audio(audio_file, format="audio/mp3")
