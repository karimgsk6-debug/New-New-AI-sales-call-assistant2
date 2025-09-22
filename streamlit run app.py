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
# Optional Edge TTS for humanized Arabic
# ----------------------------
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False

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

# ----------------------------
# Voice Generation
# ----------------------------
def generate_gtts(text, filename="output.mp3", lang="en"):
    try:
        tts = gTTS(text=text, lang=lang)
        tts.save(filename)
        return filename
    except Exception:
        return None

async def generate_edge_tts(text, filename="output_edge.mp3", voice="ar-EG-HodaNeural"):
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(filename)
        return filename
    except Exception:
        return None

def generate_tts_safe(text, lang="en"):
    """
    Auto fallback: Use edge-tts for Arabic if available, else gTTS.
    """
    if EDGE_TTS_AVAILABLE and lang.startswith("ar"):
        import asyncio
        filename = "edge_output.mp3"
        try:
            asyncio.run(generate_edge_tts(text, filename=filename, voice="ar-EG-HodaNeural"))
            return filename
        except:
            pass
    # fallback to gTTS
    return generate_gtts(text, filename="output.mp3", lang=lang)

# ----------------------------
# AI Query
# ----------------------------
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

# ----------------------------
# Language Selection
# ----------------------------
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])
tts_lang = "ar" if language == "العربية" else "en"

# ----------------------------
# Sidebar Logo
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
# Sidebar Filters
# ----------------------------
st.sidebar.header("Filters & Options")
brands = ["Shingrix", "Trelegy", "Zejula"]
segments = [
    "R – Reach: Did not start to prescribe yet and Don't believe that vaccination is his responsibility.",
    "A – Acquisition: Prescribe to patient who initiate discussion about the vaccine but Convinced about Shingrix data.",
    "C – Conversion: Proactively initiate discussion with specific patient profile but For other patient profiles he is not prescribing yet.",
    "E – Engagement: Proactively prescribe to different patient profiles"
]
barriers = [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ Vx effective",
    "Accessibility issues"
]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]
personas = [
    "Uncommitted Vaccinator",
    "Reluctant Efficiency",
    "Patient Influenced",
    "Committed Vaccinator"
]

brand = st.sidebar.selectbox("Brand", options=brands)
segment = st.sidebar.selectbox("RACE Segment", options=segments)
barrier = st.sidebar.multiselect("Doctor Barrier", options=barriers)
objective = st.sidebar.selectbox("Objective", options=objectives)
specialty = st.sidebar.selectbox("Doctor Specialty", options=specialties)
persona = st.sidebar.selectbox("HCP Persona", options=personas)

# ----------------------------
# File Upload
# ----------------------------
st.subheader("📤 Upload Supporting Documents")
uploaded_file = st.file_uploader("Upload PDF, DOCX, PPTX, or Audio", type=["pdf","docx","pptx","mp3","wav","m4a"])
if uploaded_file:
    file_ext = uploaded_file.name.split(".")[-1].lower()
    extracted_text = ""
    if file_ext == "docx":
        extracted_text = extract_text_from_docx(uploaded_file)
    elif file_ext == "pdf":
        extracted_text = extract_text_from_pdf(uploaded_file)
    elif file_ext == "pptx":
        extracted_text = extract_text_from_pptx(uploaded_file)
    elif file_ext in ["mp3","wav","m4a"]:
        extracted_text = f"🔊 Audio file uploaded ({uploaded_file.name}) - transcription not implemented yet."
    st.session_state.uploaded_docs = extracted_text[:8000]
    if extracted_text:
        st.subheader("📄 Extracted Text")
        st.write(extracted_text[:2000]+"..." if len(extracted_text)>2000 else extracted_text)

# ----------------------------
# Chat Interface at Bottom
# ----------------------------
chat_placeholder = st.empty()
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    submitted = st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})

    # Build prompt
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

# ----------------------------
# Display Chat
# ----------------------------
def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time","")
        content = msg["content"].replace("\n","<br>")
        if msg["role"]=="user":
            chat_html += f"<div style='text-align:right; background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; margin:5px; max-width:80%; display:inline-block'>{content}<br><span style='font-size:10px;color:gray'>{time}</span></div>"
        else:
            chat_html += f"<div style='text-align:left; background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; margin:5px; max-width:80%; display:inline-block'>{content}<br><span style='font-size:10px;color:gray'>{time}</span></div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# ----------------------------
# Voice Playback
# ----------------------------
if st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
    if latest_ai:
        st.subheader("🎙️ AI Voice Response")
        audio_file = generate_tts_safe(latest_ai[-1], lang=tts_lang)
        if audio_file:
            st.audio(audio_file, format="audio/mp3")
        else:
            st.warning("⚠️ Voice generation unavailable.")

# ----------------------------
# Download as Word
# ----------------------------
if st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response",0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io.BytesIO()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")
