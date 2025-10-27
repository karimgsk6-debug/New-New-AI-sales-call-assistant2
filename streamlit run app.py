# app.py - Full AI Sales Call Assistant with TRELEGY, voice, feedback, prompt suggestions

import streamlit as st
import os, re, tempfile, base64, io
from html import escape
from PyPDF2 import PdfReader
from gtts import gTTS

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
# CSS & background
# -------------------------
CSS = """
<style>
.title-box { background: rgba(255,255,255,0.95); padding: 12px; border-radius: 10px; margin-bottom: 12px; display:flex; align-items:center; justify-content:center; position:relative;}
.title-box img.left-logo { position:absolute; left:12px; height:64px; }
.title-box img.right-logo { position:absolute; right:12px; height:64px; }
.chat-container { max-height:60vh; overflow-y:auto; padding:12px; background: rgba(255,255,255,0.95); border-radius:8px; margin-bottom:160px; }
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
# Space for GROQ API key
# -------------------------
GROQ_API_KEY = "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"

# -------------------------
# Brand info
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
    try:
        if path.lower().endswith(".pdf"):
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

def simple_summary(text, bullets=6):
    if not text: return ""
    sents = re.split(r'(?<=[\.!\?])\s+',text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- "+s for s in selected])

def generate_audio_base64(text):
    if not text: return ""
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=text, lang="en", slow=False).save(tmp.name)
        with open(tmp.name,"rb") as fh:
            return base64.b64encode(fh.read()).decode()
    except Exception as e:
        return ""

# -------------------------
# Sidebar filters
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
# Title Box
# -------------------------
st.markdown(f"""
<div class="title-box">
<h2>💡 AI Sales Call Assistant — {brand_data[sel_brand]['display']}</h2>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Load references and sales summaries
# -------------------------
refs_folder = bconf["references_path"]
sales_folder = bconf["sales_path"]
combined_refs = ""
if os.path.exists(refs_folder):
    for f in sorted(os.listdir(refs_folder)):
        if f.lower().endswith((".pdf",".txt")):
            combined_refs += read_file_text(os.path.join(refs_folder,f)) + "\n"
combined_sales = ""
if os.path.exists(sales_folder):
    for f in sorted(os.listdir(sales_folder)):
        if f.lower().endswith((".pdf",".txt")):
            combined_sales += read_file_text(os.path.join(sales_folder,f)) + "\n"
if not st.session_state.medical_summary and combined_refs.strip():
    st.session_state.medical_summary = simple_summary(combined_refs, bullets=6)
if not st.session_state.sales_summary and combined_sales.strip():
    st.session_state.sales_summary = simple_summary(combined_sales, bullets=6)

# -------------------------
# Build corpus
# -------------------------
corpus_folders = [refs_folder, sales_folder]
chunks, chunk_meta = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# AI response + feedback + voice
# -------------------------
def add_ai_response(prompt, follow_up=False, context_previous=None):
    # simple snippet selection from corpus
    snippets = [c["text"] for c in chunk_meta] if chunk_meta else []
    ai_text = f"Simulated AI response for: {prompt}\n\n" + "\n".join(snippets[:5])
    audio_b64 = generate_audio_base64(ai_text)
    entry = {"role":"assistant","text":ai_text,"audio_b64":audio_b64}
    st.session_state.chat_history.append(entry)

# -------------------------
# Prompt suggestions
# -------------------------
def make_suggestions(brand_key):
    b = brand_data[brand_key]
    s=[]
    for persona in b["personas"]:
        s.append(f"Generate call flow for {persona} in {brand_key}.")
        s.append(f"Handle barrier for {persona}.")
        s.append(f"Summarize key talking points for {persona}.")
    return s

# -------------------------
# Chat render
# -------------------------
def render_chat():
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for idx, entry in enumerate(st.session_state.chat_history):
        role = entry.get("role","assistant")
        text = entry.get("text","")
        audio_b64 = entry.get("audio_b64",None)
        if role=="user":
            st.markdown(f'<div class="chat-bubble-user">{escape(text)}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-ai">{escape(text).replace("\\n","<br>")}</div>', unsafe_allow_html=True)
            if audio_b64:
                st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")
            col1,col2,col3=st.columns(3)
            with col1:
                if st.button("👍 Like", key=f"like_{idx}"): st.session_state.feedback[idx]="like"
            with col2:
                if st.button("👎 Dislike", key=f"dislike_{idx}"): st.session_state.feedback[idx]="dislike"
            with col3:
                if st.button("ℹ️ Need More", key=f"needmore_{idx}"): 
                    st.session_state.feedback[idx]="need_more"
                    add_ai_response(text)
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Chat input and prompt suggestions at bottom
# -------------------------
st.markdown('<div style="position:fixed; bottom:0; left:0; right:0; background:white; padding:8px; z-index:999;">', unsafe_allow_html=True)
with st.form("input_form", clear_on_submit=True):
    # prompt suggestions
    with st.expander("💡 Prompt Suggestions", expanded=True):
        suggs = make_suggestions(sel_brand)
        for s in suggs:
            if st.button(s, key=f"sugg_{s}"):
                st.session_state.main_input = s
    user_input = st.text_area("Ask something:", st.session_state.main_input, height=96)
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role":"user","text":user_input.strip()})
        add_ai_response(user_input.strip())
        st.session_state.main_input=""
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Render chat
# -------------------------
render_chat()

# -------------------------
# Footer
# -------------------------
st.markdown('<div class="fixed-disclaimer">💬 AI Sales Call Assistant — Confidential | Powered by GSK Modules</div>', unsafe_allow_html=True)
