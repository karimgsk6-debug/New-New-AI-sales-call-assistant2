# app.py - AI Sales Call Assistant (Full Enhanced Version)
import streamlit as st
import os, re, tempfile, base64, io
from datetime import datetime
from html import escape

# -------------------------
# Optional libraries
# -------------------------
try: from groq import Groq
except: Groq=None
try: from PyPDF2 import PdfReader
except: PdfReader=None
try: from gtts import gTTS
except: gTTS=None
try: from docx import Document; DOCX_AVAILABLE=True
except: DOCX_AVAILABLE=False
try: from sklearn.feature_extraction.text import TfidfVectorizer; from sklearn.metrics.pairwise import linear_kernel; SKLEARN_AVAILABLE=True
except: SKLEARN_AVAILABLE=False
try: import elevenlabs; ELEVENLABS_AVAILABLE=True
except: ELEVENLABS_AVAILABLE=False
try: import pyttsx3; PYTTSX3_AVAILABLE=True
except: PYTTSX3_AVAILABLE=False

# -------------------------
# Page config & background
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

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
    "medical_summary": "",
    "sales_summary": "",
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "language": "English",
}
for k,v in defaults.items():
    st.session_state.setdefault(k,v)

# -------------------------
# CSS & background
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
  display:flex;
  align-items:center;
  justify-content:center;
  position: relative;
}}
.title-box img.left-logo {{ position:absolute; left:12px; height:64px; }}
.title-box img.right-logo {{ position:absolute; right:12px; height:64px; }}
.chat-container {{ max-height: 62vh; overflow-y:auto; padding:12px; background: rgba(255,255,255,0.95); border-radius:8px; margin-bottom:160px; }}
.chat-bubble-user {{ background:#0078D7; color:white; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto; }}
.chat-bubble-ai {{ background:#eef9ff; color:#000; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }}
.suggestion-pill {{ background:#fff; border:1px solid #ddd; padding:8px 12px; border-radius:20px; margin:6px; cursor:pointer; display:inline-block; }}
.suggestion-pill:hover {{ background:#f0f8ff; }}
.citation-box {{ background:#fbfbff; border-left:4px solid #0078D7; padding:8px; margin-top:8px; border-radius:6px; font-size:13px; white-space:pre-wrap; }}
.input-area {{ position: fixed; left:20px; right:20px; bottom:18px; z-index:9999; display:flex; gap:8px; flex-direction:column; }}
.input-area textarea {{ width:100%; min-height:72px; max-height:250px; padding:10px; border-radius:8px; border:1px solid #ccc; resize:vertical; }}
.input-controls {{ display:flex; gap:8px; justify-content:flex-end; }}
.send-button {{ height:44px; padding:0 14px; border-radius:8px; border:none; background:#FF6F00; color:white; cursor:pointer; font-weight:600; }}
.feedback-button {{ height:36px; padding:0 10px; border-radius:6px; border:none; background:#ccc; color:#000; cursor:pointer; font-weight:600; }}
.feedback-button:hover {{ background:#aaa; }}
.fixed-disclaimer {{ position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# -------------------------
# Initialize GROQ client
# -------------------------
GROQ_API_KEY = "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"
client = None
if Groq and GROQ_API_KEY:
    try: client = Groq(api_key=GROQ_API_KEY)
    except: client=None

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
        "call_flow":["Pre-call planning","Prepare","Engage","Create Opportunities","Influence","Impact GSO","Post-call analysis"]
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
    }
}

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
            with open(path,"r",encoding="utf-8",errors="ignore") as fh: return fh.read()
    except: return ""

def simple_summary(text, bullets=6):
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    selected=[s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- "+s for s in selected])

def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas = [], []
    for folder in folders:
        if not folder or not os.path.exists(folder): continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf",".txt"))]
        for fname in files:
            p=os.path.join(folder,fname)
            text=read_file_text(p)
            if not text: continue
            sents = re.split(r'(?<=[\.\?\!])\s+',text)
            for i in range(0,max(1,len(sents)),chunk_size_sentences):
                chunk=" ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename":fname,"folder":folder,"start":i})
    return chunks, metas

def local_search_snippets(query,chunks,metas,top_n=3):
    if not chunks: return []
    if SKLEARN_AVAILABLE:
        try:
            vectorizer=TfidfVectorizer(stop_words="english").fit(chunks+[query])
            chunk_vecs=vectorizer.transform(chunks)
            q_vec=vectorizer.transform([query])
            sims=linear_kernel(q_vec,chunk_vecs).flatten()
            top_idxs=sims.argsort()[::-1][:top_n]
            return [{"score":float(sims[idx]),"text":chunks[idx],"meta":metas[idx]} for idx in top_idxs if sims[idx]>0]
        except: pass
    return [{"score":1.0,"text":c,"meta":metas[i]} for i,c in enumerate(chunks) if query.lower() in c.lower()][:top_n]

def generate_audio(text):
    if not text: return ""
    # Placeholder: can integrate ElevenLabs or gTTS with natural pauses
    return ""

# -------------------------
# Sidebar filters & PDF Upload
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options=list(brand_data.keys())
    sel_brand=st.selectbox("Brand", brand_options,index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand=sel_brand
    bconf=brand_data[sel_brand]
    segment=st.selectbox("Segment",bconf["segments"])
    persona=st.selectbox("HCP Persona",bconf["personas"])
    barrier=st.multiselect("Doctor Barrier",bconf["barriers"])
    specialty=st.selectbox("Specialty",bconf["specialties"])
    objective=st.selectbox("Objective",["Awareness","Adoption","Retention"])
    st.session_state.temperature=st.slider("Temperature",0.0,1.0,st.session_state.temperature,0.05)
    st.session_state.search_mode=st.selectbox("Search mode",["deep","shallow"])
    st.session_state.language=st.radio("Language",["English","Arabic"])
    uploaded_file = st.file_uploader("Upload PDF for summarization", type="pdf")
    if uploaded_file and PdfReader:
        pdf_text = "".join([p.extract_text() or "" for p in PdfReader(uploaded_file).pages])
        st.session_state.uploaded_pdf_text=pdf_text
        st.session_state.pdf_summary=simple_summary(pdf_text)

# -------------------------
# Title box
# -------------------------
st.markdown(f"""
<div class="title-box">
<img src="{GSK_LOGO_RAW}" class="left-logo">
<h2>💡 AI Sales Call Assistant — {bconf['display']}</h2>
<img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# -------------------------
# Load references & sales
# -------------------------
refs_folder=bconf["references_path"]
sales_folder=bconf["sales_path"]
combined_refs, combined_sales = "", ""
if os.path.exists(refs_folder):
    for f in sorted(os.listdir(refs_folder)):
        if f.lower().endswith((".pdf",".txt")): combined_refs+=read_file_text(os.path.join(refs_folder,f))+"\n"
if os.path.exists(sales_folder):
    for f in sorted(os.listdir(sales_folder)):
        if f.lower().endswith((".pdf",".txt")): combined_sales+=read_file_text(os.path.join(sales_folder,f))+"\n"
if not st.session_state.medical_summary and combined_refs.strip(): st.session_state.medical_summary=simple_summary(combined_refs)
if not st.session_state.sales_summary and combined_sales.strip(): st.session_state.sales_summary=simple_summary(combined_sales)

# -------------------------
# Collapsible summaries
# -------------------------
with st.expander("📚 Medical References Summary", expanded=False):
    st.markdown(st.session_state.medical_summary or "No medical summary available.")
with st.expander("💼 Sales Module Summary", expanded=False):
    st.markdown(st.session_state.sales_summary or "No sales summary available.")
if st.session_state.pdf_summary:
    with st.expander("📄 Uploaded PDF Summary", expanded=False):
        st.markdown(st.session_state.pdf_summary)

# -------------------------
# Build corpus
# -------------------------
corpus_folders=[refs_folder,sales_folder]
chunks, chunk_meta=build_corpus_for_folders(corpus_folders)

# -------------------------
# Prompt suggestions
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

# -------------------------
# Chat container & input
# -------------------------
chat_container = st.container()

def add_ai_response(prompt):
    snippets = local_search_snippets(prompt,chunks,chunk_meta,top_n=3)
    citation = "\n".join([f"{s['meta']['filename']} ({s['score']:.2f})" for s in snippets])
    # Build structured sales call
    steps = bconf.get("call_flow",[])
    response_text = f"**AI Response to: {prompt}**\n\n"
    for i,step in enumerate(steps):
        response_text += f"**Step {i+1}: {step}**\n"
        for sn in snippets:
            response_text += f"- {sn['text']}\n"
    st.session_state.chat_history.append({"role":"assistant","content":response_text,"citation":citation})

# Integrated input + prompt suggestions bubble
with st.form("main_input_form", clear_on_submit=True):
    suggs = make_suggestions(sel_brand, persona, barrier, segment, specialty, objective)
    st.markdown("### Prompt Suggestions:")
    cols = st.columns([1,1,1])
    for i,s in enumerate(suggs):
        col = cols[i%3]
        if col.button(s,key=f"sugg_{i}"): st.session_state.main_input = s
    user_input=st.text_area("Ask something:", st.session_state.main_input, height=80)
    submitted=st.form_submit_button("Send")
    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role":"user","content":user_input.strip()})
        add_ai_response(user_input.strip())
        st.session_state.main_input=""

# -------------------------
# Display chat & feedback
# -------------------------
with chat_container:
    for idx,entry in enumerate(st.session_state.chat_history):
        if entry["role"]=="user": st.markdown(f'<div class="chat-bubble-user">{escape(entry["content"])}</div>',unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-ai">{escape(entry["content"])}</div>',unsafe_allow_html=True)
            if "citation" in entry and entry["citation"]:
                st.markdown(f'<div class="citation-box">{escape(entry["citation"])}</div>',unsafe_allow_html=True)
            audio_b64 = generate_audio(entry["content"])
            if audio_b64: st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")
            # Feedback buttons
            feedback_cols=st.columns(3)
            if feedback_cols[0].button("👍 Like", key=f"like_{idx}"): st.success("Thanks for feedback!")
            if feedback_cols[1].button("👎 Dislike", key=f"dislike_{idx}"):
                st.warning("AI will ask clarification questions.")
                add_ai_response("Please clarify why previous response did not meet your needs.")
            if feedback_cols[2].button("💡 Need more", key=f"more_{idx}"):
                add_ai_response("Please expand more on previous answer.")

# -------------------------
# Footer
# -------------------------
st.markdown("""
<div class="fixed-disclaimer">
💡 This tool is for internal sales support purposes only. All medical info should be verified from official sources. 
</div>
""",unsafe_allow_html=True)
