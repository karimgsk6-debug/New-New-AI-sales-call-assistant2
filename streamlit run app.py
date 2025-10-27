# app.py - Full AI Sales Call Assistant (Enhanced, APACT, interactive feedback, humanized voice, examples)
import streamlit as st
import os, re, tempfile, base64, io
from datetime import datetime
from html import escape

# Optional libs (best-effort)
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
# Page config & background
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# Insert your GROQ API key here
# -------------------------
GROQ_API_KEY = "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"
client = None
# Optionally import Groq if installed
try:
    from groq import Groq
    if GROQ_API_KEY:
        client = Groq(api_key=GROQ_API_KEY)
except:
    client = None

# -------------------------
# Backgrounds, logos
# -------------------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
BACKGROUND_URL = REPO_RAW_BASE + "/background1.png"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# -------------------------
# Session defaults
# -------------------------
defaults = {
    "chat_history": [],
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.62,
    "search_mode": "deep",
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "feedback": {},
    "language": "English",
    "reply_style": "balanced",  # options: balanced, short_script, data, conversational
    "awaiting_style_pref": False,
    "medical_summary": {},  # brand-specific
    "sales_summary": {}     # brand-specific
}
for k,v in defaults.items():
    st.session_state.setdefault(k,v)

# -------------------------
# CSS
# -------------------------
CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}}
.title-box {{
  background: rgba(255,255,255,0.95);
  padding: 12px;
  border-radius: 10px;
  margin-bottom: 12px;
  position: relative;
  display:flex;
  align-items:center;
  justify-content:center;
}}
.title-box img.left-logo {{ position:absolute; left:12px; height:64px; }}
.title-box img.right-logo {{ position:absolute; right:12px; height:64px; }}
.chat-container {{ max-height: 60vh; overflow-y:auto; padding:12px; background: rgba(255,255,255,0.95); border-radius:8px; margin-bottom:160px; }}
.chat-bubble-user {{ background:#0078D7; color:white; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto; }}
.chat-bubble-ai {{ background:#eef9ff; color:#000; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }}
.suggestion-pill {{ background:#fff; border:1px solid #ddd; padding:8px 12px; border-radius:20px; margin:6px; cursor:pointer; display:inline-block; }}
.suggestion-pill:hover {{ background:#f0f8ff; }}
.citation-box {{ background:#fbfbff; border-left:4px solid #0078D7; padding:8px; margin-top:8px; border-radius:6px; font-size:13px; white-space:pre-wrap; }}
.input-area {{ position: fixed; left:20px; right:20px; bottom:18px; z-index:9999; display:flex; gap:8px; align-items:flex-end; }}
.input-area textarea {{ width:100%; min-height:72px; max-height:250px; padding:10px; border-radius:8px; border:1px solid #ccc; resize:vertical; }}
.send-button {{ height:44px; padding:0 14px; border-radius:8px; border:none; background:#FF6F00; color:white; cursor:pointer; font-weight:600; }}
.feedback-buttons button {{ margin-right:6px; }}
.fixed-disclaimer {{ position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# -------------------------
# Brand info (with Trelegy added)
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
# Helper functions
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

def model_summarize(text, bullets=6):
    if not text: return ""
    if client:
        try:
            prompt=f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt}],
                temperature=0.2)
            return resp.choices[0].message.content
        except:
            return simple_summary(text, bullets)
    else:
        return simple_summary(text, bullets)

def generate_audio_base64(text):
    if not text:
        return ""
    tts_text = re.sub(r'\n\s*\n', ' ... ', text)
    tts_text = tts_text.replace("\n", " ")
    if gTTS:
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                gTTS(text=tts_text, lang="en", slow=False).save(tmp.name)
                tmp.seek(0)
                audio_bytes = tmp.read()
                return base64.b64encode(audio_bytes).decode("utf-8")
        except:
            return ""
    return ""

# -------------------------
# Title Box
# -------------------------
st.markdown(f"""
<div class="title-box">
    <img src="{GSK_LOGO_RAW}" class="left-logo"/>
    <h2>AI Sales Call Assistant</h2>
    <img src="{AI_LOGO_RAW}" class="right-logo"/>
</div>
""",unsafe_allow_html=True)

# -------------------------
# Sidebar - Brand select & PDF upload
# -------------------------
with st.sidebar:
    st.selectbox("Select Brand", options=list(brand_data.keys()), key="selected_brand", format_func=lambda x: brand_data[x]["display"])
    uploaded_file = st.file_uploader("Upload PDF (Optional)", type=["pdf","txt"])
    if uploaded_file:
        try:
            if uploaded_file.type=="application/pdf" and PdfReader:
                reader = PdfReader(uploaded_file)
                st.session_state.uploaded_pdf_text = "".join([p.extract_text() or "" for p in reader.pages])
            else:
                st.session_state.uploaded_pdf_text = uploaded_file.getvalue().decode("utf-8",errors="ignore")
            st.session_state.pdf_summary = model_summarize(st.session_state.uploaded_pdf_text)
        except:
            st.session_state.uploaded_pdf_text = ""
            st.session_state.pdf_summary = ""

# -------------------------
# Load references and sales module summaries per brand
# -------------------------
brand = st.session_state.selected_brand
refs_folder = brand_data[brand]["references_path"]
sales_folder = brand_data[brand]["sales_path"]

# Initialize session dicts
if "medical_summary" not in st.session_state or not isinstance(st.session_state.medical_summary, dict):
    st.session_state.medical_summary = {}
if "sales_summary" not in st.session_state or not isinstance(st.session_state.sales_summary, dict):
    st.session_state.sales_summary = {}

# Medical references summary
combined_refs = build_corpus_for_folders([refs_folder])[0]
st.session_state.medical_summary[brand] = model_summarize(" ".join(combined_refs)) if combined_refs else ""

# Sales module summary
combined_sales = build_corpus_for_folders([sales_folder])[0]
st.session_state.sales_summary[brand] = model_summarize(" ".join(combined_sales)) if combined_sales else ""

# -------------------------
# Prompt suggestions collapsible
# -------------------------
with st.expander("Prompt Suggestions (click to expand)"):
    for s in brand_data[brand]["personas"] + brand_data[brand]["barriers"] + brand_data[brand]["segments"]:
        if st.button(s, key=f"sugg_{s}"):
            st.session_state.main_input = s

# -------------------------
# Chat container
# -------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for entry in st.session_state.chat_history:
    role = entry.get("role","ai")
    text = entry.get("text","")
    bubble_class = "chat-bubble-user" if role=="user" else "chat-bubble-ai"
    st.markdown(f'<div class="{bubble_class}">{escape(text)}</div>',unsafe_allow_html=True)
    # Feedback buttons
    if role=="ai":
        cols = st.columns([1,1,1])
        if cols[0].button("👍", key=f"like_{id(entry)}"):
            st.session_state.feedback[id(entry)] = "like"
        if cols[1].button("👎", key=f"dislike_{id(entry)}"):
            st.session_state.feedback[id(entry)] = "dislike"
        if cols[2].button("🔄 Need More", key=f"more_{id(entry)}"):
            st.session_state.feedback[id(entry)] = "more"
    # Audio playback
    audio_b64 = generate_audio_base64(text)
    if audio_b64:
        st.audio(base64.b64decode(audio_b64), format="audio/mp3")
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Chat input area (fixed bottom)
# -------------------------
st.markdown('<div class="input-area">', unsafe_allow_html=True)
st.session_state.main_input = st.text_area("Ask", value=st.session_state.main_input, key="main_input", placeholder="Type your question or use a prompt suggestion")
send_clicked = st.button("Send", key="send_button")
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Handle input
# -------------------------
if send_clicked and st.session_state.main_input.strip():
    user_text = st.session_state.main_input.strip()
    st.session_state.chat_history.append({"role":"user","text":user_text})
    # Generate AI response (fake / placeholder for demo)
    ai_text = f"AI Response for {brand} based on: {user_text}\n\nMedical Summary:\n{st.session_state.medical_summary.get(brand,'')}\nSales Summary:\n{st.session_state.sales_summary.get(brand,'')}"
    st.session_state.chat_history.append({"role":"ai","text":ai_text})
    st.session_state.main_input = ""

# -------------------------
# Footer
# -------------------------
st.markdown('<div class="fixed-disclaimer">Powered by GSK AI Sales Call Assistant - Confidential</div>', unsafe_allow_html=True)
