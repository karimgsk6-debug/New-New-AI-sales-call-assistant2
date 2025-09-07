import streamlit as st
from PIL import Image
from io import BytesIO, BytesIO as io_bytes
import fitz  # PyMuPDF
from pptx import Presentation
import tempfile
from datetime import datetime
from gtts import gTTS
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import base64
import groq

# -------------------------------
# CONFIG: Insert your GROQ API key
# -------------------------------
client = groq.Groq(api_key="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")  # <-- Replace with your key

# -------------------------------
# SESSION STATE
# -------------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# -------------------------------
# LANGUAGE
# -------------------------------
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])

# -------------------------------
# GSK LOGO
# -------------------------------
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

# -------------------------------
# DISCLAIMER
# -------------------------------
st.markdown("""
<small>
⚠️ **Disclaimer:** This AI Sales Assistant is designed to help and equip sales reps to handle HCP objections and generate better sales outcomes (GSO). All responses are AI-generated and should be critically reviewed and challenged for accuracy.
</small>
""", unsafe_allow_html=True)

# -------------------------------
# BRAND & PRODUCT DATA
# -------------------------------
gsk_brands = {
    "Shingrix": "https://www.cdc.gov/shingles/hcp/clinical-overview",
    "Trelegy": "https://www.gsk.com/en-gb/products/trelegy/",
    "Zejula": "https://www.gsk.com/en-gb/products/zejula/"
}

# -------------------------------
# RACE / BARRIERS / OBJECTIVES / PERSONA / STEPS
# -------------------------------
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

# -------------------------------
# SIDEBAR FILTERS
# -------------------------------
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

# -------------------------------
# UPLOAD PDF / PPT
# -------------------------------
uploaded_pdf = st.file_uploader("Upload brand PDF", type="pdf")
uploaded_ppt = st.file_uploader("Upload brand PPT", type=["pptx", "ppt"])

# -------------------------------
# EXTRACT VISUALS
# -------------------------------
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

# -------------------------------
# CHAT INTERFACE
# -------------------------------
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
                    <img src="https://img.icons8.com/emoji/48/000000/man-technologist-light-skin-tone.png" width="30" style='margin-left:10px;'>
                </div>
            </div>"""
        else:
            # Embed visuals in AI response
            images_html = ""
            for img in all_images:
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                images_html += f"<img src='data:image/png;base64,{img_str}' width='250' style='margin:5px;'/>"
            chat_html += f"""
            <div style='display:flex; justify-content:flex-start; margin:5px;'>
                <div style='background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; border:2px solid #888; max-width:70%; display:flex; align-items:flex-start; flex-direction:column;'>
                    <div style='flex:1;'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>
                    {images_html}
                </div>
            </div>"""
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

# -------------------------------
# CLEAR CHAT
# -------------------------------
if st.button("🗑️ Clear Chat / مسح المحادثة"):
    st.session_state.chat_history = []

# -------------------------------
# VOICE INPUT
# -------------------------------
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
        try:
            transcript = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=open(audio_path, "rb")
            )
            rep_voice_text = transcript.text
            st.success(f"🗣️ You said: {rep_voice_text}")
        except Exception as e:
            st.warning(f"⚠️ Could not transcribe voice: {e}")

# -------------------------------
# TEXT INPUT & FORM
# -------------------------------
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message... (or use voice above)", key="user_input_box")
    submitted = st.form_submit_button("➤")

if (submitted and user_input.strip()) or rep_voice_text:
    rep_message = rep_voice_text if rep_voice_text else user_input
    st.session_state.chat_history.append({"role": "user", "content": rep_message, "time": datetime.now().strftime("%H:%M")})

    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)
    references = """1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information. 2. CDC Shingrix Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html"""

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
APACT Steps (only for objections):
Acknowledge → Probing → Answer → Confirm → Transition
Use APACT only where relevant.
References:
{references}
Embed PDF/PPT visuals in response.
Provide step-by-step actionable suggestions.
Response Length: {response_length}
Response Tone: {response_tone}
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
        ai_output = f"⚠️ Could not generate AI response: {e}"

    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M")})

    # -------------------------------
    # AI VOICE RESPONSE
    # -------------------------------
    try:
        tts = gTTS(ai_output.replace("-", "").replace(",", "").replace(".", ""), lang="en" if language=="English" else "ar")
        audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(audio_file.name)
        st.audio(audio_file.name, format="audio/mp3")
    except Exception as e:
        st.warning(f"⚠️ Could not generate AI audio: {e}")

    display_chat()

# -------------------------------
# DOWNLOAD WORD
# -------------------------------
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

if DOCX_AVAILABLE and st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io_bytes()
        doc.save(word_buffer)
        st.download_button(
            label="📥 Download as Word (.docx)",
            data=word_buffer.getvalue(),
            file_name="AI_Response.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
