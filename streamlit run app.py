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

# ---------------------------- TTS Setup ----------------------------
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except ModuleNotFoundError:
    ELEVENLABS_AVAILABLE = False

from gtts import gTTS

# ElevenLabs config
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
if "chat_history" not in st.session_state or not isinstance(st.session_state.chat_history, list):
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
BACKGROUND_URL = "https://sdmntprukwest.oaiusercontent.com/files/00000000-abd4-6243-82cf-168367664603/raw?se=2025-10-02T08%3A55%3A08Z&sp=r&sv=2024-08-04&sr=b&scid=da9b1fe8-d683-5331-8dac-5d17ac775ed0&skoid=82a3371f-2f6c-4f81-8a78-2701b362559b&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-10-02T05%3A07%3A48Z&ske=2025-10-03T05%3A07%3A48Z&sks=b&skv=2024-08-04&sig=zev17ijVwaJyIwxogpGkQRRHoIWzd7z4Ic%2BWeVhPdjc%3D"
GSK_LOGO_URL = "https://usppg.org/wp-content/uploads/2025/04/GSK-logo.png"
AI_LOGO_URL = "https://sdmntpritalynorth.oaiusercontent.com/files/00000000-42e0-6246-8bd4-812f66b46668/raw?se=2025-10-02T09%3A09%3A04Z&sp=r&sv=2024-08-04&sr=b&scid=04001bb8-a622-5394-8e9b-f0e7f4f6f1f2&skoid=82a3371f-2f6c-4f81-8a78-2701b362559b&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-10-02T04%3A32%3A34Z&ske=2025-10-03T04%3A32%3A34Z&sks=b&skv=2024-08-04&sig=eStxlnunHXrvS6s65lQTrZCH1ziJhQ6mUxgpbnT/zeY%3D"

# ---------------------------- CSS ----------------------------
CSS = f"""
<style>
/* Background */
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-attachment: fixed;
  background-size: auto 150%;
}}

/* Title box */
.title-box {{
  background: rgba(245,245,245,0.85);
  padding: 15px;
  border-radius: 16px;
  text-align: center;
  margin: 12px auto;
  width: 650px;
  position: relative;
}}
.title-box img.ai-logo {{
    position: absolute;
    top: 10px;
    right: 10px;
    width: 80px;
}}

/* PDF summary box */
.pdf-summary-box {{
  background: #E6F0FF; 
  padding: 12px; 
  border-radius: 14px; 
  margin-bottom: 12px;
  white-space: pre-line;
}}

/* Chat area */
.chat-container {{
  max-height: 65vh;
  overflow-y: auto;
  padding: 12px;
  border-radius: 10px;
  background: rgba(255,255,255,0.85);
  margin-bottom: 20px;
}}

/* Bubbles */
.chat-bubble-user, .chat-bubble-ai, .chat-bubble-audio {{
  display:block;
  padding:12px;
  border-radius:12px;
  margin:12px 0;
  max-width: 86%;
  word-wrap: break-word;
}}
.chat-bubble-user {{ background: #0078D7; color:white; margin-left:auto; }}
.chat-bubble-ai {{ background: #d9f0ff; margin-right:auto; color:#000; }}
.chat-bubble-audio {{ background: #e2e2e2; margin-right:auto; font-size:0.9em; padding:10px; margin-top:12px; }}

/* Fixed chat input at bottom */
.fixed-chat-input {{
    position: fixed;
    bottom: 20px;
    left: 20px;
    right: 20px;
    z-index: 10002;
}}
.fixed-chat-input textarea {{
    width: 100%;
    min-height: 60px;
    max-height: 180px;
    resize: vertical;
}}
.send-button {{
    position: fixed;
    bottom: 20px;
    right: 30px;
    z-index: 10003;
    height: 40px;
    width: 100px;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ Client ----------------------------
GROQ_API_KEY = "Your Groq API KEY here"
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Filters / Sidebar ----------------------------
gsk_brands = ["Shingrix", "Trelegy", "Zejula"]
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist"]
objectives = ["Awareness","Adoption","Retention"]

with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", gsk_brands, key="select_brand")
    specialty = st.selectbox("Specialty", specialties, key="select_specialty")
    segment = st.selectbox("RACE Segment", race_segments, key="select_segment")
    persona = st.selectbox("HCP Persona", personas, key="select_persona")
    barrier = st.multiselect("Doctor Barrier", doctor_barriers, key="select_barrier")
    objective = st.selectbox("Objective", objectives, key="select_objective")
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"], key="select_tone")
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"], key="select_length")
    st.session_state.language = st.radio("Language", ["English","Arabic"], horizontal=True, key="select_language")

# ---------------------------- Title Box ----------------------------
st.markdown(f'''
<div class="title-box">
    <img src="{GSK_LOGO_URL}" width="140">
    <img src="{AI_LOGO_URL}" class="ai-logo">
    <h1>💡 AI Sales Call Assistant</h1>
    <p>Powered by AI to equip reps for smarter HCP conversations</p>
</div>
''', unsafe_allow_html=True)

# ---------------------------- PDF Upload & Summary ----------------------------
with st.expander("📄 PDF Summary", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
    st.session_state.pdf_summary_size = st.radio("PDF Summary Size", ["Consisted","Normal","Detailed"], horizontal=True)
    if uploaded_pdf:
        reader = PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text
        bullets_count = {"Consisted":5,"Normal":10,"Detailed":20}.get(st.session_state.pdf_summary_size,10)
        try:
            summary_prompt = f"Summarize the document into {bullets_count} bullet points:\n{full_text[:12000]}"
            ai_summary = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":"You are a helpful assistant."},
                          {"role":"user","content":summary_prompt}],
                temperature=0.4
            )
            st.session_state.pdf_summary = ai_summary.choices[0].message.content
        except Exception:
            fallback_bullets = re.findall(r'([A-Z][^.]{20,200})', full_text)
            st.session_state.pdf_summary = "\n".join(fallback_bullets[:bullets_count])
    if st.session_state.pdf_summary:
        st.markdown(f'<div class="pdf-summary-box">{escape(st.session_state.pdf_summary)}</div>', unsafe_allow_html=True)

# ---------------------------- AI Chat ----------------------------
def generate_ai_response(user_input):
    lower = user_input.lower()

    if "sales call" in lower or "call flow" in lower:
        system_prompt = """
        You are an AI sales coach for pharmaceutical reps. 
        Always generate responses using this **GSK Sales Call Flow**:
        1. Prepare
        2. Engage
        3. Create Opportunities
        4. Influence
        5. Impact GSO (Good Sell Outcome)

        For each step, provide clear, practical example lines the rep can use with an HCP.
        """
        final_prompt = f"Build a structured sales call flow for {persona}, focusing on {brand}, barriers: {barrier}, specialty: {specialty}, and objective: {objective}."

    elif "objection" in lower or "concern" in lower or "apact" in lower or "handle" in lower:
        system_prompt = """
        You are an AI objection-handling coach for pharmaceutical reps.
        Always generate responses using the **APACT framework**:
        - Acknowledge
        - Probing
        - Action
        - Confirm
        - Transition to next step

        For each milestone, provide realistic phrasing the rep can use with an HCP.
        """
        final_prompt = f"Handle the HCP objection with APACT structure. Objection context: {user_input}. Persona: {persona}, Brand: {brand}."

    else:
        system_prompt = "You are a helpful sales assistant AI for pharma reps."
        final_prompt = user_input

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"system","content":system_prompt},
                  {"role":"user","content":final_prompt}],
        temperature=0.65
    )
    return response.choices[0].message.content

# ---------------------------- Render Chat ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for item in st.session_state.chat_history:
    if isinstance(item, tuple) and len(item) == 3:
        user_msg, ai_msg, audio = item
        st.markdown(f'<div class="chat-bubble-user">{escape(user_msg)}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="chat-bubble-ai">{escape(ai_msg)}</div>', unsafe_allow_html=True)
        st.markdown(f'''
            <div class="chat-bubble-audio">
            🔊 AI Voice:<br>
            <audio controls src="data:audio/mp3;base64,{audio}"></audio>
            </div>
        ''', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Fixed Chat Input ----------------------------
st.markdown('<div class="fixed-chat-input">', unsafe_allow_html=True)
with st.form(key="chat_form", clear_on_submit=True):
    chat_input = st.text_area("Your Message", key="chat_input", placeholder="Type your message here...")
    send = st.form_submit_button("Send")
st.markdown('</div>', unsafe_allow_html=True)

if send and chat_input.strip():
    ai_resp = generate_ai_response(chat_input.strip())
    audio_base64 = generate_audio(ai_resp)
    st.session_state.chat_history.append((chat_input.strip(), ai_resp, audio_base64))

# ---------------------------- Word Export ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("📥 Export Chat to Word"):
        doc = Document()
        doc.add_heading("AI Sales Call Assistant Chat Export", 0)
        for user_msg, ai_msg, audio in st.session_state.chat_history:
            doc.add_paragraph(f"User: {user_msg}")
            doc.add_paragraph(f"AI: {ai_msg}\n")
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            bytes_data = f.read()
            b64 = base64.b64encode(bytes_data).decode()
            href = f'<a href="data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{b64}" download="AI_Chat.docx">Click here to download Word file</a>'
            st.markdown(href, unsafe_allow_html=True)
