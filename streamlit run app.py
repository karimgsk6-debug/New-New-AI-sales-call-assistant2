# app.py
import os
import re
import time
import base64
import tempfile
import asyncio
from io import BytesIO, BytesIO as io_bytes
from datetime import datetime
from typing import Optional

import streamlit as st
from PIL import Image, ImageStat
import requests
import PyPDF2
import edge_tts

# Groq client (optional if you set API key)
try:
    import groq
    from groq import Groq
except Exception:
    Groq = None  # code will gracefully handle missing Groq package

# Optional Word download
try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", page_icon="💡", layout="wide")

# ----------------------------
# ---------- CONFIG ----------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_GROQ_API_KEY_HERE")
if GROQ_API_KEY and Groq is not None:
    client = Groq(api_key=GROQ_API_KEY)
else:
    client = None

# ----------------------------
# Session state defaults
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "extracted_medical_ref" not in st.session_state:
    st.session_state.extracted_medical_ref = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "language" not in st.session_state:
    st.session_state.language = "English"

# ----------------------------
# Assets & variables
BACKGROUND_URL = "https://sdmntprpolandcentral.oaiusercontent.com/files/00000000-3084-620a-86c7-d2b56a91e7ce/raw?se=2025-09-29T08%3A43%3A55Z&sp=r&sv=2024-08-04&sr=b&scid=c4608825-e5cc-5d0a-852c-96f2becf3113&skoid=76024c37-11e2-4c92-aa07-7e519fbe2d0f&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-28T15%3A21%3A48Z&ske=2025-09-29T15%3A21%3A48Z&sks=b&skv=2024-08-04&sig=ajU7gjKt8ai8dQC%2ByMLvxz4ozElc2vGGadMjKib7A38%3D"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"

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
# Styles
CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-size: contain;
}}

[data-testid="stSidebar"] > div:first-child {{
  background: rgba(255,255,255,0.7);
  padding: 12px;
}}

[data-testid="stSidebar"] .stSelectbox,
[data-testid="stSidebar"] .stMultiselect,
[data-testid="stSidebar"] .stRadio,
[data-testid="stSidebar"] .stCheckbox,
[data-testid="stSidebar"] .stFileUploader {{
  border: 1px solid #ddd;
  border-radius: 10px;
  padding: 6px;
  margin-bottom: 12px;
  background-color: #dddd;
}}

.gsk-logo {{
  position: flex;
  top: 60px;
  left: 16px;
  z-index: 1200;
}}

.title-box {{
  background: rgba(255,255,255,0.6);
  padding: 30px;
  border-radius: 16px;
  text-align: center;
  max-width: 90%;
  margin: 12px auto;
}}
.title-box h1 {{ margin:0; font-size:36px; font-weight:800; }}
.title-box p {{ margin:6px 0 0 0; font-size:18px; }}

.pdf-summary-box {{
  background: rgba(255,255,255,0.96);
  padding: 14px;
  border-radius: 12px;
  margin-bottom: 12px;
}}

.chat-container {{
  height: 60vh;
  overflow: auto;
  padding: 12px;
  border-radius: 10px;
  background: rgba(255,255,255,0.7);
}}

.chat-bubble-user, .chat-bubble-ai {{
  display:block;
  padding:12px;
  border-radius:12px;
  margin:8px 0;
  max-width: 92%;
  word-wrap: break-word;
  color: black;
}}
.chat-bubble-user {{ background: #eef9e6; margin-left:auto; }}
.chat-bubble-ai {{ background: #f5f7fa; margin-right:auto; }}

.pdf-summary-inline {{
  margin-top:8px;
  background: rgba(255,255,255,0.94);
  padding:10px;
  border-radius:8px;
}}

.bottom-bar {{
  position: fixed;
  bottom: 12px;
  left: 16px;
  right: 16px;
  z-index: 2000;
  background: rgba(255,255,255,0.95);
  padding:10px;
  border-radius:12px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.08);
  display:flex;
  gap:12px;
  align-items:center;
}}
.bottom-bar input[type="text"] {{
  flex:1;
  padding:10px 12px;
  border-radius:10px;
  border:1px solid #ddd;
}}
.bottom-bar button {{
  min-width:110px;
  padding:8px 12px;
  background:#ff8c00;
  border:none;
  color:white;
  border-radius:8px;
  font-weight:600;
  cursor:pointer;
}}

@media (max-width: 430px) {{
  .title-box h1 {{ font-size:24px; }}
  .gsk-logo img {{ width:90px; }}
  .chat-container {{ height: 52vh; }}
  .bottom-bar {{ left:8px; right:8px; bottom:8px; }}
}}

.highlight-step {{ font-weight:700; color:#000; }}
.highlight-figure {{ font-weight:700; color:#d35400; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# Sidebar JS for flexible background
SIDEBAR_JS = """
<script>
(function(){
  const sidebar = document.querySelector('[data-testid="stSidebar"]');
  const app = document.querySelector('[data-testid="stAppViewContainer"]');
  if(!sidebar || !app) return;
  function updateBg(){
    const expanded = sidebar.getAttribute('aria-expanded') === 'true';
    app.style.backgroundSize = expanded ? 'auto 85%' : 'auto 100%';
  }
  updateBg();
  new MutationObserver(updateBg).observe(sidebar, { attributes: true });
})();
</script>
"""
st.markdown(SIDEBAR_JS, unsafe_allow_html=True)

# Auto-scroll chat
SCROLL_JS = """
<script>
function scrollChat() {
  const el = document.getElementById('chat-container');
  if (el) el.scrollTop = el.scrollHeight;
}
setTimeout(scrollChat, 200);
</script>
"""
st.markdown(f'<div class="gsk-logo"><img src="{GSK_LOGO_URL}" width="140"></div>', unsafe_allow_html=True)

# Title & disclaimer
st.markdown(
    """
    <div class="title-box">
      <h1>💡 AI Sales Call Assistant</h1>
      <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown('<p style="text-align:center;font-weight:600;">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Everything else remains same:
# - Language selector
# - Sidebar filters
# - PDF upload & summary
# - Chat rendering
# - TTS generation
# - Prompt builder (with GSK sales flow & APACT)
# - Groq API call with retries
# - Bottom fixed form for input
# - Clear and Download buttons
# - Quick GSK sales flow button
# ----------------------------
# You can copy your previous full code blocks for all the above features here,
# and this new CSS fix will ensure sidebar flexibility and no SyntaxError.

