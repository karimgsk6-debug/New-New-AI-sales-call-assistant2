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
GROQ_API_KEY = "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"  # <- replace
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
BACKGROUND_URL = ("https://sdmntprukwest.oaiusercontent.com/files/00000000-abd4-6243-82cf-168367664603/raw?se=2025-09-27T20%3A50%3A12Z&sp=r&sv=2024-08-04&sr=b&scid=ecda9bff-da85-5e32-ac41-b08c14ba28cf&skoid=d9a3f0e9-8380-4267-a144-3f27388a5c5d&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-27T12%3A41%3A14Z&ske=2025-09-28T12%3A41%3A14Z&sks=b&skv=2024-08-04&sig=oXICxZIQ74jEr/fZxSZH/TmBnN8eb/3bsNRGRUHTsf0%3D")
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
button_bg = "#FFA500" if brightness > 130 else "#FF8C00"

# ----------------------------
# CSS (full-page background + plain chat)
# ----------------------------
CSS = f"""
<style>
/* Main app background (full-page, behind sidebar) */
.stApp {{
    background: url('{BACKGROUND_URL}') no-repeat top right;
    background-size: cover; /* fill entire app */
    background-attachment: fixed;
}}

/* Sidebar default white and padding */
.stSidebar {{
    background-color: rgba(255,255,255,0.9); /* semi-transparent */
    padding: 14px;
}}

/* Filter controls borders */
.stSidebar .stSelectbox, .stSidebar .stMultiselect, .stSidebar .stRadio, .stSidebar .stCheckbox, .stSidebar .stFileUploader {{
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 8px;
    margin-bottom: 12px;
    background-color: #fff;
}}

/* Title & layout */
.gsk-logo {{
    position: fixed;
    top: 60px;
    right: 16px;
    z-index: 1000;
}}
.title-box {{
    background: rgba(255,255,255,0.96);
    padding: 28px;
    border-radius: 14px;
    text-align: center;
    max-width: 85%;
    margin: 12px auto;
}}
.title-box h1 {{ margin: 0; font-size: 38px; font-weight: 800; }}
.title-box p {{ margin: 8px 0 0 0; font-size: 18px; font-weight: 500; }}
.disclaimer {{ text-align:center; padding:10px; font-size:14px; font-weight:500; }}

/* Plain chat text (no bubbles) */
#chat-container {{
    height:60vh;
    overflow:auto;
    padding:12px;
    border-radius:8px;
    background: rgba(255,255,255,0.6);
    color: {text_color};
    font-size: 16px;
    line-height: 1.5;
}}

/* Bottom bar */
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
.chat-input {{
    flex: 1;
}}
.clear-btn, .download-btn {{
    min-width: 140px;
}}

/* Responsive tweaks */
@media (max-width: 800px) {{
    .title-box h1 {{ font-size: 28px; }}
    .gsk-logo img {{ width: 110px; }}
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# JS to handle sidebar collapse/expand and adjust background-size
SIDEBAR_JS = """
<script>
(function() {
  const app = document.querySelector('.stApp');
  const sidebar = document.querySelector('[data-testid="stSidebar"]');
  if (!app || !sidebar) return;

  function adjustBg() {
    const expanded = sidebar.getAttribute('aria-expanded') === 'true';
    app.style.backgroundSize = expanded ? 'cover' : 'cover';
  }

  adjustBg();

  const mo = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.attributeName === 'aria-expanded') adjustBg();
    }
  });
  mo.observe(sidebar, { attributes: true });
})();
</script>
"""
st.markdown(SIDEBAR_JS, unsafe_allow_html=True)

# JS to auto-scroll chat
SCROLL_JS = """
<script>
function scrollChat() {
  const container = document.getElementById('chat-container');
  if (container) container.scrollTop = container.scrollHeight;
}
setTimeout(scrollChat, 200);
</script>
"""

# ----------------------------
# Top-right logo + title + disclaimer
# ----------------------------
st.markdown(f'<div class="gsk-logo"><img src="{GSK_LOGO_URL}" width="140" /></div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="title-box">
      <h1>💡 AI Sales Call Assistant</h1>
      <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown('<p class="disclaimer">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Top-left language selector
# ----------------------------
st.markdown(
    """
    <div style="position:fixed; top:76px; left:18px; z-index:1000; background: rgba(255,255,255,0.95); padding:6px 10px; border-radius:8px;">
    """,
    unsafe_allow_html=True,
)
language = st.radio("", options=["English", "العربية"], horizontal=True, label_visibility="collapsed")
st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# Remaining code (PDF upload, sidebar filters, Groq, TTS, chat input, bottom bar, etc.)
# Use your existing code but remove chat bubble classes and use plain text
# ----------------------------
# For chat rendering:
def render_chat_html() -> str:
    html = '<div id="chat-container">'
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n", "<br>")
        for step in ["Acknowledge", "Probing", "Action", "Confirm", "Transition"]:
            content = content.replace(step, f"<span class='highlight'>{step}</span>")
        html += f"{content}<br><span style='font-size:10px;color:gray'>{msg.get('time','')}</span><br><br>"
    html += '</div>'
    return html

st.markdown(render_chat_html(), unsafe_allow_html=True)
st.markdown(SCROLL_JS, unsafe_allow_html=True)

# ----------------------------
# The rest of your code (PDF upload, Groq AI calls, TTS, bottom bar, clear/download buttons, etc.)
# ----------------------------
