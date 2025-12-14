# app_final_merged_fixed.py - Fully merged AI Sales Call Assistant (Hologram avatar, personas, tones, objections)
import streamlit as st
import os
import re
import tempfile
import base64
import io
from datetime import datetime
from html import escape

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
# Session state initialization (safe)
# -------------------------
def init_session_state():
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
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

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
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"

# -------------------------
# CSS
# -------------------------
st.markdown(
    """
    <style>
    .title-box{ background: rgba(255,255,255,0.85); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; position:relative; margin-bottom:12px; }
    .title-box img.left-logo{ position:absolute; left:12px; height:48px; }
    .title-box img.right-logo{ position:absolute; right:12px; height:48px; }
    .chat-bubble-user{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }
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
# Background
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
# GROQ loader
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
# Brand data
# -------------------------
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "specialties": ["GP", "Dermatologist", "Cardiology", "Endocrinology", "Immunology", "Internal Medicine", "Rheumatology"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/",
        "call_flow": ["Prepare", "Engage", "Create Opportunities", "Influence", "Impact GSO", "Analyze"],
        "objections": {
            "efficacy": "Focus on durable protection and age-agnostic efficacy evidence.",
            "safety": "Acknowledge common AEs, then contrast with risk of complications from shingles.",
            "cost": "Frame cost as prevention of downstream complications and reduce clinic workload."
        }
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited eligibility", "Access/reimbursement issues"],
        "specialties": ["Oncologist", "Medical Oncologist"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli/",
        "call_flow": ["COCO", "Anchor", "Engage", "Close"],
        "objections": {
            "efficacy": "Discuss durable responses in dMMR/MSI-H and appropriate patient selection.",
            "safety": "Share safety profile and monitoring guidance to reduce perceived risk.",
            "access": "Offer starter kits or initiation support and reimbursement pathways."
        }
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Side effect concerns", "Cost/coverage"],
        "specialties": ["GP", "Pulmonologist", "Internal Medicine", "Respiratory Specialist"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy/",
        "call_flow": ["Prepare", "Engage", "Demonstrate", "Address Access", "Close"],
        "objections": {
            "device": "Offer quick practical coaching and demo materials.",
            "coverage": "Explain access options and patient support programs.",
            "effectiveness": "Share comparative outcomes framed for real-world practice."
        }
    }
}

EXTRA_PERSONAS = ["Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"]
def get_persona_options(brand_key):
    base = brand_data.get(brand_key, {}).get("personas", [])
    combined = base + [p for p in EXTRA_PERSONAS if p not in base]
    return combined

# -------------------------
# File reading, corpus, summarization helpers
# -------------------------
def read_file_text(path):
    if not os.path.exists(path):
        return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()
    except Exception:
        return ""

def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas = [], []
    for folder in folders:
        if not folder or not os.path.exists(folder):
            continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf", ".txt"))]
        for fname in files:
            p = os.path.join(folder, fname)
            text = read_file_text(p)
            if not text:
                continue
            sents = re.split(r'(?<=[\.\?\!])\s+', text)
            for i in range(0, max(1, len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i : i + chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename": fname, "folder": folder, "start": i})
    return chunks, metas

def local_search_snippets(query, chunks, metas, top_n=3):
    if not chunks:
        return []
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks + [query])
            chunk_vecs = vectorizer.transform(chunks)
            q_vec = vectorizer.transform([query])
            sims = linear_kernel(q_vec, chunk_vecs).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            results = []
            for idx in top_idxs:
                if sims[idx] <= 0:
                    continue
                results.append({"score": float(sims[idx]), "text": chunks[idx], "meta": metas[idx]})
            return results
        except Exception:
            pass
    out = []
    q = query.lower()
    for i, c in enumerate(chunks):
        if q in c.lower():
            out.append({"score": 1.0, "text": c, "meta": metas[i]})
            if len(out) >= top_n:
                break
    return out

def simple_summary(text, bullets=6):
    if not text:
        return ""
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- " + s for s in selected])

def model_summarize(text, bullets=6):
    if not text:
        return ""
    client = load_groq_client()
    if client:
        try:
            prompt = f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                                 messages=[{"role":"user","content":prompt}],
                                                 temperature=0.2)
            content = getattr(resp.choices[0].message, "content", None) or getattr(resp.choices[0], "text", "")
            return content
        except Exception:
            return simple_summary(text, bullets)
    else:
        return simple_summary(text, bullets)
# -------------------------
# PDF upload and summary
# -------------------------
st.sidebar.header("Upload Reference Material (PDF/TXT)")
uploaded_file = st.sidebar.file_uploader("Upload a PDF or TXT", type=["pdf", "txt"])
if uploaded_file:
    try:
        bytes_data = uploaded_file.read()
        temp_path = os.path.join(tempfile.gettempdir(), uploaded_file.name)
        with open(temp_path, "wb") as f:
            f.write(bytes_data)
        text = read_file_text(temp_path)
        st.session_state.uploaded_pdf_text = text
        st.session_state.pdf_summary = model_summarize(text)
        st.sidebar.success(f"File '{uploaded_file.name}' uploaded and summarized.")
    except Exception as e:
        st.sidebar.error(f"Failed to process file: {e}")

# -------------------------
# Sidebar controls
# -------------------------
st.sidebar.header("Settings / Persona / Tone")
st.session_state.selected_brand = st.sidebar.selectbox(
    "Select Brand",
    list(brand_data.keys()),
    index=list(brand_data.keys()).index(st.session_state.selected_brand)
)
st.session_state.hcp_persona = st.sidebar.selectbox(
    "HCP Persona",
    get_persona_options(st.session_state.selected_brand),
    index=0
)
st.session_state.tone = st.sidebar.selectbox(
    "Tone",
    ["Friendly", "Executive", "Scientific", "Empathetic"],
    index=0
)
st.session_state.temperature = st.sidebar.slider("Response Creativity", 0.0, 1.0, st.session_state.temperature, 0.05)
st.session_state.search_mode = st.sidebar.radio("Search Mode", ["shallow", "deep"], index=1)

# -------------------------
# Chat input
# -------------------------
st.header("💬 AI Sales Call Assistant")
main_input = st.text_input("Type your question or message here:", value=st.session_state.main_input, key="main_input")
submit_pressed = st.button("Send")

if submit_pressed and main_input.strip():
    # Append user input to chat history
    st.session_state.chat_history.append({"role": "user", "content": main_input.strip()})
    st.session_state.main_input = ""  # Clear input

    # -------------------------
    # Prepare AI response
    # -------------------------
    user_query = main_input.strip()
    brand_info = brand_data.get(st.session_state.selected_brand, {})
    
    # Get reference snippets
    reference_folders = [brand_info.get("references_path", ""), brand_info.get("sales_path", "")]
    chunks, metas = build_corpus_for_folders(reference_folders)
    if st.session_state.uploaded_pdf_text:
        chunks.append(st.session_state.uploaded_pdf_text)
        metas.append({"filename": uploaded_file.name if uploaded_file else "uploaded_file", "folder": "uploaded"})

    relevant_snippets = local_search_snippets(user_query, chunks, metas, top_n=3)
    snippet_text = "\n\n".join([f"{s['text']}" for s in relevant_snippets]) if relevant_snippets else ""

    # Construct prompt for AI
    ai_prompt = f"""
You are a pharmaceutical sales assistant AI.
Brand: {st.session_state.selected_brand}
HCP Persona: {st.session_state.hcp_persona}
Tone: {st.session_state.tone}
Temperature: {st.session_state.temperature}

User Question:
{user_query}

Relevant references:
{snippet_text}

Provide a concise, actionable sales response. Format key points as bullets.
"""
    # -------------------------
    # Generate AI Response
    # -------------------------
    client = load_groq_client()
    ai_response = ""
    try:
        if client:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":ai_prompt}],
                temperature=st.session_state.temperature
            )
            ai_response = getattr(resp.choices[0].message, "content", None) or getattr(resp.choices[0], "text", "")
        else:
            ai_response = simple_summary(snippet_text or user_query, bullets=4)
    except Exception:
        ai_response = simple_summary(snippet_text or user_query, bullets=4)

    # Append AI response to history
    st.session_state.chat_history.append({"role": "assistant", "content": ai_response})

# -------------------------
# Chat rendering
# -------------------------
for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        st.markdown(f'<div class="user-bubble">{escape(msg["content"])}</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            f"""
            <div class="ai-message">
                <img src="{AI_AVATAR}" class="ai-avatar"/>
                <div class="ai-bubble">{escape(msg["content"])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# -------------------------
# Clear chat / reset
# -------------------------
if st.button("Clear Chat"):
    st.session_state.chat_history = []
    st.session_state.main_input = ""
    st.experimental_rerun()

# -------------------------
# Optional: Feedback / Like / Dislike
# -------------------------
st.sidebar.header("Feedback")
like = st.sidebar.button("👍 Like")
dislike = st.sidebar.button("👎 Dislike")
if like:
    st.session_state.feedback[len(st.session_state.chat_history)-1] = "like"
if dislike:
    st.session_state.feedback[len(st.session_state.chat_history)-1] = "dislike"

# -------------------------
# Footer / Disclaimer
# -------------------------
st.markdown(
    """
    <div class="fixed-disclaimer">
    ⚠️ This AI tool provides guidance for sales discussions. Verify clinical and local regulations before use.
    </div>
    """,
    unsafe_allow_html=True
)
