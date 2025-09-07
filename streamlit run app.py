import streamlit as st
from PIL import Image
from io import BytesIO
import fitz  # PyMuPDF for PDF image extraction
from pptx import Presentation
import tempfile
from gtts import gTTS
from datetime import datetime
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import groq

# --------------------------
# Directly insert your API key
# --------------------------
GROQ_API_KEY = "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"
client = groq.Groq(api_key=GROQ_API_KEY)

# --------------------------
# Session state
# --------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --------------------------
# Language selection
# --------------------------
language = st.radio("Select Language / اختر اللغة", ["English", "العربية"])

# --------------------------
# GSK Logo
# --------------------------
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

# --------------------------
# Brand & product data
# --------------------------
gsk_brands = {
    "Shingrix": "https://www.cdc.gov/shingles/hcp/clinical-overview",
    "Trelegy": "https://www.gsk.com/en-gb/products/trelegy/",
    "Zejula": "https://www.gsk.com/en-gb/products/zejula/"
}

# --------------------------
# Filters & options
# --------------------------
race_segments = [
    "R – Reach",
    "A – Acquisition",
    "C – Conversion",
    "E – Engagement"
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

# --------------------------
# Sidebar filters
# --------------------------
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
segment = st.sidebar.selectbox("Select RACE Segment / اختر شريحة RACE", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", doctor_barriers)
objective = st.sidebar.selectbox("Select Objective / اختر الهدف", options=objectives)
specialty = st.sidebar.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", specialties)
persona = st.sidebar.selectbox("Select HCP Persona / اختر شخصية الطبيب", personas)
response_length = st.sidebar.selectbox("Response Length / اختر طول الرد", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])
interface_mode = st.sidebar.radio("Interface Mode / اختر واجهة", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# --------------------------
# Upload PDF / PPT
# --------------------------
uploaded_pdf = st.sidebar.file_uploader("Upload brand PDF", type="pdf")
uploaded_ppt = st.sidebar.file_uploader("Upload brand PPT", type=["pptx", "ppt"])

# --------------------------
# Extract images
# --------------------------
def extract_pdf_images(pdf_file):
    images = []
    try:
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        for page in doc:
            for img in page.get_images(full=True):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                images.append(Image.open(BytesIO(image_bytes)))
    except Exception as e:
        st.warning(f"⚠️ Could not extract images from PDF: {e}")
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
    except Exception as e:
        st.warning(f"⚠️ Could not extract images from PPT: {e}")
    return images

pdf_images = extract_pdf_images(uploaded_pdf) if uploaded_pdf else []
ppt_images = extract_ppt_images(uploaded_ppt) if uploaded_ppt else []
all_images = pdf_images + ppt_images

if all_images:
    st.subheader("Uploaded Brand Visuals")
    for img in all_images:
        st.image(img, width=300)

# --------------------------
# Clear chat
# --------------------------
if st.button("🗑️ Clear Chat / مسح المحادثة"):
    st.session_state.chat_history = []

# --------------------------
# Chat display
# --------------------------
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()

def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time", "")
        content = msg["content"].replace("\n","<br>")
        if msg["role"] == "user":
            chat_html += f"<div style='text-align:right;background:#dcf8c6;padding:10px;border-radius:10px;margin:5px;'>{content}<br><small>{time}</small></div>"
        else:
            chat_html += f"<div style='text-align:left;background:#f0f2f6;padding:10px;border-radius:10px;margin:5px;'>{content}<br><small>{time}</small></div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# --------------------------
# Voice input
# --------------------------
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
        st.text_input("🗣️ Your voice converted to text:", value=rep_voice_text, key="voice_text_box")

# --------------------------
# Chat input
# --------------------------
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message or use voice above", key="user_input_box")
    submitted = st.form_submit_button("➤")

if (submitted and user_input.strip()) or rep_voice_text:
    rep_message = rep_voice_text if rep_voice_text else user_input
    st.session_state.chat_history.append({
        "role": "user",
        "content": rep_message,
        "time": datetime.now().strftime("%H:%M")
    })

    # Prepare prompt for AI
    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)
    references = """
1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information
2. CDC Shingrix Recommendations
3. Strezova et al., 2022. Long-term Protection Against Herpes Zoster
4. CDC Clinical Overview of Shingles
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
APACT Steps:
{', '.join(apact_steps)}
References:
{references}
Include uploaded visuals if any.
Provide actionable step-by-step suggestions.
Response Length: {response_length}
Response Tone: {response_tone}
"""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role":"system","content":f"You are a helpful sales assistant chatbot that responds in {language}."},
            {"role":"user","content":prompt}
        ],
        temperature=0.7
    )

    ai_output = response.choices[0].message.content

    # Replace "*" with numbering for clarity
    numbered_output = ""
    for i, line in enumerate(ai_output.splitlines(), start=1):
        if line.strip():
            numbered_output += f"{i}. {line.strip()}\n"

    st.session_state.chat_history.append({
        "role": "ai",
        "content": numbered_output,
        "time": datetime.now().strftime("%H:%M")
    })

    # AI voice reply
    tts = gTTS(numbered_output, lang="en" if language=="English" else "ar")
    audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(audio_file.name)
    st.audio(audio_file.name, format="audio/mp3")

    display_chat()

# --------------------------
# Brand leaflet link
# --------------------------
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
