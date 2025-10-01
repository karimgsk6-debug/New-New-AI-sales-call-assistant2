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
# AI Logo URL
AI_LOGO_URL = "https://sdmntpraustraliaeast.oaiusercontent.com/files/00000000-4b60-61fa-9450-ba1622fd3488/raw?se=2025-10-01T22%3A14%3A53Z&sp=r&sv=2024-08-04&sr=b&scid=5e0685db-737d-5bda-a960-befd761ac516&skoid=eb780365-537d-4279-a878-cae64e33aa9c&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-10-01T19%3A10%3A31Z&ske=2025-10-02T19%3A10%3A31Z&sks=b&skv=2024-08-04&sig=Fq1ONP%2BC2j2OlBh8kGjhfgU4zzbXf/ZJ5om/q%2B4BKCE%3D"

# Add in your CSS block
st.markdown(f"""
<style>
/* Top-right AI logo */
.ai-logo {{
    position: absolute;
    top: 10px;
    right: 20px;
    width: 120px;   /* adjust size as needed */
    height: auto;
    z-index: 1000;
}}
</style>

<img src="{AI_LOGO_URL}" class="ai-logo">
""", unsafe_allow_html=True)

# ---------------------------- TTS Setup (ElevenLabs fallback to gTTS) ----------------------------
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except ModuleNotFoundError:
    ELEVENLABS_AVAILABLE = False

# Always import gTTS for fallback
from gtts import gTTS

# ElevenLabs config
ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")  # Elderly Male Voice ID
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    elevenlabs.api_key = ELEVENLABS_API_KEY
else:
    ELEVENLABS_AVAILABLE = False  # Ensure fallback to gTTS

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
for key, value in {
    "chat_history": [],
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "voice_pref": "Male",
    "language": "English",
    "pdf_search_keyword": "",
    "pdf_summary_size": "Normal",
    "chat_input": ""
}.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = "https://sdmntprpolandcentral.oaiusercontent.com/files/00000000-466c-620a-81c6-59c1f5c85484/raw?se=2025-10-01T21%3A36%3A08Z&sp=r&sv=2024-08-04&sr=b&scid=e48070e4-6fe8-551d-b151-1591946f0e60&skoid=eb780365-537d-4279-a878-cae64e33aa9c&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-10-01T19%3A07%3A59Z&ske=2025-10-02T19%3A07%3A59Z&sks=b&skv=2024-08-04&sig=3/PGGYaseBkvjJWbMBbuzsZeNyvlAXRSqcswf%2Bm1IZI%3D"
GSK_LOGO_URL = "https://usppg.org/wp-content/uploads/2025/04/GSK-logo.png"

# ---------------------------- CSS ----------------------------
CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-attachment: fixed;
  background-size: auto 120%;
}}
.title-box {{
  background: rgba(245,245,245,0.6);
  padding: 12px;
  border-radius: 16px;
  text-align: Left;
  margin: 12px auto;
}}
.pdf-summary-box {{
  background: rgba(245,245,245,0.7);; 
  padding: 12px; 
  border-radius: 14px; 
  margin-bottom: 12px;
  white-space: pre-line;
}}
.chat-container {{
  max-height: 80vh;
  overflow-y: auto;
  padding: 12px;
  padding-bottom: 15px;
  border-radius: 20px;
  background: rgba(255,255,255,0.6);
  margin-bottom: 5;
}}
.chat-bubble-user, .chat-bubble-ai, .chat-bubble-audio {{
  display:block;
  padding:12px;
  border-radius:12px;
  margin:10px 0;
  max-width: 90%;
  word-wrap: break-word;
}}
.chat-bubble-user {{ background: rgba(245,245,245,0.6); color:white; margin-left:auto; }}
.chat-bubble-ai {{ background: rgba(245,245,245,0.7); margin-right:auto; color:#000; }}
.chat-bubble-audio {{ background: rgba(245,245,245,0.7); margin-right:auto; font-size:0.9em; padding:10px; margin-top:8px; }}
footer, header {{ z-index: 0; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ Client ----------------------------
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Filters / Sidebar ----------------------------
gsk_brands = ["Shingrix", "Trelegy", "Zejula"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Rheumatologist","Internal medicine","Neurologists"]
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
doctor_barriers = ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"]
sales_call_flow = ["Prepare","Engage","Create Opportunities","Impact GSO","Influence","Post Call Analysis"]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]
objectives = ["Awareness","Adoption","Retention"]

with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Select Brand", gsk_brands, key="select_brand")
    specialty = st.selectbox("Select Doctor Specialty", specialties, key="select_specialty")
    segment = st.selectbox("Select RACE Segment", race_segments, key="select_segment")
    persona = st.selectbox("Select HCP Persona", personas, key="select_persona")
    barrier = st.multiselect("Select Doctor Barrier", doctor_barriers, key="select_barrier")
    objective = st.selectbox("Select Objective", objectives, key="select_objective")
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"], key="select_response_length")
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"], key="select_response_tone")
    st.session_state.language = st.radio("Language", ["English","Arabic"], horizontal=True, key="radio_language")


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
            summary_prompt = f"""
            Summarize the following medical/pharma document into {bullets_count} main bullet points. 
            Document Text:
            {full_text[:12000]}
            """

            ai_summary = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":"You are a helpful assistant that creates structured, fact-based medical summaries."},
                          {"role":"user","content":summary_prompt}],
                temperature=0.4
            )
            st.session_state.pdf_summary = ai_summary.choices[0].message.content

        except Exception:
            bullets = re.findall(r'([A-Z][^.]{20,200}\.)', full_text)
            st.session_state.pdf_summary = "\n".join([f"- {b.strip()}" for b in bullets[:bullets_count]])

    keyword = st.text_input("Search in PDF Summary", value=st.session_state.pdf_search_keyword, key="pdf_search")
    st.session_state.pdf_search_keyword = keyword
    pdf_display = st.session_state.pdf_summary or "No PDF summary yet."
    if keyword:
        pdf_display = re.sub(f"(?i)({re.escape(keyword)})", r"**\1**", pdf_display)
    st.markdown('<div class="pdf-summary-box">'+pdf_display+'</div>', unsafe_allow_html=True)

# ---------------------------- AI Response Function ----------------------------
def generate_ai_response(prompt):
    context = f"""
User: {prompt}
Brand: {brand}
RACE Segment: {segment}
Objective: {objective}
Doctor Barrier: {barrier}
Persona: {persona}
Specialty: {specialty}

PDF Summary:
{st.session_state.pdf_summary}

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
    lines = esc.split('\n')
    out = ""
    for ln in lines:
        ln = ln.strip()
        if ln.startswith('- ') or ln.startswith('• '):
            out += f'&bull;&nbsp;{ln[2:]}<br>'
        else:
            out += f'{ln}<br>' if ln else '<br>'
    return out

def render_chat_history():
    html_out = ""
    for msg in st.session_state.chat_history:
        user_html = _format_content_to_html(msg.get("user",""))
        ai_html = _format_content_to_html(msg.get("ai",""))
        audio_html = f'<div class="chat-bubble-audio">🔊 AI Voice:<br><audio controls src="data:audio/mp3;base64,{msg["audio_base64"]}"></audio></div>' if msg.get("audio_base64") else ""
        html_out += f'''
        <div class="chat-bubble-ai">
            <div style="color:#0b61a4;"><b>🧑 You:</b></div>
            <div style="margin:6px 0 10px 0;">{user_html}</div>
            <div style="color:#333;"><b>🤖 AI:</b></div>
            <div style="margin:6px 0 8px 0;">{ai_html}</div>
            {audio_html}
        </div>'''
    html_out += "<div id='chat-bottom'></div>"
    st.markdown(f'<div class="chat-container">{html_out}</div>', unsafe_allow_html=True)

# ---------------------------- Chat Input & Controls ----------------------------
with st.container():
    if st.button("🗑️ Clear Conversation", key="clear_chat"):
        st.session_state.chat_history = []
        render_chat_history()

    render_chat_history()

    user_input = st.text_input(
        "Type your message...", key="chat_input",
        label_visibility="collapsed", placeholder="Ask me anything..."
    )
    send = st.button("Send", key="send_button")

    if send and user_input.strip():
        ai_resp = generate_ai_response(user_input)
        audio_base64 = generate_audio(ai_resp)
        st.session_state.chat_history.append({
            "user": user_input,
            "ai": ai_resp,
            "audio_base64": audio_base64
        })
        render_chat_history()

# ---------------------------- Export Chat ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("📥 Export Chat (.docx)"):
        doc = Document()
        doc.add_heading("AI Sales Call Assistant Chat History", 0)
        for msg in st.session_state.chat_history:
            doc.add_paragraph(f'User: {msg.get("user","")}')
            doc.add_paragraph(f'AI: {msg.get("ai","")}')
            doc.add_paragraph('')
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp.name)
        with open(tmp.name,"rb") as f:
            data = f.read()
        st.download_button("⬇️ Download Chat History (.docx)", data=data, file_name="chat_history.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
