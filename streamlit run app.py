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
except Exception:
    DOCX_AVAILABLE = False

# TTS (ElevenLabs fallback to gTTS)
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except ModuleNotFoundError:
    ELEVENLABS_AVAILABLE = False

from gtts import gTTS

# ElevenLabs config (from Streamlit secrets)
ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    elevenlabs.api_key = ELEVENLABS_API_KEY
else:
    ELEVENLABS_AVAILABLE = False

def generate_audio(text):
    try:
        text_proc = text
        for step in ["Acknowledge","Probing","Action","Confirm","Transition"]:
            text_proc = text_proc.replace(step, f"{step} ...")
        text_proc = re.sub(r'[,*]', '', text_proc)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        if ELEVENLABS_AVAILABLE:
            audio_stream = elevenlabs.generate(text=text_proc, voice=ELEVENLABS_VOICE_ID, stream=True)
            with open(tmp_file.name, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
        else:
            tts = gTTS(text=text_proc, lang="en", slow=True)
            tts.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            audio_bytes = f.read()
        return base64.b64encode(audio_bytes).decode()
    except Exception:
        return ""

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

# ---------------------------- GROQ Client ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = None
if GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

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
  background: rgba(245,245,245,0.9);
  padding: 16px;
  border-radius: 12px;
  text-align: center;
  margin: 10px auto;
}}
.chat-container {{
  height: calc(100vh - 260px);
  min-height: 300px;
  overflow-y: auto;
  padding: 16px;
  padding-bottom: 160px;
  border-radius: 10px;
  background: rgba(255,255,255,0.88);
  border: 1px solid rgba(0,0,0,0.06);
}}
.chat-bubble {{
  display: block;
  padding: 12px 14px;
  border-radius: 12px;
  margin: 10px 0;
  max-width: 92%;
  box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  white-space: pre-wrap;
}}
.chat-bubble .role-label {{ font-weight:600; margin-bottom:4px; display:block; }}
.chat-bubble.ai {{ background:#f0f7ff; color:#000; margin-left:0; }}
.chat-bubble.user {{ background:#e6f3ff; color:#000; margin-left:auto; text-align:left; }}
.audio-box {{
  margin-top:8px;
  padding:8px;
  background:#efefef;
  border-radius:8px;
}}
.bottom-bar-wrapper {{
  position: fixed;
  left: 20px;
  right: 20px;
  bottom: 18px;
  z-index: 1100;
  display:flex;
  gap:10px;
  align-items:center;
  justify-content:space-between;
  pointer-events: none;
}}
.bottom-bar {{
  pointer-events: auto;
  background: rgba(255,255,255,0.98);
  border-radius: 10px;
  padding: 8px;
  display:flex;
  gap:8px;
  align-items:center;
  flex: 1 1 auto;
  box-shadow: 0 6px 20px rgba(0,0,0,0.08);
  border: 1px solid rgba(0,0,0,0.06);
}}
.compact-send {{
  padding: 6px 10px !important;
  min-width: 40px !important;
  height: 40px !important;
  border-radius: 8px !important;
  font-size: 16px !important;
}}
.clear-btn-area {{
  margin-bottom: 8px;
  display:flex;
  justify-content:flex-end;
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

# ---------------------------- Sidebar Filters ----------------------------
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

# ---------------------------- Title ----------------------------
st.markdown(f'<div class="title-box"><img src="{GSK_LOGO_URL}" width="140"><h2 style="margin:0">💡 AI Sales Call Assistant</h2><div style="font-size:13px;color:#333">Powered by AI to equip reps for smarter HCP conversations</div></div>', unsafe_allow_html=True)

# ---------------------------- PDF Upload & Enhanced Summary ----------------------------
with st.expander("📄 PDF Summary", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
    st.session_state.pdf_summary_size = st.radio("PDF Summary Size", ["Consisted","Normal","Detailed"], horizontal=True)
    if uploaded_pdf:
        try:
            reader = PdfReader(uploaded_pdf)
            full_text = "".join([p.extract_text() or "" for p in reader.pages])
        except Exception:
            full_text = ""
        st.session_state.uploaded_pdf_text = full_text

        bullets_count = {"Consisted":5,"Normal":10,"Detailed":20}.get(st.session_state.pdf_summary_size,10)
        if full_text.strip():
            prompt = f"""
Summarize the following document into {bullets_count} main bullet points.
For each main bullet provide 1-3 sub-bullets with fact-based details (percentages, study names, years, clinical-trial phases, guidelines).
Format exactly as:
- Main point
   • sub point 1
   • sub point 2

Document:
{full_text[:12000]}
"""
            summary_text = ""
            if client:
                try:
                    resp = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role":"system","content":"You are a helpful assistant that creates structured, fact-based medical summaries."},
                                  {"role":"user","content":prompt}],
                        temperature=0.3
                    )
                    summary_text = resp.choices[0].message.content
                except Exception:
                    summary_text = ""
            if not summary_text:
                pattern = r'([A-Z][^.\n]{20,200}\b(?:\d{1,3}%?|\d{4}|study|guideline|CDC|FDA|Lancet|NEJM|BMJ|JAMA)[^.]*\.)'
                bullets = re.findall(pattern, full_text, flags=re.IGNORECASE)
                if len(bullets) < bullets_count:
                    fallback_bullets = re.findall(r'([A-Z][^.]{20,150}\.)', full_text)
                    for b in fallback_bullets:
                        if b not in bullets:
                            bullets.append(b)
                        if len(bullets) >= bullets_count:
                            break
                summary_text = "\n".join([f"- {b.strip()}" for b in bullets[:bullets_count]])
            st.session_state.pdf_summary = summary_text

    keyword = st.text_input("Search in PDF Summary", value=st.session_state.pdf_search_keyword, key="pdf_search")
    st.session_state.pdf_search_keyword = keyword
    pdf_display = st.session_state.pdf_summary or "No PDF summary yet."
    if keyword:
        pdf_display = re.sub(f"(?i)({re.escape(keyword)})", r"**\1**", pdf_display)
    st.markdown('<div style="margin-top:10px" class="pdf-summary-box">'+pdf_display+'</div>', unsafe_allow_html=True)

# ---------------------------- AI Response ----------------------------
def generate_ai_response(prompt: str) -> str:
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
    if client:
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":"You are a helpful GSK sales assistant."},
                          {"role":"user","content":context}],
                temperature=0.65
            )
            return response.choices[0].message.content
        except Exception:
            pass
    return (
        f"Sorry — I couldn't reach the model. Here's guidance:\n- User question: {prompt}\n"
        "- Suggested approach: Acknowledge concern, clarify, reference PDF, propose next action."
    )

# ---------------------------- Normalize Chat History ----------------------------
def normalize_chat_history():
    raw = st.session_state.chat_history
    if not raw:
        return
    first = raw[0]
    if isinstance(first, dict) and ("user" not in first or "ai" not in first):
        new = []
        i = 0
        while i < len(raw):
            item = raw[i]
            user_text, ai_text, audio = "", "", ""
            if item.get("role") == "user":
                user_text = item.get("content","")
                j = i+1
                while j < len(raw):
                    if raw[j].get("role")=="ai":
                        ai_text = raw[j].get("content","")
                        audio = raw[j].get("audio_base64","")
                        break
                    j+=1
                new.append({"user": user_text, "ai": ai_text, "audio_base64": audio})
                if j>i: i=j+1
                else: i+=1
            elif item.get("role")=="ai":
                new.append({"user":"","ai":item.get("content",""),"audio_base64":item.get("audio_base64","")})
                i+=1
            else:
                if "content" in item: new.append({"user":"","ai":item.get("content",""),"audio_base64":item.get("audio_base64","")})
                i+=1
        st.session_state.chat_history=new

normalize_chat_history()

# ---------------------------- Format HTML ----------------------------
def _format_content_to_html(text):
    if not text: return ""
    esc = escape(text).replace('\r\n','\n').replace('\r','\n')
    lines = esc.split('\n')
    out = ""
    for ln in lines:
        if ln.startswith('- '):
            out += f'&bull; {ln[2:]}<br>'
        elif ln.startswith('• ') or ln.startswith('* '):
            out += f'&nbsp;&nbsp;&bull; {ln[2:]}<br>'
        else:
            out += '<br>' if ln=="" else f'{ln}<br>'
    return out

# ---------------------------- Render Chat ----------------------------
def render_chat_history():
    normalize_chat_history()
    html=""
    for msg in st.session_state.chat_history:
        user_html = _format_content_to_html(msg.get("user",""))
        ai_html = _format_content_to_html(msg.get("ai",""))
        audio_html=""
        if msg.get("audio_base64"):
            audio_html=f'<div class="audio-box">🔊 AI Voice:<br><audio controls src="data:audio/mp3;base64,{msg["audio_base64"]}"></audio></div>'
        html+=f'''
        <div class="chat-bubble ai">
            <span class="role-label">🧑 You:</span>
            <div>{user_html}</div>
            <span class="role-label" style="margin-top:8px;">🤖 AI:</span>
            <div>{ai_html}</div>
            {audio_html}
        </div>
        '''
    html+='<div id="chat-bottom"></div>'
    st.markdown(f'<div class="chat-container" id="chat-container">{html}</div>', unsafe_allow_html=True)
    st.markdown("""
    <script>
    const container = document.getElementById('chat-container');
    if(container) { container.scrollTop = container.scrollHeight; }
    setTimeout(()=> {
        const inputs = document.querySelectorAll('textarea, input[type="text"]');
        if(inputs.length) inputs[inputs.length-1].focus();
    },100);
    </script>
    """, unsafe_allow_html=True)

# ---------------------------- Clear Chat Button ----------------------------
st.markdown('<div class="clear-btn-area">', unsafe_allow_html=True)
if st.button("🗑️ Clear Conversation"):
    st.session_state.chat_history=[]
    st.experimental_rerun()
st.markdown('</div>', unsafe_allow_html=True)

render_chat_history()

# ---------------------------- Bottom Bar Input ----------------------------
user_input = st.text_area("", value="", key="chat_input", placeholder="Type message (Shift+Enter for newline)", height=80)
col1, col2 = st.columns([0.08,0.92])
with col1:
    send_clicked = st.button("📤", key="send_button", help="Send message", use_container_width=False)
with col2: pass

if send_clicked and user_input.strip():
    ai_resp = generate_ai_response(user_input)
    audio_b64 = generate_audio(ai_resp)
    st.session_state.chat_history.append({
        "user": user_input,
        "ai": ai_resp,
        "audio_base64": audio_b64
    })
    st.experimental_rerun()

# ---------------------------- Export Chat ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("📥 Export Chat (.docx)"):
        doc = Document()
        doc.add_heading("AI Sales Call Assistant Chat History",0)
        for msg in st.session_state.chat_history:
            doc.add_paragraph(f'User: {msg.get("user","")}')
            doc.add_paragraph(f'AI: {msg.get("ai","")}')
            doc.add_paragraph('')
        tmp = tempfile.NamedTemporaryFile(delete=False,suffix=".docx")
        doc.save(tmp.name)
        with open(tmp.name,"rb") as f: data=f.read()
        st.download_button("⬇️ Download Chat History (.docx)", data=data, file_name="chat_history.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
