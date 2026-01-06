# ============================================================
# AI SALES CALL ASSISTANT
# RAG + SENTENCE CITATION + ROLE PLAY
# ============================================================

import streamlit as st
import os, re, io, base64
from html import escape

# -------------------------
# OPTIONAL IMPORTS
# -------------------------
try:
    from groq import Groq
except:
    Groq = None

try:
    from PyPDF2 import PdfReader
except:
    PdfReader = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN = True
except:
    SKLEARN = False

# -------------------------
# PAGE CONFIG
# -------------------------
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------
# PRODUCT MASTER DATA
# -------------------------
PRODUCTS = {
    "shingrix": {
        "display": "Shingrix",
        "indication": "Herpes Zoster (Shingles) Prevention",
        "segments": ["Reach", "Acquire", "Convert", "Engage"],
        "personas": [
            "Evidence-led",
            "Time-pressured",
            "Skeptical",
            "Patient-influenced",
            "Committed vaccinator"
        ],
        "specialties": ["GP", "Internal Medicine", "Rheumatology", "Immunology"],
        "barriers": [
            "HZ not perceived as serious",
            "Time constraints",
            "Cost concerns",
            "Safety misconceptions"
        ],
        "objectives": ["Awareness", "Adoption", "Acceleration"],
        "call_flow": ["Prepare", "Engage", "Create Opportunity", "Influence", "Impact", "Analyze"],
        "objections": ["Efficacy", "Safety", "Cost"],
        "refs": ".devcontainer/references/shingrix/",
        "sales": ".devcontainer/SalesModule/shingrix/"
    },

    "jemperli": {
        "display": "Jemperli",
        "indication": "dMMR / MSI-H Endometrial Cancer",
        "segments": ["Identify", "Initiate", "Adopt", "Advocate"],
        "personas": [
            "Data-driven oncologist",
            "Skeptical specialist",
            "Early adopter",
            "Guideline follower"
        ],
        "specialties": ["Medical Oncology", "Gynecologic Oncology"],
        "barriers": [
            "Patient eligibility uncertainty",
            "Safety concerns",
            "Reimbursement complexity"
        ],
        "objectives": ["Trial", "Routine Use", "Advocacy"],
        "call_flow": ["COCO", "Anchor", "Engage", "Close"],
        "objections": ["Efficacy", "Safety", "Access"],
        "refs": ".devcontainer/references/jemperli/",
        "sales": ".devcontainer/SalesModule/jemperli/"
    },

    "trelegy": {
        "display": "Trelegy",
        "indication": "COPD Maintenance Therapy",
        "segments": ["Awareness", "Diagnose", "Adopt", "Adhere"],
        "personas": [
            "Primary care prescriber",
            "Pulmonologist",
            "Nurse educator"
        ],
        "specialties": ["GP", "Pulmonology", "Respiratory"],
        "barriers": [
            "Inhaler technique",
            "Formulary access",
            "Side effect concerns"
        ],
        "objectives": ["Initiation", "Switch", "Adherence"],
        "call_flow": ["Prepare", "Engage", "Demonstrate", "Access", "Close"],
        "objections": ["Device", "Coverage", "Effectiveness"],
        "refs": ".devcontainer/references/trelegy/",
        "sales": ".devcontainer/SalesModule/trelegy/"
    }
}

# -------------------------
# SESSION INIT
# -------------------------
def init_session():
    defaults = {
        "chat": [],
        "roleplay_history": [],
        "brand": "shingrix",
        "persona": "",
        "tone": "executive",
        "simulation": False
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_session()

# -------------------------
# GROQ CLIENT
# -------------------------
def groq_client():
    key = os.getenv("GROQ_API_KEY", "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")
    if not key or not Groq:
        return None
    return Groq(api_key=key)

# -------------------------
# FILE & CORPUS HANDLING
# -------------------------
def read_text(path):
    if not os.path.exists(path):
        return ""
    if path.endswith(".pdf") and PdfReader:
        reader = PdfReader(path)
        return " ".join(p.extract_text() or "" for p in reader.pages)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def build_corpus(paths):
    chunks, sources = [], []
    for folder in paths:
        if not os.path.exists(folder):
            continue
        for f in os.listdir(folder):
            if f.endswith((".pdf", ".txt")):
                text = read_text(os.path.join(folder, f))
                for s in re.split(r'(?<=[.!?])\s+', text):
                    if len(s.strip()) > 40:
                        chunks.append(s.strip())
                        sources.append(f)
    return chunks, sources

def retrieve(query, chunks, sources, k=6):
    if not SKLEARN or not chunks:
        return []
    vec = TfidfVectorizer(stop_words="english")
    X = vec.fit_transform(chunks + [query])
    sims = linear_kernel(X[-1], X[:-1]).flatten()
    idxs = sims.argsort()[::-1][:k]
    return [{"text": chunks[i], "src": sources[i]} for i in idxs if sims[i] > 0]

def cite_sentences(text, refs):
    output = []
    for s in re.split(r'(?<=[.!?])\s+', text):
        src = "Approved material"
        for r in refs:
            if any(w.lower() in r["text"].lower() for w in s.split()[:4]):
                src = r["src"]
                break
        output.append(f"{s}<br><span style='font-size:12px;color:#9cf'>(Source: {src})</span>")
    return "<br>".join(output)

# -------------------------
# GUARDED GENERATION
# -------------------------
def guarded_llm(prompt):
    client = groq_client()
    if not client:
        return "LLM not configured."

    refs = retrieve(prompt, CORPUS, SOURCES)
    if not refs:
        return "⚠️ Not covered in the provided Sales Modules or References."

    context = "\n".join([f"[{r['src']}] {r['text']}" for r in refs])

    final_prompt = f"""
STRICT COMPLIANCE:
- Use ONLY the CONTEXT
- Do NOT add knowledge
- If missing, say so

CONTEXT:
{context}

TASK:
{prompt}
"""

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": final_prompt}],
        temperature=0.3
    )

    return cite_sentences(resp.choices[0].message.content, refs)

# -------------------------
# ROLE PLAY ENGINE
# -------------------------
def roleplay(rep_text):
    persona = st.session_state.persona
    history = "\n".join(st.session_state.roleplay_history[-6:])

    prompt = f"""
You are a healthcare professional persona: {persona}

Conversation:
{history}

Rep says:
{rep_text}

Respond as the HCP only.
"""

    reply = guarded_llm(prompt)
    st.session_state.roleplay_history += [f"REP: {rep_text}", f"HCP: {reply}"]
    return reply

# -------------------------
# SIDEBAR
# -------------------------
with st.sidebar:
    st.header("🔧 Call Configuration")

    brand = st.selectbox("Brand", PRODUCTS.keys(), format_func=lambda x: PRODUCTS[x]["display"])
    st.session_state.brand = brand
    product = PRODUCTS[brand]

    st.caption(f"**Indication:** {product['indication']}")

    st.selectbox("Segment", product["segments"])
    st.selectbox("Objective", product["objectives"])
    st.selectbox("Specialty", product["specialties"])

    st.session_state.persona = st.selectbox("HCP Persona", product["personas"])
    st.selectbox("HCP Personality", ["Friendly", "Assertive", "Skeptical", "Detail-oriented"])
    st.session_state.tone = st.selectbox("Tone", ["executive", "coaching", "persuasive", "clinical"])

    st.toggle("🎭 Call Simulation Mode", key="simulation")

    if st.button("🗑 Clear Session"):
        st.session_state.chat = []
        st.session_state.roleplay_history = []

# -------------------------
# BUILD CORPUS
# -------------------------
CORPUS, SOURCES = build_corpus([product["refs"], product["sales"]])

# -------------------------
# MAIN UI
# -------------------------
st.title(f"💡 {product['display']} — AI Sales Call Assistant")
st.caption("Mode: 🎭 Simulation" if st.session_state.simulation else "Mode: 📋 Advisor")

user_input = st.text_area("Your input")

if st.button("Send") and user_input.strip():
    if st.session_state.simulation:
        reply = roleplay(user_input)
    else:
        reply = guarded_llm(user_input)

    st.session_state.chat.append(("rep", user_input))
    st.session_state.chat.append(("ai", reply))

# -------------------------
# CHAT DISPLAY
# -------------------------
for role, msg in st.session_state.chat:
    if role == "rep":
        st.markdown(f"🧑‍💼 **REP:** {escape(msg)}")
    else:
        st.markdown(f"🩺 **HCP / AI:**<br>{msg}", unsafe_allow_html=True)

# -------------------------
# DISCLAIMER
# -------------------------
st.markdown(
    "<hr><small>Internal use only. Content restricted to approved materials.</small>",
    unsafe_allow_html=True
)
