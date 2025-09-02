import streamlit as st
from PIL import Image
import requests
from io import BytesIO
from datetime import datetime
import re
import groq
from groq import Groq
from gtts import gTTS
from audiorecorder import audiorecorder

# ========== CONFIG ==========
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# Initialize Groq client
client = Groq(api_key=st.secrets["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"])

# ========== FUNCTIONS ==========

# Function: Generate AI Sales Call Flow + Objection Handling
def generate_ai_response(prompt):
    system_message = """
You are an AI assistant helping pharmaceutical sales representatives.

- Always structure responses as a Sales Call Flow (Prepare → Engage → Create Opportunities → Drive Impact → Post Call Analysis).
- Use APCT (Acknowledge, Probe, Confirm, Transition) ONLY when handling objections or concerns.
- Think step-by-step like a sales rep planning their visit.
- Provide references when possible (e.g., CDC, EDA prescribing info).
- Use professional tone suitable for HCP discussions.
"""
    response = client.chat.completions.create(
        model="llama-3.1-70b-versatile",
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

# Function: Convert text to speech
def text_to_speech(text, filename="ai_reply.mp3"):
    tts = gTTS(text=text, lang="en")
    tts.save(filename)
    return filename

# Function: Display Chat Bubble
def display_message(sender, message, timestamp, is_ai=True, audio_file=None):
    icon_url = "https://img.icons8.com/emoji/48/000000/robot-emoji.png" if is_ai else "https://img.icons8.com/emoji/48/000000/speaking-head-emoji.png"

    st.markdown(
        f"""
        <div style='display:flex; justify-content:flex-start; margin:5px;'>
            <div style='background:#f0f2f6; padding:10px; border-radius:15px; border:2px solid #888; max-width:75%; display:flex; align-items:flex-start;'>
                <img src="{icon_url}" width="30" style='margin-right:10px;'>
                <div style='flex:1;'>
                    <b>{sender}</b>: {message}<br>
                    <span style='font-size:10px; color:gray;'>{timestamp}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    if audio_file:
        st.audio(audio_file, format="audio/mp3")

# Function: Split AI reply into steps (Sales Call Flow or APCT if objections)
def display_structured_response(ai_text):
    # Sales Call Flow steps
    call_flow_steps = ["Prepare", "Engage", "Create Opportunities", "Drive Impact", "Post Call Analysis"]
    # APCT steps for objections
    objection_steps = ["Acknowledge", "Probe", "Confirm", "Transition"]

    # First try splitting by Call Flow steps
    steps = re.split(r'(?<=\b)(Prepare|Engage|Create Opportunities|Drive Impact|Post Call Analysis)\b', ai_text)
    if len(steps) <= 1:  # If no call flow, try APCT
        steps = re.split(r'(?<=\b)(Acknowledge|Probe|Confirm|Transition)\b', ai_text)

    # Display each step separately
    for i in range(1, len(steps), 2):
        step_title = steps[i]
        step_content = steps[i+1] if i+1 < len(steps) else ""
        display_message("AI Assistant", f"**{step_title}:** {step_content.strip()}", datetime.now().strftime("%H:%M"), is_ai=True)

# ========== APP HEADER ==========
col1, col2 = st.columns([1,5])
with col1:
    logo_url = "https://upload.wikimedia.org/wikipedia/commons/4/4f/GSK_logo_2022.svg"
    st.image(logo_url, width=80)
with col2:
    st.markdown("<h2 style='color:orange; font-weight:bold;'>AI Sales Call Assistant</h2>", unsafe_allow_html=True)

st.markdown(
    """
    ⚠️ <i>This AI tool is designed to support GSK reps in structuring sales calls.  
    Always refer to approved references and use your judgment during HCP interactions.</i>
    """,
    unsafe_allow_html=True
)

# ========== VOICE INPUT ==========
st.markdown("### 🎤 Record Your Sales Call Message")
audio = audiorecorder("Click to record", "Click to stop recording")

if len(audio) > 0:
    # Play back the recorded message
    st.audio(audio.export().read(), format="audio/wav")
    
    # Placeholder transcription (replace with STT later)
    rep_message = "Rep voice message transcribed (placeholder: integrate STT here)."
    display_message("Rep (Voice)", rep_message, datetime.now().strftime("%H:%M"), is_ai=False)

    # Generate AI structured reply
    ai_reply = generate_ai_response(rep_message)
    reply_audio = text_to_speech(ai_reply)

    display_structured_response(ai_reply)
    st.audio(reply_audio, format="audio/mp3")

# ========== TEXT INPUT ==========
st.markdown("### 💬 Or Type Your Sales Call Message")
user_input = st.text_area("Enter your message here:")

if st.button("Send Text Message"):
    if user_input.strip():
        display_message("Rep", user_input, datetime.now().strftime("%H:%M"), is_ai=False)
        
        ai_reply = generate_ai_response(user_input)
        reply_audio = text_to_speech(ai_reply)

        display_structured_response(ai_reply)
        st.audio(reply_audio, format="audio/mp3")
