import streamlit as st
from groq import Groq
import os
from gtts import gTTS
import base64
from io import BytesIO
import PyPDF2
import docx

# ----------------------------
# Config & API
# ----------------------------
st.set_page_config(page_title="AI Health Assistant", layout="centered")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
if not GROQ_API_KEY:
    st.warning("⚠️ Please set your GROQ_API_KEY environment variable.")
else:
    client = Groq(api_key=GROQ_API_KEY)

# ----------------------------
# Helper Functions
# ----------------------------
def text_to_speech(text, lang="en"):
    """Convert text to speech (AI reply)"""
    try:
        tts = gTTS(text=text, lang=lang)
        audio_fp = BytesIO()
        tts.write_to_fp(audio_fp)
        audio_fp.seek(0)
        audio_bytes = audio_fp.read()
        b64 = base64.b64encode(audio_bytes).decode()
        return f'<audio autoplay controls src="data:audio/mp3;base64,{b64}"></audio>'
    except Exception as e:
        return f"⚠️ TTS error: {e}"

def parse_file(uploaded_file):
    """Extract text from uploaded file"""
    if uploaded_file is None:
        return None
    if uploaded_file.name.endswith(".pdf"):
        reader = PyPDF2.PdfReader(uploaded_file)
        return " ".join([page.extract_text() for page in reader.pages if page.extract_text()])
    elif uploaded_file.name.endswith(".docx"):
        doc = docx.Document(uploaded_file)
        return " ".join([para.text for para in doc.paragraphs])
    elif uploaded_file.name.endswith(".txt"):
        return uploaded_file.read().decode("utf-8")
    return None

def ask_ai(prompt):
    """Send user prompt to Groq LLM"""
    try:
        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a medical AI assistant. Provide clear, evidence-based answers."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
        return response.choices[0].message["content"].strip()
    except Exception as e:
        return f"⚠️ AI error: {e}"

# ----------------------------
# UI
# ----------------------------
st.title("💬 AI Health Assistant")
st.caption("Powered by Groq | Includes CDC/WHO references | WhatsApp-style UI")

st.markdown(
    """
    **🔗 Medical References:**  
    - [CDC Health Topics](https://www.cdc.gov)  
    - [WHO Official Website](https://www.who.int)  
    """
)

# Session state for messages
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# File Upload
uploaded_file = st.file_uploader("📎 Upload a file (PDF, DOCX, TXT)", type=["pdf", "docx", "txt"])
if uploaded_file:
    file_text = parse_file(uploaded_file)
    if file_text:
        st.session_state["messages"].append({"role": "user", "content": file_text})

# Display messages (WhatsApp style)
for msg in st.session_state["messages"]:
    if msg["role"] == "user":
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;justify-content:flex-end;margin:5px;">
                <div style="background:#dcf8c6;padding:10px;border-radius:10px;max-width:70%;margin-left:5px;">
                    {msg['content']}
                </div>
                <div style="margin-left:5px;">👤</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:  # AI
        st.markdown(
            f"""
            <div style="display:flex;align-items:center;justify-content:flex-start;margin:5px;">
                <div style="margin-right:5px;">🤖</div>
                <div style="background:#ffffff;padding:10px;border-radius:10px;max-width:70%;box-shadow:0px 1px 2px rgba(0,0,0,0.1);">
                    {msg['content']}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(text_to_speech(msg["content"], lang="ar" if any("\u0600" <= c <= "\u06FF" for c in msg["content"]) else "en"), unsafe_allow_html=True)

# Input box like WhatsApp
st.markdown("---")
with st.form("chat_form", clear_on_submit=True):
    cols = st.columns([8, 1])
    user_input = cols[0].text_input("💬 Type your message...", placeholder="Message AI...", label_visibility="collapsed")
    submitted = cols[1].form_submit_button("📤")

if submitted and user_input:
    st.session_state["messages"].append({"role": "user", "content": user_input})
    ai_reply = ask_ai(user_input)
    st.session_state["messages"].append({"role": "assistant", "content": ai_reply})
    st.rerun()
