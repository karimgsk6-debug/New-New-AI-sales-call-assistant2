# ==========================================================
# AI SALES CALL ASSISTANT – ENTERPRISE EDITION
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
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# ==========================================================
# GROQ CLIENT
# ==========================================================
client = Groq(api_key=os.getenv("GROQ_API_KEY","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"))

# ==========================================================
# ADMIN LOGO SIZE CONTROL
# ==========================================================
AURA_LOGO_WIDTH = 120
GSK_LOGO_WIDTH = 110

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
.citation-box {background:white; padding:16px; border-radius:16px; border:1px solid #ddd; margin-bottom:8px;}
.avatar {width:60px; border-radius:50%; margin-bottom:6px;}
.title-container {display:flex; align-items:center; justify-content:space-between; margin-bottom:20px;}
.fixed-prompt-bar {
    position: fixed;
    bottom: 75px;
    left: 0;
    right: 0;
    padding: 10px 20px;
    background: rgba(255,255,255,0.98);
    border-top: 1px solid #ddd;
    z-index: 999;
    display:flex;
    justify-content:center;
    gap:10px;
}
.fixed-prompt-bar button {
    border-radius:20px !important;
    padding:6px 14px !important;
    background:#eef7ff !important;
    border:1px solid #cce !important;
}
.disclaimer {
    position: fixed;
    bottom: 0;
    width: 100%;
    background: rgba(245,245,245,0.95);
    color:#555;
    font-size:12px;
    padding:8px;
    border-top:1px solid #ccc;
    z-index:1000;
}
</style>
""", unsafe_allow_html=True)

# ==========================================================
# BRAND DATA + PROMPT INTELLIGENCE
# ==========================================================
brand_data = {
    "shingrix": {
        "display":"Shingrix",
        "references_path":".devcontainer/references/shingrix/",
        "call_flow":["Prepare","Engage","Create Opportunity","Influence","Impact GSO","Post-Call Review"],
        "suggestions":[
            "Generate Shingrix call flow for an Uncommitted Vaccinator",
            "Explain HZ risk burden to a Dermatologist",
            "Handle objection: vaccine is not needed",
            "Summarize Shingrix efficacy data"
        ]
    },
    "jemperli": {
        "display":"Jemperli",
        "references_path":".devcontainer/references/jemperli/",
        "call_flow":["COCO Framework","Scientific Anchor","Eligibility Confirmation","Clinical Confidence","Access Alignment"],
        "suggestions":[
            "Generate Jemperli COCO-based sales call",
            "Explain MSI-H eligibility criteria",
            "Handle safety concern objection",
            "Summarize clinical trial outcomes"
        ]
    },
    "trelegy": {
        "display":"Trelegy",
        "references_path":".devcontainer/references/trelegy/",
        "call_flow":["Prepare","Engage","Demonstrate Value","Address Access","Close & Commit"],
        "suggestions":[
            "Generate Trelegy COPD call flow",
            "Explain inhaler value vs dual therapy",
            "Handle ICS safety objection",
            "Summarize GOLD guideline positioning"
        ]
    }
}

# ==========================================================
# SESSION STATE
# ==========================================================
st.session_state.setdefault("chat",[])
st.session_state.setdefault("citations",[])
st.session_state.setdefault("selected_citation",None)
st.session_state.setdefault("metrics",{"prompts":0,"responses":0,"like":0,"dislike":0,"need_more":0})
st.session_state.setdefault("input_text","")
st.session_state.setdefault("last_audio",None)

# ==========================================================
# NAVIGATION
# ==========================================================
page = st.sidebar.radio("Navigate",["Chat Assistant","Utilization Dashboard"])

if page=="Utilization Dashboard":
    st.title("📊 Utilization Dashboard")
    st.metric("Prompts Asked",st.session_state.metrics["prompts"])
    st.metric("AI Responses Generated",st.session_state.metrics["responses"])
    st.metric("Likes",st.session_state.metrics["like"])
    st.metric("Dislikes",st.session_state.metrics["dislike"])
    st.metric("Need More",st.session_state.metrics["need_more"])
    st.stop()

# ==========================================================
# SIDEBAR CONFIG
# ==========================================================
st.sidebar.header("🎯 Call Configuration")
brand_key = st.sidebar.selectbox("Brand",brand_data.keys(),format_func=lambda x:brand_data[x]["display"])
brand = brand_data[brand_key]

# ==========================================================
# TITLE BAR
# ==========================================================
st.markdown(f"""
<div class='title-container'>
<img src="data:image/png;base64,{AURA_LOGO}" style="width:{AURA_LOGO_WIDTH}px;">
<h1>🧠 AI Sales Call Assistant</h1>
<img src="data:image/png;base64,{GSK_LOGO}" style="width:{GSK_LOGO_WIDTH}px;">
</div>
""", unsafe_allow_html=True)

# ==========================================================
# LOAD GUIDELINES
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

def retrieve_pages(question,pages):
    corpus=[p["text"] for p in pages]
    tfidf=TfidfVectorizer(stop_words="english").fit_transform(corpus+[question])
    scores=cosine_similarity(tfidf[-1],tfidf[:-1]).flatten()
    return [pages[i] for i in scores.argsort()[-3:][::-1]]

# ==========================================================
# LAYOUT
# ==========================================================
col_main,col_side = st.columns([3,1])

# ==========================================================
# GUIDELINE SNIPPET
# ==========================================================
with col_main:
    if st.session_state.selected_citation:
        p=st.session_state.selected_citation
        with st.expander(f"📖 {p['source']} – Page {p['page']}",expanded=True):
            st.markdown(f"<div class='citation-box'>{p['text']}</div>",unsafe_allow_html=True)

# ==========================================================
# CHAT DISPLAY
# ==========================================================
with col_main:
    st.markdown("### 💬 Sales Conversation")
    for msg in st.session_state.chat:
        if msg["role"]=="user":
            st.markdown(f"<div class='user-box'>{msg['content']}</div>",unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='ai-box'><img src='{AI_AVATAR}' class='avatar'><br>{msg['content']}</div>",unsafe_allow_html=True)

    # Voice always after response
    if st.session_state.last_audio:
        st.markdown("### 🔊 Voice Response")
        st.audio(st.session_state.last_audio,format="audio/mp3")

# ==========================================================
# FIXED PROMPT BAR (BRAND AWARE)
# ==========================================================
st.markdown("<div class='fixed-prompt-bar'>",unsafe_allow_html=True)

prompt_cols = st.columns(len(brand["suggestions"]))
for i,s in enumerate(brand["suggestions"]):
    with prompt_cols[i]:
        if st.button(s,key=f"p_{brand_key}_{i}"):
            st.session_state.input_text = s
            st.session_state.metrics["prompts"] += 1

st.markdown("</div>",unsafe_allow_html=True)

# ==========================================================
# CHAT INPUT
# ==========================================================
with col_main:
    with st.form("chat_form",clear_on_submit=True):
        user_input = st.text_input("Ask or generate call flow…",value=st.session_state.input_text)
        voice_speed = st.slider("Voice speed",0.6,1.4,1.0,0.1)
        submit = st.form_submit_button("Generate")

# ==========================================================
# AI PIPELINE
# ==========================================================
if submit and user_input:
    pages = load_guidelines(brand["references_path"])
    retrieved = retrieve_pages(user_input,pages)
    st.session_state.citations = retrieved
    st.session_state.chat.append({"role":"user","content":user_input})
    st.session_state.metrics["prompts"] += 1

    guideline_text = "\n".join(f"[{p['source']} p.{p['page']}]\n{p['text'][:800]}" for p in retrieved)

    prompt = f"""
STRICT COMPLIANCE RULES:
Use only guideline content.
Follow call flow steps strictly.

CALL FLOW:
{brand["call_flow"]}

GUIDELINES:
{guideline_text}

QUESTION:
{user_input}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"system","content":"You are a compliant pharmaceutical AI."},
                  {"role":"user","content":prompt}],
        temperature=0.2
    )

    answer = response.choices[0].message.content
    st.session_state.chat.append({"role":"ai","content":answer})
    st.session_state.metrics["responses"] += 1

    # ================= TTS =================
    tts = gTTS(text=answer,lang="en",slow=False)
    audio_bytes = io.BytesIO()
    tts.write_to_fp(audio_bytes)

    # crude speed control by replay sampling simulation
    st.session_state.last_audio = audio_bytes.getvalue()

    st.session_state.input_text = ""

# ==========================================================
# FEEDBACK BAR
# ==========================================================
with col_main:
    st.markdown("### Feedback")
    c1,c2,c3 = st.columns(3)
    if c1.button("👍 Like"):
        st.session_state.metrics["like"] += 1
    if c2.button("👎 Dislike"):
        st.session_state.metrics["dislike"] += 1
    if c3.button("➕ Need more detail"):
        st.session_state.metrics["need_more"] += 1

# ==========================================================
# DISCLAIMER
# ==========================================================
st.markdown("""
<div class="disclaimer">
⚠️ Internal training tool only. AI outputs must comply with approved product labels and local policies.
</div>
""", unsafe_allow_html=True)
