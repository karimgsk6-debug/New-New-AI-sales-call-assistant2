import os
import io
import time
import streamlit as st
import requests
from PIL import Image
from docx import Document
import pdfplumber
from pptx import Presentation
import fitz  # PyMuPDF
from gtts import gTTS
import edge_tts
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

def generate_tts(text, lang="en", filename="output.mp3", voice_type="en-US-JennyNeural"):
    try:
        if lang == "ar":
            communicate = edge_tts.Communicate(text, voice=voice_type)
            return communicate.save(filename)
        else:
            tts = gTTS(text=text, lang=lang)
            tts.save(filename)
            return filename
    except Exception as e:
        print("TTS Error:", e)
        return None

def ask_ai_streaming(prompt):
    response_text = ""
    try:
        resp = client.chat.completions.stream(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "system", "content": "You are a helpful AI medical sales assistant."},
                      {"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        for chunk in resp:
            delta = chunk.choices[0].delta.get("content", "")
            response_text += delta
            yield response_text
    except Exception:
        response_text = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": "You are a helpful AI medical sales assistant."},
                      {"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        ).choices[0].message.content
        yield response_text

# ----------------------------
# Session State
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = ""

# ----------------------------
# Sidebar Filters
# ----------------------------
st.sidebar.header("Filters & Options")
gsk_brands = ["Shingrix", "Trelegy", "Zejula"]
brand = st.sidebar.selectbox("Brand", gsk_brands)

race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
segment = st.sidebar.selectbox("RACE Segment", race_segments)

doctor_barriers = [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ Vx effective",
    "Accessibility issues"
]
barrier = st.sidebar.multiselect("Doctor Barriers", options=doctor_barriers)

specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]
specialty = st.sidebar.selectbox("Doctor Specialty", specialties)

personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
persona = st.sidebar.selectbox("HCP Persona", personas)

thinking_styles = ["Analytical", "Skeptic", "Emotional", "Pragmatic"]
hcp_thinking = st.sidebar.selectbox("HCP Thinking Style", thinking_styles)

response_tones = ["Formal", "Casual", "Friendly", "Persuasive"]
response_tone = st.sidebar.selectbox("AI Response Tone", response_tones)

language = st.sidebar.radio("Select Language / اختر اللغة", options=["English", "العربية"])

# ----------------------------
# Upload Documents
# ----------------------------
st.subheader("Upload Supporting Documents")
uploaded_file = st.file_uploader("PDF, DOCX, PPTX, Audio", type=["pdf","docx","pptx","mp3","wav","m4a"])
if uploaded_file:
    file_ext = uploaded_file.name.split(".")[-1].lower()
    extracted_text = ""
    extracted_images = []
    if file_ext=="docx":
        extracted_text = extract_text_from_docx(uploaded_file)
    elif file_ext=="pdf":
        extracted_text = extract_text_from_pdf(uploaded_file)
        extracted_images = extract_images_from_pdf(uploaded_file)
    elif file_ext=="pptx":
        extracted_text = extract_text_from_pptx(uploaded_file)
    elif file_ext in ["mp3","wav","m4a"]:
        extracted_text = f"🔊 Audio file uploaded ({uploaded_file.name}) - transcription not implemented yet."

    st.session_state.uploaded_docs = extracted_text[:8000]

    if extracted_text:
        st.subheader("Extracted Text")
        st.write(extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else ""))
    if extracted_images:
        st.subheader("Extracted Images")
        for img in extracted_images:
            st.image(img, use_container_width=True)

# ----------------------------
# Chat container and sticky input
# ----------------------------
st.markdown("""
<style>
#chat_container { height: 500px; overflow-y: auto; padding:10px; border:1px solid #ccc; border-radius:10px; }
#input_form { position: fixed; bottom: 0; left: 25%; width: 70%; background: #fff; padding:10px; border-top:1px solid #ccc; z-index: 999; }
</style>
<div id='chat_container'></div>
""", unsafe_allow_html=True)

with st.form("chat_form", clear_on_submit=True, key='input_form'):
    user_input = st.text_input("Type your message...", key="user_input_box", placeholder="Write a message...")
    submitted = st.form_submit_button("➤")

# ----------------------------
# Process user input
# ----------------------------
if submitted and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})

    prompt = f"""
Language: {language}
User Input: {user_input}
Brand: {brand}
RACE Segment: {segment}
Doctor Barriers: {', '.join(barrier) if barrier else 'None'}
Doctor Specialty: {specialty}
HCP Persona: {persona}
HCP Thinking Style: {hcp_thinking}
AI Response Tone: {response_tone}
Uploaded Docs Context: {st.session_state.uploaded_docs}
Provide actionable suggestions tailored to this persona.
"""

    response_container = st.empty()
    full_response = ""
    audio_files = []

    for chunk in ask_ai_streaming(prompt):
        full_response = chunk
        response_container.markdown(full_response.replace('\n','<br>'), unsafe_allow_html=True)

    st.session_state.chat_history.append({"role":"ai","content":full_response,"time":datetime.now().strftime("%H:%M")})

    # Generate TTS
    filename = f"ai_voice_{len(st.session_state.chat_history)}.mp3"
    lang_code = "ar" if language=="العربية" else "en"
    generate_tts(full_response, lang=lang_code, filename=filename)
    audio_files.append(filename)

# ----------------------------
# Display chat
# ----------------------------
chat_html = ""
for i, msg in enumerate(st.session_state.chat_history):
    time = msg.get("time","")
    content = msg["content"].replace("\n","<br>")
    if msg["role"]=="user":
        chat_html += f"<div style='text-align:right; background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; margin:5px; display:inline-block; max-width:80%;'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>"
    else:
        chat_html += f"<div style='text-align:left; background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; margin:5px; display:inline-block; max-width:80%;'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span>"
        voice_file = f"ai_voice_{i+1}.mp3"
        if os.path.exists(voice_file):
            chat_html += f"<audio controls src='{voice_file}'></audio>"
        chat_html += "</div>"

st.markdown(chat_html, unsafe_allow_html=True)

# ----------------------------
# Word Download
# ----------------------------
if st.session_state.chat_history:
    doc = Document()
    doc.add_heading("AI Sales Call Responses",0)
    for msg in st.session_state.chat_history:
        if msg["role"]=="ai":
            doc.add_paragraph(msg["content"])
    word_buffer = io.BytesIO()
    doc.save(word_buffer)
    st.download_button("📥 Download AI Responses as Word", word_buffer.getvalue(), file_name="AI_Responses.docx")
