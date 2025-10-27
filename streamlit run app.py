# app.py - Full AI Sales Call Assistant with editable summaries
import streamlit as st
import os, re, tempfile, base64
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
try: from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import linear_kernel; SKLEARN_AVAILABLE=True
except: SKLEARN_AVAILABLE=False
try: import elevenlabs; ELEVENLABS_AVAILABLE=True
except: ELEVENLABS_AVAILABLE=False
try: import pyttsx3; PYTTSX3_AVAILABLE=True
except: PYTTSX3_AVAILABLE=False

# -------------------------
# Page & repo config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")
REPO_USER="karimgsk6-debug"
REPO_NAME="New-New-AI-sales-call-assistant2"
COMMIT="845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_BLOB_BASE=f"https://github.com/{REPO_USER}/{REPO_NAME}/blob/{COMMIT}/.devcontainer"
REPO_RAW_BASE=f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
BACKGROUND_URL=REPO_RAW_BASE+"/.devcontainer/background1.png"
GSK_LOGO_RAW=f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW=f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# -------------------------
# Session defaults
# -------------------------
defaults={"chat_history":[],"main_input":"","selected_brand":"shingrix","temperature":0.62,
          "search_mode":"deep","medical_summary":"","sales_summary":"","uploaded_pdf_text":"",
          "pdf_summary":"","followup_state":None,"language":"English"}
for k,v in defaults.items(): st.session_state.setdefault(k,v)

# -------------------------
# CSS & background
# -------------------------
st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}}
.title-box {{
  background: rgba(255,255,255,0.95);
  padding: 12px; border-radius:10px;
  margin-bottom:12px; position:relative; display:flex;
  align-items:center; justify-content:center;
}}
.title-box img.left-logo {{position:absolute; left:12px; height:64px;}}
.title-box img.right-logo {{position:absolute; right:12px; height:64px;}}
.chat-container {{ max-height:62vh; overflow-y:auto; padding:12px; background: rgba(255,255,255,0.95); border-radius:8px; margin-bottom:140px; }}
.chat-bubble-user {{ background:#0078D7; color:white; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto; }}
.chat-bubble-ai {{ background:#eef9ff; color:#000; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }}
.suggestion-pill {{ background:#fff; border:1px solid #ddd; padding:8px 12px; border-radius:20px; margin:6px; cursor:pointer; display:inline-block; }}
.suggestion-pill:hover {{ background:#f0f8ff; }}
.citation-box {{ background:#fbfbff; border-left:4px solid #0078D7; padding:8px; margin-top:8px; border-radius:6px; font-size:13px; white-space:pre-wrap; }}
.input-area {{ position: fixed; left:20px; right:20px; bottom:18px; z-index:9999; display:flex; gap:8px; align-items:flex-end; }}
.input-area textarea {{ width:100%; min-height:72px; max-height:250px; padding:10px; border-radius:8px; border:1px solid #ccc; resize:vertical; }}
.send-button {{ height:44px; padding:0 14px; border-radius:8px; border:none; background:#FF6F00; color:white; cursor:pointer; font-weight:600; }}
.fixed-disclaimer {{ position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }}
.floating-panel {{
  position: fixed; right:20px; width:400px; max-width:90%; z-index:9998; bottom:100px;
  background:rgba(255,255,255,0.95); border-radius:10px; padding:8px; box-shadow:0 4px 8px rgba(0,0,0,0.1);
}}
.panel-header {{ font-weight:600; cursor:pointer; padding:4px; border-bottom:1px solid #ccc; }}
.panel-content {{ display:none; padding-top:4px; }}
</style>
<script>
function togglePanel(panelId){{
  const c=document.getElementById(panelId);
  c.style.display=(c.style.display==='block')?'none':'block';
}}
document.addEventListener("DOMContentLoaded", function(){{
  document.getElementById('medical-panel-content').style.display='none';
  document.getElementById('sales-panel-content').style.display='none';
}});
</script>
""", unsafe_allow_html=True)

# -------------------------
# Initialize GROQ client
# -------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY","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")
client=None
if Groq and GROQ_API_KEY:
    try: client=Groq(api_key=GROQ_API_KEY)
    except: client=None

# -------------------------
# Brand data
# -------------------------
brand_data = {
    "shingrix":{"display":"Shingrix","segments":["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
    "personas":["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
    "barriers":["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
    "specialties":["GP","Dermatologist","Geriatrician"],
    "references_path":".devcontainer/references/shingrix/","sales_path":".devcontainer/SalesModule/shingrix/",
    "call_flow":["Pre-call planning","Prepare","Engage","Create Opportunities","Influence","Impact GSO","Post-call analysis"]},
    "jemperli":{"display":"Jemperli","segments":["Target Identification","Trial Adoption","Routine Use","Advocacy"],
    "personas":["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
    "barriers":["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
    "specialties":["Oncologist","Medical Oncologist"],
    "references_path":".devcontainer/references/jemperli/","sales_path":".devcontainer/SalesModule/jemperli/",
    "call_flow":["COCO","Anchor","Engage","Close"]},
    "trelegy":{"display":"Trelegy","segments":["Awareness","Diagnosis","Adoption","Adherence"],
    "personas":["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
    "barriers":["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
    "specialties":["GP","Pulmonologist","Respiratory Specialist"],
    "references_path":".devcontainer/references/trelegy/","sales_path":".devcontainer/SalesModule/trelegy/",
    "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"]}
}

# -------------------------
# Sidebar filters
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    sel_brand = st.selectbox("Brand", list(brand_data.keys()), index=list(brand_data.keys()).index(st.session_state.selected_brand))
    st.session_state.selected_brand=sel_brand
    bconf=brand_data[sel_brand]
    segment = st.selectbox("Segment", bconf["segments"], key="sidebar_segment")
    persona = st.selectbox("HCP Persona", bconf["personas"], key="sidebar_persona")
    barrier = st.multiselect("Doctor Barrier", bconf["barriers"], key="sidebar_barrier")
    specialty = st.selectbox("Specialty", bconf["specialties"], key="sidebar_specialty")
    objective = st.selectbox("Objective", ["Awareness","Adoption","Retention"], key="sidebar_objective")
    st.slider("Temperature",0.0,1.0,value=st.session_state.temperature,step=0.05,key="temperature")
    st.selectbox("Search mode", ["deep","shallow"], index=0 if st.session_state.search_mode=="deep" else 1,key="search_mode")
    st.radio("Language", ["English","Arabic"], index=0 if st.session_state.language=="English" else 1,key="language")
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

# -------------------------
# Process PDF
# -------------------------
if uploaded_file and PdfReader:
    pdf_reader = PdfReader(uploaded_file)
    text=""
    for page in pdf_reader.pages: text+=page.extract_text() or ""
    st.session_state.uploaded_pdf_text=text
    # Optional: summarize first 500 words
    st.session_state.pdf_summary = " ".join(text.split()[:500])

# -------------------------
# Title Box
# -------------------------
st.markdown(f"""
<div class="title-box">
<img src="{GSK_LOGO_RAW}" class="left-logo">
AI Sales Call Assistant
<img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# -------------------------
# Floating editable panels
# -------------------------
with st.container():
    st.markdown("""
    <div class="floating-panel" id="medical-panel">
      <div class="panel-header" onclick="togglePanel('medical-panel-content')">📚 Medical Summary</div>
      <div class="panel-content" id="medical-panel-content">
    """, unsafe_allow_html=True)
    st.session_state.medical_summary = st.text_area(
        "Medical Summary", value=st.session_state.medical_summary,
        key="medical_panel_text", height=120
    )
    st.markdown("</div></div>", unsafe_allow_html=True)

    st.markdown("""
    <div class="floating-panel" style="bottom:220px;" id="sales-panel">
      <div class="panel-header" onclick="togglePanel('sales-panel-content')">💼 Sales Summary</div>
      <div class="panel-content" id="sales-panel-content">
    """, unsafe_allow_html=True)
    st.session_state.sales_summary = st.text_area(
        "Sales Summary", value=st.session_state.sales_summary,
        key="sales_panel_text", height=120
    )
    st.markdown("</div></div>", unsafe_allow_html=True)

# -------------------------
# Chat container
# -------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for c in st.session_state.chat_history:
    if c["role"]=="user": st.markdown(f'<div class="chat-bubble-user">{escape(c["content"])}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">{escape(c["content"])}</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Prompt suggestions (click to input)
# -------------------------
suggestions = ["Generate call flow for this HCP", "Generate objections handling", "Summarize PDF for HCP", "Prepare patient discussion"]
cols = st.columns(len(suggestions))
for i, s in enumerate(suggestions):
    if cols[i].button(s):
        st.session_state.main_input=s

# -------------------------
# Bottom input area
# -------------------------
st.markdown("""
<div class="input-area">
<form id="chat-form">
<textarea id="chat-input" placeholder="Type your message...">{}</textarea>
<button class="send-button" onclick="document.getElementById('chat-form').submit(); return false;">Send</button>
</form>
</div>
""".format(escape(st.session_state.main_input)), unsafe_allow_html=True)

user_input = st.text_area("Your Message", value=st.session_state.main_input, key="main_input_area", height=60)
if st.button("Send"):
    msg={"role":"user","content":user_input}
    st.session_state.chat_history.append(msg)
    # Here integrate AI generation, e.g., call GROQ API or OpenAI
    ai_response=f"AI generated response for: {user_input}"
    st.session_state.chat_history.append({"role":"ai","content":ai_response})
    st.session_state.main_input=""

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown('<div class="fixed-disclaimer">💡 All AI-generated content is advisory. Verify before sharing with HCPs.</div>', unsafe_allow_html=True)
