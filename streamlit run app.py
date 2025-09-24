# app.py
import os
import io
import base64
import requests
from pathlib import Path
from datetime import datetime
import asyncio

import streamlit as st
from PIL import Image
from docx import Document
import pdfplumber
from pptx import Presentation

# optional LLM + TTS libraries
from groq import Groq
import edge_tts

# ----------------------------
# App configuration
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# ----------------------------
# Constants & defaults
# ----------------------------
BACKGROUND_URL = "https://image.shutterstock.com/image-photo/young-arab-girl-using-ipad-260nw-2616487693.jpg"
DEFAULT_BLUR = 4
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

async def generate_tts_edge_async(text, voice="en-US-JennyNeural", filename=None):
    if filename is None:
        filename = f"ai_tts_{datetime.now().strftime('%Y%m%d_%H%M%S%f')}.mp3"
    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(filename)
    return filename

def generate_tts_edge(text, voice="en-US-JennyNeural", filename=None):
    return asyncio.run(generate_tts_edge_async(text, voice=voice, filename=filename))

def safe_groq_client():
    if GROQ_API_KEY:
        try:
            return Groq(api_key=GROQ_API_KEY)
        except Exception as e:
            st.warning(f"Could not initialize Groq client: {e}")
            return None
    return None

def ask_ai_via_groq(prompt, client=None, fallback_message="⚠️ Groq API key missing or request failed."):
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
# Sidebar UI: theme, blur, segmentation & filters
# ----------------------------
st.sidebar.header("⚙️ Settings & Filters")

# Theme toggle visible and selectable
theme_choice = st.sidebar.radio("Theme", options=["Dark (white text)", "Light (black text)"], index=0)

# Background blur slider
blur_intensity = st.sidebar.slider("Background blur (px)", min_value=0, max_value=12, value=DEFAULT_BLUR)

# Brands & segmentation fully expanded
st.sidebar.subheader("Brand & Segmentation")
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

st.sidebar.subheader("RACE Segmentation")
race_segments = [
    "R – Reach: Did not start to prescribe yet",
    "A – Acquisition: Prescribe to patient who initiate discussion",
    "C – Conversion: Proactively initiate discussion with specific patient profile",
    "E – Engagement: Proactively prescribe to different patient profiles",
]
segment = st.sidebar.selectbox("👥 RACE Segment", race_segments)

st.sidebar.subheader("Doctor Barriers (select all that apply)")
doctor_barriers = [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ Vx effective",
    "Accessibility issues",
    "Regulatory concerns",
    "Patient hesitancy",
]
barrier = st.sidebar.multiselect("🚧 Doctor Barrier", options=doctor_barriers, default=[])

st.sidebar.subheader("Doctor / HCP attributes")
specialty = st.sidebar.selectbox("🩺 Doctor Specialty", options=["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist","Immunologist"])
persona = st.sidebar.selectbox("🧑‍⚕️ HCP Persona", options=["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"])
tone = st.sidebar.selectbox("🎤 AI Tone", options=["Formal","Casual","Friendly","Persuasive"])
thinking = st.sidebar.selectbox("💡 HCP Thinking Style", options=["Analytical","Skeptic","Emotional","Pragmatic"])

st.sidebar.markdown("---")
call_stage = st.sidebar.selectbox("📞 Call Stage", options=[
    "Prepare the Call","Engage","Create Opportunities","Influence","Impact GSO (Good Sell Outcome)",
    "Closing with Commitment","Post-Call Analysis"
])
st.sidebar.markdown("---")

# ----------------------------
# Theme colors derived from selection
# ----------------------------
is_light = theme_choice.startswith("Light")
font_color = "black" if is_light else "white"
bubble_user_bg = "rgba(255,255,255,0.14)" if is_light else "rgba(0,0,0,0.35)"
bubble_ai_bg = "rgba(0,0,0,0.06)" if is_light else "rgba(255,98,0,0.12)"
input_bg = "rgba(255,255,255,0.9)" if is_light else "rgba(0,0,0,0.45)"
input_color = "black" if is_light else "white"
overlay_alpha = 0.35 if not is_light else 0.15

# ----------------------------
# Background CSS: blurred layer only, top crop, dark overlay
# ----------------------------
st.markdown(f"""
<style>
/* Main container background (top-centered crop of girl image) */
[data-testid="stAppViewContainer"] {{
    position: relative;
    background-image: url("{BACKGROUND_URL}");
    background-repeat: no-repeat;
    background-position: top center;
    background-size: cover;
}}

/* blurred background pseudo-element (keeps content sharp) */
[data-testid="stAppViewContainer"]::before {{
    content: "";
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-image: url("{BACKGROUND_URL}");
    background-repeat: no-repeat;
    background-position: top center;
    background-size: cover;
    filter: blur({blur_intensity}px) brightness(0.65);
    z-index: -2;
}}

/* overlay for better readability */
[data-testid="stAppViewContainer"]::after {{
    content: "";
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,{overlay_alpha});
    z-index: -1;
}}

/* force adaptive font color */
* {{
    color: {font_color} !important;
}}

/* Inputs styling */
.stTextInput > div > input, .stTextArea > div > textarea {{
    background: {input_bg} !important;
    color: {input_color} !important;
    border-radius: 8px;
    padding: 8px;
    border: 1px solid rgba(0,0,0,0.08) !important;
}}

/* Buttons style */
.stButton>button {{
    background: #FF6200 !important;
    color: white !important;
    border: none !important;
}}

/* Chat and prompt styling (position fixed prompt) */
.chat-container {{ max-height:60vh; overflow-y:auto; padding-bottom:90px; }}
.user-bubble {{ text-align:right; background:{bubble_user_bg}; padding:10px; border-radius:15px 15px 0 15px; margin:6px; display:inline-block; max-width:80%; color:{font_color}; }}
.ai-bubble {{ text-align:left; background:{bubble_ai_bg}; padding:10px; border-radius:15px 15px 15px 0; margin:6px; display:inline-block; max-width:80%; color:{font_color}; }}
.apact-step {{ background:#ffd700; color:#000; font-weight:bold; padding:2px 6px; border-radius:4px; }}

.prompt-container {{
    position: fixed;
    bottom: 14px;
    left: 2.5%;
    width: 95%;
    background: rgba(0,0,0,0.38);
    padding: 10px 12px;
    z-index: 9999;
    border-radius: 12px;
    display:flex;
    gap:8px;
    align-items:center;
}}
.prompt-input {{
    flex:1;
    background: transparent;
    border:none;
    outline:none;
    color: {font_color} !important;
    font-size:16px;
}}
.send-btn {{
    background: #FF6200;
    color:white;
    border:none;
    border-radius:8px;
    padding:8px 12px;
    cursor:pointer;
}}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Header + disclaimer
# ----------------------------
st.markdown(f"""
<div style='text-align:center; padding:10px; margin-bottom:8px;'>
  <h2 style='margin:0; color:#FF9C3C;'>💡 AI Sales Call Assistant</h2>
  <div style='color:{font_color};'>Supports sales reps with APCT objection-handling & call flow guidance</div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div style='padding:10px; background: rgba(0,0,0,0.28); border-radius:10px; margin-bottom:12px; color:{font_color};'>
  <strong>⚠️ Disclaimer:</strong> This AI tool is for sales-support only and is not a substitute for official medical advice or product documentation.
</div>
""", unsafe_allow_html=True)

# ----------------------------
# Top area: logo + title
# ----------------------------
col1, col2 = st.columns([1,5])
with col1:
    logo_local = Path("images/gsk_logo.png")
    try:
        if logo_local.is_file():
            st.image(str(logo_local), width=100)
        else:
            st.image("https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png", width=100)
    except Exception:
        st.image("https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png", width=100)
with col2:
    st.title("🧠 AI Sales Call Assistant")

# ----------------------------
# Brand image preview (optional)
# ----------------------------
try:
    brand_image_url = gsk_brands_images.get(brand)
    if brand_image_url and brand_image_url.startswith("http"):
        resp = requests.get(brand_image_url, timeout=6)
        img = Image.open(io.BytesIO(resp.content))
        st.image(img, width=200)
    else:
        st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)
except Exception:
    st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)

# ----------------------------
# Upload supporting docs
# ----------------------------
st.subheader("📤 Upload Supporting Documents")
uploaded_file = st.file_uploader("Upload PDF, DOCX, PPTX, or Audio (mp3/wav/m4a)", type=["pdf","docx","pptx","mp3","wav","m4a"])
if uploaded_file:
    ext = uploaded_file.name.split(".")[-1].lower()
    if ext == "pdf":
        st.session_state.uploaded_docs = extract_text_from_pdf(uploaded_file)
    elif ext == "docx":
        st.session_state.uploaded_docs = extract_text_from_docx(uploaded_file)
    elif ext == "pptx":
        st.session_state.uploaded_docs = extract_text_from_pptx(uploaded_file)
    else:
        st.session_state.uploaded_docs = f"Audio uploaded: {uploaded_file.name} (transcription not implemented)"
    st.info("Uploaded content preview (truncated):")
    st.write(st.session_state.uploaded_docs[:2000] + ("..." if len(st.session_state.uploaded_docs) > 2000 else ""))

# ----------------------------
# Initialize session state for chat history
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = ""

# ----------------------------
# Chat CSS + display
# ----------------------------
st.markdown(f"""
<style>
/* ensure chat area doesn't overlap with fixed prompt on small screens */
@media (max-width: 600px) {{
  .chat-container {{ max-height:50vh; }}
}}
</style>
""", unsafe_allow_html=True)

chat_placeholder = st.empty()

def display_chat():
    chat_html = "<div class='chat-container'>"
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n","<br>")
        # APACT highlight mapping (common variants)
        for step in ["Acknowledge","Probing","Action","Confirm","Transition","APACT","Probing:","Acknowledge:"]:
            content = content.replace(step, f"<span class='apact-step'>{step}</span>")
        time = msg.get("time","")
        if msg["role"] == "user":
            chat_html += f"<div class='user-bubble'>{content}<br><span style='font-size:10px;color:rgba(255,255,255,0.7);'>{time} &#10148;&#10148;</span></div>"
        else:
            chat_html += f"<div class='ai-bubble'>{content}<br><span style='font-size:10px;color:rgba(255,255,255,0.7);'>{time}</span></div>"
            if "audio_bytes" in msg:
                audio_base64 = base64.b64encode(msg["audio_bytes"]).decode()
                chat_html += f"<div style='margin:6px 8px;'><audio controls src='data:audio/mp3;base64,{audio_base64}'></audio></div>"
    chat_html += "</div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# ----------------------------
# Chat Input (fixed prompt at bottom)
# ----------------------------
st.markdown("<div class='prompt-container'>", unsafe_allow_html=True)
with st.form("chat_input_form", clear_on_submit=True):
    cols = st.columns([12,1])
    with cols[0]:
        user_input = st.text_input("", placeholder="Type your message...", key="prompt_input", label_visibility="collapsed")
    with cols[1]:
        submitted = st.form_submit_button("📩")
st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# Clear chat button
# ----------------------------
if st.button("🗑 Clear Chat History"):
    st.session_state.chat_history = []
    st.experimental_rerun()

# ----------------------------
# Handle message submission: call LLM + TTS
# ----------------------------
if submitted and user_input and user_input.strip():
    # Save user message
    st.session_state.chat_history.append({
        "role":"user", "content": user_input, "time": datetime.now().strftime("%H:%M")
    })
    display_chat()

    # Build prompt with context
    prompt_text = f"""
Sales Call Flow Stage: {call_stage}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Brand: {brand}
Doctor Specialty: {specialty}
HCP Persona: {persona}
HCP Thinking Style: {thinking}
AI Tone: {tone}
Uploaded Docs Context: {st.session_state.uploaded_docs[:2000] if st.session_state.uploaded_docs else 'None'}
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

    # Call Groq
    groq_client = safe_groq_client()
    ai_text = ask_ai_via_groq(prompt_text, client=groq_client, fallback_message="⚠️ Groq API not configured or request failed.")

    # Try generate TTS
    audio_bytes = None
    try:
        tts_file = generate_tts_edge(ai_text, voice="en-US-JennyNeural")
        with open(tts_file, "rb") as f:
            audio_bytes = f.read()
    except Exception as e:
        st.warning(f"TTS generation issue: {e}")

    # Append AI response (with audio if available)
    entry = {"role":"ai", "content": ai_text, "time": datetime.now().strftime("%H:%M")}
    if audio_bytes:
        entry["audio_bytes"] = audio_bytes
    st.session_state.chat_history.append(entry)
    display_chat()

# ----------------------------
# Download Word (latest AI)
# ----------------------------
latest_ai = [m for m in st.session_state.chat_history if m["role"]=="ai"]
if latest_ai:
    latest_text = latest_ai[-1]["content"]
    try:
        from docx import Document as DocxDoc
        doc = DocxDoc()
        doc.add_heading("AI Sales Call Assistant - Latest Response", level=1)
        doc.add_paragraph(latest_text)
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)
        st.download_button("📥 Download latest AI response (.docx)", buffer.getvalue(), file_name="AI_Response.docx")
    except Exception:
        st.download_button("📥 Download latest AI response (.txt)", latest_text, file_name="AI_Response.txt")

# ----------------------------
# APCT expandable guidance
# ----------------------------
with st.expander("📌 APCT / AP A C T Objection Handling Framework"):
    st.markdown("""
    **APACT / APCT steps** — AI will highlight these when used in objection handling:
    - **Acknowledge**: Recognize the HCP's concern.
    - **Probing**: Ask targeted clarifying questions.
    - **Action / Clarify**: Provide evidence-based info concisely.
    - **Confirm**: Check for acceptance/understanding.
    - **Transition**: Move to next step/closing.
    """, unsafe_allow_html=True)

# ----------------------------
# Brand leaflet link + footer note
# ----------------------------
st.markdown(f"[📑 Brand Leaflet]({gsk_brands.get(brand)})")
st.markdown("<div style='font-size:12px; margin-top:12px; color:rgba(255,255,255,0.75)'>Built for internal sales support • Not for external distribution</div>", unsafe_allow_html=True)
