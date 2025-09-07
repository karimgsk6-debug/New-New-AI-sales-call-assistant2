import os
import streamlit as st
from PIL import Image
import requests
from io import BytesIO
import fitz  # PyMuPDF for PDF handling
from pptx import Presentation
from groq import Groq
import tempfile
import base64
from gtts import gTTS
import st_audiorec

# =========================
# CONFIG
# =========================
API_KEY = "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"  # 🔑 Direct API key here
client = Groq(api_key=API_KEY)

st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# =========================
# HEADER & DISCLAIMER
# =========================
col1, col2 = st.columns([1, 4])
with col1:
    try:
        gsk_logo = Image.open("gsk_logo.png")
        st.image(gsk_logo, width=120)
    except:
        st.write("🟠 **GSK**")

with col2:
    st.markdown(
        "<h2 style='color:orange;'>AI Sales Call Assistant</h2>"
        "<b>Disclaimer:</b> This tool supports sales reps in preparing smarter calls. "
        "Always refer to approved GSK references.",
        unsafe_allow_html=True,
    )

st.markdown("---")

# =========================
# HCP SEGMENTS / PERSONAS / BARRIERS
# =========================
st.sidebar.header("📌 HCP Profile")
hcp_segment = st.sidebar.selectbox("HCP Segment", ["High Potential", "Medium Potential", "Low Potential"])
persona = st.sidebar.selectbox("Persona", ["Innovator", "Conservative", "Skeptic"])
barrier = st.sidebar.multiselect("Barriers", ["Cost", "Efficacy Doubts", "Side Effects", "Lack of Awareness"])

# =========================
# SALES CALL MODULES
# =========================
st.sidebar.header("📌 Sales Call Flow")
call_step = st.sidebar.radio(
    "Select Call Flow Step",
    ["Prepare", "Engage", "Create Opportunities", "Drive Impact", "Post-Call Analysis"]
)

st.sidebar.header("📌 APACT Technique")
use_apact = st.sidebar.checkbox("Enable APACT for Objection Handling")

# =========================
# REP INPUT
# =========================
st.subheader("🗣️ Record or Write Your Input")

# Voice recording
wav_audio_data = st_audiorec.st_audiorec()
rep_input_text = ""

if wav_audio_data is not None:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_wav:
        tmp_wav.write(wav_audio_data)
        audio_path = tmp_wav.name
    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-large-v3",
            file=audio_file
        )
        rep_input_text = transcript.text
        st.success(f"✅ Voice-to-Text: {rep_input_text}")

# Text input
rep_manual_text = st.text_area("Or type your input here:", "")
if rep_manual_text.strip():
    rep_input_text += " " + rep_manual_text.strip()

# =========================
# VOICE STYLE
# =========================
voice_style = st.selectbox("🎙️ Select Voice Style", ["Professional", "Friendly", "Empathetic"])

# =========================
# AI RESPONSE
# =========================
if st.button("Generate AI Response"):
    if not rep_input_text.strip():
        st.warning("Please provide input (voice or text).")
    else:
        with st.spinner("🤖 Generating AI Response..."):
            # Build the prompt
            prompt = f"""
            You are an AI Sales Call Assistant.

            HCP Segment: {hcp_segment}
            Persona: {persona}
            Barriers: {', '.join(barrier) if barrier else 'None'}
            Sales Call Step: {call_step}
            APACT: {"Enabled" if use_apact else "Disabled"}
            Rep Input: {rep_input_text}

            Response rules:
            - Always structure thinking according to the Sales Call Flow:
              Prepare → Engage → Create Opportunities → Drive Impact → Post-Call Analysis
            - Use APACT (Acknowledge, Probe, Address, Confirm, Transition) ONLY when objections/barriers appear.
            - Be persuasive, empathetic, and aligned with GSK tone.
            - Style: {voice_style} tone.
            """

            response = client.chat.completions.create(
                model="meta-llama/llama-3.1-70b-instruct",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )

            ai_response = response.choices[0].message.content
            st.markdown("### 💡 AI Response")
            st.write(ai_response)

            # =========================
            # SMART AUDIO OUTPUT
            # =========================
            lang = "ar" if any("\u0600" <= c <= "\u06FF" for c in ai_response) else "en"
            slow_mode = True if voice_style == "Empathetic" else False

            tts = gTTS(text=ai_response, lang=lang, slow=slow_mode)
            audio_file_path = "ai_response.mp3"
            tts.save(audio_file_path)

            with open(audio_file_path, "rb") as audio_file:
                audio_bytes = audio_file.read()
            st.audio(audio_bytes, format="audio/mp3")
