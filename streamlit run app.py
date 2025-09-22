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
import asyncio
import edge_tts  # for humanized Arabic TTS
from groq import Groq

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

async def generate_edge_tts(text, filename="output.mp3", voice="ar-SY-HodaNeural"):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)
    return filename

def generate_gtts(text, filename="output.mp3", lang="en"):
    try:
        tts = gTTS(text=text, lang=lang)
        tts.save(filename)
        return filename
    except Exception:
        return None

def ask_ai(prompt):
    """Send a query to Groq model"""
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
# Sidebar Filters (WhatsApp-style info/settings)
# ----------------------------
st.sidebar.header("Filters & Options")
brands = ["Shingrix", "Trelegy", "Zejula"]
brand = st.sidebar.selectbox("Select Brand", brands)

race_segments = [
    "R – Reach",
    "A – Acquisition",
    "C – Conversion",
    "E – Engagement"
]
segment = st.sidebar.selectbox("Select RACE Segment", race_segments)

doctor_barriers = [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ Vx effective",
    "Accessibility issues"
]
barrier = st.sidebar.multiselect("Select Doctor Barrier", doctor_barriers)

specialties = ["GP", "Cardiologist", "Dermatologist"]
specialty = st.sidebar.selectbox("Doctor Specialty", specialties)

personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced"]
persona = st.sidebar.selectbox("HCP Persona", personas)

objectives = ["Awareness", "Adoption", "Retention"]
objective = st.sidebar.selectbox("Objective", objectives)

response_length = st.sidebar.selectbox("Response Length", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])

# ----------------------------
# Upload Documents
# ----------------------------
st.subheader("📤 Upload Supporting Documents")
uploaded_file = st.file_uploader("Upload PDF, DOCX, PPTX, or Audio", type=["pdf", "docx", "pptx", "mp3", "wav", "m4a"])
if uploaded_file:
    file_ext = uploaded_file.name.split(".")[-1].lower()
    extracted_text = ""

    if file_ext == "docx":
        extracted_text = extract_text_from_docx(uploaded_file)
    elif file_ext == "pdf":
        extracted_text = extract_text_from_pdf(uploaded_file)
    elif file_ext == "pptx":
        extracted_text = extract_text_from_pptx(uploaded_file)
    elif file_ext in ["mp3", "wav", "m4a"]:
        extracted_text = f"🔊 Audio file uploaded ({uploaded_file.name}) - transcription not implemented yet."

    st.session_state.uploaded_docs = extracted_text[:8000]
    if extracted_text:
        st.subheader("📄 Extracted Text")
        st.write(extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else ""))

# ----------------------------
# Chat interface
# ----------------------------
st.markdown("<h2>💬 Chat with AI</h2>", unsafe_allow_html=True)
chat_placeholder = st.empty()

def render_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        content = msg["content"].replace('\n', '<br>')
        time = msg.get("time", "")
        if msg["role"] == "user":
            chat_html += f"<div style='text-align:right; display:flex; justify-content:flex-end; margin-bottom:5px;'>"
            chat_html += f"<div style='background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; max-width:70%;'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>"
            chat_html += f"<div style='font-size:35px; margin-left:5px;'>🚹</div></div>"
        else:
            chat_html += f"<div style='text-align:left; display:flex; justify-content:flex-start; margin-bottom:5px;'>"
            chat_html += f"<div style='font-size:35px; margin-right:5px;'>🤖</div>"
            chat_html += f"<div style='background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; max-width:70%;'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div></div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

# ----------------------------
# Input box fixed at bottom
# ----------------------------
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    submitted = st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_input,
        "time": datetime.now().strftime("%H:%M")
    })

    # Build AI prompt
    references = "1. CDC Shingrix Recommendations\n2. Clinical Overview of Shingles\n3. WHO Vaccine Overview"
    prompt = f"""
User input: {user_input}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Brand: {brand}
Doctor Specialty: {specialty}
HCP Persona: {persona}
References: {references}
Response Length: {response_length}
Response Tone: {response_tone}
"""

    # Get AI output
    ai_output = ask_ai(prompt)
    st.session_state.chat_history.append({
        "role": "ai",
        "content": ai_output,
        "time": datetime.now().strftime("%H:%M")
    })
    render_chat()

    # Generate voice
    if response_tone.lower() in ["arabic", "العربية"]:
        asyncio.run(generate_edge_tts(ai_output, filename="ai_response.mp3", voice="ar-SY-HodaNeural"))
    else:
        generate_gtts(ai_output, filename="ai_response.mp3", lang="en")
    st.audio("ai_response.mp3", format="audio/mp3")

# Initial render
render_chat()

# ----------------------------
# Word Download
# ----------------------------
if st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io.BytesIO()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")
