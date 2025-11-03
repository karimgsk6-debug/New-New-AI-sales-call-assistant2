# app.py - AI Sales Call Assistant (FINAL, integrated, ready-to-use)

import streamlit as st
import os, io, tempfile, base64, re
from datetime import datetime
from html import escape
import requests

# Optional libs
try:
    from PyPDF2 import PdfReader
except:
    PdfReader = None

try:
    from gtts import gTTS
except:
    gTTS = None

try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# GROQ API configuration (insert your key)
# -------------------------
GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.ai/v1/llm"

# -------------------------
# Session defaults & multi‑brand storage
# -------------------------
defaults = {
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.62,
    "search_mode": "deep",
    "language": "English",
    "reply_style": "balanced",
    "pdf_docs": {},           # brand -> combined text
    "pdf_summaries": {},      # brand -> summary string
    "feedback_stats": {},     # brand -> dict like {"like":0,"dislike":0,"need_more":0}
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# chat_history per brand
if "chat_history" not in st.session_state:
    st.session_state.chat_history = {}  # dict: brand -> list of messages

# -------------------------
# Brand definitions
# -------------------------
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "personas": ["GP", "Dermatologist", "Pharmacist"],
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "barriers": ["Cost", "Awareness", "Side Effects", "Efficacy doubts"],
        "specialties": ["General Practice", "Dermatology", "Geriatrics"]
    },
    "jemperli": {
        "display": "Jemperli",
        "personas": ["Oncologist", "Gynecologist", "Medical Oncologist"],
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "barriers": ["Safety", "Guideline familiarity", "Access", "Reimbursement"],
        "specialties": ["Oncology", "Gynecology"]
    },
    "trelegy": {
        "display": "Trelegy",
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "barriers": ["Formulary access", "Inhaler technique", "Side effect concerns", "Cost/coverage"],
        "specialties": ["Pulmonology", "Respiratory"]
    }
}

# -------------------------
# Utility functions
# -------------------------
def read_file_text_from_uploaded(uploaded_file):
    try:
        if uploaded_file.type and "pdf" in uploaded_file.type and PdfReader:
            reader = PdfReader(uploaded_file)
            return "\n".join([p.extract_text() or "" for p in reader.pages])
        else:
            return uploaded_file.getvalue().decode("utf-8", errors="ignore")
    except Exception:
        return ""

def model_summarize(text: str, bullets: int = 6) -> str:
    if not text:
        return ""
    sents = re.split(r'(?<=[\.!\?])\s+', text)
    top = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join([f"- {s}" for s in top])

def generate_audio_base64(text: str) -> str:
    if not text or not gTTS:
        return ""
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=text, lang="en", slow=False).save(tmp.name)
        with open(tmp.name, "rb") as fh:
            return base64.b64encode(fh.read()).decode("utf-8")
    except Exception:
        return ""

def export_chat_to_docx(brand: str):
    hist = st.session_state.chat_history.get(brand, [])
    doc = Document()
    doc.add_heading(f"AI Sales Call Assistant – {brand_data[brand]['display']}", 0)
    doc.add_paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    # PDF summary
    if brand in st.session_state.pdf_summaries:
        doc.add_heading("Uploaded Document Summary", level=1)
        doc.add_paragraph(st.session_state.pdf_summaries[brand])
    # Chat transcript
    doc.add_heading("Conversation & AI Output", level=1)
    for msg in hist:
        role = msg.get("role", "")
        text = msg.get("text", "")
        doc.add_heading(role.capitalize(), level=2)
        doc.add_paragraph(text)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    doc.save(tmp.name)
    return tmp.name

def build_corpus_for_brands():
    # Combine uploaded docs into one corpus list for retrieval
    corp = []
    for b, txt in st.session_state.pdf_docs.items():
        if txt:
            corp.append(txt)
    return corp

def query_groq_safe(prompt: str, context_docs: list, max_tokens: int = 700):
    if not GROQ_API_KEY or GROQ_API_KEY == "Add_GROQ_API_Here":
        return None
    context_text = "\n\n".join(context_docs)
    payload = {
        "prompt": f"Use context material and respond to the user prompt with structured, example-driven sales flow.\n\nContext:\n{context_text}\n\nUser Prompt:\n{prompt}",
        "max_output_tokens": max_tokens
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    try:
        r = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        resp = r.json()
        out = resp.get("output_text") or resp.get("result") or resp.get("text")
        return out
    except Exception as e:
        st.session_state["groq_unavailable"] = True
        return None

# -------------------------
# Sidebar: Uploads, brand filters, export/clear
# -------------------------
with st.sidebar:
    st.title("Sidebar Controls")
    sel_brand = st.selectbox("Select Brand", list(brand_data.keys()), format_func=lambda k: brand_data[k]["display"])
    persona = st.selectbox("HCP Persona", brand_data[sel_brand]["personas"])
    segment = st.selectbox("Segment", brand_data[sel_brand]["segments"])
    barrier = st.multiselect("Doctor Barriers", brand_data[sel_brand]["barriers"])
    specialty = st.selectbox("Specialty", brand_data[sel_brand]["specialties"])
    objective = st.selectbox("Objective", ["Awareness","Adoption","Retention"])

    st.markdown("---")
    st.subheader("Upload Document")
    uploaded = st.file_uploader("Upload PDF/TXT for this brand", type=["pdf","txt"], key=f"upload_{sel_brand}")
    if uploaded:
        txt = read_file_text_from_uploaded(uploaded)
        if txt:
            st.session_state.pdf_docs.setdefault(sel_brand, "")
            st.session_state.pdf_docs[sel_brand] += "\n\n" + txt
            st.session_state.pdf_summaries[sel_brand] = model_summarize(st.session_state.pdf_docs[sel_brand])
            st.success("Document uploaded and summarized.")
        else:
            st.error("Failed to read uploaded document.")

    st.markdown("---")
    st.subheader("Brand Tools")
    if st.button(f"Clear {brand_data[sel_brand]['display']} Chat"):
        st.session_state.chat_history[sel_brand] = []
        st.session_state.feedback_stats[sel_brand] = {"like":0,"dislike":0,"need_more":0}
        st.experimental_rerun()

    if DOCX_AVAILABLE:
        if st.button(f"Export {brand_data[sel_brand]['display']} DOCX"):
            path = export_chat_to_docx(sel_brand)
            with open(path, "rb") as f:
                st.download_button("Download DOCX", f, file_name=f"{brand_data[sel_brand]['display']}_Session.docx")

# -------------------------
# Copilot suggestions & input
# -------------------------
def make_suggestions(brand_key, persona, barrier_list, segment, specialty, objective):
    s = []
    s.append("Generate sales call")
    s.append(f"Call flow for {persona} focusing {objective}")
    if barrier_list:
        s.append(f"Handle objection: {', '.join(barrier_list[:2])}")
    s.append(f"Quick adoption message for {brand_data[brand_key]['display']} to {specialty}")
    s.append("Short role-play example")
    return s

copilot_suggestions = make_suggestions(sel_brand, persona, barrier, segment, specialty, objective)

st.header(f"AI Sales Call Assistant — {brand_data[sel_brand]['display']}")
st.write("Suggestion Pills:")
for pill in copilot_suggestions:
    if st.button(pill, key=f"sugg_{pill}"):
        st.session_state.main_input = pill

user_input = st.text_area("Your message", value=st.session_state.main_input, height=80)
if st.button("Send"):
    msg = user_input.strip()
    if msg:
        # Build context docs
        context_docs = list(st.session_state.pdf_docs.values())
        # Query GROQ if possible
        groq_resp = query_groq_safe(msg, context_docs)
        ai_output = None
        if groq_resp:
            ai_output = groq_resp
        else:
            # fallback simple generation
            ai_output = generate_structured_sales_call(sel_brand, persona, specialty, objective)
        # Append to chat
        st.session_state.chat_history.setdefault(sel_brand, [])
        st.session_state.chat_history[sel_brand].append({"role":"user","text":msg})
        # AI response with optional audio
        audio_b64 = generate_audio_base64(ai_output)
        st.session_state.chat_history[sel_brand].append({"role":"assistant","text":ai_output,"audio_b64":audio_b64})
        # Ensure feedback stats initialized
        st.session_state.feedback_stats.setdefault(sel_brand, {"like":0,"dislike":0,"need_more":0})
        st.session_state.main_input = ""
        st.experimental_rerun()

# -------------------------
# Display chat & feedback
# -------------------------
if sel_brand in st.session_state.chat_history:
    for idx, msg in enumerate(st.session_state.chat_history[sel_brand]):
        role = msg.get("role", "")
        text = msg.get("text", "")
        if role == "user":
            st.markdown(f"**You:** {text}")
        else:
            st.markdown(f"**Assistant:** {text}")
            if msg.get("audio_b64"):
                st.audio(io.BytesIO(base64.b64decode(msg["audio_b64"])), format="audio/mp3")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("👍 Like", key=f"like_{sel_brand}_{idx}"):
                    st.session_state.feedback_stats[sel_brand]["like"] += 1
            with c2:
                if st.button("👎 Dislike", key=f"dislike_{sel_brand}_{idx}"):
                    st.session_state.feedback_stats[sel_brand]["dislike"] += 1
            with c3:
                if st.button("🔄 Need more", key=f"more_{sel_brand}_{idx}"):
                    st.session_state.feedback_stats[sel_brand]["need_more"] += 1

# -------------------------
# Multi-brand dashboard
# -------------------------
st.markdown("---")
st.subheader("📊 Multi‑Brand Dashboard")
for bkey, binfo in brand_data.items():
    chats = st.session_state.chat_history.get(bkey, [])
    chat_pairs = len(chats) // 2
    pdf_uploaded = bkey in st.session_state.pdf_docs and bool(st.session_state.pdf_docs[bkey].strip())
    summary = "Yes" if pdf_uploaded else "No"
    fb = st.session_state.feedback_stats.get(bkey, {"like":0,"dislike":0,"need_more":0})
    st.markdown(f"**{binfo['display']}**: Chats ≈ {chat_pairs}, PDF Uploaded: {summary}, 👍 {fb['like']} 👎 {fb['dislike']} 🔄 {fb['need_more']}")

# -------------------------
# Sticky disclaimer
# -------------------------
st.markdown("""
<div style="
position:fixed;
bottom:10px;
left:10px;
right:10px;
background:white;
padding:8px;
border:1px solid #ccc;
border-radius:6px;
box-shadow:0 2px 8px rgba(0,0,0,0.1);
text-align:center;
font-size:12px;">
⚠️ Internal tool— outputs are based on uploaded references and AI model. Always validate clinical & compliance content before use.
</div>
""", unsafe_allow_html=True)
