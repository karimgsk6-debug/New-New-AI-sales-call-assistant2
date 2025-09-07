import streamlit as st
from PIL import Image
from io import BytesIO, BytesIO as io_bytes
import fitz
from pptx import Presentation
import tempfile
from datetime import datetime
import os

# --- Voice synthesis ---
import pyttsx3
from gtts import gTTS

# --- WebRTC voice input ---
from streamlit_webrtc import webrtc_streamer, WebRtcMode

# --- Optional Word export ---
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# --- Groq API ---
import groq
from groq import Groq
client = Groq(api_key="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")  # <<< insert real key

# --- Session ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Language ---
language = st.radio("Select Language / اختر اللغة", ["English", "العربية"])

# --- Branding ---
logo_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
col1, col2 = st.columns([1,5])
with col1: st.image(logo_url, width=120)
with col2: st.title("🧠 AI Sales Call Assistant (Voice + Text)")

# --- Brand links ---
gsk_brands = {
    "Shingrix": "https://www.cdc.gov/shingles/hcp/clinical-overview",
    "Trelegy": "https://www.gsk.com/en-gb/products/trelegy/",
    "Zejula": "https://www.gsk.com/en-gb/products/zejula/"
}

# --- Filters ---
race_segments = [
    "R – Reach: Did not start to prescribe yet...",
    "A – Acquisition: Prescribe if patient initiates discussion...",
    "C – Conversion: Proactively initiate for specific profile...",
    "E – Engagement: Proactively prescribe broadly"
]
doctor_barriers = ["HZ not seen as risk","No time","Cost","Doubts on effectiveness","Accessibility issues"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
gsk_approaches = ["Use data-driven evidence","Focus on outcomes","Leverage storytelling"]
sales_call_flow = ["Prepare","Engage","Create Opportunities","Drive Impact","Post Call Analysis"]
apact_steps = ["Acknowledge","Probing","Answer","Confirm","Transition"]

# --- Sidebar ---
st.sidebar.header("Filters")
brand = st.sidebar.selectbox("Brand", list(gsk_brands.keys()))
segment = st.sidebar.selectbox("RACE", race_segments)
barrier = st.sidebar.multiselect("Barriers", doctor_barriers)
objective = st.sidebar.selectbox("Objective", objectives)
specialty = st.sidebar.selectbox("Specialty", specialties)
persona = st.sidebar.selectbox("Persona", personas)

# --- Upload PDFs/PPTs ---
uploaded_pdf = st.sidebar.file_uploader("Upload PDF", type="pdf")
uploaded_ppt = st.sidebar.file_uploader("Upload PPT", type=["pptx","ppt"])

def extract_pdf_images(pdf_file):
    images=[]
    try:
        doc=fitz.open(pdf_file)
        for page in doc:
            for img in page.get_images(full=True):
                xref=img[0]
                base=doc.extract_image(xref)
                images.append(Image.open(BytesIO(base["image"])))
    except: pass
    return images

def extract_ppt_images(ppt_file):
    images=[]
    try:
        prs=Presentation(ppt_file)
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.shape_type==13:
                    images.append(Image.open(BytesIO(shape.image.blob)))
    except: pass
    return images

all_images=[]
if uploaded_pdf: all_images+=extract_pdf_images(uploaded_pdf)
if uploaded_ppt: all_images+=extract_ppt_images(uploaded_ppt)
if all_images:
    st.subheader("Uploaded Visuals")
    for img in all_images: st.image(img,width=300)

# --- Chat display ---
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()
def display_chat():
    html=""
    for msg in st.session_state.chat_history:
        time=msg.get("time","")
        text=msg["content"].replace("\n","<br>")
        if msg["role"]=="user":
            html+=f"<div style='text-align:right;'><b>🧑 Rep:</b> {text}<br><i>{time}</i></div><hr>"
        else:
            html+=f"<div style='text-align:left;'><b>🤖 AI:</b> {text}<br><i>{time}</i></div><hr>"
    chat_placeholder.markdown(html,unsafe_allow_html=True)
display_chat()

# --- Voice input ---
st.subheader("🎙️ Rep Voice Input")
webrtc_ctx=webrtc_streamer(
    key="speech", mode=WebRtcMode.SENDRECV,
    audio_receiver_size=1024,
    media_stream_constraints={"audio":True,"video":False}
)
rep_voice_text=None
if webrtc_ctx and webrtc_ctx.audio_receiver:
    frames=webrtc_ctx.audio_receiver.get_frames(timeout=1)
    if frames:
        with tempfile.NamedTemporaryFile(delete=False,suffix=".wav") as tmp:
            tmp.write(frames[0].to_ndarray().tobytes())
            audio_path=tmp.name
        try:
            transcript=client.audio.transcriptions.create(
                model="whisper-large-v3", file=open(audio_path,"rb"))
            rep_voice_text=transcript.text
            st.success(f"🗣️ You said: {rep_voice_text}")
        except: st.warning("⚠️ Voice transcription failed")

# --- Text input ---
with st.form("chat",clear_on_submit=True):
    text_input=st.text_input("Type message...",key="txt")
    submit=st.form_submit_button("Send ➤")

if (submit and text_input.strip()) or rep_voice_text:
    msg=rep_voice_text if rep_voice_text else text_input
    st.session_state.chat_history.append({"role":"user","content":msg,"time":datetime.now().strftime("%H:%M")})

    references = """
Medical References for AI Response:
- ZOE-50, ZOE-70, ZOE-HSCT phase III trials (Shingrix)
- Clinically significant shingles pain reported 86-88% (ZBPI ≥3)
- Duration: mean 17-22 days; 12-17% beyond 3 months
- Patient-reported QoL impact: age ≥50, Canada qualitative study
- Data on burden of disease, efficacy, safety, long-term protection, pain, quality of life
"""
    prompt=f"""
Language: {language}
Rep input: {msg}
Brand: {brand}
RACE: {segment}
Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Specialty: {specialty}
Persona: {persona}
Sales Flow: {" → ".join(sales_call_flow)}
APACT: {" → ".join(apact_steps)}
Approaches: {"; ".join(gsk_approaches)}
References: {references}
Provide structured response including medical evidence, step-by-step actionable suggestions. Make response engaging and natural.
"""

    try:
        response=client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role":"system","content":f"You are a GSK sales assistant following sales flow and APACT only for objections. Respond in {language}."},
                {"role":"user","content":prompt}
            ],temperature=0.7
        )
        ai_output=response.choices[0].message.content
        st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M")})

        # --- Voice output ---
        if language=="English":
            engine=pyttsx3.init()
            engine.setProperty("rate",160)
            engine.setProperty("volume",0.9)
            voices=engine.getProperty("voices")
            engine.setProperty("voice", voices[1].id if len(voices)>1 else voices[0].id)
            audio_file=tempfile.NamedTemporaryFile(delete=False,suffix=".mp3")
            engine.save_to_file(ai_output,audio_file.name)
            engine.runAndWait()
            st.audio(audio_file.name,format="audio/mp3")
        else:
            tts=gTTS(ai_output,lang="ar",slow=False)
            audio_file=tempfile.NamedTemporaryFile(delete=False,suffix=".mp3")
            tts.save(audio_file.name)
            st.audio(audio_file.name,format="audio/mp3")

        display_chat()
    except:
        st.warning("⚠️ AI response failed")

# --- Word export ---
if DOCX_AVAILABLE and st.session_state.chat_history:
    ai_msgs=[m["content"] for m in st.session_state.chat_history if m["role"]=="ai"]
    if ai_msgs:
        doc=Document(); doc.add_heading("AI Sales Call Response",0)
        doc.add_paragraph(ai_msgs[-1])
        buf=io_bytes(); doc.save(buf)
        st.download_button("📥 Download Word",buf.getvalue(),"AI_Response.docx")

# --- Leaflet ---
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
