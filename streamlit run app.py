# ============================================================
# AI Sales Call Assistant - Fixed Sticky Footer + Response
# ============================================================
import streamlit as st
import os, base64

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
# GROQ CLIENT
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
    except:
        pass

set_dynamic_background(BACKGROUND_PATH)

# ============================================================
# Persona / objection helpers
# ============================================================
def persona_profile(name):
    return {"quick_win": "Provide concise data highlight and 1-line adoption suggestion."}

def objection_response(product_key, objection_key, persona):
    product = brand_data.get(product_key, {})
    base = product.get("objections", {})
    reply = base.get(objection_key, "Acknowledge the concern, offer concise evidence, and propose a low-effort next step.")
    prof = persona_profile(persona)
    return f"{reply} (Tailored: {prof['quick_win']})"

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
# Load summaries
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

# ============================================================
# Generate sales call (fallback enabled)
# ============================================================
def generate_sales_call(scenario):
    client = get_client()
    if client is None:
        # fallback response
        return f"Generated sales call for **{scenario['persona']}** regarding **{scenario['brand']}**. (Fallback mode)"
    # TODO: Replace with actual GROQ/Llama call
    return f"Generated sales call for {scenario['persona']} regarding {scenario['brand']}."

# ============================================================
# Sidebar filters
# ============================================================
st.sidebar.title("Filters / Selections")
brand_key = st.sidebar.selectbox("Select brand", list(brand_data.keys()), index=0)
bconf = brand_data[brand_key]

persona_val = st.sidebar.selectbox("Select HCP persona", bconf["personas"])
segment_val = st.sidebar.selectbox("Segment", bconf["segments"])
specialty_val = st.sidebar.selectbox("Specialty", bconf["specialties"])
objective_val = st.sidebar.text_input("Objective for call", "Increase adoption")

# ============================================================
# Main interface
# ============================================================
st.title("AI Sales Call Assistant")

# Collapsible prompt suggestions container
with st.expander("Prompt Suggestions (Click to insert in chat)", expanded=True):
    prompts = make_suggestions(brand_key, persona_val, bconf["barriers"], segment_val, specialty_val, objective_val)
    for p in prompts:
        if st.button(p, key=p):
            st.session_state.main_input += (" " + p)

# Input and Generate button
scenario = {"brand": brand_key, "persona": persona_val, "segment": segment_val, "specialty": specialty_val, "objective": objective_val}
user_input = st.text_input("Your message", value=st.session_state.main_input, key="chat_input")
if st.button("Generate Sales Call"):
    st.session_state.chat_history.append({"role":"user","content":user_input})
    output = generate_sales_call(scenario)
    st.session_state.chat_history.append({"role":"ai","content":output})
    st.session_state.main_input = ""  # reset input

# Display chat history
for msg in st.session_state.chat_history:
    if msg["role"]=="user":
        st.markdown(f'<div class="user-bubble">{msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="ai-message">
            <img class="ai-avatar" src="{AI_AVATAR}">
            <div class="ai-bubble">{msg["content"]}</div>
        </div>
        """, unsafe_allow_html=True)

# ============================================================
# Sticky disclaimer at bottom
# ============================================================
st.markdown(
    """
    <style>
    .disclaimer-box { 
        position: fixed; bottom: 0; left: 0; right: 0; 
        background:white; color:#333; padding:12px; 
        border-top:1px solid #ccc; z-index:9999; font-size:12px; 
        max-height:140px; overflow-y:auto;
    }
    </style>
    <div class="disclaimer-box">
    ⚠️ This tool is for internal training purposes only.
    </div>
    """,
    unsafe_allow_html=True
)
