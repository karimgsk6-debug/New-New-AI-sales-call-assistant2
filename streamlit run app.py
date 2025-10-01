# app.py
import streamlit as st
from PIL import Image
from io import BytesIO
import re
import tempfile
import base64
from groq import Groq
from PyPDF2 import PdfReader
from html import escape

# Optional docx export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False

# ---------------------------- TTS Setup (ElevenLabs fallback to gTTS) ----------------------------
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except ModuleNotFoundError:
    ELEVENLABS_AVAILABLE = False

from gtts import gTTS

ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "") 
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    elevenlabs.api_key = ELEVENLABS_API_KEY
else:
    ELEVENLABS_AVAILABLE = False

def generate_audio(text):
    for step in ["Acknowledge","Probing","Action","Confirm","Transition"]:
        text = text.replace(step, f"{step} ...")
    text = re.sub(r'[.,*]', '', text)
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    if ELEVENLABS_AVAILABLE:
        audio_stream = elevenlabs.generate(text=text, voice=ELEVENLABS_VOICE_ID, stream=True)
        with open(tmp_file.name, "wb") as f:
            for chunk in audio_stream:
                f.write(chunk)
    else:
        tts = gTTS(text=text, lang="en", slow=True)
        tts.save(tmp_file.name)
    with open(tmp_file.name, "rb") as f:
        audio_bytes = f.read()
        audio_base64 = base64.b64encode(audio_bytes).decode()
    return audio_base64

# ---------------------------- CONFIG ----------------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- Session Defaults ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "voice_pref" not in st.session_state:
    st.session_state.voice_pref = "Old Male"
if "language" not in st.session_state:
    st.session_state.language = "English"
if "pdf_search_keyword" not in st.session_state:
    st.session_state.pdf_search_keyword = ""
if "pdf_summary_size" not in st.session_state:
    st.session_state.pdf_summary_size = "Normal"

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = "https://www.shutterstock.com/image-photo/excited-girl-white-shirt-using-260nw-708132598.jpg"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"
AI_LOGO_URL = "https://sdmntpraustraliaeast.oaiusercontent.com/files/00000000-4b60-61fa-9450-ba1622fd3488/raw?se=2025-10-01T22%3A14%3A53Z&sp=r&sv=2024-08-04&sr=b&scid=5e0685db-737d-5bda-a960-befd761ac516&skoid=eb780365-537d-4279-a878-cae64e33aa9c&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-10-01T19%3A10%3A31Z&ske=2025-10-02T19%3A10%3A31Z&sks=b&skv=2024-08-04&sig=Fq1ONP%2BC2j2OlBh8kGjhfgU4zzbXf/ZJ5om/q%2B4BKCE%3D"

# ---------------------------- CSS ----------------------------
CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-attachment: fixed;
  background-size: auto 150%;
}}
.title-box {{
  background: rgba(245,245,245,0.85);
  padding: 15px;
  border-radius: 16px;
  text-align: left;
  margin: 12px auto;
  width: 75%;
  position: relative;
}}
.title-box img.ai-logo {{
  position: absolute;
  top: 10px;
  right: 10px;
  width: 100px;
  height: auto;
}}
.pdf-summary-box {{
  background: #E6F0FF; 
  padding: 12px; 
  border-radius: 14px; 
  margin-bottom: 12px;
  white-space: pre-line;
}}
.chat-container {{
  max-height: 65vh;
  overflow-y: auto;
  padding: 12px;
  padding-bottom: 20px;
  border-radius: 10px;
  background: rgba(255,255,255,0.85);
}}
.chat-bubble-user {{
  background: #0078D7; color:white; margin-left:auto; margin-bottom:16px; padding:12px; border-radius:12px; max-width:80%;
}}
.chat-bubble-ai {{
  background: #D9F0FF; color:#000; margin-right:auto; margin-bottom:16px; padding:12px; border-radius:12px; max-width:80%;
}}
.chat-bubble-audio {{
  background: #f0f0f0; margin-right:auto; font-size:0.9em; padding:10px; margin-bottom:16px; border-radius:10px;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ Client ----------------------------
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Filters / Sidebar ----------------------------
gsk_brands = ["Shingrix", "Trelegy", "Zejula"]
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
sales_call_flow = ["Prepare","Engage","Create Opportunities","Impact GSO","Influence","Post Call Analysis"]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist"]

with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Select Brand", gsk_brands, key="select_brand")
    segment = st.selectbox("Select RACE Segment", race_segments, key="select_segment")
    barrier = st.multiselect("Select Doctor Barrier", doctor_barriers, key="select_barrier")
    objective = st.selectbox("Select Objective", objectives, key="select_objective")
    specialty = st.selectbox("Select Doctor Specialty", specialties, key="select_specialty")
    persona = st.selectbox("Select HCP Persona", personas, key="select_persona")
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"], key="select_length")
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"], key="select_tone")
    st.session_state.language = st.radio("Language", ["English","Arabic"], horizontal=True, key="select_language")

# ---------------------------- Title Box ----------------------------
st.markdown(f'''
<div class="title-box">
    <img src="{GSK_LOGO_URL}" width="140">
    <h1>💡 AI Sales Call Assistant</h1>
    <p>Powered by AI to equip reps for smarter HCP conversations</p>
    <img class="ai-logo" src="{AI_LOGO_URL}">
</div>
''', unsafe_allow_html=True)

# ---------------------------- Chat Input and Rendering ----------------------------
user_input = st.text_input("Type your message:", key="chat_input")
send = st.button("Send")

if send and user_input.strip():
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role":"system","content":"You are a pharma sales AI assistant."},
                {"role":"user","content":user_input}
            ],
            temperature=0.65
        )
        ai_resp = response.choices[0].message.content
        audio_base64 = generate_audio(ai_resp)

        st.session_state.chat_history.append(("user", user_input))
        st.session_state.chat_history.append(("ai", ai_resp))
        st.session_state.chat_history.append(("audio", audio_base64))

    except Exception as e:
        st.error(f"Error generating AI response: {e}")

st.markdown('<div class="chat-container" id="chat-container">', unsafe_allow_html=True)
for item in st.session_state.chat_history:
    role, msg = item
    if role == "user":
        st.markdown(f'<div class="chat-bubble-user">{escape(msg)}</div>', unsafe_allow_html=True)
    elif role == "ai":
        st.markdown(f'<div class="chat-bubble-ai">{escape(msg)}</div>', unsafe_allow_html=True)
    elif role == "audio":
        st.markdown(f'''
        <div class="chat-bubble-audio">
            🔊 <audio controls>
            <source src="data:audio/mp3;base64,{msg}" type="audio/mp3">
            </audio>
        </div>
        ''', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
