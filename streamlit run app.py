# app.py - AI Sales Call Assistant (Final Full Version)
import streamlit as st
import os, base64
import requests

# Optional libs
try:
    from PyPDF2 import PdfReader
except:
    PdfReader = None

# -------------------------
# GROQ API Integration
# -------------------------
GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.com/v1/generate"

def call_groq_api(prompt):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {"prompt": prompt, "max_tokens": 500}
    try:
        response = requests.post(GROQ_API_URL, headers=headers, json=data)
        response.raise_for_status()
        return response.json().get("text", "")
    except:
        return None

# -------------------------
# Brand & Persona Data
# -------------------------
brand_data = {
    "brandA": {
        "display": "Brand A",
        "segments": ["High Potential", "Medium Potential"],
        "personas": ["Persona 1", "Persona 2"],
        "specialties": ["Cardiology", "Oncology"]
    },
    "brandB": {
        "display": "Brand B",
        "segments": ["High Potential", "Low Potential"],
        "personas": ["Persona 3", "Persona 4"],
        "specialties": ["Neurology", "Dermatology"]
    },
    "GSK": {
        "display": "GSK Brand",
        "segments": ["Premium", "Standard"],
        "personas": ["Expert Doctor", "Junior Doctor"],
        "specialties": ["Vaccines", "Respiratory"]
    }
}

# -------------------------
# Fallback local generator
# -------------------------
def generate_structured_sales_call_local(brand_key, persona, specialty, objective):
    return (
        f"Structured Sales Call for {brand_data[brand_key]['display']}\n"
        f"- Persona: {persona}\n"
        f"- Specialty: {specialty}\n"
        f"- Objective: {objective}\n"
        "- Key Points:\n"
        "  1. Greet and engage the doctor.\n"
        "  2. Address top 2 known barriers.\n"
        "  3. Highlight product efficacy and safety.\n"
        "  4. Share case/example or quick testimonial.\n"
        "  5. Close with call to action or next steps.\n"
    )

# -------------------------
# Page config and style
# -------------------------
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
/* Full-page linear orange gradient */
body, .stApp {
    background: linear-gradient(120deg, #FFA500, #FF7F50);
}

/* Title bubble */
.title-bubble {
    background: rgba(255, 255, 255, 0.9);
    border-radius: 20px;
    padding: 15px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
}

/* Logos in title */
.title-bubble img {
    height: 50px;
    margin-right: 10px;
}

/* Collapsible prompt suggestion */
.collapsible {
    background-color: #fff3e0;
    cursor: pointer;
    padding: 10px;
    border-radius: 10px;
    margin-bottom: 10px;
}

.content {
    padding: 10px;
    display: none;
    border-radius: 10px;
    background-color: #fff8f0;
}

/* Responsive three-column layout */
.column-container {
    display: flex;
    flex-wrap: wrap;
    gap: 15px;
}

.column {
    flex: 1;
    min-width: 300px;
}

/* Sticky disclaimer at the bottom */
.sticky-disclaimer {
    position: fixed;
    bottom: 0;
    left: 0;
    width: 100%;
    background-color: rgba(255,255,255,0.9);
    padding: 10px;
    text-align: center;
    font-size: 14px;
    border-top: 1px solid #ccc;
}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Title Bubble
# -------------------------
st.markdown("""
<div class="title-bubble">
    <div style="display:flex; align-items:center;">
        <img src="https://upload.wikimedia.org/wikipedia/commons/4/48/GSK_logo.svg" alt="GSK Logo">
        <img src="https://upload.wikimedia.org/wikipedia/commons/0/05/Artificial_intelligence_logo.svg" alt="AI Logo">
        <h2>AI Sales Call Assistant</h2>
    </div>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Sidebar Filters
# -------------------------
with st.sidebar:
    st.header("Filters & Inputs")
    sel_brand = st.selectbox("Select Brand", list(brand_data.keys()))
    persona = st.selectbox("Select Persona", brand_data[sel_brand]['personas'])
    specialty = st.selectbox("Select Specialty", brand_data[sel_brand]['specialties'])
    objective = st.text_input("Objective", "Promote product adoption")
    uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])

# -------------------------
# PDF Processing
# -------------------------
pdf_text = ""
if uploaded_file and PdfReader:
    reader = PdfReader(uploaded_file)
    for page in reader.pages:
        pdf_text += page.extract_text()

# -------------------------
# Prompt Suggestions Collapsible
# -------------------------
prompt_suggestions = """
<div class="collapsible">Prompt Suggestions (Click to Expand)</div>
<div class="content">
- Generate call flow for selected HCP.<br>
- Identify top barriers for this doctor.<br>
- Provide product comparison points.<br>
- Suggest objection handling script.<br>
- Highlight key clinical evidence.<br>
</div>

<script>
var coll = document.getElementsByClassName("collapsible");
for (var i = 0; i < coll.length; i++) {
  coll[i].addEventListener("click", function() {
    this.classList.toggle("active");
    var content = this.nextElementSibling;
    if (content.style.display === "block") { content.style.display = "none"; }
    else { content.style.display = "block"; }
  });
}
</script>
"""

# -------------------------
# Generate AI Output
# -------------------------
if st.button("Generate Sales Call Script"):
    prompt = f"Generate structured sales call for brand {sel_brand}, persona {persona}, specialty {specialty}, objective {objective}."
    ai_output = call_groq_api(prompt)
    
    if not ai_output:
        ai_output = generate_structured_sales_call_local(sel_brand, persona, specialty, objective)
    
    # -------------------------
    # Multi-brand dashboard (Responsive 3-column)
    # -------------------------
    st.markdown('<div class="column-container">', unsafe_allow_html=True)
    
    # Column 1 - PDF Summary
    st.markdown('<div class="column">', unsafe_allow_html=True)
    st.subheader("PDF Summary")
    st.text_area("PDF Content", pdf_text, height=400)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Column 2 - AI Output
    st.markdown('<div class="column">', unsafe_allow_html=True)
    st.subheader("AI Generated Sales Call")
    st.text_area("AI Output", ai_output, height=400)
    
    # Interactive feedback
    feedback = st.radio("Do you like this output?", ["👍 Yes", "👎 No"], key="feedback")
    if feedback == "👎 No":
        reason = st.selectbox("Why not?", [
            "Too generic",
            "Missing details",
            "Wrong tone",
            "Other"
        ])
        if st.button("Regenerate"):
            ai_output = call_groq_api(prompt)
            if not ai_output:
                ai_output = generate_structured_sales_call_local(sel_brand, persona, specialty, objective)
            st.text_area("Regenerated Output", ai_output, height=300)
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Column 3 - Prompt Suggestions
    st.markdown('<div class="column">', unsafe_allow_html=True)
    st.subheader("Prompt Suggestions")
    st.markdown(prompt_suggestions, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Sticky Disclaimer
# -------------------------
st.markdown("""
<div class="sticky-disclaimer">
⚠️ This AI-generated sales call content is for internal reference only. Always verify clinical data and company policies before use.
</div>
""", unsafe_allow_html=True)
