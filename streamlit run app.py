import os
import re
import streamlit as st
from io import BytesIO
from datetime import datetime
from PIL import Image
import fitz  # PyMuPDF
from pptx import Presentation
import tempfile
from gtts import gTTS
from streamlit_webrtc import webrtc_streamer, WebRtcMode

# --- Optional dependency for Word download ---
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# ----------------------------
# Load API Key (fixed)
# ----------------------------
api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
if not api_key:
    st.error("❌ API key not found. Please set GROQ_API_KEY in Streamlit secrets or environment variables.")
else:
    from groq import Groq
    client = Groq(api_key=api_key)

# ----------------------------
# Page Config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ----------------------------
# Session State
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ----------------------------
# Language Selection
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
    st.title("🧠 AI Sales Call Assistant (Voice + Text)")

# ----------------------------
# Brand & Product Data
# ----------------------------
gsk_brands = {
    "Shingrix": "https://www.cdc.gov/shingles/hcp/clinical-overview",
    "Trelegy": "https://www.gsk.com/en-gb/products/trelegy/",
    "Zejula": "https://www.gsk.com/en-gb/products/zejula/"
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
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
gsk_approaches = ["Use data-driven evidence", "Focus on patient outcomes", "Leverage storytelling techniques"]
sales_call_flow = ["Prepare", "Engage", "Create Opportunities", "Drive Impact", "Post Call Analysis"]
apact_steps = ["Acknowledge", "Probing", "Answer", "Confirm", "Transition"]

# ----------------------------
# Sidebar
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
# PDF / PPT Upload & Extraction
# ----------------------------
uploaded_pdf = st.sidebar.file_uploader("Upload brand PDF", type="pdf")
uploaded_ppt = st.sidebar.file_uploader("Upload brand PPT", type=["pptx", "ppt"])

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
                if shape.shape_type == 13:  # Picture
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

# ----------------------------
# Clear Chat
# ----------------------------
if st.button("🗑️ Clear Chat / مسح المحادثة"):
    st.session_state.chat_history = []

# ----------------------------
# Display Chat
# ----------------------------
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()
def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time", "")
        content = msg["content"].replace('\n','<br>').strip()
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

# ----------------------------
# Voice Input
# ----------------------------
st.subheader("🎙️ Record Your Voice")
webrtc_ctx = webrtc_streamer(
    key="speech",
    mode=WebRtcMode.SENDRECV,
    audio_receiver_size=1024,
    media_stream_constraints={"audio": True, "video": False},
)
rep_voice_text = None
if webrtc_ctx and webrtc_ctx.audio_receiver:
    audio_frames = webrtc_ctx.audio_receiver.get_frames(timeout=1)
    if audio_frames:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
            tmp_wav.write(audio_frames[0].to_ndarray().tobytes())
            audio_path = tmp_wav.name
        transcript = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=open(audio_path, "rb")
        )
        rep_voice_text = transcript.text
        st.success(f"🗣️ You said: {rep_voice_text}")

# ----------------------------
# Chat Input
# ----------------------------
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message... (or use voice above)", key="user_input_box")
    submitted = st.form_submit_button("➤")

if (submitted and user_input.strip()) or rep_voice_text:
    rep_message = rep_voice_text if rep_voice_text else user_input
    st.session_state.chat_history.append({"role": "user", "content": rep_message, "time": datetime.now().strftime("%H:%M")})

    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)
    references = f"""
1. {brand} Official References.
2. CDC Clinical Overview: https://www.cdc.gov/shingles/hcp/clinical-overview
"""
    prompt = f"""
Language: {language}
User input: {rep_message}
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
Embed PDF/PPT visuals.
Provide step-by-step actionable suggestions.
Response Length: {response_length}
Response Tone: {response_tone}
"""

    # Call Groq Chat API
    if api_key:
        try:
            response = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role":"system","content":f"You are a helpful sales assistant chatbot that responds in {language}."},
                          {"role":"user","content":prompt}],
                temperature=0.7
            )
            ai_output = response.choices[0].message.content
            st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M")})

            # AI voice reply
            tts = gTTS(ai_output, lang="ar" if language=="العربية" else "en")
            audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            tts.save(audio_file.name)
            st.audio(audio_file.name, format="audio/mp3")
            display_chat()

        except Exception as e:
            st.error(f"❌ AI request failed: {e}")

# ----------------------------
# Word Download
# ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = BytesIO()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")

# ----------------------------
# Brand Leaflet
# ----------------------------
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
