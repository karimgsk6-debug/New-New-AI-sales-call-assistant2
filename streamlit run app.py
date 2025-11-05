# app.py - Full AI Sales Call Assistant (Enhanced)
import streamlit as st
import os, re, tempfile, base64, io
from datetime import datetime
from html import escape

# Optional libs
try:
    from groq import Groq
except:
    Groq = None

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

try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except:
    ELEVENLABS_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except:
    PYTTSX3_AVAILABLE = False

# -------------------------
# Page config & background
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_BLOB_BASE = f"https://github.com/{REPO_USER}/{REPO_NAME}/blob/{COMMIT}/.devcontainer"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
BACKGROUND_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/Bacground2.png"
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
    "feedback": {},
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
  background-position: right;
  background-attachment: flex;
}}
.title-box {{
  background: rgba(255,255,255,0.7);
  padding: 12px;
  border-radius: 10px;
  margin-bottom: 12px;
  position: relative;
  display:flex;
  align-items:center;
  justify-content:center;
}}
.title-box img.left-logo {{ position:absolute; left:12px; height:64px; }}
.title-box img.right-logo {{ position:absolute; right:12px; height:70px; }}
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
# Initialize GROQ client
# -------------------------
GROQ_API_KEY = "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"
client = None
if Groq and GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except:
        client = None

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
    sents = re.split(r'(?<=[\.\?\!])\s+',text)
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

def generate_audio(text):
    if not text: return ""
    if ELEVENLABS_AVAILABLE:
        try:
            elevenlabs.api_key = st.secrets.get("ELEVENLABS_API_KEY","ELEVENLABS_API_KEY_HERE")
            audio_stream = elevenlabs.generate(text=text, voice="alloy", model="eleven_multilingual_v1", stream=True)
            tmp = tempfile.NamedTemporaryFile(delete=False,suffix=".mp3")
            with open(tmp.name,"wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
            with open(tmp.name,"rb") as fh: return base64.b64encode(fh.read()).decode()
        except: pass
    if gTTS:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False,suffix=".mp3")
            gTTS(text=text, lang="en", slow=False).save(tmp.name)
            with open(tmp.name,"rb") as fh: return base64.b64encode(fh.read()).decode()
        except: pass
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

with st.sidebar.expander("🌐 Add External Reference URLs (one per line)", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT","DOCX"], horizontal=True)

# -------------------------
# Title box
# -------------------------
st.markdown(f"""
<div class="title-box">
<img src="{GSK_LOGO_RAW}" class="left-logo">
<h2>💡 AI Sales Call Assistant — {brand_data[sel_brand]['display']}</h2>
<img src="{AI_LOGO_RAW}" class="right-logo">
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
    st.session_state.medical_summary = model_summarize(combined_refs, bullets=6)
if not st.session_state.sales_summary and combined_sales.strip():
    st.session_state.sales_summary = model_summarize(combined_sales, bullets=6)

with st.expander("📚 Medical References Summary", expanded=False):
    st.markdown(st.session_state.medical_summary or "No medical summary available.")
with st.expander("💼 Sales Module Summary", expanded=False):
    st.markdown(st.session_state.sales_summary or "No sales summary available.")

# -------------------------
# PDF Upload and summarize
# -------------------------
uploaded_file = st.file_uploader("Upload PDF for summary", type=["pdf"])
if uploaded_file and PdfReader:
    reader = PdfReader(uploaded_file)
    pdf_text = "".join([p.extract_text() or "" for p in reader.pages])
    st.session_state.uploaded_pdf_text = pdf_text
    st.session_state.pdf_summary = model_summarize(pdf_text, bullets=6)
    st.success("PDF summarized successfully!")
if st.session_state.pdf_summary:
    with st.expander("📄 Uploaded PDF Summary", expanded=False):
        st.markdown(st.session_state.pdf_summary)

# -------------------------
# Build corpus
# -------------------------
corpus_folders = [refs_folder, sales_folder]
chunks, chunk_meta = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

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
# AI Response with APACT + humanized + interactive feedback
# -------------------------
def add_ai_response(prompt, follow_up=False):
    snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=5)
    citation = "\n".join([f"{s['meta']['filename']} ({s['score']:.2f})" for s in snippets])

    response_lines = []

    if not follow_up:
        # --- APACT ---
        response_lines.append(f"**Acknowledge:** Thank you for raising this concern. I understand your perspective.")
        response_lines.append("**Probing:** Could you clarify if your main concern is about efficacy, safety, or patient eligibility?")
        response_lines.append("**Actions:** Based on your input, here are recommended steps:")
        for step in bconf["call_flow"]:
            step_snippets = [s['text'] for s in snippets if step.lower() in s['text'].lower()]
            if step_snippets:
                response_lines.append(f"**{step}:**")
                for sn in step_snippets:
                    response_lines.append(f"- {sn}")
            else:
                response_lines.append(f"**{step}:** - Refer to the sales module and uploaded references for guidance.")
        response_lines.append("**Confirm:** Does this approach address your concern sufficiently?")
        response_lines.append("**Transition:** If yes, we can move on to the next discussion point or objective.")
        response_lines.append("\n*Note: Tailored using sales module and uploaded references.*")
    else:
        # Follow-up for feedback
        response_lines.append("I noticed you disliked the previous answer. Could you help me understand better?")
        response_lines.append("- What specific part was unclear or insufficient?")
        response_lines.append("- Are you looking for more examples, data, or step-by-step guidance?")
        response_lines.append("- Any particular objection you want me to focus on next?")

    ai_text = "\n".join(response_lines)
    st.session_state.chat_history.append({"role":"assistant","content":ai_text,"citation":citation})

# -------------------------
# Chat container and input
# -------------------------
chat_container = st.container()

with st.expander("💡 Prompt Suggestions (Click to Expand)", expanded=False):
    suggs = make_suggestions(sel_brand, persona, barrier, segment, specialty, objective)
    sugg_cols = st.columns(3)
    for i, s in enumerate(suggs):
        col = sugg_cols[i % 3]
        if col.button(s, key=f"sugg_{i}"):
            st.session_state.main_input = s

with st.form("main_input_form", clear_on_submit=True):
    user_input = st.text_area("Ask something:", st.session_state.main_input, height=72)
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role":"user","content":user_input.strip()})
        add_ai_response(user_input.strip())
        st.session_state.main_input = ""

# -------------------------
# Display chat with audio and interactive feedback
# -------------------------
with chat_container:
    for idx,entry in enumerate(st.session_state.chat_history):
        if entry["role"]=="user":
            st.markdown(f'<div class="chat-bubble-user">{escape(entry["content"])}</div>',unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-ai">{escape(entry["content"])}</div>',unsafe_allow_html=True)
            if "citation" in entry and entry["citation"]:
                st.markdown(f'<div class="citation-box">{escape(entry["citation"])}</div>',unsafe_allow_html=True)
            # Audio playback
            audio_b64 = generate_audio(entry["content"])
            if audio_b64:
                st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")
            # Feedback buttons
            fb_cols = st.columns(3)
            if entry["content"] not in st.session_state.feedback:
                if fb_cols[0].button("👍 Like", key=f"like_{idx}"): st.session_state.feedback[entry["content"]]="like"
                if fb_cols[1].button("👎 Dislike", key=f"dislike_{idx}"): 
                    st.session_state.feedback[entry["content"]]="dislike"
                    add_ai_response("Follow-up based on user dislike", follow_up=True)
                if fb_cols[2].button("ℹ️ Need More", key=f"needmore_{idx}"): 
                    st.session_state.feedback[entry["content"]]="need_more"
                    add_ai_response("The user requested more information; expand the previous answer.", follow_up=True)

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown("""
<div class="fixed-disclaimer">
💡 This tool is for internal sales support purposes only. All medical info should be verified from official sources. 
</div>
""",unsafe_allow_html=True)
