# app.py - AI Sales Call Assistant (Structured Steps + Citations at Bottom)

import streamlit as st
import os, re, tempfile, base64, io
from datetime import datetime
from html import escape

# -------------------------
# Optional Libraries
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
# Page config
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
        "call_flow": [
            "Prepare",
            "Engage",
            "Create Opportunities",
            "Influence",
            "Impact GSO",
            "Post-call Analysis"
        ],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/"
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
            return "".join(p.extract_text() or "" for p in reader.pages)
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except:
        return ""

def build_corpus(folders):
    chunks, metas = [], []
    for folder in folders:
        if not os.path.exists(folder):
            continue
        for file in os.listdir(folder):
            if not file.lower().endswith((".txt", ".pdf")):
                continue
            text = read_file_text(os.path.join(folder, file))
            sentences = re.split(r'(?<=[.!?])\s+', text)
            for s in sentences:
                if len(s.strip()) > 40:
                    chunks.append(s.strip())
                    metas.append(file)
    return chunks, metas

def search_snippets(query, chunks, metas, top_n=5):
    results = []
    if SKLEARN_AVAILABLE and chunks:
        vectorizer = TfidfVectorizer(stop_words="english")
        X = vectorizer.fit_transform(chunks + [query])
        scores = linear_kernel(X[-1], X[:-1]).flatten()
        top_idx = scores.argsort()[::-1][:top_n]
        for i in top_idx:
            if scores[i] > 0:
                results.append((chunks[i], metas[i], scores[i]))
    return results

# -------------------------
# AI RESPONSE (REWRITTEN)
# -------------------------
def add_ai_response(user_prompt, follow_up=False):

    brand = brand_data[st.session_state.selected_brand]
    call_flow = brand["call_flow"]

    # Retrieve knowledge
    folders = [brand["references_path"], brand["sales_path"]]
    chunks, metas = build_corpus(folders)
    snippets = search_snippets(user_prompt, chunks, metas)

    # Prepare citations
    citation_files = sorted(set(m for _, m, _ in snippets))

    # -------------------------
    # Build structured response
    # -------------------------
    response = []

    response.append("**Structured Call Guidance**")
    response.append("")

    for step in call_flow:
        response.append(f"**{step}**")
        matched = [
            s for s, _, _ in snippets
            if step.lower() in s.lower()
        ]

        if matched:
            for m in matched[:2]:
                response.append(f"- {m}")
        else:
            response.append(
                "- Apply standard brand-aligned messaging and adapt based on HCP reaction."
            )

        response.append("")

    response.append("**Next Step**")
    response.append(
        "- Confirm alignment with the HCP and transition to the agreed objective."
    )

    # -------------------------
    # Save to chat history
    # -------------------------
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": "\n".join(response),
        "citations": citation_files
    })

# -------------------------
# UI
# -------------------------
st.title("💡 AI Sales Call Assistant")

user_input = st.text_area("Ask your question")
if st.button("Send") and user_input.strip():
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_input
    })
    add_ai_response(user_input)

# -------------------------
# Chat rendering
# -------------------------
for entry in st.session_state.chat_history:
    if entry["role"] == "user":
        st.markdown(
            f"<div style='background:#0078D7;color:white;padding:10px;border-radius:10px;margin:6px 0;'>"
            f"{escape(entry['content'])}</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div style='background:#eef9ff;padding:12px;border-radius:10px;margin:6px 0;'>"
            f"{escape(entry['content'])}</div>",
            unsafe_allow_html=True
        )

        if entry.get("citations"):
            st.markdown(
                "<div style='font-size:13px;margin-top:6px;border-left:4px solid #0078D7;padding-left:8px;'>"
                "<b>Sources & References</b><br>"
                + "<br>".join(entry["citations"])
                + "</div>",
                unsafe_allow_html=True
            )
