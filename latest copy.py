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
from datetime import datetime
import time

# ----------------------------
# App Configuration
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ----------------------------
# Groq API Setup
# ----------------------------
GROQ_API_KEY = "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"
API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ----------------------------
# Session State
# ----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "typing" not in st.session_state:
    st.session_state.typing = False
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = ""

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

def stream_ai_response(user_input):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.1-70b-versatile",
        "messages": [{"role": "user", "content": user_input}],
        "stream": True
    }
    with requests.post(API_URL, headers=headers, json=payload, stream=True) as r:
        partial_text = ""
        for line in r.iter_lines():
            if line:
                try:
                    chunk = line.decode("utf-8").replace("data: ", "")
                    if chunk.strip() == "[DONE]":
                        break
                    data = eval(chunk)  # crude SSE parser
                    delta = data["choices"][0]["delta"].get("content", "")
                    if delta:
                        partial_text += delta
                        yield partial_text
                except Exception:
                    continue

# ----------------------------
# Sidebar (collapsible)
# ----------------------------
with st.sidebar:
    st.markdown("## 🎯 Filters")
    brands = ["Shingrix", "Trelegy", "Zejula"]
    segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
    barriers = [
        "HCP does not consider HZ as risk",
        "No time to discuss preventive measures",
        "Cost considerations",
        "Not convinced HZ Vx effective",
        "Accessibility issues"
    ]
    objectives = ["Awareness", "Adoption", "Retention"]
    specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]
    personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
    approaches = ["Use data-driven evidence", "Focus on patient outcomes", "Leverage storytelling techniques"]

    selected_brands = st.multiselect("Brand", brands, default=brands)
    selected_segments = st.multiselect("RACE Segment", segments, default=segments)
    selected_barriers = st.multiselect("Doctor Barriers", barriers)
    selected_objectives = st.multiselect("Objective", objectives)
    selected_specialties = st.multiselect("Specialty", specialties)
    selected_personas = st.multiselect("HCP Persona", personas)
    selected_approaches = st.multiselect("Sales Approaches", approaches)

    st.markdown("## 📄 Upload Documents")
    uploaded_file = st.file_uploader("PDF, DOCX, PPTX, Audio", type=["pdf", "docx", "pptx", "mp3", "wav", "m4a"])
    if uploaded_file:
        ext = uploaded_file.name.split(".")[-1].lower()
        extracted_text = ""
        extracted_images = []
        if ext == "docx":
            extracted_text = extract_text_from_docx(uploaded_file)
        elif ext == "pdf":
            extracted_text = extract_text_from_pdf(uploaded_file)
            extracted_images = extract_images_from_pdf(uploaded_file)
        elif ext == "pptx":
            extracted_text = extract_text_from_pptx(uploaded_file)
        elif ext in ["mp3", "wav", "m4a"]:
            extracted_text = f"🔊 Audio uploaded ({uploaded_file.name}) – transcription not implemented."

        st.session_state.uploaded_docs = extracted_text[:8000]
        if extracted_text:
            st.subheader("📄 Extracted Text")
            st.write(extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else ""))
        if extracted_images:
            st.subheader("🖼️ Extracted Images")
            for img in extracted_images:
                st.image(img, use_container_width=True)

    st.markdown("## ⚙️ Settings")
    response_length = st.selectbox("Response Length", ["Short", "Medium", "Long"])
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])
    tts_enabled = st.checkbox("Enable TTS", value=True)
    if st.button("📥 Download Latest AI Response as Word"):
        if st.session_state.messages:
            latest_ai = [m["content"] for m in st.session_state.messages if m["role"]=="assistant"]
            if latest_ai:
                doc = Document()
                doc.add_heading("AI Sales Call Response", 0)
                doc.add_paragraph(latest_ai[-1])
                word_buffer = io.BytesIO()
                doc.save(word_buffer)
                st.download_button("Download", word_buffer.getvalue(), file_name="AI_Response.docx")

    st.markdown("### References")
    st.markdown("""
1. CDC Shingrix Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html  
2. CDC Clinical Overview of Shingles: https://www.cdc.gov/shingles/hcp/clinical-overview/index.html  
3. WHO Vaccine Overview: https://www.who.int/news-room/fact-sheets/detail/shingles
""")

# ----------------------------
# Main Chat Interface
# ----------------------------
st.subheader("💬 Chat with AI")

# Display chat
chat_placeholder = st.empty()
def display_chat():
    chat_html = ""
    for msg in st.session_state.messages:
        time_str = msg.get("time", "")
        content = msg["content"].replace("\n","<br>")
        if msg["role"]=="user":
            chat_html += f"""
            <div style='display:flex; justify-content:flex-end; align-items:flex-end; margin:5px'>
                <div style='background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; max-width:70%'>
                    {content}<br>
                    <span style='font-size:10px; color:gray;'>{time_str} ✅✅</span>
                </div>
                <div style='font-size:35px; margin-left:5px;'>🚹</div>
            </div>
            """
        else:
            chat_html += f"""
            <div style='display:flex; justify-content:flex-start; align-items:flex-start; margin:5px'>
                <div style='font-size:35px; margin-right:5px;'>🤖</div>
                <div style='background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; max-width:70%'>
                    {content}<br>
                    <span style='font-size:10px; color:gray;'>{time_str} ✔✔</span>
                </div>
            </div>
            """
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

# Input fixed at bottom
st.markdown("""
<style>
div[data-testid="stTextInput"] {position: fixed; bottom: 15px; width: 80%;}
.block-container {padding-bottom: 150px;}
</style>
""", unsafe_allow_html=True)

user_input = st.text_input("Type your message...", key="input")
if user_input:
    current_time = datetime.now().strftime("%H:%M")
    st.session_state.messages.append({"role":"user","content":user_input,"time":current_time})
    st.session_state.typing = True
    st.experimental_rerun()

# Word-by-word streaming AI response
if st.session_state.typing:
    last_user = st.session_state.messages[-1]["content"]
    current_time = datetime.now().strftime("%H:%M")
    placeholder = st.empty()
    ai_text = ""

    for partial in stream_ai_response(last_user):
        ai_text = partial
        placeholder.markdown(f"""
        <div style='display:flex; justify-content:flex-start; align-items:flex-start; margin:5px'>
            <div style='font-size:35px; margin-right:5px;'>🤖</div>
            <div style='background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; max-width:70%'>
                {ai_text}<br>
                <span style='font-size:10px; color:gray;'>{current_time} ✔✔</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        time.sleep(0.05)

    st.session_state.messages.append({"role":"assistant","content":ai_text,"time":current_time})
    st.session_state.typing = False
    st.experimental_rerun()

# ----------------------------
# TTS Playback
# ----------------------------
if tts_enabled and st.session_state.messages:
    latest_ai = [m["content"] for m in st.session_state.messages if m["role"]=="assistant"]
    if latest_ai:
        audio_file = generate_tts(latest_ai[-1])
        if audio_file:
            st.audio(audio_file, format="audio/mp3")
        else:
            st.warning("⚠️ Voice response unavailable.")

display_chat()
