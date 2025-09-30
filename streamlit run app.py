import streamlit as st
from PIL import Image
from io import BytesIO
import requests
import re
import base64
import tempfile
from datetime import datetime
from docx import Document
from gtts import gTTS
from groq import Groq
import PyPDF2

# ---------------------- CONFIG ----------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------- STYLING ----------------------
BACKGROUND_URL = "https://www.shutterstock.com/image-photo/excited-girl-white-shirt-using-260nw-708132598.jpg"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png"

st.markdown(f"""
<style>
.title-box {{
    background: rgba(245,245,245,0.8);
    padding: 20px;
    border-radius: 12px;
    text-align: center;
    max-width: 95%;
    margin: 10px auto;
}}
.title-box h1 {{ margin:0; font-size:32px; font-weight:800; color:#000; }}
.title-box p {{ margin:6px 0 0 0; font-size:16px; color:#333; }}

.chat-container {{
    height: 60vh;
    overflow-y: auto;
    padding:12px;
    border-radius:10px;
    background: rgba(255,255,255,0.85);
}}

.chat-bubble-user {{ background-color:#DCF8C6; border-radius:20px; padding:12px; margin:6px; max-width:70%; float:right; clear:both; }}
.chat-bubble-ai {{ background-color:#fdfdf5; border-radius:20px; padding:12px; margin:6px; max-width:70%; float:left; clear:both; font-size:15px; }}

.pdf-summary-inline {{
    margin-top:8px;
    background: #fdfdf5; 
    padding:10px;
    border-radius:8px;
    border:1px solid #ccc;
}}
.pdf-summary-item {{
    margin-bottom:6px;
}}
.highlight {{
    background-color: #ffeb3b;
    font-weight:bold;
}}

.bottom-bar {{
    position: fixed;
    bottom:12px;
    left:16px;
    right:16px;
    z-index:1200;
    background: rgba(255,255,255,0.98);
    padding:10px;
    border-radius:12px;
    display:flex;
    gap:12px;
    align-items:center;
}}
.bottom-bar input[type="text"] {{
    flex:1;
    padding:10px 12px;
    border-radius:8px;
    border:1px solid #ddd;
}}
.bottom-bar button {{
    min-width:110px;
    padding:8px 12px;
    border-radius:8px;
    background:#ff8c00;
    color:white;
    border:none;
    font-weight:600;
    cursor:pointer;
}}
</style>
""", unsafe_allow_html=True)

# ---------------------- SESSION STATE ----------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = []
if "pdf_refs" not in st.session_state:
    st.session_state.pdf_refs = ""
if "voice_pref" not in st.session_state:
    st.session_state.voice_pref = "Male Neural"

# ---------------------- GROQ CLIENT ----------------------
GROQ_API_KEY = "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"
groq_client = Groq(api_key=GROQ_API_KEY)

# ---------------------- TITLE + LOGO ----------------------
st.markdown(f'<div class="title-box"><img src="{GSK_LOGO_URL}" width="140" /><h1>💡 GSK AI Sales Call Assistant</h1><p>Powered by AI to equip sales reps for smarter HCP conversations</p></div>', unsafe_allow_html=True)

# ---------------------- PDF UPLOAD ----------------------
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
if uploaded_pdf:
    reader = PyPDF2.PdfReader(uploaded_pdf)
    full_text = "".join([p.extract_text() or "" for p in reader.pages])
    matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
    st.session_state.pdf_refs = ", ".join(matches) if matches else "None"
    lines = [ln.strip() for ln in full_text.splitlines() if ln.strip()]
    st.session_state.pdf_summary = lines[:10]

# ---------------------- PDF SUMMARY DISPLAY ----------------------
if st.session_state.pdf_summary:
    search_term = st.text_input("🔍 Search PDF Summary", key="pdf_search")
    with st.expander("View PDF Summary", expanded=False):
        for item in st.session_state.pdf_summary:
            display_item = item
            if search_term:
                display_item = re.sub(f"({re.escape(search_term)})", r"<span class='highlight'>\1</span>", item, flags=re.I)
            if search_term.lower() in item.lower() or search_term == "":
                st.markdown(f"<div class='pdf-summary-item pdf-summary-inline'>- {display_item}</div>", unsafe_allow_html=True)
    with st.expander("📚 Extracted References", expanded=False):
        st.markdown(st.session_state.pdf_refs)

# ---------------------- HELPER FUNCTIONS ----------------------
def render_chat_history():
    html_out = ""
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            html_out += f"<div class='chat-bubble-user'>{msg['content']}</div>"
        else:
            audio_html = ""
            if msg.get("audio"):
                audio_html = f"<br><audio controls style='margin-top:8px;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
            html_out += f"<div class='chat-bubble-ai'>{msg['content']}{audio_html}</div>"
    st.markdown(f"<div class='chat-container' id='chat-container'>{html_out}</div>", unsafe_allow_html=True)
    # Auto-scroll JS
    st.markdown("""
    <script>
    var chatContainer = document.getElementById('chat-container');
    if(chatContainer){
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    </script>
    """, unsafe_allow_html=True)

def generate_ai_response(user_input: str) -> str:
    context = (
        "You are a GSK sales assistant. Follow Sales Call Flow: Prepare, Engage, Create Opportunities, "
        "Impact GSO, Influence, Post-call Analysis. Use APACT for objections. Provide structured responses and references."
    )
    if st.session_state.pdf_summary:
        context += "\nPDF Summary:\n" + "\n".join(st.session_state.pdf_summary)
    try:
        response = groq_client.chat.completions.create(
            messages=[{"role":"system","content":context},{"role":"user","content":user_input}],
            model="llama-3.3-70b-versatile"
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI Error: {e}"

def generate_tts(text: str) -> str:
    if not text:
        return None
    text_clean = re.sub(r'[.,?!]', '', text)
    tts = gTTS(text=text_clean, lang='en', tld='com', slow=False)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tts.save(tmp.name)
    with open(tmp.name,"rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode()
    return audio_b64

# ---------------------- CHAT INPUT (BOTTOM FIXED) ----------------------
st.markdown('<div class="bottom-bar">', unsafe_allow_html=True)
user_input = st.text_input("Type your message...", key="chat_input")
send_btn = st.button("Send")
st.markdown('</div>', unsafe_allow_html=True)

if send_btn and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input})
    ai_text = generate_ai_response(user_input)
    audio_b64 = generate_tts(ai_text)
    st.session_state.chat_history.append({"role":"ai","content":ai_text,"audio":audio_b64})

render_chat_history()

# ---------------------- EXPORT ----------------------
if st.session_state.chat_history:
    doc = Document()
    for msg in st.session_state.chat_history:
        role = "User" if msg["role"]=="user" else "AI"
        doc.add_paragraph(f"{role}: {msg['content']}")
    doc_path = "AI_Response.docx"
    doc.save(doc_path)
    with open(doc_path,"rb") as f:
        st.download_button("⬇️ Download Chat History (.docx)", f, "AI_Response.docx")
