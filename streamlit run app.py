# ============================================================
# app.py - AI Sales Call Assistant (Fully merged, ready-to-paste)
# ============================================================

import streamlit as st
import os
import base64
import tempfile
from datetime import datetime
from html import escape

# -------------------------
# Optional imports
# -------------------------
try:
    from groq import Groq
except ImportError:
    Groq = None

# ============================================================
# API & Repo Config
# ============================================================
GROQ_API_KEY = "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"  # <-- Replace with your GROQ API key if available

REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"

GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"
AI_AVATAR = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

BASE_PATH = ".devcontainer"
SALES_MODULE_PATH = os.path.join(BASE_PATH, "SalesModule")
REFERENCE_PATH = os.path.join(BASE_PATH, "references")

# ============================================================
# Page config
# ============================================================
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# ============================================================
# Session defaults
# ============================================================
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
# Brand data
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
# GROQ CLIENT
# ============================================================
def get_client():
    if not GROQ_API_KEY or GROQ_API_KEY == "Add_GROQ_API_here" or Groq is None:
        return None
    try:
        return Groq(api_key=GROQ_API_KEY)
    except Exception as e:
        st.warning(f"⚠️ Could not initialize GROQ client: {e}")
        return None

# ============================================================
# Objection handling per product & persona
# ============================================================
def persona_profile(persona):
    profiles = {
        "Friendly": {"quick_win": "Offer concise key points and follow-up link."},
        "Evidence-led": {"quick_win": "Provide trial highlights and summary reference."},
        "Time-pressured": {"quick_win": "Provide one-line script and nurse checklist."},
        "Skeptical": {"quick_win": "Share safety data and small pilot option."},
        "Early-adopter": {"quick_win": "Offer co-design of pilot with outcomes."},
    }
    return profiles.get(persona, {"quick_win": "Provide a concise actionable step."})

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
# Load references & sales modules
# ============================================================
def load_folder_text(folder_path):
    texts = []
    if not os.path.exists(folder_path):
        return ""
    for f in os.listdir(folder_path):
        file_path = os.path.join(folder_path, f)
        if os.path.isfile(file_path) and f.lower().endswith(('.txt', '.md')):
            with open(file_path, "r", encoding="utf-8") as file:
                texts.append(file.read())
    return "\n\n".join(texts)

def generate_summaries(brand_key):
    bconf = brand_data.get(brand_key, {})
    refs_folder = bconf.get("references_path", "")
    sales_folder = bconf.get("sales_path", "")

    medical_text = load_folder_text(refs_folder)
    sales_text = load_folder_text(sales_folder)

    st.session_state.medical_summary = medical_text[:3000]  # limit for display
    st.session_state.sales_summary = sales_text[:3000]

# ============================================================
# Generate sales call (mock)
# ============================================================
def generate_sales_call(scenario):
    client = get_client()
    # Fallback if no client
    if client is None:
        return f"⚠️ GROQ API unavailable. Generating generic call for {st.session_state.selected_brand}...\nScenario: {scenario}\n[Generated text here]"
    # Insert real GROQ API call logic here if API key is set
    return f"[Brand-specific call generated via GROQ for {st.session_state.selected_brand}]\nScenario: {scenario}"

# ============================================================
# CSS & Background
# ============================================================
st.markdown(
    """
    <style>
    .ai-message { display:flex; align-items:flex-start; gap:12px; margin:10px 0; }
    .ai-avatar { width:52px; height:52px; border-radius:50%; box-shadow: 0 0 12px rgba(0,255,255,0.6); flex-shrink:0; animation:holoPulse 2.5s infinite ease-in-out; }
    @keyframes holoPulse { 0% { box-shadow:0 0 8px rgba(0,255,255,0.35);} 50% { box-shadow:0 0 22px rgba(0,255,255,0.9);} 100% { box-shadow:0 0 8px rgba(0,255,255,0.35);} }
    .ai-bubble { background: rgba(255,255,255,0.06); border:1px solid rgba(0,255,255,0.18); color:#E6FBFF; padding:14px; border-radius:14px; backdrop-filter: blur(6px); max-width:90%; white-space:pre-wrap; }
    .fixed-disclaimer{ font-size:12px; color:#aac; position:fixed; bottom:4px; left:4px; opacity:0.9; }
    </style>
    """,
    unsafe_allow_html=True,
)

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
# Sidebar: Brand selection
# ============================================================
st.sidebar.title("Select Brand")
selected_brand = st.sidebar.radio("Brand", options=list(brand_data.keys()), index=0)
st.session_state.selected_brand = selected_brand

generate_summaries(selected_brand)

# ============================================================
# Main interface
# ============================================================
st.title("AI Sales Call Assistant")
st.image(AI_AVATAR, width=120)
scenario = st.text_area("Enter scenario / HCP interaction:", height=120)
if st.button("Generate Sales Call"):
    output = generate_sales_call(scenario)
    st.markdown(f'<div class="ai-message"><img src="{AI_AVATAR}" class="ai-avatar"><div class="ai-bubble">{escape(output)}</div></div>', unsafe_allow_html=True)
    # Optionally add voice generation below here

# ============================================================
# Display summaries
# ============================================================
with st.expander("Medical Reference Summary"):
    st.text_area("Medical Summary", value=st.session_state.medical_summary, height=150)
with st.expander("Sales Module Summary"):
    st.text_area("Sales Summary", value=st.session_state.sales_summary, height=150)

# ============================================================
# Footer disclaimer
# ============================================================
st.markdown('<div class="fixed-disclaimer">⚠️ For internal use only. Not for external distribution.</div>', unsafe_allow_html=True)
