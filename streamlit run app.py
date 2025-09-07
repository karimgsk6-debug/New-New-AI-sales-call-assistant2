import streamlit as st
from PIL import Image
from io import BytesIO, BytesIO as io_bytes
import fitz
from pptx import Presentation
import tempfile
from gtts import gTTS
from datetime import datetime
import re
import groq
from groq import Groq
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
import av

# --- Optional Word download ---
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# --- Groq client ---
GROQ_API_KEY = "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"  # <--- INSERT YOUR API KEY
client = Groq(api_key=GROQ_API_KEY)

# --- Session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "rep_voice_text" not in st.session_state:
    st.session_state.rep_voice_text = ""

# --- Language ---
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])

# --- Logo ---
logo_local_path = "images/gsk_logo.png"
logo_fallback_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
col1, col2 = st.columns([1,5])
with col1:
    try:
        st.image(Image.open(logo_local_path), width=120)
    except:
        st.image(logo_fallback_url, width=120)
with col2:
    st.title("🧠 AI Sales Call Assistant (Voice + Text)")

# --- Brand data ---
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

# --- Chat display ---
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
            chat_html += f"""
            <div style='display:flex; justify-content:flex-start; margin:5px;'>
                <div style='background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; border:2px solid #888; max-width:70%; display:flex; align-items:flex-start;'>
                    <img src="https://img.icons8.com/emoji/48/000000/robot-emoji.png" width="30" style='margin-right:10px;'>
                    <div style='flex:1;'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>
                </div>
            </div>"""
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)
display_chat()

# --- Voice Recorder ---
class AudioProcessor(AudioProcessorBase):
    def __init__(self):
        self.audio_frames = []

    def recv(self, frame: av.AudioFrame) -> av.AudioFrame:
        self.audio_frames.append(frame)
        return frame

def record_and_send(audio_frames):
    # Save audio
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
        for frame in audio_frames:
            tmp_wav.write(frame.to_ndarray().tobytes())
        audio_path = tmp_wav.name

    # Transcribe
    transcript = client.audio.transcriptions.create(
        model="whisper-large-v3",
        file=open(audio_path, "rb")
    )
    rep_message = transcript.text
    st.session_state.rep_voice_text = rep_message
    st.session_state.chat_history.append({
        "role":"user",
        "content":rep_message,
        "time":datetime.now().strftime("%H:%M")
    })

    # --- Prepare AI prompt ---
    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)
    references = """
1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information
2. CDC Shingrix Recommendations
3. Strezova et al., 2022. Long-term Protection Against Herpes Zoster
4. CDC Clinical Overview of Shingles
5. Burden of Disease, Efficacy, Long-term Efficacy, Safety
6. Pain Descriptions and Quality of Life
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
Acknowledge → Probing → Answer → Confirm → Transition
Use APACT where relevant.
References:
{references}
Embed PDF/PPT visuals.
Provide numbered step-by-step actionable suggestions.
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
    st.session_state.chat_history.append({
        "role":"ai",
        "content":ai_output,
        "time":datetime.now().strftime("%H:%M")
    })

    # --- AI voice ---
    clean_text = re.sub(r"[-,+*…]", " ", ai_output)
    tts = gTTS(text=clean_text, lang="en" if language=="English" else "ar", slow=False)
    audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(audio_file.name)
    st.audio(audio_file.name, format="audio/mp3")
    display_chat()

# --- Record & Send button ---
st.subheader("🎤 Record & Send Voice")
if st.button("Record & Send"):
    audio_processor = AudioProcessor()
    webrtc_ctx = webrtc_streamer(
        key="speech",
        mode=WebRtcMode.SENDRECV,
        audio_processor_factory=lambda: audio_processor,
        media_stream_constraints={"audio": True, "video": False},
        async_processing=True
    )
    st.info("Recording... Speak now and wait a few seconds for processing.")
    if webrtc_ctx.audio_receiver:
        import time
        time.sleep(5)  # Record for 5 seconds
        record_and_send(audio_processor.audio_frames)

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
