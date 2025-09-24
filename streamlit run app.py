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
# Home Page Background (ROBUST)
# ----------------------------
background_url = "https://images.unsplash.com/photo-1682686581986-78d030d5c1d1?auto=format&fit=crop&w=1470&q=80"
st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{
    background-image: url("{background_url}");
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}}
[data-testid="stAppViewContainer"] .css-18e3th9 {{
    background-color: rgba(0,0,0,0.0);
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
# The rest of your code (logo, sidebar filters, chat, uploads, TTS, word download) 
# can remain exactly as in the previous full code provided, 
# just ensure the background CSS above replaces the old background code.
# ----------------------------
