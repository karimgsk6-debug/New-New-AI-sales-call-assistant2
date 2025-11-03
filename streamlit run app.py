# app.py - AI Sales Call Assistant (Full Copilot Merge)
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
# Session Defaults
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
# Brand Data
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
# CSS Styling for Copilot UI
# -------------------------
st.markdown("""
<style>
/* Background */
[data-testid="stAppViewContainer"] {background: linear-gradient(90deg,#f5f6fa,#e6f0ff);}

/* Chat bubbles */
.chat-bubble-user {background:#0078D7;color:white;padding:12px;border-radius:12px;margin:8px 0;max-width:78%;margin-left:auto;}
.chat-bubble-ai {background:#eef9ff;color:#000;padding:12px;border-radius:12px;margin:8px 0;max-width:78%;box-shadow:0 2px 6px rgba(0,0,0,0.04);}

/* feedback row */
.feedback-row {display:flex;gap:8px;margin-top:8px;align-items:center;}
.feedback-btn {background:#fff;border:1px solid #e6e9ee;padding:6px 10px;border-radius:8px;cursor:pointer;}
.combined-fixed {position: fixed;left:20px;right:20px;bottom:18px;z-index:9999;background: rgba(255,255,255,0.98);padding:12px;border-radius:10px;box-shadow:0 12px 40px rgba(0,0,0,0.08);}
.resizable-combined {resize: vertical;overflow: auto;border:1px solid #ddd;padding:10px;border-radius:8px;background:#fff;min-height:110px;max-height:400px;}
.suggestion-pill {display:inline-block;padding:6px 12px;border-radius:20px;background:#f6f8fa;margin:4px;border:1px solid #e6e9ee;font-size:14px;}
.fixed-disclaimer {position: fixed;left:0;right:0;bottom:0;background: rgba(255,255,255,0.7);padding:8px;border-top:2px solid #FF6F00;text-align:center;font-size:13px;z-index:9997;}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Helper Functions
# -------------------------
def read_file_text(path: str) -> str:
    if not os.path.exists(path): return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path,"r",encoding="utf-8",errors="ignore") as fh: return fh.read()
    except: return ""

def simple_summary(text:str, bullets:int=6)->str:
    if not text: return ""
    sents = re.split(r'(?<=[\.!\?])\s+', text)
    return "\n".join([f"- {s.strip()}" for s in sents[:bullets]])

def model_summarize(text:str, bullets:int=6)->str: return simple_summary(text, bullets)

def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas = [], []
    for folder in folders:
        if not folder or not os.path.exists(folder): continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf",".txt"))]
        for fname in files:
            p = os.path.join(folder,fname)
            text = read_file_text(p)
            if not text: continue
            sents = re.split(r'(?<=[\.!\?])\s+', text)
            for i in range(0, max(1,len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk: chunks.append(chunk); metas.append({"filename":fname,"folder":folder,"start":i})
    return chunks, metas

def local_search_snippets(query:str, chunks:list, metas:list, top_n:int=5):
    if not chunks or not query: return []
    q = query.lower().strip()
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks+[query])
            sims = linear_kernel(vectorizer.transform([query]), vectorizer.transform(chunks)).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            return [{"score":float(sims[i]),"text":chunks[i],"meta":metas[i]} for i in top_idxs if sims[i]>0]
        except: pass
    out=[]
    for i,c in enumerate(chunks):
        if q in c.lower(): out.append({"score":1.0,"text":c,"meta":metas[i]})
        if len(out)>=top_n: break
    return out

def generate_audio_base64(text:str)->str:
    if not text or not gTTS: return ""
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=text.replace("\n"," "), lang="en", slow=False).save(tmp.name)
        with open(tmp.name,"rb") as fh: return base64.b64encode(fh.read()).decode("utf-8")
    except: return ""

# -------------------------
# Sidebar (brand + filters + PDF upload)
# -------------------------
with st.sidebar:
    st.subheader("Brand & Filters")
    sel_brand = st.selectbox("Brand", list(brand_data.keys()), index=list(brand_data.keys()).index(st.session_state["selected_brand"]), format_func=lambda k: brand_data[k]["display"])
    st.session_state["selected_brand"]=sel_brand
    bconf=brand_data[sel_brand]

    persona = st.selectbox("HCP Persona", bconf.get("personas",[]))
    segment = st.selectbox("Segment", bconf.get("segments",[]))
    barrier = st.multiselect("Doctor Barrier", bconf.get("barriers",[]))
    specialty = st.selectbox("Specialty", bconf.get("specialties",[]))
    objective = st.selectbox("Objective",["Awareness","Adoption","Retention"])
    st.session_state["temperature"]=st.slider("Temperature",0.0,1.0,st.session_state["temperature"],0.05)
    st.session_state["search_mode"]=st.selectbox("Search mode",["deep","shallow"])
    st.session_state["language"]=st.radio("Language",["English","Arabic"])

    st.subheader("Upload PDF/TXT")
    uploaded_file = st.file_uploader("Upload file (PDF/TXT)", type=["pdf","txt"])
    if uploaded_file:
        try:
            text=""
            if uploaded_file.type=="application/pdf" and PdfReader:
                reader=PdfReader(uploaded_file)
                text="".join([p.extract_text() or "" for p in reader.pages])
            else: text=uploaded_file.getvalue().decode("utf-8",errors="ignore")
            st.session_state["pdf_summary"][sel_brand]=model_summarize(text)
            st.success("Uploaded file summarized for this brand.")
        except: st.error("Failed to read uploaded file.")

# -------------------------
# Build corpus for local search
# -------------------------
refs_folder = brand_data[sel_brand]["references_path"]
sales_folder = brand_data[sel_brand]["sales_path"]
corpus_folders = [p for p in (refs_folder,sales_folder) if os.path.exists(p)]
chunks, metas = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# Copilot-style AI response + feedback
# -------------------------
def add_ai_response(prompt:str, follow_up:bool=False, context_previous:str=None):
    snippets = local_search_snippets(prompt,chunks,metas,top_n=6)
    out=["Thanks — I hear you. Let’s tackle this together." if not follow_up else "Thanks — refining this for you.",""]
    out.append("**Opening lines:**")
    out.append("- 'I appreciate you bringing this up — important for patient decisions.'")
    if not follow_up:
        out.append("**Call Flow:**")
        for step in brand_data[sel_brand]["call_flow"]:
            out.append(f"- {step}: refer to sales module/examples")
    else:
        out.append("**Follow-up Feedback:**")
        if context_previous: out.append(f"- Regarding previous: \"{context_previous[:140]}...\"")
        out.append("- Choices: A) unclear, B) not practical, C) too technical, D) other")
    ai_text="\n".join(out)
    audio_b64=generate_audio_base64(ai_text)
    st.session_state["chat_history"].append({"role":"assistant","text":ai_text,"audio_b64":audio_b64})

# -------------------------
# Chat Display
# -------------------------
st.markdown('<div class="chat-container">',unsafe_allow_html=True)
for idx, entry in enumerate(st.session_state["chat_history"]):
    role=entry.get("role","assistant"); text=entry.get("text","")
    if role=="user":
        st.markdown(f'<div class="chat-bubble-user">🧑‍💼 {escape(text)}</div>',unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 {escape(text).replace("\\n","<br>")}</div>',unsafe_allow_html=True)
        if entry.get("audio_b64"):
            try: st.audio(io.BytesIO(base64.b64decode(entry["audio_b64"])),format="audio/mp3")
            except: pass
        fb_key=f"fb_{idx}"
        st.markdown('<div class="feedback-row">',unsafe_allow_html=True)
        c1,c2,c3,c4=st.columns([1,1,1,6])
        with c1:
            if st.button("👍 Like",key=f"like_{idx}"):
                st.session_state["feedback"][fb_key]="like"
        with c2:
            if st.button("👎 Dislike",key=f"dislike_{idx}"):
                st.session_state["feedback"][fb_key]="dislike"
                add_ai_response("User disliked previous response — follow up",follow_up=True,context_previous=text)
        with c3:
            if st.button("ℹ️ Need More",key=f"needmore_{idx}"):
                st.session_state["feedback"][fb_key]="need_more"
                add_ai_response("User requested more detail — follow up",follow_up=True,context_previous=text)
        with c4:
            fb_val=st.session_state["feedback"].get(fb_key,"")
            if fb_val: st.markdown(f"**Feedback:** {fb_val}")
        st.markdown('</div>',unsafe_allow_html=True)
st.markdown('</div>',unsafe_allow_html=True)

# -------------------------
# Bottom fixed box (suggestions + input)
# -------------------------
def make_suggestions(brand_key, persona_val, barriers_list, segment_val, specialty_val, objective_val):
    s=[]
    s.append(f"Generate call flow for {persona_val} focused on {objective_val}.")
    if barriers_list:
        s.append(f"Handle objection: {', '.join(barriers_list[:2])} for {persona_val}.")
    s.append(f"Summarize HCP persona insights for {persona_val}.")
    s.append(f"Key talking points for {brand_data[brand_key]['display']} in {segment_val}.")
    s.append(f"Draft adoption message for {brand_data[brand_key]['display']} to a {specialty_val}.")
    return s

suggestions=make_suggestions(sel_brand,persona,barrier,segment,specialty,objective)
st.markdown('<div class="combined-fixed">',unsafe_allow_html=True)
st.markdown('<div class="resizable-combined">',unsafe_allow_html=True)
with st.expander("💡 Prompt Suggestions (click)"):
    pills_html=" ".join([f'<span class="suggestion-pill">{escape(s)}</span>' for s in suggestions])
    st.markdown(pills_html,unsafe_allow_html=True)
    btn_cols = st.columns(min(4,len(suggestions)))
    for i,s in enumerate(suggestions):
        if btn_cols[i % len(btn_cols)].button(s,key=f"suggbtn_{i}"):
            st.session_state["main_input"]=s
            st.session_state["chat_history"].append({"role":"user","text":s})
            add_ai_response(s)

main_text=st.text_area("Type message or click a suggestion",value=st.session_state.get("main_input",""),height=96)
col_send,col_clear=st.columns([1,1])
with col_send:
    if st.button("Send"):
        if main_text.strip():
            st.session_state["chat_history"].append({"role":"user","text":main_text.strip()})
            add_ai_response(main_text.strip())
            st.session_state["main_input"]=""
with col_clear:
    if st.button("Clear input"): st.session_state["main_input"]=""

st.markdown('</div>',unsafe_allow_html=True)
st.markdown('</div>',unsafe_allow_html=True)

# -------------------------
# Disclaimer
# -------------------------
st.markdown('<div class="fixed-disclaimer">⚠️ Internal tool — grounded in GSK-approved references. Verify clinical info before external use.</div>',unsafe_allow_html=True)
