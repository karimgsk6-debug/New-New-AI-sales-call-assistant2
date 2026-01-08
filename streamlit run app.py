import streamlit as st
import os
import re
import tempfile
import base64
from datetime import datetime

# -------------------------
# Soft imports
# -------------------------
try:
    from groq import Groq
except Exception:
    Groq = None

try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

try:
    from gtts import gTTS
except Exception:
    gTTS = None

try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except Exception:
    ELEVENLABS_AVAILABLE = False

# -------------------------
# Session initialization
# -------------------------
def _init_session():
    defaults = {
        "chat_history": [],
        "main_input": "",
        "selected_brand": "shingrix",
        "temperature": 0.95,
        "search_mode": "deep",
        "medical_summary": "",
        "sales_summary": "",
        "uploaded_pdf_text": "",
        "pdf_summary": "",
        "feedback": {},
        "dislike_state": None,
        "language": "English",
        "prompt_suggestions": ["Handle objection", "Summarize key points", "Prepare sales script", "Follow-up strategy"],
        "persona": "Doctor",
        "objection": "",
        "audio_enabled": False
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

_init_session()

# -------------------------
# CSS styling
# -------------------------
st.markdown(
    """
    <style>
    .chat-bubble-user{ background: rgba(0,0,0,0.08); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }
    .chat-bubble-ai{ background: #ffffff; color:#000; padding:12px 16px; border-radius:12px; box-shadow: 0 1px 6px rgba(0,0,0,0.085); margin:8px 0; max-width:90%; white-space:pre-wrap; }
    .fixed-disclaimer{ font-size:12px; color:#444; margin-top:16px; opacity:0.9; }
    .prompt-suggestion{ display:inline-block; background:#f0f0f0; padding:4px 8px; margin:2px; border-radius:6px; cursor:pointer; font-size:13px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# Helpers
# -------------------------
def clean_text(text):
    if not text:
        return ""
    text = ''.join(c if c.isprintable() else ' ' for c in text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def read_pdf_text(path):
    if PdfReader is None or not os.path.exists(path):
        return ""
    try:
        reader = PdfReader(path)
        text = "".join([p.extract_text() or "" for p in reader.pages])
        return clean_text(text)
    except:
        return ""

def simple_summary(text, bullets=6):
    if not text:
        return ""
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- " + s for s in selected])

def load_groq_client():
    api_key = os.getenv("GROQ_API_KEY", "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") or (st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else "")
    if not api_key or Groq is None:
        return None
    try:
        return Groq(api_key=api_key)
    except:
        return None

def model_summarize(text, bullets=6):
    client = load_groq_client()
    if client:
        try:
            prompt = f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                                 messages=[{"role":"user","content":prompt}],
                                                 temperature=0.2)
            content = getattr(resp.choices[0].message, "content", None) or getattr(resp.choices[0], "text", "")
            return clean_text(content)
        except:
            return simple_summary(text, bullets)
    else:
        return simple_summary(text, bullets)

def generate_audio(text):
    text = clean_text(text)
    if not text:
        return ""
    if ELEVENLABS_AVAILABLE:
        try:
            elevenlabs.api_key = st.secrets.get("ELEVENLABS_API_KEY", "")
            audio_stream = elevenlabs.generate(text=text, voice="alloy", model="eleven_multilingual_v1", stream=True)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            with open(tmp.name, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
            with open(tmp.name, "rb") as fh:
                return base64.b64encode(fh.read()).decode()
        except:
            pass
    if gTTS:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            gTTS(text=text, lang="en", slow=False).save(tmp.name)
            with open(tmp.name, "rb") as fh:
                return base64.b64encode(fh.read()).decode()
        except:
            pass
    return ""

def generate_ai_response(user_msg, persona, objection, pdf_summary):
    # Placeholder for AI logic, integrate your model here (GROQ, OpenAI, etc.)
    response = f"**Persona:** {persona}\n"
    response += f"**Objection Handling:** {objection if objection else 'None'}\n\n"
    response += f"**User Message:** {user_msg}\n"
    if pdf_summary:
        response += f"\n**Reference Summary:**\n{pdf_summary}\n"
    response += "\n**Suggestions:**\n" + "\n".join([f"- {s}" for s in st.session_state.prompt_suggestions])
    return clean_text(response)

# -------------------------
# Sidebar
# -------------------------
st.sidebar.title("Dashboard")
st.sidebar.selectbox("Persona", ["Doctor", "Pharmacist", "Nurse"], key="persona")
st.sidebar.checkbox("Enable Audio", key="audio_enabled")
st.sidebar.markdown(f"**Selected Brand:** {st.session_state.selected_brand}")
st.sidebar.markdown(f"**Language:** {st.session_state.language}")

# -------------------------
# Prompt suggestions
# -------------------------
with st.expander("Prompt Suggestions", expanded=True):
    for i, p in enumerate(st.session_state.prompt_suggestions):
        if st.button(p, key=f"prompt_{i}"):
            st.session_state.main_input = p
            st.experimental_rerun()  # Trigger AI response immediately

# -------------------------
# Chat interface
# -------------------------
st.title("AI Sales Call Assistant")

uploaded_file = st.file_uploader("Upload PDF/Text for reference", type=["pdf","txt"])
if uploaded_file:
    if uploaded_file.type == "application/pdf":
        st.session_state.uploaded_pdf_text = read_pdf_text(uploaded_file)
    else:
        st.session_state.uploaded_pdf_text = clean_text(uploaded_file.getvalue().decode("utf-8", errors="ignore"))
    st.session_state.pdf_summary = model_summarize(st.session_state.uploaded_pdf_text)

user_input = st.text_area("Your Message", value=st.session_state.main_input, key="main_input", height=80)

if st.button("Send") or st.session_state.main_input in st.session_state.prompt_suggestions:
    user_msg = st.session_state.main_input
    ai_response = generate_ai_response(user_msg, st.session_state.persona, st.session_state.objection, st.session_state.pdf_summary)
    st.session_state.chat_history.append({"user": user_msg, "ai": ai_response})
    
    if st.session_state.audio_enabled:
        audio_b64 = generate_audio(ai_response)
        if audio_b64:
            st.audio(base64.b64decode(audio_b64))
    
    st.session_state.main_input = ""

# Display chat history
for chat in st.session_state.chat_history:
    st.markdown(f'<div class="chat-bubble-user">{chat["user"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="chat-bubble-ai">{chat["ai"]}</div>', unsafe_allow_html=True)

st.markdown("<div class='fixed-disclaimer'>Disclaimer: This AI tool is for sales simulation only.</div>", unsafe_allow_html=True)
