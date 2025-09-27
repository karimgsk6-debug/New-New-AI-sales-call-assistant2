# app.py
import streamlit as st
from PIL import ImageStat, Image
import requests
from io import BytesIO
from datetime import datetime
import PyPDF2
import asyncio
import edge_tts
import base64
import re
from groq import Groq

# ----------------------------
# Page Config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", page_icon="💡", layout="wide")

# ----------------------------
# GROQ API (replace with your own key)
# ----------------------------
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# ----------------------------
# Session State
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""

# ----------------------------
# CSS Styling (GSK Orange gradient background + sidebar white with borders)
# ----------------------------
CSS = """
<style>
.stApp {
    background: linear-gradient(135deg, #ff5f1f 0%, #ff944d 100%);
    background-attachment: fixed;
}

.stSidebar {
    background-color: #fff;
    padding: 14px;
    border-left: 2px solid #eee;
}

.stSidebar .stSelectbox, .stSidebar .stMultiselect, .stSidebar .stRadio, 
.stSidebar .stCheckbox, .stSidebar .stFileUploader {
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 8px;
    margin-bottom: 12px;
    background-color: #fff;
}

.gsk-logo {
    position: fixed;
    top: 60px;
    right: 16px;
    z-index: 1000;
}

.title-box {
    background: rgba(255,255,255,0.85);
    padding: 28px;
    border-radius: 14px;
    text-align: center;
    max-width: 85%;
    margin: 12px auto;
}
.title-box h1 { margin: 0; font-size: 38px; font-weight: 800; }
.title-box p { margin: 8px 0 0 0; font-size: 18px; font-weight: 500; }

.chat-bubble-user {
    text-align: right;
    background: rgba(220,248,198,0.95);
    padding: 12px;
    border-radius: 15px 15px 0 15px;
    margin: 6px;
    display: inline-block;
    max-width: 80%;
}
.chat-bubble-ai {
    text-align: left;
    background: rgba(240,242,246,0.95);
    padding: 12px;
    border-radius: 15px 15px 15px 0;
    margin: 6px;
    display: inline-block;
    max-width: 80%;
}
.highlight {
    font-weight: bold;
    background-color: yellow;
    color: black;
    padding: 2px 4px;
    border-radius: 4px;
}

.bottom-bar {
    position: fixed;
    bottom: 12px;
    width: 96%;
    left: 2%;
    z-index: 1000;
    display:flex;
    gap:12px;
    align-items:center;
}
.chat-input { flex: 1; }
.clear-btn, .download-btn { min-width: 140px; }

@media (max-width: 800px) {
    .title-box h1 { font-size: 28px; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------
# JavaScript to adapt background with sidebar expand/collapse
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

# ----------------------------
# TTS Function (English + Arabic)
# ----------------------------
async def synthesize_speech(text: str, lang: str = "en") -> Optional[str]:
    try:
        if lang == "ar":
            voice = "ar-EG-SalmaNeural"
        else:
            voice = "en-US-JennyNeural"
        communicate = edge_tts.Communicate(text, voice)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            out_path = f.name
        await communicate.save(out_path)
        return out_path
    except Exception as e:
        st.error(f"TTS error: {e}")
        return None

def play_audio(file_path: str):
    if file_path and os.path.exists(file_path):
        with open(file_path, "rb") as f:
            audio_bytes = f.read()
        st.audio(audio_bytes, format="audio/mp3")

# ----------------------------
# PDF Upload & Summary
# ----------------------------
def extract_pdf_text(file) -> str:
    reader = PyPDF2.PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def summarize_text(text: str) -> str:
    if not text.strip():
        return "No text found."
    summary_prompt = f"Summarize this medical text in 5 bullet points:\n\n{text[:2000]}"
    resp = client.chat.completions.create(
        model="llama3-8b-8192",
        messages=[{"role": "system", "content": "You are a medical summarizer."},
                  {"role": "user", "content": summary_prompt}]
    )
    return resp.choices[0].message.content.strip()

# ----------------------------
# Chat Completion with GROQ (APACT + GSK sales call)
# ----------------------------
def groq_chat_completion(messages):
    return client.chat.completions.create(
        model="llama3-8b-8192",
        messages=messages,
        temperature=0.6,
        max_tokens=512
    )

# ----------------------------
# UI Layout
# ----------------------------
# Sidebar
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/5/59/GlaxoSmithKline_logo.svg", width=160)
    st.subheader("📊 Filters")
    segment = st.selectbox("HCP Segment", ["All", "High Potential", "Medium", "Low"])
    specialty = st.multiselect("Specialty", ["GP", "Dermatologist", "Cardiologist", "Other"])

# Header
st.markdown(
    "<div class='title-box'><h1>💡 AI Sales Call Assistant</h1><p>Guided by GSK Sales Call Flow & APACT</p></div>",
    unsafe_allow_html=True
)

# PDF Upload above chat
uploaded_file = st.file_uploader("📄 Upload PDF (Medical Reference)", type=["pdf"])
if uploaded_file is not None:
    pdf_text = extract_pdf_text(uploaded_file)
    st.session_state.uploaded_pdf_text = pdf_text
    st.session_state.pdf_summary = summarize_text(pdf_text)
    st.success("✅ PDF uploaded and summarized")

if st.session_state.pdf_summary:
    st.write("### 📌 PDF Summary")
    st.write(st.session_state.pdf_summary)

# Chat History
st.subheader("💬 Chatbot Interface")
for role, content in st.session_state.chat_history:
    if role == "user":
        st.markdown(f"<div class='chat-bubble-user'>{content}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='chat-bubble-ai'>{content}</div>", unsafe_allow_html=True)

# ----------------------------
# Bottom bar with input + buttons
# ----------------------------
st.markdown("<div class='bottom-bar'>", unsafe_allow_html=True)
with st.container():
    user_input = st.text_input("💬 Type your question...", key="user_input", label_visibility="collapsed")
    col1, col2, col3 = st.columns([1,1,1])
    with col1:
        if st.button("Send"):
            if user_input.strip():
                st.session_state.chat_history.append(("user", user_input))
                messages = [{"role": "system", "content": "You are an AI sales assistant using APACT (Acknowledge, Probe, Address, Confirm, Transition) within GSK's call flow."}]
                if st.session_state.uploaded_pdf_text:
                    messages.append({"role": "system", "content": "Use this reference:\n" + st.session_state.uploaded_pdf_text[:2000]})
                for role, content in st.session_state.chat_history:
                    messages.append({"role": role, "content": content})

                resp = groq_chat_completion(messages)
                ai_reply = resp.choices[0].message.content
                st.session_state.chat_history.append(("assistant", ai_reply))

                # TTS playback
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                audio_file = loop.run_until_complete(synthesize_speech(ai_reply, lang="en"))
                play_audio(audio_file)

    with col2:
        if st.button("🗑️ Clear Chat", key="clear"):
            st.session_state.chat_history = []
    with col3:
        if st.button("📥 Download Chat", key="download"):
            chat_text = "\n".join([f"{r.upper()}: {c}" for r,c in st.session_state.chat_history])
            b64 = base64.b64encode(chat_text.encode()).decode()
            href = f'<a href="data:text/plain;base64,{b64}" download="chat_history.txt">Download TXT</a>'
            st.markdown(href, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)
