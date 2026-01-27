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

client = Groq(api_key="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")


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

# ==========================================================
# BACKGROUND
# ==========================================================
def set_background(image_path):
    if os.path.exists(image_path):
        encoded = image_to_base64(image_path)
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
.user-box {background:#f0f0f0; padding:12px; border-radius:12px; margin-bottom:6px;}
.ai-box {background:white; padding:18px; border-radius:16px; border:1px solid #ddd; margin-bottom:6px;}
.citation-box {background:white; padding:16px; border-radius:14px; border:1px solid #ddd;}
.avatar {width:60px; border-radius:50%; margin-bottom:8px;}
.title-container {display:flex; align-items:center; justify-content:space-between;}
.feedback-container {display:flex; gap:12px;}
.fixed-prompts {position:fixed; bottom:60px; width:65%; z-index:100;}
.disclaimer {position:fixed; bottom:0; width:100%; background:#f5f5f5; font-size:12px; padding:8px; border-top:1px solid #ccc;}
</style>
""", unsafe_allow_html=True)

# ==========================================================
# BRAND DATA
# ==========================================================
brand_data = {
    "shingrix": {
        "display":"Shingrix",
        "segments":["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas":["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers":["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
        "specialties":["GP","Dermatologist","Geriatrician"],
        "references_path":".devcontainer/references/shingrix/",
        "sales_path":".devcontainer/SalesModule/shingrix/",
        "call_flow":["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Post-call Analysis"]
    },
    "jemperli": {
        "display":"Jemperli",
        "segments":["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas":["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers":["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties":["Oncologist","Medical Oncologist"],
        "references_path":".devcontainer/references/jemperli/",
        "sales_path":".devcontainer/SalesModule/jemperli/",
        "call_flow":["COCO","Anchor","Engage","Close"]
    },
    "trelegy": {
        "display":"Trelegy",
        "segments":["Awareness","Diagnosis","Adoption","Adherence"],
        "personas":["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers":["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties":["GP","Pulmonologist","Respiratory Specialist"],
        "references_path":".devcontainer/references/trelegy/",
        "sales_path":".devcontainer/SalesModule/trelegy/",
        "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"]
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
# LOAD GUIDELINES (RAG)
# ==========================================================
@st.cache_data
def load_guidelines(path):
    pages = []
    if os.path.exists(path):
        for file in os.listdir(path):
            if file.endswith(".pdf"):
                reader = PdfReader(os.path.join(path,file))
                for i,p in enumerate(reader.pages):
                    txt = p.extract_text()
                    if txt:
                        pages.append({"source":file,"page":i+1,"text":txt})
    return pages

def retrieve_pages(q, pages, k=3):
    corpus = [p["text"] for p in pages]
    tfidf = TfidfVectorizer(stop_words="english").fit_transform(corpus+[q])
    scores = cosine_similarity(tfidf[-1], tfidf[:-1]).flatten()
    idx = scores.argsort()[-k:][::-1]
    return [pages[i] for i in idx]

# ==========================================================
# SIDEBAR CONFIG
# ==========================================================
st.sidebar.header("🎯 Call Configuration")
brand_key = st.sidebar.selectbox("Brand", brand_data.keys(), format_func=lambda x: brand_data[x]["display"])
brand = brand_data[brand_key]
persona = st.sidebar.selectbox("Persona", brand["personas"])
specialty = st.sidebar.selectbox("Specialty", brand["specialties"])
tone = st.sidebar.selectbox("Tone", ["Scientific","Executive","Friendly"])

LOGO_SIZE = st.sidebar.slider("Logo size (px)", 50, 120, 80)

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
# GUIDELINE SNIPPET
# ==========================================================
if st.session_state.selected_citation:
    p = st.session_state.selected_citation
    with st.expander(f"📖 {p['source']} – Page {p['page']}", expanded=True):
        st.markdown(f"<div class='citation-box'>{p['text']}</div>", unsafe_allow_html=True)

# ==========================================================
# CHAT HISTORY
# ==========================================================
st.markdown("### 💬 Sales Conversation")

for msg in st.session_state.chat:
    if msg["role"] == "user":
        st.markdown(f"<div class='user-box'>{msg['content']}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class='ai-box'>
        <img src='{AI_AVATAR}' class='avatar'><br>
        {msg['content']}
        </div>
        """, unsafe_allow_html=True)
        tts = gTTS(msg["content"])
        audio = io.BytesIO()
        tts.write_to_fp(audio)
        st.audio(audio.getvalue(), format="audio/mp3")

# ==========================================================
# FIXED PROMPT SUGGESTIONS
# ==========================================================
with st.container():
    st.markdown("<div class='fixed-prompts'>", unsafe_allow_html=True)
    with st.expander("💡 Prompt Suggestions", expanded=True):
        for s in [
            "Generate full sales call flow",
            "Summarize guideline for HCP",
            "Handle common objections",
            "Explain safety profile"
        ]:
            if st.button(s):
                st.session_state.chat.append({"role":"user","content":s})
    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================================
# CHAT INPUT
# ==========================================================
with st.form("chat_form", clear_on_submit=True):
    q = st.text_input("Ask a medical or sales question…")
    submit = st.form_submit_button("Generate")

if submit and q:
    st.session_state.metrics["prompts"] += 1
    pages = load_guidelines(brand["references_path"])
    retrieved = retrieve_pages(q, pages)
    st.session_state.citations = retrieved

    citations_text = "\n".join(f"[{p['source']} p.{p['page']}]\n{p['text'][:800]}" for p in retrieved)

    prompt = f"""
You are a compliant pharmaceutical sales AI.

Use BULLET POINTS and structured headings.
Organize medical summaries as:
• Indication
• Eligible patients
• Key clinical evidence
• Safety considerations
• Clinical takeaway

Follow the sales call steps strictly:
{', '.join(brand['call_flow'])}

Guidelines:
{citations_text}

Question:
{q}

Persona: {persona}
Specialty: {specialty}
Tone: {tone}
"""

    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":prompt}],
        temperature=0.2
    )

    answer = res.choices[0].message.content
    st.session_state.chat.append({"role":"user","content":q})
    st.session_state.chat.append({"role":"ai","content":answer})
    st.session_state.metrics["responses"] += 1

# ==========================================================
# FEEDBACK
# ==========================================================
st.markdown("### Feedback")
c1,c2,c3 = st.columns(3)
if c1.button("👍 Like"): st.session_state.feedback["like"] += 1
if c2.button("👎 Dislike"): st.session_state.feedback["dislike"] += 1
if c3.button("🔁 Need More"): st.session_state.feedback["need_more"] += 1

# ==========================================================
# DISCLAIMER
# ==========================================================
st.markdown("""
<div class="disclaimer">
⚠️ Internal training use only. Non-promotional. Follow local compliance policies.
</div>
""", unsafe_allow_html=True)
