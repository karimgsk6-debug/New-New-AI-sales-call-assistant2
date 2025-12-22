# ============================================================
# app.py — AI Medical Rep Sales Call Assistant (LIVE ROLE-PLAY)
# Brand-governed | SalesModule-driven | Hologram UI
# ============================================================

import streamlit as st
import os, base64, tempfile
from datetime import datetime

# ============================================================
# 🔐 GROQ API KEY
# ============================================================
GROQ_API_KEY = "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"

# ============================================================
# SAFE IMPORTS
# ============================================================
try:
    from groq import Groq
except:
    Groq = None

try:
    from gtts import gTTS
except:
    gTTS = None

# ============================================================
# REPO ASSETS
# ============================================================
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"

GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"
AI_AVATAR = ".devcontainer/Visuals/futuristic_hologram_ai.gif"
HCP_AVATAR = ".devcontainer/Visuals/HCP.gif"
REP_AVATAR = ".devcontainer/Visuals/sales rep.gif"

# ============================================================
# PATH CONFIG
# ============================================================
BASE_PATH = ".devcontainer"
SALES_MODULE_PATH = os.path.join(BASE_PATH, "SalesModule")
REFERENCE_PATH = os.path.join(BASE_PATH, "references")

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# ============================================================
# SESSION STATE
# ============================================================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "last_hcp_options" not in st.session_state:
    st.session_state.last_hcp_options = []
if "main_input" not in st.session_state:
    st.session_state.main_input = ""
if "selected_brand" not in st.session_state:
    st.session_state.selected_brand = "shingrix"
if "hcp_persona" not in st.session_state:
    st.session_state.hcp_persona = ""
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.3

# ============================================================
# BRAND DATA
# ============================================================
BRANDS = {
    "shingrix": {
        "display": "Shingrix",
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "specialties": ["GP", "Dermatology", "Cardiology", "Immunology", "Internal Medicine"],
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "references_path": os.path.join(REFERENCE_PATH, "shingrix"),
        "sales_path": os.path.join(SALES_MODULE_PATH, "shingrix"),
        "call_flow": ["Prepare", "Engage", "Create Opportunities", "Influence", "Impact GSO", "Analyze"],
        "objections": {
            "efficacy": "Focus on durable protection and age-agnostic efficacy evidence.",
            "safety": "Acknowledge common AEs, then contrast with risk of complications from shingles.",
            "cost": "Frame cost as prevention of downstream complications and reduce clinic workload."
        }
    },
    "jemperli": {
        "display": "Jemperli",
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "specialties": ["Oncologist", "Medical Oncologist"],
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "references_path": os.path.join(REFERENCE_PATH, "jemperli"),
        "sales_path": os.path.join(SALES_MODULE_PATH, "jemperli"),
        "call_flow": ["COCO", "Anchor", "Engage", "Close"],
        "objections": {
            "efficacy": "Discuss durable responses in dMMR/MSI-H and appropriate patient selection.",
            "safety": "Share safety profile and monitoring guidance to reduce perceived risk.",
            "access": "Offer starter kits or initiation support and reimbursement pathways."
        }
    },
    "trelegy": {
        "display": "Trelegy",
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "specialties": ["GP", "Pulmonologist", "Internal Medicine", "Respiratory Specialist"],
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "references_path": os.path.join(REFERENCE_PATH, "trelegy"),
        "sales_path": os.path.join(SALES_MODULE_PATH, "trelegy"),
        "call_flow": ["Prepare", "Engage", "Demonstrate", "Address Access", "Close"],
        "objections": {
            "device": "Offer quick practical coaching and demo materials.",
            "coverage": "Explain access options and patient support programs.",
            "effectiveness": "Share comparative outcomes framed for real-world practice."
        }
    }
}

# ============================================================
# CSS STYLING
# ============================================================
st.markdown(
"""
<style>
.title-box{ background: rgba(255,255,255,0.85); padding:8px; border-radius:8px; display:flex; align-items:center; justify-content:center; margin-bottom:12px; }
.title-box img.left-logo{ height:36px; margin-right:8px; }
.title-box img.right-logo{ height:36px; margin-left:8px; }
.ai-message{display:flex;align-items:flex-start;gap:12px;margin:6px 0;}
.ai-avatar{width:48px;height:48px;border-radius:50%;flex-shrink:0;}
.ai-bubble{background: rgba(255,255,255,0.06); border:1px solid rgba(0,255,255,0.18); padding:12px; border-radius:12px; max-width:90%; white-space:pre-wrap;}
.user-bubble{background: rgba(0,0,0,0.06); padding:10px 14px; border-radius:12px; margin:6px 0; max-width:80%;}
.collapsible {background-color: #222; color: #E6FBFF; cursor: pointer; padding:6px; width:100%; border:none; text-align:left; outline:none; font-size:14px;}
.content {padding: 0 12px; display:none; overflow:hidden; background-color:#333; color:#E6FBFF;}
.fixed-disclaimer{font-size:12px;color:#aac;margin-top:16px;opacity:0.9;}
</style>
""", unsafe_allow_html=True
)

# ============================================================
# TITLE BOX
# ============================================================
bconf = BRANDS[st.session_state.selected_brand]
st.markdown(f"""
<div class="title-box">
    <img src="{GSK_LOGO_RAW}" class="left-logo">
    <h2>💡 AI Sales Call Assistant — {bconf['display']}</h2>
    <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.header("Call Configuration")
    brand = st.selectbox("Brand", list(BRANDS.keys()))
    st.session_state.selected_brand = brand
    bconf = BRANDS[brand]

    st.session_state.hcp_persona = st.selectbox("HCP Persona", bconf["personas"])
    st.selectbox("Specialty", bconf["specialties"])
    st.selectbox("Segment", bconf["segments"])
    st.session_state.temperature = st.slider("Creativity", 0.0, 1.0, 0.3)

# ============================================================
# GROQ CLIENT
# ============================================================
def get_client():
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("Add_"):
        st.warning("⚠️ GROQ API is not set")
        return None
    if Groq is None:
        st.warning("⚠️ groq package not installed")
        return None
    return Groq(api_key=GROQ_API_KEY)

# ============================================================
# FILE HELPERS
# ============================================================
def read_file(path):
    if path.endswith(".txt"):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return ""

def load_folder(folder):
    if not os.path.exists(folder):
        return ""
    texts = []
    for f in os.listdir(folder):
        if f.endswith(".txt"):
            texts.append(read_file(os.path.join(folder, f)))
    return "\n".join(texts)

# ============================================================
# TEXT → VOICE
# ============================================================
def text_to_voice(text):
    if not gTTS:
        return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    gTTS(text=text[:2000], lang="en").save(tmp.name)
    return open(tmp.name, "rb").read()

# ============================================================
# GENERATE AI RESPONSE
# ============================================================
def generate_sales_call(rep_query):
    brand_conf = BRANDS[st.session_state.selected_brand]
    sales_module = load_folder(brand_conf["sales_path"])
    references = load_folder(brand_conf["references_path"])

    client = get_client()
    if not client:
        return "⚠️ GROQ API unavailable"

    system_prompt = f"""
You are a pharmaceutical sales excellence coach.
Use ONLY the provided Sales Module and References.
Brand: {brand_conf['display']}
HCP Persona: {st.session_state.hcp_persona}
Tone: executive
"""

    user_prompt = f"""
SALES MODULE:
{sales_module}

REFERENCES:
{references}

Scenario / Query from Sales Rep:
{rep_query}

TASK:
Generate a full sales call with HCP messages (simulate) and AI sales assistant replies.
Include examples of what the Sales Rep could say next.
"""
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=st.session_state.temperature,
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"Error generating AI response: {e}"

# ============================================================
# PROMPT SUGGESTIONS COLLAPSIBLE
# ============================================================
st.markdown('<button class="collapsible">💡 Suggested Sales Rep Phrases</button><div class="content" id="prompt_suggestions">', unsafe_allow_html=True)
prompt_phrases = [
    "Generate full sales call",
    "Ask medical question about product",
    "Ask for approved product indication",
    "Respond to common objection",
    "Highlight clinical trial evidence"
]
for phrase in prompt_phrases:
    if st.button(phrase, key=f"prompt_{phrase}"):
        st.session_state.main_input = phrase
st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# CHAT INPUT
# ============================================================
rep_input = st.text_input("Sales Rep Query", value=st.session_state.main_input, key="rep_input")
if st.button("SEND"):
    if rep_input.strip():
        ai_resp = generate_sales_call(rep_input)
        st.session_state.chat_history.append({"role": "rep", "text": rep_input})
        st.session_state.chat_history.append({"role": "ai", "text": ai_resp})
        st.session_state.main_input = ""

# ============================================================
# DISPLAY CHAT HISTORY
# ============================================================
for msg in st.session_state.chat_history:
    if msg["role"] == "rep":
        st.markdown(f'<div class="ai-message"><img src="{REP_AVATAR}" class="ai-avatar"><div class="user-bubble">{msg["text"]}</div></div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="ai-message"><img src="{AI_AVATAR}" class="ai-avatar"><div class="ai-bubble">{msg["text"]}</div></div>', unsafe_allow_html=True)
        audio = text_to_voice(msg["text"])
        if audio:
            st.audio(audio, format="audio/mp3")

# ============================================================
# FOOTER DISCLAIMER
# ============================================================
st.markdown('<div class="fixed-disclaimer">Internal use only. Generated content limited to approved materials.</div>', unsafe_allow_html=True)
