# app_final_merged.py - Fully functioning AI Sales Call Assistant
import streamlit as st
import os
import re
import tempfile
import base64
import io
from datetime import datetime
from html import escape

# -------------------------
# Optional imports
# -------------------------
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
# Resources
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
        "chat_history": [],
        "main_input": "",
        "selected_brand": "shingrix",
        "temperature": 0.95,
        "search_mode": "deep",
        "medical_summary": "",
        "sales_summary": "",
        "uploaded_pdf_text": "",
        "pdf_summary": "",
        "feedback": {},
        "dislike_state": None,
        "language": "English",
        "hcp_persona": "Friendly",
        "hcp_personality": "Friendly",
        "tone": "executive",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

_init_session()

# -------------------------
# CSS for UI
# -------------------------
st.markdown("""
<style>
.title-box{ background: rgba(255,255,255,0.85); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; position:relative; margin-bottom:12px; }
.title-box img.left-logo{ position:absolute; left:12px; height:48px; }
.title-box img.right-logo{ position:absolute; right:12px; height:48px; }

.chat-bubble-user{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }
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
.user-bubble{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Dynamic background
# -------------------------
def set_dynamic_background(image_path):
    if not os.path.exists(image_path):
        return
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
    </style>""", unsafe_allow_html=True)

set_dynamic_background(BACKGROUND_PATH)

# -------------------------
# GROQ client
# -------------------------
def load_groq_client():
    api_key = os.getenv("GROQ_API_KEY", "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") or (st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else "")
    if not api_key or Groq is None:
        return None
    try:
        return Groq(api_key=api_key)
    except:
        return None

# -------------------------
# Product / Brand data
# -------------------------
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "specialties": ["GP", "Dermatologist", "Cardiology", "Endocrinology", "Immunology", "Internal Medicine", "Rheumatology"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/",
        "call_flow": ["Prepare", "Engage", "Create Opportunities", "Influence", "Impact GSO", "Analyze"],
        "objections": {
            "efficacy": "Focus on durable protection and age-agnostic efficacy evidence.",
            "safety": "Acknowledge common AEs, then contrast with risk of complications from shingles.",
            "cost": "Frame cost as prevention of downstream complications and reduce clinic workload."
        }
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited eligibility", "Access/reimbursement issues"],
        "specialties": ["Oncologist", "Medical Oncologist"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli/",
        "call_flow": ["COCO", "Anchor", "Engage", "Close"],
        "objections": {
            "efficacy": "Discuss durable responses in dMMR/MSI-H and appropriate patient selection.",
            "safety": "Share safety profile and monitoring guidance to reduce perceived risk.",
            "access": "Offer starter kits or initiation support and reimbursement pathways."
        }
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Side effect concerns", "Cost/coverage"],
        "specialties": ["GP", "Pulmonologist", "Internal Medicine", "Respiratory Specialist"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy/",
        "call_flow": ["Prepare", "Engage", "Demonstrate", "Address Access", "Close"],
        "objections": {
            "device": "Offer quick practical coaching and demo materials.",
            "coverage": "Explain access options and patient support programs.",
            "effectiveness": "Share comparative outcomes framed for real-world practice."
        }
    }
}

# -------------------------
# Persona helper
# -------------------------
EXTRA_PERSONAS = ["Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"]
def get_persona_options(brand_key):
    base = brand_data.get(brand_key, {}).get("personas", [])
    combined = base + [p for p in EXTRA_PERSONAS if p not in base]
    return combined

# -------------------------
# Chat message rendering
# -------------------------
def render_ai_message(message_html):
    st.markdown(f"""
    <div class="ai-message">
        <img src="{AI_AVATAR}" class="ai-avatar" />
        <div class="ai-bubble">{message_html}</div>
    </div>
    """, unsafe_allow_html=True)

def render_user_message(msg):
    st.markdown(f'<div class="user-bubble">{escape(msg)}</div>', unsafe_allow_html=True)

# -------------------------
# Sidebar selections
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]

    segment = st.selectbox("Segment", bconf["segments"])
    persona_sel = st.selectbox("HCP Persona", get_persona_options(sel_brand), index=0)
    st.session_state.hcp_persona = persona_sel

    hcp_personality = st.selectbox("HCP Personality", ["Assertive", "Masked", "Friendly", "Details-oriented", "Skeptic"])
    st.session_state.hcp_personality = hcp_personality

    barrier = st.multiselect("Doctor Barrier", bconf["barriers"])
    specialty = st.selectbox("Specialty", bconf["specialties"])
    objective = st.selectbox("Objective", ["Awareness", "Adoption", "Retention"])
    st.session_state.temperature = st.slider("Temperature", 0.0, 1.0, st.session_state.temperature, 0.05)
    st.session_state.search_mode = st.selectbox("Search mode", ["deep", "shallow"])
    st.session_state.language = st.radio("Language", ["English", "Arabic"])
    st.session_state.tone = st.selectbox("Tone", ["executive", "coaching", "persuasive", "clinical"], index=0)
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []
        st.experimental_rerun()

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
# PDF upload & text extraction
# -------------------------
def extract_pdf_text(uploaded_file):
    if not PdfReader:
        return "PyPDF2 not installed. Cannot read PDF."
    try:
        reader = PdfReader(uploaded_file)
        text = "\n".join([page.extract_text() or "" for page in reader.pages])
        return text
    except Exception as e:
        return f"Error reading PDF: {e}"

uploaded_file = st.file_uploader("Upload PDF (Clinical / Sales)", type=["pdf"])
if uploaded_file:
    pdf_text = extract_pdf_text(uploaded_file)
    st.session_state.uploaded_pdf_text = pdf_text
    st.session_state.pdf_summary = f"PDF uploaded. {len(pdf_text.split())} words extracted."

if st.session_state.pdf_summary:
    st.markdown(f"<div class='story'>{st.session_state.pdf_summary}</div>", unsafe_allow_html=True)

# -------------------------
# Helper: Simple summarization (fallback)
# -------------------------
def summarize_text(text, max_len=200):
    if not text: return ""
    return text[:max_len] + ("..." if len(text) > max_len else "")

# -------------------------
# Load medical references
# -------------------------
def load_medical_summary(brand_key):
    path = brand_data[brand_key].get("references_path")
    if not path or not os.path.exists(path):
        return "No medical references available."
    files = [f for f in os.listdir(path) if f.endswith(".txt")]
    texts = []
    for f in files:
        try:
            with open(os.path.join(path, f), "r", encoding="utf-8") as file:
                texts.append(file.read())
        except: continue
    return "\n".join(texts)

# -------------------------
# Load sales module summaries
# -------------------------
def load_sales_summary(brand_key):
    path = brand_data[brand_key].get("sales_path")
    if not path or not os.path.exists(path):
        return "No sales summaries available."
    files = [f for f in os.listdir(path) if f.endswith(".txt")]
    texts = []
    for f in files:
        try:
            with open(os.path.join(path, f), "r", encoding="utf-8") as file:
                texts.append(file.read())
        except: continue
    return "\n".join(texts)

# Initialize summaries
if not st.session_state.medical_summary:
    st.session_state.medical_summary = summarize_text(load_medical_summary(st.session_state.selected_brand), 500)
if not st.session_state.sales_summary:
    st.session_state.sales_summary = summarize_text(load_sales_summary(st.session_state.selected_brand), 500)

# -------------------------
# Display summaries
# -------------------------
with st.expander("Medical References Summary", expanded=False):
    st.markdown(st.session_state.medical_summary)

with st.expander("Sales Module Summary", expanded=False):
    st.markdown(st.session_state.sales_summary)

# -------------------------
# Objection handling
# -------------------------
def render_objections():
    obs = brand_data[st.session_state.selected_brand].get("objections", {})
    if not obs: return
    st.markdown("<div class='step-title'>Objection Handling</div>", unsafe_allow_html=True)
    for k, v in obs.items():
        st.markdown(f"<div class='objection'><b>{k.capitalize()}:</b> {v}</div>", unsafe_allow_html=True)

render_objections()

# -------------------------
# AI Chat Input
# -------------------------
def ai_response(prompt):
    # Placeholder AI response logic, replace with OpenAI/GROQ
    base_text = f"Brand: {st.session_state.selected_brand}\nPersona: {st.session_state.hcp_persona}\nTone: {st.session_state.tone}\n\nPrompt: {prompt}"
    if st.session_state.pdf_summary:
        base_text += f"\n\nPDF Summary: {st.session_state.pdf_summary}"
    return base_text[:800] + "..."  # truncate for display

st.markdown("<div class='step-title'>AI Chat</div>", unsafe_allow_html=True)
main_input = st.text_area("Enter your question / prompt:", value=st.session_state.main_input, height=80)
if st.button("Send"):
    if main_input.strip():
        st.session_state.chat_history.append({"user": main_input})
        ai_msg = ai_response(main_input)
        st.session_state.chat_history.append({"ai": ai_msg})
        st.session_state.main_input = ""

# -------------------------
# Render chat history
# -------------------------
for msg in st.session_state.chat_history:
    if "user" in msg:
        render_user_message(msg["user"])
    if "ai" in msg:
        render_ai_message(msg["ai"])

# -------------------------
# Audio generation (gTTS / ElevenLabs)
# -------------------------
def play_audio(text):
    if ELEVENLABS_AVAILABLE:
        try:
            from elevenlabs import generate, play
            audio = generate(text=text, voice="alloy")
            play(audio)
            return
        except:
            pass
    if gTTS:
        tts = gTTS(text=text)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tmp_file.name)
        st.audio(tmp_file.name)

if st.session_state.chat_history:
    last_ai_msg = st.session_state.chat_history[-1].get("ai")
    if last_ai_msg:
        if st.button("🔊 Play Last AI Response"):
            play_audio(last_ai_msg)

# -------------------------
# Prompt suggestions (collapsible)
# -------------------------
suggestions = [
    "Highlight key efficacy points",
    "Address safety concerns",
    "Overcome cost objections",
    "Engage patient influence",
    "Summarize medical reference"
]
with st.expander("💡 Prompt Suggestions", expanded=False):
    for s in suggestions:
        if st.button(s):
            st.session_state.main_input = s

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown("<div class='fixed-disclaimer'>⚠️ AI Sales Call Assistant is a support tool. Always verify with latest clinical and sales guidelines.</div>", unsafe_allow_html=True)
