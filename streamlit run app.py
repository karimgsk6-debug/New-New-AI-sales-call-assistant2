# app.py
import streamlit as st
from PIL import Image, ImageStat
from io import BytesIO
import requests
import tempfile
import string
import re

from gtts import gTTS
from groq import Groq

try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False

st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- Session Defaults ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "extracted_medical_ref" not in st.session_state:
    st.session_state.extracted_medical_ref = ""
if "language" not in st.session_state:
    st.session_state.language = "English"
if "voice_pref" not in st.session_state:
    st.session_state.voice_pref = "English Neural"

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = "https://www.shutterstock.com/image-photo/excited-girl-white-shirt-using-260nw-708132598.jpg"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"

def get_brightness(url: str) -> int:
    try:
        r = requests.get(url, timeout=6)
        img = Image.open(BytesIO(r.content)).convert("L")
        stat = ImageStat.Stat(img)
        return int(stat.mean[0])
    except:
        return 255

brightness = get_brightness(BACKGROUND_URL)
text_color = "black" if brightness > 130 else "white"

# ---------------------------- CSS ----------------------------
CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-attachment: fixed;
  background-size: auto 150%;
  transition: background-size 0.25s ease;
}}
.title-box {{
  background: rgba(245,245,245,0.7);
  padding: 20px;
  border-radius: 16px;
  text-align: center;
  max-width: 90%;
  margin: 12px auto;
}}
.title-box h1 {{ margin:0; font-size:34px; font-weight:800; color:#000; }}
.title-box p {{ margin:6px 0 0 0; font-size:16px; color:#333; }}
.pdf-summary-box {{
  background: #E6F0FF; 
  padding: 12px; 
  border-radius: 14px; 
  margin-bottom: 12px;
  white-space: pre-line;
}}
.chat-container {{
  height: 60vh;
  overflow:auto;
  padding:12px;
  border-radius:10px;
  background: rgba(255,255,255,0.76);
  display:flex;
  flex-direction:column-reverse;
}}
.chat-bubble-user, .chat-bubble-ai {{
  display:inline-block;
  padding:12px;
  border-radius:12px;
  margin:8px 0;
  max-width: 86%;
  word-wrap: break-word;
  color: #000;
}}
.chat-bubble-user {{ background: #DCF8C6; margin-left:auto; }}
.chat-bubble-ai {{ background: #E6F0FF; margin-right:auto; }}
.bottom-bar {{
  position: fixed;
  bottom: 12px;
  left: 16px;
  right: 16px;
  z-index: 1200;
  background: rgba(255,255,255,0.98);
  padding:10px;
  border-radius:12px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.06);
  display:flex;
  gap:12px;
  align-items:center;
}}
.bottom-bar input[type="text"] {{
  flex:1;
  padding:10px 12px;
  border-radius:8px;
  border:1px solid #ddd;
  outline:none;
}}
.bottom-bar button {{
  min-width:110px;
  padding:8px 12px;
  border-radius:8px;
  background:#ff8c00;
  color:white;
  border:none;
  font-weight:600;
  cursor:pointer;
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
    st.session_state.voice_pref = st.selectbox("Voice preference", ["English Neural","Arabic Neural","Male Neural","Female Neural"])

# ---------------------------- Title Box ----------------------------
st.markdown(f'<div class="title-box"><img src="{GSK_LOGO_URL}" width="140"><h1>💡 AI Sales Call Assistant</h1><p>Powered by AI to equip reps for smarter HCP conversations</p></div>', unsafe_allow_html=True)

# ---------------------------- PDF Upload ----------------------------
with st.expander("📄 Upload PDF & Summary", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
    if uploaded_pdf:
        from PyPDF2 import PdfReader
        reader = PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"
        bullets = re.findall(r"([A-Z][^.]{10,200}\d{0,4}[^.]*(?:\.)?)", full_text)
        st.session_state.pdf_summary = "\n".join([f"- {b.strip()}" for b in bullets[:15]])
        st.markdown('<div class="pdf-summary-box">'+st.session_state.pdf_summary+'</div>', unsafe_allow_html=True)
        keyword = st.text_input("Search in PDF Summary")
        if keyword:
            highlighted = st.session_state.pdf_summary.replace(keyword, f"**{keyword}**")
            st.markdown('<div class="pdf-summary-box">'+highlighted+'</div>', unsafe_allow_html=True)
        with st.expander("Extracted References", expanded=False):
            st.write(st.session_state.extracted_medical_ref)

# ---------------------------- Chat History ----------------------------
st.markdown("<h3>💬 Chat</h3>", unsafe_allow_html=True)
chat_container = st.container()

def render_chat_history():
    with chat_container:
        html_out = ""
        for msg in st.session_state.chat_history:
            content = msg["content"]
            if msg["role"]=="user":
                html_out += f'<div class="chat-bubble-user">{content}</div>'
            else:
                html_out += f'<div class="chat-bubble-ai">{content}</div>'
        st.markdown(html_out, unsafe_allow_html=True)

render_chat_history()

# ---------------------------- AI Response & gTTS ----------------------------
def generate_ai_response(prompt):
    if not client:
        return "⚠️ AI service not configured"
    
    # Build context with PDF summary + sales call & APACT
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

Instructions:
- Structure response along sales call steps: {', '.join(sales_call_flow)}
- For each step, inject APACT actions: {', '.join(APACT_STEPS)}
- Make responses actionable and concise.
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"system","content":"You are a helpful GSK medical sales assistant."},
                  {"role":"user","content":context}],
        temperature=0.65
    )
    ai_text = response.choices[0].message.content

    # gTTS for Male Neural voice
    if "Male" in st.session_state.voice_pref:
        # Add natural pauses: replace periods and bullets with short pause markers
        tts_text = ai_text.replace(". ",". \n").replace("- ","\n- ")
        tts_text_clean = tts_text.translate(str.maketrans("", "", string.punctuation))
        tts = gTTS(text=tts_text_clean, lang="en", tld="co.uk")
        tmp_mp3 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tmp_mp3.name)
        st.audio(tmp_mp3.name, format="audio/mp3")

    return ai_text

# ---------------------------- Bottom Chat Input ----------------------------
with st.container():
    col1, col2 = st.columns([8,1])
    with col1:
        user_input = st.text_input("Type your message...", key="chat_input")
    with col2:
        send = st.button("Send")
    if send and user_input.strip():
        st.session_state.chat_history.append({"role":"user","content":user_input})
        ai_resp = generate_ai_response(user_input)
        st.session_state.chat_history.append({"role":"ai","content":ai_resp})
        render_chat_history()

# ---------------------------- Export Chat ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("📥 Export Chat (.docx)"):
        doc = Document()
        doc.add_heading("AI Sales Call Assistant Chat History", 0)
        for msg in st.session_state.chat_history:
            doc.add_paragraph(f'{msg["role"].capitalize()}: {msg["content"]}')
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp.name)
        with open(tmp.name,"rb") as f:
            data = f.read()
        st.download_button("⬇️ Download Chat History (.docx)", data=data, file_name="chat_history.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
