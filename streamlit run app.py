# app.py - AI Sales Call Assistant (Full Merged with GROQ API & Enhancements)
import streamlit as st
import os, re, io, tempfile, base64
from datetime import datetime
from html import escape
import requests

# Optional libraries
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

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except:
    SKLEARN_AVAILABLE = False

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# GROQ API Config
# -------------------------
GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.ai/v1/llm"

# -------------------------
# Session defaults
# -------------------------
defaults = {
    "chat_history": [],
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.62,
    "search_mode": "deep",
    "language": "English",
    "reply_style": "balanced",
    "awaiting_style_pref": False,
    "pdf_docs": {},
    "pdf_summaries": {},
    "feedback_stats": {"like": 0, "dislike": 0, "need_more": 0},
    "module_filters": [],
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# Nested dicts
for nk in ("medical_summary", "sales_summary", "pdf_summary", "feedback"):
    if nk not in st.session_state or not isinstance(st.session_state[nk], dict):
        st.session_state[nk] = {}

# -------------------------
# Brand & Repo config
# -------------------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
BACKGROUND_URL = REPO_RAW_BASE + "/background1.png"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

brand_data = {
    "shingrix": {
        "display":"Shingrix",
        "segments":["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas":["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers":["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
        "specialties":["GP","Dermatologist","Geriatrician"],
        "references_path":".devcontainer/references/shingrix/",
        "sales_path":".devcontainer/SalesModule/shingrix/",
        "call_flow":["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Post-call Analysis"]
    },
    "jemperli": {
        "display":"Jemperli",
        "segments":["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas":["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers":["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties":["Oncologist","Medical Oncologist"],
        "references_path":".devcontainer/references/jemperli/",
        "sales_path":".devcontainer/SalesModule/jemperli/",
        "call_flow":["COCO","Anchor","Engage","Close"]
    },
    "trelegy": {
        "display":"Trelegy",
        "segments":["Awareness","Diagnosis","Adoption","Adherence"],
        "personas":["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers":["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties":["GP","Pulmonologist","Respiratory Specialist"],
        "references_path":".devcontainer/references/trelegy/",
        "sales_path":".devcontainer/SalesModule/trelegy/",
        "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"]
    }
}

# -------------------------
# CSS styling
# -------------------------
st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}}
.chat-bubble-user{{background: linear-gradient(90deg,#0078D7,#0066C8); color:white; padding:12px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto;}}
.chat-bubble-ai{{background: linear-gradient(90deg,#eef9ff,#e6f4ff); color:#000; padding:12px; border-radius:12px; margin:8px 0; max-width:78%;}}
.feedback-row{{display:flex; gap:8px; margin-top:8px; align-items:center;}}
.feedback-btn{{background:#fff; border:1px solid #e6e9ee; padding:6px 10px; border-radius:8px; cursor:pointer;}}
.combined-fixed{{position: fixed; left:20px; right:20px; bottom:18px; z-index:9999; background: rgba(255,255,255,0.98); padding:12px; border-radius:10px;}}
.resizable-combined{{resize: vertical; overflow: auto; border:1px solid #ddd; padding:10px; border-radius:8px; background:#fff; min-height:110px; max-height:400px;}}
.suggestion-pill{{display:inline-block; padding:6px 12px; border-radius:20px; background:#f6f8fa; margin:4px; border:1px solid #e6e9ee; font-size:14px;}}
.fixed-disclaimer{{position: fixed; left:0; right:0; bottom:0; background: rgba(255,255,255,0.7); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:13px; z-index:9997;}}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Helper functions
# -------------------------
def read_file_text(path_or_file):
    try:
        if hasattr(path_or_file, "read"):
            if "pdf" in getattr(path_or_file, "type","") and PdfReader:
                reader = PdfReader(path_or_file)
                return "".join([p.extract_text() or "" for p in reader.pages])
            elif path_or_file.type == "text/plain":
                return path_or_file.read().decode("utf-8", errors="ignore")
        elif os.path.exists(path_or_file):
            if path_or_file.lower().endswith(".pdf") and PdfReader:
                reader = PdfReader(path_or_file)
                return "".join([p.extract_text() or "" for p in reader.pages])
            else:
                with open(path_or_file,"r",encoding="utf-8", errors="ignore") as fh:
                    return fh.read()
    except Exception:
        return ""

def simple_summary(text, bullets=6):
    sents = re.split(r'(?<=[.!?])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join([f"- {s}" for s in selected])

def generate_audio_base64(text):
    if not text or not gTTS:
        return ""
    tts_text = re.sub(r'\n\s*\n', ' ... ', text).replace("\n"," ")
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=tts_text, lang="en", slow=False).save(tmp.name)
        with open(tmp.name, "rb") as fh:
            return base64.b64encode(fh.read()).decode("utf-8")
    except Exception:
        return ""

def query_groq(prompt, context_docs):
    context_text = "\n\n".join(context_docs)
    payload = {
        "prompt": f"Use the following reference material to answer user query. Only show AI response, no references.\n\nReferences:\n{context_text}\n\nUser question: {prompt}",
        "max_output_tokens": 600
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    try:
        r = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json().get("output_text","Sorry, could not generate response.")
    except Exception as e:
        return f"Error querying GROQ API: {e}"

# -------------------------
# Sidebar: Brand selection, filters, PDF upload
# -------------------------
with st.sidebar:
    st.image(GSK_LOGO_RAW, width=150)
    st.subheader("Brand & Filters")
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state["selected_brand"]), format_func=lambda k: brand_data[k]["display"])
    st.session_state["selected_brand"] = sel_brand
    bconf = brand_data[sel_brand]

    # Filters
    persona = st.selectbox("HCP Persona", bconf.get("personas", []))
    segment = st.selectbox("Segment", bconf.get("segments", []))
    barrier = st.multiselect("Doctor Barrier", bconf.get("barriers", []))
    specialty = st.selectbox("Specialty", bconf.get("specialties", []))
    objective = st.selectbox("Objective", ["Awareness","Adoption","Retention"])
    st.session_state["temperature"] = st.slider("Temperature", 0.0,1.0, st.session_state["temperature"],0.05)
    st.session_state["search_mode"] = st.selectbox("Search mode", ["deep","shallow"])
    st.session_state["language"] = st.radio("Language", ["English","Arabic"])

    # Upload PDF/TXT
    with st.expander("Upload PDF/TXT (brand-specific)"):
        uploaded_file = st.file_uploader("Upload file", type=["pdf","txt"], key="sidebar_upload")
        if uploaded_file:
            text = read_file_text(uploaded_file)
            st.session_state["pdf_docs"][sel_brand] = text
            st.session_state["pdf_summaries"][sel_brand] = simple_summary(text)
            st.success("File summarized for this brand.")

    # Clear chat
    st.markdown("---")
    if st.button("🗑️ Clear Chat"):
        st.session_state["chat_history"] = []
        st.session_state["feedback"] = {}

# -------------------------
# Header
# -------------------------
st.markdown(f"""
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
<img src="{GSK_LOGO_RAW}" style="height:56px;">
<h1 style="margin:0">💡 AI Sales Call Assistant — {brand_data[sel_brand]['display']}</h1>
<img src="{AI_LOGO_RAW}" style="height:56px;">
</div>
""", unsafe_allow_html=True)

# -------------------------
# Build reference corpus
# -------------------------
refs_folder = brand_data[sel_brand]["references_path"]
sales_folder = brand_data[sel_brand]["sales_path"]
corpus_docs = []

for folder in [refs_folder, sales_folder]:
    if os.path.exists(folder):
        for f in sorted(os.listdir(folder)):
            if f.lower().endswith((".pdf",".txt")):
                corpus_docs.append(read_file_text(os.path.join(folder,f)))

# Include uploaded PDFs
if sel_brand in st.session_state["pdf_docs"]:
    corpus_docs.append(st.session_state["pdf_docs"][sel_brand])

# -------------------------
# Chat input + AI response
# -------------------------
def add_ai_response(user_prompt):
    response_text = query_groq(user_prompt, corpus_docs)
    audio_b64 = generate_audio_base64(response_text)
    st.session_state["chat_history"].append({"role":"assistant","text":response_text,"audio_b64":audio_b64})

# -------------------------
# Display chat
# -------------------------
st.markdown('<div style="max-height:56vh; overflow-y:auto;">', unsafe_allow_html=True)
for idx, entry in enumerate(st.session_state["chat_history"]):
    role = entry.get("role")
    text = entry.get("text","")
    if role=="user":
        st.markdown(f'<div class="chat-bubble-user">🧑‍💼 {escape(text)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 {escape(text).replace("\\n","<br>")}</div>', unsafe_allow_html=True)
        if entry.get("audio_b64"):
            try: st.audio(io.BytesIO(base64.b64decode(entry["audio_b64"])), format="audio/mp3")
            except: pass
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Prompt input
# -------------------------
user_input = st.text_area("Type your message", value=st.session_state.get("main_input",""), height=96)
col_send, col_clear = st.columns([1,1])
with col_send:
    if st.button("Send"):
        if user_input.strip():
            st.session_state["chat_history"].append({"role":"user","text":user_input.strip()})
            add_ai_response(user_input.strip())
            st.session_state["main_input"]=""
            try: st.rerun()
            except: pass
with col_clear:
    if st.button("Clear Input"):
        st.session_state["main_input"]=""
        try: st.rerun()
        except: pass

# -------------------------
# Bottom disclaimer
# -------------------------
st.markdown("""
<div class="fixed-disclaimer">
⚠️ Internal tool — outputs grounded in GSK-approved references and sales modules. Verify before external use.
</div>
""", unsafe_allow_html=True)
