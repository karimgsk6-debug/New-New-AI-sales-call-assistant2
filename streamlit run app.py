# ======================================================
# AI PHARMA SALES CALL SIMULATOR (ENTERPRISE VERSION)
# ======================================================

import streamlit as st
import os, base64
from html import escape

# -------------------------
# OPTIONAL IMPORTS
# -------------------------
try:
    from groq import Groq
except:
    Groq = None

# -------------------------
# PAGE CONFIG
# -------------------------
st.set_page_config(
    page_title="AI Sales Call Simulator",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------
# SESSION STATE
# -------------------------
for k, v in {
    "chat": [],
    "turn": "rep",
    "stage": "Opening"
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# -------------------------
# API CLIENT
# -------------------------
def get_llm():
    api_key = "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"
    if "ADD_GROQ" in api_key or Groq is None:
        return None
    return Groq(api_key=api_key)

# -------------------------
# PRODUCT INTELLIGENCE
# -------------------------
PRODUCTS = {
    "Shingrix": {
        "indication": "Prevention of herpes zoster in adults ≥50 years",
        "key_messages": [
            "High efficacy across age groups",
            "Durable protection",
            "Strong real-world evidence"
        ],
        "objections": {
            "Safety": "Reactogenicity is transient and expected",
            "Priority": "HZ burden increases sharply with age"
        },
        "sales_steps": [
            "Opening & rapport",
            "Disease awareness",
            "Risk identification",
            "Value positioning",
            "Objection handling",
            "Commitment"
        ],
        "references": [
            "ZOE-50 & ZOE-70 trials",
            "ACIP recommendations"
        ]
    },
    "Jemperli": {
        "indication": "dMMR recurrent or advanced endometrial cancer",
        "key_messages": [
            "Targeted for dMMR",
            "Durable responses",
            "Biomarker-driven precision"
        ],
        "objections": {
            "Eligibility": "Clear testing pathway",
            "Safety": "Manageable immune-related AEs"
        },
        "sales_steps": [
            "Account mapping",
            "Patient identification",
            "Testing discussion",
            "Clinical value",
            "Access discussion"
        ],
        "references": [
            "GARNET trial",
            "NCCN guidelines"
        ]
    },
    "Trelegy": {
        "indication": "COPD & asthma maintenance therapy",
        "key_messages": [
            "Once-daily triple therapy",
            "Improved adherence",
            "Reduced exacerbations"
        ],
        "objections": {
            "Technique": "Single inhaler simplicity",
            "Cost": "Reduced exacerbation burden"
        },
        "sales_steps": [
            "Patient profiling",
            "Treatment gaps",
            "Switch discussion",
            "Technique confidence",
            "Close"
        ],
        "references": [
            "IMPACT study",
            "GINA & GOLD"
        ]
    }
}

# -------------------------
# SIDEBAR (CRM-STYLE)
# -------------------------
with st.sidebar:
    st.header("🧠 Call Configuration")

    product = st.selectbox("Brand", PRODUCTS.keys())
    segment = st.selectbox("HCP Segment", ["Target","Growth","Maintain"])
    specialty = st.selectbox("Specialty", ["GP","Pulmonologist","Oncologist","Gyn-Onc"])
    persona = st.selectbox("Persona", ["Evidence-driven","Skeptical","Time-pressed"])
    style = st.selectbox("Communication Style", ["Challenger","Supportive","Concise"])
    barrier = st.selectbox("Primary Barrier", list(PRODUCTS[product]["objections"].keys()))
    objective = st.selectbox("Call Objective", ["Awareness","Adoption","Switch","Commitment"])

# -------------------------
# SYSTEM PROMPT (HCP ROLE)
# -------------------------
def build_hcp_prompt(user_input):
    p = PRODUCTS[product]
    return f"""
You are an HCP in a sales role-play.

Specialty: {specialty}
Persona: {persona}
Segment: {segment}
Communication style: {style}
Primary concern: {barrier}

Brand discussed: {product}
Indication: {p["indication"]}

You must:
- Speak ONLY as HCP
- Respond realistically
- Raise objections when appropriate
- Follow sales call stage: {st.session_state.stage}

Medical Rep says:
{user_input}
"""

# -------------------------
# HCP RESPONSE
# -------------------------
def hcp_reply(user_input):
    client = get_llm()
    if not client:
        return "[API NOT CONFIGURED – add key]"

    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":build_hcp_prompt(user_input)}],
        temperature=0.4
    )
    return r.choices[0].message.content

# -------------------------
# CHAT INPUT
# -------------------------
st.subheader("🗣 Rep ↔ HCP Live Simulation")

with st.form("chat", clear_on_submit=True):
    user = st.text_area("You are the Medical Rep", height=90)
    send = st.form_submit_button("Send")

if send and user:
    st.session_state.chat.append(("rep", user))
    hcp = hcp_reply(user)
    st.session_state.chat.append(("hcp", hcp))

# -------------------------
# CHAT RENDER
# -------------------------
for role, msg in st.session_state.chat:
    if role == "rep":
        st.markdown(f"<div style='background:#eee;padding:10px;border-radius:10px'>{escape(msg)}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='background:#0b3c49;color:#d9faff;padding:12px;border-radius:12px'>{escape(msg)}</div>", unsafe_allow_html=True)

# -------------------------
# STRUCTURED SALES CALL GENERATOR
# -------------------------
with st.expander("📋 Generate Full Brand Sales Call"):
    p = PRODUCTS[product]
    st.markdown("### Structured Sales Call")
    for step in p["sales_steps"]:
        st.markdown(f"**{step}**")
        st.write(f"Suggested messaging aligned with {product} value & {p['references'][0]}")

# -------------------------
# REFERENCES
# -------------------------
with st.expander("📚 Medical References"):
    for r in PRODUCTS[product]["references"]:
        st.write(f"• {r}")

st.caption("Internal training simulation – not for promotional use.")
