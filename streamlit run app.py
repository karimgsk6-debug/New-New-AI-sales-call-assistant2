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
st.markdown("""
<style>
.chat-container {
    height: 65vh;   /* auto-resizes with sidebar */
    overflow-y: auto;
    padding: 10px;
    background: #f9f9f9;
    border-radius: 12px;
    border: 1px solid #ddd;
    margin-bottom: 60px; /* leave space for input bar */
}
.chat-bubble {
    background: #fff;
    padding: 12px 16px;
    border-radius: 12px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.chat-bubble-user {
    background: #e7f3ff;
}
.chat-bubble-ai {
    background: #f1f1f1;
}
.bottom-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 8px 16px;
    background: #fff;
    border-top: 1px solid #ddd;
    display: flex;
    align-items: center;
    gap: 8px;
    z-index: 999;
}
.bottom-bar input {
    flex-grow: 1;
    padding: 10px;
    border-radius: 8px;
    border: 1px solid #ccc;
}
.small-btn {
    padding: 4px 10px !important;
    font-size: 13px !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------- Chat Rendering ----------------------------
def render_chat_history():
    html_out = ""
    for msg in st.session_state.chat_history:
        html_out += f"""
        <div class="chat-bubble chat-bubble-ai">
            <b>🧑 You:</b> {msg["user"]}<br><br>
            <b>🤖 AI:</b> {msg["ai"]}
            <div class="chat-bubble-audio">
                🔊 AI Voice:<br>
                <audio controls src="data:audio/mp3;base64,{msg['audio_base64']}"></audio>
            </div>
        </div>
        """
    st.markdown(f'<div class="chat-container">{html_out}</div>', unsafe_allow_html=True)

# ---------------------------- Input Bar ----------------------------
render_chat_history()

st.markdown('<div class="bottom-bar">', unsafe_allow_html=True)
user_input = st.text_input("Type your message...", key="chat_input", label_visibility="collapsed", placeholder="Ask me anything...")
send = st.button("Send", key="send_btn", help="Send message", type="primary")
clear = st.button("🗑️ Clear", key="clear_btn")
st.markdown('</div>', unsafe_allow_html=True)

# Handle actions
if clear:
    st.session_state.chat_history = []
    st.rerun()

if send and user_input.strip():
    ai_resp = generate_ai_response(user_input)
    audio_base64 = generate_audio(ai_resp)
    st.session_state.chat_history.append({
        "user": user_input,
        "ai": ai_resp,
        "audio_base64": audio_base64
    })
    st.rerun()

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
