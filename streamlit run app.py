# app.py
import streamlit as st
from PIL import Image
import re
import tempfile
import base64
from groq import Groq
from PyPDF2 import PdfReader
from html import escape
from gtts import gTTS

# Optional docx export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False

# ---------------------------- TTS Setup ----------------------------
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except ModuleNotFoundError:
    ELEVENLABS_AVAILABLE = False

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

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = "https://sdmntprpolandcentral.oaiusercontent.com/files/00000000-466c-620a-81c6-59c1f5c85484/raw?se=2025-10-01T21%3A36%3A08Z&sp=r&sv=2024-08-04&sr=b&scid=e48070e4-6fe8-551d-b151-1591946f0e60&skoid=eb780365-537d-4279-a878-cae64e33aa9c&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-10-01T19%3A07%3A59Z&ske=2025-10-02T19%3A07%3A59Z&sks=b&skv=2024-08-04&sig=3/PGGYaseBkvjJWbMBbuzsZeNyvlAXRSqcswf%2Bm1IZI%3D"
GSK_LOGO_URL = "https://usppg.org/wp-content/uploads/2025/04/GSK-logo.png"
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
  width: 70%;
  position: relative;
}}
.title-box img.ai-logo {{
  position: absolute;
  top: 10px;
  right: 10px;
  width: 100px;
  height: auto;
}}
.chat-container {{
  max-height: 65vh;
  overflow-y: auto;
  padding: 12px;
  border-radius: 10px;
  background: rgba(255,255,255,0.85);
  margin-bottom: 10px;
}}
.chat-bubble-user {{
  background: #0078D7; color:white; margin-left:auto; margin-bottom:20px; padding:12px; border-radius:12px; max-width:80%;
}}
.chat-bubble-ai {{
  background: #D9F0FF; color:#000; margin-right:auto; margin-bottom:20px; padding:12px; border-radius:12px; max-width:80%;
}}
.chat-bubble-audio {{
  background: #f0f0f0; margin-right:auto; font-size:0.9em; padding:10px; margin-bottom:20px; border-radius:10px;
}}
.pdf-summary-box {{
  background: #E6F0FF; 
  padding: 12px; 
  border-radius: 14px; 
  margin-bottom: 12px;
  white-space: pre-line;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ Client ----------------------------
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Sidebar Filters ----------------------------
gsk_brands = ["Shingrix", "Trelegy", "Zejula"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist"]
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
doctor_barriers = ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"]
objectives = ["Awareness","Adoption","Retention"]

with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Select Brand", gsk_brands, key="select_brand")
    specialty = st.selectbox("Select Specialty", specialties, key="select_specialty")
    segment = st.selectbox("Select RACE Segment", race_segments, key="select_segment")
    persona = st.selectbox("Select HCP Persona", personas, key="select_persona")
    barrier = st.multiselect("Select Doctor Barrier", doctor_barriers, key="select_barrier")
    objective = st.selectbox("Select Objective", objectives, key="select_objective")
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"], key="select_length")
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"], key="select_tone")
    language = st.radio("Language", ["English","Arabic"], horizontal=True, key="select_lang")

# ---------------------------- Title Box ----------------------------
st.markdown(f'''
<div class="title-box">
    <img src="{GSK_LOGO_URL}" width="140">
    <h1>💡 AI Sales Call Assistant</h1>
    <p>Powered by AI to equip reps for smarter HCP conversations</p>
    <img class="ai-logo" src="{AI_LOGO_URL}">
</div>
''', unsafe_allow_html=True)

# ---------------------------- Sales Flow / APACT ----------------------------
sales_call_flow = ["Prepare","Engage","Create Opportunities","Impact GSO","Influence","Post Call Analysis"]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]

# ---------------------------- PDF Upload ----------------------------
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
if uploaded_pdf:
    reader = PdfReader(uploaded_pdf)
    full_text = "".join([p.extract_text() or "" for p in reader.pages])
    st.session_state.uploaded_pdf_text = full_text
    st.session_state.pdf_summary = "\n".join(full_text.split("\n")[:10])

# Collapsible PDF Summary
with st.expander("📄 PDF Summary (click to expand/collapse)", expanded=False):
    if st.session_state.pdf_summary:
        st.markdown(f'<div class="pdf-summary-box">{st.session_state.pdf_summary}</div>', unsafe_allow_html=True)
    else:
        st.write("No PDF uploaded.")

# ---------------------------- Chat Input & Handling ----------------------------
user_input = st.text_input("Type your message below:", key="chat_input")
send = st.button("Send")

def highlight_keywords(text, keywords):
    for kw in keywords:
        text = re.sub(f"(?i)({re.escape(kw)})", r'<mark>\1</mark>', text)
    return text

def generate_ai_response(prompt):
    if "sales call flow" in prompt.lower():
        context = f"Use Sales Call Flow steps: {', '.join(sales_call_flow)}.\nInclude relevant points from the PDF:\n{st.session_state.pdf_summary}"
    elif "handling objection" in prompt.lower():
        context = f"Use APACT steps: {', '.join(APACT_STEPS)}.\nInclude relevant points from the PDF:\n{st.session_state.pdf_summary}"
    else:
        context = f"Include relevant points from the PDF:\n{st.session_state.pdf_summary}"
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"system","content":"You are a helpful GSK sales assistant."},
                  {"role":"user","content":context + "\nUser: " + prompt}],
        temperature=0.65
    )
    return response.choices[0].message.content

# ---------------------------- Chat History ----------------------------
if send and user_input.strip():
    ai_resp = generate_ai_response(user_input)
    audio_base64 = generate_audio(ai_resp)
    st.session_state.chat_history.append((user_input, ai_resp, audio_base64))

# ---------------------------- Render Chat ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for user_msg, ai_msg, audio in st.session_state.chat_history:
    st.markdown(f'<div class="chat-bubble-user">{user_msg}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="chat-bubble-ai">{highlight_keywords(ai_msg, ["Shingrix","HZ","vaccine"])}</div>', unsafe_allow_html=True)
    st.markdown(f'''
        <div class="chat-bubble-audio">
        🔊 AI Voice:<br>
        <audio controls src="data:audio/mp3;base64,{audio}"></audio>
        </div>
    ''', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Download Chat as Word ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    doc = Document()
    for user_msg, ai_msg, _ in st.session_state.chat_history:
        doc.add_paragraph(f"User: {user_msg}")
        doc.add_paragraph(f"AI: {ai_msg}")
        doc.add_paragraph("")
    tmp_doc = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    doc.save(tmp_doc.name)
    with open(tmp_doc.name, "rb") as f:
        st.download_button("📄 Download Chat as Word", f, file_name="AI_SalesCall_Chat.docx")
