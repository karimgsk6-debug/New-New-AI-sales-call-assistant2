import streamlit as st
import os, io, re, math
from datetime import datetime
from html import escape
from typing import List

# =========================
# GROQ API PLACEHOLDER
# =========================
GROQ_API_KEY = "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"

# =========================
# OPTIONAL IMPORTS
# =========================
try:
    from PyPDF2 import PdfReader
except:
    PdfReader = None

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# SESSION STATE INIT
# =========================
def init_session():
    defaults = {
        "chat": [],
        "brand": "shingrix",
        "persona": "Friendly",
        "specialty": "",
        "segment": "",
        "objective": "Awareness",
        "roleplay": False,
        "pdf_chunks": [],
        "pdf_sources": [],
        "temperature": 0.8
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_session()

# =========================
# BRAND DATA
# =========================
brand_data = {
    "shingrix": {
        "display": "Shingrix – Herpes Zoster Vaccine",
        "segments": ["GP", "Dermatologist", "Geriatrician"],
        "personas": ["Uncommitted Vaccinator", "Skeptical", "Evidence-led"],
        "specialties": ["Dermatologist", "GP", "Geriatrics"],
        "barriers": ["Safety", "Efficacy", "Patient demand"],
    },
    "trelegy": {
        "display": "Trelegy Ellipta – COPD / Asthma",
        "segments": ["Pulmonologist", "GP"],
        "personas": ["Time-pressured", "Guideline-driven"],
        "specialties": ["Pulmonologist", "GP"],
        "barriers": ["Adherence", "Device complexity", "Cost"],
    },
    "jemperli": {
        "display": "Jemperli – Immuno-Oncology",
        "segments": ["Oncologist"],
        "personas": ["Early adopter", "Skeptical"],
        "specialties": ["Oncologist"],
        "barriers": ["Eligibility", "Safety", "Reimbursement"],
    }
}

# =========================
# PDF INGESTION (RAG)
# =========================
def extract_pdf_text(uploaded_files):
    text, sources = [], []
    if not PdfReader:
        return [], []
    for f in uploaded_files:
        reader = PdfReader(f)
        raw = ""
        for p in reader.pages:
            raw += p.extract_text() or ""
        chunks = chunk_text(raw)
        for c in chunks:
            text.append(c)
            sources.append(f.name)
    return text, sources

def chunk_text(text, size=600):
    words = text.split()
    return [" ".join(words[i:i+size]) for i in range(0, len(words), size)]

def retrieve_context(query, chunks, k=3):
    scored = []
    q_words = set(query.lower().split())
    for c in chunks:
        score = sum(1 for w in q_words if w in c.lower())
        scored.append((score, c))
    scored.sort(reverse=True)
    return [c for s, c in scored[:k] if s > 0]

# =========================
# SALES CALL FLOW GENERATOR
# =========================
def generate_sales_call_flow():
    b = brand_data[st.session_state.brand]
    return f"""
Here is a tailored sales call flow for **{b['display']}**, targeting an **{st.session_state.persona}**, specifically a **{st.session_state.specialty}**, with the objective of **{st.session_state.objective}**:

---

### **Prepare**
- Persona: {st.session_state.persona}
- Specialty: {st.session_state.specialty}
- Objective: {st.session_state.objective}
- Key insight: High unmet need and under-recognition of disease burden

---

### **Engage**
- Opening: *"Good morning Doctor, thank you for your time."*
- Attention grabber: *"Many patients underestimate the long-term burden of this condition."*

---

### **Create Opportunities**
- Questioning: *"How often do you encounter eligible patients?"*
- Data introduction: Clinical efficacy, guideline alignment

---

### **Influence**
- Evidence: Guidelines, RCTs, real-world data
- Objection handling: Address safety, efficacy, eligibility
- Value framing: Patient outcomes & practice efficiency

---

### **Impact GSO**
- Agreement: Small next step (trial patients, education)
- Support: Materials, reminders, nurse education

---

### **Post-Call Analysis**
- CRM documentation
- Objection tracking
- Follow-up planning
"""

# =========================
# ROLE PLAY RESPONSE
# =========================
def roleplay_hcp_response(user_input, context):
    persona = st.session_state.persona
    tone = {
        "Uncommitted Vaccinator": "cautious, curious but hesitant",
        "Skeptical": "challenging and data-focused",
        "Evidence-led": "scientific and guideline-driven"
    }.get(persona, "neutral")

    return f"""
*(Speaking as a {persona} HCP, {tone})*

I hear what you're saying, but I still have concerns.

From my experience, patients often hesitate, and I want to clearly understand:
- Long-term benefit
- Safety profile
- Real guideline support

Can you clarify how this applies specifically to my patients?
"""

# =========================
# MAIN UI
# =========================
st.title("🧠 AI Sales Call Assistant")

# ---------- SIDEBAR ----------
with st.sidebar:
    st.header("Configuration")
    st.session_state.brand = st.selectbox(
        "Brand", brand_data.keys(),
        format_func=lambda x: brand_data[x]["display"]
    )
    st.session_state.segment = st.selectbox(
        "Segment", brand_data[st.session_state.brand]["segments"]
    )
    st.session_state.specialty = st.selectbox(
        "Specialty", brand_data[st.session_state.brand]["specialties"]
    )
    st.session_state.persona = st.selectbox(
        "Persona", brand_data[st.session_state.brand]["personas"]
    )
    st.session_state.objective = st.selectbox(
        "Objective", ["Awareness", "Adoption", "Retention"]
    )
    st.session_state.roleplay = st.checkbox("🎭 Role-Play Mode (AI = HCP)")
    st.session_state.temperature = st.slider("Creativity", 0.0, 1.0, 0.8)

    st.divider()
    uploaded = st.file_uploader("Upload PDFs (Guidelines, Studies)", accept_multiple_files=True)
    if uploaded:
        chunks, sources = extract_pdf_text(uploaded)
        st.session_state.pdf_chunks.extend(chunks)
        st.session_state.pdf_sources.extend(sources)
        st.success(f"{len(chunks)} knowledge chunks loaded")

# ---------- CHAT ----------
for c in st.session_state.chat:
    st.markdown(f"**{c['role']}**: {c['content']}")

user_input = st.chat_input("Type here…")

if user_input:
    st.session_state.chat.append({"role": "User", "content": user_input})

    if "generate sales call flow" in user_input.lower():
        reply = generate_sales_call_flow()

    elif st.session_state.roleplay:
        context = retrieve_context(user_input, st.session_state.pdf_chunks)
        reply = roleplay_hcp_response(user_input, context)

    else:
        context = retrieve_context(user_input, st.session_state.pdf_chunks)
        reply = "Based on available data:\n\n" + "\n".join(context[:2]) if context else "Please upload guidelines for grounded answers."

    st.session_state.chat.append({"role": "Assistant", "content": reply})
    st.rerun()
