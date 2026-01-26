import streamlit as st
from datetime import datetime
from groq import Groq
import os
from PyPDF2 import PdfReader
import re

# =========================
# OPTIONAL WORD DOWNLOAD
# =========================
try:
    from docx import Document
    from io import BytesIO as io_bytes
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# =========================
# GROQ CLIENT
# =========================
client = Groq(api_key="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")

# =========================
# BRAND MASTER DATA
# =========================
brand_data = {
    "shingrix": {
        "display":"Shingrix",
        "segments":["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas":["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers":["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
        "specialties":["GP","Dermatologist","Geriatrician"],
        "references_path":".devcontainer/references/shingrix/",
        "call_flow":["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Post-call Analysis"],
        "leaflet":"https://example.com/shingrix-leaflet"
    },
    "jemperli": {
        "display":"Jemperli",
        "segments":["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas":["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers":["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties":["Oncologist","Medical Oncologist"],
        "references_path":".devcontainer/references/jemperli/",
        "call_flow":["COCO","Anchor","Engage","Close"],
        "leaflet":"https://example.com/jemperli-leaflet"
    },
    "trelegy": {
        "display":"Trelegy",
        "segments":["Awareness","Diagnosis","Adoption","Adherence"],
        "personas":["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers":["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties":["GP","Pulmonologist","Respiratory Specialist"],
        "references_path":".devcontainer/references/trelegy/",
        "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"],
        "leaflet":"https://example.com/trelegy-leaflet"
    }
}

# =========================
# LOAD GUIDELINES WITH PAGE CITATION
# =========================
def load_guidelines_with_pages(path, max_chars=5000):
    pages = []
    if not os.path.exists(path):
        return ""

    for file in os.listdir(path):
        if file.lower().endswith(".pdf"):
            reader = PdfReader(os.path.join(path, file))
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages.append(f"[Guideline Page {i+1}]\n{text}")

    combined = "\n\n".join(pages)
    return combined[:max_chars]

# =========================
# OFF-LABEL DETECTION
# =========================
def detect_off_label(ai_text, guideline_text):
    risky_phrases = [
        "any patient",
        "all patients",
        "including children",
        "off-label",
        "unapproved",
        "broader population",
        "outside indication"
    ]

    for phrase in risky_phrases:
        if phrase.lower() in ai_text.lower():
            return True

    # crude population extension check
    populations = re.findall(r"(children|pregnant|immunocompromised|pediatric)", ai_text.lower())
    if populations and not any(p in guideline_text.lower() for p in populations):
        return True

    return False

# =========================
# SESSION STATE
# =========================
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# =========================
# HEADER
# =========================
st.title("🧠 AI Sales Call Assistant")
language = st.radio("Select Language / اختر اللغة", ["English", "العربية"])

# =========================
# SIDEBAR
# =========================
st.sidebar.header("Filters & Options")

brand_key = st.sidebar.selectbox(
    "Select Brand",
    options=list(brand_data.keys()),
    format_func=lambda x: brand_data[x]["display"]
)

brand_cfg = brand_data[brand_key]

segment = st.sidebar.selectbox("Segment", brand_cfg["segments"])
persona = st.sidebar.selectbox("Persona", brand_cfg["personas"])
barrier = st.sidebar.multiselect("Doctor Barriers", brand_cfg["barriers"])
specialty = st.sidebar.selectbox("Specialty", brand_cfg["specialties"])
objective = st.sidebar.selectbox("Objective", ["Awareness", "Adoption", "Retention"])
response_length = st.sidebar.selectbox("Response Length", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])

# =========================
# CLEAR CHAT
# =========================
if st.button("🗑️ Clear Chat"):
    st.session_state.chat_history = []

# =========================
# CHAT DISPLAY
# =========================
for msg in st.session_state.chat_history:
    role_icon = "🧑" if msg["role"] == "user" else "🤖"
    st.markdown(f"**{role_icon}:** {msg['content']}")

# =========================
# INPUT
# =========================
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...")
    submitted = st.form_submit_button("Send")

# =========================
# AI + RAG + GUARDRAILS
# =========================
if submitted and user_input.strip():

    st.session_state.chat_history.append({
        "role":"user",
        "content":user_input,
        "time":datetime.now().strftime("%H:%M")
    })

    guideline_text = load_guidelines_with_pages(brand_cfg["references_path"])
    flow_str = " → ".join(brand_cfg["call_flow"])

    prompt = f"""
STRICT COMPLIANCE RULES:
- Use ONLY approved indications from guideline text
- Cite page numbers for every clinical or indication statement
- NEVER generalize populations
- NEVER use placeholders
- If indication is unclear, say so explicitly

GUIDELINES (WITH PAGE NUMBERS):
{guideline_text}

USER REQUEST:
{user_input}

CONTEXT:
Brand: {brand_cfg['display']}
Segment: {segment}
Persona: {persona}
Specialty: {specialty}
Barriers: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}

CALL FLOW:
{flow_str}

Use APACT framework.
Tone: {response_tone}
Length: {response_length}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role":"system","content":"You are a compliant pharmaceutical sales AI."},
            {"role":"user","content":prompt}
        ],
        temperature=0.3
    )

    ai_output = response.choices[0].message.content

    # =========================
    # OFF-LABEL VALIDATION
    # =========================
    if detect_off_label(ai_output, guideline_text):
        ai_output = (
            "⚠️ **Compliance Notice:**\n\n"
            "Your request may involve off-label or non-approved use. "
            "This assistant can only discuss **approved indications explicitly stated in official guidelines**. "
            "Please rephrase your request within the approved label."
        )

    st.session_state.chat_history.append({
        "role":"ai",
        "content":ai_output,
        "time":datetime.now().strftime("%H:%M")
    })

    st.rerun()

# =========================
# DISCLAIMER (FIXED)
# =========================
st.markdown("""
<style>
.disclaimer {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    background: #f5f5f5;
    color: #333;
    font-size: 12px;
    padding: 10px;
    border-top: 1px solid #ddd;
    z-index: 9999;
}
</style>

<div class="disclaimer">
⚠️ <b>Disclaimer:</b> Internal training use only. Non-promotional.
AI-generated content does not replace approved medical, legal, or regulatory materials.
</div>
""", unsafe_allow_html=True)

# =========================
# LEAFLET
# =========================
st.markdown(f"[📄 Brand Leaflet – {brand_cfg['display']}]({brand_cfg['leaflet']})")
