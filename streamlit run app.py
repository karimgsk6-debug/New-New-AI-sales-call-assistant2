import streamlit as st
import base64
import os
from gtts import gTTS
import tempfile
import PyPDF2
import requests
from io import BytesIO

# -------------------- PAGE CONFIG --------------------
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide"
)

# -------------------- BACKGROUND IMAGE --------------------
def set_bg_from_url(url):
    page_bg_img = f"""
    <style>
    .stApp {{
        background-image: url("{url}");
        background-size: cover;
        background-position: center center;
        background-repeat: no-repeat;
        background-attachment: fixed;
        transition: all 0.3s ease-in-out;
    }}
    [data-testid="stSidebar"] {{
        background-color: rgba(255, 255, 255, 0.8) !important;  /* semi-transparent white */
        border-right: 1px solid #e0e0e0;
    }}
    </style>
    """
    st.markdown(page_bg_img, unsafe_allow_html=True)

# Use the provided background image
bg_url = "https://sdmntprnortheu.oaiusercontent.com/files/00000000-7268-61f4-9aa6-71a39056c20e/raw?se=2025-09-25T15%3A42%3A47Z&sp=r&sv=2024-08-04&sr=b&scid=dfa0d35f-01ac-5224-bec7-ff9f505758dd&skoid=b32d65cd-c8f1-46fb-90df-c208671889d4&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-25T09%3A41%3A15Z&ske=2025-09-26T09%3A41%3A15Z&sks=b&skv=2024-08-04&sig=ap%2BO7ty9YJurxH528T8cPoSQD5Kh6VHdsvf/nvdkbjs%3D"
set_bg_from_url(bg_url)

# -------------------- SIDEBAR --------------------
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/5/5a/GlaxoSmithKline_logo.svg", use_column_width=True)
st.sidebar.markdown("### Filters")

with st.sidebar.expander("📂 Segmentation Filters", expanded=True):
    st.markdown(
        """
        <style>
        .sidebar-content {
            border: 1px solid #ccc;
            border-radius: 8px;
            padding: 8px;
            margin-bottom: 10px;
            background-color: #fafafa;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    st.markdown('<div class="sidebar-content">Specialty Filter</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-content">Region Filter</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-content">Potential Filter</div>', unsafe_allow_html=True)

# -------------------- MAIN LAYOUT --------------------
st.title("💊 AI Sales Call Assistant (APACT + GSK Flow)")

# -------- PDF UPLOAD + SUMMARIZE --------
st.subheader("📑 Upload and Summarize PDF")
uploaded_pdf = st.file_uploader("Upload a PDF", type="pdf")

if uploaded_pdf:
    pdf_reader = PyPDF2.PdfReader(uploaded_pdf)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() or ""
    st.text_area("Extracted PDF Content", text[:2000] + "...", height=200)
    if st.button("Summarize PDF"):
        st.success("✅ PDF summarized (mock response).")

# -------- CHAT INTERFACE --------
st.subheader("💬 Chatbot Interface")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

user_input = st.text_area("Type your question here...", height=100)

col1, col2, col3 = st.columns([1,1,1])
with col1:
    if st.button("Send"):
        if user_input.strip():
            st.session_state.chat_history.append(("user", user_input))
            ai_response = f"AI response to: {user_input}\n\n(Using GSK APACT model)"
            st.session_state.chat_history.append(("ai", ai_response))
with col2:
    if st.button("Clear Chat"):
        st.session_state.chat_history = []
with col3:
    if st.button("Download Chat"):
        chat_text = "\n".join([f"{role}: {msg}" for role, msg in st.session_state.chat_history])
        b64 = base64.b64encode(chat_text.encode()).decode()
        href = f'<a href="data:file/txt;base64,{b64}" download="chat_history.txt">Download</a>'
        st.markdown(href, unsafe_allow_html=True)

# -------- DISPLAY CHAT --------
for role, msg in st.session_state.chat_history:
    if role == "user":
        st.markdown(f"🧑‍💼 **You:** {msg}")
    else:
        st.markdown(f"🤖 **AI:** {msg}")

        # Generate TTS in English & Arabic (remove punctuation for smoother voice)
        try:
            clean_msg = msg.replace(".", "").replace(",", "").replace(";", "").replace(":", "")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmpfile:
                tts = gTTS(clean_msg, lang="en")
                tts.save(tmpfile.name)
                st.audio(tmpfile.name)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmpfile_ar:
                tts_ar = gTTS(clean_msg, lang="ar")
                tts_ar.save(tmpfile_ar.name)
                st.audio(tmpfile_ar.name)

        except Exception as e:
            st.warning(f"TTS error: {e}")
