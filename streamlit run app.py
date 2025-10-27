# app.py - Full AI Sales Call Assistant with GROQ placeholder
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
    "medical_summary": {},  # dict per brand
    "sales_summary": {},    # dict per brand
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
# GROQ API placeholder
# -------------------------
GROQ_API_KEY = "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"
client = None
# You can initialize Groq client here if you want to enable AI summarization

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

def simple_summary(text, bullets=6):
    if not text: return ""
    sents = re.split(r'(?<=[\.!\?])\s+',text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- "+s for s in selected])

def model_summarize(text, bullets=6):
    # Placeholder summarization; replace with GROQ call if desired
    return simple_summary(text, bullets)

def generate_audio_base64(text):
    if not text: return ""
    tts_text = text.replace("\n"," ")
    if gTTS:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            gTTS(text=tts_text, lang="en", slow=False).save(tmp.name)
            with open(tmp.name,"rb") as fh:
                return base64.b64encode(fh.read()).decode()
        except:
            return ""
    return ""

# -------------------------
# Sidebar: select brand & options
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

# -------------------------
# Title section
# -------------------------
st.markdown(f"<h2>💡 AI Sales Call Assistant — {bconf['display']}</h2>", unsafe_allow_html=True)

# -------------------------
# Load brand-specific summaries
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

brand = st.session_state.selected_brand
if brand not in st.session_state.medical_summary and combined_refs.strip():
    st.session_state.medical_summary[brand] = model_summarize(combined_refs, bullets=6)
if brand not in st.session_state.sales_summary and combined_sales.strip():
    st.session_state.sales_summary[brand] = model_summarize(combined_sales, bullets=6)

# -------------------------
# Display summaries
# -------------------------
with st.expander("📚 Medical References Summary", expanded=False):
    st.markdown(st.session_state.medical_summary.get(brand,"No summary available."))
with st.expander("💼 Sales Module Summary", expanded=False):
    st.markdown(st.session_state.sales_summary.get(brand,"No summary available."))

# -------------------------
# PDF Upload
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
# Chat & prompt suggestions container
# -------------------------
chat_container = st.container()

# Example suggestions per brand/persona
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
# Add AI response
# -------------------------
def add_ai_response(prompt):
    out_lines = []
    out_lines.append(f"*Thanks — I hear you. Let's tackle this together.*\n")
    out_lines.append("**🟢 Example Action Plan:**")
    out_lines.append(f"- Address main concerns for {persona} in {segment}.")
    out_lines.append(f"- Key talking points from {brand_data[brand]['display']} sales module.")
    ai_text = "\n".join(out_lines)
    audio_b64 = generate_audio_base64(ai_text)
    st.session_state.chat_history.append({"role":"assistant","text":ai_text,"audio_b64":audio_b64})

# -------------------------
# Chat input & suggestions at bottom
# -------------------------
def chat_input_area():
    suggs = make_suggestions(sel_brand, persona, barrier, segment, specialty, objective)
    with st.container():
        with st.expander("💬 Prompt Suggestions (click to expand)", expanded=False):
            for s in suggs:
                if st.button(s, key=f"sugg_{s}"):
                    st.session_state.main_input = s
                    add_ai_response(s)
        st.text_area("Your message", key="main_input", height=90)
        if st.button("Send"):
            if st.session_state.main_input.strip():
                add_ai_response(st.session_state.main_input.strip())
                st.session_state.main_input = ""

chat_input_area()

# -------------------------
# Render chat
# -------------------------
with chat_container:
    for entry in st.session_state.chat_history:
        role = entry.get("role","assistant")
        text = entry.get("text","")
        audio_b64 = entry.get("audio_b64","")
        st.markdown(f"**{role.capitalize()}:** {text}")
        if audio_b64:
            st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")
        # Interactive feedback
        cols = st.columns([1,1,1])
        if cols[0].button("👍", key=f"like_{id(entry)}"): st.session_state.feedback[id(entry)]="like"
        if cols[1].button("👎", key=f"dislike_{id(entry)}"): st.session_state.feedback[id(entry)]="dislike"
        if cols[2].button("❓ Need more", key=f"more_{id(entry)}"): st.session_state.feedback[id(entry)]="more"

# -------------------------
# Footer
# -------------------------
st.markdown("---")
st.markdown("© 2025 AI Sales Call Assistant | Confidential Internal Use Only")

