import os
import io
import base64
import requests
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
# External Background Image (Blurred)
# ----------------------------
background_url = "https://image.shutterstock.com/image-photo/young-arab-girl-using-ipad-260nw-2616487693.jpg"

st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{
    background: url("{background_url}") no-repeat center center fixed;
    background-size: cover;
}}
[data-testid="stAppViewContainer"]::before {{
    content: "";
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: url("{background_url}") no-repeat center center fixed;
    background-size: cover;
    filter: blur(8px) brightness(0.85);
    z-index: -1;
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
if mode == "Dark":
    st.markdown("""
    <style>
    body, [data-testid="stAppViewContainer"] {{
        color: white !important;
    }}
    .stTextInput input, .stTextArea textarea {{
        background-color: #222 !important;
        color: white !important;
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
# Chat Section (Prompt Box like ChatGPT)
# ----------------------------
st.markdown(
    """
    <style>
    .prompt-box {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 10px;
        border-radius: 12px;
        border: 1px solid #ccc;
        background: white;
        margin-top: 15px;
    }
    .prompt-box input {
        flex-grow: 1;
        border: none;
        outline: none;
        font-size: 16px;
    }
    .send-btn {
        background: #FF6200;
        color: white;
        border: none;
        border-radius: 50%;
        padding: 10px 14px;
        cursor: pointer;
        font-size: 18px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

user_prompt = st.text_input("💬 Ask something:", placeholder="Type your question here...")

if st.button("▶️ Send"):
    if user_prompt:
        st.markdown(f"<div class='user-bubble'>🧑 You: {user_prompt}</div>", unsafe_allow_html=True)
        # Dummy AI response (can be replaced with Groq/LLM output)
        ai_response = "🤖 AI: Let's apply APCT — *Acknowledge, Probe, Clarify, Tailor*."
        st.markdown(f"<div class='ai-bubble'>{ai_response}</div>", unsafe_allow_html=True)

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
