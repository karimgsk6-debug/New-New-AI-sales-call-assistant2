# app.py — AI Sales Call Assistant (Structured Call Flow + Citations)

import streamlit as st
import os, re, tempfile, base64, io
from datetime import datetime
from html import escape

# Optional libraries
try:
    from groq import Groq
except:
    Groq = None

try:
    from PyPDF2 import PdfReader
except:
    PdfReader = None

try:
    from gtts import gTTS
except:
    gTTS = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except:
    SKLEARN_AVAILABLE = False


# -------------------------
# Page configuration
# -------------------------
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------
# Session defaults
# -------------------------
defaults = {
    "chat_history": [],
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.6,
    "language": "English",
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# -------------------------
# Initialize GROQ
# -------------------------
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY) if Groq and GROQ_API_KEY else None

# -------------------------
# Brand configuration
# -------------------------
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
            "HCP does not consider HZ a risk",
            "No time for discussion",
            "Cost concerns",
            "Not convinced of efficacy"
        ],
        "specialties": ["GP", "Dermatologist", "Geriatrician"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/",
        "call_flow": [
            "Prepare",
            "Engage",
            "Create Opportunities",
            "Influence",
            "Impact GSO",
            "Post-call Analysis"
        ]
    }
}

# -------------------------
# Helpers
# -------------------------
def read_file_text(path):
    if not os.path.exists(path):
        return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except:
        return ""

def build_corpus(folders):
    chunks, metas = [], []
    for folder in folders:
        if not os.path.exists(folder):
            continue
        for f in os.listdir(folder):
            if f.lower().endswith((".pdf", ".txt")):
                text = read_file_text(os.path.join(folder, f))
                sentences = re.split(r'(?<=[.!?])\s+', text)
                for s in sentences:
                    if len(s.strip()) > 40:
                        chunks.append(s.strip())
                        metas.append({"filename": f})
    return chunks, metas

def search_snippets(query, chunks, metas, top_n=5):
    if not SKLEARN_AVAILABLE or not chunks:
        return []
    vectorizer = TfidfVectorizer(stop_words="english")
    vectors = vectorizer.fit_transform(chunks + [query])
    sims = linear_kernel(vectors[-1], vectors[:-1]).flatten()
    top_idx = sims.argsort()[::-1][:top_n]
    return [
        {"text": chunks[i], "meta": metas[i], "score": sims[i]}
        for i in top_idx if sims[i] > 0
    ]

# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    sel_brand = st.selectbox("Brand", list(brand_data.keys()))
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]

    persona = st.selectbox("HCP Persona", bconf["personas"])
    specialty = st.selectbox("Specialty", bconf["specialties"])
    segment = st.selectbox("Segment", bconf["segments"])
    barrier = st.multiselect("Barriers", bconf["barriers"])
    objective = st.selectbox("Objective", ["Awareness", "Adoption", "Retention"])

    st.session_state.temperature = st.slider("Creativity", 0.0, 1.0, 0.6)

    if st.button("Clear Chat"):
        st.session_state.chat_history = []

# -------------------------
# Load knowledge base
# -------------------------
refs_folder = bconf["references_path"]
sales_folder = bconf["sales_path"]
chunks, metas = build_corpus([refs_folder, sales_folder])

# -------------------------
# CORE AI RESPONSE (STRICT STRUCTURE)
# -------------------------
def add_ai_response(user_prompt):
    snippets = search_snippets(user_prompt, chunks, metas)

    citations = []
    for s in snippets:
        citations.append(f"- {s['meta']['filename']} (score {s['score']:.2f})")

    system_prompt = f"""
You are a pharmaceutical sales excellence coach.

ABSOLUTE RULES (DO NOT BREAK):
- Use ONLY these call steps:
{', '.join(bconf['call_flow'])}

FOR EACH STEP:
- Show the step title in **bold**
- Use bullet points
- Write ONLY what the sales rep should SAY to the HCP
- DO NOT explain, define, or describe the step
- DO NOT restate selling models, frameworks, or background theory

CONTENT STYLE:
- Spoken language
- First-person sales rep voice
- Ready to use in a live call
- Short, clear sentences

DO NOT:
- Mention documents, sources, models, or training material
- Rephrase step definitions
"""

    user_context = f"""
Brand: {bconf['display']}
Persona: {persona}
Specialty: {specialty}
Segment: {segment}
Barriers: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}

Request:
{user_prompt}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_context}
            ],
            temperature=st.session_state.temperature
        )
        ai_text = response.choices[0].message.content
    except:
        ai_text = "⚠️ Unable to generate response."

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": ai_text,
        "citation": "\n".join(citations)
    })

# -------------------------
# UI
# -------------------------
st.title(f"AI Sales Call Assistant — {bconf['display']}")

user_input = st.text_area("Ask your question:")
if st.button("Send") and user_input.strip():
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_input
    })
    add_ai_response(user_input)

# -------------------------
# Chat display
# -------------------------
for entry in st.session_state.chat_history:
    if entry["role"] == "user":
        st.markdown(f"🧑‍💼 **You:** {escape(entry['content'])}")
    else:
        st.markdown(f"🤖 **AI Response:**\n\n{entry['content']}")
        if entry.get("citation"):
            st.markdown("📚 **References**")
            st.markdown(entry["citation"])

# -------------------------
# Footer
# -------------------------
st.markdown(
    "<hr><small>Internal use only. Medical content must follow local compliance.</small>",
    unsafe_allow_html=True
)
