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
    if ELEVENLABS_AVAILABLE:
        audio_stream = elevenlabs.generate(text=text, voice=ELEVENLABS_VOICE_ID, stream=True)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        with open(tmp_file.name, "wb") as f:
            for chunk in audio_stream:
                f.write(chunk)
    else:
        tts = gTTS(text=text, lang="en", slow=True)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tmp_file.name)
    with open(tmp_file.name, "rb") as f:
        audio_bytes = f.read()
        audio_base64 = base64.b64encode(audio_bytes).decode()
    return audio_base64

# ---------------------------- CONFIG ----------------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- Session Defaults ----------------------------
for key, default in {
    "chat_history": [], "uploaded_pdf_text": "", "pdf_summary": "", 
    "voice_pref": "Old Male", "language": "English", 
    "pdf_search_keyword": "", "pdf_summary_size": "Normal"
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = "https://www.shutterstock.com/image-photo/excited-girl-white-shirt-using-260nw-708132598.jpg"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"

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
  background: rgba(245,245,245,0.7);
  padding: 20px;
  border-radius: 16px;
  text-align: center;
  margin: 12px auto;
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
  padding-bottom: 80px; 
  border-radius: 10px;
  background: rgba(255,255,255,0.85);
  margin-bottom: 0;
  max-width: 650px;
}}
.chat-bubble-user, .chat-bubble-ai, .chat-bubble-audio {{
  display:block;
  padding:12px;
  border-radius:12px;
  margin:8px 0;
  max-width: 86%;
  word-wrap: break-word;
}}
.chat-bubble-user {{ background: #0078D7; color:white; margin-left:auto; }}
.chat-bubble-ai {{ background: #E6F0FF; margin-right:auto; color:#000; }}
.chat-bubble-audio {{ background: #D3D3D3; margin-right:auto; font-size:0.9em; padding:10px; margin-top:8px; }}
.chat-input-container {{
    position: fixed;
    bottom: 20px;
    left: 20px;
    width: 650px;  
    display: flex;
    border-radius: 10px;
    background: rgba(255,255,255,0.95);
    padding: 5px 10px;
    z-index: 10002;
}}
.chat-input-container input[type="text"] {{
    flex: 1;
    border: none;
    outline: none;
    font-size: 1rem;
    padding: 10px;
    border-radius: 8px 0 0 8px;
}}
.chat-input-container button {{
    background-color: #0078D7;
    color: white;
    border: none;
    padding: 0 16px;
    font-size: 1rem;
    cursor: pointer;
    border-radius: 0 8px 8px 0;
}}
@media (max-width: 800px) {{
  .chat-container, .chat-input-container {{
      width: calc(100% - 40px);
      left: 10px;
  }}
}}
footer, header {{ z-index: 0; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ Client ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Filters / Sidebar ----------------------------
gsk_brands = ["Shingrix", "Trelegy", "Zejula"]
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist"]
sales_call_flow = ["Prepare","Engage","Create Opportunities","Impact GSO","Influence","Post Call Analysis"]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]

with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Select Brand", gsk_brands)
    segment = st.selectbox("Select RACE Segment", race_segments)
    barrier = st.multiselect("Select Doctor Barrier", doctor_barriers)
    objective = st.selectbox("Select Objective", objectives)
    specialty = st.selectbox("Select Doctor Specialty", specialties)
    persona = st.selectbox("Select HCP Persona", personas)
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"])
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"])
    st.session_state.language = st.radio("Language", ["English","Arabic"], horizontal=True)

# ---------------------------- Title Box ----------------------------
st.markdown(f'<div class="title-box"><img src="{GSK_LOGO_URL}" width="140"><h1>💡 AI Sales Call Assistant</h1><p>Powered by AI to equip reps for smarter HCP conversations</p></div>', unsafe_allow_html=True)

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
            summary_prompt = f"Summarize into {bullets_count} bullets:\n{full_text[:12000]}"
            ai_summary = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role":"system","content":"You are a helpful assistant that creates structured, fact-based medical summaries."},
                    {"role":"user","content":summary_prompt}
                ],
                temperature=0.4
            )
            st.session_state.pdf_summary = ai_summary.choices[0].message.content
        except Exception:
            pattern = r'([A-Z][^.]{20,150}\.)'
            bullets = re.findall(pattern, full_text)
            st.session_state.pdf_summary = "\n".join([f"- {b.strip()}" for b in bullets[:bullets_count]])

    keyword = st.text_input("Search in PDF Summary", value=st.session_state.pdf_search_keyword, key="pdf_search")
    st.session_state.pdf_search_keyword = keyword
    pdf_display = st.session_state.pdf_summary or "No PDF summary yet."
    if keyword:
        pdf_display = re.sub(f"(?i)({re.escape(keyword)})", r"**\1**", pdf_display)
    st.markdown('<div class="pdf-summary-box">'+pdf_display+'</div>', unsafe_allow_html=True)

# ---------------------------- AI Response ----------------------------
def generate_ai_response(prompt):
    context = f"""
User: {prompt}
Brand: {brand}
RACE Segment: {segment}
Objective: {objective}
Doctor Barrier: {barrier}
Persona: {persona}
Specialty: {specialty}
PDF Summary: {st.session_state.pdf_summary}
Sales Call Flow: {', '.join(sales_call_flow)}
APACT Steps: {', '.join(APACT_STEPS)}
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"system","content":"You are a helpful GSK sales assistant."},
                  {"role":"user","content":context}],
        temperature=0.65
    )
    return response.choices[0].message.content

# ---------------------------- Chat Rendering ----------------------------
def _format_content_to_html(text):
    if not text: return ""
    esc = escape(text).replace('\r\n','\n').replace('\r','\n')
    out = "".join(f"&bull;&nbsp;{ln[2:]}<br>" if ln.strip().startswith(('-','•')) else (ln+'<br>' if ln else '<br>') for ln in esc.split('\n'))
    return out

def render_chat_history():
    html_out = ""
    for msg in st.session_state.chat_history:
        user_html = _format_content_to_html(msg.get("user",""))
        ai_html = _format_content_to_html(msg.get("ai",""))
        audio_html = f'<div class="chat-bubble-audio">🔊 AI Voice:<br><audio controls src="data:audio/mp3;base64,{msg.get("audio_base64","")}"></audio></div>' if msg.get("audio_base64") else ""
        html_out += f'''
        <div class="chat-bubble-ai">
            <div style="color:#0b61a4;"><b>🧑 You:</b></div>
            <div style="margin:6px 0 10px 0;">{user_html}</div>
            <div style="color:#333;"><b>🤖 AI:</b></div>
            <div style="margin:6px 0 8px 0;">{ai_html}</div>
            {audio_html}
        </div>
        '''
    html_out += "<div id='chat-bottom'></div>"
    st.markdown(f'<div class="chat-container">{html_out}</div>', unsafe_allow_html=True)
    st.markdown("<script>const chat=document.querySelector('.chat-container'); if(chat) chat.scrollTop = chat.scrollHeight;</script>", unsafe_allow_html=True)

# ---------------------------- Chat Input & Send ----------------------------
render_chat_history()

with st.container():
    if st.button("🗑️ Clear Conversation", key="clear_chat"):
        st.session_state.chat_history = []
        st.runtime.scriptrunner.rerun() # safely refresh page

    if "chat_input" not in st.session_state:
        st.session_state.chat_input = ""

    col1, col2 = st.columns([5,1])
    with col1:
        user_input = st.text_input("", value=st.session_state.chat_input, key="chat_input", placeholder="Type your message...")
    with col2:
        send = st.button("Send", key="send_button")

    if send and user_input.strip():
        ai_resp = generate_ai_response(user_input)
        audio_base64 = generate_audio(ai_resp)
        st.session_state.chat_history.append({
            "user": user_input,
            "ai": ai_resp,
            "audio_base64": audio_base64
        })
        # Instead of clearing session_state directly, trigger rerun
        st.experimental_rerun()

# ---------------------------- Export Chat ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("📥 Export Chat (.docx)"):
        doc = Document()
        doc.add_heading("AI Sales Call Assistant Chat History", 0)
        for msg in st.session_state.chat_history:
            doc.add_paragraph(f'User: {msg.get("user","")}')
            doc.add_paragraph(f'AI: {msg.get("ai","")}')
            doc.add_paragraph('')  # spacing
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp.name)
        with open(tmp.name, "rb") as f:
            data = f.read()
        st.download_button(
            "⬇️ Download Chat History (.docx)", 
            data=data, 
            file_name="chat_history.docx", 
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
