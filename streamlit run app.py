import os
import io
import asyncio
import streamlit as st
import requests
from PIL import Image
from docx import Document
from pptx import Presentation
from gtts import gTTS
from datetime import datetime

# Edge TTS import with safe fallback
try:
    from edge_tts import Communicate
    EDGE_TTS_AVAILABLE = True
except ModuleNotFoundError:
    EDGE_TTS_AVAILABLE = False

from groq import Groq

# ----------------------------
# App Configuration
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ----------------------------
# Groq API Setup
# ----------------------------
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# ----------------------------
# Helper Functions
# ----------------------------
def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join([p.text for p in doc.paragraphs])

def extract_text_from_pptx(file):
    prs = Presentation(file)
    text_runs = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text_runs.append(shape.text)
    return "\n".join(text_runs)

def generate_tts(text, lang="en"):
    """gTTS fallback TTS"""
    try:
        tts = gTTS(text=text, lang=lang)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception as e:
        st.warning(f"⚠️ TTS error: {e}")
        return None

async def generate_edge_tts(text, voice="ar-EG-HanaNeural", filename="arabic.mp3"):
    """Use edge-tts for Arabic humanized voice"""
    communicate = Communicate(text, voice)
    await communicate.save(filename)
    return filename

def ask_ai(prompt):
    """Call Groq AI with fallback"""
    model = "llama-3.1-70b-versatile"
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role":"system","content":"You are a helpful AI medical sales assistant."},
                          {"role":"user","content":prompt}],
                temperature=0.8,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception:
            model = "llama-3.1-8b-instant" if attempt == 0 else model
    raise RuntimeError("Unable to get AI response")

# ----------------------------
# Session State
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = None
if "last_audio" not in st.session_state:
    st.session_state.last_audio = None

# ----------------------------
# Language Selection
# ----------------------------
language = st.radio("Select Language / اختر اللغة", ["English", "العربية"], horizontal=True)

# ----------------------------
# GSK Logo
# ----------------------------
logo_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
col1, col2 = st.columns([1,5])
with col1:
    st.image(logo_url, width=120)
with col2:
    st.title("🧠 AI Sales Call Assistant")

# ----------------------------
# Sidebar Filters (multi-select)
# ----------------------------
st.sidebar.header("Filters & Options")
gsk_brands = ["Shingrix", "Trelegy", "Zejula"]
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = ["HCP does not consider HZ as risk","No time","Cost","Not convinced","Accessibility issues"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]

brand = st.sidebar.selectbox("Brand", gsk_brands)
segment = st.sidebar.selectbox("RACE Segment", race_segments)
barrier = st.sidebar.multiselect("Doctor Barrier", doctor_barriers)
objective = st.sidebar.selectbox("Objective", objectives)
specialty = st.sidebar.selectbox("Doctor Specialty", specialties)
persona = st.sidebar.selectbox("HCP Persona", personas)

# ----------------------------
# Upload Documents
# ----------------------------
st.subheader("📤 Upload Supporting Documents")
uploaded_file = st.file_uploader("Upload PDF, DOCX, PPTX", type=["pdf","docx","pptx"])
if uploaded_file:
    ext = uploaded_file.name.split(".")[-1].lower()
    text = ""
    if ext == "docx":
        text = extract_text_from_docx(uploaded_file)
    elif ext == "pptx":
        text = extract_text_from_pptx(uploaded_file)
    st.session_state.uploaded_docs = text[:8000]
    st.write(text[:2000]+"..." if len(text)>2000 else text)

# ----------------------------
# Chat Placeholder
# ----------------------------
chat_placeholder = st.empty()

def render_chat():
    html = "<div style='max-height:500px; overflow-y:auto;'>"
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n","<br>")
        time = msg.get("time","")
        if msg["role"]=="user":
            html += f"""
            <div style='display:flex; justify-content:flex-end; align-items:flex-end; margin-bottom:5px;'>
                <div style='background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; max-width:70%;'>
                    {content}<br><span style='font-size:10px;color:gray;'>{time} ✅✅</span>
                </div>
                <div style='font-size:35px; margin-left:5px;'>🚹</div>
            </div>
            """
        else:
            html += f"""
            <div style='display:flex; justify-content:flex-start; align-items:flex-start; margin-bottom:5px;'>
                <div style='font-size:35px; margin-right:5px;'>🤖</div>
                <div style='background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; max-width:70%;'>
                    {content}<br><span style='font-size:10px;color:gray;'>{time}</span>
                </div>
            </div>
            """
    html += "</div>"
    chat_placeholder.markdown(html, unsafe_allow_html=True)

render_chat()

# ----------------------------
# Message Input at Bottom
# ----------------------------
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("", placeholder="Type your message…")
    submitted = st.form_submit_button("📤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})
    # Build prompt
    prompt = f"""
Language: {language}
User Input: {user_input}
Brand: {brand}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Uploaded Docs: {st.session_state.uploaded_docs if st.session_state.uploaded_docs else 'None'}
Respond concisely in a friendly, professional tone with emojis.
"""
    ai_response = ask_ai(prompt)
    st.session_state.chat_history.append({"role":"ai","content":ai_response,"time":datetime.now().strftime("%H:%M")})
    
    # Generate voice
    if language=="العربية" and EDGE_TTS_AVAILABLE:
        asyncio.run(generate_edge_tts(ai_response))
        st.session_state.last_audio = "arabic.mp3"
    else:
        audio_fp = generate_tts(ai_response, lang="ar" if language=="العربية" else "en")
        st.session_state.last_audio = audio_fp

    render_chat()

# ----------------------------
# Play Audio
# ----------------------------
if st.session_state.last_audio:
    st.audio(st.session_state.last_audio, format="audio/mp3")

# ----------------------------
# Download AI Response as Word
# ----------------------------
if st.session_state.chat_history:
    latest_ai = [m["content"] for m in st.session_state.chat_history if m["role"]=="ai"]
    if latest_ai:
        from docx import Document
        doc = Document()
        doc.add_heading("AI Sales Call Response",0)
        doc.add_paragraph(latest_ai[-1])
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        st.download_button("📥 Download as Word (.docx)", buffer, file_name="AI_Response.docx")
