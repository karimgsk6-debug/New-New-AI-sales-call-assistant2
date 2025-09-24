import os
import io
import base64
from pathlib import Path
from datetime import datetime

import streamlit as st
from PIL import Image
from docx import Document
import pdfplumber
from pptx import Presentation
from groq import Groq
import asyncio
import edge_tts

# ----------------------------
# App Configuration
# ----------------------------
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------
# External Background Image (Cropped + Overlay)
# ----------------------------
background_url = "https://image.shutterstock.com/image-photo/young-arab-girl-using-ipad-260nw-2616487693.jpg"

st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{
    background: url("{background_url}") no-repeat top center fixed;
    background-size: cover;
}}
[data-testid="stAppViewContainer"]::before {{
    content: "";
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.45); /* dark overlay */
    z-index: -1;
}}
body, [data-testid="stAppViewContainer"], .stMarkdown, .stTextInput, .stTextArea, .stButton button {{
    color: white !important;
}}
.stTextInput input, .stTextArea textarea {{
    background-color: rgba(255,255,255,0.1) !important;
    color: white !important;
    border-radius: 8px;
    border: 1px solid #aaa;
}}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Branding & Header
# ----------------------------
st.markdown(
    "<h1 style='color:#FF6200; text-align:center;'>AI Sales Call Assistant</h1>",
    unsafe_allow_html=True,
)
st.markdown(
    "<p style='text-align:center; font-size:18px;'>Powered by GSK • APCT objection-handling • Dark Mode Toggle</p>",
    unsafe_allow_html=True,
)

# ----------------------------
# Dark/Light Mode Toggle
# ----------------------------
mode = st.sidebar.radio("🌗 Theme", ["Light", "Dark"])
if mode == "Light":
    st.markdown("""
    <style>
    body, [data-testid="stAppViewContainer"], .stMarkdown {{
        color: black !important;
    }}
    .stTextInput input, .stTextArea textarea {{
        background-color: white !important;
        color: black !important;
    }}
    </style>
    """, unsafe_allow_html=True)

# ----------------------------
# Upload Section
# ----------------------------
st.sidebar.header("📂 Upload Files")
uploaded_files = st.sidebar.file_uploader(
    "Upload DOCX, PDF, or PPTX",
    type=["docx", "pdf", "pptx"],
    accept_multiple_files=True,
)

# ----------------------------
# Process Uploaded Files
# ----------------------------
def extract_text_from_file(file):
    text = ""
    if file.name.endswith(".docx"):
        doc = Document(file)
        for p in doc.paragraphs:
            text += p.text + "\n"
    elif file.name.endswith(".pdf"):
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    elif file.name.endswith(".pptx"):
        prs = Presentation(file)
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text += shape.text + "\n"
    return text

uploaded_text = ""
if uploaded_files:
    for f in uploaded_files:
        uploaded_text += extract_text_from_file(f) + "\n"

# ----------------------------
# Initialize Groq Client
# ----------------------------
groq_api_key = os.getenv("GROQ_API_KEY")
groq_client = None
if groq_api_key:
    groq_client = Groq(api_key=groq_api_key)

async def generate_tts(text, filename="response.mp3"):
    communicate = edge_tts.Communicate(text, "en-US-JennyNeural")
    await communicate.save(filename)
    return filename

def generate_ai_response(prompt):
    if not groq_client:
        return "⚠️ Groq API key not found. Please set GROQ_API_KEY."
    chat_completion = groq_client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[
            {"role": "system", "content": "You are a helpful sales assistant using APCT objection handling."},
            {"role": "user", "content": prompt},
        ]
    )
    return chat_completion.choices[0].message.content

# ----------------------------
# Chat Section (Prompt Box like ChatGPT)
# ----------------------------
st.markdown(
    """
    <style>
    .user-bubble {{
        background: rgba(255,255,255,0.1);
        padding: 10px 14px;
        margin: 8px 0;
        border-radius: 12px;
    }}
    .ai-bubble {{
        background: rgba(255,98,0,0.2);
        padding: 10px 14px;
        margin: 8px 0;
        border-radius: 12px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

user_prompt = st.text_input("💬 Ask something:", placeholder="Type your question here...")

if st.button("▶️ Send"):
    if user_prompt:
        st.markdown(f"<div class='user-bubble'>🧑 You: {user_prompt}</div>", unsafe_allow_html=True)
        ai_response = generate_ai_response(user_prompt + "\n\n" + uploaded_text)
        st.markdown(f"<div class='ai-bubble'>🤖 {ai_response}</div>", unsafe_allow_html=True)

        # Generate TTS
        try:
            filename = asyncio.run(generate_tts(ai_response))
            audio_file = open(filename, "rb")
            st.audio(audio_file.read(), format="audio/mp3")
        except Exception as e:
            st.error(f"TTS Error: {e}")

# ----------------------------
# APCT Highlights
# ----------------------------
with st.expander("📌 APCT Objection Handling Framework"):
    st.markdown(
        """
        - **Acknowledge**: Recognize the HCP’s concern.  
        - **Probe**: Ask clarifying questions to understand deeper.  
        - **Clarify**: Provide clear, evidence-based information.  
        - **Tailor**: Personalize the response to their context.  
        """,
        unsafe_allow_html=True,
    )
