import streamlit as st
from PIL import Image
from io import BytesIO
import fitz  # PyMuPDF for fallback (if needed)
from pptx import Presentation
import tempfile
import pyttsx3
from gtts import gTTS
from streamlit_webrtc import webrtc_streamer, WebRtcMode
from pdf2image import convert_from_bytes
from datetime import datetime
import re
import os
import base64

# --- Initialize Groq client with API key directly ---
import groq
from groq import Groq
client = Groq(api_key="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")

# --- Session state ---
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

# --- Extract images from PDF ---
def extract_pdf_images(uploaded_pdf):
    images = []
    if uploaded_pdf:
        try:
            pdf_bytes = uploaded_pdf.read()
            pil_images = convert_from_bytes(pdf_bytes)
            for img in pil_images:
                images.append(img)
        except Exception as e:
            st.warning(f"⚠️ Could not extract images from PDF: {e}")
    return images

# --- Extract images from PPT ---
def extract_ppt_images(ppt_file):
    images = []
    if ppt_file:
        try:
            prs = Presentation(ppt_file)
            for slide in prs.slides:
                for shape in slide.shapes:
                    if shape.shape_type == 13:  # Picture
                        img = shape.image
                        images.append(Image.open(BytesIO(img.blob)))
        except Exception as e:
            st.warning(f"⚠️ Could not extract images from PPT: {e}")
    return images

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

# --- Voice input (record button) ---
st.subheader("🎙️ Record Your Voice")
rep_voice_text = st.text_area("Your recorded message will appear here:", height=80)
if st.button("Record / تسجيل"):
    webrtc_ctx = webrtc_streamer(
        key="speech",
        mode=WebRtcMode.SENDRECV,
        audio_receiver_size=1024,
        media_stream_constraints={"audio": True, "video": False},
    )
    if webrtc_ctx and webrtc_ctx.audio_receiver:
        audio_frames = webrtc_ctx.audio_receiver.get_frames(timeout=5)
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

# --- Chat input form ---
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message... (or use voice above)", value=rep_voice_text or "", key="user_input_box")
    submitted = st.form_submit_button("➤")

if (submitted and user_input.strip()):
    rep_message = user_input
    st.session_state.chat_history.append({"role": "user", "content": rep_message, "time": datetime.now().strftime("%H:%M")})

    # Embed PDF/PPT visuals in AI response
    pdf_images = extract_pdf_images(uploaded_pdf)
    ppt_images = extract_ppt_images(uploaded_ppt)
    all_images = pdf_images + ppt_images
    visuals_html = ""
    for idx, img in enumerate(all_images):
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        visuals_html += f'<p>Visual {idx+1}:</p><img src="data:image/png;base64,{img_str}" width="300"><br>'

    approaches_str = "\n".join([f"{i+1}. {a}" for i,a in enumerate(gsk_approaches)])
    flow_str = " → ".join(sales_call_flow)
    references = """
1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information
2. CDC Shingrix Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html
3. Strezova et al., 2022. Long-term Protection Against Herpes Zoster: https://doi.org/10.1093/ofid/ofac485
4. CDC Clinical Overview of Shingles: https://www.cdc.gov/shingles/hcp/clinical-overview/index.html
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
APACT Steps (only for objections):
Acknowledge → Probing → Answer → Confirm → Transition
Use APACT only where relevant.
References:
{references}
Embed PDF/PPT visuals as images in response:
{visuals_html}
Provide step-by-step actionable suggestions.
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
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M")})

    # AI voice reply
    # Remove punctuations to make it sound more natural
    clean_output = re.sub(r"[-,.;:!?]+", "", ai_output)
    tts = gTTS(clean_output, lang="en" if language=="English" else "ar")
    audio_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(audio_file.name)
    st.audio(audio_file.name, format="audio/mp3")

    display_chat()

# --- Word download ---
try:
    from docx import Document
    if st.session_state.chat_history:
        latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
        if latest_ai:
            doc = Document()
            doc.add_heading("AI Sales Call Response", 0)
            doc.add_paragraph(latest_ai[-1])
            word_buffer = BytesIO()
            doc.save(word_buffer)
            st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")
except:
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# --- Brand leaflet ---
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
