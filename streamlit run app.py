# app.py - AI Sales Call Assistant (Final Merged Version)
import streamlit as st
import os, re, tempfile, base64, io
from html import escape
from datetime import datetime

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
# Initialize session_state
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
for k,v in defaults.items():
    st.session_state.setdefault(k,v)

# Initialize nested dicts
for nested_key in ["medical_summary", "sales_summary", "pdf_summary", "feedback"]:
    if nested_key not in st.session_state or not isinstance(st.session_state[nested_key], dict):
        st.session_state[nested_key] = {}

# -------------------------
# -------------------------
# GROQ API Placeholder
# -------------------------
# You can add your GROQ API key here and use it in your backend processing.
# This section is hidden from the UI.
GROQ_API_KEY = "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"  # <-- Replace with your actual GROQ API key

def query_groq_api(prompt):
    """
    Example function to query GROQ API.
    Currently just a placeholder; integrate the actual API call here.
    """
    if GROQ_API_KEY == "add_GROQ_API_here":
        return "GROQ API not configured."
    # TODO: Replace with real GROQ query logic
    # response = groq_client.query(GROQ_API_KEY, prompt)
    # return response
    return f"Processed with GROQ: {prompt[:50]}..."

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
    return simple_summary(text, bullets)

def generate_audio_base64(text):
    if not text or not gTTS: return ""
    tts_text = re.sub(r'\n\s*\n', ' ... ', text)
    tts_text = tts_text.replace("\n", " ")
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=tts_text, lang="en", slow=False).save(tmp.name)
        with open(tmp.name, "rb") as fh:
            return base64.b64encode(fh.read()).decode()
    except:
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

with st.sidebar.expander("🌐 Add External Reference URLs (one per line)", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT","DOCX"], horizontal=True)

# -------------------------
# Title box
# -------------------------
st.markdown(f"""
<div class="title-box" style="background:rgba(255,255,255,0.95);padding:12px;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:12px;">
<h2>💡 AI Sales Call Assistant — {bconf['display']}</h2>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Load references and sales summaries per brand
# -------------------------
refs_folder = bconf["references_path"]
sales_folder = bconf["sales_path"]

# Medical references summary
combined_refs = ""
if os.path.exists(refs_folder):
    for f in sorted(os.listdir(refs_folder)):
        if f.lower().endswith((".pdf",".txt")):
            combined_refs += read_file_text(os.path.join(refs_folder,f)) + "\n"
if combined_refs.strip():
    st.session_state.medical_summary[sel_brand] = model_summarize(combined_refs, bullets=6)
else:
    st.session_state.medical_summary[sel_brand] = "No medical references available."

# Sales module summary
combined_sales = ""
if os.path.exists(sales_folder):
    for f in sorted(os.listdir(sales_folder)):
        if f.lower().endswith((".pdf",".txt")):
            combined_sales += read_file_text(os.path.join(sales_folder,f)) + "\n"
if combined_sales.strip():
    st.session_state.sales_summary[sel_brand] = model_summarize(combined_sales, bullets=6)
else:
    st.session_state.sales_summary[sel_brand] = "No sales module content available."

with st.expander("📚 Medical References Summary", expanded=False):
    st.markdown(st.session_state.medical_summary.get(sel_brand,""))
with st.expander("💼 Sales Module Summary", expanded=False):
    st.markdown(st.session_state.sales_summary.get(sel_brand,""))

# -------------------------
# PDF Upload
# -------------------------
uploaded_file = st.file_uploader("Upload PDF for summary", type=["pdf"])
if uploaded_file and PdfReader:
    reader = PdfReader(uploaded_file)
    pdf_text = "".join([p.extract_text() or "" for p in reader.pages])
    st.session_state.pdf_summary[sel_brand] = model_summarize(pdf_text, bullets=6)
    st.success("PDF summarized successfully!")
if sel_brand in st.session_state.pdf_summary:
    with st.expander("📄 Uploaded PDF Summary", expanded=False):
        st.markdown(st.session_state.pdf_summary[sel_brand])

# -------------------------
# Build corpus
# -------------------------
corpus_folders = [refs_folder, sales_folder]
chunks, chunk_meta = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# Prompt suggestions helper
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
# AI Response builder
# -------------------------
def add_ai_response(prompt):
    snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=5)
    out_lines = []
    out_lines.append("**🟢 Acknowledge**")
    out_lines.append("I understand the concern you've raised. Example phrasing: 'I know time is tight — here's a 60-second way to explain benefit.'")
    out_lines.append("**🔵 Probe — sample questions**")
    out_lines.append("- Open: 'Can you tell me more about which patients you're most worried about?'")
    out_lines.append("- Closed: 'Is your main worry safety, efficacy, or cost?'")
    out_lines.append("**🟠 Share insights**")
    if snippets:
        for s in snippets:
            out_lines.append(f"- {s['text']}")
    else:
        out_lines.append("- No exact matches found in the reference materials.")
    out_lines.append("**🔴 Close / Next steps**")
    out_lines.append("- Offer a follow-up resource or schedule next call.")
    ai_text = "\n".join(out_lines)
    st.session_state.chat_history.append({"role":"assistant","text":ai_text})
    return ai_text

# -------------------------
# Chat area & suggestions bubble
# -------------------------
with st.container():
    sugg_exp = st.expander("💡 Prompt Suggestions", expanded=False)
    suggestions = make_suggestions(sel_brand, persona, barrier, segment, specialty, objective)
    for s in suggestions:
        if st.button(s, key=f"sugg_{s[:20]}"):
            st.session_state.main_input = s

# -------------------------
# Chat input & display
# -------------------------
col1, col2 = st.columns([4,1])
with col1:
    user_input = st.text_input("Ask AI:", value=st.session_state.main_input, key="chat_input")
    if st.button("Send") and user_input.strip():
        st.session_state.chat_history.append({"role":"user","text":user_input})
        ai_text = add_ai_response(user_input)
        # Generate audio
        audio_b64 = generate_audio_base64(ai_text)
        if audio_b64:
            st.audio(base64.b64decode(audio_b64), format="audio/mp3")
        st.session_state.main_input = ""

# Render chat history
for entry in st.session_state.chat_history:
    role = entry.get("role","")
    text = entry.get("text","")
    if role=="user":
        st.markdown(f"**You:** {text}")
    elif role=="assistant":
        st.markdown(f"**AI:** {text}")
        # Feedback buttons
        col_like,col_dislike,col_more = st.columns(3)
        if col_like.button("👍", key=f"like_{len(st.session_state.chat_history)}"):
            st.session_state.feedback[entry["text"]] = "like"
        if col_dislike.button("👎", key=f"dislike_{len(st.session_state.chat_history)}"):
            st.session_state.feedback[entry["text"]] = "dislike"
        if col_more.button("📝 Need More", key=f"more_{len(st.session_state.chat_history)}"):
            st.session_state.feedback[entry["text"]] = "need more"

# -------------------------
# Footer
# -------------------------
st.markdown("""
<hr>
<div style="text-align:center;font-size:12px;color:gray;">
💬 AI Assistant for Sales Enablement. All content is based on internal training material and medical references. Not for public use.
</div>
""", unsafe_allow_html=True)
