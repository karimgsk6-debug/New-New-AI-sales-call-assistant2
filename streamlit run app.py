# app_final_merged.py - AI Sales Call Assistant (with Groq, RAG, citations, roleplay)
import streamlit as st
import os, re, io, base64, tempfile
from datetime import datetime
from html import escape

# -------------------------
# Soft imports
# -------------------------
try:
    from groq import Groq
except Exception:
    Groq = None

try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

try:
    from gtts import gTTS
except Exception:
    gTTS = None

# Fixed sklearn import
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except:
    SKLEARN_AVAILABLE = False

try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except:
    ELEVENLABS_AVAILABLE = False

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# Resources & Avatar
# -------------------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"

# -------------------------
# Session defaults
# -------------------------
def _init_session():
    defaults = {
        "chat_history": [], "main_input": "", "selected_brand": "shingrix",
        "temperature": 0.95, "search_mode": "deep",
        "medical_summary": "", "sales_summary": "",
        "uploaded_pdf_text": "", "pdf_summary": "",
        "feedback": {}, "dislike_state": None,
        "language": "English", "hcp_persona": "Friendly",
        "hcp_personality": "Friendly", "tone": "executive"
    }
    for k,v in defaults.items():
        st.session_state.setdefault(k,v)

_init_session()

# -------------------------
# CSS for hologram avatar + chat bubbles
# -------------------------
st.markdown("""
<style>
.title-box{ background: rgba(255,255,255,0.85); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; position:relative; margin-bottom:12px; }
.title-box img.left-logo{ position:absolute; left:12px; height:48px; }
.title-box img.right-logo{ position:absolute; right:12px; height:48px; }

/* User bubble */
.user-bubble{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }

/* AI bubble with avatar on left */
.ai-message { display:flex; align-items:flex-start; gap:12px; margin:10px 0; }
.ai-avatar { width:52px; height:52px; border-radius:50%; box-shadow: 0 0 12px rgba(0,255,255,0.6); flex-shrink:0; animation:holoPulse 2.5s infinite ease-in-out; }
@keyframes holoPulse { 0% { box-shadow:0 0 8px rgba(0,255,255,0.35);} 50% { box-shadow:0 0 22px rgba(0,255,255,0.9);} 100% { box-shadow:0 0 8px rgba(0,255,255,0.35);} }
.ai-bubble { background: rgba(255,255,255,0.06); border:1px solid rgba(0,255,255,0.18); color:#E6FBFF; padding:14px; border-radius:14px; backdrop-filter: blur(6px); max-width:90%; white-space:pre-wrap; }

.citation-box{ font-size:12px; color:#bcd; margin-left:6px; margin-bottom:6px; }
.fixed-disclaimer{ font-size:12px; color:#aac; margin-top:16px; opacity:0.9; }
.step-title{ font-weight:700; margin-top:8px; color:#BFF; }
.story{ font-style:italic; margin:6px 0 10px 0; color:#DFF; }
ul.assist-list{ margin:6px 0 6px 18px; padding:0; color:#DDF; }
.objection{ background:rgba(255,248,240,0.06); padding:8px; border-radius:8px; margin:6px 0; border:1px solid rgba(255,224,198,0.08); color:#FFD; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Background helper
# -------------------------
def set_dynamic_background(image_path):
    if not os.path.exists(image_path): return
    try:
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
        st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background: linear-gradient(90deg, rgba(255,140,0,0.06), rgba(255,165,0,0.02)),
                        url("data:image/png;base64,{encoded}");
            background-repeat: no-repeat;
            background-position: right top;
            background-size: cover;
        }}
        </style>
        """, unsafe_allow_html=True)
    except: pass

set_dynamic_background(BACKGROUND_PATH)

# -------------------------
# GROQ client loader
# -------------------------
def load_groq_client():
    api_key = os.getenv("GROQ_API_KEY","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") or (st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else "")
    if not api_key or Groq is None: return None
    try: return Groq(api_key=api_key)
    except: return None

# -------------------------
# Product Data
# -------------------------
brand_data = {
    "shingrix": {
        "display":"Shingrix",
        "segments":["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas":["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers":["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
        "specialties":["GP","Dermatologist","Cardiology","Endocrinology","Immunology","Internal Medicine","Rheumatology"],
        "references_path":".devcontainer/references/shingrix/",
        "sales_path":".devcontainer/SalesModule/shingrix/",
        "call_flow":["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Analyze"],
        "objections":{"efficacy":"Focus on durable protection and age-agnostic efficacy.","safety":"Acknowledge common AEs, contrast with shingles risk.","cost":"Frame cost as prevention of downstream complications."}
    },
    "jemperli": {
        "display":"Jemperli",
        "segments":["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas":["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers":["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties":["Oncologist","Medical Oncologist"],
        "references_path":".devcontainer/references/jemperli/",
        "sales_path":".devcontainer/SalesModule/jemperli/",
        "call_flow":["COCO","Anchor","Engage","Close"],
        "objections":{"efficacy":"Discuss durable responses and appropriate patient selection.","safety":"Share safety profile and monitoring guidance.","access":"Offer starter kits, initiation support, reimbursement pathways."}
    },
    "trelegy": {
        "display":"Trelegy",
        "segments":["Awareness","Diagnosis","Adoption","Adherence"],
        "personas":["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers":["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties":["GP","Pulmonologist","Internal Medicine","Respiratory Specialist"],
        "references_path":".devcontainer/references/trelegy/",
        "sales_path":".devcontainer/SalesModule/trelegy/",
        "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"],
        "objections":{"device":"Offer quick practical coaching and demo materials.","coverage":"Explain access options and patient support.","effectiveness":"Share comparative outcomes."}
    }
}

# -------------------------
# Session helpers for file reading, corpus building, summarization
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
    except: return ""

def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas = [],[]
    for folder in folders:
        if not folder or not os.path.exists(folder): continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf",".txt"))]
        for fname in files:
            p = os.path.join(folder,fname)
            text = read_file_text(p)
            if not text: continue
            sents = re.split(r'(?<=[\.\?\!])\s+',text)
            for i in range(0,max(1,len(sents)),chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename":fname,"folder":folder,"start":i})
    return chunks, metas

def local_search_snippets(query,chunks,metas,top_n=3):
    if not chunks: return []
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks+[query])
            chunk_vecs = vectorizer.transform(chunks)
            q_vec = vectorizer.transform([query])
            sims = linear_kernel(q_vec,chunk_vecs).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            results=[]
            for idx in top_idxs:
                if sims[idx]<=0: continue
                results.append({"score":float(sims[idx]),"text":chunks[idx],"meta":metas[idx]})
            return results
        except: pass
    # fallback simple search
    out=[]
    q=query.lower()
    for i,c in enumerate(chunks):
        if q in c.lower():
            out.append({"score":1.0,"text":c,"meta":metas[i]})
            if len(out)>=top_n: break
    return out

def simple_summary(text,bullets=6):
    if not text: return ""
    sents = re.split(r'(?<=[\.\?\!])\s+',text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- "+s for s in selected])

def model_summarize(text,bullets=6):
    if not text: return ""
    client = load_groq_client()
    if client:
        try:
            prompt=f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
                        messages=[{"role":"user","content":prompt}],
                        temperature=0.2)
            content = getattr(resp.choices[0].message,"content",None) or getattr(resp.choices[0],"text","")
            return content
        except: return simple_summary(text,bullets)
    else:
        return simple_summary(text,bullets)

# -------------------------
# Audio generation
# -------------------------
def generate_audio(text):
    if not text: return ""
    if ELEVENLABS_AVAILABLE:
        try:
            elevenlabs.api_key = st.secrets.get("ELEVENLABS_API_KEY","")
            audio_stream = elevenlabs.generate(text=text,voice="alloy",model="eleven_multilingual_v1",stream=True)
            tmp = tempfile.NamedTemporaryFile(delete=False,suffix=".mp3")
            with open(tmp.name,"wb") as f:
                for chunk in audio_stream: f.write(chunk)
            with open(tmp.name,"rb") as fh: return base64.b64encode(fh.read()).decode()
        except: pass
    if gTTS:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False,suffix=".mp3")
            gTTS(text=text,lang="en",slow=False).save(tmp.name)
            with open(tmp.name,"rb") as fh: return base64.b64encode(fh.read()).decode()
        except: pass
    return ""

# -------------------------
# Build corpus for selected brand
# -------------------------
# (to be used in roleplay and snippet retrieval)
def build_brand_corpus(brand_key):
    product_data = brand_data.get(brand_key,{})
    corpus_folders = [product_data.get("references_path",""),product_data.get("sales_path","")]
    chunks, chunk_meta = build_corpus_for_folders(corpus_folders)
    return chunks, chunk_meta

# -------------------------
# Sidebar UI
# -------------------------
with st.sidebar.expander("Filters & Options",expanded=True):
    brand_options=list(brand_data.keys())
    sel_brand = st.selectbox("Brand",brand_options,index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand=sel_brand
    bconf = brand_data[sel_brand]

    segment = st.selectbox("HCP Segment",bconf["segments"])
    persona_options = bconf["personas"]
    persona_sel = st.selectbox("HCP Persona",persona_options,index=0)
    st.session_state.hcp_persona=persona_sel

    hcp_personality = st.selectbox("HCP Personality", ["Assertive","Masked","Friendly","Details-oriented","Skeptic"])
    st.session_state.hcp_personality = hcp_personality

    barrier = st.multiselect("Doctor Barriers",bconf["barriers"])
    specialty = st.selectbox("Specialty",bconf["specialties"])
    objective = st.selectbox("Objective",["Awareness","Adoption","Retention"])
    st.session_state.temperature = st.slider("Temperature",0.0,1.0,st.session_state.temperature,0.05)
    st.session_state.search_mode = st.selectbox("Search Mode",["deep","shallow"])
    st.session_state.language = st.radio("Language",["English","Arabic"])
    st.session_state.tone = st.selectbox("Tone",["executive","coaching","persuasive","clinical"],index=0)
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history=[]
        st.experimental_rerun()

with st.sidebar.expander("🌐 External References (one URL per line)",expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options",expanded=False):
    export_format = st.radio("Choose Export Format",["TXT","DOCX"],horizontal=True)

# -------------------------
# Title Box
# -------------------------
st.markdown(f"""
<div class="title-box">
<img src="{GSK_LOGO_RAW}" class="left-logo">
<h2>💡 AI Sales Call Assistant — {bconf['display']}</h2>
<img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""",unsafe_allow_html=True)

# -------------------------
# Load & summarize references
# -------------------------
refs_folder = bconf.get("references_path","")
sales_folder = bconf.get("sales_path","")

combined_refs=""
if os.path.exists(refs_folder):
    for f in sorted(os.listdir(refs_folder)):
        if f.lower().endswith((".pdf",".txt")):
            combined_refs += read_file_text(os.path.join(refs_folder,f))+"\n"

combined_sales=""
if os.path.exists(sales_folder):
    for f in sorted(os.listdir(sales_folder)):
        if f.lower().endswith((".pdf",".txt")):
            combined_sales += read_file_text(os.path.join(sales_folder,f))+"\n"

if not st.session_state.medical_summary and combined_refs.strip():
    st.session_state.medical_summary = model_summarize(combined_refs,bullets=6)
if not st.session_state.sales_summary and combined_sales.strip():
    st.session_state.sales_summary = model_summarize(combined_sales,bullets=6)

with st.expander("📚 Medical References Summary",expanded=False):
    st.markdown(st.session_state.medical_summary or "No medical summary available.")

with st.expander("💼 Sales Module Summary",expanded=False):
    st.markdown(st.session_state.sales_summary or "No sales summary available.")

# -------------------------
# PDF upload
# -------------------------
uploaded_file = st.file_uploader("Upload PDF for summary (brand-specific)",type=["pdf"])
if uploaded_file and PdfReader:
    try:
        reader = PdfReader(uploaded_file)
        pdf_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = pdf_text
        st.session_state.pdf_summary = model_summarize(pdf_text,bullets=6)
        st.success("PDF summarized successfully!")
    except:
        st.error("Failed to read the uploaded PDF.")

if st.session_state.pdf_summary:
    with st.expander("📄 Uploaded PDF Summary"):
        st.markdown(st.session_state.pdf_summary)

# -------------------------
# Chat / Roleplay UI
# -------------------------
def render_chat():
    for msg in st.session_state.chat_history:
        if msg["role"]=="user":
            st.markdown(f'<div class="user-bubble">{escape(msg["content"])}</div>',unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="ai-message">
            <img src="{AI_AVATAR}" class="ai-avatar">
            <div class="ai-bubble">{escape(msg["content"])}</div>
            </div>
            """,unsafe_allow_html=True)

def roleplay(user_input:str)->str:
    client = load_groq_client()
    if not client:
        return f"[!] GROQ API not configured. Please replace 'ADD_GROQ_API_here' with your API key."
    chunks, metas = build_brand_corpus(st.session_state.selected_brand)
    context_snippets = "\n".join([s["text"] for s in local_search_snippets(user_input,chunks,metas,top_n=3)])
    final_prompt = f"""
You are a pharmaceutical sales assistant for {bconf['display']} interacting with HCP.
HCP Persona: {st.session_state.hcp_persona}, Personality: {st.session_state.hcp_personality}, Tone: {st.session_state.tone}.
Context Snippets: {context_snippets}

User says: {user_input}
Provide a professional response with per-sentence citations and actionable advice.
"""
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"user","content":final_prompt}],
            temperature=st.session_state.temperature
        )
        reply = getattr(resp.choices[0].message,"content",None) or getattr(resp.choices[0],"text","")
        return reply
    except Exception as e:
        return f"[!] Error from GROQ: {str(e)}"

# Input box
st.text_input("Type your message:",key="main_input",on_change=lambda: st.session_state.chat_history.append(
    {"role":"user","content":st.session_state.main_input})
)
if st.session_state.main_input.strip():
    user_input = st.session_state.main_input
    ai_reply = roleplay(user_input)
    st.session_state.chat_history.append({"role":"assistant","content":ai_reply})
    st.session_state.main_input=""
render_chat()
