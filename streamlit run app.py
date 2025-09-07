import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode
from PIL import Image
from io import BytesIO
import fitz
from pptx import Presentation
import tempfile
import asyncio
import edge_tts
from datetime import datetime
from docx import Document
import groq
from groq import Groq
import streamlit.components.v1 as components

# --- Groq API key ---
client = Groq(api_key="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")

# --- Session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Sidebar filters ---
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand", ["Shingrix", "Trelegy", "Zejula"])
race_segments = [
    "R – Reach: Did not start to prescribe yet and Don't believe that vaccination is his responsibility.",
    "A – Acquisition: Prescribe to patient who initiate discussion about the vaccine but Convinced about Shingrix data.",
    "C – Conversion: Proactively initiate discussion with specific patient profile but For other patient profiles he is not prescribing yet.",
    "E – Engagement: Proactively prescribe to different patient profiles"
]
segment = st.sidebar.selectbox("RACE Segment", race_segments)
barrier = st.sidebar.multiselect("Doctor Barriers", [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ Vx effective",
    "Accessibility issues"
])
specialty = st.sidebar.selectbox("Doctor Specialty", ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"])
persona = st.sidebar.selectbox("HCP Persona", ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"])

# --- PDF/PPT upload ---
uploaded_pdf = st.sidebar.file_uploader("Upload PDF", type="pdf")
uploaded_ppt = st.sidebar.file_uploader("Upload PPT", type=["pptx", "ppt"])

# --- Extract images ---
def extract_pdf_images(pdf_file):
    images = []
    try:
        doc = fitz.open(pdf_file)
        for page in doc:
            for img in page.get_images(full=True):
                xref = img[0]
                base_image = doc.extract_image(xref)
                images.append(Image.open(BytesIO(base_image["image"])))
    except: pass
    return images

def extract_ppt_images(ppt_file):
    images = []
    try:
        prs = Presentation(ppt_file)
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.shape_type == 13:
                    images.append(Image.open(BytesIO(shape.image.blob)))
    except: pass
    return images

pdf_images = extract_pdf_images(uploaded_pdf) if uploaded_pdf else []
ppt_images = extract_ppt_images(uploaded_ppt) if uploaded_ppt else []
all_images = pdf_images + ppt_images
if all_images:
    st.subheader("Uploaded Visuals")
    for img in all_images: st.image(img, width=300)

# --- Chat display ---
st.subheader("💬 AI Sales Assistant")
chat_placeholder = st.empty()
def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n", "<br>")
        time = msg.get("time", "")
        if msg["role"] == "user":
            chat_html += f"<div style='text-align:right; background:#dcf8c6; margin:5px; padding:10px; border-radius:15px;'>{content}<br><span style='font-size:10px;color:gray;'>{time}</span></div>"
        else:
            chat_html += f"<div style='text-align:left; background:#f0f2f6; margin:5px; padding:10px; border-radius:15px;'>{content}<br><span style='font-size:10px;color:gray;'>{time}</span></div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# --- WhatsApp-style hold-to-record button using JS ---
st.subheader("🎤 Press and Hold to Record")
components.html("""
<style>
#recordBtn {
  width: 150px;
  height: 50px;
  background-color: #4CAF50;
  color: white;
  font-size: 18px;
  border: none;
  border-radius: 25px;
}
#recordBtn:active {
  background-color: #45a049;
}
</style>
<button id="recordBtn">Hold to Record</button>
<script>
const btn = document.getElementById("recordBtn");
let mediaRecorder;
let audioChunks = [];

btn.onmousedown = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({audio:true});
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.start();
    mediaRecorder.ondataavailable = e => { audioChunks.push(e.data); };
};
btn.onmouseup = async () => {
    mediaRecorder.stop();
    mediaRecorder.onstop = async () => {
        const blob = new Blob(audioChunks, {type:"audio/wav"});
        const reader = new FileReader();
        reader.readAsDataURL(blob);
        reader.onloadend = () => {
            const base64data = reader.result;
            fetch("/_send_audio", {
                method:"POST",
                body: JSON.stringify({audio: base64data})
            });
        };
        audioChunks = [];
    };
};
</script>
""", height=100)

# --- Chat input & submission ---
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_area("Type your message (or leave voice message above)", height=100)
    submitted = st.form_submit_button("Send")

if submitted and user_input.strip():
    rep_message = user_input
    st.session_state.chat_history.append({"role":"user","content":rep_message,"time":datetime.now().strftime("%H:%M")})
    display_chat()

    references = """
1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information. Approval Date: 11-9-2023. Version: GDS07/IPI02.
2. CDC Shingrix Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html
3. Strezova et al., 2022. Long-term Protection Against Herpes Zoster: https://doi.org/10.1093/ofid/ofac485
4. CDC Clinical Overview of Shingles: https://www.cdc.gov/shingles/hcp/clinical-overview/index.html
"""
    prompt = f"""
User input: {rep_message}
RACE Segment: {segment}
Doctor Barriers: {', '.join(barrier)}
Doctor Specialty: {specialty}
HCP Persona: {persona}
References: {references}
Include PDF/PPT content if uploaded.
"""

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role":"system","content":"You are a helpful male storytelling sales assistant."},{"role":"user","content":prompt}],
            temperature=0.7
        )
        ai_output = response.choices[0].message.content
    except:
        ai_output = "❌ AI response failed."

    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M")})
    display_chat()

    async def play_voice():
        tts = edge_tts.Communicate(ai_output, voice="en-US-GuyNeural")
        tmp_mp3 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        await tts.save(tmp_mp3.name)
        st.audio(tmp_mp3.name, format="audio/mp3")
    asyncio.run(play_voice())

# --- Word download ---
if st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = BytesIO()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")
