# app.py - Full AI Sales Call Assistant with interactive feedback
import streamlit as st
from PIL import Image
import os, re, tempfile, base64
from io import BytesIO
from datetime import datetime
from groq import Groq
from PyPDF2 import PdfReader
from html import escape
from gtts import gTTS
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False

try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except:
    ELEVENLABS_AVAILABLE = False

# ---------------- Page Config ----------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ---------------- Assets ----------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_BLOB_BASE = f"https://github.com/{REPO_USER}/{REPO_NAME}/blob/{COMMIT}/.devcontainer"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"

BACKGROUND_URL = REPO_RAW_BASE + "/.devcontainer/background1.png"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# ---------------- Session Defaults ----------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "voice_pref" not in st.session_state:
    st.session_state.voice_pref = "Old Male"
if "pdf_summary_size" not in st.session_state:
    st.session_state.pdf_summary_size = "Normal"
if "main_input" not in st.session_state:
    st.session_state.main_input = ""
if "selected_brand" not in st.session_state:
    st.session_state.selected_brand = "trelegy"
if "temp_value" not in st.session_state:
    st.session_state.temp_value = 0.6
if "search_mode" not in st.session_state:
    st.session_state.search_mode = "deep"

# ---------------- CSS ----------------
CSS = f"""
<style>
.stApp {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-attachment: fixed;
  background-position: center;
}}
.title-box {{
  background: rgba(255,255,255,0.92);
  padding: 12px;
  border-radius: 10px;
  margin-bottom: 14px;
  position: relative;
  display:flex;
  align-items:center;
  justify-content:center;
}}
.title-box img.left-logo {{ position:absolute; left:16px; width:130px; height:auto; }}
.title-box img.right-logo {{ position:absolute; right:16px; width:130px; height:auto; }}
.title-box h1 {{ margin:0; font-size:22px; }}
.chat-container {{
  max-height: 56vh;
  overflow-y:auto;
  padding: 14px;
  border-radius: 10px;
  background: rgba(255,255,255,0.94);
  margin-bottom: 140px;
}}
.chat-bubble-user {{ background:#0078D7; color:white; padding:12px; border-radius:10px; margin:8px 0; max-width:78%; margin-left:auto; }}
.chat-bubble-ai {{ background:#d9f0ff; color:#000; padding:12px; border-radius:10px; margin:8px 0; max-width:78%; }}
.suggestions-inline {{ background: rgba(255,255,255,0.96); padding:10px; border-radius:8px; box-shadow:0 4px 10px rgba(0,0,0,0.06); }}
.suggestion-pill {{ background:#fff; border:1px solid #ddd; padding:8px 12px; border-radius:20px; cursor:pointer; margin:6px; display:inline-block; }}
.suggestion-pill:hover {{ background:#eef6ff; }}
.input-area {{
  position: fixed;
  left:24px;
  right:24px;
  bottom:18px;
  z-index:9999;
  display:flex;
  gap:8px;
  align-items:flex-end;
}}
.input-area textarea {{
  width:100%;
  min-height:72px;
  max-height:200px;
  padding:10px;
  border-radius:8px;
  border:1px solid #ccc;
  resize:vertical;
}}
.send-button {{
  height:44px;
  padding:0 14px;
  border-radius:8px;
  border:none;
  background:#FF6F00;
  color:white;
  cursor:pointer;
  display:flex;
  align-items:center;
  gap:8px;
  font-weight:600;
}}
.citation-box {{
  background:#fbfbff;
  border-left:4px solid #0078D7;
  padding:8px;
  margin-top:8px;
  border-radius:6px;
  font-size:13px;
  white-space:pre-wrap;
}}
.fixed-disclaimer {{ position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }}
.feedback-buttons button {{ margin-right: 6px; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------- GROQ API ----------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = None
if GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except:
        client = None

# ---------------- Brands ----------------
brand_data = {
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Concerns about side effects", "Cost/coverage"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy"
    },
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix"
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited patient eligibility", "Access/reimbursement issues"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli"
    }
}
specialties = ["GP", "Pulmonologist", "Internal medicine", "Oncologist"]
objectives = ["Awareness", "Adoption", "Retention"]

# ---------------- Helper Functions ----------------
def read_file_text(path):
    try:
        if path.lower().endswith(".pdf"):
            reader = PdfReader(path)
            text = "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        return text
    except:
        return ""

def build_corpus_for_paths(folder_paths, chunk_size_sentences=3):
    chunks, metadatas = [], []
    for folder in folder_paths:
        if not folder or not os.path.exists(folder):
            continue
        files = [f for f in os.listdir(folder) if f.lower().endswith((".pdf", ".txt"))]
        for fname in files:
            p = os.path.join(folder, fname)
            text = read_file_text(p)
            sents = re.split(r'(?<=[\.\?\!])\s+', text)
            for i in range(0, max(1, len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metadatas.append({"filename": fname, "folder": folder, "start": i})
    return chunks, metadatas

def find_top_n_snippets(query, chunks, metadatas, top_n=3):
    if not chunks: return []
    try:
        vectorizer = TfidfVectorizer(stop_words="english").fit(chunks + [query])
        chunk_vecs = vectorizer.transform(chunks)
        q_vec = vectorizer.transform([query])
        sims = linear_kernel(q_vec, chunk_vecs).flatten()
        top_idxs = sims.argsort()[::-1][:top_n]
        results = []
        for idx in top_idxs:
            if sims[idx] <= 0: continue
            results.append({"score": float(sims[idx]), "text": chunks[idx], "meta": metadatas[idx]})
        return results
    except:
        out=[]
        q=query.lower()
        for i,c in enumerate(chunks):
            if q in c.lower():
                out.append({"score":1.0,"text":c,"meta":metadatas[i]})
                if len(out)>=top_n: break
        return out

def generate_audio(text):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        tts_text = re.sub(r'[,*]{1,}', '', text)
        if ELEVENLABS_AVAILABLE:
            audio_stream = elevenlabs.generate(text=tts_text, voice=ELEVENLABS_VOICE_ID, stream=True)
            with open(tmp.name,"wb") as f:
                for ch in audio_stream: f.write(ch)
        else:
            tts = gTTS(text=tts_text, lang="en", slow=False)
            tts.save(tmp.name)
        with open(tmp.name,"rb") as fh:
            return base64.b64encode(fh.read()).decode()
    except:
        return ""

# ---------------- Sidebar ----------------
with st.sidebar.expander("Filters & Options", expanded=True):
    sel_brand_key = st.selectbox("Brand", sorted(list(brand_data.keys())),
                                index=list(sorted(brand_data.keys())).index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand_key
    sel_brand = brand_data[sel_brand_key]
    segment = st.selectbox("Segment", sel_brand["segments"])
    persona = st.selectbox("HCP Persona", sel_brand["personas"])
    barrier = st.multiselect("Doctor Barrier", sel_brand["barriers"])
    specialty = st.selectbox("Specialty", specialties)
    objective = st.selectbox("Objective", objectives)
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])
    st.session_state.temp_value = st.slider("AI Temperature", 0.1, 1.0, st.session_state.temp_value, 0.05)
    st.session_state.search_mode = st.selectbox("Search Mode", ["deep", "shallow"], index=0 if st.session_state.search_mode=="deep" else 1)
    selected_language = st.radio("Language", ["English","Arabic"], horizontal=True)
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []

with st.sidebar.expander("🌐 Add External Reference URLs", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Export Format", ["TXT", "DOCX"], horizontal=True)

# ---------------- Title ----------------
st.markdown(f"""
<div class="title-box">
  <img src="{GSK_LOGO_RAW}" class="left-logo">
  <h1>💡 AI Sales Call Assistant — {brand_data[st.session_state.selected_brand]['display']}</h1>
  <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# ---------------- Load references ----------------
refs_folder = sel_brand["references_path"]
sales_folder = sel_brand["sales_path"]

local_refs_text, local_ref_files = "", []
sales_text, sales_files = "", []

if os.path.exists(refs_folder):
    for f in os.listdir(refs_folder):
        if f.lower().endswith((".pdf", ".txt")):
            local_ref_files.append(f)
            local_refs_text += read_file_text(os.path.join(refs_folder,f)) + "\n"

if os.path.exists(sales_folder):
    for f in os.listdir(sales_folder):
        if f.lower().endswith((".pdf", ".txt")):
            sales_files.append(f)
            sales_text += read_file_text(os.path.join(sales_folder,f)) + "\n"

corpus_folders=[]
if refs_folder: corpus_folders.append(refs_folder)
if sales_folder: corpus_folders.append(sales_folder)
chunks, chunk_meta = build_corpus_for_paths(corpus_folders)

# ---------------- PDF Upload ----------------
with st.expander("📄 Upload Custom PDF for AI Context", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
    st.session_state.pdf_summary_size = st.radio("PDF Summary Size", ["Consisted","Normal","Detailed"], horizontal=True)
    if uploaded_pdf:
        reader = PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text
        st.success(f"Loaded {len(full_text)} characters from uploaded PDF.")
        bullets_count = {"Consisted":5,"Normal":10,"Detailed":20}.get(st.session_state.pdf_summary_size,10)
        # basic summarization
        sts = re.findall(r'([A-Z][^.]{20,200})', full_text)
        st.session_state.pdf_summary = "\n".join(sts[:bullets_count])
    if st.session_state.pdf_summary:
        st.markdown(f"<div style='background:#E6F0FF;padding:12px;border-radius:8px;white-space:pre-line'>{escape(st.session_state.pdf_summary)}</div>", unsafe_allow_html=True)

# ---------------- Chat container ----------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for idx,msg in enumerate(st.session_state.chat_history):
    if msg["role"]=="user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(msg["content"])}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(msg["content"])}</div>', unsafe_allow_html=True)
        if msg.get("citations"):
            for c in msg["citations"]:
                fname = c["meta"]["filename"]
                blob_url = f"{REPO_BLOB_BASE}/references/{st.session_state.selected_brand}/{fname}" if fname in local_ref_files else f"{REPO_BLOB_BASE}/SalesModule/{st.session_state.selected_brand}/{fname}"
                st.markdown(f'<div class="citation-box"><b>Excerpt from {escape(fname)}:</b><br>{escape(c["text"][:800])}...<br><a href="{blob_url}" target="_blank">View full file</a></div>', unsafe_allow_html=True)
        if msg.get("audio"):
            try: st.audio(base64.b64decode(msg["audio"]), format="audio/mp3")
            except: pass
        # ---------------- Feedback ----------------
        fb_cols = st.columns(4)
        fb_labels = ["👍 Like","👎 Dislike","😐 Neutral","ℹ️ Need more"]
        for i,lbl in enumerate(fb_labels):
            if fb_cols[i].button(lbl, key=f"fb_{idx}_{i}"):
                st.session_state.main_input = lbl
                # TODO: handle dislike / need more logic interactive followup here
st.markdown('</div>', unsafe_allow_html=True)

# ---------------- Suggestion pills ----------------
def build_suggestions(brand_key, persona, barrier_list, segment, specialty, objective):
    s=[]
    s.append(f"Generate call flow for {persona} focused on {objective}.")
    if barrier_list: s.append(f"Handle objection: {', '.join(barrier_list[:2])} for {persona}.")
    else: s.append(f"Identify common objections for {persona}.")
    s.append(f"Summarize HCP persona insights for {persona}.")
    s.append(f"Key talking points for {brand_data[brand_key]['display']} in {segment}.")
    s.append(f"Draft short adoption message for {brand_data[brand_key]['display']} to a {specialty}.")
    return s

with st.expander("Prompt Suggestions (click to autofill)", expanded=False):
    suggs = build_suggestions(st.session_state.selected_brand, persona, barrier, segment, specialty, objective)
    st.markdown('<div class="suggestions-inline">', unsafe_allow_html=True)
    cols = st.columns([1,1,1])
    for i,s in enumerate(suggs):
        col=cols[i%3]
        if col.button(s, key=f"sugg_{i}"):
            st.session_state.main_input = s
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------- Input Area ----------------
with st.container():
    st.markdown('<div class="input-area">', unsafe_allow_html=True)
    st.text_area("Enter your message here...", key="main_input", value=st.session_state.main_input, placeholder="Type or click a suggestion...")
    send_clicked = st.button("Send", key="send_main", help="Send to AI")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------- AI Response (mock) ----------------
if send_clicked and st.session_state.main_input.strip():
    prompt_text = st.session_state.main_input
    # ---------------- Prepare citations ----------------
    top_refs = find_top_n_snippets(prompt_text, chunks, chunk_meta, top_n=3 if st.session_state.search_mode=="deep" else 1)
    citations = top_refs
    # ---------------- Generate AI response (mock placeholder) ----------------
    ai_response = f"AI response for: {prompt_text[:200]}"
    st.session_state.chat_history.append({
        "role":"ai",
        "content":ai_response,
        "citations":citations,
        "audio":generate_audio(ai_response)
    })
    st.session_state.main_input = ""  # clear input

# ---------------- Footer / Disclaimer ----------------
st.markdown('<div class="fixed-disclaimer">⚠️ Disclaimer: This tool is for educational and sales support purposes only. Not for medical prescription or patient advice.</div>', unsafe_allow_html=True)
