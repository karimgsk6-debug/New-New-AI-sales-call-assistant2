import streamlit as st
from PIL import Image
from io import BytesIO, BytesIO as io_bytes
import fitz  # PyMuPDF
from pptx import Presentation
import tempfile
from datetime import datetime
import re
from gtts import gTTS
from streamlit_webrtc import webrtc_streamer, WebRtcMode
from streamlit_mic_recorder import mic_recorder
import groq
from groq import Groq

# --- API Key (replace with your actual key) ---
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# --- Session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Language ---
language = st.radio("Select Language / اختر اللغة", ["English", "العربية"])

# --- GSK Logo ---
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
    st.title("🧠 AI Sales Call Assistant (Voice + Text)")

# --- Brands & Products ---
gsk_brands = {
    "Shingrix": "https://www.cdc.gov/shingles/hcp/clinical-overview",
    "Trelegy": "https://www.gsk.com/en-gb/products/trelegy/",
    "Zejula": "https://www.gsk.com/en-gb/products/zejula/"
}

# --- HCP / RACE / Barriers ---
race_segments = [
    "R – Reach: Did not start prescribing yet",
    "A – Acquisition: Prescribe when patient initiates discussion",
    "C – Conversion: Proactively discuss with specific patient profiles",
    "E – Engagement: Proactively prescribe to different patient profiles"
]
doctor_barriers = [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ Vx effective",
    "Accessibility issues"
]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
gsk_approaches = ["Use data-driven evidence", "Focus on patient outcomes", "Leverage storytelling techniques"]
sales_call_flow = ["Prepare", "Engage", "Create Opportunities", "Drive Impact", "Post Call Analysis"]
apact_steps = ["Acknowledge", "Probing", "Answer", "Confirm", "Transition"]

# --- Sidebar filters ---
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand", list(gsk_brands.keys()))
segment = st.sidebar.selectbox("Select RACE Segment", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barrier", doctor_barriers, default=[])
objective = st.sidebar.selectbox("Select Objective", objectives)
specialty = st.sidebar.selectbox("Select Doctor Specialty", specialties)
persona = st.sidebar.selectbox("Select HCP Persona", personas)
response_length = st.sidebar.selectbox("Response Length", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])
interface_mode = st.sidebar.radio("Interface Mode", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# --- Upload PDF/PPT ---
uploaded_pdf = st.sidebar.file_uploader("Upload brand PDF", type="pdf")
uploaded_ppt = st.sidebar.file_uploader("Upload brand PPT", type=["pptx","ppt"])

# --- Extract visuals ---
def extract_pdf_images(pdf_file):
    images = []
    try:
        doc = fitz.open(pdf_file)
        for page in doc:
            for img in page.get_images(full=True):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                images.append(Image.open(BytesIO(image_bytes)))
    except:
        st.warning("⚠️ Could not extract images from PDF")
    return images

def extract_ppt_images(ppt_file):
    images = []
    try:
        prs = Presentation(ppt_file)
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.shape_type == 13:
                    image = shape.image
                    images.append(Image.open(BytesIO(image.blob)))
    except:
        st.warning("⚠️ Could not extract images from PPT")
    return images

pdf_images = extract_pdf_images(uploaded_pdf) if uploaded_pdf else []
ppt_images = extract_ppt_images(uploaded_ppt) if uploaded_ppt else []
all_images = pdf_images + ppt_images
if all_images:
    st.subheader("Uploaded Brand Visuals")
    for img in all_images:
        st.image(img, width=300)

# --- Clear chat ---
if st.button("🗑️ Clear Chat"):
    st.session_state.chat_history = []

# --- Chat display ---
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()
def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n","<br>")
        time = msg.get("time","")
        if msg["role"]=="user":
            chat_html += f"<div style='text-align:right;background:#dcf8c6;padding:8px;margin:5px;border-radius:10px;'>{content}<br><span style='font-size:10px;color:gray'>{time}</span></div>"
        else:
            chat_html += f"<div style='text-align:left;background:#f0f2f6;padding:8px;margin:5px;border-radius:10px;'>{content}<br><span style='font-size:10px;color:gray'>{time}</span></div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)
display_chat()

# =========================
# REP Input: Voice + Text
# =========================
st.subheader("🗣️ Record or Type Your Message")

audio = mic_recorder(start_prompt="🎙️ Start Recording", stop_prompt="⏹️ Stop Recording", key="recorder")
rep_input_text = ""

if audio:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
        tmp_wav.write(audio["bytes"])
        audio_path = tmp_wav.name
    with open(audio_path,"rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=audio_file
        )
        rep_input_text = transcript.text
        st.success(f"✅ Voice-to-Text: {rep_input_text}")

rep_manual_text = st.text_area("Or type your message here:", "")
if rep_manual_text.strip():
    rep_input_text += " " + rep_manual_text.strip()

# =========================
# Submit message
# =========================
if st.button("Send") and rep_input_text.strip():
    st.session_state.chat_history.append({"role":"user","content":rep_input_text,"time":datetime.now().strftime("%H:%M")})
    
    # --- Prepare prompt for AI ---
    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)
    references = f"""
1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information.
2. CDC Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html
"""
    prompt = f"""
Language: {language}
User input: {rep_input_text}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Brand: {brand}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Approved Sales Approaches:
{approaches_str}
Sales Call Flow Steps:
{flow_str}
APACT Steps:
Acknowledge → Probing → Answer → Confirm → Transition
Use APACT only where relevant.
References:
{references}
Embed PDF/PPT visuals.
Provide actionable suggestions step by step.
Response Length: {response_length}
Response Tone: {response_tone}
"""

    # --- Get AI response ---
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role":"system","content":f"You are a helpful sales assistant chatbot that responds in {language}."},
            {"role":"user","content":prompt}
        ],
        temperature=0.7
    )
    ai_output = response.choices[0].message.content
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M")})

    # --- AI voice ---
    tts = gTTS(ai_output, lang="en" if language=="English" else "ar")
    audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(audio_file.name)
    st.audio(audio_file.name, format="audio/mp3")

    display_chat()

# --- Word Download ---
try:
    from docx import Document
    if st.session_state.chat_history:
        latest_ai = [m["content"] for m in st.session_state.chat_history if m["role"]=="ai"]
        if latest_ai:
            doc = Document()
            doc.add_heading("AI Sales Call Response",0)
            doc.add_paragraph(latest_ai[-1])
            word_buffer = io_bytes()
            doc.save(word_buffer)
            st.download_button("📥 Download AI Response", word_buffer.getvalue(), "AI_Response.docx")
except ImportError:
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# --- Brand Leaflet ---
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
