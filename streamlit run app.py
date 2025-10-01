# app.py
import streamlit as st
from PyPDF2 import PdfReader
from gtts import gTTS
import base64
import tempfile
import re
from groq import Groq

# Optional docx export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False

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
    st.session_state.voice_pref = "Male Neural"
if "language" not in st.session_state:
    st.session_state.language = "English"
if "pdf_search_keyword" not in st.session_state:
    st.session_state.pdf_search_keyword = ""
if "pdf_summary_size" not in st.session_state:
    st.session_state.pdf_summary_size = "Normal"

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
  height: 60vh;
  overflow-y: auto;
  padding: 12px;
  border-radius: 10px;
  background: rgba(255,255,255,0.8);
  margin-bottom: 120px;
}}
.chat-bubble-user, .chat-bubble-ai, .chat-bubble-audio {{
  display:inline-block;
  padding:12px;
  border-radius:12px;
  margin:8px 0;
  max-width: 86%;
  word-wrap: break-word;
}}
.chat-bubble-user {{ background: #0078D7; color:white; margin-left:auto; }}
.chat-bubble-ai {{ background: #E6F0FF; margin-right:auto; }}
.chat-bubble-audio {{ background: #D3D3D3; margin-right:auto; font-size:0.9em; }}
.bottom-bar {{
  position: fixed;
  bottom: 12px;
  left: 16px;
  right: 16px;
  background: rgba(255,255,255,0.98);
  padding: 10px;
  border-radius: 12px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.06);
  display:flex;
  gap:12px;
  align-items:center;
  z-index: 1000;
}}
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
sales_call_flow = ["Prepare","Engage","Create Opportunities","Impact GSO","Influence","Post Call Analysis"]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist"]

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
    st.session_state.voice_pref = st.selectbox("Voice preference", ["Male Neural","Female Neural"])

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

        # --- AI summarization ---
        try:
            summary_prompt = f"""
            Summarize the following medical/pharma document into {bullets_count} main bullet points. 
            Provide 2–4 sub-bullets for each main point with factual details.
            Document Text:
            {full_text[:12000]}
            """
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
            pattern = r'([A-Z][^.\n]{20,200}\b(?:\d{1,3}%?|\d{4}|study|guideline|CDC|FDA|Lancet|NEJM|BMJ|JAMA)[^.]*\.)'
            bullets = re.findall(pattern, full_text, flags=re.IGNORECASE)
            if len(bullets) < bullets_count:
                fallback_bullets = re.findall(r'([A-Z][^.]{20,150}\.)', full_text)
                for b in fallback_bullets:
                    if b not in bullets:
                        bullets.append(b)
                    if len(bullets) >= bullets_count:
                        break
            st.session_state.pdf_summary = "\n".join([f"- {b.strip()}" for b in bullets[:bullets_count]])

    keyword = st.text_input("Search in PDF Summary", value=st.session_state.pdf_search_keyword)
    st.session_state.pdf_search_keyword = keyword
    pdf_display = st.session_state.pdf_summary
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

# ---------------------------- Generate TTS ----------------------------
def generate_audio(text):
    # Add APACT pauses
    for step in ["Acknowledge","Probing","Action","Confirm","Transition"]:
        text = text.replace(step, f"{step} ...")
    text = re.sub(r'[.,*]', '', text)
    tts = gTTS(text=text, lang="en", slow=True)
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(tmp_file.name)
    with open(tmp_file.name, "rb") as f:
        audio_bytes = f.read()
    return base64.b64encode(audio_bytes).decode()

# ---------------------------- Render Chat History ----------------------------
def render_chat_history():
    chat_html = ""
    for msg in st.session_state.chat_history:
        chat_html += f"""
        <div class="chat-bubble-user">
            🧑 You: {msg['user']}
        </div>
        <div class="chat-bubble-ai">
            🤖 AI: {msg['ai']}
            <div class="chat-bubble-audio">
                🔊 AI Voice:<br>
                <audio controls src="data:audio/mp3;base64,{msg['audio_base64']}"></audio>
            </div>
        </div>
        """
    st.markdown(f'<div class="chat-container">{chat_html}<div id="chat-bottom"></div></div>', unsafe_allow_html=True)
    st.markdown(
        "<script>var chat=document.querySelector('.chat-container');chat.scrollTop=chat.scrollHeight;</script>",
        unsafe_allow_html=True
    )

# ---------------------------- Send Message ----------------------------
def send_message():
    user_input = st.session_state.get("chat_input", "").strip()
    if not user_input:
        return
    ai_resp = generate_ai_response(user_input)
    audio_b64 = generate_audio(ai_resp)
    st.session_state.chat_history.append({
        "user": user_input,
        "ai": ai_resp,
        "audio_base64": audio_b64
    })
    st.session_state.chat_input = ""
    render_chat_history()

# ---------------------------- Bottom Input ----------------------------
st.markdown('<div class="bottom-bar">', unsafe_allow_html=True)
st.text_input("Type your message...", key="chat_input", label_visibility="collapsed", placeholder="Ask me anything...")
st.button("Send", on_click=send_message)
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Clear Chat ----------------------------
if st.button("🗑️ Clear Conversation"):
    st.session_state.chat_history = []

render_chat_history()

# ---------------------------- Export Chat ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("📥 Export Chat (.docx)"):
        doc = Document()
        doc.add_heading("AI Sales Call Assistant Chat History", 0)
        for msg in st.session_state.chat_history:
            doc.add_paragraph(f'User: {msg["user"]}')
            doc.add_paragraph(f'AI: {msg["ai"]}')
            doc.add_paragraph('')
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp.name)
        with open(tmp.name,"rb") as f:
            data = f.read()
        st.download_button("⬇️ Download Chat History (.docx)", data=data, file_name="chat_history.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
