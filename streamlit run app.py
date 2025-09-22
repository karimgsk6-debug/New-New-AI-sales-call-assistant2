# ----------------------------
# Imports
# ----------------------------
import os
import io
import streamlit as st
import requests
from PIL import Image
from docx import Document
import pdfplumber
from pptx import Presentation
from gtts import gTTS
from datetime import datetime
from groq import Groq

# ----------------------------
# App Config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ----------------------------
# Groq API
# ----------------------------
GROQ_API_KEY = "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"  # Insert your key
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

def generate_tts_safe(text, lang="en", filename=None):
    """Generate TTS safely and return filename."""
    if not filename:
        filename = f"tts_{datetime.now().strftime('%H%M%S%f')}.mp3"
    try:
        tts = gTTS(text=text, lang=lang)
        tts.save(filename)
        return filename
    except Exception as e:
        print("TTS Error:", e)
        return None

def ask_ai(prompt):
    """Send a query to Groq."""
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
language = st.radio("Select Language / اختر اللغة", ["English", "العربية"])
tts_lang = "ar" if language=="العربية" else "en"

# ----------------------------
# Logo
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
# Brand & Filters
# ----------------------------
gsk_brands = {"Shingrix":"https://example.com/shingrix-leaflet"}
race_segments = ["R – Reach","A – Acquisition","C – Conversion","E – Engagement"]
doctor_barriers = ["HCP does not consider HZ as risk","No time to discuss preventive measures"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency"]

st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand", list(gsk_brands.keys()))
segment = st.sidebar.selectbox("Select RACE Segment", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barrier", doctor_barriers)
objective = st.sidebar.selectbox("Select Objective", objectives)
specialty = st.sidebar.selectbox("Select Doctor Specialty", specialties)
persona = st.sidebar.selectbox("Select HCP Persona", personas)

# ----------------------------
# Upload Documents
# ----------------------------
st.subheader("📤 Upload Documents")
uploaded_file = st.file_uploader("PDF, DOCX, PPTX, Audio", type=["pdf","docx","pptx","mp3","wav","m4a"])
if uploaded_file:
    ext = uploaded_file.name.split(".")[-1].lower()
    extracted_text = ""
    if ext=="docx":
        extracted_text = extract_text_from_docx(uploaded_file)
    elif ext=="pdf":
        extracted_text = extract_text_from_pdf(uploaded_file)
    elif ext=="pptx":
        extracted_text = extract_text_from_pptx(uploaded_file)
    elif ext in ["mp3","wav","m4a"]:
        extracted_text = f"🔊 Audio uploaded: {uploaded_file.name} (transcription not available)"
    st.session_state.uploaded_docs = extracted_text[:8000]
    if extracted_text:
        st.subheader("📄 Extracted Text")
        st.write(extracted_text[:2000]+"..." if len(extracted_text)>2000 else extracted_text)

# ----------------------------
# Chat Display + Voice
# ----------------------------
chat_placeholder = st.empty()
def display_chat_with_voice():
    chat_html = ""
    for idx, msg in enumerate(st.session_state.chat_history):
        time = msg.get("time","")
        content = msg["content"].replace("\n","<br>")
        if msg["role"]=="user":
            chat_html += f"<div style='text-align:right;background:#dcf8c6;padding:10px;border-radius:15px 15px 0px 15px;margin:5px;max-width:80%;display:inline-block'>{content}<br><span style='font-size:10px;color:gray'>{time}</span></div>"
        else:
            chat_html += f"<div style='text-align:left;background:#f0f2f6;padding:10px;border-radius:15px 15px 15px 0px;margin:5px;max-width:80%;display:inline-block'>{content}<br><span style='font-size:10px;color:gray'>{time}</span></div>"
            # Generate TTS per message
            audio_file = generate_tts_safe(msg["content"], lang=tts_lang)
            if audio_file:
                chat_html += f"<audio controls src='{audio_file}' style='margin-left:5px;margin-bottom:10px;'></audio>"
            else:
                chat_html += "<span style='color:red;'>⚠️ Voice unavailable</span><br>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat_with_voice()

# ----------------------------
# Chat Form at Bottom
# ----------------------------
st.markdown("<div style='position:fixed;bottom:0;width:100%;background:white;padding:10px;box-shadow:0px -2px 5px rgba(0,0,0,0.1);z-index:9999;'>", unsafe_allow_html=True)
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box", placeholder="Write a message...")
    submitted = st.form_submit_button("➤")
st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# Handle New Message
# ----------------------------
if submitted and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})

    # Build AI prompt
    prompt = f"""
Language: {language}
User input: {user_input}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Brand: {brand}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Uploaded Docs: {st.session_state.uploaded_docs}
Use APACT for objections.
Provide professional and friendly suggestions.
"""
    ai_response = ask_ai(prompt)
    st.session_state.chat_history.append({"role":"ai","content":ai_response,"time":datetime.now().strftime("%H:%M")})

    display_chat_with_voice()

# ----------------------------
# Word Download
# ----------------------------
if st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response",0)
        for text in latest_ai:
            doc.add_paragraph(text)
        word_buffer = io.BytesIO()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")

# ----------------------------
# Brand Leaflet
# ----------------------------
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
