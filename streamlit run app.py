# app.py - Final Full Version with Footer
import streamlit as st
import os, re, tempfile, base64, io
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

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# GROQ API backend variable (not exposed)
# -------------------------
GROQ_API_KEY = "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"
client = None  # placeholder for GROQ client init if needed

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
    "pdf_summary": {},
    "medical_summary": {},
    "sales_summary": {},
    "feedback": {},
    "language": "English",
}
for k,v in defaults.items():
    st.session_state.setdefault(k,v)

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

def simple_summary(text, bullets=6):
    if not text: return ""
    sents = re.split(r'(?<=[\.!\?])\s+',text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- "+s for s in selected])

def model_summarize(text, bullets=6):
    return simple_summary(text, bullets)

def generate_audio_base64(text):
    if not text or not gTTS: return ""
    tts_text = re.sub(r'\n\s*\n', ' ... ', text).replace("\n"," ")
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=tts_text, lang="en", slow=False).save(tmp.name)
        with open(tmp.name,"rb") as fh:
            return base64.b64encode(fh.read()).decode()
    except:
        return ""

def local_search_snippets(query,chunks,metas,top_n=5):
    out=[]
    q=query.lower()
    for i,c in enumerate(chunks):
        if q in c.lower():
            out.append({"score":1.0,"text":c,"meta":metas[i]})
            if len(out)>=top_n: break
    return out

def build_clean_citation(snippets):
    return ""  # references removed from AI response

# -------------------------
# Sidebar: Brand & Options
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
# Title box
# -------------------------
st.markdown(f"""
<div style="background:rgba(255,255,255,0.95);padding:12px;border-radius:10px;margin-bottom:12px;display:flex;align-items:center;justify-content:center;">
<h2>💡 AI Sales Call Assistant — {brand_data[sel_brand]['display']}</h2>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Load references & sales summaries per brand
# -------------------------
for brand in brand_data:
    refs_folder = brand_data[brand]["references_path"]
    sales_folder = brand_data[brand]["sales_path"]
    combined_refs, combined_sales = "", ""
    if os.path.exists(refs_folder):
        for f in sorted(os.listdir(refs_folder)):
            if f.lower().endswith((".pdf",".txt")):
                combined_refs += read_file_text(os.path.join(refs_folder,f)) + "\n"
    if os.path.exists(sales_folder):
        for f in sorted(os.listdir(sales_folder)):
            if f.lower().endswith((".pdf",".txt")):
                combined_sales += read_file_text(os.path.join(sales_folder,f)) + "\n"
    if brand not in st.session_state.medical_summary and combined_refs.strip():
        st.session_state.medical_summary[brand] = model_summarize(combined_refs, bullets=6)
    if brand not in st.session_state.sales_summary and combined_sales.strip():
        st.session_state.sales_summary[brand] = model_summarize(combined_sales, bullets=6)

# Show current brand summaries
with st.expander("📚 Medical References Summary", expanded=False):
    st.markdown(st.session_state.medical_summary.get(sel_brand,"No medical summary available."))
with st.expander("💼 Sales Module Summary", expanded=False):
    st.markdown(st.session_state.sales_summary.get(sel_brand,"No sales summary available."))

# -------------------------
# PDF Upload per brand
# -------------------------
uploaded_file = st.file_uploader("Upload PDF for summary", type=["pdf"])
if uploaded_file and PdfReader:
    reader = PdfReader(uploaded_file)
    pdf_text = "".join([p.extract_text() or "" for p in reader.pages])
    st.session_state.uploaded_pdf_text = pdf_text
    st.session_state.pdf_summary[sel_brand] = model_summarize(pdf_text, bullets=6)
    st.success("PDF summarized successfully!")
if st.session_state.pdf_summary.get(sel_brand):
    with st.expander("📄 Uploaded PDF Summary", expanded=False):
        st.markdown(st.session_state.pdf_summary[sel_brand])

# -------------------------
# Build corpus per brand
# -------------------------
corpus_folders = [bconf["references_path"], bconf["sales_path"]]
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
# AI response generation
# -------------------------
def add_ai_response(prompt, follow_up=False):
    snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=6)
    out_lines = [f"*Thanks — let's tackle this together.*\n"] if not follow_up else ["*Thanks for the feedback — refining response.*\n"]
    out_lines.append("**Response based on brand-specific references and sales call flow:**")
    for step in bconf.get("call_flow", []):
        out_lines.append(f"**{step}:** - Follow the module step; Example phrasing based on PDF and sales kit.")
    out_lines.append("*Reference: internal summaries only.*")

    ai_text = "\n".join(out_lines)
    audio_b64 = generate_audio_base64(ai_text)
    st.session_state.chat_history.append({"role":"assistant","content":ai_text, "audio_b64":audio_b64})

# -------------------------
# Chat container + input + prompt suggestions bubble
# -------------------------
chat_container = st.container()
with chat_container:
    for idx,entry in enumerate(st.session_state.chat_history):
        if entry.get("role")=="user":
            st.markdown(f'<div style="background:#0078D7;color:white;padding:10px;border-radius:12px;margin:8px 0;max-width:78%;margin-left:auto;">{escape(entry["content"])}</div>',unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#eef9ff;color:#000;padding:10px;border-radius:12px;margin:8px 0;max-width:78%;">{escape(entry["content"]).replace("\\n","<br>")}</div>',unsafe_allow_html=True)
            audio_b64 = entry.get("audio_b64","")
            if audio_b64:
                st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")
            # Feedback buttons
            fb_cols = st.columns(3)
            entry_key = f"fb_{idx}"
            if entry_key not in st.session_state.feedback:
                if fb_cols[0].button("👍 Like", key=f"like_{idx}"):
                    st.session_state.feedback[entry_key]="like"
                if fb_cols[1].button("👎 Dislike", key=f"dislike_{idx}"):
                    st.session_state.feedback[entry_key]="dislike"
                    add_ai_response(st.session_state.chat_history[idx]["content"], follow_up=True)
                if fb_cols[2].button("🔄 Need More", key=f"needmore_{idx}"):
                    st.session_state.feedback[entry_key]="need_more"
                    add_ai_response(st.session_state.chat_history[idx]["content"], follow_up=True)

# Prompt suggestions bubble (collapsible)
with st.expander("💡 Prompt Suggestions (click to resize)", expanded=False):
    suggestions = make_suggestions(sel_brand, persona, barrier, segment, specialty, objective)
    for s in suggestions:
        if st.button(s, key=f"sugg_{s}"):
            st.session_state.main_input = s

# Chat input
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_area("Enter your message:", value=st.session_state.main_input, height=60)
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role":"user","content":user_input})
        add_ai_response(user_input.strip())
        st.session_state.main_input = ""

# -------------------------
# Footer
# -------------------------
st.markdown("""
<div style="margin-top:20px;text-align:center;color:gray;font-size:12px;">
© 2025 GSK AI Sales Call Assistant | All rights reserved.
</div>
""", unsafe_allow_html=True)
