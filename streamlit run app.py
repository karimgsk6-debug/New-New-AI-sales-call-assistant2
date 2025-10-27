# app.py - Full AI Sales Call Assistant with TRELEGY, feedback, voice, prompts
import streamlit as st
import os, re, tempfile, base64, io
from html import escape
from datetime import datetime

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
# Backend API placeholder
# -------------------------
GROQ_API_KEY = "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"  # placeholder
client = None  # integrate GROQ client here later

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

def generate_audio_base64(text):
    if not text: return ""
    tts_text = text.replace("\n", " ... ")
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=tts_text, lang="en", slow=False).save(tmp.name)
        with open(tmp.name,"rb") as fh:
            return base64.b64encode(fh.read()).decode()
    except Exception:
        return ""

def add_ai_response(prompt, follow_up=False, context_previous=None):
    # simplified enriched response respecting brand sales flow
    brand_key = st.session_state.selected_brand
    bconf = brand_data[brand_key]
    out_lines = [f"*Response for {bconf['display']} ({brand_key.upper()})*"]
    out_lines.append(f"Prompt: {prompt}")
    out_lines.append("\n**Sales Call Flow Guidance:**")
    for step in bconf.get("call_flow", []):
        out_lines.append(f"- {step}: Example phrasing based on uploaded sales module and references.")
    ai_text = "\n".join(out_lines)
    audio_b64 = generate_audio_base64(ai_text)
    st.session_state.chat_history.append({"role":"assistant","text":ai_text,"audio_b64":audio_b64})

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

# -------------------------
# Title
# -------------------------
st.markdown(f"""
<div style="background:#fff;padding:12px;border-radius:10px;margin-bottom:12px;text-align:center;">
<h2>💡 AI Sales Call Assistant — {brand_data[sel_brand]['display']}</h2>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Prompt suggestions (collapsible, above input)
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
# Chat rendering + feedback
# -------------------------
def render_chat():
    chat_box_height = 350
    st.markdown(f'<div style="max-height:{chat_box_height}px; overflow-y:auto;">', unsafe_allow_html=True)
    for idx, entry in enumerate(st.session_state.chat_history):
        if entry["role"]=="user":
            st.markdown(f'<div style="background:#0078D7;color:white;padding:8px;margin:4px;border-radius:8px;">{escape(entry["text"])}</div>',unsafe_allow_html=True)
        else:
            st.markdown(f'<div style="background:#eef9ff;color:#000;padding:8px;margin:4px;border-radius:8px;">{escape(entry["text"]).replace("\\n","<br>")}</div>',unsafe_allow_html=True)
            if entry.get("audio_b64"):
                st.audio(io.BytesIO(base64.b64decode(entry["audio_b64"])), format="audio/mp3")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("👍 Like", key=f"like_{idx}"):
                    st.session_state.feedback[idx] = "like"
            with col2:
                if st.button("👎 Dislike", key=f"dislike_{idx}"):
                    st.session_state.feedback[idx] = "dislike"
            with col3:
                if st.button("ℹ️ Need More", key=f"needmore_{idx}"):
                    st.session_state.feedback[idx] = "need_more"
                    add_ai_response(entry["text"])
                    st.experimental_rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# Bottom-fixed input + prompt suggestions
# -------------------------
def chat_input_area():
    with st.container():
        with st.expander("💡 Prompt Suggestions (Click to Expand)", expanded=True):
            suggs = make_suggestions(sel_brand, persona, barrier, segment, specialty, objective)
            sugg_cols = st.columns(3)
            for i,s in enumerate(suggs):
                col = sugg_cols[i%3]
                if col.button(s, key=f"sugg_{i}"):
                    st.session_state.main_input = s

        user_input = st.text_area("Ask something:", st.session_state.main_input, height=80)
        if st.button("Send"):
            if user_input.strip():
                st.session_state.chat_history.append({"role":"user","text":user_input.strip()})
                add_ai_response(user_input.strip())
                st.session_state.main_input = ""

# -------------------------
# Main layout
# -------------------------
render_chat()
chat_input_area()

# -------------------------
# Footer
# -------------------------
st.markdown("""
<div style="position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997;">
💡 This tool is for internal sales support only. Verify medical info from official sources.
</div>
""", unsafe_allow_html=True)
