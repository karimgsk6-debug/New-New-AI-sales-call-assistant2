import streamlit as st
import tempfile
import os
import fitz  # PyMuPDF
from gtts import gTTS
from docx import Document
from pptx import Presentation
from groq import Groq

# --- Safe Audio Recorder Imports ---
use_audiorecorder = False
use_webrtc = False

try:
    from st_audiorecorder import st_audiorecorder
    use_audiorecorder = True
except ImportError:
    st.warning("⚠️ st-audiorecorder not installed. Will try streamlit-webrtc fallback.")

try:
    from streamlit_webrtc import webrtc_streamer, WebRtcMode
    use_webrtc = True
except ImportError:
    st.warning("⚠️ streamlit-webrtc not installed. Voice recording may not work.")

# --- Page Setup ---
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# --- Sidebar ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/7/79/GSK_logo_2022.svg", width=150)
st.sidebar.title("AI Sales Call Assistant")
st.sidebar.markdown("""
This tool helps **pharma reps** prepare for customer interactions.  
⚠️ **Disclaimer:** Always refer to **approved GSK references**.  
""")

# --- Groq API Setup ---
api_key = os.getenv("GROQ_API_KEY") or st.sidebar.text_input("🔑 Enter your GROQ API Key", type="password")
if not api_key:
    st.warning("⚠️ Please enter your API Key to proceed.")
client = Groq(api_key=api_key) if api_key else None

# --- HCP Segments, Persona, Barriers ---
race_segments = [
    "R – Reach: Did not start to prescribe yet and Don't believe vaccination is his responsibility.",
    "A – Acquisition: Prescribe to patient who initiate discussion but is convinced about Shingrix data.",
    "C – Conversion: Proactively initiate discussion with specific patient profile but not prescribing for all.",
    "E – Engagement: Proactively prescribe to different patient profiles."
]
doctor_barriers = [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ vaccine is effective",
    "Accessibility issues"
]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
gsk_approaches = ["Use data-driven evidence", "Focus on patient outcomes", "Leverage storytelling techniques"]
sales_call_flow = ["Prepare", "Engage", "Create Opportunities", "Drive Impact", "Post Call Analysis"]
apact_steps = ["Acknowledge", "Probing", "Answer", "Confirm", "Transition"]

# --- Sidebar Filters ---
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand", options=["Shingrix", "Trelegy", "Zejula"])
segment = st.sidebar.selectbox("Select RACE Segment", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barriers", options=doctor_barriers)
objective = st.sidebar.selectbox("Select Objective", objectives)
specialty = st.sidebar.selectbox("Select Doctor Specialty", specialties)
persona = st.sidebar.selectbox("Select HCP Persona", personas)
response_length = st.sidebar.selectbox("Response Length", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])

# --- References ---
references = """📚 References:
1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information. Approval Date: 11-9-2023. Version: GDS07/IPI02.  
2. CDC Shingrix Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html  
3. Strezova et al., 2022. Long-term Protection Against Herpes Zoster: https://doi.org/10.1093/ofid/ofac485  
4. CDC Clinical Overview of Shingles: https://www.cdc.gov/shingles/hcp/clinical-overview/index.html  
"""

# --- Helper Functions ---
def extract_text_from_file(uploaded_file):
    """Extracts text from PDF, Word, or PowerPoint."""
    text = ""
    if uploaded_file.name.endswith(".pdf"):
        pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        for page in pdf:
            text += page.get_text()
    elif uploaded_file.name.endswith(".docx"):
        doc = Document(uploaded_file)
        for para in doc.paragraphs:
            text += para.text + "\n"
    elif uploaded_file.name.endswith(".pptx"):
        prs = Presentation(uploaded_file)
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text += shape.text + "\n"
    return text.strip()

def generate_ai_response(prompt):
    """Generates AI response using Groq LLM."""
    if not client:
        return "❌ Groq API Key not set. Cannot generate AI response."
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": "You are a helpful AI sales assistant."},
                      {"role": "user", "content": prompt}],
            model="llama3-70b-8192"
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"❌ Error generating response: {e}"

# --- Main Interface ---
st.title("💊 AI Sales Call Assistant")
st.markdown("📌 Prepare for your **customer interactions** with AI-powered insights.")

# --- File Upload ---
uploaded_file = st.file_uploader("📂 Upload reference material (PDF, DOCX, PPTX)", type=["pdf", "docx", "pptx"])
reference_text = ""
if uploaded_file:
    reference_text = extract_text_from_file(uploaded_file)
    with st.expander("📖 Extracted Reference Text"):
        st.write(reference_text if reference_text else "⚠️ No text extracted.")

# --- Voice Recording ---
st.subheader("🎙️ Record Your Voice Message")
audio_path, rep_voice_text = None, None

if use_audiorecorder:
    st.info("Press 🎤 button below to record. Release when done.")
    audio = st_audiorecorder()
    if audio is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(audio)
            audio_path = f.name
        st.audio(audio_path)
        with open(audio_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-large-v3",
                file=f
            )
            rep_voice_text = transcript.text
        st.text_area("📝 Voice converted to text:", value=rep_voice_text, height=80)
elif use_webrtc:
    st.info("🎤 Using fallback (webrtc) for recording on Streamlit Cloud")
    webrtc_ctx = webrtc_streamer(
        key="voice",
        mode=WebRtcMode.SENDRECV,
        audio_receiver_size=1024,
        media_stream_constraints={"audio": True, "video": False},
    )
    if webrtc_ctx and webrtc_ctx.audio_receiver:
        frames = webrtc_ctx.audio_receiver.get_frames(timeout=1)
        if frames:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
                tmp_wav.write(frames[0].to_ndarray().tobytes())
                audio_path = tmp_wav.name
            with open(audio_path, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-large-v3",
                    file=f
                )
                rep_voice_text = transcript.text
            st.text_area("📝 Voice converted to text:", value=rep_voice_text, height=80)
else:
    st.info("⚠️ Voice recording not available. Please type your input below.")

# --- AI Response Generation ---
user_input = st.text_input("Type your message (if no voice input)")
if user_input.strip():
    rep_voice_text = user_input.strip()

if st.button("🚀 Generate AI Sales Call Suggestions"):
    if not rep_voice_text and not reference_text:
        st.warning("⚠️ Please provide either a voice input or reference file.")
    else:
        final_prompt = f"""
Language: English
User Input: {rep_voice_text if rep_voice_text else "N/A"}
Segment: {segment}
Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Specialty: {specialty}
Persona: {persona}
Sales Approaches: {'; '.join(gsk_approaches)}
Sales Call Flow: {' → '.join(sales_call_flow)}
APACT Steps: {' → '.join(apact_steps)}
References: {references}
Reference material text: {reference_text if reference_text else "N/A"}
Response Length: {response_length}
Response Tone: {response_tone}
"""
        response = generate_ai_response(final_prompt)
        st.markdown("## 🤖 AI Sales Call Suggestions")
        st.write(response)

        # Generate AI voice feedback
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            tts = gTTS(text=response, lang="en")
            tts.save(f.name)
            st.audio(f.name)
