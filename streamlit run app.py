# app.py
import os
import io
import streamlit as st
import requests
from PIL import Image
from docx import Document
import pdfplumber
import fitz  # PyMuPDF
from pptx import Presentation
from datetime import datetime
from groq import Groq

# ----------------------------
# App config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

st.title("🧠 AI Sales Call Assistant (Light + TTS)")

# ----------------------------
# Groq API setup
# ----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
if GROQ_API_KEY == "your_groq_api_key_here" or not GROQ_API_KEY:
    st.warning("⚠️ GROQ_API_KEY not set. Set GROQ_API_KEY as an environment variable or replace the placeholder in code.")
client = Groq(api_key=GROQ_API_KEY)

# ----------------------------
# References (will be included in prompts)
# ----------------------------
REFERENCE_TEXT = (
    "References:\n"
    "1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information. Approval Date: 11-9-2023. Version: GDS07/IPI02.\n"
    "2. CDC Shingrix Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html\n"
    "3. Strezova et al., 2022. Long-term Protection Against Herpes Zoster: https://doi.org/10.1093/ofid/ofac485\n"
    "4. CDC Clinical Overview of Shingles: https://www.cdc.gov/shingles/hcp/clinical-overview/index.html\n"
)

# ----------------------------
# Helper functions
# ----------------------------
def extract_text_from_docx(file_obj):
    doc = Document(file_obj)
    return "\n".join([p.text for p in doc.paragraphs]).strip()

def extract_text_from_pdf(file_obj):
    text = ""
    try:
        with pdfplumber.open(file_obj) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        st.warning(f"Could not extract PDF text: {e}")
    return text.strip()

def extract_images_from_pdf(file_obj):
    images = []
    try:
        pdf = fitz.open(stream=file_obj.read(), filetype="pdf")
        for page_index in range(len(pdf)):
            img_list = pdf[page_index].get_images(full=True)
            for img_meta in img_list:
                xref = img_meta[0]
                base_image = pdf.extract_image(xref)
                image_bytes = base_image["image"]
                images.append(Image.open(io.BytesIO(image_bytes)))
    except Exception as e:
        st.warning(f"Could not extract images from PDF: {e}")
    return images

def extract_text_from_pptx(file_obj):
    text_runs = []
    try:
        prs = Presentation(file_obj)
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text:
                    text_runs.append(shape.text)
    except Exception as e:
        st.warning(f"Could not extract PPTX text: {e}")
    return "\n".join(text_runs).strip()

def generate_tts(text: str, lang: str = "en", filename: str = "ai_response.mp3"):
    """
    Create speech from text using gTTS.
    Imported inside function to avoid import-time crash if gTTS not installed.
    Returns filename or None on failure.
    """
    try:
        from gtts import gTTS  # import here to avoid ModuleNotFoundError at startup
    except Exception:
        st.warning("⚠️ gTTS not installed. TTS unavailable. Add 'gTTS' to requirements if you want audio replies.")
        return None

    try:
        tts = gTTS(text=text, lang=lang)
        tts.save(filename)
        return filename
    except Exception as e:
        st.warning(f"⚠️ TTS generation failed: {e}")
        return None

def ask_ai(prompt: str):
    """Query Groq API and return text response (safe access)."""
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
        # Access message content as attribute
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"AI request failed: {e}")
        return f"⚠️ AI request failed: {e}"

# ----------------------------
# Session state (chat history + uploaded docs)
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # list of dicts: {"role","content","time"}
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = ""

# ----------------------------
# Sidebar filters (kept light)
# ----------------------------
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Brand", options=["Shingrix", "Trelegy", "Zejula"])
persona = st.sidebar.selectbox("HCP Persona", options=["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"])
response_tone = st.sidebar.selectbox("Response Tone", options=["Formal", "Casual", "Friendly", "Persuasive"])
response_length = st.sidebar.selectbox("Response Length", options=["Short", "Medium", "Long"])
language = st.sidebar.radio("Language / اختر اللغة", options=["English", "العربية"])

# ----------------------------
# Logo & header area
# ----------------------------
col1, col2 = st.columns([1, 5])
with col1:
    logo_path = "images/gsk_logo.png"
    if os.path.exists(logo_path):
        st.image(logo_path, width=120)
    else:
        st.image("https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png", width=120)
with col2:
    st.markdown("### AI Sales Call Assistant — quick mode (TTS replies, document parsing)")

# ----------------------------
# File uploader: PDF / DOCX / PPTX / Audio
# ----------------------------
st.subheader("📤 Upload supporting document or voice")
uploaded_file = st.file_uploader("Upload PDF, DOCX, PPTX, or Audio (MP3/WAV/M4A). Audio transcription not implemented.", type=["pdf","docx","pptx","mp3","wav","m4a"])

if uploaded_file:
    ext = uploaded_file.name.split(".")[-1].lower()
    extracted_text = ""
    extracted_images = []

    if ext == "docx":
        extracted_text = extract_text_from_docx(uploaded_file)
    elif ext == "pdf":
        # Need to reset stream for fitz usage, so read bytes for fitz and reuse with pdfplumber via BytesIO
        b = uploaded_file.read()
        extracted_images = extract_images_from_pdf(io.BytesIO(b))
        # pdfplumber expects a file-like object, so use BytesIO
        extracted_text = extract_text_from_pdf(io.BytesIO(b))
    elif ext == "pptx":
        extracted_text = extract_text_from_pptx(uploaded_file)
    elif ext in ("mp3","wav","m4a"):
        extracted_text = f"🔊 Audio uploaded: {uploaded_file.name} — transcription not implemented."
        # also provide playback
        st.audio(uploaded_file)

    # store for later prompts (truncate to reasonable size)
    st.session_state.uploaded_docs = (extracted_text or "")[:8000]

    if extracted_text:
        st.subheader("📄 Extracted / Uploaded Text")
        st.text_area("Preview (truncated)", extracted_text[:4000], height=200)

    if extracted_images:
        st.subheader("🖼️ Extracted Images")
        for img in extracted_images:
            st.image(img, use_column_width=True)

    # Offer immediate AI response to the document content
    if extracted_text:
        st.subheader("🤖 AI summary / response (from uploaded text)")
        prompt_for_doc = (
            f"Language: {language}\n"
            f"Brand: {brand}\n"
            f"HCP Persona: {persona}\n"
            f"Response Tone: {response_tone}\n"
            f"Response Length: {response_length}\n\n"
            f"Supporting Document Content:\n{extracted_text}\n\n"
            f"{REFERENCE_TEXT}\n\n"
            "Provide concise, actionable suggestions a medical sales rep can use in a call."
        )
        ai_resp = ask_ai(prompt_for_doc)
        st.write(ai_resp)
        # TTS
        tts_lang = "ar" if language == "العربية" else "en"
        audio_path = generate_tts(ai_resp, lang=tts_lang)
        if audio_path:
            st.audio(audio_path, format="audio/mp3")
        # add to chat history
        st.session_state.chat_history.append({"role":"user","content":"Uploaded document","time":datetime.now().strftime("%H:%M")})
        st.session_state.chat_history.append({"role":"ai","content":ai_resp,"time":datetime.now().strftime("%H:%M")})

# ----------------------------
# Chat / WhatsApp-like input
# ----------------------------
st.subheader("💬 Ask the AI (type below)")
def display_chat():
    if not st.session_state.chat_history:
        st.info("No conversation yet — type a question or upload a document to begin.")
        return
    for msg in st.session_state.chat_history:
        role = msg["role"]
        time = msg.get("time","")
        content = msg["content"]
        if role == "user":
            st.markdown(f"<div style='text-align:right;background:#dcf8c6;padding:10px;border-radius:12px;margin:6px;'><b>You</b><br>{content}<div style='font-size:10px;color:gray'>{time}</div></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='text-align:left;background:#f0f2f6;padding:10px;border-radius:12px;margin:6px;'><b>AI</b><br>{content}<div style='font-size:10px;color:gray'>{time}</div></div>", unsafe_allow_html=True)

display_chat()

with st.form("chat_form", clear_on_submit=True):
    user_message = st.text_input("Type your message (or paste a part of the uploaded doc)...")
    submit = st.form_submit_button("Send")
if submit and user_message:
    # append user message
    st.session_state.chat_history.append({"role":"user","content":user_message,"time":datetime.now().strftime("%H:%M")})

    # build prompt (including references and any uploaded doc snippet)
    combined_prompt = (
        f"Language: {language}\n"
        f"Brand: {brand}\n"
        f"HCP Persona: {persona}\n"
        f"Response Tone: {response_tone}\n"
        f"Response Length: {response_length}\n\n"
        f"User question:\n{user_message}\n\n"
    )
    if st.session_state.uploaded_docs:
        combined_prompt += f"Supporting documents (truncated):\n{st.session_state.uploaded_docs}\n\n"
    combined_prompt += REFERENCE_TEXT
    combined_prompt += "\nUse APACT (Acknowledge → Probing → Answer → Confirm → Transition). Provide actionable suggestions."

    # call AI
    ai_answer = ask_ai(combined_prompt)
    st.session_state.chat_history.append({"role":"ai","content":ai_answer,"time":datetime.now().strftime("%H:%M")})
    # show updated chat
    display_chat()

    # TTS
    tts_lang = "ar" if language == "العربية" else "en"
    audio_file = generate_tts(ai_answer, lang=tts_lang)
    if audio_file:
        st.audio(audio_file, format="audio/mp3")

# ----------------------------
# Download chat as Word
# ----------------------------
if st.session_state.chat_history:
    latest_ai_items = [m for m in st.session_state.chat_history if m["role"]=="ai"]
    if latest_ai_items:
        if st.button("📥 Download latest AI response as Word (.docx)"):
            doc = Document()
            doc.add_heading("AI Sales Call Assistant - Conversation", level=1)
            for m in st.session_state.chat_history:
                doc.add_paragraph(f"{m['role'].upper()} ({m['time']}):\n{m['content']}\n")
            buf = io.BytesIO()
            doc.save(buf)
            st.download_button("Download .docx", data=buf.getvalue(), file_name="AI_Conversation.docx")

# ----------------------------
# Footer / brand leaflet link
# ----------------------------
st.markdown(f"[Brand Leaflet - {brand}](https://example.com/{brand.lower()})")
st.caption("Note: Audio upload transcription not implemented in this lightweight version. TTS replies use gTTS (if installed).")
