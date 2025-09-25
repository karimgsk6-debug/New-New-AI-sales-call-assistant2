import os
import io
import time
import streamlit as st
import requests
from PIL import Image
from docx import Document
import fitz  # PyMuPDF
import pdfplumber
from pptx import Presentation
from gtts import gTTS
from groq import Groq
from datetime import datetime

# ----------------------------
# App Configuration
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ----------------------------
# Groq API Setup
# ----------------------------
GROQ_API_KEY = "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"  # Replace with your key
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

def extract_images_from_pdf(file):
    images = []
    pdf = fitz.open(file)
    for page_num in range(len(pdf)):
        for img_index, img in enumerate(pdf[page_num].get_images()):
            xref = img[0]
            base_image = pdf.extract_image(xref)
            image_bytes = base_image["image"]
            images.append(Image.open(io.BytesIO(image_bytes)))
    return images

def extract_text_from_pptx(file):
    prs = Presentation(file)
    text_runs = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text_runs.append(shape.text)
    return "\n".join(text_runs)

def generate_tts(text, filename="output.mp3"):
    try:
        tts = gTTS(text=text, lang="en")
        tts.save(filename)
        return filename
    except Exception:
        return None

def ask_ai_streaming(prompt):
    """Stream AI response word by word."""
    model = "llama-3.1-70b-versatile"
    try:
        # Streaming simulation: Groq does not natively support streaming
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "You are a helpful AI medical sales assistant."},
                      {"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        full_text = response.choices[0].message.content
        words = full_text.split()
        streaming_text = ""
        for word in words:
            streaming_text += word + " "
            yield streaming_text
            time.sleep(0.03)  # Adjust typing speed here
    except Exception:
        # Fallback
        model = "llama-3.1-8b-instant"
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "You are a helpful AI medical sales assistant."},
                      {"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1000
        )
        yield response.choices[0].message.content

# ----------------------------
# Session State
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = ""
if "typing" not in st.session_state:
    st.session_state.typing = False

# ----------------------------
# Language
# ----------------------------
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])

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
# Brand & Product Data
# ----------------------------
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

# ----------------------------
# Filters & Options (Multi-select & sidebar)
# ----------------------------
race_segments = [
    "R – Reach",
    "A – Acquisition",
    "C – Conversion",
    "E – Engagement"
]
doctor_barriers = [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ Vx effective",
    "Accessibility issues"
]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]
personas = [
    "Uncommitted Vaccinator",
    "Reluctant Efficiency",
    "Patient Influenced",
    "Committed Vaccinator"
]

# Sidebar
with st.sidebar:
    st.header("Filters & Options")
    brand = st.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
    segment = st.selectbox("Select RACE Segment / اختر شريحة RACE", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", options=doctor_barriers)
    objective = st.selectbox("Select Objective / اختر الهدف", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", options=specialties)
    persona = st.selectbox("Select HCP Persona / اختر شخصية الطبيب", options=personas)
    response_length = st.selectbox("Response Length / اختر طول الرد", ["Short", "Medium", "Long"])
    response_tone = st.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])

# ----------------------------
# Display brand image
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
    file_ext = uploaded_file.name.split(".")[-1].lower()
    extracted_text = ""
    extracted_images = []

    if file_ext == "docx":
        extracted_text = extract_text_from_docx(uploaded_file)
    elif file_ext == "pdf":
        extracted_text = extract_text_from_pdf(uploaded_file)
        extracted_images = extract_images_from_pdf(uploaded_file)
    elif file_ext == "pptx":
        extracted_text = extract_text_from_pptx(uploaded_file)
    elif file_ext in ["mp3", "wav", "m4a"]:
        extracted_text = f"🔊 Audio file uploaded ({uploaded_file.name}) - transcription not implemented yet."

    st.session_state.uploaded_docs = extracted_text[:8000]

    if extracted_text:
        st.subheader("📄 Extracted Text")
        st.write(extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else ""))

    if extracted_images:
        st.subheader("🖼️ Extracted Images")
        for img in extracted_images:
            st.image(img, use_container_width=True)

# ----------------------------
# Chat Interface
# ----------------------------
chat_placeholder = st.empty()

def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time_stamp = msg.get("time", "")
        content = msg["content"].replace("\n", "<br>")
        if msg["role"] == "user":
            chat_html += f"""
            <div style="display:flex; justify-content:flex-end; align-items:flex-end; margin-bottom:5px;">
                <div style="background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; max-width:70%;">
                    {content}<br>
                    <span style="font-size:10px; color:gray;">{time_stamp} ✅✅</span>
                </div>
                <div style="font-size:35px; margin-left:5px;">🚹</div>
            </div>
            """
        else:
            chat_html += f"""
            <div style="display:flex; justify-content:flex-start; align-items:flex-start; margin-bottom:5px;">
                <div style="font-size:35px; margin-right:5px;">🤖</div>
                <div style="background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; max-width:70%;">
                    {content}<br>
                    <span style="font-size:10px; color:gray;">{time_stamp}</span>
                </div>
            </div>
            """
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

# ----------------------------
# Message Form at Bottom
# ----------------------------
with st.form("chat_form", clear_on_submit=True):
    col_msg, col_send = st.columns([8,1])
    with col_msg:
        user_input = st.text_input("Type your message…", key="user_input_box", placeholder="Enter your question")
    with col_send:
        submitted = st.form_submit_button("📤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})
    # Build prompt
    references = (
        "1. CDC Shingrix Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html\n"
        "2. CDC Clinical Overview of Shingles: https://www.cdc.gov/shingles/hcp/clinical-overview/index.html\n"
        "3. WHO Vaccine Overview: https://www.who.int/news-room/fact-sheets/detail/shingles"
    )
    prompt = f"""
Language: {language}
User input: {user_input}
Brand: {brand}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Uploaded Docs Context: {st.session_state.uploaded_docs}
References:
{references}
Respond in a lively, engaging style with emojis.
"""
    # Stream AI response
    st.session_state.typing = True
    ai_text = ""
    for chunk in ask_ai_streaming(prompt):
        ai_text = chunk
        if st.session_state.typing:
            if len(st.session_state.chat_history) == 0 or st.session_state.chat_history[-1]["role"] != "ai":
                st.session_state.chat_history.append({"role":"ai","content":ai_text,"time":datetime.now().strftime("%H:%M")})
            else:
                st.session_state.chat_history[-1]["content"] = ai_text
        display_chat()
    st.session_state.typing = False

# ----------------------------
# TTS Playback
# ----------------------------
if st.session_state.chat_history:
    latest_ai = [m["content"] for m in st.session_state.chat_history if m["role"]=="ai"]
    if latest_ai:
        audio_file = generate_tts(latest_ai[-1])
        if audio_file:
            st.audio(audio_file, format="audio/mp3")

# ----------------------------
# Word Download
# ----------------------------
if st.session_state.chat_history:
    latest_ai = [m["content"] for m in st.session_state.chat_history if m["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io.BytesIO()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")

# ----------------------------
# Brand Leaflet
# ----------------------------
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")

# Display chat
display_chat()


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
# Background image external link
BACKGROUND_URL = "https://makemoneywithoutajob.com/wp-content/uploads/make-money-with-your-ipad-5.jpg"

# Insert your Groq API key here
GROQ_API_KEY = "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"

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
                {"role": "system", "content": "You are a helpful AI medical sales assistant. Structure responses according to the pharma sales call flow. Use APACT steps (Acknowledge, Probing, Action, Confirm, Transition to next step) only when handling objections and highlight each step in bold yellow. Reference uploaded docs if available."},
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
<div style='position:relative; z-index:1; text-align:center; padding:15px; background:linear-gradient(90deg,#ff8c00,#ffb347); 
            color:white; border-radius:12px; margin-bottom:10px;'>
    <h2 style='margin:0;'>💡 AI Sales Call Assistant</h2>
    <p style='margin:0;'>Powered by AI to equip sales reps for smarter HCP conversations</p>
</div>

<div style='padding:10px; border-radius:10px; margin-bottom:20px; font-size:13px; color:black;'>
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
        for step in ["Acknowledge","Probing","Action","Confirm","Transition to next step"]:
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
