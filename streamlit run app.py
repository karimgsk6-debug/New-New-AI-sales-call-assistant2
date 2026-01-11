import streamlit as st
import os, re, tempfile, base64, io
from html import escape
from datetime import datetime

# =============================
# OPTIONAL IMPORTS
# =============================
try:
    from groq import Groq
except:
    Groq = None

try:
    from PyPDF2 import PdfReader
except:
    PdfReader = None

try:
    from gtts import gTTS
except:
    gTTS = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except:
    SKLEARN_AVAILABLE = False

# =============================
# PAGE CONFIG
# =============================
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =============================
# SESSION INIT
# =============================
defaults = {
    "chat_history": [],
    "roleplay_history": [],
    "main_input": "",
    "selected_brand": "shingrix",
    "persona": "Skeptical Specialist",
    "tone": "consultative",
    "barrier": [],
    "specialty": "",
    "temperature": 0.4,
    "language": "English",
    "audio_enabled": False,
    "live_roleplay": False,
    "current_step": "Engage",
    "uploaded_pdf_text": "",
    "pdf_summary": ""
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# =============================
# GROQ CLIENT
# =============================
def load_groq():
    key = os.getenv("GROQ_API_KEY", "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")
    if not key or Groq is None:
        return None
    return Groq(api_key=key)

# =============================
# BRAND CONFIG
# =============================
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "call_flow": ["Prepare", "Engage", "Create Opportunities", "Influence", "Impact GSO", "Analyze"],
        "personas": ["Skeptical Specialist", "Committed Vaccinator", "Time-Pressured"],
        "barriers": ["Efficacy doubts", "Safety concerns", "Cost", "No time"],
        "specialties": ["GP", "IM", "Rheumatology"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/"
    }
}

bconf = brand_data[st.session_state.selected_brand]

# =============================
# UTILS
# =============================
def clean_text(t):
    return re.sub(r"\s+", " ", "".join(c if c.isprintable() else " " for c in t)).strip()

def read_pdf(file):
    if not PdfReader:
        return ""
    reader = PdfReader(file)
    return " ".join(p.extract_text() or "" for p in reader.pages)

def summarize(text):
    client = load_groq()
    if not client or not text:
        return text[:500]
    resp = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": f"Summarize in 5 bullets:\n{text[:8000]}"}],
        temperature=0.2,
        max_tokens=400
    )
    return clean_text(resp.choices[0].message.content)

def audio(text):
    if not gTTS or not text:
        return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    gTTS(text=text, lang="en").save(tmp.name)
    with open(tmp.name, "rb") as f:
        return base64.b64encode(f.read()).decode()

# =============================
# AI COACH (NON ROLE-PLAY)
# =============================
def generate_ai_response(prompt):
    client = load_groq()
    if not client:
        return "Groq unavailable."

    system = f"""
You are a senior pharma sales trainer.

For EACH call step generate:
- Objective
- Exact wording
- 3 micro-actions
- Success indicator

Brand: {bconf['display']}
Persona: {st.session_state.persona}
Tone: {st.session_state.tone}
Barriers: {", ".join(st.session_state.barrier)}
Steps: {", ".join(bconf['call_flow'])}

NO placeholders. NO generic advice.
"""

    resp = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        temperature=st.session_state.temperature,
        max_tokens=1500
    )

    text = clean_text(resp.choices[0].message.content)
    blocks = re.split(r"\n(?=[A-Z][A-Za-z ]+:)", text)

    html = ""
    for b in blocks:
        lines = b.split("\n")
        html += f"<div class='step-title'>{escape(lines[0])}</div><ul>"
        for l in lines[1:]:
            html += f"<li>{escape(l)}</li>"
        html += "</ul>"
    return html

# =============================
# 🎤 LIVE ROLE-PLAY ENGINE
# =============================
def roleplay_response(rep_text):
    client = load_groq()
    history = "\n".join(
        f"{m['role']}: {m['content']}"
        for m in st.session_state.roleplay_history[-6:]
    )

    system = f"""
You are a REAL doctor in a live sales call.

Rules:
- You are the HCP
- Be busy, realistic, sometimes resistant
- Respond naturally (1–3 short paragraphs)
- No coaching explanations

Context:
Brand: {bconf['display']}
Persona: {st.session_state.persona}
Barriers: {", ".join(st.session_state.barrier)}
Step: {st.session_state.current_step}

Conversation:
{history}
"""

    resp = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": rep_text}
        ],
        temperature=0.6,
        max_tokens=400
    )

    return clean_text(resp.choices[0].message.content)

# =============================
# SIDEBAR
# =============================
with st.sidebar:
    st.header("⚙️ Configuration")

    st.session_state.live_roleplay = st.toggle("🎤 Live Role-Play Mode")

    st.session_state.persona = st.selectbox("Persona", bconf["personas"])
    st.session_state.current_step = st.selectbox("Call Step", bconf["call_flow"])
    st.session_state.barrier = st.multiselect("Barriers", bconf["barriers"])
    st.session_state.tone = st.selectbox("Tone", ["consultative","confident","clinical"])
    st.session_state.audio_enabled = st.checkbox("🔊 Audio")

    if st.button("🗑️ Reset"):
        st.session_state.chat_history = []
        st.session_state.roleplay_history = []
        st.experimental_rerun()

# =============================
# UI
# =============================
st.title("🤖 AI Sales Call Assistant")

# -------- ROLE PLAY MODE --------
if st.session_state.live_roleplay:
    st.info("You are the **Sales Rep**. AI is the **Doctor**.")

    for m in st.session_state.roleplay_history:
        label = "🧑‍💼 You" if m["role"] == "rep" else "🩺 Doctor"
        st.markdown(f"**{label}:** {escape(m['content'])}")

    rep_input = st.text_input("What do you say?")
    if st.button("Send") and rep_input:
        st.session_state.roleplay_history.append({"role":"rep","content":rep_input})
        reply = roleplay_response(rep_input)
        st.session_state.roleplay_history.append({"role":"hcp","content":reply})

        if st.session_state.audio_enabled:
            a = audio(reply)
            if a:
                st.audio(io.BytesIO(base64.b64decode(a)), format="audio/mp3")

        st.experimental_rerun()

# -------- COACH MODE --------
else:
    with st.form("chat"):
        user_input = st.text_area("Describe the situation or objection", height=80)
        submitted = st.form_submit_button("Generate Coaching")

    if submitted and user_input:
        st.session_state.chat_history.append({"role":"user","content":user_input})
        resp = generate_ai_response(user_input)
        st.session_state.chat_history.append({"role":"ai","content":resp})
        st.experimental_rerun()

    for c in st.session_state.chat_history:
        if c["role"] == "user":
            st.markdown(f"<div class='chat-bubble-user'>{escape(c['content'])}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='chat-bubble-ai'>{c['content']}</div>", unsafe_allow_html=True)

st.markdown("<small>For internal sales training only.</small>", unsafe_allow_html=True)
