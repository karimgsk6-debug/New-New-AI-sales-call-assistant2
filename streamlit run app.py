# app.py - AI Sales Call Assistant (Full merged + enhanced UI + summaries + prompt bubble)
import streamlit as st
import os, re, io, tempfile, base64
from datetime import datetime
from html import escape

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
# Repository & asset URLs
# -------------------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
BACKGROUND_URL = REPO_RAW_BASE + "/background1.png"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# -------------------------
# GROQ API placeholder
# -------------------------
GROQ_API_KEY = "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"

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
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)
for nk in ("medical_summary", "sales_summary", "pdf_summary", "feedback"):
    if nk not in st.session_state or not isinstance(st.session_state[nk], dict):
        st.session_state[nk] = {}

# -------------------------
# Brand configuration
# -------------------------
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
# CSS & visuals
# -------------------------
st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}}
.header {{
  display:flex; align-items:center; justify-content:space-between; gap:12px;
  background: linear-gradient(90deg, rgba(255,255,255,0.85), rgba(255,255,255,0.78));
  padding:10px 18px; border-radius:10px; margin-bottom:12px; box-shadow: 0 6px 18px rgba(0,0,0,0.06);
}}
.header .title {{ text-align:center; flex:1; }}
.header img.left-logo {{ height:56px; }}
.header img.right-logo {{ height:56px; }}
.section-bubble {{
  background: rgba(255,255,255,0.95);
  border-radius: 10px; padding:12px; margin-bottom:10px;
  box-shadow: 0 6px 18px rgba(11,22,55,0.04);
}}
.chat-container {{
  max-height:50vh; overflow-y:auto; padding:12px;
  background: rgba(255,255,255,0.95); border-radius:8px; margin-bottom:60px;
}}
.chat-bubble-user {{
  background: linear-gradient(90deg,#0078D7,#0066C8);
  color:white; padding:12px; border-radius:12px; margin:8px 0; max-width:78%;
  margin-left:auto; box-shadow:0 2px 6px rgba(0,0,0,0.08);
}}
.chat-bubble-ai {{
  background: linear-gradient(90deg,#eef9ff,#e6f4ff);
  color:#000; padding:12px; border-radius:12px; margin:8px 0; max-width:78%;
  box-shadow:0 2px 6px rgba(0,0,0,0.04);
}}
.feedback-row {{ display:flex; gap:8px; margin-top:8px; align-items:center; }}
.feedback-btn {{ background:#fff; border:1px solid #e6e9ee; padding:6px 10px; border-radius:8px; cursor:pointer; }}
.combined-fixed {{ position: fixed; left:20px; right:20px; bottom:18px; z-index:9999; background: rgba(255,255,255,0.98); padding:12px; border-radius:10px; box-shadow: 0 12px 40px rgba(0,0,0,0.08); }}
.resizable-combined {{ resize: vertical; overflow: auto; border:1px solid #ddd; padding:10px; border-radius:8px; background:#fff; min-height:110px; max-height:400px; }}
.suggestion-pill {{ display:inline-block; padding:6px 12px; border-radius:20px; background:#f6f8fa; margin:4px; border:1px solid #e6e9ee; font-size:14px; cursor:pointer; }}
.fixed-small-text {{ font-size:12px; color:#555; margin-top:4px; text-align:right; }}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Helper functions
# -------------------------
def read_file_text(path: str) -> str:
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

def simple_summary(text: str, bullets: int = 6) -> str:
    if not text: return ""
    sents = re.split(r'(?<=[\.!\?])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join([f"- {s}" for s in selected])

def model_summarize(text: str, bullets: int = 6) -> str:
    if not text: return ""
    return simple_summary(text, bullets)

def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas = [], []
    for folder in folders:
        if not folder or not os.path.exists(folder):
            continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf", ".txt"))]
        for fname in files:
            p = os.path.join(folder, fname)
            text = read_file_text(p)
            if not text: continue
            sents = re.split(r'(?<=[\.!\?])\s+', text)
            for i in range(0, max(1, len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename": fname, "folder": folder, "start": i})
    return chunks, metas

def local_search_snippets(query: str, chunks: list, metas: list, top_n: int = 5):
    if not chunks or not query: return []
    q = query.lower().strip()
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks + [query])
            chunk_vecs = vectorizer.transform(chunks)
            q_vec = vectorizer.transform([query])
            sims = linear_kernel(q_vec, chunk_vecs).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            results = []
            for idx in top_idxs:
                if sims[idx] <= 0: continue
                results.append({"score": float(sims[idx]), "text": chunks[idx], "meta": metas[idx]})
            return results
        except Exception: pass
    out = []
    for i, c in enumerate(chunks):
        if q in c.lower():
            out.append({"score": 1.0, "text": c, "meta": metas[i]})
            if len(out) >= top_n: break
    return out

def generate_audio_base64(text: str) -> str:
    if not text or not gTTS: return ""
    tts_text = re.sub(r'\n\s*\n', ' ... ', text).replace("\n", " ")
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=tts_text, lang="en", slow=False).save(tmp.name)
        with open(tmp.name, "rb") as fh:
            return base64.b64encode(fh.read()).decode("utf-8")
    except Exception: return ""

# -------------------------
# Sidebar: filters, uploads
# -------------------------
with st.sidebar:
    st.image(GSK_LOGO_RAW, width=150)
    st.markdown("---")
    st.subheader("Filters & Options")
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state["selected_brand"]), format_func=lambda k: brand_data[k]["display"])
    st.session_state["selected_brand"] = sel_brand
    bconf = brand_data[sel_brand]
    persona = st.selectbox("HCP Persona", bconf.get("personas", []))
    segment = st.selectbox("Segment", bconf.get("segments", []))
    barrier = st.multiselect("Doctor Barrier", bconf.get("barriers", []))
    specialty = st.selectbox("Specialty", bconf.get("specialties", []))
    objective = st.selectbox("Objective", ["Awareness", "Adoption", "Retention"])
    st.session_state["temperature"] = st.slider("Temperature", 0.0, 1.0, st.session_state["temperature"], 0.05)
    st.session_state["search_mode"] = st.selectbox("Search mode", ["deep", "shallow"])
    st.session_state["language"] = st.radio("Language", ["English", "Arabic"])

    st.markdown("---")
    st.subheader("Export")
    export_format = st.selectbox("Export format", ["DOCX" if DOCX_AVAILABLE else "TXT", "TXT"])
    st.markdown("---")
    with st.expander("Upload PDF/TXT (brand-specific)"):
        uploaded_file = st.file_uploader("Upload a PDF or TXT", type=["pdf","txt"], key="sidebar_upload")
        if uploaded_file:
            try:
                if hasattr(uploaded_file, "type") and uploaded_file.type == "application/pdf" and PdfReader:
                    reader = PdfReader(uploaded_file)
                    pdf_text = "".join([p.extract_text() or "" for p in reader.pages])
                else:
                    pdf_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
                st.session_state["pdf_summary"].setdefault(sel_brand, model_summarize(pdf_text, bullets=6))
                st.success("Uploaded file summarized for this brand.")
            except Exception:
                st.error("Failed to read uploaded file.")
    st.markdown("---")
    if st.button("🗑️ Clear Chat (all)"):
        st.session_state["chat_history"] = []
        st.session_state["feedback"] = {}

# -------------------------
# Header
# -------------------------
st.markdown(f"""
<div class="header">
  <div style="width:140px;"><img src="{GSK_LOGO_RAW}" class="left-logo"></div>
  <div class="title"><h1 style="margin:0">💡 AI Sales Call Assistant</h1><div style="color:#666;font-size:14px;">{brand_data[st.session_state['selected_brand']]['display']}</div></div>
  <div style="width:140px;text-align:right;"><img src="{AI_LOGO_RAW}" class="right-logo"></div>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Summaries: Medical & Sales
# -------------------------
brand = st.session_state["selected_brand"]
refs_folder = brand_data[brand]["references_path"]
sales_folder = brand_data[brand]["sales_path"]

if brand not in st.session_state["medical_summary"]:
    combined_refs = ""
    if os.path.exists(refs_folder):
        for f in sorted(os.listdir(refs_folder)):
            if f.lower().endswith((".pdf", ".txt")):
                combined_refs += read_file_text(os.path.join(refs_folder, f)) + "\n"
    st.session_state["medical_summary"][brand] = model_summarize(combined_refs, bullets=6) if combined_refs.strip() else ""

if brand not in st.session_state["sales_summary"]:
    combined_sales = ""
    if os.path.exists(sales_folder):
        for f in sorted(os.listdir(sales_folder)):
            if f.lower().endswith((".pdf", ".txt")):
                combined_sales += read_file_text(os.path.join(sales_folder, f)) + "\n"
    st.session_state["sales_summary"][brand] = model_summarize(combined_sales, bullets=6) if combined_sales.strip() else ""

chunks, metas = build_corpus_for_folders([p for p in (refs_folder, sales_folder) if os.path.exists(p)], chunk_size_sentences=3)

with st.expander("📚 Medical References Summary", expanded=True):
    md = st.session_state["medical_summary"].get(brand, "")
    st.markdown(f'<div class="section-bubble">{md if md else "No medical references found."}</div>', unsafe_allow_html=True)

with st.expander("💼 Sales Module Summary", expanded=True):
    sd = st.session_state["sales_summary"].get(brand, "")
    st.markdown(f'<div class="section-bubble">{sd if sd else "No sales module content found."}</div>', unsafe_allow_html=True)

# -------------------------
# Chat container
# -------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for idx, entry in enumerate(st.session_state["chat_history"]):
    role = entry.get("role", "assistant")
    text = entry.get("text", "")
    if role == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑‍💼 {escape(text)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 {escape(text).replace("\\n","<br>")}</div>', unsafe_allow_html=True)
        if entry.get("audio_b64"):
            try: st.audio(io.BytesIO(base64.b64decode(entry["audio_b64"])), format="audio/mp3")
            except Exception: pass
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Bottom fixed input + prompt suggestions + fixed small text
# -------------------------
def make_suggestions(brand_key, persona_val, barriers_list, segment_val, specialty_val, objective_val):
    s=[]
    s.append(f"Generate call flow for {persona_val} focused on {objective_val}.")
    if barriers_list: s.append(f"Handle objection: {', '.join(barriers_list[:2])} for {persona_val}.")
    else: s.append(f"Identify common objections for {persona_val}.")
    s.append(f"Summarize HCP persona insights for {persona_val}.")
    s.append(f"Key talking points for {brand_data[brand_key]['display']} in {segment_val}.")
    s.append(f"Draft a short adoption message for {brand_data[brand_key]['display']} to a {specialty_val}.")
    return s

suggestions = make_suggestions(brand, persona, barrier, segment, specialty, objective)

st.markdown('<div class="combined-fixed">', unsafe_allow_html=True)
st.markdown('<div class="resizable-combined">', unsafe_allow_html=True)
with st.expander("💡 Prompt Suggestions (click to expand)", expanded=False):
    pills_html = " ".join([f'<span class="suggestion-pill">{escape(s)}</span>' for s in suggestions])
    st.markdown(pills_html, unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

user_input = st.text_area("Ask a question or type command here...", value="", height=80, key="main_input")

st.markdown('<div class="fixed-small-text">Please refer to Write Right Principles course: BUS-LGL-WRJA-001</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Processing user input
# -------------------------
if st.button("Send") and user_input.strip():
    st.session_state["chat_history"].append({"role":"user","text":user_input})
    # Generate AI response
    # For demonstration, we will do a simple search-based response
    results = local_search_snippets(user_input, chunks, metas, top_n=5)
    response_text = ""
    if results:
        response_text += "Relevant info:\n" + "\n".join([f"- {r['text'][:250]}..." for r in results])
    else:
        response_text += "🤖 I could not find exact references. Please clarify or rephrase your query."

    audio_b64 = generate_audio_base64(response_text)
    st.session_state["chat_history"].append({"role":"assistant","text":response_text, "audio_b64": audio_b64})
    st.experimental_rerun()
