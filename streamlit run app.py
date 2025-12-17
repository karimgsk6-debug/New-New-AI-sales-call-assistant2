# ============================================================
# AI Sales Call Assistant - Full Merged Version
# ============================================================
import streamlit as st
import os, base64, io
from datetime import datetime

# -------------------------
# Optional imports
# -------------------------
try:
    from groq import Groq
except:
    Groq = None

# -------------------------
# API key placeholder
# -------------------------
GROQ_API_KEY = "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"

# ============================================================
# REPO ASSETS
# ============================================================
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"
AI_AVATAR = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

# ============================================================
# PATH CONFIG
# ============================================================
BASE_PATH = ".devcontainer"
SALES_MODULE_PATH = os.path.join(BASE_PATH, "SalesModule")
REFERENCE_PATH = os.path.join(BASE_PATH, "references")

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

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

# ============================================================
# BRAND DATA
# ============================================================
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

# ============================================================
# GROQ CLIENT INITIALIZATION
# ============================================================
def get_client():
    if not GROQ_API_KEY or GROQ_API_KEY == "Add_GROQ_API_here":
        return None
    if Groq is None:
        return None
    return Groq(api_key=GROQ_API_KEY)

# ============================================================
# Background helper
# ============================================================
def set_dynamic_background(image_path):
    if not os.path.exists(image_path):
        return
    try:
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
        st.markdown(
            f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background: linear-gradient(90deg, rgba(255,140,0,0.06), rgba(255,165,0,0.02)),
                            url("data:image/png;base64,{encoded}");
                background-repeat: no-repeat;
                background-position: right top;
                background-size: cover;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass

set_dynamic_background(BACKGROUND_PATH)

# ============================================================
# CSS for avatar + chat bubbles + sticky input + footer
# ============================================================
st.markdown(
    """
    <style>
    .ai-message { display:flex; align-items:flex-start; gap:12px; margin:10px 0; }
    .ai-avatar { width:52px; height:52px; border-radius:50%; box-shadow: 0 0 12px rgba(0,255,255,0.6); flex-shrink:0; animation:holoPulse 2.5s infinite ease-in-out; }
    @keyframes holoPulse { 0% { box-shadow:0 0 8px rgba(0,255,255,0.35);} 50% { box-shadow:0 0 22px rgba(0,255,255,0.9);} 100% { box-shadow:0 0 8px rgba(0,255,255,0.35);} }
    .ai-bubble { background: rgba(255,255,255,0.06); border:1px solid rgba(0,255,255,0.18); color:#E6FBFF; padding:14px; border-radius:14px; backdrop-filter: blur(6px); max-width:90%; white-space:pre-wrap; }

    .user-bubble{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }

    .suggestions-box{ background: rgba(20,20,40,0.5); padding:10px; border-radius:8px; margin-bottom:6px; color:#CFF; }

    /* Sticky input */
    .stTextInput>div>div>input {position: fixed !important; bottom: 8px; width:calc(100% - 40px); z-index:1000; }
    footer { position: fixed !important; bottom:0; width:100%; opacity:0.85; font-size:12px; text-align:center; color:#aac; background: rgba(0,0,0,0.02); }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# Objection handling per product & persona
# ============================================================
def persona_profile(name):
    return {"quick_win": "Provide concise data highlight and 1-line adoption suggestion."}

def objection_response(product_key, objection_key, persona):
    product = brand_data.get(product_key, {})
    base = product.get("objections", {})
    reply = base.get(objection_key, "Acknowledge the concern, offer concise evidence, and propose a low-effort next step.")
    prof = persona_profile(persona)

    if "evidence" in persona.lower():
        return f"Answer (Evidence-led): {reply} Provide trial highlights and one quick citation; offer to share a 1-page evidence summary."
    if "time" in persona.lower():
        return f"Answer (Time-pressured): {reply} Then offer a single-sentence script and a nurse checklist to make adoption painless."
    if "skeptical" in persona.lower():
        return f"Answer (Skeptical): {reply} Start by acknowledging, then show safety data and a monitoring plan; propose a conservative pilot."
    if "early" in persona.lower():
        return f"Answer (Early-adopter): {reply} Highlight differentiation and offer to co-design a small pilot with outcome monitoring."
    return f"{reply} (Tailored suggestion: {prof['quick_win']})"

# ============================================================
# Prompt suggestions
# ============================================================
def make_suggestions(brand_key, persona_val, barriers_list, segment_val, specialty_val, objective_val):
    s=[]
    s.append(f"Generate call flow for {persona_val} focused on {objective_val}.")
    if barriers_list: s.append(f"Handle objection: {', '.join(barriers_list[:2])} for {persona_val}.")
    else: s.append(f"Identify common objections for {persona_val}.")
    s.append(f"Summarize HCP persona insights for {persona_val}.")
    s.append(f"Key talking points for {brand_data[brand_key]['display']} in {segment_val}.")
    s.append(f"Draft a short adoption message for {brand_data[brand_key]['display']} to a {specialty_val}.")
    return s

# ============================================================
# Load references and sales summaries
# ============================================================
def load_summary(folder_path):
    summary = ""
    if not os.path.exists(folder_path):
        return summary
    for fname in os.listdir(folder_path):
        fpath = os.path.join(folder_path, fname)
        if os.path.isfile(fpath) and fname.endswith(".txt"):
            with open(fpath, "r", encoding="utf-8") as f:
                summary += f.read() + "\n"
    return summary

def generate_sales_call(scenario):
    client = get_client()
    if not client:
        return "⚠️ GROQ API unavailable - running in fallback mode."
    # Placeholder: in real app, replace with actual GROQ/Llama call
    return f"Generated sales call for {scenario['persona']} regarding {scenario['brand']}."

# ============================================================
# Main interface
# ============================================================
st.title("AI Sales Call Assistant")

# Brand selection
brand_key = st.selectbox("Select brand", list(brand_data.keys()), index=0)
bconf = brand_data[brand_key]

persona_val = st.selectbox("Select HCP persona", bconf["personas"])
segment_val = st.selectbox("Segment", bconf["segments"])
specialty_val = st.selectbox("Specialty", bconf["specialties"])
objective_val = st.text_input("Objective for call", "Increase adoption")

# Collapsible prompt suggestions
with st.expander("Prompt Suggestions", expanded=False):
    prompts = make_suggestions(brand_key, persona_val, bconf["barriers"], segment_val, specialty_val, objective_val)
    for p in prompts:
        st.markdown(f"- {p}", unsafe_allow_html=True)

# Input scenario
scenario = {"brand": brand_key, "persona": persona_val, "segment": segment_val, "specialty": specialty_val, "objective": objective_val}
if st.button("Generate Sales Call"):
    output = generate_sales_call(scenario)
    st.markdown(f"""
    <div class="ai-message">
        <img class="ai-avatar" src="{AI_AVATAR}">
        <div class="ai-bubble">{output}</div>
    </div>
    """, unsafe_allow_html=True)

# Footer disclaimer
st.markdown('<div class="fixed-disclaimer">⚠️ This tool is for internal training purposes only.</div>', unsafe_allow_html=True)
