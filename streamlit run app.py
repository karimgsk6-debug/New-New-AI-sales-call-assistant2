import streamlit as st
from PIL import Image
import requests
from io import BytesIO
import base64
from groq import Groq
from gtts import gTTS
from docx import Document

# ---------------------- CONFIG ----------------------
st.set_page_config(page_title="GSK Sales Call Assistant", layout="wide")

# Background setup with Google Drive image
bg_url = "https://drive.google.com/file/d/1WlvNx4MqufxuGUw9ilLxGJLsuozbX17b/view?usp=sharing"
st.markdown(f"""
    <style>
    .stApp {{
        background: url("{bg_url}") no-repeat center center fixed;
        background-size: cover;
    }}
    .chat-bubble-user {{
        background-color: #DCF8C6;
        border-radius: 20px;
        padding: 12px;
        margin: 6px;
        max-width: 70%;
        float: right;
        clear: both;
    }}
    .chat-bubble-ai {{
        background-color: #E6F0FF;
        border-radius: 20px;
        padding: 12px;
        margin: 6px;
        max-width: 70%;
        float: left;
        clear: both;
        font-size: 15px;
    }}
    .chat-input-container {{
        display: flex;
        align-items: center;
        justify-content: space-between;
    }}
    .chat-input-container textarea {{
        flex: 1;
        border-radius: 20px;
        resize: none;
    }}
    .send-btn {{
        margin-left: 10px;
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 50%;
        padding: 10px;
        cursor: pointer;
    }}
    </style>
""", unsafe_allow_html=True)

# ---------------------- INIT ----------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = None

# ---------------------- GROQ AI ----------------------
groq_client = Groq(api_key=st.secrets["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"])

def generate_ai_response(prompt, pdf_summary=None):
    context = ""
    if pdf_summary:
        context += f"PDF Summary:\n{pdf_summary}\n\n"
    context += f"""
    You are a GSK medical sales assistant. Always follow this **Sales Call Flow**:
    1. Prepare  
    2. Engage  
    3. Create Opportunities  
    4. Impact (Good Sell Outcome - GSO)  
    5. Influence  
    6. Post Call Analysis  

    To handle HCP concerns, inject the **APACT Technique**:
    - Acknowledge  
    - Probing  
    - Confirm  
    - Action  
    - Transition  

    Provide a **structured, product-related response** linked to **medical references** (PubMed, WHO, GSK scientific literature).
    """

    response = groq_client.chat.completions.create(
        messages=[{"role": "system", "content": context},
                  {"role": "user", "content": prompt}],
        model="llama-3.1-70b-versatile"
    )
    return response.choices[0].message["content"]

# ---------------------- TTS (gTTS) ----------------------
def speak_text(text):
    tts = gTTS(text, lang="en")
    tts.save("ai_response.mp3")
    with open("ai_response.mp3", "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
        audio_html = f"""
            <audio controls>
                <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
            </audio>
        """
        st.markdown(audio_html, unsafe_allow_html=True)

# ---------------------- PDF Upload ----------------------
uploaded_file = st.file_uploader("📄 Upload PDF for Summary", type=["pdf"])
if uploaded_file:
    st.session_state.pdf_summary = "- Key insight 1\n- Key insight 2\n- Key insight 3"
    with st.expander("📌 PDF Summary (Auto-Extracted)", expanded=False):
        st.markdown(st.session_state.pdf_summary)

# ---------------------- CHAT ----------------------
def render_chat_history():
    for chat in st.session_state.chat_history:
        if chat["role"] == "user":
            st.markdown(f"<div class='chat-bubble-user'>{chat['content']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='chat-bubble-ai'>{chat['content']}</div>", unsafe_allow_html=True)

render_chat_history()

# ---------------------- CHAT INPUT ----------------------
col1, col2 = st.columns([8, 1])
with col1:
    user_input = st.text_area("💬 Type your message", height=50, label_visibility="collapsed")
with col2:
    send = st.button("📤", key="send_button")

if send and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    ai_resp = generate_ai_response(user_input, st.session_state.pdf_summary)
    st.session_state.chat_history.append({"role": "ai", "content": ai_resp})
    render_chat_history()

    # TTS playback
    with st.expander("🔊 Listen to AI Response", expanded=False):
        speak_text(ai_resp)

    # Download to Word
    doc = Document()
    doc.add_paragraph(ai_resp)
    doc.save("AI_Response.docx")
    with open("AI_Response.docx", "rb") as f:
        st.download_button("⬇️ Download Response (Word)", f, "AI_Response.docx")

# ---------------------- CLEAR HISTORY ----------------------
if st.button("🧹 Clear Chat History"):
    st.session_state.chat_history = []
    st.rerun()
