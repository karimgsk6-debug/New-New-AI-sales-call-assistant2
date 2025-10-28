# app.py - AI Sales Call Assistant (Updated + Visual Enhancements)
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
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# Repo assets
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# -------------------------
# Session defaults
# -------------------------
defaults = {
    "chat_history": [],
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.7,
    "search_mode": "deep",
    "language": "English",
    "reply_style": "balanced",
    "awaiting_style_pref": False,
    "call_count": 0,
    "export_count": 0,
    "feedback_stats": {"like": 0, "dislike": 0, "need_more": 0},
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)
for name in ("medical_summary", "sales_summary", "pdf_summary"):
    if name not in st.session_state or not isinstance(st.session_state[name], dict):
        st.session_state[name] = {}

# -------------------------
# Brand config
# -------------------------
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas": ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
        "specialties": ["GP","Dermatologist","Geriatrician"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/",
        "call_flow": ["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Post-call Analysis"]
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas": ["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties": ["Oncologist","Medical Oncologist"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli/",
        "call_flow": ["COCO","Anchor","Engage","Close"]
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness","Diagnosis","Adoption","Adherence"],
        "personas": ["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers": ["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties": ["GP","Pulmonologist","Respiratory Specialist"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy/",
        "call_flow": ["Prepare","Engage","Demonstrate","Address Access","Close"]
    }
}

# -------------------------
# CSS (pure orange gradient + dark footer)
# -------------------------
st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{
  background: linear-gradient(135deg, rgba(255,165,0,0.15), rgba(255,140,0,0.1));
  background-size: cover; background-position: center; backdrop-filter: blur(6px);
}}
.header {{
  display:flex; align-items:center; justify-content:space-between;
  padding:10px 16px; border-radius:10px; background: rgba(0,0,0,0.45); color:#fff; margin-bottom:12px;
}}
.header .title {{ text-align:center; flex:1; margin:0 8px; }}
.header img.left-logo, .header img.right-logo {{ height:56px; }}
.section-bubble {{ background: rgba(255,255,255,0.05); border-radius:10px; padding:12px; margin-bottom:10px; color:#fff; }}
.chat-container {{ max-height:56vh; overflow-y:auto; padding:12px; background: rgba(0,0,0,0.4); border-radius:8px; margin-bottom:180px; color:#fff; }}
.chat-bubble-user {{ background: linear-gradient(90deg,#0078D7,#0066C8); color:white; padding:12px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto; }}
.chat-bubble-ai {{ background: linear-gradient(90deg,#fff5eb,#fff1e6); color:#1b1b1b; padding:12px; border-radius:12px; margin:8px 0; max-width:78%; }}
.feedback-row {{ display:flex; gap:8px; margin-top:8px; align-items:center; }}
.feedback-btn {{ background: rgba(255,255,255,0.08); color: #fff; padding:6px 10px; border-radius:8px; border: none; cursor: pointer; }}
.fixed-disclaimer {{ position: fixed; left:0; right:0; bottom:0; background: rgba(0,0,0,0.7); padding:10px; color:#fff; text-align:center; z-index:9997; }}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Helper functions (read files, summarize, search, audio)
# -------------------------
def read_file_text(path):
    if not os.path.exists(path): return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            return open(path, "r", encoding="utf-8", errors="ignore").read()
    except: return ""

def simple_summary(text, bullets=6):
    sents = re.split(r'(?<=[\.!\?])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join([f"- {s}" for s in selected])

def model_summarize(text, bullets=6):
    bullets_text = simple_summary(text, bullets)
    if not bullets_text: return ""
    return "\n\n".join([
        "**Key Findings**", bullets_text,
        "**Clinical Insights**", "- Review the most clinically relevant points above.",
        "**Action Points**", "- Use above lines as short scripts or data bullets in the call."
    ])

def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas = [], []
    for folder in folders:
        if not folder or not os.path.exists(folder): continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf", ".txt"))]
        for fname in files:
            p = os.path.join(folder, fname)
            text = read_file_text(p)
            if not text: continue
            sents = re.split(r'(?<=[\.!\?])\s+', text)
            for i in range(0, max(1,len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename": fname, "folder": folder, "start": i})
    return chunks, metas

def local_search_snippets(query, chunks, metas, top_n=5):
    if not chunks or not query: return []
    q = query.lower().strip()
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks+[query])
            sims = linear_kernel(vectorizer.transform([query]), vectorizer.transform(chunks)).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            return [{"score": float(sims[idx]), "text": chunks[idx], "meta": metas[idx]} for idx in top_idxs if sims[idx]>0]
        except: pass
    # fallback substring search
    out=[]
    for i,c in enumerate(chunks):
        if q in c.lower():
            out.append({"score":1.0,"text":c,"meta":metas[i]})
            if len(out)>=top_n: break
    return out

def generate_audio_base64(text):
    if not text or not gTTS: return ""
    tts_text = re.sub(r'\n\s*\n',' ... ', text).replace("\n"," ")
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=tts_text, lang="en", slow=False).save(tmp.name)
        with open(tmp.name,"rb") as fh:
            return base64.b64encode(fh.read()).decode("utf-8")
    except: return ""

def export_call_flow_bytes(text, fmt="docx"):
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_brand = st.session_state.get("selected_brand","brand")
    if fmt=="docx" and DOCX_AVAILABLE:
        doc = Document()
        doc.add_heading(f"{brand_data[safe_brand]['display']} — Generated Call Flow", level=2)
        for line in text.splitlines(): doc.add_paragraph(line)
        bio=io.BytesIO(); doc.save(bio); bio.seek(0)
        return bio.read(), f"{safe_brand}_callflow_{now}.docx"
    else:
        return text.encode("utf-8"), f"{safe_brand}_callflow_{now}.txt"
# -------------------------
# Header + Logos
# -------------------------
st.markdown(f"""
<div class="header">
    <img class="left-logo" src="{GSK_LOGO_RAW}" alt="GSK Logo"/>
    <div class="title"><h2>AI Sales Call Assistant</h2></div>
    <img class="right-logo" src="{AI_LOGO_RAW}" alt="AI Logo"/>
</div>
""", unsafe_allow_html=True)

# -------------------------
# File Upload + Summary
# -------------------------
uploaded_file = st.file_uploader("Upload PDF / TXT for auto-summary", type=["pdf","txt"], key="upload")
if uploaded_file:
    file_bytes = uploaded_file.read()
    tmp_path = os.path.join(tempfile.gettempdir(), uploaded_file.name)
    with open(tmp_path, "wb") as f: f.write(file_bytes)
    text_content = read_file_text(tmp_path)
    summary_text = model_summarize(text_content)
    st.session_state["pdf_summary"] = {"name": uploaded_file.name, "summary": summary_text}
    st.markdown(f'<div class="section-bubble"><b>Summary for {uploaded_file.name}:</b><br>{summary_text}</div>', unsafe_allow_html=True)

# -------------------------
# Prompt Suggestions
# -------------------------
prompt_suggestions = [
    "Generate call flow for this HCP",
    "Summarize recent clinical studies",
    "Highlight key objections",
    "Provide patient case examples",
]
st.markdown('<div class="section-bubble"><b>Prompt suggestions:</b> ' + ", ".join(prompt_suggestions) + '</div>', unsafe_allow_html=True)

# -------------------------
# Chat display
# -------------------------
st.markdown('<div class="chat-container" id="chat_container">', unsafe_allow_html=True)
for msg in st.session_state.chat_history:
    if msg["role"]=="user":
        st.markdown(f'<div class="chat-bubble-user">{escape(msg["text"])}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">{escape(msg["text"])}</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# User input
# -------------------------
user_input = st.chat_input("Ask AI Sales Assistant...")
if user_input:
    st.session_state.chat_history.append({"role":"user","text":user_input})
    # Simple mock AI response
    ai_response = f"**AI Response:** Based on your input '{user_input}', consider following points:\n- Point 1\n- Point 2\n- Point 3"
    st.session_state.chat_history.append({"role":"ai","text":ai_response})
    st.experimental_rerun()

# -------------------------
# Feedback system
# -------------------------
st.markdown('<div class="feedback-row">', unsafe_allow_html=True)
like = st.button("👍 Like")
dislike = st.button("👎 Dislike")
need_more = st.button("🔄 Regenerate")
st.markdown('</div>', unsafe_allow_html=True)

if like:
    st.session_state.feedback_stats["like"] += 1
if dislike:
    st.session_state.feedback_stats["dislike"] += 1
    # Interactive follow-up
    reason = st.radio("Why did you dislike the response?", ["Too long","Not clear","Missing info","Other"])
    if reason:
        st.info(f"AI will regenerate taking into account: {reason}")
        # Mock regeneration
        regenerated = f"**Regenerated Response ({reason}):** Consider these updated points..."
        st.session_state.chat_history.append({"role":"ai","text":regenerated})
        st.experimental_rerun()
if need_more:
    st.session_state.feedback_stats["need_more"] += 1
    regenerated = f"**Regenerated Response:** Here is a refreshed version based on your last input."
    st.session_state.chat_history.append({"role":"ai","text":regenerated})
    st.experimental_rerun()

# -------------------------
# Export Call Flow
# -------------------------
export_text = "\n".join([m["text"] for m in st.session_state.chat_history if m["role"]=="ai"])
if export_text:
    st.download_button("📄 Export Call Flow (DOCX)", data=export_call_flow_bytes(export_text, fmt="docx")[0], file_name=export_call_flow_bytes(export_text, fmt="docx")[1])
    st.download_button("📄 Export Call Flow (TXT)", data=export_call_flow_bytes(export_text, fmt="txt")[0], file_name=export_call_flow_bytes(export_text, fmt="txt")[1])

# -------------------------
# Footer / Disclaimer
# -------------------------
st.markdown('<div class="fixed-disclaimer">⚠️ This AI tool is for internal sales training and assistance only. Not for clinical decisions.</div>', unsafe_allow_html=True)
