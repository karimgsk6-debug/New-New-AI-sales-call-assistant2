import streamlit as st
from PIL import Image
from io import BytesIO, BytesIO as io_bytes
import fitz  # PDF
from pptx import Presentation
import tempfile
import os
from datetime import datetime
import re
from streamlit_webrtc import webrtc_streamer, WebRtcMode

# TTS with natural male voice (edge-tts)
import asyncio
import edge_tts

# Groq AI
import groq
from groq import Groq
client = Groq(api_key="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")  # <-- insert API key

# Optional Word download
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# --- Session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Language ---
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])

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

# --- Brands ---
gsk_brands = {
    "Shingrix": "https://www.cdc.gov/shingles/hcp/clinical-overview",
    "Trelegy": "https://www.gsk.com/en-gb/products/trelegy/",
    "Zejula": "https://www.gsk.com/en-gb/products/zejula/"
}

# --- Filters ---
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
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
gsk_approaches = ["Use data-driven evidence", "Focus on patient outcomes", "Leverage storytelling techniques"]
sales_call_flow = ["Prepare", "Engage", "Create Opportunities", "Drive Impact", "Post Call Analysis"]
apact_steps = ["Acknowledge", "Probing", "Answer", "Confirm", "Transition"]

# --- Sidebar filters ---
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
segment = st.sidebar.selectbox("Select RACE Segment / اختر شريحة RACE", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", options=doctor_barriers, default=[])
objective = st.sidebar.selectbox("Select Objective / اختر الهدف", options=objectives)
specialty = st.sidebar.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", options=specialties)
persona = st.sidebar.selectbox("Select HCP Persona / اختر شخصية الطبيب", options=personas)
response_length = st.sidebar.selectbox("Response Length / اختر طول الرد", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Storytelling"])

# --- Upload PDF / PPT ---
uploaded_pdf = st.sidebar.file_uploader("Upload brand PDF", type="pdf")
uploaded_ppt = st.sidebar.file_uploader("Upload brand PPT", type=["pptx", "ppt"])

def extract_pdf_text_images(pdf_file):
    text_content = ""
    images = []
    try:
        doc = fitz.open(pdf_file)
        for page in doc:
            text_content += page.get_text()
            for img in page.get_images(full=True):
                xref = img[0]
                base_image = doc.extract_image(xref)
                images.append(Image.open(BytesIO(base_image["image"])))
    except:
        st.warning("⚠️ Could not extract PDF content")
    return text_content, images

def extract_ppt_images(ppt_file):
    images = []
    text_content = ""
    try:
        prs = Presentation(ppt_file)
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.has_text_frame:
                    text_content += shape.text + "\n"
                if shape.shape_type == 13:  # Picture
                    images.append(Image.open(BytesIO(shape.image.blob)))
    except:
        st.warning("⚠️ Could not extract PPT content")
    return text_content, images

pdf_text, pdf_images = extract_pdf_text_images(uploaded_pdf) if uploaded_pdf else ("", [])
ppt_text, ppt_images = extract_ppt_images(uploaded_ppt) if uploaded_ppt else ("", [])
all_text = pdf_text + "\n" + ppt_text
all_images = pdf_images + ppt_images

# --- Display visuals ---
if all_images:
    st.subheader("Uploaded Visuals")
    for img in all_images:
        st.image(img, width=300)

# --- Clear chat ---
if st.button("🗑️ Clear Chat / مسح المحادثة"):
    st.session_state.chat_history = []

# --- Chat display ---
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()
def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time", "")
        content = msg["content"].replace('\n','<br>').strip()
        if msg["role"]=="user":
            chat_html += f"<div style='text-align:right;background:#dcf8c6;padding:10px;margin:5px;border-radius:15px;'>{content}<br><small>{time}</small></div>"
        else:
            chat_html += f"<div style='text-align:left;background:#f0f2f6;padding:10px;margin:5px;border-radius:15px;'>{content}<br><small>{time}</small></div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)
display_chat()

# --- Voice recording ---
st.subheader("🎙️ Leave a voice message or type your question")
rep_voice_text = st.text_input("Your transcribed question will appear here...")

webrtc_ctx = webrtc_streamer(
    key="rep_voice",
    mode=WebRtcMode.SENDRECV,
    audio_receiver_size=1024,
    media_stream_constraints={"audio": True, "video": False},
    async_processing=True
)

if webrtc_ctx and webrtc_ctx.audio_receiver:
    frames = webrtc_ctx.audio_receiver.get_frames(timeout=1)
    if frames:
        audio_file_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        frames[0].to_file(audio_file_path)
        try:
            transcript = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=open(audio_file_path,"rb")
            )
            rep_voice_text = transcript.text
            st.success(f"🗣️ You said: {rep_voice_text}")
        except:
            st.warning("⚠️ Could not transcribe voice")

# --- Chat input ---
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Or type your question...", key="user_input_box")
    submitted = st.form_submit_button("➤")

if (submitted and user_input.strip()) or rep_voice_text.strip():
    rep_message = rep_voice_text if rep_voice_text.strip() else user_input
    st.session_state.chat_history.append({"role":"user","content":rep_message,"time":datetime.now().strftime("%H:%M")})

    # --- References ---
    references = """1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information. Approval Date: 11-9-2023. Version: GDS07/IPI02.
2. CDC Shingrix Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html
3. Strezova et al., 2022. Long-term Protection Against Herpes Zoster: https://doi.org/10.1093/ofid/ofac485
4. CDC Clinical Overview of Shingles: https://www.cdc.gov/shingles/hcp/clinical-overview/index.html"""

    # --- Prompt ---
    numbered_text = re.sub(r'[\*\-\•]', '', all_text)
    prompt = f"""
Language: {language}
User input: {rep_message}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Brand: {brand}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Approved Sales Approaches: {', '.join(gsk_approaches)}
Sales Call Flow Steps: {' → '.join(sales_call_flow)}
APACT Steps: {' → '.join(apact_steps)}
References & extracted content: {numbered_text[:2000]} {references}
Response Length: {response_length}
Response Tone: {response_tone}
Provide step-by-step suggestions in numbered format.
Remove punctuation in AI voice output.
Storytelling, engaging male voice.
"""

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role":"system","content":f"You are a helpful sales assistant chatbot that responds in {language}."},
                {"role":"user","content":prompt}
            ],
            temperature=0.7
        )
        ai_output = response.choices[0].message.content
    except Exception as e:
        ai_output = f"⚠️ Error generating AI response: {str(e)}"

    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M")})
    display_chat()

    # --- Generate male storytelling voice (edge-tts) ---
    async def tts_play(text, file_path):
        communicate = edge_tts.Communicate(text, "en-US-GuyNeural")  # male, natural
        await communicate.save(file_path)

    audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    asyncio.run(tts_play(ai_output, audio_file.name))
    st.audio(audio_file.name, format="audio/mp3")

    # --- Word download ---
    if DOCX_AVAILABLE:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(ai_output)
        word_buffer = io_bytes()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")

# --- Brand leaflet ---
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
