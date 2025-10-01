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
    # Add APACT pauses
    for step in ["Acknowledge","Probing","Action","Confirm","Transition"]:
        text = text.replace(step, f"{step} ...")
    # Remove punctuation for smoother reading (optional)
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
if "chat_history" not in st.session_state:
    # canonical format: list of {"user": str, "ai": str, "audio_base64": str}
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

/* Title and PDF summary boxes */
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

/* Chat area */
.chat-container {{
  max-height: 65vh;
  overflow-y: auto;
  padding: 12px;
  padding-bottom: 160px; /* leave room for fixed input */
  border-radius: 10px;
  background: rgba(255,255,255,0.8);
  margin-bottom: 0;
}}

/* Bubbles */
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

/* Make last Streamlit text input and button fixed to bottom
   (we render the chat_input as the last input in the page so :last-of-type targets it) */
div[data-testid="stTextInput"]:last-of-type,
div[data-testid="stTextArea"]:last-of-type {{
  position: fixed !important;
  bottom: 18px;
  left: 20px;
  right: 160px;
  z-index: 10002;
  background: rgba(255,255,255,0.9);
  border-radius: 10px;
  padding: 6px;
}}

/* fix the last button (Send) to the right */
div[data-testid="stButton"]:last-of-type {{
  position: fixed !important;
  bottom: 16px;
  right: 20px;
  z-index: 10003;
}}

/* small responsiveness */
@media (max-width: 800px) {{
  div[data-testid="stTextInput"]:last-of-type,
  div[data-testid="stTextArea"]:last-of-type {{
    left: 12px;
    right: 100px;
  }}
}}

/* ensure fixed input overlays properly */
footer, header {{
  z-index: 0;
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

        # --- Enhanced AI summarization with sub-bullets ---
        try:
            summary_prompt = f"""
            Summarize the following medical/pharma document into {bullets_count} main bullet points. 

            Format rules:
            - Each main bullet point should be a broad theme or finding.
            - Under each main bullet, provide 2–4 sub-bullets (•) with elaborative, fact-based details.
            - Sub-bullets must include supporting evidence if available (percentages, years, clinical trials, guidelines, studies).
            - Write in a professional, concise, and factual style.
            - Always structure like this:

            - Main Point
               • Sub fact 1
               • Sub fact 2
               • Sub fact 3

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
            # fallback regex summary if AI fails
            pattern = r'([A-Z][^.\n]{20,200}\b(?:\d{1,3}%?|\d{4}|study|guideline|CDC|FDA|Lancet|NEJM|BMJ|JAMA)[^.]*\.)'
            bullets = re.findall(pattern, full_text, flags=re.IGNORECASE)
            if len(bullets) < bullets_count:
                fallback_bullets = re.findall(r'([A-Z][^.]{20,150}\.)', full_text)
                for b in fallback_bullets:
                    if b not in bullets:
                        bullets.append(b)
                    if len(bullets) >= bullets_count:
                        break
            # Format as basic bullets with no sub-bullets
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

# ---------------------------- Normalize existing chat history formats ----------------------------
def normalize_chat_history():
    """
    Converts older message pairs like [{"role":"user","content":..},{"role":"ai","content":..}, ...]
    into canonical form: [{"user":..,"ai":..,"audio_base64":..}, ...]
    """
    raw = st.session_state.chat_history
    # if already canonical, nothing to do
    if not raw:
        return
    # detect a likely legacy format by checking first element keys
    first = raw[0]
    if isinstance(first, dict) and ("role" in first or "content" in first) and not ("user" in first and "ai" in first):
        new = []
        i = 0
        while i < len(raw):
            item = raw[i]
            if item.get("role") == "user":
                user_text = item.get("content", "")
                # look ahead for next AI message
                ai_text = ""
                audio = ""
                j = i + 1
                while j < len(raw):
                    if raw[j].get("role") == "ai":
                        ai_text = raw[j].get("content", "")
                        audio = raw[j].get("audio_base64", "")
                        break
                    j += 1
                new.append({"user": user_text, "ai": ai_text, "audio_base64": audio})
                if j > i:
                    i = j + 1
                else:
                    i += 1
            elif item.get("role") == "ai":
                new.append({"user": "", "ai": item.get("content", ""), "audio_base64": item.get("audio_base64", "")})
                i += 1
            else:
                # unknown structure: try to salvage
                if "content" in item:
                    new.append({"user": "", "ai": item.get("content", ""), "audio_base64": item.get("audio_base64", "")})
                i += 1
        st.session_state.chat_history = new
    else:
        # already canonical or different but fine - leave as is
        return

# run normalization once
normalize_chat_history()

# ---------------------------- Chat Rendering ----------------------------
def _format_content_to_html(text):
    """Escape text then convert simple bullets and newlines into HTML-friendly representation."""
    if not text:
        return ""
    esc = escape(text)
    # Normalize newlines
    esc = esc.replace('\r\n', '\n').replace('\r', '\n')
    lines = esc.split('\n')
    out = ""
    for ln in lines:
        ln = ln.strip()
        if ln.startswith('- '):
            out += f'&bull;&nbsp;{ln[2:]}<br>'
        elif ln.startswith('• '):
            out += f'&bull;&nbsp;{ln[2:]}<br>'
        else:
            # preserve blank lines
            if ln == "":
                out += '<br>'
            else:
                out += f'{ln}<br>'
    return out

def render_chat_history():
    # ensure normalization in case session mutated
    normalize_chat_history()

    html_out = ""
    for msg in st.session_state.chat_history:
        user_html = _format_content_to_html(msg.get("user", ""))
        ai_html = _format_content_to_html(msg.get("ai", ""))
        audio_html = ""
        if msg.get("audio_base64"):
            audio_html = f'<div class="chat-bubble-audio">🔊 AI Voice:<br><audio controls src="data:audio/mp3;base64,{msg["audio_base64"]}"></audio></div>'

        # Combined single bubble per turn (user + ai)
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

    # Auto-scroll & focus helper (scroll chat and focus the last input)
    scroll_js = """
    <script>
    (function(){
        const chat = document.querySelector('.chat-container');
        if(chat) { chat.scrollTop = chat.scrollHeight; }
        const bottom = document.getElementById('chat-bottom');
        if(bottom) { bottom.scrollIntoView({behavior:'auto', block:'end'}); }
        // focus last text input (the pinned chat input)
        setTimeout(()=> {
            const inputs = document.querySelectorAll('input[type="text"], textarea');
            if(inputs.length) {
                const last = inputs[inputs.length - 1];
                try { last.focus(); } catch(e) {}
            }
        }, 120);
    })();
    </script>
    """
    st.markdown(scroll_js, unsafe_allow_html=True)

# ---------------------------- Chat Input ----------------------------
# We render the chat history first, then the Streamlit text_input (which our CSS pins to the bottom).
with st.container():
    if st.button("🗑️ Clear Conversation"):
        st.session_state.chat_history = []
        # after clearing, re-render
        render_chat_history()

    render_chat_history()

    # Chat input - kept as the *last* text input on the page so CSS :last-of-type pins it
    user_input = st.text_input("Type your message...", key="chat_input", label_visibility="collapsed", placeholder="Ask me anything...")
    send = st.button("Send", key="send_button")

    if send and user_input and user_input.strip():
        # call the model and audio
        ai_resp = generate_ai_response(user_input)
        audio_base64 = generate_audio(ai_resp)

        # append as a single turn
        st.session_state.chat_history.append({
            "user": user_input,
            "ai": ai_resp,
            "audio_base64": audio_base64
        })

        # clear input widget by resetting the session_state key
        st.session_state["chat_input"] = ""

        # re-render to show the new message and scroll
        render_chat_history()

# ---------------------------- Export Chat ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("📥 Export Chat (.docx)"):
        doc = Document()
        doc.add_heading("AI Sales Call Assistant Chat History", 0)
        for msg in st.session_state.chat_history:
            doc.add_paragraph(f'User: {msg.get("user", "")}')
            doc.add_paragraph(f'AI: {msg.get("ai", "")}')
            doc.add_paragraph('')  # spacing
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp.name)
        with open(tmp.name,"rb") as f:
            data = f.read()
        st.download_button("⬇️ Download Chat History (.docx)", data=data, file_name="chat_history.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
