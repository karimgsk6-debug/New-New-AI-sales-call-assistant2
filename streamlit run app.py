# ==========================================================
# AI SALES CALL ASSISTANT – WHITE BUBBLES + Brand Call Flow
# ==========================================================

import streamlit as st
import os, base64
from groq import Groq
from PyPDF2 import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

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
GSK_LOGO = ".devcontainer/Visuals/GSK-logo.png"
AURA_LOGO = ".devcontainer/Visuals/AURA.png"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

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
st.session_state.setdefault("feedback", {})
st.session_state.setdefault("input_text", "")

# ==========================================================
# LOAD GUIDELINES
# ==========================================================
@st.cache_data(show_spinner=False)
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
# RAG RETRIEVAL
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
    <img src='{AURA_LOGO}'>
    <h1>🧠 AI Sales Call Assistant</h1>
    <img src='{GSK_LOGO}'>
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
# 2. Prompt Suggestions (copilot-style)
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

# ==========================================================
# 3. Sales Conversation + AI Response
# ==========================================================
with col_main:
    st.markdown("### 💬 Sales Conversation")
    for msg in st.session_state.chat:
        if msg["role"]=="user":
            st.markdown(f"<div class='user-box'>{msg['content']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='ai-box'><img src='{AI_AVATAR}' class='avatar'><br>{msg['content']}</div>", unsafe_allow_html=True)

    # Chat input form
    with st.form("chat_form", clear_on_submit=True):
        user_input = st.text_input("Ask a medical question or generate a sales call flow…", value=st.session_state.input_text)
        submit = st.form_submit_button("Generate")

        if submit and user_input:
            pages = load_guidelines(brand["references_path"])
            retrieved = retrieve_pages(user_input, pages)
            st.session_state.citations = retrieved
            st.session_state.chat.append({"role":"user","content":user_input})

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
            st.session_state.input_text = ""

# ==========================================================
# 4. TTS Placeholder
# ==========================================================
with col_main:
    st.audio(None)

# ==========================================================
# 5. Feedback Cycle
# ==========================================================
with col_main:
    st.markdown("### Feedback")
    col1, col2, col3 = st.columns(3)
    with col1: st.button("👍 Like", key="like")
    with col2: st.button("👎 Dislike", key="dislike")
    with col3: st.button("⏳ Need More", key="need_more")

# ==========================================================
# DISCLAIMER
# ==========================================================
st.markdown("""
<div class="disclaimer">
⚠️ Internal training use only. AI-generated content is non-promotional and must strictly comply with approved product labels and local compliance policies.
</div>
""", unsafe_allow_html=True)
