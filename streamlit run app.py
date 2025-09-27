# app.py
import streamlit as st
from PIL import Image, ImageStat
import requests
from io import BytesIO, BytesIO as io_bytes
import groq
from groq import Groq
from datetime import datetime
import PyPDF2
import asyncio
import edge_tts
import base64
import re
import os
import tempfile
import time
from typing import Optional

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", page_icon="💡", layout="wide")

# ----------------------------
# Optional Word download (docx)
# ----------------------------
try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# ----------------------------
# GROQ client (replace with your key)
# ----------------------------
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# ----------------------------
# Session state defaults
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "extracted_medical_ref" not in st.session_state:
    st.session_state.extracted_medical_ref = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""

# ----------------------------
# Assets & styling variables
# ----------------------------
# Permanent Unsplash healthcare background
BACKGROUND_URL = "https://sdmntprsouthcentralus.oaiusercontent.com/files/00000000-a9b4-61f7-b2cf-05a782087038/raw?se=2025-09-27T16%3A42%3A35Z&sp=r&sv=2024-08-04&sr=b&scid=5258dbc1-6382-5fec-a8d5-ad7bcc18750b&skoid=b928fb90-500a-412f-a661-1ece57a7c318&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-26T17%3A22%3A36Z&ske=2025-09-27T17%3A22%3A36Z&sks=b&skv=2024-08-04&sig=eSrtOWb2e5Fm4%2Bpg7z1kf2I0XJ2H3I/Mqc5df0aOFSk%3D"
GSK_LOGO_URL = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"

def get_brightness(url: str) -> int:
    try:
        r = requests.get(url, timeout=8)
        img = Image.open(BytesIO(r.content)).convert("L")
        stat = ImageStat.Stat(img)
        return int(stat.mean[0])
    except Exception:
        return 255

brightness = get_brightness(BACKGROUND_URL)
text_color = "black" if brightness > 130 else "white"

# ----------------------------
# CSS (responsive background + sidebar white + filter borders + UI)
# ----------------------------
CSS = f"""
<style>
.stApp {{
    background: url('{BACKGROUND_URL}') no-repeat top right;
    background-size: cover;
    background-attachment: fixed;
}}

.stSidebar {{
    background-color: #fff;
    padding: 14px;
    border-left: 2px solid #eee;
}}

.stSidebar .stSelectbox, .stSidebar .stMultiselect, .stSidebar .stRadio, 
.stSidebar .stCheckbox, .stSidebar .stFileUploader {{
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 8px;
    margin-bottom: 12px;
    background-color: #fff;
}}

.gsk-logo {{
    position: fixed;
    top: 60px;
    right: 16px;
    z-index: 1000;
}}
.title-box {{
    background: rgba(255,255,255,0.7);
    padding: 28px;
    border-radius: 14px;
    text-align: center;
    max-width: 85%;
    margin: 12px auto;
}}
.title-box h1 {{ margin: 0; font-size: 38px; font-weight: 800; }}
.title-box p {{ margin: 8px 0 0 0; font-size: 18px; font-weight: 500; }}
.disclaimer {{ text-align:center; padding:10px; font-size:14px; font-weight:500; }}

.chat-bubble-user {{
    text-align: right;
    background: rgba(220,248,198,0.95);
    padding: 12px;
    border-radius: 15px 15px 0 15px;
    margin: 6px;
    display: inline-block;
    max-width: 80%;
    color: {text_color};
}}
.chat-bubble-ai {{
    text-align: left;
    background: rgba(240,242,246,0.95);
    padding: 12px;
    border-radius: 15px 15px 15px 0;
    margin: 6px;
    display: inline-block;
    max-width: 80%;
    color: {text_color};
}}
.highlight {{
    font-weight: bold;
    background-color: yellow;
    color: black;
    padding: 2px 4px;
    border-radius: 4px;
}}

.bottom-bar {{
    position: fixed;
    bottom: 12px;
    width: 96%;
    left: 2%;
    z-index: 1000;
    display:flex;
    gap:12px;
    align-items:center;
}}
.chat-input {{ flex: 1; }}

.clear-btn, .download-btn {{
    min-width: 140px;
}}

@media (max-width: 800px) {{
    .title-box h1 {{ font-size: 28px; }}
    .gsk-logo img {{ width: 110px; }}
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------
# Sidebar background responsiveness (JS)
# ----------------------------
SIDEBAR_JS = """
<script>
(function() {
  function setBgSize(expanded) {
    const el = document.querySelector('.stApp');
    if (!el) return;
    el.style.backgroundSize = expanded ? 'auto 90%' : 'cover';
  }
  const sidebar = document.querySelector('[data-testid="stSidebar"]');
  if (!sidebar) return;
  setBgSize(sidebar.getAttribute('aria-expanded') === 'true');
  const mo = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.attributeName === 'aria-expanded') {
        setBgSize(sidebar.getAttribute('aria-expanded') === 'true');
      }
    }
  });
  mo.observe(sidebar, { attributes: true });
})();
</script>
"""
st.markdown(SIDEBAR_JS, unsafe_allow_html=True)
