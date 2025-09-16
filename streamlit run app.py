import os
import io
import tempfile
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
from streamlit_webrtc import webrtc_streamer, AudioProcessorBase, WebRtcMode
import av
import speech_recognition as sr

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
    try:
        tts = gTTS(text=text, lang="en")
        tts.save(filename)
        return filename
    except Exception:
        return None

def ask_ai(prompt):
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

# ----------------------------
# Session State
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = ""
if "audio_buffer" not in st.session_state:
    st.session_state.audio_buffer = None

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
# Upload Documents
# ----------------------------
st.subheader("📤 Upload Supporting Documents")
uploaded_file = st.file_uploader("Upload PDF, DOCX, PPTX, or Audio", type=["pdf","docx","pptx","mp3","wav","m4a"])
if uploaded_file:
    file_ext = uploaded_file.name.split(".")[-1].lower()
    extracted_text, extracted_images = "", []
    if file_ext == "docx": extracted_text = extract_text_from_docx(uploaded_file)
    elif file_ext == "pdf":
        extracted_text = extract_text_from_pdf(uploaded_file)
        extracted_images = extract_images_from_pdf(uploaded_file)
    elif file_ext == "pptx": extracted_text = extract_text_from_pptx(uploaded_file)
    elif file_ext in ["mp3","wav","m4a"]: extracted_text = f"🔊 Audio uploaded ({uploaded_file.name}) - transcription not implemented."
    st.session_state.uploaded_docs = extracted_text[:8000]
    if extracted_text: st.write(extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else ""))
    if extracted_images:
        for img in extracted_images: st.image(img, use_container_width=True)

# ----------------------------
# Chat Display
# ----------------------------
chat_placeholder = st.empty()
def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time","")
        content = msg["content"].replace("\n","<br>")
        if msg["role"] == "user":
            chat_html += f"""
            <div style='text-align:right; background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; margin:5px; display:inline-block; max-width:80%;'>
                <img src='https://cdn-icons-png.flaticon.com/512/147/147144.png' style='width:25px; vertical-align:middle; border-radius:50%'>
                {content}<br>
                <span style='font-size:10px; color:gray;'>{time}</span>
            </div>
            """
        else:
            chat_html += f"""
            <div style='text-align:left; background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; margin:5px; display:inline-block; max-width:80%;'>
                <img src='https://cdn-icons-png.flaticon.com/512/4712/4712027.png' style='width:25px; vertical-align:middle; border-radius:50%'>
                {content}<br>
                <span style='font-size:10px; color:gray;'>{time}</span>
            </div>
            """
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# ----------------------------
# Audio Recording & Transcription
# ----------------------------
class AudioProcessor(AudioProcessorBase):
    def __init__(self):
        self.frames = []

    def recv(self, frame: av.AudioFrame):
        pcm = frame.to_ndarray()
        self.frames.append(pcm)
        return frame

webrtc_ctx = webrtc_streamer(
    key="voice",
    mode=WebRtcMode.SENDONLY,
    audio_processor_factory=AudioProcessor,
    media_stream_constraints={"audio": True, "video": False},
    async_processing=True,
    placeholder=st.empty()
)

if webrtc_ctx.audio_receiver:
    audio_frames = webrtc_ctx.audio_receiver.get_frames(timeout=1)
    if audio_frames:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            for frame in audio_frames:
                f.write(frame.to_bytes())
            st.session_state.audio_buffer = f.name

# ----------------------------
# Mic Transcription Button
# ----------------------------
if st.session_state.audio_buffer:
    r = sr.Recognizer()
    with sr.AudioFile(st.session_state.audio_buffer) as source:
        audio_data = r.record(source)
        try:
            transcript = r.recognize_google(audio_data)
            st.session_state.chat_history.append({"role":"user","content":transcript,"time":datetime.now().strftime("%H:%M")})
            display_chat()
            # AI Prompt
            prompt = f"Language: {language}\nUser input: {transcript}\nReferences: CDC, WHO, EDA, clinical papers."
            ai_output = ask_ai(prompt)
            st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M")})
            display_chat()
            # TTS
            audio_file = generate_tts(ai_output)
            if audio_file: st.audio(audio_file, format="audio/mp3")
        except Exception as e:
            st.warning(f"⚠️ Could not transcribe audio: {e}")

# ----------------------------
# Text Input Box (Fixed Bottom)
# ----------------------------
with st.form("chat_form", clear_on_submit=True):
    col1, col2 = st.columns([0.9,0.1])
    with col1:
        user_input = st.text_input("Type a message...", key="user_input_box")
    with col2:
        submitted = st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})
    prompt = f"Language: {language}\nUser input: {user_input}\nReferences: CDC, WHO, EDA, clinical papers."
    ai_output = ask_ai(prompt)
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M")})
    display_chat()
    audio_file = generate_tts(ai_output)
    if audio_file: st.audio(audio_file, format="audio/mp3")
