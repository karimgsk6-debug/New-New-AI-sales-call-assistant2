# ==========================================================
# AI SALES CALL ASSISTANT – ENTERPRISE VERSION
# ==========================================================
import streamlit as st
import os, base64, io
from groq import Groq
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from gtts import gTTS

# ==========================================================
# PAGE CONFIG
# ==========================================================
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ==========================================================
# GROQ CLIENT
# ==========================================================
client = Groq(api_key=os.getenv("GROQ_API_KEY","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"))

# ==========================================================
# ADMIN CONTROLS
# ==========================================================
AURA_LOGO_WIDTH = 130
GSK_LOGO_WIDTH = 120

# ==========================================================
# VISUAL ASSETS
# ==========================================================
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"
GSK_LOGO_PATH = ".devcontainer/Visuals/GSK-logo.png"
AURA_LOGO_PATH = ".devcontainer/Visuals/AURA.png"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

def image_to_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

GSK_LOGO = image_to_base64(GSK_LOGO_PATH)
AURA_LOGO = image_to_base64(AURA_LOGO_PATH)

# ==========================================================
# BACKGROUND
# ==========================================================
def set_background(image_path):
    if os.path.exists(image_path):
        with open(image_path,"rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background: url("data:image/png;base64,{encoded}");
            background-size: cover;
        }}
        </style>
        """, unsafe_allow_html=True)

set_background(BACKGROUND_PATH)

# ==========================================================
# CSS
# ==========================================================
st.markdown("""
<style>
.user-box {background:#f2f2f2; padding:12px; border-radius:12px; margin-bottom:6px;}
.ai-box {background:white; padding:16px; border-radius:16px; border:1px solid #ddd; margin-bottom:6px;}
.citation-box {background:white; padding:16px; border-radius:16px; border:1px solid #ddd;}
.avatar {width:60px; border-radius:50%; margin-bottom:8px;}
.title-container {display:flex; align-items:center; justify-content:space-between;}
.fixed-prompt-bar {
    position: fixed;
    bottom: 70px;
    left: 0;
    right: 0;
    padding: 10px 24px;
    background: rgba(255,255,255,0.97);
    border-top: 1px solid #ddd;
    z-index: 999;
    display: flex;
    gap: 10px;
    justify-content: center;
}
.fixed-prompt-bar button {
    border-radius: 20px;
    padding: 6px 14px;
    background: #f0f8ff;
    border: 1px solid #cce;
    font-size: 14px;
}
.voice-box {background:white; padding:12px; border-radius:12px; border:1px solid #ddd; margin-top:6px;}
</style>
""", unsafe_allow_html=True)

# ==========================================================
# BRAND DATA
# ==========================================================
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "references_path": ".devcontainer/references/shingrix/",
        "call_flow": ["Prepare","Engage","Create Opportunity","Influence","Impact GSO","Post-Call Review"],
        "prompts":[
            "Generate Shingrix vaccination call flow",
            "Handle HZ risk perception objection",
            "Explain Shingrix safety profile",
            "Build patient education pitch"
        ]
    },
    "jemperli": {
        "display": "Jemperli",
        "references_path": ".devcontainer/references/jemperli/",
        "call_flow": ["COCO Framework","Scientific Anchor","Eligibility Confirmation","Clinical Confidence","Access Alignment"],
        "prompts":[
            "COCO framework sales call",
            "Eligibility confirmation flow",
            "IO safety discussion guide",
            "Access & reimbursement objection handling"
        ]
    },
    "trelegy": {
        "display": "Trelegy",
        "references_path": ".devcontainer/references/trelegy/",
        "call_flow": ["Prepare","Engage","Demonstrate Value","Address Access","Close & Commit"],
        "prompts":[
            "COPD adoption flow",
            "ICS safety objection handling",
            "Formulary restriction strategy",
            "Inhaler technique education flow"
        ]
    }
}

# ==========================================================
# SESSION STATE
# ==========================================================
st.session_state.setdefault("chat", [])
st.session_state.setdefault("citations", [])
st.session_state.setdefault("selected_citation", None)
st.session_state.setdefault("input_text", "")
st.session_state.setdefault("last_audio", None)
st.session_state.setdefault("tts_speed", 1.0)

# ==========================================================
# SIDEBAR
# ==========================================================
st.sidebar.header("🎯 Configuration")
brand_key = st.sidebar.selectbox("Brand", list(brand_data.keys()), format_func=lambda x: brand_data[x]["display"])
brand = brand_data[brand_key]

# ==========================================================
# TITLE
# ==========================================================
st.markdown(f"""
<div class='title-container'>
    <img src='data:image/png;base64,{AURA_LOGO}' style='width:{AURA_LOGO_WIDTH}px;'>
    <h1>🧠 AI Sales Call Assistant</h1>
    <img src='data:image/png;base64,{GSK_LOGO}' style='width:{GSK_LOGO_WIDTH}px;'>
</div>
""", unsafe_allow_html=True)

# ==========================================================
# RAG
# ==========================================================
@st.cache_data
def load_guidelines(path):
    pages=[]
    if os.path.exists(path):
        for f in os.listdir(path):
            if f.endswith(".pdf"):
                reader=PdfReader(os.path.join(path,f))
                for i,p in enumerate(reader.pages):
                    t=p.extract_text()
                    if t:
                        pages.append({"source":f,"page":i+1,"text":t})
    return pages

def retrieve_pages(q,pages,k=3):
    corpus=[p["text"] for p in pages]
    tfidf=TfidfVectorizer(stop_words="english").fit_transform(corpus+[q])
    scores=cosine_similarity(tfidf[-1],tfidf[:-1]).flatten()
    idx=scores.argsort()[-k:][::-1]
    return [pages[i] for i in idx]

# ==========================================================
# CHAT UI
# ==========================================================
st.markdown("### 💬 Sales Conversation")

for msg in st.session_state.chat:
    if msg["role"]=="user":
        st.markdown(f"<div class='user-box'>{msg['content']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='ai-box'><img src='{AI_AVATAR}' class='avatar'><br>{msg['content']}</div>", unsafe_allow_html=True)

# ================= Voice Player =================
if st.session_state.last_audio:
    st.markdown("### 🔊 Voice")
    st.markdown("<div class='voice-box'>", unsafe_allow_html=True)
    st.audio(st.session_state.last_audio, format="audio/mp3")

    colv1,colv2,colv3 = st.columns([1,1,2])
    with colv1:
        if st.button("🔁 Replay Voice"):
            st.audio(st.session_state.last_audio, format="audio/mp3")
    with colv2:
        speed = st.selectbox("Speed", ["0.8x","1.0x","1.2x"])
        st.session_state.tts_speed = float(speed.replace("x",""))
    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================================
# INPUT
# ==========================================================
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Ask or generate a sales call…", value=st.session_state.input_text)
    submit = st.form_submit_button("Generate")

    if submit and user_input:
        pages = load_guidelines(brand["references_path"])
        retrieved = retrieve_pages(user_input, pages)
        st.session_state.chat.append({"role":"user","content":user_input})

        citations_text="\n".join(f"[{p['source']} p.{p['page']}]\n{p['text'][:800]}" for p in retrieved)

        prompt=f"""
STRICT COMPLIANCE:
Use only approved guidelines.
Follow sales call flow: {', '.join(brand['call_flow'])}

GUIDELINES:
{citations_text}

QUESTION:
{user_input}
"""

        response=client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role":"system","content":"You are a compliant pharmaceutical sales AI."},
                {"role":"user","content":prompt}
            ],
            temperature=0.2
        )

        answer=response.choices[0].message.content
        st.session_state.chat.append({"role":"ai","content":answer})

        # ============ TTS ============
        tts = gTTS(text=answer, lang='en', slow=False)
        audio_bytes = io.BytesIO()
        tts.write_to_fp(audio_bytes)
        st.session_state.last_audio = audio_bytes.getvalue()

        st.session_state.input_text = ""

# ==========================================================
# FIXED CONTEXT-AWARE PROMPT BAR
# ==========================================================
st.markdown("""<div class="fixed-prompt-bar">""", unsafe_allow_html=True)

cols = st.columns(len(brand["prompts"]))
for i,p in enumerate(brand["prompts"]):
    with cols[i]:
        if st.button(p, key=f"ctx_prompt_{i}"):
            st.session_state.input_text = p

st.markdown("</div>", unsafe_allow_html=True)
