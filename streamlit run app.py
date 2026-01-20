# app.py — AI Sales Call Assistant (Simulation Call Mode)

import streamlit as st
import os, re
from html import escape

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
    SKLEARN_AVAILABLE = True
except:
    SKLEARN_AVAILABLE = False

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# -------------------------
# Session defaults
# -------------------------
defaults = {
    "chat_history": [],
    "selected_brand": "shingrix",
    "temperature": 0.6,
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# -------------------------
# GROQ init
# -------------------------
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY) if Groq and GROQ_API_KEY else None

# -------------------------
# Brand config
# -------------------------
brand_data = {
    "shingrix": {
        "display": "Shingrix",
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
            "Post-call Close"
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
        if path.endswith(".pdf") and PdfReader:
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
            if f.endswith((".pdf", ".txt")):
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
    idxs = sims.argsort()[::-1][:top_n]
    return [
        {"text": chunks[i], "meta": metas[i], "score": sims[i]}
        for i in idxs if sims[i] > 0
    ]

# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    sel_brand = st.selectbox("Brand", list(brand_data.keys()))
    bconf = brand_data[sel_brand]

    persona = st.selectbox("HCP Persona", bconf["personas"])
    specialty = st.selectbox("Specialty", bconf["specialties"])
    barrier = st.multiselect("Barriers", bconf["barriers"])
    objective = st.selectbox("Objective", ["Awareness", "Adoption", "Activation"])

    if st.button("Clear Chat"):
        st.session_state.chat_history = []

# -------------------------
# Load knowledge
# -------------------------
chunks, metas = build_corpus([
    bconf["references_path"],
    bconf["sales_path"]
])

# -------------------------
# AI RESPONSE — SIMULATION CALL ONLY
# -------------------------
def add_ai_response(user_prompt):
    snippets = search_snippets(user_prompt, chunks, metas)

    citations = [
        f"- {s['meta']['filename']} (score {s['score']:.2f})"
        for s in snippets
    ]

    system_prompt = f"""
You are a pharmaceutical sales representative.

TASK:
Generate a REALISTIC SALES CALL SIMULATION.

STRICT RULES (MANDATORY):
- Use ONLY these step titles:
{', '.join(bconf['call_flow'])}

- Under EACH step:
  - Write bullet points
  - Each bullet is a SENTENCE THE REP SAYS to the HCP
  - Spoken, natural, field-ready language

ABSOLUTELY FORBIDDEN:
- Selling model explanations
- Training or coaching language
- Step definitions
- Framework names
- Pharma vs vaccine comparisons
- Background theory

DO NOT explain anything.
DO NOT educate the reader.
ONLY simulate the call dialogue.
"""

    user_context = f"""
Brand: {bconf['display']}
Persona: {persona}
Specialty: {specialty}
Barriers: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}

User request:
{user_prompt}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_context}
            ],
            temperature=0.6
        )
        ai_text = response.choices[0].message.content
    except:
        ai_text = "⚠️ Unable to generate simulation."

    st.session_state.chat_history.append({
        "role": "assistant",
        "content": ai_text,
        "citation": "\n".join(citations)
    })

# -------------------------
# UI
# -------------------------
st.title(f"AI Sales Call Simulation — {bconf['display']}")

user_input = st.text_area("What do you want to simulate?")
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
        st.markdown(entry["content"])
        if entry.get("citation"):
            st.markdown("📚 **References**")
            st.markdown(entry["citation"])

# -------------------------
# Footer
# -------------------------
st.markdown(
    "<hr><small>Internal use only – promotional content must follow local compliance.</small>",
    unsafe_allow_html=True
)
