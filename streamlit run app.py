import streamlit as st
from PIL import Image, ImageStat
from io import BytesIO
import requests
import base64
import os
import re
import tempfile
import asyncio
from datetime import datetime

# GROQ Client
from groq import Groq

# TTS
import edge_tts

# Docx Export
from docx import Document

# -------------------------- CONFIG --------------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")
st.set_option('deprecation.showfileUploaderEncoding', False)

# -------------------------- ASSETS --------------------------
BACKGROUND_URL = "https://drive.google.com/uc?id=1WlvNx4MqufxuGUw9ilLxGJLsuozbX17b"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png"

def get_brightness(url: str) -> int:
    try:
        r = requests.get(url, timeout=6)
        img = Image.open(BytesIO(r.content)).convert("L")
        stat = ImageStat.Stat(img)
        return int(stat.mean[0])
    except:
        return 255

text_color = "black" if get_brightness(BACKGROUND_URL) > 130 else "white"

# -------------------------- STYLING --------------------------
st.markdown(f"""
<style>
.stApp {{
  background: url("{BACKGROUND_URL}") no-repeat center top fixed;
  background-size: cover;
}}
.title-box {{
  background: rgba(245,245,245,0.7);
  padding: 20px; border-radius: 12px; text-align:center; max-width:90%; margin:auto;
}}
.chat-container {{
  max-height: 55vh; overflow-y:auto; padding:12px; border-radius:10px;
  background: rgba(255,255,255,0.8);
}}
.chat-bubble-user {{ background:#DCF8C6; border-radius:20px; padding:10px; margin:6px; max-width:70%; float:right; clear:both; }}
.chat-bubble-ai {{ background:#E6F0FF; border-radius:20px; padding:10px; margin:6px; max-width:70%; float:left; clear:both; }}
.pdf-summary-box {{ background:#E6F0FF; padding:12px; border-radius:12px; margin-bottom:10px; }}
.bottom-bar {{
  position:fixed; bottom:12px; left:16px; right:16px; z-index:1200;
  background: rgba(255,255,255,0.95); padding:10px; border-radius:12px;
  display:flex; gap:8px; align-items:center;
}}
.bottom-bar input[type="text"] {{ flex:1; padding:10px; border-radius:8px; border:1px solid #ddd; outline:none; }}
.bottom-bar button {{
  min-width:100px; padding:8px; border-radius:8px; background:#4CAF50; color:white; border:none; font-weight:600; cursor:pointer;
}}
</style>
""", unsafe_allow_html=True)

# -------------------------- SESSION STATE --------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "pdf_search" not in st.session_state:
    st.session_state.pdf_search = ""
if "extracted_refs" not in st.session_state:
    st.session_state.extracted_refs = ""
if "language" not in st.session_state:
    st.session_state.language = "English"
if "voice_pref" not in st.session_state:
    st.session_state.voice_pref = "English Male"

# -------------------------- FILTERS --------------------------
gsk_brands = ["Shingrix", "Trelegy", "Zejula"]
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = ["Time", "Cost", "Efficacy doubts", "Other"]
personas = ["Uncommitted", "Reluctant", "Patient Influenced", "Committed"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Pulmonologist"]

with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", gsk_brands)
    segment = st.selectbox("RACE Segment", race_segments)
    barrier = st.multiselect("Doctor Barrier(s)", doctor_barriers)
    objective = st.selectbox("Objective", objectives)
    specialty = st.selectbox("Specialty", specialties)
    persona = st.selectbox("HCP Persona", personas)
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"])
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"])
    st.session_state.language = st.radio("Language", ["English","Arabic"], horizontal=True)
    st.session_state.voice_pref = st.selectbox("Voice preference", ["English Male","Arabic Male","Default"])

# -------------------------- TITLE --------------------------
st.markdown(f"""
<div class="title-box">
  <img src="{GSK_LOGO_URL}" width="140"><br>
  <h1>💡 AI Sales Call Assistant</h1>
  <p>Powered by AI for smarter HCP conversations</p>
</div>
""", unsafe_allow_html=True)

# -------------------------- PDF UPLOAD & SUMMARY --------------------------
with st.expander("📄 Upload PDF & Summary", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF for reference", type=["pdf"])
    if uploaded_pdf:
        import PyPDF2
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text
        # Extract references
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_refs = ", ".join(matches) if matches else "None"
        # Simple bullet summary
        lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
        st.session_state.pdf_summary = "\n".join([f"- {ln}" for ln in lines[:10]])  # show first 10 bullets

    # Search inside PDF summary
    search_term = st.text_input("🔍 Search PDF summary", value=st.session_state.pdf_search)
    st.session_state.pdf_search = search_term

    if st.session_state.pdf_summary:
        summary_display = st.session_state.pdf_summary
        if search_term:
            summary_display = re.sub(f"({re.escape(search_term)})", r"<mark>\1</mark>", summary_display, flags=re.I)
        st.markdown(f'<div class="pdf-summary-box">{summary_display.replace("\\n","<br>")}</div>', unsafe_allow_html=True)

    # Collapsible extracted references
    with st.expander("📚 Extracted References", expanded=False):
        st.write(st.session_state.extracted_refs)

# -------------------------- GROQ CLIENT --------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
groq_client = Groq(api_key=GROQ_API_KEY)

def generate_ai_response(prompt: str) -> str:
    context = f"""
You are a GSK medical sales assistant. Always follow sales call steps: Prepare, Engage, Create Opportunities, Impact GSO, Influence, Post Call Analysis.
Use APACT for objections: Acknowledge, Probing, Action, Confirm, Transition.
Use PDF summary and extracted references if available: {st.session_state.pdf_summary}
"""
    resp = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"system","content":context},{"role":"user","content":prompt}]
    )
    return resp.choices[0].message.content

# -------------------------- TTS --------------------------
async def _edge_save_async(ssml_text: str, voice: str, outpath: str):
    comm = edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts(text: str) -> str:
    if not text: return None
    ssml = f"<speak>{text}</speak>"
    voice = "en-US-GuyNeural"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_name = tmp.name
    tmp.close()
    try:
        asyncio.run(_edge_save_async(ssml, voice, tmp_name))
        with open(tmp_name,"rb") as f:
            return base64.b64encode(f.read()).decode()
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)

# -------------------------- CHAT --------------------------
st.markdown("<h3>💬 Chat</h3>", unsafe_allow_html=True)
st.markdown('<div id="chat_box" class="chat-container">', unsafe_allow_html=True)
for msg in st.session_state.chat_history:
    bubble_class = "chat-bubble-user" if msg["role"]=="user" else "chat-bubble-ai"
    st.markdown(f'<div class="{bubble_class}">{msg["content"]}</div>', unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# -------------------------- BOTTOM INPUT --------------------------
with st.container():
    col1, col2 = st.columns([8,1])
    with col1:
        user_input = st.text_input("Type your message here...", key="chat_input_box")
    with col2:
        send = st.button("Send", key="chat_send_button")

if send and user_input:
    st.session_state.chat_history.append({"role":"user","content":user_input})
    ai_resp = generate_ai_response(user_input)
    st.session_state.chat_history.append({"role":"ai","content":ai_resp})

    audio_b64 = synthesize_tts(ai_resp)
    if audio_b64:
        st.markdown(f"<audio controls src='data:audio/mp3;base64,{audio_b64}'></audio>", unsafe_allow_html=True)

# -------------------------- EXPORT --------------------------
if st.button("📥 Export Chat to Word") and st.session_state.chat_history:
    doc = Document()
    doc.add_heading("AI Sales Call Assistant Chat",0)
    for msg in st.session_state.chat_history:
        doc.add_paragraph(f"{msg['role'].title()}: {msg['content']}")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    doc.save(tmp.name)
    tmp.close()
    with open(tmp.name,"rb") as f:
        st.download_button("Download .docx", f, file_name="chat_history.docx")
