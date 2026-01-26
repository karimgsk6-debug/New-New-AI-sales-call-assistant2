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
