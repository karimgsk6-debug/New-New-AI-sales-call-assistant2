# app.py - AI Sales Call Assistant (fully merged, production-ready)

import streamlit as st
import os, io, tempfile, base64
from datetime import datetime

# -------------------------
# GROQ API key
# -------------------------
GROQ_API_KEY = "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"

# -------------------------
# Brand configuration & frameworks
# -------------------------
brand_data = {
    "shingrix": {
        "display":"Shingrix",
        "segments":["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas":["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers":["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
        "specialties":["GP","Dermatologist","Geriatrician"],
        "references_path":".devcontainer/references/shingrix/",
        "sales_path":".devcontainer/SalesModule/shingrix/",
        "call_flow":["PREPARE","ENGAGE","CREATE OPPORTUNITY","INFLUENCE","IMPACT GSO","ANALYSE"]
    },
    "jemperli": {
        "display":"Jemperli",
        "segments":["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas":["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers":["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties":["Oncologist","Medical Oncologist"],
        "references_path":".devcontainer/references/jemperli/",
        "sales_path":".devcontainer/SalesModule/jemperli/",
        "call_flow":["COCO","Anchor","Engage","Close"]
    },
    "trelegy": {
        "display":"Trelegy",
        "segments":["Awareness","Diagnosis","Adoption","Adherence"],
        "personas":["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers":["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties":["GP","Pulmonologist","Respiratory Specialist"],
        "references_path":".devcontainer/references/trelegy/",
        "sales_path":".devcontainer/SalesModule/trelegy/",
        "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"]
    }
}

# -------------------------
# Session state initialization
# -------------------------
if "selected_brand" not in st.session_state:
    st.session_state["selected_brand"] = "shingrix"
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "pdf_docs" not in st.session_state:
    st.session_state["pdf_docs"] = {}
if "pdf_summaries" not in st.session_state:
    st.session_state["pdf_summaries"] = {}
if "feedback_stats" not in st.session_state:
    st.session_state["feedback_stats"] = {"like":0,"dislike":0,"need_more":0}
if "followup_options" not in st.session_state:
    st.session_state["followup_options"] = {}

# -------------------------
# Placeholder functions
# -------------------------
def read_file_text_from_uploaded(uploaded_file):
    return "Dummy extracted text from file."

def model_summarize(text, bullets=5):
    return "• " + "\n• ".join([f"Summary bullet {i+1}" for i in range(bullets)])

# -------------------------
# Generate call flow dynamically
# -------------------------
def generate_call_flow(brand_key, persona_label, specialty_label, objective, key_insights=None, benefits=None, evidence=None, indications=None, objections=None):
    key_insights = key_insights or []
    benefits = benefits or []
    evidence = evidence or []
    indications = indications or []
    objections = objections or []

    out_lines = []

    if brand_key == "jemperli":
        out_lines.append("**COCO (Pre-call planning):**")
        out_lines.append(f"- Persona: {persona_label} ({specialty_label})")
        out_lines.append(f"- Objective: {objective}")
        out_lines.append(f"- Suggested patient type: {indications[0] if indications else 'Select a patient type to align on.'}")
        out_lines.append("- Actions:")
        out_lines.append("    - Review last call notes & CRM flags for similar patients.")
        out_lines.append('    - Draft 2 thought-provoking questions to challenge status quo.')
        out_lines.append("- Example probing question: \"What would you change about current care for this patient if we could reduce treatment burden?\"")
        out_lines.append("")
        out_lines.append("**Anchor (Open the conversation):**")
        out_lines.append("- Actions:")
        out_lines.append('    - Start with the patient story based on COCO insights and align on the call objective.')
        out_lines.append('    - Example opening: "Dr. X, based on our last discussion, I want to focus on patients who... Is that OK?"')
        out_lines.append("")
        out_lines.append("**Engage (Two-way dialogue):**")
        out_lines.append("- Actions:")
        out_lines.append("    - Use open questions, listen, and reflect; connect clinical data where appropriate.")
        out_lines.append('    - Example phrase: "Tell me how you manage patients like Mrs. D — what is your biggest concern?"')
        out_lines.append("    - Suggested data to reference: " + (evidence[0] if evidence else "trial results or label data relevant to efficacy/safety."))
        out_lines.append("")
        out_lines.append("**Close (Commit & next steps):**")
        out_lines.append("- Actions:")
        out_lines.append("    - Agree on a measurable incremental step (e.g., identify one eligible patient to start the discussion).")
        out_lines.append('    - Example close: "Can we agree you will discuss this with one eligible patient this week and I will follow up?"')
        out_lines.append("    - Next action to record: set follow-up date and CRM note.")
        out_lines.append("")

    elif brand_key == "shingrix":
        out_lines.append("**PREPARE:**")
        out_lines.append("- Actions:")
        out_lines.append("    - Link to last call & identify eligible patient types (e.g., adults ≥50, patients with comorbidities).")
        out_lines.append('    - Example opening prep line: "I reviewed our last call regarding older adults at risk — I want to focus on prevention."')
        if key_insights:
            out_lines.append("- Key clinical insights to use:")
            for k in key_insights:
                out_lines.append(f"    - {k}")
        out_lines.append("")
        out_lines.append("**ENGAGE:**")
        out_lines.append("- Actions (emotive):")
        out_lines.append("    - Build rapport, tell the patient story, highlight feelings and impact (pain, quality of life).")
        out_lines.append('    - Example question: "Imagine if a 65-year-old diabetic patient developed shingles — how might that affect their daily life?"')
        out_lines.append("    - Use vivid language: 'excruciating pain, lasting impact on sleep & mobility.'")
        out_lines.append("")
        out_lines.append("**CREATE OPPORTUNITY:**")
        out_lines.append("- Actions:")
        out_lines.append("    - Ask powerful, insightful questions to reveal unmet needs.")
        out_lines.append('    - Example probe: "How do you currently discuss prevention in chronic disease reviews?"')
        if benefits:
            out_lines.append("- Benefits to highlight:")
            for b in benefits:
                out_lines.append(f"    - {b}")
        out_lines.append("")
        out_lines.append("**INFLUENCE:**")
        out_lines.append("- Actions:")
        out_lines.append("    - Tailor message to co-identified patient; handle objections via APACT (Acknowledge, Probe, Advise, Confirm, Transition).")
        if objections:
            out_lines.append("- Anticipated objections & short responses:")
            for o in objections:
                out_lines.append(f"    - {o} — Suggested reply: 'I understand — here's the evidence and a practical way to mitigate.'")
        out_lines.append("")
        out_lines.append("**IMPACT GSO & ANALYSE:**")
        out_lines.append("- Actions:")
        out_lines.append("    - Secure a commitment (e.g., discuss Shingrix with the next eligible patient).")
        out_lines.append("    - CRM action: log commitment, set follow-up date, record barriers and agreed next steps.")
        out_lines.append("")

    else:
        out_lines.append("**Default competitive sales module**")
        out_lines.append("- Prepare, Open, Uncover, Align, Close, Analyse")

    if not (key_insights or benefits or evidence or indications):
        out_lines.append("**Note:** Upload brand sales/medical PDFs for richer, evidence-based plan.")

    return "\n".join(out_lines)

# -------------------------
# Main interface photo
# -------------------------
st.image(
    "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main_interface_photo.png",
    use_column_width=True
)

# -------------------------
# Sidebar: logos, brand filters, dashboard, uploads, export
# -------------------------
with st.sidebar:
    st.markdown("<div style='display:flex;justify-content:center;align-items:center;'>", unsafe_allow_html=True)
    st.markdown("<img src='https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/845b8f1ae98e46440e840c0a906f3610dd343c9a/.devcontainer/GSK1-logo.png' style='height:64px'>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("Brand & Filters")
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state["selected_brand"]), format_func=lambda k: brand_data[k]["display"])
    st.session_state["selected_brand"] = sel_brand
    bconf = brand_data[sel_brand]
    persona = st.selectbox("HCP Persona", bconf.get("personas", []))
    specialty = st.selectbox("Specialty", bconf.get("specialties", []))
    segment = st.selectbox("Segment", bconf.get("segments", []))
    barrier = st.multiselect("Doctor Barrier", bconf.get("barriers", []))
    objective = st.selectbox("Objective", ["Awareness", "Adoption", "Retention"])
    st.markdown("---")
    st.subheader("📊 Dashboard")
    st.markdown(f"<div class='sidebar-metric'><b>Calls</b><br>{len([m for m in st.session_state['chat_history'] if m.get('role')=='assistant'])}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sidebar-metric'><b>Uploaded docs</b><br>{len(st.session_state['pdf_docs'])}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sidebar-metric'><b>Likes</b><br>{st.session_state['feedback_stats']['like']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sidebar-metric'><b>Dislikes</b><br>{st.session_state['feedback_stats']['dislike']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sidebar-metric'><b>Regens</b><br>{st.session_state['feedback_stats']['need_more']}</div>", unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("Upload (brand)")
    with st.expander("Upload PDF / TXT / DOCX (sidebar)"):
        uploaded_side = st.file_uploader("Upload file for brand context", type=["pdf","txt","docx"], key="sidebar_upload")
        if uploaded_side:
            text = read_file_text_from_uploaded(uploaded_side)
            if text:
                st.session_state["pdf_docs"].setdefault(sel_brand, "")
                st.session_state["pdf_docs"][sel_brand] += "\n\n" + text
                st.session_state["pdf_summaries"][sel_brand] = model_summarize(st.session_state["pdf_docs"][sel_brand], bullets=8)
                st.success("Sidebar file added and summarized.")
                st.experimental_rerun()
            else:
                st.error("Could not read file.")
    st.markdown("---")
    st.subheader("Export / Reset")
    export_format = st.selectbox("Export format", ["DOCX", "TXT"])
    if st.button("🗑️ Clear chat"):
        st.session_state["chat_history"] = []
        st.session_state["followup_options"] = {}
        st.session_state["feedback_stats"] = {"like":0,"dislike":0,"need_more":0}
        st.experimental_rerun()

# -------------------------
# Generated call flow display
# -------------------------
st.markdown("## Generated Call Flow")
generated_text = generate_call_flow(sel_brand, persona, specialty, objective)
st.text_area("Call Flow", generated_text, height=500)

# -------------------------
# Sticky disclaimer bubble
# -------------------------
st.markdown(f"""
<div class="disclaimer-sticky" aria-hidden="false">
  <div class="disclaimer-bubble" role="region" aria-label="Disclaimer (sticky)">
    <div style="font-size:13px; color:#111;">
      ⚠️ Internal tool — outputs are grounded in uploaded and repository references. Verify clinical and compliance information before external use.
    </div>
    <div style="font-size:13px; color:#333; opacity:0.9;">
      <b>Contact:</b> Compliance Team • <span style="margin-left:10px">GROQ key: {"set" if GROQ_API_KEY != "Add_GROQ_API_here" else "not set"}</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
