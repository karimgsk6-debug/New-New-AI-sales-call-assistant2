# app_full_ready.py - AI Sales Call Assistant with GROQ API

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

# GROQ API placeholder
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
# AI rendering
# -------------------------
HOLO_AVATAR = AI_AVATAR
def render_ai_message(message_html):
    st.markdown(f'<div class="ai-message"><img src="{HOLO_AVATAR}" class="ai-avatar"/><div class="ai-bubble">{message_html}</div></div>', unsafe_allow_html=True)
def render_user_message(msg):
    st.markdown(f'<div class="user-bubble">{escape(msg)}</div>', unsafe_allow_html=True)

# -------------------------
# Footer Disclaimer
# -------------------------
st.markdown('<div class="fixed-disclaimer">💡 This tool is for internal sales support purposes only. Verify all medical info.</div>', unsafe_allow_html=True)

# -------------------------
# Sidebar & Brand Selection
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]
    segment = st.selectbox("Segment", bconf["segments"])
    persona_options = get_persona_options(sel_brand)
    persona_sel = st.selectbox("HCP Persona", persona_options, index=0)
    st.session_state.hcp_persona = persona_sel
    hcp_personality = st.selectbox("HCP Personality", ["Assertive","Masked","Friendly","Details-oriented","Skeptic"])
    st.session_state.hcp_personality = hcp_personality
    barrier = st.multiselect("Doctor Barrier", bconf["barriers"])
    specialty = st.selectbox("Specialty", bconf["specialties"])
    objective = st.selectbox("Objective", ["Awareness","Adoption","Retention"])
    st.session_state.temperature = st.slider("Temperature",0.0,1.0,st.session_state.temperature,0.05)
    st.session_state.search_mode = st.selectbox("Search mode",["deep","shallow"])
    st.session_state.language = st.radio("Language",["English","Arabic"])
    st.session_state.tone = st.selectbox("Tone",["executive","coaching","persuasive","clinical"], index=0)
    if st.button("🗑️ Clear Chat"): st.session_state.chat_history = []; st.experimental_rerun()

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
# (Your dynamic AI functions like make_story_for_step and add_ai_response go here)
# They will use brand_data, persona selection, GROQ API key, etc.
# -------------------------

# -------------------------
# End of merged ready-to-run app
# -------------------------
