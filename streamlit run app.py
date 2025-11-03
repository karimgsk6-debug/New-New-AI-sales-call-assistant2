# app.py - Full AI Sales Call Assistant with GROQ, Brand Config, Bullets, Sidebar & Dashboard
import streamlit as st
import os, io
from PyPDF2 import PdfReader
import requests
import numpy as np

# -------------------------
# Brand configuration & verbatim frameworks
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
# Framework titles & verbatim
# -------------------------
JEMPERLI_FRAMEWORK_TITLE = "IMPACT Competitive Selling Framework"
JEMPERLI_FRAMEWORK_VERBATIM = """COCO, or the commercial-oriented call objective, represents the pre-call planning step..."""
SHINGRIX_FRAMEWORK_TITLE = "EMOTIVE Selling Framework"
SHINGRIX_FRAMEWORK_VERBATIM = """1-PREPARE: Link to the last Call, Create Interest and share value..."""
GSK_DEFAULT_TITLE = "Competitive Selling Module"
GSK_DEFAULT_VERBATIM = """1-Prepare to sell
2-Open the sales call
3-Uncover opportunities
4-Align on brand and address objections
5-Close with commitments
6-Analyse sales call and plan next steps"""

# -------------------------
# GROQ API
# -------------------------
GROQ_API_KEY = "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"
GROQ_BASE_URL = "https://api.groq.ai/v1"

# -------------------------
# Helper functions
# -------------------------
def chunk_text(text, chunk_size=500):
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i+chunk_size]))
    return chunks

def upload_pdf(file):
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def groq_embed(texts):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    payload = {"input": texts, "model": "groq-text-embedding-3-small"}
    response = requests.post(f"{GROQ_BASE_URL}/embeddings", json=payload, headers=headers)
    response.raise_for_status()
    return [item['embedding'] for item in response.json()['data']]

def groq_search(query_embedding, embeddings, top_k=3):
    query_vec = np.array(query_embedding)
    emb_matrix = np.array(embeddings)
    scores = emb_matrix @ query_vec
    top_indices = scores.argsort()[-top_k:][::-1]
    return top_indices

def groq_chat(prompt):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    payload = {"model": "groq-chat-4", "messages": [{"role": "user", "content": prompt}]}
    response = requests.post(f"{GROQ_BASE_URL}/chat/completions", json=payload, headers=headers)
    response.raise_for_status()
    return response.json()['choices'][0]['message']['content']

def generate_ai_response(question):
    if "pdf_chunks" in st.session_state:
        query_emb = groq_embed([question])[0]
        top_indices = groq_search(query_emb, st.session_state['pdf_embeddings'])
        relevant_chunks = [st.session_state['pdf_chunks'][i] for i in top_indices]
        prompt = "Answer based on these excerpts:\n\n" + "\n\n".join(relevant_chunks)
        prompt += f"\n\nQuestion: {question}"
    else:
        prompt = question
    return groq_chat(prompt)

# -------------------------
# Generate practical bullets per brand
# -------------------------
def generate_practical_bullets(brand_key, persona_label="", specialty_label="", objective="Awareness", indications=None, evidence=None, key_insights=None, benefits=None, objections=None):
    out_lines = []
    indications = indications or []
    evidence = evidence or []
    key_insights = key_insights or []
    benefits = benefits or []
    objections = objections or []

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
        out_lines.append('    - Start with patient story based on COCO insights and align on objective.')
        out_lines.append('    - Example: "Dr. X, based on our last discussion, I want to focus on patients who... Is that OK?"')
        out_lines.append("")
        out_lines.append("**Engage (Two-way dialogue):**")
        out_lines.append("- Actions:")
        out_lines.append("    - Use open questions, listen, reflect; connect clinical data where appropriate.")
        out_lines.append('    - Example: "Tell me how you manage patients like Mrs. D — what is your biggest concern?"')
        out_lines.append("    - Suggested data to reference: " + (evidence[0] if evidence else "trial results or label data relevant to efficacy/safety."))
        out_lines.append("")
        out_lines.append("**Close (Commit & next steps):**")
        out_lines.append("- Actions:")
        out_lines.append("    - Agree on measurable incremental step (e.g., identify one eligible patient to start discussion).")
        out_lines.append('    - Example close: "Can we agree you will discuss this with one eligible patient this week and I will follow up?"')
        out_lines.append("    - Next action: set follow-up date and CRM note.")
        out_lines.append("")
    elif brand_key == "shingrix":
        out_lines.append("**PREPARE:**")
        out_lines.append("- Actions:")
        out_lines.append("    - Link to last call & identify eligible patient types (≥50y, comorbidities).")
        out_lines.append('    - Example: "I reviewed our last call regarding older adults at risk — focus on prevention."')
        if key_insights:
            out_lines.append("- Key clinical insights:")
            for k in key_insights:
                out_lines.append(f"    - {k}")
        out_lines.append("")
        out_lines.append("**ENGAGE:**")
        out_lines.append("- Actions (emotive):")
        out_lines.append("    - Build rapport, tell patient story, highlight feelings/impact.")
        out_lines.append('    - Example: "Imagine if a 65y diabetic developed shingles — impact on daily life?"')
        out_lines.append("    - Use vivid language: 'excruciating pain, lasting impact on sleep & mobility.'")
        out_lines.append("")
        out_lines.append("**CREATE OPPORTUNITY:**")
        out_lines.append("- Actions:")
        out_lines.append("    - Ask insightful questions to reveal unmet needs.")
        out_lines.append('    - Example: "How do you discuss prevention in chronic disease reviews?"')
        if benefits:
            out_lines.append("- Benefits to highlight:")
            for b in benefits:
                out_lines.append(f"    - {b}")
        out_lines.append("")
        out_lines.append("**INFLUENCE:**")
        out_lines.append("- Actions:")
        out_lines.append("    - Tailor message; handle objections via APACT.")
        if objections:
            out_lines.append("- Anticipated objections & replies:")
            for o in objections:
                out_lines.append(f"    - {o} — Suggested reply: provide evidence/practical mitigation.")
        out_lines.append("")
        out_lines.append("**IMPACT GSO & ANALYSE:**")
        out_lines.append("- Actions:")
        out_lines.append("    - Secure commitment (discuss Shingrix with next eligible patient).")
        out_lines.append("    - CRM action: log commitment, set follow-up, record barriers & next steps.")
        out_lines.append("")
    else:
        out_lines.append("**1 - Prepare to sell**")
        out_lines.append("- Actions: gather patient examples, recent data, prior call notes.")
        out_lines.append("")
        out_lines.append("**2 - Open the sales call**")
        out_lines.append("- Actions: attention opener, quick value statement.")
        out_lines.append("")
        out_lines.append("**3 - Uncover opportunities**")
        out_lines.append("- Actions: ask questions to surface unmet needs.")
        out_lines.append("")
        out_lines.append("**4 - Align on brand & address objections**")
        out_lines.append("- Actions: map benefits to unmet needs.")
        if objections:
            out_lines.append("- Objections & suggested responses:")
            for o in objections:
                out_lines.append(f"    - {o} — Provide data or workaround.")
        out_lines.append("")
        out_lines.append("**5 - Close with commitments**")
        out_lines.append("- Actions: request commitment, set next step.")
        out_lines.append("")
        out_lines.append("**6 - Analyse call & plan next steps**")
        out_lines.append("- Actions: capture insights, follow-up, iterate.")
        out_lines.append("")

    if not (key_insights or benefits or evidence or indications):
        out_lines.append("**Note:** Upload brand-specific documents for richer, evidence-based plan.")
    return "\n".join(out_lines)

# -------------------------
# Streamlit UI
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")
st.image("main_interface_photo.png", use_column_width=True)

# Initialize session state
if "pdf_docs" not in st.session_state:
    st.session_state["pdf_docs"] = {}
if "pdf_summaries" not in st.session_state:
    st.session_state["pdf_summaries"] = {}
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "selected_brand" not in st.session_state:
    st.session_state["selected_brand"] = list(brand_data.keys())[0]
if "feedback_stats" not in st.session_state:
    st.session_state["feedback_stats"] = {"like":0,"dislike":0,"need_more":0}

# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    st.markdown("<div style='display:flex;justify-content:center;align-items:center;'>", unsafe_allow_html=True)
    st.markdown("<img src='https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/845b8f1ae98e46440e840c0a906f3610dd343c9a/.devcontainer/GSK1-logo.png' style='height:64px'>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("Brand & Filters")
    sel_brand = st.selectbox("Brand", list(brand_data.keys()), index=list(brand_data.keys()).index(st.session_state["selected_brand"]), format_func=lambda k: brand_data[k]["display"])
    st.session_state["selected_brand"] = sel_brand
    bconf = brand_data[sel_brand]
    persona = st.selectbox("HCP Persona", bconf.get("personas", []))
    segment = st.selectbox("Segment", bconf.get("segments", []))
    barrier = st.multiselect("Doctor Barrier", bconf.get("barriers", []))
    specialty = st.selectbox("Specialty", bconf.get("specialties", []))
    objective = st.selectbox("Objective", ["Awareness","Adoption","Retention"])
    
    st.markdown("---")
    st.subheader("Upload (brand context)")
    uploaded_side = st.file_uploader("Upload PDF / TXT / DOCX", type=["pdf","txt","docx"], key="sidebar_upload")
    if uploaded_side:
        # Dummy text reader, replace with actual parsing
        text = "Extracted text from uploaded file."
        st.session_state["pdf_docs"].setdefault(sel_brand, "")
        st.session_state["pdf_docs"][sel_brand] += "\n\n" + text
        st.success("Sidebar file added.")

# -------------------------
# Header
# -------------------------
st.markdown("""
<div class="header">
  <div style="width:140px;"><img src="https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/845b8f1ae98e46440e840c0a906f3610dd343c9a/.devcontainer/GSK1-logo.png" class="left-logo"></div>
  <div class="title"><h2 style="margin:0">AI Sales Call Assistant</h2><div style="color:#555;font-size:13px;">APACT-guided — structured call flows</div></div>
  <div style="width:140px;text-align:right;"><img src="https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/845b8f1ae98e46440e840c0a906f3610dd343c9a/.devcontainer/AURA1.png" class="ai-logo"></div>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Sticky disclaimer
# -------------------------
st.markdown("""
<div class="disclaimer-sticky" aria-hidden="false">
  <div class="disclaimer-bubble" role="region" aria-label="Disclaimer (sticky)">
    <div style="font-size:13px; color:#111;">
      ⚠️ Internal tool — outputs are grounded in uploaded and repository references. Verify clinical and compliance information before external use.
    </div>
    <div style="font-size:13px; color:#333; opacity:0.9;">
      <b>Contact:</b> Compliance Team • <span style="margin-left:10px">GROQ key: {key_state}</span>
    </div>
  </div>
</div>
""".format(key_state=("set" if GROQ_API_KEY and GROQ_API_KEY != "Add_GROQ_API_here" else "not set")), unsafe_allow_html=True)
