# ======================================================
# AI PHARMA SALES CALL SIMULATOR – STABLE VERSION
# ======================================================

import streamlit as st
from html import escape

# -------------------------
# OPTIONAL GROQ IMPORT
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
# SESSION STATE INIT
# -------------------------
if "chat" not in st.session_state:
    st.session_state.chat = []

if "rep_input" not in st.session_state:
    st.session_state.rep_input = ""

# -------------------------
# LLM CLIENT
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
        "sales_steps": [
            "Opening & rapport",
            "Disease awareness",
            "Risk identification",
            "Value positioning",
            "Objection handling",
            "Commitment"
        ],
        "objections": {
            "Safety": "Reactogenicity is transient and expected",
            "Priority": "HZ risk increases with age"
        },
        "references": ["ZOE-50", "ZOE-70", "ACIP"]
    },
    "Jemperli": {
        "indication": "dMMR advanced or recurrent endometrial cancer",
        "sales_steps": [
            "Account mapping",
            "Patient identification",
            "Testing discussion",
            "Clinical value",
            "Access"
        ],
        "objections": {
            "Eligibility": "Clear biomarker pathway",
            "Safety": "Manageable immune AEs"
        },
        "references": ["GARNET", "NCCN"]
    },
    "Trelegy": {
        "indication": "COPD and asthma maintenance",
        "sales_steps": [
            "Patient profiling",
            "Treatment gaps",
            "Switch discussion",
            "Technique confidence",
            "Close"
        ],
        "objections": {
            "Technique": "Single inhaler simplicity",
            "Cost": "Reduced exacerbations"
        },
        "references": ["IMPACT", "GOLD", "GINA"]
    }
}

# -------------------------
# SIDEBAR
# -------------------------
with st.sidebar:
    st.header("🧠 Call Configuration")

    product = st.selectbox("Brand", PRODUCTS.keys())
    specialty = st.selectbox("Specialty", ["GP", "Pulmonologist", "Oncologist"])
    segment = st.selectbox("HCP Segment", ["Target", "Growth", "Maintain"])
    persona = st.selectbox("Persona", ["Evidence-driven", "Skeptical", "Time-pressed"])
    style = st.selectbox("Communication Style", ["Concise", "Challenger", "Supportive"])
    barrier = st.selectbox("Primary Barrier", PRODUCTS[product]["objections"].keys())
    objective = st.selectbox("Call Objective", ["Awareness", "Adoption", "Commitment"])

# -------------------------
# HCP PROMPT
# -------------------------
def hcp_prompt(rep_text):
    p = PRODUCTS[product]
    return f"""
You are an HCP in a role-play with a pharma rep.

Specialty: {specialty}
Persona: {persona}
Segment: {segment}
Style: {style}
Primary concern: {barrier}

Brand: {product}
Indication: {p['indication']}

Rules:
- Respond ONLY as the HCP
- Be realistic and challenging
- Raise objections when appropriate

Medical Rep says:
{rep_text}
"""

# -------------------------
# HCP RESPONSE
# -------------------------
def hcp_reply(rep_text):
    client = get_llm()
    if not client:
        return "[API NOT CONFIGURED – add key]"

    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": hcp_prompt(rep_text)}],
        temperature=0.4
    )
    return r.choices[0].message.content

# -------------------------
# MAIN UI
# -------------------------
st.subheader("🗣 Rep ↔ HCP Live Simulation")

st.text_area(
    "You are the Medical Rep",
    key="rep_input",
    height=100,
    placeholder="Start the call..."
)

if st.button("Send"):
    if st.session_state.rep_input.strip():
        rep_msg = st.session_state.rep_input
        st.session_state.chat.append(("rep", rep_msg))

        hcp_msg = hcp_reply(rep_msg)
        st.session_state.chat.append(("hcp", hcp_msg))

        st.session_state.rep_input = ""

# -------------------------
# CHAT DISPLAY
# -------------------------
for role, msg in st.session_state.chat:
    if role == "rep":
        st.markdown(
            f"<div style='background:#eee;padding:10px;border-radius:10px;margin:6px 0'>{escape(msg)}</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div style='background:#0b3c49;color:#d9faff;padding:12px;border-radius:12px;margin:6px 0'>{escape(msg)}</div>",
            unsafe_allow_html=True
        )

# -------------------------
# STRUCTURED SALES CALL
# -------------------------
with st.expander("📋 Structured Brand Sales Call"):
    st.markdown(f"### {product} Sales Call Flow")
    for step in PRODUCTS[product]["sales_steps"]:
        st.markdown(f"**{step}** – Aligned messaging and evidence")

# -------------------------
# REFERENCES
# -------------------------
with st.expander("📚 Medical References"):
    for ref in PRODUCTS[product]["references"]:
        st.write(f"• {ref}")

st.caption("Internal training simulator – not for promotional use.")
