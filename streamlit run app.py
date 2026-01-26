# ==========================================================
# AI SALES CALL ASSISTANT – MULTI-BRAND COMPLIANT RAG PLATFORM
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
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================================
# GROQ CLIENT
# ==========================================================
client = Groq(
    api_key=os.getenv("GROQ_API_KEY", "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")
)

# ==========================================================
# VISUAL ASSETS
# ==========================================================
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

# ==========================================================
# BACKGROUND
# ==========================================================
def set_background(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        st.markdown(
            f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background:
                    linear-gradient(rgba(5,10,20,0.92), rgba(5,10,20,0.92)),
                    url("data:image/png;base64,{encoded}");
                background-size: cover;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

set_background(BACKGROUND_PATH)

# ==========================================================
# CSS
# ==========================================================
st.markdown("""
<style>
.ai-box {background:rgba(0,255,255,0.06); padding:16px; border-radius:16px; border:1px solid rgba(0,255,255,0.2)}
.user-box {background:rgba(255,255,255,0.08); padding:12px; border-radius:12px}
.avatar {width:64px; border-radius:50%; box-shadow:0 0 20px rgba(0,255,255,0.9)}
.section-title {color:#7ff; font-weight:700; font-size:20px}
.disclaimer {
    position: fixed;
    bottom: 0;
    width: 100%;
    background: rgba(10,10,10,0.95);
    color:#bbb;
    font-size:12px;
    padding:8px;
    border-top:1px solid #333;
    z-index:100;
}
</style>
""", unsafe_allow_html=True)

# ==========================================================
# BRAND MASTER DATA (FULL)
# ==========================================================
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": [
            "Uncommitted Vaccinator",
            "Reluctant Efficiency",
            "Patient Influenced",
            "Committed Vaccinator"
        ],
        "barriers": [
            "HZ perceived as low risk",
            "Time constraints",
            "Cost concerns",
            "Doubts on vaccine necessity"
        ],
        "specialties": ["GP", "Dermatologist", "Geriatrician"],
        "references_path": ".devcontainer/references/shingrix/",
        "call_flow": [
            "Prepare",
            "Engage",
            "Create Opportunity",
            "Influence",
            "Impact GSO",
            "Post-Call Review"
        ]
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Targeting", "Initiation", "Optimization", "Advocacy"],
        "personas": [
            "Data-Driven Oncologist",
            "Skeptical Prescriber",
            "Innovator",
            "Late Adopter"
        ],
        "barriers": [
            "Eligibility uncertainty",
            "Safety concerns",
            "Limited experience with IO",
            "Access / reimbursement"
        ],
        "specialties": ["Oncologist", "Medical Oncologist"],
        "references_path": ".devcontainer/references/jemperli/",
        "call_flow": [
            "COCO Framework",
            "Scientific Anchor",
            "Eligibility Confirmation",
            "Clinical Confidence",
            "Access Alignment"
        ]
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": [
            "Primary Care COPD Prescriber",
            "Pulmonologist",
            "Respiratory Nurse Specialist"
        ],
        "barriers": [
            "Formulary restrictions",
            "Inhaler technique concerns",
            "ICS safety perception",
            "Cost & access"
        ],
        "specialties": ["GP", "Pulmonologist", "Respiratory Specialist"],
        "references_path": ".devcontainer/references/trelegy/",
        "call_flow": [
            "Prepare",
            "Engage",
            "Demonstrate Value",
            "Address Access",
            "Close & Commit"
        ]
    }
}

# ==========================================================
# SESSION STATE
# ==========================================================
st.session_state.setdefault("chat", [])
st.session_state.setdefault("citations", [])

# ==========================================================
# SIDEBAR – CONFIGURATION
# ==========================================================
st.sidebar.header("🎯 Call Configuration")

brand_key = st.sidebar.selectbox(
    "Brand",
    list(brand_data.keys()),
    format_func=lambda x: brand_data[x]["display"]
)
brand = brand_data[brand_key]

segment = st.sidebar.selectbox("Segment", brand["segments"])
persona = st.sidebar.selectbox("Persona", brand["personas"])
specialty = st.sidebar.selectbox("Specialty", brand["specialties"])
barriers = st.sidebar.multiselect("HCP Barriers", brand["barriers"])
objective = st.sidebar.selectbox("Objective", ["Awareness", "Adoption", "Retention"])
tone = st.sidebar.selectbox("Tone", ["Executive", "Scientific", "Friendly"])

# ==========================================================
# LOAD GUIDELINES
# ==========================================================
@st.cache_data(show_spinner=False)
def load_guidelines(path):
    pages = []
    for file in os.listdir(path):
        if file.lower().endswith(".pdf"):
            reader = PdfReader(os.path.join(path, file))
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages.append({
                        "source": file,
                        "page": i + 1,
                        "text": text
                    })
    return pages

# ==========================================================
# SEMANTIC RAG
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
    risky_terms = ["children", "pediatric", "pregnant", "off-label", "unapproved"]
    for t in risky_terms:
        if t in answer.lower() and t not in combined:
            return True
    return False

# ==========================================================
# MAIN UI
# ==========================================================
st.title("🧠 AI Sales Call Assistant")

col1, col2 = st.columns([3,2])

# ------------------ CHAT ------------------
with col1:
    st.markdown("### 💬 Sales Conversation")

    for msg in st.session_state.chat:
        if msg["role"] == "user":
            st.markdown(f"<div class='user-box'>{msg['content']}</div>", unsafe_allow_html=True)
        else:
            st.markdown(
                f"""
                <div class='ai-box'>
                    <img src="{AI_AVATAR}" class="avatar"><br><br>
                    {msg['content']}
                </div>
                """,
                unsafe_allow_html=True
            )

    with st.form("chat_form"):
        question = st.text_input("Ask a medical question or generate a sales call flow…")
        submit = st.form_submit_button("Generate")

# ------------------ MODULES ------------------
with col2:
    st.markdown("### 📊 Sales Module Flow")
    for step in brand["call_flow"]:
        st.markdown(f"- **{step}**")

    st.markdown("---")
    st.markdown("### 📚 Medical References")
    st.caption("Auto-retrieved guideline pages only")

# ==========================================================
# AI PIPELINE
# ==========================================================
if submit and question:
    st.session_state.chat.append({"role": "user", "content": question})

    pages = load_guidelines(brand["references_path"])
    retrieved = retrieve_pages(question, pages)

    st.session_state.citations = retrieved

    citations_text = "\n".join(
        f"[{p['source']} p.{p['page']}]\n{p['text'][:900]}"
        for p in retrieved
    )

    prompt = f"""
STRICT COMPLIANCE RULES:
- Use ONLY approved guideline content
- Cite page numbers like [p.X]
- Do NOT generalize populations
- Do NOT mention off-label use

GUIDELINES:
{citations_text}

QUESTION:
{question}

CONTEXT:
Brand: {brand['display']}
Segment: {segment}
Persona: {persona}
Specialty: {specialty}
Objective: {objective}
Barriers: {', '.join(barriers) if barriers else 'None'}
Tone: {tone}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are a compliant pharmaceutical sales AI."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    answer = response.choices[0].message.content

    if detect_off_label(answer, retrieved):
        answer = (
            "⚠️ **Compliance Alert**\n\n"
            "The requested response may fall outside approved product indications. "
            "Please rephrase using approved label language."
        )

    st.session_state.chat.append({"role": "ai", "content": answer})
    st.rerun()

# ==========================================================
# CITATION VIEWER
# ==========================================================
if st.session_state.citations:
    with st.expander("📖 View cited guideline snippets"):
        for p in st.session_state.citations:
            st.markdown(
                f"**{p['source']} – Page {p['page']}**\n\n{p['text'][:1500]}..."
            )

# ==========================================================
# FIXED DISCLAIMER
# ==========================================================
st.markdown("""
<div class="disclaimer">
⚠️ Internal training use only. AI-generated content is non-promotional and must strictly comply with approved product labels and local compliance policies.
</div>
""", unsafe_allow_html=True)
