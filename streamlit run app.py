import streamlit as st
from PIL import Image
from io import BytesIO, BytesIO as io_bytes
import fitz
from pptx import Presentation
import tempfile
from datetime import datetime
from gtts import gTTS
from streamlit_webrtc import webrtc_streamer, WebRtcMode
import groq
from groq import Groq

# --- Optional Word download ---
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# --- Groq client with API Key ---
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# --- Session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "rep_voice_text" not in st.session_state:
    st.session_state.rep_voice_text = ""

# --- Language selection ---
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
brand = st.sidebar.selectbox("Select Brand / اختر العلامة التجارية", list(gsk_brands.keys()))
segment = st.sidebar.selectbox("Select RACE Segment / اختر شريحة RACE", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", doctor_barriers)
objective = st.sidebar.selectbox("Select Objective / اختر الهدف", objectives)
specialty = st.sidebar.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", specialties)
persona = st.sidebar.selectbox("Select HCP Persona / اختر شخصية الطبيب", personas)
response_length = st.sidebar.selectbox("Response Length / اختر طول الرد", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])
interface_mode = st.sidebar.radio("Interface Mode / اختر واجهة", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# --- Upload PDF / PPT ---
uploaded_pdf = st.sidebar.file_uploader("Upload brand PDF", type="pdf")
uploaded_ppt = st.sidebar.file_uploader("Upload brand PPT", type=["pptx", "ppt"])

# --- Extract images from PDF/PPT ---
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

all_images = (extract_pdf_images(uploaded_pdf) if uploaded_pdf else []) + \
             (extract_ppt_images(uploaded_ppt) if uploaded_ppt else [])
if all_images:
    st.subheader("Uploaded Brand Visuals")
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
        time = msg.get("time","")
        content = msg["content"].replace("\n","<br>").strip()
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

# --- Voice Record Button ---
st.subheader("🎤 Record Voice Message")
if st.button("🎙️ Record"):
    webrtc_ctx = webrtc_streamer(
        key="speech",
        mode=WebRtcMode.SENDRECV,
        audio_receiver_size=1024,
        media_stream_constraints={"audio": True, "video": False}
    )

    if webrtc_ctx and webrtc_ctx.audio_receiver:
        audio_frames = webrtc_ctx.audio_receiver.get_frames(timeout=3)
        if audio_frames:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
                tmp_wav.write(audio_frames[0].to_ndarray().tobytes())
                audio_path = tmp_wav.name
            transcript = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=open(audio_path, "rb")
            )
            st.session_state.rep_voice_text = transcript.text
            st.success(f"🗣️ Your message converted to text!")

# --- Chat input ---
rep_input = st.text_input("Type your message or use voice above", value=st.session_state.rep_voice_text, key="chat_input_box")
if st.button("➤ Send") and rep_input.strip():
    st.session_state.chat_history.append({"role":"user","content":rep_input,"time":datetime.now().strftime("%H:%M")})

    # --- AI Prompt ---
    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)
    references = """1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information. Approval Date: 11-9-2023. Version: GDS07/IPI02.
2. CDC Shingrix Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html
3. Strezova et al., 2022. Long-term Protection Against Herpes Zoster: https://doi.org/10.1093/ofid/ofac485
4. CDC Clinical Overview of Shingles: https://www.cdc.gov/shingles/hcp/clinical-overview/index.html
5. Burden of Disease, Pain, QoL, Long-term efficacy data: eye.2
"""
    prompt = f"""
Language: {language}
User input: {rep_input}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Brand: {brand}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Approved Sales Approaches: {approaches_str}
Sales Call Flow Steps: {flow_str}
APACT Steps (for objections): {' → '.join(apact_steps)}
References: {references}
Embed PDF/PPT visuals if available.
Provide step-by-step actionable suggestions.
Response Length: {response_length}
Response Tone: {response_tone}
"""

    # --- AI response ---
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

    # --- AI Voice ---
    tts = gTTS(text=ai_output, lang="en" if language=="English" else "ar", slow=False)
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
