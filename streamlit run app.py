# app.py - Full AI Sales Call Assistant (with RAG, UI, Sidebar Segments, Background Image)

import streamlit as st
import os, re, tempfile, base64, io
from datetime import datetime
from html import escape
from PIL import Image

# --------------------------
# IMPORT GROQ
# --------------------------
try:
    from groq import Groq
except:
    Groq = None


# --------------------------
# 1. SETUP GROQ API
# --------------------------
GROQ_API_KEY = "Add_GROQ_API_Here"

client = None
if Groq and GROQ_API_KEY and GROQ_API_KEY != "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":
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except:
        client = None


# ========================================================================
# 2. LOAD FILES FOR RAG (REFERENCES + SALES MODULES)
# ========================================================================

import glob
import nltk
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

nltk.download("punkt", quiet=True)

def load_all_files(base_path):
    data = []
    for file in glob.glob(base_path + "/**/*.*", recursive=True):
        try:
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
                data.append((os.path.basename(file), text))
        except:
            pass
    return data

def split_into_chunks(text, max_words=180):
    words = nltk.word_tokenize(text)
    chunks, current = [], []
    for w in words:
        current.append(w)
        if len(current) >= max_words:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks

def build_vector_db():
    all_docs = []

    reference_paths = [
        ".devcontainer/references/jemperli",
        ".devcontainer/references/shingrix",
        ".devcontainer/references/trelegy"
    ]
    
    sales_paths = [
        ".devcontainer/SalesModule/jemperli",
        ".devcontainer/SalesModule/shingrix",
        ".devcontainer/SalesModule/trelegy"
    ]

    for p in reference_paths + sales_paths:
        for fname, text in load_all_files(p):
            for chunk in split_into_chunks(text):
                all_docs.append(chunk)

    if not all_docs:
        all_docs.append("Empty RAG dataset. No files found.")

    vectorizer = TfidfVectorizer(stop_words="english")
    vectors = vectorizer.fit_transform(all_docs)

    return all_docs, vectorizer, vectors

docs, vectorizer, vectors = build_vector_db()


def search_docs(query, top_k=5):
    if not query.strip():
        return []

    q_vec = vectorizer.transform([query])
    scores = np.dot(vectors, q_vec.T).toarray().ravel()
    top_ids = np.argsort(scores)[::-1][:top_k]
    return [docs[i] for i in top_ids]


# ========================================================================
# 3. GENERATE AI RESPONSE WITH HYBRID RAG (OPTION C)
# ========================================================================

def generate_ai_response(user_input, context_info):
    retrieved = search_docs(user_input, top_k=5)
    rag_text = "\n\n--- Retrieved Relevant Medical & Sales Insights ---\n"
    for idx, chunk in enumerate(retrieved):
        rag_text += f"\n[{idx+1}] {chunk}\n"

    prompt = f"""
You are MR Mentor, an AI Sales Coach for pharmaceutical representatives.

Follow **Hybrid RAG Mode**:
- **Medical accuracy** must come ONLY from retrieved RAG data.
- **Sales coaching** can include your own reasoning.
- **Conversation style** can be natural.
- Never invent medical facts not found in retrieved documents.

--------------------------
HCP & Visit Context:
{context_info}

--------------------------
User Question:
{user_input}

{rag_text}

Now produce:
1. A crisp, structured, high-value answer.
2. Medical claims ONLY from retrieved RAG evidence.
3. Tailored sales guidance based on HCP segment, barriers & specialty.
"""

    if client:
        try:
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}]
            )
            return res.choices[0].message["content"]
        except:
            pass

    return "⚠️ Running in offline/fallback mode — No GROQ response available."


# ========================================================================
# 4. STREAMLIT UI — WHITE CHAT BUBBLES + BACKGROUND IMAGE
# ========================================================================

# Background image
def add_bg():
    image_path = ".devcontainer/Visuals/MR mentor final1.png"
    if os.path.exists(image_path):
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url('data:image/png;base64,{encoded}');
                background-size: cover;
                background-position: right;
                background-repeat: no-repeat;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )

add_bg()

st.markdown(
    """
    <style>
    .user-bubble {
        background: #DCF2FF;
        padding: 12px 18px;
        border-radius: 18px;
        max-width: 78%;
        margin: 8px 0;
        font-size: 16px;
    }
    .ai-bubble {
        background: #FFFFFF;
        padding: 14px 20px;
        border-radius: 18px;
        max-width: 78%;
        margin: 10px 0;
        font-size: 17px;
        border-left: 4px solid #FF6A00;
        box-shadow: 0 0 6px rgba(0,0,0,0.08);
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("💊 MR Mentor — AI Sales Call Assistant")


# ========================================================================
# 5. SIDEBAR — HCP SEGMENT + SPECIALTY + BARRIERS
# ========================================================================

st.sidebar.title("HCP Profile")

hcp_segment = st.sidebar.selectbox(
    "HCP Segment:",
    ["High Value", "Medium Value", "Low Value", "New to Brand"]
)

hcp_specialty = st.sidebar.selectbox(
    "Specialty:",
    ["GP", "Dermatology", "Oncology", "Immunology", "Pulmonology", "Other"]
)

hcp_barriers = st.sidebar.multiselect(
    "HCP Barriers:",
    ["Lack of Awareness", "Safety Concerns", "Efficacy Doubts", "Too Busy", 
     "Cost Concerns", "Prefers Competitor", "No Time for Reps"]
)

persona = st.sidebar.selectbox(
    "Persona:",
    ["Analytical", "Skeptical", "Supportive", "Passive", "Time-Pressed"]
)

behavior_type = st.sidebar.selectbox(
    "Behavior Type:",
    ["Early Adopter", "Follower", "Skeptic", "Unengaged"]
)

objection_type = st.sidebar.selectbox(
    "Objection Type:",
    ["Clinical", "Safety", "Cost", "Access", "Time", "Other"]
)

visit_type = st.sidebar.selectbox(
    "Visit Type:",
    ["Detailing Visit", "Follow-Up Visit", "Objection Handling", "Awareness Visit"]
)

engagement = st.sidebar.select_slider(
    "Engagement Level:",
    ["Very Low", "Low", "Medium", "High", "Very High"]
)


# ========================================================================
# 6. MAIN CHAT INTERFACE
# ========================================================================

if "history" not in st.session_state:
    st.session_state.history = []

user_msg = st.text_input("Ask MR Mentor something...")

if user_msg:
    context = f"""
    Segment: {hcp_segment}
    Specialty: {hcp_specialty}
    Barriers: {', '.join(hcp_barriers) if hcp_barriers else 'None'}
    Persona: {persona}
    Behavior: {behavior_type}
    Objection: {objection_type}
    Visit Type: {visit_type}
    Engagement: {engagement}
    """

    ai_answer = generate_ai_response(user_msg, context)

    st.session_state.history.append(("user", user_msg))
    st.session_state.history.append(("ai", ai_answer))


# Display chat
st.markdown("### Conversation")
for role, msg in st.session_state.history:
    if role == "user":
        st.markdown(f"<div class='user-bubble'>{escape(msg)}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='ai-bubble'>{msg}</div>", unsafe_allow_html=True)
