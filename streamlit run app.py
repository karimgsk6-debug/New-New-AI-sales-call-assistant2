# ==========================================================
# AI SALES CALL ASSISTANT – FULL FEATURED WITH DASHBOARD
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
# VISUAL ASSETS
# ==========================================================
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"

BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final.png"

def image_to_base64(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return None

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
.user-box {background:rgba(240,240,240,1); padding:12px; border-radius:12px; margin-bottom:6px;}
.ai-box {background:white; padding:16px; border-radius:16px; border:1px solid rgba(200,200,200,0.3); margin-bottom:6px;}
.citation-box {background:white; padding:16px; border-radius:16px; border:1px solid rgba(200,200,200,0.3); margin-bottom:8px;}
.avatar {width:64px; border-radius:50%; box-shadow:0 0 20px rgba(0,0,0,0.2); margin-bottom:8px;}
.section-title {color:#0a3; font-weight:700; font-size:20px;}
.disclaimer {position:fixed; bottom:0; width:100%; background: rgba(245,245,245,0.95); color:#555; font-size:12px; padding:8px; border-top:1px solid #ccc; z-index:100;}
.title-container {display:flex; align-items:center; justify-content:space-between; margin-bottom:16px;}
.title-container img {height:40px; margin-left:8px; margin-right:8px;}
.prompt-bubble {background:#f0f8ff; padding:12px; border-radius:16px; margin-bottom:8px; cursor:pointer;}
.feedback-container {display:flex; gap:10px; margin-top:8px;}
.call-flow-step {background:#f8f8f8; padding:12px; border-radius:12px; margin-bottom:6px;}
</style>
""", unsafe_allow_html=True)

# ==========================================================
# BRAND DATA
# ==========================================================
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers": ["HZ perceived as low risk","Time constraints","Cost concerns","Doubts on vaccine necessity"],
        "specialties": ["GP","Dermatologist","Geriatrician"],
        "references_path": ".devcontainer/references/shingrix/",
        "call_flow": ["Prepare","Engage","Create Opportunity","Influence","Impact GSO","Post-Call Review"]
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Targeting","Initiation","Optimization","Advocacy"],
        "personas": ["Data-Driven Oncologist","Skeptical Prescriber","Innovator","Late Adopter"],
        "barriers": ["Eligibility uncertainty","Safety concerns","Limited experience with IO","Access / reimbursement"],
        "specialties": ["Oncologist","Medical Oncologist"],
        "references_path": ".devcontainer/references/jemperli/",
        "call_flow": ["COCO Framework","Scientific Anchor","Eligibility Confirmation","Clinical Confidence","Access Alignment"]
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness","Diagnosis","Adoption","Adherence"],
        "personas": ["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse Specialist"],
        "barriers": ["Formulary restrictions","Inhaler technique concerns","ICS safety perception","Cost & access"],
        "specialties": ["GP","Pulmonologist","Respiratory Specialist"],
        "references_path": ".devcontainer/references/trelegy/",
        "call_flow": ["Prepare","Engage","Demonstrate Value","Address Access","Close & Commit"]
    }
}

# ==========================================================
# SESSION STATE
# ==========================================================
st.session_state.setdefault("chat", [])
st.session_state.setdefault("citations", [])
st.session_state.setdefault("selected_citation", None)
st.session_state.setdefault("feedback", {"like":0,"dislike":0,"need_more":0})
st.session_state.setdefault("input_text", "")
st.session_state.setdefault("metrics", {"prompts":0,"responses":0})

# ==========================================================
# DASHBOARD PAGE
# ==========================================================
pages = ["Chat Assistant", "Utilization Dashboard"]
page = st.sidebar.radio("Navigate", pages)

if page=="Utilization Dashboard":
    st.markdown("## 📊 Utilization Dashboard")
    st.metric("Total prompts asked", st.session_state.metrics["prompts"])
    st.metric("Total AI responses generated", st.session_state.metrics["responses"])
    st.metric("Likes", st.session_state.feedback["like"])
    st.metric("Dislikes", st.session_state.feedback["dislike"])
    st.metric("Need More", st.session_state.feedback["need_more"])
    st.stop()  # stop here on dashboard page

# ==========================================================
# LOAD GUIDELINES
# ==========================================================
@st.cache_data
def load_guidelines(path):
    pages = []
    if os.path.exists(path):
        for file in os.listdir(path):
            if file.lower().endswith(".pdf"):
                reader = PdfReader(os.path.join(path, file))
                for i, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text:
                        pages.append({"source": file,"page": i+1,"text": text})
    return pages

# ==========================================================
# RAG
# ==========================================================
def retrieve_pages(question, pages, top_k=3):
    corpus = [p["text"] for p in pages]
    tfidf = TfidfVectorizer(stop_words="english").fit_transform(corpus + [question])
    scores = cosine_similarity(tfidf[-1], tfidf[:-1]).flatten()
    top_idx = scores.argsort()[-top_k:][::-1]
    return [pages[i] for i in top_idx]

# ==========================================================
# OFF-LABEL DETECTION
# ==========================================================
def detect_off_label(answer, refs):
    combined = " ".join(p["text"].lower() for p in refs)
    risky_terms = ["children","pediatric","pregnant","off-label","unapproved"]
    for t in risky_terms:
        if t in answer.lower() and t not in combined:
            return True
    return False

# ==========================================================
# SIDEBAR CONFIG
# ==========================================================
st.sidebar.header("🎯 Call Configuration")
brand_key = st.sidebar.selectbox("Brand", list(brand_data.keys()), format_func=lambda x: brand_data[x]["display"])
brand = brand_data[brand_key]
segment = st.sidebar.selectbox("Segment", brand["segments"])
persona = st.sidebar.selectbox("Persona", brand["personas"])
specialty = st.sidebar.selectbox("Specialty", brand["specialties"])
barriers = st.sidebar.multiselect("HCP Barriers", brand["barriers"])
objective = st.sidebar.selectbox("Objective", ["Awareness","Adoption","Retention"])
tone = st.sidebar.selectbox("Tone", ["Executive","Scientific","Friendly"])

with st.sidebar.expander("📊 Sales Module Flow", expanded=True):
    for step in brand["call_flow"]:
        st.markdown(f"- **{step}**")

with st.sidebar.expander("📚 Medical References", expanded=True):
    st.caption("Click page to view snippet")
    if st.session_state.citations:
        for i, p in enumerate(st.session_state.citations):
            if st.button(f"{p['source']} – Page {p['page']}", key=f"cit_{i}"):
                st.session_state.selected_citation = p

# ==========================================================
# TITLE
# ==========================================================
st.markdown(f"""
<div class='title-container'>
    <img src='data:image/png;base64,{AURA_LOGO}'>
    <h1>🧠 AI Sales Call Assistant</h1>
    <img src='data:image/png;base64,{GSK_LOGO}'>
</div>
""", unsafe_allow_html=True)

col_main, col_side = st.columns([3,1])

# ==========================================================
# 1. Selected Guideline Snippet (white collapsible)
# ==========================================================
with col_main:
    if st.session_state.selected_citation:
        p = st.session_state.selected_citation
        with st.expander(f"📖 {p['source']} – Page {p['page']}", expanded=True):
            st.markdown(f"<div class='citation-box'>{p['text']}</div>", unsafe_allow_html=True)

# ==========================================================
# 2. Prompt Suggestions
# ==========================================================
with col_main:
    with st.expander("💡 Prompt Suggestions", expanded=False):
        suggestions = [
            "Generate sales call flow for selected HCP persona",
            "Summarize guideline snippet for HCP",
            "Provide objection handling strategies",
            "Explain safety considerations"
        ]
        for s in suggestions:
            if st.button(s, key=f"prompt_{s}"):
                st.session_state.input_text = s
                st.session_state.metrics["prompts"] += 1

# ==========================================================
# 3. Sales Conversation + AI Response + Voice
# ==========================================================
with col_main:
    st.markdown("### 💬 Sales Conversation")
    for msg in st.session_state.chat:
        if msg["role"]=="user":
            st.markdown(f"<div class='user-box'>{msg['content']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='ai-box'><img src='{AI_AVATAR}' class='avatar'><br>{msg['content']}</div>", unsafe_allow_html=True)

    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("Ask a medical question or generate a sales call flow…", value=st.session_state.input_text)
        submit = st.form_submit_button("Generate")
        if submit and user_input:
            pages = load_guidelines(brand["references_path"])
            retrieved = retrieve_pages(user_input, pages)
            st.session_state.citations = retrieved
            st.session_state.chat.append({"role":"user","content":user_input})
            st.session_state.metrics["prompts"] += 1

            citations_text = "\n".join(f"[{p['source']} p.{p['page']}]\n{p['text'][:900]}" for p in retrieved)
            prompt = f"""
STRICT COMPLIANCE RULES:
- Use ONLY approved guideline content
- Cite page numbers like [p.X]
- Do NOT generalize populations
- Do NOT mention off-label use

GUIDELINES:
{citations_text}

QUESTION:
{user_input}

CONTEXT:
Brand: {brand['display']}
Segment: {segment}
Persona: {persona}
Specialty: {specialty}
Objective: {objective}
Barriers: {', '.join(barriers) if barriers else 'None'}
Tone: {tone}

Follow the brand-specific sales call steps: {', '.join(brand['call_flow'])}
"""

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":"You are a compliant pharmaceutical sales AI."},
                          {"role":"user","content":prompt}],
                temperature=0.2
            )

            answer = response.choices[0].message.content
            if detect_off_label(answer, retrieved):
                answer = "⚠️ **Compliance Alert** – Outside approved indications."

            st.session_state.chat.append({"role":"ai","content":answer})
            st.session_state.metrics["responses"] += 1
            st.session_state.input_text = ""

            # ================= TTS =================
            tts = gTTS(text=answer, lang='en')
            audio_bytes = io.BytesIO()
            tts.write_to_fp(audio_bytes)
            st.audio(audio_bytes.getvalue(), format="audio/mp3")
