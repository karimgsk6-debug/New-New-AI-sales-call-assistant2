import streamlit as st
from PIL import Image
from io import BytesIO, BytesIO as io_bytes
import fitz  # PyMuPDF
from pptx import Presentation
import tempfile
from gtts import gTTS
from datetime import datetime
import re
from streamlit_webrtc import webrtc_streamer, WebRtcMode

# Groq client
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

# --- Upload PDF ---
uploaded_pdf = st.sidebar.file_uploader("Upload brand PDF", type="pdf")
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

pdf_text, pdf_images = extract_pdf_text_images(uploaded_pdf) if uploaded_pdf else ("", [])

# --- Display PDF visuals ---
if pdf_images:
    st.subheader("Uploaded PDF Visuals")
    for img in pdf_images:
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

# --- Voice recording + text ---
st.subheader("🎙️ Record your voice (or type)")
rep_voice_text = st.text_input("Your question will appear here after recording...")

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

    # --- Prompt ---
    numbered_pdf_text = re.sub(r'[\*\-\•]', '', pdf_text)
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
References from PDF & external: {numbered_pdf_text[:2000]}
Response Length: {response_length}
Response Tone: {response_tone}
Provide step-by-step suggestions with numbered steps.
Remove punctuation in audio output.
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

    # --- Append AI response ---
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M")})
    display_chat()

    # --- Generate AI voice ---
    tts = gTTS(ai_output, lang="en" if language=="English" else "ar", slow=False)
    audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(audio_file.name)
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
