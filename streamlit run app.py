# app.py
import os
import io
import base64
import requests
from datetime import datetime
import asyncio

import streamlit as st
from PIL import Image
from docx import Document
import pdfplumber
from pptx import Presentation

from groq import Groq
import edge_tts

# ----------------------------
# App configuration
# ----------------------------
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------
# Constants
# ----------------------------
BACKGROUND_URL = "https://makemoneywithoutajob.com/wp-content/uploads/make-money-with-your-ipad-5.jpg"
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# ----------------------------
# Helper functions
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

# ----------------------------
# TTS functions
# ----------------------------
async def generate_tts_edge_async(text, voice="en-US-JennyNeural", filename=None):
    if filename is None:
        filename = f"ai_tts_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}.mp3"
    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(filename)
    return filename

def generate_tts_edge(text, voice="en-US-JennyNeural"):
    return asyncio.run(generate_tts_edge_async(text, voice=voice))

# ----------------------------
# Groq AI
# ----------------------------
def safe_groq_client():
    if GROQ_API_KEY:
        try:
            return Groq(api_key=GROQ_API_KEY)
        except Exception as e:
            st.warning(f"Could not initialize Groq client: {e}")
            return None
    return None

def ask_ai_via_groq(prompt, client=None, fallback_message="⚠️ Groq API not configured or request failed."):
    if client is None:
        client = safe_groq_client()
    if client is None:
        return fallback_message
    try:
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a helpful AI medical sales assistant. Structure responses according to the pharma sales call flow. Use APACT only when handling objections and highlight each step. Reference uploaded docs if available."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            max_tokens=1000,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"{fallback_message} Error: {e}"

# ----------------------------
# HEADER: Page title + disclaimer
# ----------------------------
st.markdown(f"""
<div style='text-align:center; padding:15px; background:linear-gradient(90deg,#ff8c00,#ffb347); 
            color:white; border-radius:12px; margin-bottom:10px;'>
    <h2 style='margin:0;'>💡 AI Sales Call Assistant</h2>
    <p style='margin:0;'>Powered by AI to equip sales reps for smarter HCP conversations</p>
</div>

<div style='padding:10px; border-radius:10px; margin-bottom:20px; font-size:13px; color:white;'>
    ⚠️ <b>Disclaimer:</b> This AI tool is to equip sales reps and is not a substitute for official product info or medical advice.
</div>
""", unsafe_allow_html=True)

# ----------------------------
# Sidebar: filters
# ----------------------------
st.sidebar.header("⚙️ Settings & Filters")

theme_choice = st.sidebar.radio("Theme", options=["Dark Mode", "Light Mode"], index=0)

# Brands
st.sidebar.subheader("Brand & Segmentation")
gsk_brands = {
    "Shingrix": "https://example.com/shingrix-leaflet",
    "Trelegy": "https://example.com/trelegy-leaflet",
    "Zejula": "https://example.com/zejula-leaflet",
}
brand = st.sidebar.selectbox("💊 Select Brand", options=list(gsk_brands.keys()))

# RACE HCP Segments
st.sidebar.subheader("HCP Segmentation (RACE)")
hcp_segments = [
    "R – Reach: Did not start to prescribe yet",
    "A – Acquisition: Prescribe to patient who initiate discussion",
    "C – Conversion: Proactively initiate discussion with specific patient profile",
    "E – Engagement: Proactively prescribe to different patient profiles"
]
segment = st.sidebar.selectbox("👥 Segment", hcp_segments)

# Barriers
st.sidebar.subheader("Doctor Barriers")
doctor_barriers = [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ Vx effective",
    "Accessibility issues",
    "Regulatory concerns",
    "Patient hesitancy",
]
barrier = st.sidebar.multiselect("🚧 Select Barriers", options=doctor_barriers, default=[])

# Attributes
st.sidebar.subheader("Doctor / HCP Attributes")
specialty = st.sidebar.selectbox("🩺 Specialty", options=["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist","Immunologist"])
persona = st.sidebar.selectbox("🧑‍⚕️ Persona", options=["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"])

# Tone & Mindset
response_tone = st.sidebar.selectbox("🎤 Response Tone", options=["Formal","Empathetic","Confident","Concise","Persuasive"])
hcp_mindset = st.sidebar.selectbox("💡 HCP Mindset", options=["Analytical","Practical","Risk-Averse","Innovative","Skeptical","Patient-Centered"])

# Call stage
st.sidebar.markdown("---")
call_stage = st.sidebar.selectbox("📞 Call Stage", options=[
    "Prepare the Call","Engage","Create Opportunities","Influence","Impact GSO (Good Sell Outcome)",
    "Closing with Commitment","Post-Call Analysis"
])

# ----------------------------
# Colors & Bubbles
# ----------------------------
font_color = "white"
bubble_user_bg = "rgba(255,255,255,0.14)"
bubble_ai_bg = "rgba(0,0,0,0.35)"

# ----------------------------
# Background & styling
# ----------------------------
st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{
    background-image: url("{BACKGROUND_URL}");
    background-repeat: no-repeat;
    background-position: center top;
    background-size: cover;
    height: 100vh;
    width: 100%;
    filter: blur(3px);
    position: fixed;
    z-index: -1;
}}

/* Chat overlay */
.chat-container {{
    color: {font_color} !important;
    padding:10px;
    background: transparent !important;
}}
.user-bubble {{
    text-align:right;
    background:{bubble_user_bg};
    color:{font_color};
    padding:10px;
    border-radius:15px 15px 0 15px;
    margin:6px;
    display:inline-block;
    max-width:80%;
}}
.ai-bubble {{
    text-align:left;
    background:{bubble_ai_bg};
    color:{font_color};
    padding:10px;
    border-radius:15px 15px 15px 0;
    margin:6px;
    display:inline-block;
    max-width:80%;
}}
.apact-step {{
    background:#ffd700; color:#000; font-weight:bold; padding:2px 6px; border-radius:4px;
}}

/* Floating input box */
.chat-input-container {{
    position: fixed;
    bottom: 10px;
    width: 90%;
    left: 5%;
    display:flex;
}}
.chat-input-container input {{
    flex:1;
    padding:10px;
    border-radius:20px;
    border:none;
    outline:none;
    background: rgba(0,0,0,0.3);
    color:white;
}}
.chat-input-container button {{
    margin-left:5px;
    border:none;
    border-radius:50%;
    background:#ff8c00;
    color:white;
    font-weight:bold;
    width:45px;
    height:45px;
    cursor:pointer;
}}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Chat history
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = ""

chat_placeholder = st.empty()
def display_chat():
    chat_html = "<div class='chat-container'>"
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n","<br>")
        for step in ["Acknowledge","Probing","Action","Confirm","Transition"]:
            content = content.replace(step, f"<span class='apact-step'>{step}</span>")
        if msg["role"] == "user":
            chat_html += f"<div class='user-bubble'>{content}</div>"
        else:
            chat_html += f"<div class='ai-bubble'>{content}</div>"
    chat_html += "</div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)
display_chat()

# ----------------------------
# Chat input
# ----------------------------
st.markdown("""
<div class="chat-input-container">
<form id="chat-form">
<input id="user-input" type="text" placeholder="Type your message...">
<button type="submit">📩</button>
</form>
</div>
""", unsafe_allow_html=True)

user_input = st.text_input("", key="chat_input")
if st.button("📩 Send") and user_input:
    st.session_state.chat_history.append({"role":"user","content":user_input})
    display_chat()

    # AI response
    prompt = f"""
Stage: {call_stage}
Segment: {segment}
Barriers: {', '.join(barrier) if barrier else 'None'}
Brand: {brand}
Specialty: {specialty}
Persona: {persona}
HCP Mindset: {hcp_mindset}
Tone: {response_tone}
Docs: {st.session_state.uploaded_docs[:1000]}
Input: {user_input}
"""
    groq_client = safe_groq_client()
    ai_text = ask_ai_via_groq(prompt, groq_client)
    
    # Append AI response
    st.session_state.chat_history.append({"role":"ai","content":ai_text})
    display_chat()
    
    # Generate TTS
    audio_file = generate_tts_edge(ai_text)
    audio_bytes = open(audio_file, "rb").read()
    st.audio(audio_bytes, format="audio/mp3")
    
    # Download as Word
    doc = Document()
    doc.add_heading("AI Sales Call Response", 0)
    doc.add_paragraph(ai_text)
    word_buffer = io.BytesIO()
    doc.save(word_buffer)
    st.download_button("📥 Download AI Response as Word", word_buffer.getvalue(), file_name="AI_Response.docx")
