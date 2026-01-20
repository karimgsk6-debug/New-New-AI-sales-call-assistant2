# app_final_complete.py
# AI Sales Call Assistant – Fully Dynamic Call Script Generator

import streamlit as st
import random
from html import escape
from datetime import datetime

# =========================
# GROQ API PLACEHOLDER
# =========================
GROQ_API_KEY = "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"

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
def init_state():
    defaults = {
        "chat_history": [],
        "selected_brand": "shingrix",
        "hcp_persona": "Friendly",
        "hcp_personality": "Friendly",
        "temperature": 0.8,
        "language": "English",
        "tone": "persuasive"
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_state()

# =========================
# BRAND DATA
# =========================
brand_data = {
    "shingrix": {
        "display": "Shingrix (Herpes Zoster Vaccine)",
        "segments": ["GP", "Dermatologist", "Geriatrician"],
        "barriers": ["Efficacy doubts", "Safety concerns", "Low patient demand"],
        "specialties": ["General Practice", "Dermatology", "Geriatrics"],
        "medical_summary": """
• Herpes Zoster affects almost 1 in 3 adults
• Risk increases significantly after age 50
• PHN is the most common complication
• Shingrix shows >90% efficacy across age groups
""",
        "sales_summary": """
• Strong guideline endorsement
• Clear unmet need in older adults
• Opportunity to educate non-vaccinating specialties
• Fits prevention-focused discussions
"""
    },

    "trelegy": {
        "display": "Trelegy Ellipta (COPD / Asthma)",
        "segments": ["Pulmonologist", "GP"],
        "barriers": ["Inhaler complexity", "Adherence", "Cost"],
        "specialties": ["Pulmonology", "General Practice"],
        "medical_summary": """
• Triple therapy improves lung function
• Reduces exacerbations
• Once-daily inhalation
• Strong GOLD guideline positioning
""",
        "sales_summary": """
• Simplification message is key
• Position against multiple inhalers
• Focus on adherence and outcomes
"""
    },

    "jemperli": {
        "display": "Jemperli (dMMR / MSI-H Oncology)",
        "segments": ["Oncologist"],
        "barriers": ["Eligibility", "Safety", "Reimbursement"],
        "specialties": ["Oncology"],
        "medical_summary": """
• PD-1 inhibitor
• Strong response rates in dMMR/MSI-H tumors
• Durable responses observed
""",
        "sales_summary": """
• Precision medicine positioning
• Diagnostic-driven discussions
• High unmet need populations
"""
    }
}

# =========================
# UI STYLES
# =========================
st.markdown("""
<style>
.ai-box {
    background: rgba(0,255,255,0.05);
    border: 1px solid rgba(0,255,255,0.2);
    padding: 16px;
    border-radius: 14px;
    margin: 12px 0;
}
.user-box {
    background: rgba(0,0,0,0.05);
    padding: 12px;
    border-radius: 12px;
    margin: 8px 0;
}
.step-title {
    font-weight: 700;
    color: #0ff;
    margin-top: 10px;
}
</style>
""", unsafe_allow_html=True)

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.header("🔧 Call Setup")

    brand = st.selectbox(
        "Brand",
        list(brand_data.keys()),
        format_func=lambda x: brand_data[x]["display"]
    )
    st.session_state.selected_brand = brand
    b = brand_data[brand]

    segment = st.selectbox("HCP Segment", b["segments"])
    specialty = st.selectbox("Specialty", b["specialties"])
    persona = st.selectbox(
        "Persona",
        ["Friendly", "Skeptical", "Evidence-led", "Uncommitted Vaccinator", "Time-pressured"]
    )
    barriers = st.multiselect("Barriers", b["barriers"])
    objective = st.selectbox("Objective", ["Awareness", "Adoption", "Retention"])

    if st.button("🧹 Clear Chat"):
        st.session_state.chat_history = []
        st.experimental_rerun()

# =========================
# TITLE
# =========================
st.title(f"💡 AI Sales Call Assistant — {b['display']}")

# =========================
# DYNAMIC SUMMARIES
# =========================
with st.expander("📘 Medical Reference Summary"):
    st.markdown(b["medical_summary"])

with st.expander("📊 Sales Module Summary"):
    st.markdown(b["sales_summary"])

# =========================
# CORE CALL SCRIPT ENGINE
# =========================
def generate_call_script():
    barrier_text = ", ".join(barriers) if barriers else "no major stated barriers"

    script = f"""
Here is a **tailored sales call flow for {b['display']}**, targeting a **{persona}**, specifically a **{specialty}**, with the objective of **{objective}**.

---

### **Prepare**
• Identify persona: {persona}, {segment}  
• Anticipated barriers: {barrier_text}  
• Target patients: Based on specialty guidelines  
• Rep preparation:
  - Review latest guidelines
  - Prepare one key clinical proof point
  - Define a clear call objective

**Rep should ask internally:**  
"What is the ONE insight this HCP doesn’t already know?"

---

### **Engage**
**What to SAY:**  
"Good morning Dr. [Name], I know your time is limited, I wanted to briefly discuss an important topic relevant to your patients."

**What to ASK:**  
• "How often do you encounter patients affected by this condition?"
• "What are your current challenges in managing/preventing it?"

---

### **Create Opportunities**
**What to SAY:**  
"Many physicians mention challenges around {barrier_text}. This is exactly where {b['display']} can help."

**What to ASK:**  
• "What would make management easier in your daily practice?"
• "Are there patient types you feel are underserved?"

---

### **Influence**
**Clinical positioning:**  
• Share 1–2 key data points (efficacy, durability, simplicity)
• Link data to real patient outcomes

**Handle objections:**  
"If safety/efficacy is a concern, clinical data shows strong consistency across populations."

**What to ASK:**  
• "How does this data compare with your current approach?"
• "Would this address your main concern?"

---

### **Impact / Close**
**What to SAY:**  
"Based on our discussion, introducing {b['display']} could be a meaningful step for selected patients."

**Next steps:**  
• Agreement on trial use
• Educational material for staff
• Follow-up plan

**Close question:**  
"What would be the best next step from your perspective?"

---

### **Post-Call Analysis**
• Document insights & objections  
• Update CRM segmentation  
• Define next call objective  
• Reflect: What worked? What didn’t?

---

✅ **Rep mindset:** Be consultative, not promotional. Lead with value.
"""
    return script

# =========================
# CHAT INTERFACE
# =========================
user_input = st.text_input("Type your request (e.g. 'Generate sales call flow')")

if st.button("Generate"):
    if user_input:
        st.session_state.chat_history.append(("user", user_input))
        response = generate_call_script()
        st.session_state.chat_history.append(("assistant", response))

# =========================
# CHAT DISPLAY
# =========================
for role, msg in st.session_state.chat_history:
    if role == "user":
        st.markdown(f"<div class='user-box'>{escape(msg)}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='ai-box'>{msg}</div>", unsafe_allow_html=True)

# =========================
# FOOTER
# =========================
st.markdown(
    "<small>⚠️ Internal training tool only. Verify all medical information.</small>",
    unsafe_allow_html=True
)
