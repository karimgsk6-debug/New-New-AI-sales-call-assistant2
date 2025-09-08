import streamlit as st
import tempfile
import os
import fitz  # PyMuPDF
from gtts import gTTS
from docx import Document
from pptx import Presentation
from groq import Groq

# --- Page Setup ---
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# --- Sidebar ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/7/79/GSK_logo_2022.svg", width=150)
st.sidebar.title("AI Sales Call Assistant")
st.sidebar.markdown("""
This tool helps **pharma reps** prepare for customer interactions.  
⚠️ **Disclaimer:** Always refer to **approved GSK references**.  
""")

# --- Groq API Setup ---
api_key = os.getenv("GROQ_API_KEY") or st.sidebar.text_input("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", type="password")
if not api_key:
    st.warning("⚠️ Please enter your API Key to proceed.")
client = Groq(api_key=api_key) if api_key else None

# --- HCP Segments, Persona, Barriers ---
race_segments = [
    "R – Reach: Did not start to prescribe yet and Don't believe vaccination is his responsibility.",
    "A – Acquisition: Prescribe to patient who initiate discussion but is convinced about Shingrix data.",
    "C – Conversion: Proactively initiate discussion with specific patient profile but not prescribing for all.",
    "E – Engagement: Proactively prescribe to different patient profiles."
]
doctor_barriers = [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ vaccine is effective",
    "Accessibility issues"
]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
gsk_approaches = ["Use data-driven evidence", "Focus on patient outcomes", "Leverage storytelling techniques"]
sales_call_flow = ["Prepare", "Engage", "Create Opportunities", "Drive Impact", "Post Call Analysis"]
apact_steps = ["Acknowledge", "Probing", "Answer", "Confirm", "Transition"]

# --- Sidebar Filters ---
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand", options=["Shingrix", "Trelegy", "Zejula"])
segment = st.sidebar.selectbox("Select RACE Segment", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barriers", options=doctor_barriers)
objective = st.sidebar.selectbox("Select Objective", objectives)
specialty = st.sidebar.selectbox("Select Doctor Specialty", specialties)
persona = st.sidebar.selectbox("Select HCP Persona", personas)
response_length = st.sidebar.selectbox("Response Length", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])

# --- References ---
references = """📚 References:
1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information. Approval Date: 11-9-2023. Version: GDS07/IPI02.  
2. CDC Shingrix Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html  
3. Strezova et al., 2022. Long-term Protection Against Herpes Zoster: https://doi.org/10.1093/ofid/ofac485  
4. CDC Clinical Overview of Shingles: https://www.cdc.gov/shingles/hcp/clinical-overview/index.html  
"""

# --- Helper Functions ---
def extract_text_from_file(uploaded_file):
    """Extracts text from PDF, Word, or PowerPoint."""
    text = ""
    if uploaded_file.name.endswith(".pdf"):
        pdf = fitz.open(stream=uploaded_file.read(), filetype="pdf")
        for page in pdf:
            text += page.get_text()
    elif uploaded_file.name.endswith(".docx"):
        doc = Document(uploaded_file)
        for para in doc.paragraphs:
            text += para.text + "\n"
    elif uploaded_file.name.endswith(".pptx"):
        prs = Presentation(uploaded_file)
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text += shape.text + "\n"
    return text.strip()

def generate_ai_response(prompt):
    """Generates AI response using Groq LLM."""
    if not client:
        return "❌ Groq API Key not set. Cannot generate AI response."
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": "You are a helpful AI sales assistant."},
                      {"role": "user", "content": prompt}],
            model="llama3-70b-8192"
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"❌ Error generating response: {e}"

# --- Main Interface ---
st.title("💊 AI Sales Call Assistant")
st.markdown("📌 Prepare for your **customer interactions** with AI-powered insights.")

# --- File Upload ---
uploaded_file = st.file_uploader("📂 Upload reference material (PDF, DOCX, PPTX)", type=["pdf", "docx", "pptx"])
reference_text = ""
if uploaded_file:
    reference_text = extract_text_from_file(uploaded_file)
    with st.expander("📖 Extracted Reference Text"):
        st.write(reference_text if reference_text else "⚠️ No text extracted.")

# --- Text Input Only ---
st.subheader("📝 Type Your Message")
rep_input = st.text_area("Enter your message to generate AI sales call suggestions")

# --- AI Response Generation ---
if st.button("🚀 Generate AI Sales Call Suggestions"):
    if not rep_input.strip() and not reference_text:
        st.warning("⚠️ Please provide a message or upload reference material.")
    else:
        final_prompt = f"""
Language: English
User Input: {rep_input if rep_input else 'N/A'}
Segment: {segment}
Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Specialty: {specialty}
Persona: {persona}
Sales Approaches: {'; '.join(gsk_approaches)}
Sales Call Flow: {' → '.join(sales_call_flow)}
APACT Steps: {' → '.join(apact_steps)}
References: {references}
Reference material text: {reference_text if reference_text else 'N/A'}
Response Length: {response_length}
Response Tone: {response_tone}
"""
        response = generate_ai_response(final_prompt)
        st.markdown("## 🤖 AI Sales Call Suggestions")
        st.write(response)

        # Generate AI voice feedback
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            tts = gTTS(text=response, lang="en")
            tts.save(f.name)
            st.audio(f.name)
