import streamlit as st
from datetime import datetime
from groq import Groq
import os
from PyPDF2 import PdfReader
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# =========================
# GROQ CLIENT
# =========================
client = Groq(api_key="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")

# =========================
# Soft imports (optional)
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
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except Exception:
    ELEVENLABS_AVAILABLE = False

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# Resources & Avatar
# -------------------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

# Futuristic hologram avatar URL (replace with your asset if desired)
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"

# -------------------------
# Session defaults
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
        "hcp_persona": "Friendly",
        "hcp_personality": "Friendly",
        "tone": "executive",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

_init_session()

# -------------------------
# CSS for hologram avatar + chat bubbles
# -------------------------
st.markdown(
    """
    <style>
    .title-box{ background: rgba(255,255,255,0.85); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; position:relative; margin-bottom:12px; }
    .title-box img.left-logo{ position:absolute; left:12px; height:48px; }
    .title-box img.right-logo{ position:absolute; right:12px; height:48px; }

    /* User bubble */
    .chat-bubble-user{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }

    /* AI bubble with avatar on left */
    .ai-message { display:flex; align-items:flex-start; gap:12px; margin:10px 0; }
    .ai-avatar { width:52px; height:52px; border-radius:50%; box-shadow: 0 0 12px rgba(0,255,255,0.6); flex-shrink:0; animation:holoPulse 2.5s infinite ease-in-out; }
    @keyframes holoPulse { 0% { box-shadow:0 0 8px rgba(0,255,255,0.35);} 50% { box-shadow:0 0 22px rgba(0,255,255,0.9);} 100% { box-shadow:0 0 8px rgba(0,255,255,0.35);} }
    .ai-bubble { background: rgba(255,255,255,0.06); border:1px solid rgba(0,255,255,0.18); color:#E6FBFF; padding:14px; border-radius:14px; backdrop-filter: blur(6px); max-width:90%; white-space:pre-wrap; }

    .citation-box{ font-size:12px; color:#bcd; margin-left:6px; margin-bottom:6px; }
    .fixed-disclaimer{ font-size:12px; color:#aac; margin-top:16px; opacity:0.9; }
    .step-title{ font-weight:700; margin-top:8px; color:#BFF; }
    .story{ font-style:italic; margin:6px 0 10px 0; color:#DFF; }
    ul.assist-list{ margin:6px 0 6px 18px; padding:0; color:#DDF; }
    .objection{ background:rgba(255,248,240,0.06); padding:8px; border-radius:8px; margin:6px 0; border:1px solid rgba(255,224,198,0.08); color:#FFD; }
    .user-bubble{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# Background helper
# -------------------------
def set_dynamic_background(image_path):
    if not os.path.exists(image_path):
        return
    try:
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
        st.markdown(
            f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background: linear-gradient(90deg, rgba(255,140,0,0.06), rgba(255,165,0,0.02)),
                            url("data:image/png;base64,{encoded}");
                background-repeat: no-repeat;
                background-position: right top;
                background-size: cover;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass

set_dynamic_background(BACKGROUND_PATH)

# -------------------------
# GROQ client loader
# -------------------------
def load_groq_client():
    api_key = os.getenv("GROQ_API_KEY", "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") or (st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else "")
    if not api_key or Groq is None:
        return None
    try:
        return Groq(api_key=api_key)
    except Exception:
        return None

# -------------------------
# BRAND MASTER DATA
# =========================
brand_data = {
    "shingrix": {
        "display":"Shingrix",
        "segments":["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas":["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers":["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
        "specialties":["GP","Dermatologist","Geriatrician"],
        "references_path":".devcontainer/references/shingrix/",
        "call_flow":["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Post-call Analysis"],
        "leaflet":"https://example.com/shingrix-leaflet"
    },
    "jemperli": {
        "display":"Jemperli",
        "segments":["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas":["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers":["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties":["Oncologist","Medical Oncologist"],
        "references_path":".devcontainer/references/jemperli/",
        "call_flow":["COCO","Anchor","Engage","Close"],
        "leaflet":"https://example.com/jemperli-leaflet"
    },
    "trelegy": {
        "display":"Trelegy",
        "segments":["Awareness","Diagnosis","Adoption","Adherence"],
        "personas":["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers":["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties":["GP","Pulmonologist","Respiratory Specialist"],
        "references_path":".devcontainer/references/trelegy/",
        "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"],
        "leaflet":"https://example.com/trelegy-leaflet"
    }
}

# =========================
# LOAD & INDEX PDF PAGES
# =========================
@st.cache_data(show_spinner=False)
def load_guidelines_pages(path):
    pages = []
    for file in os.listdir(path):
        if file.lower().endswith(".pdf"):
            reader = PdfReader(os.path.join(path, file))
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages.append({
                        "page": i + 1,
                        "source": file,
                        "text": text.strip()
                    })
    return pages

# =========================
# SEMANTIC RETRIEVAL
# =========================
def retrieve_relevant_pages(question, pages, top_k=3):
    corpus = [p["text"] for p in pages]
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf = vectorizer.fit_transform(corpus + [question])
    scores = cosine_similarity(tfidf[-1], tfidf[:-1]).flatten()
    top_indices = scores.argsort()[-top_k:][::-1]
    return [pages[i] for i in top_indices]

# =========================
# OFF-LABEL DETECTION
# =========================
def detect_off_label(ai_text, retrieved_pages):
    combined_text = " ".join(p["text"].lower() for p in retrieved_pages)
    risky_terms = ["children", "pediatric", "pregnant", "off-label", "unapproved"]

    for term in risky_terms:
        if term in ai_text.lower() and term not in combined_text:
            return True
    return False

# =========================
# SESSION STATE
# =========================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_citations" not in st.session_state:
    st.session_state.last_citations = []

# =========================
# UI
# =========================
st.title("🧠 AI Sales Call Assistant")
language = st.radio("Select Language / اختر اللغة", ["English", "العربية"])

# =========================
# SIDEBAR
# =========================
st.sidebar.header("Filters & Options")

brand_key = st.sidebar.selectbox(
    "Select Brand",
    list(brand_data.keys()),
    format_func=lambda x: brand_data[x]["display"]
)
brand_cfg = brand_data[brand_key]

segment = st.sidebar.selectbox("Segment", brand_cfg["segments"])
persona = st.sidebar.selectbox("Persona", brand_cfg["personas"])
barrier = st.sidebar.multiselect("Doctor Barriers", brand_cfg["barriers"])
specialty = st.sidebar.selectbox("Specialty", brand_cfg["specialties"])
objective = st.sidebar.selectbox("Objective", ["Awareness", "Adoption", "Retention"])
tone = st.sidebar.selectbox("Tone", ["Formal", "Friendly", "Persuasive"])
length = st.sidebar.selectbox("Length", ["Short", "Medium", "Long"])

# =========================
# CHAT DISPLAY
# =========================
for msg in st.session_state.chat_history:
    icon = "🧑" if msg["role"] == "user" else "🤖"
    st.markdown(f"**{icon}:** {msg['content']}")

# =========================
# INPUT
# =========================
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...")
    submitted = st.form_submit_button("Send")

# =========================
# AI PIPELINE
# =========================
if submitted and user_input.strip():

    st.session_state.chat_history.append({
        "role":"user",
        "content":user_input
    })

    all_pages = load_guidelines_pages(brand_cfg["references_path"])
    retrieved_pages = retrieve_relevant_pages(user_input, all_pages)

    citation_block = "\n\n".join(
        f"[Guideline {p['source']} – Page {p['page']}]\n{p['text'][:1200]}"
        for p in retrieved_pages
    )

    st.session_state.last_citations = retrieved_pages

    flow = " → ".join(brand_cfg["call_flow"])

    prompt = f"""
STRICT COMPLIANCE RULES:
- Use ONLY the content below
- Cite page numbers like [p.X]
- Never generalize populations
- Never mention off-label use

APPROVED GUIDELINE EXCERPTS:
{citation_block}

USER QUESTION:
{user_input}

CONTEXT:
Brand: {brand_cfg['display']}
Segment: {segment}
Persona: {persona}
Specialty: {specialty}
Objective: {objective}
Barriers: {', '.join(barrier) if barrier else 'None'}

CALL FLOW:
{flow}

Tone: {tone}
Length: {length}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role":"system","content":"You are a compliant pharmaceutical sales AI."},
            {"role":"user","content":prompt}
        ],
        temperature=0.3
    )

    ai_text = response.choices[0].message.content

    if detect_off_label(ai_text, retrieved_pages):
        ai_text = (
            "⚠️ **Compliance Block**\n\n"
            "The requested information may fall outside approved indications. "
            "Please rephrase your question using approved label language."
        )

    st.session_state.chat_history.append({
        "role":"ai",
        "content":ai_text
    })

    st.rerun()

# =========================
# CITATION HIGHLIGHT PANEL
# =========================
if st.session_state.last_citations:
    with st.expander("📖 View cited guideline pages"):
        for p in st.session_state.last_citations:
            st.markdown(
                f"**📄 {p['source']} – Page {p['page']}**\n\n"
                f"{p['text'][:1500]}..."
            )

# =========================
# DISCLAIMER
# =========================
st.markdown("""
<style>
.disclaimer {
    position: fixed;
    bottom: 0;
    width: 100%;
    background: #f5f5f5;
    padding: 8px;
    font-size: 12px;
    border-top: 1px solid #ccc;
}
</style>
<div class="disclaimer">
⚠️ Internal training use only. AI-generated content is non-promotional and must align with approved product labels.
</div>
""", unsafe_allow_html=True)

# =========================
# LEAFLET
# =========================
st.markdown(f"[📄 Brand Leaflet – {brand_cfg['display']}]({brand_cfg['leaflet']})")
