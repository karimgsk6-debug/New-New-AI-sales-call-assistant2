import os
import io
import streamlit as st
import requests
from PIL import Image
from docx import Document
import pdfplumber
from pptx import Presentation
from datetime import datetime
from groq import Groq
import asyncio
import edge_tts
import base64

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
# GSK Digital Theme CSS
# ----------------------------
st.markdown("""
    <style>
    body {
        background: linear-gradient(180deg, #ffffff, #fdf2ec);
        font-family: "Helvetica Neue", Arial, sans-serif;
    }
    .block-container {padding-top: 1rem; padding-bottom: 1rem;}
    /* Header */
    .header-bar {background: #FF6A13; color: white; text-align: center; padding: 15px;
        border-radius: 12px; margin-bottom: 15px;}
    .header-bar h2 {margin: 0; font-size: 26px;}
    .header-bar p {margin: 0; font-size: 14px;}
    /* Disclaimer */
    .disclaimer {background: #F5F5F5; border-left: 4px solid #FF6A13; padding: 10px 15px;
        border-radius: 8px; font-size: 13px; color: #333; margin-bottom: 20px;}
    /* Chat bubbles */
    .chat-container {max-height: 500px; overflow-y: auto; padding: 10px;}
    .user-bubble {background: #002D72; color: white; padding: 10px 14px; border-radius: 18px 18px 0 18px;
        margin: 8px 0; text-align: right; font-size: 15px;}
    .ai-bubble {background: #ffffff; border: 1px solid #ddd; color: #333; padding: 10px 14px;
        border-radius: 18px 18px 18px 0; margin: 8px 0; text-align: left; font-size: 15px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);}
    /* Input box */
    .stTextInput input {border: 1px solid #FF6A13 !important; border-radius: 12px !important; font-size: 15px !important;}
    .stButton button {background-color: #FF6A13 !important; color: white !important; border-radius: 12px !important; border: none !important; font-weight: bold;}
    .stButton button:hover {background-color: #e85a0f !important;}
    </style>
""", unsafe_allow_html=True)

# ----------------------------
# Header + Disclaimer
# ----------------------------
st.markdown("""
    <div class='header-bar'>
        <h2>💡 AI Sales Call Assistant</h2>
        <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
    </div>
""", unsafe_allow_html=True)

st.markdown("""
    <div class='disclaimer'>
        ⚠️ <b>Disclaimer:</b> The main objective of this AI tool is to equip the sales representative 
        with the right tools to handle different HCP concerns. It is not a substitute for official product 
        information or medical advice.
    </div>
""", unsafe_allow_html=True)

# ----------------------------
# Helper Functions
# ----------------------------
def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join([p.text for p in doc.paragraphs])

def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

def extract_text_from_pptx(file):
    prs = Presentation(file)
    text_runs = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text_runs.append(shape.text)
    return "\n".join(text_runs)

async def generate_tts_edge(text, lang="en-US-JennyNeural"):
    text_clean = text.replace(".", "").replace(",", "").replace("*", "")
    filename = f"ai_tts_{datetime.now().strftime('%H%M%S%f')}.mp3"
    communicate = edge_tts.Communicate(text_clean, voice=lang)
    await communicate.save(filename)
    with open(filename, "rb") as f:
        audio_bytes = f.read()
    return audio_bytes

def ask_ai(prompt):
    try:
        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "system", "content": "You are a helpful AI medical sales assistant. Provide actionable suggestions using APACT technique and reference uploaded documents."},
                      {"role": "user", "content": prompt}],
            temperature=0.7, max_tokens=1000
        )
    except:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": "You are a helpful AI medical sales assistant. Provide actionable suggestions using APACT technique and reference uploaded documents."},
                      {"role": "user", "content": prompt}],
            temperature=0.7, max_tokens=1000
        )
    return response.choices[0].message.content

# ----------------------------
# Session State
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = ""

# ----------------------------
# Sidebar Filters
# ----------------------------
st.sidebar.header("🔍 Filters & Options")

gsk_brands = {"Shingrix": "https://example.com/shingrix-leaflet","Trelegy": "https://example.com/trelegy-leaflet","Zejula": "https://example.com/zejula-leaflet"}
brand = st.sidebar.selectbox("💊 Select Brand", options=list(gsk_brands.keys()))

race_segments = ["R – Reach","A – Acquisition","C – Conversion","E – Engagement"]
segment = st.sidebar.selectbox("👥 RACE Segment", race_segments)

doctor_barriers = ["HCP does not consider HZ risk","No time","Cost","Not convinced efficacy","Accessibility"]
barrier = st.sidebar.multiselect("🚧 Doctor Barriers", options=doctor_barriers, default=[])

objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
ai_tones = ["Formal","Casual","Friendly","Persuasive"]
hcp_thinking = ["Analytical","Skeptic","Emotional","Pragmatic"]

objective = st.sidebar.selectbox("🎯 Objective", options=objectives)
specialty = st.sidebar.selectbox("🩺 Doctor Specialty", options=specialties)
persona = st.sidebar.selectbox("🧑 Persona", options=personas)
tone = st.sidebar.selectbox("🎙️ AI Tone", options=ai_tones)
thinking = st.sidebar.selectbox("💭 HCP Thinking", options=hcp_thinking)
language = st.sidebar.radio("🌐 Language", options=["English","العربية"])
voice_lang = "ar-SA-HamedNeural" if language=="العربية" else "en-US-JennyNeural"

# ----------------------------
# Upload Docs
# ----------------------------
st.subheader("📤 Upload Supporting Documents")
uploaded_file = st.file_uploader("Upload PDF, DOCX, PPTX, or Audio", type=["pdf","docx","pptx"])
if uploaded_file:
    ext = uploaded_file.name.split(".")[-1].lower()
    if ext=="pdf": st.session_state.uploaded_docs = extract_text_from_pdf(uploaded_file)
    elif ext=="docx": st.session_state.uploaded_docs = extract_text_from_docx(uploaded_file)
    elif ext=="pptx": st.session_state.uploaded_docs = extract_text_from_pptx(uploaded_file)
    st.write(st.session_state.uploaded_docs[:2000]+"..." if len(st.session_state.uploaded_docs)>2000 else st.session_state.uploaded_docs)

# ----------------------------
# Sales Call Flow
# ----------------------------
sales_flow_steps = ["Prepare the call","Engage","Create opportunities","Influence","Impact GSO (Good Sell Outcome)","Close with commitment","Post-call analysis & assessment"]

# ----------------------------
# Display Chat Function
# ----------------------------
chat_placeholder = st.empty()

def display_chat():
    chat_html = "<div class='chat-container'>"
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n","<br>")
        time = msg.get("time","")
        if msg["role"]=="user":
            chat_html += f"<div class='user-bubble'>{content}<br><span style='font-size:10px;color:lightgray;'>{time}</span></div>"
        else:
            chat_html += f"<div class='ai-bubble'>{content}<br><span style='font-size:10px;color:gray;'>{time}</span></div>"
            if "audio_bytes" in msg:
                audio_base64 = base64.b64encode(msg["audio_bytes"]).decode()
                chat_html += f"<audio controls style='margin:5px 0;'><source src='data:audio/mp3;base64,{audio_base64}' type='audio/mp3'></audio>"
    chat_html += "</div><script>var chatBox=document.querySelector('.chat-container'); chatBox.scrollTop=chatBox.scrollHeight;</script>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

# ----------------------------
# Input
# ----------------------------
with st.form("chat_form", clear_on_submit=True):
    col1, col2 = st.columns([8,1])
    with col1:
        user_input = st.text_input("", placeholder="Type your message...")
    with col2:
        submitted = st.form_submit_button("📩")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})

    step = sales_flow_steps[len([m for m in st.session_state.chat_history if m['role']=="ai"]) % len(sales_flow_steps)]
    prompt = f"Stage: {step}\nLanguage: {language}\nSegment: {segment}\nBarrier: {', '.join(barrier) if barrier else 'None'}\nObjective: {objective}\nBrand: {brand}\nSpecialty: {specialty}\nPersona: {persona}\nThinking: {thinking}\nTone: {tone}\nDocs: {st.session_state.uploaded_docs[:2000]}\nUser: {user_input}\nProvide actionable suggestions using APACT technique."
    ai_text = ask_ai(prompt)
    audio_bytes = asyncio.run(generate_tts_edge(ai_text, lang=voice_lang))

    st.session_state.chat_history.append({"role":"ai","content":f"📌 *{step}*: {ai_text}","time":datetime.now().strftime("%H:%M"),"audio_bytes":audio_bytes})

display_chat()

# ----------------------------
# Word Download
# ----------------------------
if st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response",0)
        for resp in latest_ai: doc.add_paragraph(resp)
        word_buffer = io.BytesIO(); doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")
