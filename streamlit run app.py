# app_full_dynamic.py - AI Sales Call Assistant fully functional

import streamlit as st
import os, re, io, base64, random
from html import escape
from datetime import datetime

# -------------------------
# Optional Imports
# -------------------------
try:
    from PyPDF2 import PdfReader
except:
    PdfReader = None
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except:
    ELEVENLABS_AVAILABLE = False
try:
    from gtts import gTTS
except:
    gTTS = None

# -------------------------
# GROQ API placeholder
# -------------------------
GROQ_API_KEY = "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"

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# Resources & Avatars
# -------------------------
GSK_LOGO_RAW = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/AURA1.png"
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"

# -------------------------
# Session defaults
# -------------------------
def _init_session():
    defaults = {
        "chat_history": [], "main_input": "", "selected_brand": "shingrix",
        "temperature":0.95, "search_mode":"deep", "medical_summary":"", "sales_summary":"",
        "uploaded_pdf_text":"", "pdf_summary":"", "feedback":{}, "dislike_state":None,
        "language":"English", "hcp_persona":"Friendly", "hcp_personality":"Friendly",
        "tone":"executive", "chunks":[], "chunk_meta":[]
    }
    for k,v in defaults.items():
        st.session_state.setdefault(k,v)
_init_session()

# -------------------------
# CSS Styling
# -------------------------
st.markdown("""
<style>
.title-box{ background: rgba(255,255,255,0.85); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; position:relative; margin-bottom:12px; }
.title-box img.left-logo{ position:absolute; left:12px; height:48px; }
.title-box img.right-logo{ position:absolute; right:12px; height:48px; }
.ai-message { display:flex; align-items:flex-start; gap:12px; margin:10px 0; }
.ai-avatar { width:52px; height:52px; border-radius:50%; box-shadow:0 0 12px rgba(0,255,255,0.6); flex-shrink:0; animation:holoPulse 2.5s infinite ease-in-out; }
@keyframes holoPulse { 0% { box-shadow:0 0 8px rgba(0,255,255,0.35);} 50% { box-shadow:0 0 22px rgba(0,255,255,0.9);} 100% { box-shadow:0 0 8px rgba(0,255,255,0.35);} }
.ai-bubble { background: rgba(255,255,255,0.06); border:1px solid rgba(0,255,255,0.18); color:#E6FBFF; padding:14px; border-radius:14px; max-width:90%; white-space:pre-wrap; }
.user-bubble{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }
.step-title{ font-weight:700; margin-top:8px; color:#BFF; }
.story{ font-style:italic; margin:6px 0 10px 0; color:#DFF; }
.objection{ background:rgba(255,248,240,0.06); padding:8px; border-radius:8px; margin:6px 0; border:1px solid rgba(255,224,198,0.08); color:#FFD; }
.fixed-disclaimer{ font-size:12px; color:#aac; margin-top:16px; opacity:0.9; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Brand Data
# -------------------------
brand_data = {
    "shingrix": {
        "display": "Shingrix (Herpes Zoster Vaccine)",
        "segments": ["GP","Internal Medicine","Geriatrics"],
        "barriers":["Efficacy doubts","Safety concerns","Patient adherence"],
        "specialties":["General Practitioner","Geriatrician","Infectious Disease"],
        "personas":["Friendly","Skeptical","Evidence-led"],
        "references_path":"./references/shingrix",
        "sales_path":"./sales/shingrix",
        "call_flow":["Prepare","Engage","Create Opportunities","Influence","Close"],
        "objections":{"efficacy":"Share trial results showing >90% efficacy.",
                      "safety":"Highlight safety data; minor injection site reactions only.",
                      "cost":"Discuss reimbursement options and patient assistance."}
    },
    "trelegy": {
        "display":"Trelegy Ellipta (COPD / Asthma)",
        "segments":["Pulmonologist","GP","Respiratory Specialist"],
        "barriers":["Patient adherence","Inhaler technique","Price sensitivity"],
        "specialties":["Pulmonologist","General Practitioner"],
        "personas":["Time-pressured","Evidence-led","Friendly"],
        "references_path":"./references/trelegy",
        "sales_path":"./sales/trelegy",
        "call_flow":["Prepare","Engage","Create Opportunities","Influence","Close"],
        "objections":{"efficacy":"Present comparative studies with other triple therapy inhalers.",
                      "safety":"Show low systemic corticosteroid exposure; discuss monitoring plan.",
                      "adherence":"Offer inhaler training and patient reminder support."}
    },
    "jemperli": {
        "display":"Jemperli (DMMR/MSI-H Cancer Immunotherapy)",
        "segments":["Oncologist","Hospital Specialist"],
        "barriers":["Immune-related side effects","Eligibility criteria","Cost / Reimbursement"],
        "specialties":["Oncologist","Hospital Specialist"],
        "personas":["Early-adopter","Skeptical","Evidence-led"],
        "references_path":"./references/jemperli",
        "sales_path":"./sales/jemperli",
        "call_flow":["Prepare","Engage","Create Opportunities","Influence","Close"],
        "objections":{"efficacy":"Provide pivotal trial data and progression-free survival outcomes.",
                      "safety":"Explain immune-mediated side effect monitoring & mitigation.",
                      "eligibility":"Highlight patient selection criteria and companion diagnostics."}
    }
}

EXTRA_PERSONAS = ["Evidence-led","Time-pressured","Skeptical","Early-adopter"]
def get_persona_options(brand_key):
    base = brand_data.get(brand_key, {}).get("personas", [])
    return base + [p for p in EXTRA_PERSONAS if p not in base]

# -------------------------
# File reading / corpus
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

def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas = [], []
    for folder in folders:
        if not folder or not os.path.exists(folder): continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf",".txt"))]
        for fname in files:
            p = os.path.join(folder,fname)
            text = read_file_text(p)
            if not text: continue
            sents = re.split(r'(?<=[\.\?\!])\s+', text)
            for i in range(0,max(1,len(sents)),chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk: chunks.append(chunk); metas.append({"filename":fname,"folder":folder,"start":i})
    return chunks, metas

def simple_summary(text, bullets=6):
    if not text: return ""
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    return "\n".join(["- "+s for s in sents[:bullets]])

def model_summarize(text, bullets=6):
    return simple_summary(text, bullets)

# -------------------------
# AI rendering
# -------------------------
HOLO_AVATAR = AI_AVATAR
def render_ai_message(message_html):
    st.markdown(f'<div class="ai-message"><img src="{HOLO_AVATAR}" class="ai-avatar"/><div class="ai-bubble">{message_html}</div></div>', unsafe_allow_html=True)
def render_user_message(msg):
    st.markdown(f'<div class="user-bubble">{escape(msg)}</div>', unsafe_allow_html=True)

# -------------------------
# Generate step story with examples
# -------------------------
def make_story_for_step(step, brand_key, persona_name, tone, snippet=""):
    prof = {"priority":"Key points","style":"Friendly","quick_win":"Quick tip"}
    examples = {
        "Prepare":["Review patient history","Check guidelines","Update stock status"],
        "Engage":["Greet HCP, show interest","Ask about current patients","Share relevant facts"],
        "Create Opportunities":["Ask open questions","Identify unmet needs","Present solutions"],
        "Influence":["Share data highlights","Provide trial evidence","Discuss outcomes"],
        "Close":["Agree on next step","Provide leave-behind","Confirm follow-up"]
    }
    step_examples = examples.get(step, ["Perform relevant actions"])
    example_html = "<br>".join([f"- {e}" for e in step_examples])
    micro_action = f"Quick action for {step}: {random.choice(step_examples)}"
    return f"<div class='step-title'>{escape(step)} ({escape(tone)})</div><div class='story'>{example_html}</div><div>{micro_action}</div>"

# -------------------------
# Generate AI call flow response
# -------------------------
def generate_sales_flow(prompt:str, persona_name:str, tone:str):
    bconf = brand_data.get(st.session_state.selected_brand, {})
    flow = bconf.get("call_flow", ["Prepare","Engage","Create Opportunities","Influence","Close"])
    html_parts = [f"<div><strong>Brand:</strong> {bconf.get('display','')} | Persona: {persona_name} | Tone: {tone}</div>"]
    for step in flow:
        html_parts.append(make_story_for_step(step, st.session_state.selected_brand, persona_name, tone))
    html_parts.append("<div class='step-title'>Objection Handling</div>")
    for obj, reply in bconf.get("objections",{}).items():
        html_parts.append(f"<div class='objection'><strong>{obj.title()}:</strong> {reply}</div>")
    return "\n".join(html_parts)

def add_ai_response(prompt_text):
    persona_name = st.session_state.hcp_persona
    tone = st.session_state.tone
    html_response = generate_sales_flow(prompt_text, persona_name, tone)
    st.session_state.chat_history.append({"role":"assistant","content":html_response,"citation":""})

# -------------------------
# Sidebar / Brand Selection UI
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]

    # Summaries
    refs_folder = bconf.get("references_path","")
    sales_folder = bconf.get("sales_path","")
    combined_refs = ""
    combined_sales = ""
    if os.path.exists(refs_folder):
        for f in sorted(os.listdir(refs_folder)):
            if f.lower().endswith((".pdf",".txt")): combined_refs += read_file_text(os.path.join(refs_folder,f))+"\n"
    if os.path.exists(sales_folder):
        for f in sorted(os.listdir(sales_folder)):
            if f.lower().endswith((".pdf",".txt")): combined_sales += read_file_text(os.path.join(sales_folder,f))+"\n"
    if combined_refs: st.session_state.medical_summary = model_summarize(combined_refs,6)
    if combined_sales: st.session_state.sales_summary = model_summarize(combined_sales,6)

# -------------------------
# Display Summaries
# -------------------------
with st.expander("📚 Medical References Summary"):
    st.markdown(st.session_state.medical_summary or "No medical summary available.")
with st.expander("💼 Sales Module Summary"):
    st.markdown(st.session_state.sales_summary or "No sales summary available.")

# -------------------------
# Chat Interface
# -------------------------
st.markdown(f"""
<div class="title-box">
<img src="{GSK_LOGO_RAW}" class="left-logo">
<h2>💡 AI Sales Call Assistant — {bconf.get('display','')}</h2>
<img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

main_input = st.text_area("Enter your prompt:", st.session_state.main_input, height=100)
if st.button("Send"):
    if main_input.strip():
        st.session_state.chat_history.append({"role":"user","content":main_input})
        add_ai_response(main_input)
        st.session_state.main_input = ""

for msg in st.session_state.chat_history:
    if msg["role"]=="user": render_user_message(msg["content"])
    else: render_ai_message(msg["content"])

st.markdown('<div class="fixed-disclaimer">💡 Internal sales support only. Verify medical info.</div>', unsafe_allow_html=True)
