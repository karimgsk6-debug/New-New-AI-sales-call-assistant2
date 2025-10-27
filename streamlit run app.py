# app.py - AI Sales Call Assistant (Final Version)
import streamlit as st
import os, re, tempfile, base64, io
from datetime import datetime
from html import escape

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
# Session defaults
# -------------------------
defaults = {
    "chat_history": [],
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.62,
    "search_mode": "deep",
    "medical_summary": "",
    "sales_summary": "",
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "feedback": {},
    "language": "English",
    "reply_style": "balanced",
    "awaiting_style_pref": False,
}
for k,v in defaults.items():
    st.session_state.setdefault(k,v)

# -------------------------
# CSS
# -------------------------
CSS = """
<style>
.title-box {
  background: rgba(255,255,255,0.95);
  padding: 12px;
  border-radius: 10px;
  margin-bottom: 12px;
  display:flex; align-items:center; justify-content:center;
}
.chat-container { max-height:60vh; overflow-y:auto; padding:12px; background: rgba(255,255,255,0.95); border-radius:8px; margin-bottom:200px; }
.chat-bubble-user { background:#0078D7; color:white; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto; }
.chat-bubble-ai { background:#eef9ff; color:#000; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }
.suggestion-pill { background:#fff; border:1px solid #ddd; padding:8px 12px; border-radius:20px; margin:6px; cursor:pointer; display:inline-block; }
.suggestion-pill:hover { background:#f0f8ff; }
.citation-box { background:#fbfbff; border-left:4px solid #0078D7; padding:8px; margin-top:8px; border-radius:6px; font-size:13px; white-space:pre-wrap; }
.input-area { position: fixed; left:20px; right:20px; bottom:18px; z-index:9999; display:flex; gap:8px; align-items:flex-end; }
.input-area textarea { width:100%; min-height:72px; max-height:250px; padding:10px; border-radius:8px; border:1px solid #ccc; resize:vertical; }
.send-button { height:44px; padding:0 14px; border-radius:8px; border:none; background:#FF6F00; color:white; cursor:pointer; font-weight:600; }
.feedback-buttons button { margin-right:6px; }
.fixed-disclaimer { position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# -------------------------
# Brands, Personas, Barriers, Segments, Specialties
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
# Placeholder for GROQ API
# -------------------------
GROQ_API_KEY = "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"
client = None

# -------------------------
# Helpers
# -------------------------
def read_file_text(path):
    if not os.path.exists(path): return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path,"r",encoding="utf-8",errors="ignore") as fh:
                return fh.read()
    except:
        return ""

def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas = [], []
    for folder in folders:
        if not folder or not os.path.exists(folder): continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf",".txt"))]
        for fname in files:
            p = os.path.join(folder,fname)
            text = read_file_text(p)
            if not text: continue
            sents = re.split(r'(?<=[\.!\?])\s+',text)
            for i in range(0,max(1,len(sents)),chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename":fname,"folder":folder,"start":i})
    return chunks, metas

def local_search_snippets(query,chunks,metas,top_n=5):
    if not chunks: return []
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks+[query])
            chunk_vecs = vectorizer.transform(chunks)
            q_vec = vectorizer.transform([query])
            sims = linear_kernel(q_vec,chunk_vecs).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            results = []
            for idx in top_idxs:
                if sims[idx]<=0: continue
                results.append({"score":float(sims[idx]),"text":chunks[idx],"meta":metas[idx]})
            return results
        except:
            pass
    out = []
    q=query.lower()
    for i,c in enumerate(chunks):
        if q in c.lower():
            out.append({"score":1.0,"text":c,"meta":metas[i]})
            if len(out)>=top_n: break
    return out

def simple_summary(text, bullets=6):
    if not text: return ""
    sents = re.split(r'(?<=[\.!\?])\s+',text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- "+s for s in selected])

def generate_audio_base64(text):
    if not text or not gTTS: return ""
    tts_text = text.replace("\n"," ... ")
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=tts_text, lang="en", slow=False).save(tmp.name)
        with open(tmp.name,"rb") as fh:
            return base64.b64encode(fh.read()).decode()
    except Exception:
        return ""

# -------------------------
# Sidebar
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]
    segment = st.selectbox("Segment", bconf["segments"])
    persona = st.selectbox("HCP Persona", bconf["personas"])
    barrier = st.multiselect("Doctor Barrier", bconf["barriers"])
    specialty = st.selectbox("Specialty", bconf["specialties"])
    objective = st.selectbox("Objective", ["Awareness","Adoption","Retention"])
    st.session_state.temperature = st.slider("Temperature",0.0,1.0,st.session_state.temperature,0.05)
    st.session_state.search_mode = st.selectbox("Search mode", ["deep","shallow"])
    st.session_state.language = st.radio("Language", ["English","Arabic"])
    if st.button("🗑️ Clear Chat"): st.session_state.chat_history=[]

# -------------------------
# Title
# -------------------------
st.markdown(f"""
<div class="title-box">
<h2>💡 AI Sales Call Assistant — {brand_data[sel_brand]['display']}</h2>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Load references & sales summaries
# -------------------------
refs_folder = bconf["references_path"]
sales_folder = bconf["sales_path"]
chunks, chunk_meta = build_corpus_for_folders([refs_folder,sales_folder], chunk_size_sentences=3)

# -------------------------
# AI response
# -------------------------
def add_ai_response(prompt):
    snippets = local_search_snippets(prompt,chunks,chunk_meta)
    text_lines = ["*AI Response:*"]
    for s in snippets[:3]:
        text_lines.append(f"- {s['text'][:220]} ...")
    ai_text = "\n".join(text_lines)
    audio_b64 = generate_audio_base64(ai_text)
    st.session_state.chat_history.append({"role":"assistant","text":ai_text,"audio_b64":audio_b64})

# -------------------------
# Chat display
# -------------------------
chat_container = st.container()
with chat_container:
    for idx,entry in enumerate(st.session_state.chat_history):
        if entry.get("role")=="user":
            st.markdown(f'<div class="chat-bubble-user">{escape(entry["text"])}</div>',unsafe_allow_html=True)
        elif entry.get("role")=="assistant":
            st.markdown(f'<div class="chat-bubble-ai">{escape(entry["text"]).replace("\\n","<br>")}</div>',unsafe_allow_html=True)
            audio_b64 = entry.get("audio_b64","")
            if audio_b64:
                try: st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")
                except: pass
            # Feedback buttons
            fb_cols = st.columns(3)
            if fb_cols[0].button("👍 Like", key=f"like_{idx}"):
                st.session_state.feedback[f"fb_{idx}"]="like"
            if fb_cols[1].button("👎 Dislike", key=f"dislike_{idx}"):
                st.session_state.feedback[f"fb_{idx}"]="dislike"
            if fb_cols[2].button("ℹ️ Need More", key=f"needmore_{idx}"):
                st.session_state.feedback[f"fb_{idx}"]="need_more"

# -------------------------
# Chat input + prompt suggestions at bottom
# -------------------------
st.markdown('<div class="input-area">', unsafe_allow_html=True)
with st.expander("💡 Prompt Suggestions", expanded=True):
    suggestions = ["Generate call flow","Highlight key barriers","Propose objections","Suggest engagement style"]
    for s in suggestions:
        if st.button(s, key=f"sugg_{s}"):
            st.session_state.main_input = s

with st.form("chat_input_form", clear_on_submit=True):
    user_input = st.text_area("Type your question here...", st.session_state.main_input, height=96)
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role":"user","text":user_input.strip()})
        add_ai_response(user_input.strip())
        st.session_state.main_input = ""
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown("""
<div class="fixed-disclaimer">
⚠️ This tool is for internal sales support only. Do not share with external users.
</div>
""", unsafe_allow_html=True)
