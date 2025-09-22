import os
import io
import asyncio
import streamlit as st
import requests
from PIL import Image
from docx import Document
import pdfplumber
from pptx import Presentation
from datetime import datetime
from edge_tts import Communicate
from groq import Groq

# ----------------------------
# App Configuration
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ----------------------------
# Groq API Setup
# ----------------------------
GROQ_API_KEY = "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"  # Replace with your key
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

async def generate_arabic_voice(text, filename="arabic.mp3"):
    communicate = Communicate(text, voice="ar-EG-HodaNeural")  # Human-like Arabic voice
    await communicate.save(filename)
    return filename

def generate_english_tts(text, filename="output.mp3"):
    try:
        from gtts import gTTS
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
# Filters & Options
# ----------------------------
race_segments = [
    "R – Reach: Did not start to prescribe yet and Don't believe that vaccination is his responsibility.",
    "A – Acquisition: Prescribe to patient who initiate discussion about the vaccine but Convinced about Shingrix data.",
    "C – Conversion: Proactively initiate discussion with specific patient profile but For other patient profiles he is not prescribing yet.",
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
personas = [
    "Uncommitted Vaccinator",
    "Reluctant Efficiency",
    "Patient Influenced",
    "Committed Vaccinator"
]
gsk_approaches = [
    "Use data-driven evidence",
    "Focus on patient outcomes",
    "Leverage storytelling techniques"
]
sales_call_flow = ["Prepare", "Engage", "Create Opportunities", "Influence", "Drive Impact", "Post Call Analysis"]

# ----------------------------
# Sidebar Filters (multi-select enabled)
# ----------------------------
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
segment = st.sidebar.selectbox("Select RACE Segment / اختر شريحة RACE", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", options=doctor_barriers, default=[])
objective = st.sidebar.selectbox("Select Objective / اختر الهدف", options=objectives)
specialty = st.sidebar.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", options=specialties)
persona = st.sidebar.selectbox("Select HCP Persona / اختر شخصية الطبيب", options=personas)
response_length = st.sidebar.selectbox("Response Length / اختر طول الرد", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])
interface_mode = st.sidebar.radio("Interface Mode / اختر واجهة", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# ----------------------------
# Display brand image
# ----------------------------
image_path = gsk_brands_images.get(brand)
try:
    if image_path.startswith("http"):
        response = requests.get(image_path)
        img = Image.open(io.BytesIO(response.content))
    else:
        img = Image.open(image_path)
    st.image(img, width=200)
except:
    st.warning(f"⚠️ Could not load image for {brand}. Using placeholder.")
    st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)

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
# Chat Interface (bottom-fixed)
# ----------------------------
chat_placeholder = st.empty()
input_container = st.empty()

def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time", "")
        content = msg["content"].replace("\n", "<br>")
        if msg["role"] == "user":
            chat_html += f"<div style='text-align:right; background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; margin:5px; max-width:80%; display:inline-block'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>"
        else:
            chat_html += f"<div style='text-align:left; background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; margin:5px; max-width:80%; display:inline-block'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

# ----------------------------
# Input form pinned at bottom
# ----------------------------
with input_container.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("", placeholder="Type your message...", key="user_input_box")
    submitted = st.form_submit_button("Send")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})
    display_chat()

    # Build prompt
    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)
    references = (
        "1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information. Approval Date: 11-9-2023. Version: GDS07/IPI02.\n"
        "2. CDC Shingrix Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html\n"
        "3. Strezova et al., 2022. Long-term Protection Against Herpes Zoster: https://doi.org/10.1093/ofid/ofac485\n"
        "4. CDC Clinical Overview of Shingles: https://www.cdc.gov/shingles/hcp/clinical-overview/index.html"
    )
    prompt = f"""
Language: {language}
User input: {user_input}
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
References:
{references}
Use APACT (Acknowledge → Probing → Answer → Confirm → Transition) technique for handling objections.
Response Length: {response_length}
Response Tone: {response_tone}
Provide actionable suggestions tailored to this persona in a friendly and professional manner.
"""
    # Get AI output
    ai_output = ask_ai(prompt)

    # Word-by-word streaming
    current_text = ""
    for word in ai_output.split():
        current_text += word + " "
        if st.session_state.chat_history[-1]["role"] == "ai":
            st.session_state.chat_history[-1]["content"] = current_text
        else:
            st.session_state.chat_history.append({"role": "ai", "content": current_text, "time": datetime.now().strftime("%H:%M")})
        display_chat()
        asyncio.sleep(0.1)

    # TTS
    if language == "العربية":
        asyncio.run(generate_arabic_voice(ai_output))
        st.audio("arabic.mp3", format="audio/mp3")
    else:
        audio_file = generate_english_tts(ai_output)
        if audio_file:
            st.audio(audio_file, format="audio/mp3")

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

# ----------------------------
# Brand Leaflet
# ----------------------------
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
