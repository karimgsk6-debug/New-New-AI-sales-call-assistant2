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
    # Remove punctuation for smoother TTS
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
                {"role": "system", "content": "You are a helpful AI medical sales assistant. Structure answers by the sales call flow, use APACT technique, and reference uploaded documents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1200
        )
    except:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a helpful AI medical sales assistant. Structure answers by the sales call flow, use APACT technique, and reference uploaded documents."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1200
        )
    return response.choices[0].message.content

# ----------------------------
# Expanded Medical References
# ----------------------------
references = {
    "Shingrix": {
        "GP": [
            "Lal H et al. Efficacy of an adjuvanted herpes zoster subunit vaccine in older adults. NEJM 2015.",
            "GSK Product Monograph: Shingrix, 2023."
        ],
        "Specialist": [
            "Dagnew AF et al. Shingrix in immunocompromised adults. Lancet Infect Dis 2021."
        ]
    },
    "Trelegy": {
        "Pulmonologist": [
            "Lipson DA et al. Once-daily single-inhaler triple therapy in COPD. NEJM 2018.",
            "GSK Product Monograph: Trelegy Ellipta, 2023."
        ]
    },
    "Zejula": {
        "Oncologist": [
            "Mirza MR et al. Niraparib maintenance therapy in platinum-sensitive ovarian cancer. NEJM 2016.",
            "GSK Product Monograph: Zejula, 2023."
        ]
    }
}

# ----------------------------
# Session State
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = ""

# ----------------------------
# Language Selection
# ----------------------------
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])
voice_lang = "ar-SA-HamedNeural" if language=="العربية" else "en-US-JennyNeural"

# ----------------------------
# Logo & Header
# ----------------------------
logo_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
col1, col2 = st.columns([1,5])
with col1:
    st.image(logo_url, width=120)
with col2:
    st.title("🧠 AI Sales Call Assistant")

st.markdown("""
<div style='padding:10px; background:#f8f9fa; border:1px solid #ddd; border-radius:10px; margin-bottom:20px; font-size:13px;'>
⚠️ <b>Disclaimer:</b> The main objective of this AI tool is to equip the sales representative with the right tools to handle different HCP concerns. 
It is not a substitute for official product information or medical advice.
</div>
""", unsafe_allow_html=True)

# ----------------------------
# Sidebar Filters
# ----------------------------
st.sidebar.header("Filters & Options")
gsk_brands = list(references.keys())
brand = st.sidebar.selectbox("Select Brand", options=gsk_brands)
segment = st.sidebar.selectbox("Segment", options=["GP", "Specialist", "Oncologist", "Pulmonologist"])
barrier = st.sidebar.multiselect("Doctor Barrier", ["Awareness", "Access", "Affordability", "Attitude"])
objective = st.sidebar.selectbox("Objective", ["Awareness", "Adoption", "Retention"])
specialty = st.sidebar.selectbox("Specialty", ["GP", "Oncologist", "Pulmonologist", "Dermatologist"])
persona = st.sidebar.selectbox("HCP Persona", ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"])
tone = st.sidebar.selectbox("AI Tone", ["Formal", "Casual", "Friendly", "Persuasive"])
thinking = st.sidebar.selectbox("HCP Thinking Style", ["Analytical", "Skeptic", "Emotional", "Pragmatic"])

# ----------------------------
# Upload Supporting Docs
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
    st.success(f"✅ Uploaded {uploaded_file.name}")

# ----------------------------
# Sales Call Flow
# ----------------------------
call_flow = [
    "Pre-Call Planning",
    "Engage",
    "Create Opportunity",
    "Influence",
    "Impact (GSO)",
    "Closing with Commitment",
    "Post-Call Analysis"
]
call_stage = st.selectbox("Select Call Stage", options=call_flow)

# ----------------------------
# Chat Styling
# ----------------------------
st.markdown("""
<style>
.chat-container { max-height:65vh; overflow-y:auto; padding-bottom:70px; }
.user-bubble { text-align:right; background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; margin:5px; display:inline-block; max-width:80%; box-shadow:0 1px 3px rgba(0,0,0,0.1);}
.ai-bubble { text-align:left; background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; margin:5px; display:inline-block; max-width:80%; box-shadow:0 1px 3px rgba(0,0,0,0.1);}
.prompt-container { position:fixed; bottom:10px; width:95%; background:#fff; padding:5px 10px; z-index:999; box-shadow:0 0 5px rgba(0,0,0,0.1); border-radius:10px;}
</style>
""", unsafe_allow_html=True)

chat_placeholder = st.empty()

# ----------------------------
# Display Chat
# ----------------------------
def display_chat():
    chat_html = "<div class='chat-container'>"
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n","<br>")
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
# Chat Input
# ----------------------------
with st.form("chat_form", clear_on_submit=True):
    st.markdown("<div class='prompt-container'>", unsafe_allow_html=True)
    col1, col2 = st.columns([8,1])
    with col1:
        user_input = st.text_input("", placeholder="Type your message...")
    with col2:
        submitted = st.form_submit_button("📩")
    st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# AI Processing
# ----------------------------
if submitted and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})
    prompt = f"""
Stage: {call_stage}
Language: {language}
Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Brand: {brand}
Doctor Specialty: {specialty}
HCP Persona: {persona}
HCP Thinking Style: {thinking}
AI Tone: {tone}
Uploaded Docs Context: {st.session_state.uploaded_docs[:2000]}
User Input: {user_input}

Please structure the response according to the full sales call flow:
1. Pre-Call Planning
2. Engage
3. Create Opportunity
4. Influence
5. Impact (GSO)
6. Closing with Commitment
7. Post-Call Analysis

Always tailor the answer using APACT technique and reference the brand medical data.
"""
    ai_text = ask_ai(prompt)

    # Add references if available
    refs = references.get(brand, {}).get(specialty, [])
    if refs:
        ai_text += "\n\n📚 References:\n" + "\n".join([f"- {r}" for r in refs])

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
