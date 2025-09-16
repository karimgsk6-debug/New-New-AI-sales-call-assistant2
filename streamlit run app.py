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

# ----------------------------
# App Configuration
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# Initialize Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
if not GROQ_API_KEY:
    st.error("❌ GROQ_API_KEY not found. Please set it in your environment.")
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

def generate_tts(text, lang="en", filename="output.mp3"):
    """Convert text to speech using gTTS (supports English & Arabic)."""
    tts = gTTS(text=text, lang=lang)
    tts.save(filename)
    return filename

def ask_ai(prompt):
    """Send a query to Groq model."""
    response = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a helpful AI medical sales assistant. Always cite credible sources (CDC, WHO, PubMed)."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=800
    )
    # Ensure safe extraction of response content
    try:
        return response.choices[0].message.content
    except Exception:
        return "⚠️ No valid response received from AI."

# ----------------------------
# Streamlit UI
# ----------------------------
st.title("💊 AI Sales Call Assistant")

# WhatsApp-style chat input
user_input = st.chat_input("💬 Type your message or upload a file below...")

# File uploader (PDF, DOCX, PPTX, audio)
uploaded_file = st.file_uploader(
    "📂 Upload a document (PDF, DOCX, PPTX) or an audio file",
    type=["pdf", "docx", "pptx", "mp3", "wav", "m4a"]
)

extracted_text = ""
extracted_images = []

if uploaded_file:
    file_ext = uploaded_file.name.split(".")[-1].lower()

    if file_ext == "docx":
        extracted_text = extract_text_from_docx(uploaded_file)
    elif file_ext == "pdf":
        extracted_text = extract_text_from_pdf(uploaded_file)
        extracted_images = extract_images_from_pdf(uploaded_file)
    elif file_ext == "pptx":
        extracted_text = extract_text_from_pptx(uploaded_file)
    elif file_ext in ["mp3", "wav", "m4a"]:
        extracted_text = f"🔊 Audio file uploaded: {uploaded_file.name} (transcription not yet supported)."

    if extracted_text:
        st.subheader("📄 Extracted Text")
        st.write(extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else ""))

    if extracted_images:
        st.subheader("🖼️ Extracted Images")
        for img in extracted_images:
            st.image(img, use_container_width=True)

# Handle chat input or extracted text
if user_input or extracted_text:
    st.subheader("🤖 AI Assistant Response")

    query = user_input if user_input else extracted_text
    ai_response = ask_ai(query)
    st.write(ai_response)

    # Voice generation (English by default, switch to Arabic if input seems Arabic)
    st.subheader("🎙️ AI Voice Response")
    lang = "ar" if any("\u0600" <= ch <= "\u06FF" for ch in ai_response) else "en"
    audio_file = generate_tts(ai_response, lang=lang)
    st.audio(audio_file, format="audio/mp3")

    # References section
    st.subheader("📚 Medical References")
    st.markdown("""
    - [CDC - Centers for Disease Control and Prevention](https://www.cdc.gov)
    - [WHO - World Health Organization](https://www.who.int)
    - [PubMed - Biomedical Literature](https://pubmed.ncbi.nlm.nih.gov)
    """)

