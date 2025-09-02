# --- Safe Imports ---
try:
    import re as regex
except ImportError:
    raise RuntimeError("⚠️ Python 're' library missing. Ensure file not named 're.py'.")

import streamlit as st
from PIL import Image
from io import BytesIO, BytesIO as io_bytes
from datetime import datetime
import tempfile

# PDF/PPT
import fitz
from pptx import Presentation

# Voice support
try:
    from gtts import gTTS
    from streamlit_webrtc import webrtc_streamer, WebRtcMode
except ImportError:
    st.warning("⚠️ Voice features disabled. Install gtts + streamlit-webrtc.")
    gTTS = None
    webrtc_streamer = None
    WebRtcMode = None

# Optional Word download
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# --- Initialize Groq client ---
import groq
client = Groq(api_key="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")  # replace with your API key

# --- Session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Language selection ---
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

# --- Brand & product data ---
gsk_brands = {
    "Shingrix": "https://www.cdc.gov/shingles/hcp/clinical-overview",
    "Trelegy": "https://www.gsk.com/en-gb/products/trelegy/",
    "Zejula": "https://www.gsk.com/en-gb/products/zejula/"
}

# --- Filters & options ---
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
response_tone = st.sidebar.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])
interface_mode = st.sidebar.radio("Interface Mode / اختر واجهة", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# --- Upload PDF / PPT ---
uploaded_pdf = st.sidebar.file_uploader("Upload brand PDF", type="pdf")
uploaded_ppt = st.sidebar.file_uploader("Upload brand PPT", type=["pptx", "ppt"])

# --- Extract images ---
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
                if shape.shape_type == 13:  # Picture
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
if st.button("🗑️ Clear Chat / مسح المحادثة"):
    st.session_state.chat_history = []

# --- Chat bubble display ---
chat_placeholder = st.empty()
def render_message(message, sender="ai"):
    timestamp = datetime.now().strftime("%H:%M")
    if sender=="user":
        icon="https://img.icons8.com/ios-filled/50/000000/user.png"
        align="flex-end"
        bg="#dcf8c6"
        radius="15px 15px 0px 15px"
    else:
        icon="https://img.icons8.com/emoji/48/000000/robot-emoji.png"
        align="flex-start"
        bg="#f0f2f6"
        radius="15px 15px 15px 0px"
    chat_placeholder.markdown(f"""
    <div style='display:flex; justify-content:{align}; margin:5px;'>
        <div style='background:{bg}; padding:10px; border-radius:{radius}; max-width:80%; border:1px solid #ccc; display:flex; align-items:flex-start;'>
            <img src="{icon}" width="25" style='margin-right:10px'/>
            <div style='flex:1;'>{message}<div style='font-size:10px; color:gray; text-align:right'>{timestamp}</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def display_chat():
    for msg in st.session_state.chat_history:
        render_message(msg["content"], sender=msg["role"])

# --- Voice Input ---
rep_voice_text = None
if webrtc_streamer:
    st.subheader("🎙️ Record Your Voice")
    ctx = webrtc_streamer(key="speech", mode=WebRtcMode.SENDRECV, media_stream_constraints={"audio": True, "video": False})
    if ctx and ctx.audio_receiver:
        frames = ctx.audio_receiver.get_frames(timeout=1)
        if frames:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
                tmp_wav.write(frames[0].to_ndarray().tobytes())
                audio_path = tmp_wav.name
            # --- Transcribe via Groq Whisper ---
            transcript = client.audio.transcriptions.create(model="whisper-large-v3", file=open(audio_path,"rb"))
            rep_voice_text = transcript.text
            st.success(f"🗣️ You said: {rep_voice_text}")

# --- Chat input form ---
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message or scenario here...")
    submitted = st.form_submit_button("➤")

if (submitted and user_input.strip()) or rep_voice_text:
    rep_message = rep_voice_text if rep_voice_text else user_input
    st.session_state.chat_history.append({"role":"user","content":rep_message})

    # --- Construct Groq Prompt ---
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
Sales Call Flow Steps (rep should follow): {', '.join(sales_call_flow)}
APCT Steps (only to handle objections): {', '.join(apact_steps)}
Embed PDF/PPT visuals if relevant.
Provide step-by-step actionable guidance in 'thinking guide' style.
Response Tone: {response_tone}
Response Length: {response_length}
"""

    # --- Groq AI Response ---
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role":"system","content":f"You are a helpful sales assistant chatbot that responds in {language}."},
                  {"role":"user","content":prompt}],
        temperature=0.7
    )
    ai_output = response.choices[0].message.content
    st.session_state.chat_history.append({"role":"ai","content":ai_output})

    # --- AI voice reply ---
    if gTTS:
        tts = gTTS(ai_output, lang="en" if language=="English" else "ar")
        audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(audio_file.name)
        st.audio(audio_file.name, format="audio/mp3")

    display_chat()

# --- Word download ---
if DOCX_AVAILABLE and st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io_bytes()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")

# --- Brand leaflet ---
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
