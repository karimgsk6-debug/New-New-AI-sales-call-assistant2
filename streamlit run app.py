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
    text_clean = text.replace(".", "").replace(",", "").replace("*", "").replace("...", "")
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
            messages=[
                {"role": "system", "content": "You are a helpful AI medical sales assistant. Structure responses according to the pharma sales call flow. Use APACT only when handling objections and highlight each step. Reference uploaded docs if available."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
    except:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a helpful AI medical sales assistant. Structure responses according to the pharma sales call flow. Use APACT only when handling objections and highlight each step. Reference uploaded docs if available."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
    return response.choices[0].message.content

# ----------------------------
# Session State
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = ""
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

# ----------------------------
# Theme Toggle
# ----------------------------
st.sidebar.header("⚙️ Settings")
dark_mode_toggle = st.sidebar.checkbox("🌙 Dark Mode", value=False)
st.session_state.dark_mode = dark_mode_toggle

bg_color = "#1b1b1b" if dark_mode_toggle else "#ffffff"
text_color = "#ffffff" if dark_mode_toggle else "#000000"
user_bubble_color = "#004aad" if dark_mode_toggle else "#dcf8c6"
ai_bubble_color = "#ff8c00" if dark_mode_toggle else "#f0f2f6"
input_bg_color = "#333333" if dark_mode_toggle else "#ffffff"
input_text_color = "#ffffff" if dark_mode_toggle else "#000000"
placeholder_color = "#bbbbbb" if dark_mode_toggle else "#999999"

# ----------------------------
# Language Selection
# ----------------------------
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])
voice_lang = "ar-SA-HamedNeural" if language=="العربية" else "en-US-JennyNeural"

# ----------------------------
# Home Page Background (ROBUST + FROSTED EFFECT)
# ----------------------------
background_url = "https://www.google.com/url?sa=i&url=https%3A%2F%2Fwww.shutterstock.com%2Fsearch%2Fgirl-using-ipad&psig=AOvVaw3Ewkory8cwnlIZZFGuAdqr&ust=1758808629129000&source=images&cd=vfe&opi=89978449&ved=0CBYQjRxqFwoTCMD0j_LG8Y8DFQAAAAAdAAAAABAV"

st.markdown(f"""
<style>
/* Main app background */
[data-testid="stAppViewContainer"] {{
    background-image: url("{background_url}");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}}

/* Make main content container transparent so background shows */
[data-testid="stAppViewContainer"] .css-18e3th9 {{
    background-color: rgba(0,0,0,0.0);
}}

/* Chat boxes with frosted glass effect */
.user-bubble, .ai-bubble {{
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
}}

/* Prompt container frosted effect */
.prompt-container {{
    backdrop-filter: blur(5px);
    -webkit-backdrop-filter: blur(5px);
}}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Header + Disclaimer
# ----------------------------
st.markdown(f"""
<div style='text-align:center; padding:15px; background:linear-gradient(90deg,#ff8c00,#ffb347); 
            color:white; border-radius:12px; margin-bottom:10px;'>
    <h2 style='margin:0;'>💡 AI Sales Call Assistant</h2>
    <p style='margin:0;'>Powered by AI to equip sales reps for smarter HCP conversations</p>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div style='padding:10px; background:#f8f9fa; border:1px solid #ddd; border-radius:10px; margin-bottom:20px; font-size:13px; color:{text_color};'>
    ⚠️ <b>Disclaimer:</b> This AI tool is to equip sales reps and is not a substitute for official product info or medical advice.
</div>
""", unsafe_allow_html=True)

# ----------------------------
# GSK Logo
# ----------------------------
logo_local_path = "images/gsk_logo.png"
logo_fallback_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
col1, col2 = st.columns([1,5])
with col1:
    try:
        logo_img = Image.open(logo_local_path)
        st.image(logo_img, width=120)
    except:
        st.image(logo_fallback_url, width=120)
with col2:
    st.title("🧠 AI Sales Call Assistant")

# ----------------------------
# Sidebar Filters
# ----------------------------
st.sidebar.header("Filters & Options")
gsk_brands = {
    "Shingrix": "https://example.com/shingrix-leaflet",
    "Trelegy": "https://example.com/trelegy-leaflet",
    "Zejula": "https://example.com/zejula-leaflet",
}
gsk_brands_images = {
    "Trelegy": "https://www.example.com/trelegy.png",
    "Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Zejula": "https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png",
}
brand = st.sidebar.selectbox("💊 Select Brand", options=list(gsk_brands.keys()))
race_segments = [
    "R – Reach: Did not start to prescribe yet",
    "A – Acquisition: Prescribe to patient who initiate discussion",
    "C – Conversion: Proactively initiate discussion with specific patient profile",
    "E – Engagement: Proactively prescribe to different patient profiles"
]
segment = st.sidebar.selectbox("👥 RACE Segment", race_segments)
doctor_barriers = [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ Vx effective",
    "Accessibility issues"
]
barrier = st.sidebar.multiselect("🚧 Doctor Barrier", options=doctor_barriers, default=[])
objective = st.sidebar.selectbox("🎯 Objective", options=["Awareness", "Adoption", "Retention"])
specialty = st.sidebar.selectbox("🩺 Doctor Specialty", options=["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist"])
persona = st.sidebar.selectbox("🧑‍⚕️ HCP Persona", options=["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"])
tone = st.sidebar.selectbox("🎤 AI Tone", options=["Formal","Casual","Friendly","Persuasive"])
thinking = st.sidebar.selectbox("💡 HCP Thinking Style", options=["Analytical","Skeptic","Emotional","Pragmatic"])

# ----------------------------
# Brand Image
# ----------------------------
image_path = gsk_brands_images.get(brand)
try:
    if image_path.startswith("http"):
        response = requests.get(image_path)
        img = Image.open(io.BytesIO(response.content))
    else:
        img = Image.open(image_path)
    st.image(img, width=200)
except:
    st.warning(f"⚠️ Could not load image for {brand}. Using placeholder.")
    st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)

# ----------------------------
# Upload Documents
# ----------------------------
st.subheader("📤 Upload Supporting Documents")
uploaded_file = st.file_uploader("Upload PDF, DOCX, PPTX, or Audio", type=["pdf", "docx", "pptx", "mp3", "wav", "m4a"])
if uploaded_file:
    ext = uploaded_file.name.split(".")[-1].lower()
    if ext=="pdf":
        st.session_state.uploaded_docs = extract_text_from_pdf(uploaded_file)
    elif ext=="docx":
        st.session_state.uploaded_docs = extract_text_from_docx(uploaded_file)
    elif ext=="pptx":
        st.session_state.uploaded_docs = extract_text_from_pptx(uploaded_file)
    else:
        st.session_state.uploaded_docs = f"Audio uploaded: {uploaded_file.name} (transcription not implemented)"
    st.write(st.session_state.uploaded_docs[:2000]+"..." if len(st.session_state.uploaded_docs)>2000 else st.session_state.uploaded_docs)

# ----------------------------
# Sales Call Flow
# ----------------------------
call_flow = [
    "Prepare the Call",
    "Engage",
    "Create Opportunities",
    "Influence",
    "Impact GSO (Good Sell Outcome)",
    "Closing with Commitment",
    "Post-Call Analysis"
]
call_stage = st.selectbox("📞 Select Call Stage", options=call_flow)

# ----------------------------
# Chat CSS
# ----------------------------
st.markdown(f"""
<style>
body {{ background-color: {bg_color}; color:{text_color}; }}
.chat-container {{ max-height:65vh; overflow-y:auto; padding-bottom:70px; }}
.user-bubble {{ text-align:right; background:{user_bubble_color}; padding:10px; border-radius:15px 15px 0px 15px; margin:5px; display:inline-block; max-width:80%; box-shadow:0 1px 3px rgba(0,0,0,0.1); color:{text_color};}}
.ai-bubble {{ text-align:left; background:{ai_bubble_color}; padding:10px; border-radius:15px 15px 15px 0px; margin:5px; display:inline-block; max-width:80%; box-shadow:0 1px 3px rgba(0,0,0,0.1); color:{text_color};}}
.apact-step {{ background:#ffd700; font-weight:bold; padding:2px 4px; border-radius:4px; }}
.prompt-container {{ position:fixed; bottom:10px; width:95%; background:{input_bg_color}; padding:5px 10px; z-index:999; box-shadow:0 0 5px rgba(0,0,0,0.1); border-radius:10px;}}
.prompt-container input {{ color:{input_text_color}; background:{input_bg_color}; }}
.prompt-container ::placeholder {{ color:{placeholder_color}; }}
</style>
""", unsafe_allow_html=True)

chat_placeholder = st.empty()

# ----------------------------
# Display Chat Function
# ----------------------------
def display_chat():
    chat_html = "<div class='chat-container'>"
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n","<br>")
        # Highlight APACT steps
        for step in ["Acknowledge","Probing","Action","Confirm","Transition"]:
            content = content.replace(step,f"<span class='apact-step'>{step}</span>")
        time = msg.get("time","")
        if msg["role"]=="user":
            chat_html += f"<div class='user-bubble'>{content}<br><span style='font-size:10px;color:gray;'>{time} &#10148;&#10148;</span></div>"
        else:
            chat_html += f"<div class='ai-bubble'>{content}<br><span style='font-size:10px;color:gray;'>{time}</span></div>"
            if "audio_bytes" in msg:
                audio_base64 = base64.b64encode(msg["audio_bytes"]).decode()
                chat_html += f"<audio controls style='margin:5px 0;'><source src='data:audio/mp3;base64,{audio_base64}' type='audio/mp3'></audio>"
    chat_html += "</div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

# ----------------------------
# Chat Input Form (FIXED)
# ----------------------------
st.markdown("<div class='prompt-container'>", unsafe_allow_html=True)
with st.form("chat_input_form", clear_on_submit=True):
    col1, col2 = st.columns([7,1])
    with col1:
        user_input = st.text_input("", placeholder="Type your message...")
    with col2:
        submitted = st.form_submit_button("📩")
st.markdown("</div>", unsafe_allow_html=True)

# Clear chat button
if st.button("🗑 Clear Chat"):
    st.session_state.chat_history = []

# ----------------------------
# Handle AI Response
# ----------------------------
if submitted and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})
    prompt_text = f"""
Sales Call Flow Stage: {call_stage}
Language: {language}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Brand: {brand}
Doctor Specialty: {specialty}
HCP Persona: {persona}
HCP Thinking Style: {thinking}
AI Tone: {tone}
Uploaded Docs Context: {st.session_state.uploaded_docs[:2000]}
User Input: {user_input}

➡️ Structure response following this flow:
1. Prepare the Call
2. Engage
3. Create Opportunities
4. Influence
5. Impact GSO (Good Sell Outcome)
6. Closing with Commitment
7. Post-Call Analysis

Use APACT only when handling objections and highlight each step.
"""
    ai_text = ask_ai(prompt_text)
    audio_bytes = asyncio.run(generate_tts_edge(ai_text, lang=voice_lang))
    st.session_state.chat_history.append({"role":"ai","content":ai_text,"time":datetime.now().strftime("%H:%M"),"audio_bytes":audio_bytes})

display_chat()

# ----------------------------
# Word Download
# ----------------------------
if st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response",0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io.BytesIO()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")

# ----------------------------
# Brand Leaflet
# ----------------------------
st.markdown(f"[📑 Brand Leaflet]({gsk_brands.get(brand)})")
