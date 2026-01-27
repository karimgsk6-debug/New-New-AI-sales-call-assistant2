# ==========================================================
# AI SALES CALL ASSISTANT – FULL FEATURED MERGED VERSION
# ==========================================================

import streamlit as st
import os, base64, io
from groq import Groq
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from gtts import gTTS

# ==========================================================
# CONFIG
# ==========================================================
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🔐 GROQ API PLACEHOLDER
client = Groq(api_key=os.getenv("GROQ_API_KEY", "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"))

# ==========================================================
# ASSETS & LOGOS
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

def set_background(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as f:
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
.ai-box {background:white; padding:16px; border-radius:16px; border:1px solid #ddd;}
.citation-box {background:white; padding:16px; border-radius:16px; border:1px solid #ddd;}
.avatar {width:64px; border-radius:50%; margin-bottom:8px;}
.title-container {display:flex; align-items:center; justify-content:space-between;}
.prompt-bubble {background:#eef5ff; padding:12px; border-radius:16px;}
.disclaimer {position:fixed; bottom:0; width:100%; background:#f7f7f7; padding:8px; font-size:12px;}
.fixed-prompts {position:fixed; bottom:60px; width:65%; z-index:100;}
</style>
""", unsafe_allow_html=True)

# ==========================================================
# BRAND DATA
# ==========================================================
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas": ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers": ["HZ perceived as low risk","Time constraints","Cost concerns","Doubts on vaccine necessity"],
        "specialties": ["GP","Dermatologist","Geriatrician","Neurologist"],
        "references_path": ".devcontainer/references/shingrix/",
        "call_flow": ["Prepare","Engage","Create Opportunity","Influence","Impact GSO","Post-Call Review"]
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Targeting","Initiation","Optimization","Advocacy"],
        "personas": ["Data-Driven Oncologist","Innovator","Late Adopter"],
        "barriers": ["Eligibility uncertainty","Safety concerns","Access / reimbursement"],
        "specialties": ["Medical Oncologist"],
        "references_path": ".devcontainer/references/jemperli/",
        "call_flow": ["COCO Framework","Scientific Anchor","Eligibility Confirmation","Clinical Confidence","Access Alignment"]
    }
}

# ==========================================================
# SESSION STATE
# ==========================================================
st.session_state.setdefault("chat", [])
st.session_state.setdefault("citations", [])
st.session_state.setdefault("selected_citation", None)
st.session_state.setdefault("metrics", {"prompts":0,"responses":0})
st.session_state.setdefault("feedback", {"like":0,"dislike":0,"need_more":0})

# ==========================================================
# DASHBOARD
# ==========================================================
page = st.sidebar.radio("Navigate", ["Chat Assistant","Utilization Dashboard"])

if page == "Utilization Dashboard":
    st.title("📊 Utilization Dashboard")
    st.metric("Prompts Asked", st.session_state.metrics["prompts"])
    st.metric("Responses Generated", st.session_state.metrics["responses"])
    st.metric("👍 Likes", st.session_state.feedback["like"])
    st.metric("👎 Dislikes", st.session_state.feedback["dislike"])
    st.metric("🔁 Need More", st.session_state.feedback["need_more"])
    st.stop()

# ==========================================================
# SIDEBAR CONFIG
# ==========================================================
st.sidebar.header("🎯 Call Configuration")

brand_key = st.sidebar.selectbox("Brand", brand_data.keys(), format_func=lambda x: brand_data[x]["display"])
brand = brand_data[brand_key]

segment = st.sidebar.selectbox("Segment", brand["segments"])
persona = st.sidebar.selectbox("Persona", brand["personas"])
specialty = st.sidebar.selectbox("Specialty", brand["specialties"])
objective = st.sidebar.selectbox("Objective", ["Awareness","Adoption","Retention"])
tone = st.sidebar.selectbox("Tone", ["Scientific","Executive","Friendly"])

LOGO_SIZE = st.sidebar.slider("Logo Size", 50, 120, 80)

# ==========================================================
# TITLE
# ==========================================================
st.markdown(f"""
<div class='title-container'>
    <img src='data:image/png;base64,{AURA_LOGO}' height='{LOGO_SIZE}'>
    <h1>🧠 AI Sales Call Assistant</h1>
    <img src='data:image/png;base64,{GSK_LOGO}' height='{LOGO_SIZE}'>
</div>
""", unsafe_allow_html=True)

# ==========================================================
# LOAD GUIDELINES
# ==========================================================
@st.cache_data
def load_guidelines(path):
    pages = []
    if os.path.exists(path):
        for file in os.listdir(path):
            if file.endswith(".pdf"):
                reader = PdfReader(os.path.join(path,file))
                for i,p in enumerate(reader.pages):
                    text = p.extract_text()
                    if text:
                        pages.append({"source":file,"page":i+1,"text":text})
    return pages

def retrieve_pages(question, pages, k=3):
    corpus = [p["text"] for p in pages]
    tfidf = TfidfVectorizer(stop_words="english").fit_transform(corpus+[question])
    scores = cosine_similarity(tfidf[-1], tfidf[:-1]).flatten()
    idx = scores.argsort()[-k:][::-1]
    return [pages[i] for i in idx]

# ==========================================================
# MAIN UI
# ==========================================================
col_main, col_side = st.columns([3,1])

# 📖 Selected Guideline Snippet
with col_main:
    if st.session_state.selected_citation:
        p = st.session_state.selected_citation
        with st.expander(f"📖 {p['source']} – Page {p['page']}", expanded=True):
            st.markdown(f"<div class='citation-box'>{p['text']}</div>", unsafe_allow_html=True)

# 💬 Conversation
with col_main:
    st.markdown("## 💬 Sales Conversation")
    for msg in st.session_state.chat:
        if msg["role"] == "user":
            st.markdown(f"<div class='user-box'>{msg['content']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='ai-box'><img src='{AI_AVATAR}' class='avatar'><br>{msg['content']}</div>", unsafe_allow_html=True)
            audio = gTTS(msg["content"])
            buf = io.BytesIO()
            audio.write_to_fp(buf)
            st.audio(buf.getvalue(), format="audio/mp3")

# 💡 Prompt Suggestions
with st.container():
    with st.expander("💡 Prompt Suggestions", expanded=True):
        for s in [
            "Generate full sales call flow",
            "Summarize guideline relevance",
            "Handle HCP objection",
            "Explain safety profile"
        ]:
            if st.button(s):
                st.session_state.chat.append({"role":"user","content":s})
                st.session_state.metrics["prompts"] += 1
                st.rerun()

# ✍️ Chat Input
with st.form("chat"):
    user_input = st.text_input("Ask a question or generate a sales call flow")
    submitted = st.form_submit_button("Generate")

    if submitted and user_input:
        pages = load_guidelines(brand["references_path"])
        refs = retrieve_pages(user_input, pages)
        st.session_state.citations = refs

        prompt = f"""
You are a compliant pharmaceutical sales AI.

Brand: {brand['display']}
Persona: {persona}
Specialty: {specialty}
Objective: {objective}
Tone: {tone}

Follow this sales call flow:
{', '.join(brand['call_flow'])}

Use only approved guideline content.
Answer in structured bullet points.

Question:
{user_input}
"""

        res = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":prompt}],
            temperature=0.2
        )

        answer = res.choices[0].message.content
        st.session_state.chat.append({"role":"user","content":user_input})
        st.session_state.chat.append({"role":"ai","content":answer})
        st.session_state.metrics["prompts"] += 1
        st.session_state.metrics["responses"] += 1
        st.rerun()

# 👍 Feedback
with col_main:
    c1,c2,c3 = st.columns(3)
    if c1.button("👍 Like"): st.session_state.feedback["like"] += 1
    if c2.button("👎 Dislike"): st.session_state.feedback["dislike"] += 1
    if c3.button("🔁 Need More"): st.session_state.feedback["need_more"] += 1

# ⚠️ Disclaimer
st.markdown("""
<div class='disclaimer'>
⚠️ Internal training use only. Non-promotional. Content must comply with local regulations and approved labels.
</div>
""", unsafe_allow_html=True)
