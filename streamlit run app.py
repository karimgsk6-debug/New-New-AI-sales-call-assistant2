import streamlit as st
from PIL import Image
from io import BytesIO, BytesIO as io_bytes
import fitz  # PyMuPDF
from pptx import Presentation
import tempfile
from datetime import datetime
from gtts import gTTS
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import os

# Optional Word download
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# --- Groq API (replace YOUR_API_KEY with your actual key) ---
import groq
from groq import Groq
client = Groq(api_key="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")

# --- Session State ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Language selection ---
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])

# --- GSK Logo ---
logo_local_path = "images/gsk_logo.png"
logo_fallback_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
col1, col2 = st.columns([1, 5])
with col1:
    try:
        logo_img = Image.open(logo_local_path)
        st.image(logo_img, width=120)
    except:
        st.image(logo_fallback_url, width=120)
with col2:
    st.title("🧠 AI Sales Call Assistant (Voice + Text)")

# --- HCP Segments, Persona, Barriers, etc. ---
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

# --- Sidebar Filters & Uploads (lower left) ---
with st.sidebar:
    st.header("Filters & Options")
    brand = st.selectbox("Select Brand / اختر العلامة التجارية", options=["Shingrix","Trelegy","Zejula"])
    segment = st.selectbox("Select RACE Segment / اختر شريحة RACE", race_segments)
    barrier = st.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective / اختر الهدف", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", options=specialties)
    persona = st.selectbox("Select HCP Persona / اختر شخصية الطبيب", options=personas)
    response_length = st.selectbox("Response Length / اختر طول الرد", ["Short", "Medium", "Long"])
    response_tone = st.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])
    interface_mode = st.radio("Interface Mode / اختر واجهة", ["Chatbot", "Card Dashboard", "Flow Visualization"])
    
    uploaded_pdf = st.file_uploader("Upload Brand PDF", type="pdf")
    uploaded_ppt = st.file_uploader("Upload Brand PPT", type=["pptx","ppt"])

# --- Extract visuals ---
def extract_pdf_images(pdf_file):
    images = []
    try:
        doc = fitz.open(pdf_file)
        for page in doc:
            for img in page.get_images(full=True):
                xref = img[0]
                base_image = doc.extract_image(xref)
                images.append(Image.open(BytesIO(base_image["image"])))
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
                    images.append(Image.open(BytesIO(shape.image.blob)))
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

# --- Clear Chat ---
if st.button("🗑️ Clear Chat / مسح المحادثة"):
    st.session_state.chat_history = []

# --- Chat Display ---
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()
def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time","")
        content = msg["content"].replace("\n","<br>").strip()
        if msg["role"]=="user":
            chat_html += f"""
            <div style='display:flex; justify-content:flex-end; margin:5px;'>
                <div style='background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; border:2px solid #888; max-width:70%; display:flex; align-items:flex-start;'>
                    <div style='flex:1;'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>
                </div>
            </div>"""
        else:
            chat_html += f"""
            <div style='display:flex; justify-content:flex-start; margin:5px;'>
                <div style='background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; border:2px solid #888; max-width:70%; display:flex; align-items:flex-start;'>
                    <div style='flex:1;'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>
                </div>
            </div>"""
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)
display_chat()

# --- Voice Recording (WhatsApp style) ---
st.subheader("🎙️ Record Your Voice Message")
webrtc_ctx = webrtc_streamer(
    key="voice",
    mode=WebRtcMode.SENDRECV,
    audio_receiver_size=1024,
    media_stream_constraints={"audio": True, "video": False},
)

rep_voice_text = None
if webrtc_ctx and webrtc_ctx.audio_receiver:
    frames = webrtc_ctx.audio_receiver.get_frames(timeout=1)
    if frames:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
            tmp_wav.write(frames[0].to_ndarray().tobytes())
            audio_path = tmp_wav.name
        # Transcription via Groq Whisper
        transcript = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=open(audio_path,"rb")
        )
        rep_voice_text = transcript.text
        st.text_area("Your voice converted to text:", value=rep_voice_text, height=80)

# --- Chat Input ---
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message or use voice above")
    submitted = st.form_submit_button("Send")

if (submitted and user_input.strip()) or rep_voice_text:
    rep_message = rep_voice_text if rep_voice_text else user_input
    st.session_state.chat_history.append({"role":"user","content":rep_message,"time":datetime.now().strftime("%H:%M")})

    references = """1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information. Approval Date: 11-9-2023. Version: GDS07/IPI02.
2. CDC Shingrix Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html
3. Strezova et al., 2022. Long-term Protection Against Herpes Zoster: https://doi.org/10.1093/ofid/ofac485
4. CDC Clinical Overview of Shingles: https://www.cdc.gov/shingles/hcp/clinical-overview/index.html
"""
    prompt = f"""
Language: {language}
User Input: {rep_message}
Segment: {segment}
Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Specialty: {specialty}
Persona: {persona}
Sales Approaches: {'; '.join(gsk_approaches)}
Sales Call Flow: {' → '.join(sales_call_flow)}
APACT Steps: {' → '.join(apact_steps)}
References: {references}
Embed PDF/PPT visuals if available.
Response Length: {response_length}
Response Tone: {response_tone}
"""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role":"system","content":f"You are a helpful AI sales assistant chatbot that responds in {language}."},
            {"role":"user","content":prompt}
        ],
        temperature=0.7
    )

    ai_output = response.choices[0].message.content
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M")})

    # Male storytelling voice
    tts = gTTS(text=ai_output, lang="en" if language=="English" else "ar", tld="co.uk")
    audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(audio_file.name)
    st.audio(audio_file.name, format="audio/mp3")

    display_chat()

# --- Word Download ---
if DOCX_AVAILABLE and st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response",0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io_bytes()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")
