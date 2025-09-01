import streamlit as st 
from PIL import Image
import requests
from io import BytesIO, BytesIO as io_bytes
import fitz  # PyMuPDF for PDF extraction
from pptx import Presentation  # For PPT extraction
import base64
import groq
from groq import Groq
from datetime import datetime
import re

# --- Optional dependency for Word download ---
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# --- Initialize Groq client ---
client = Groq(api_key="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")

# --- Session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Language selection ---
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])

# --- GSK Logo ---
logo_local_path = "images/gsk_logo.png"
logo_fallback_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
col1, col2 = st.columns([1,5])
with col1:
    try:
        logo_img = Image.open(logo_local_path)
        st.image(logo_img, width=120)
    except:
        st.image(logo_fallback_url, width=120)
with col2:
    st.title("🧠 AI Sales Call Assistant")

# --- Brand & product data ---
gsk_brands = {
    "Shingrix": "https://www.cdc.gov/shingles/hcp/clinical-overview",
    "Trelegy": "https://www.gsk.com/en-gb/products/trelegy/",
    "Zejula": "https://www.gsk.com/en-gb/products/zejula/"
}

# --- Filters & options ---
race_segments = [
    "R – Reach: Did not start to prescribe yet and Don't believe that vaccination is his responsibility.",
    "A – Acquisition: Prescribe to patient who initiate discussion about the vaccine but Convinced about Shingrix data.",
    "C – Conversion: Proactively initiate discussion with specific patient profile but For other patient profiles he is not prescribing yet.",
    "E – Engagement: Proactively prescribe to different patient profiles"
]
doctor_barriers = [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ Vx effective",
    "Accessibility issues"
]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
gsk_approaches = ["Use data-driven evidence", "Focus on patient outcomes", "Leverage storytelling techniques"]
sales_call_flow = ["Prepare", "Engage", "Create Opportunities", "Influence", "Drive Impact", "Post Call Analysis"]

# --- Sidebar filters ---
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
segment = st.sidebar.selectbox("Select RACE Segment / اختر شريحة RACE", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", options=doctor_barriers, default=[])
objective = st.sidebar.selectbox("Select Objective / اختر الهدف", options=objectives)
specialty = st.sidebar.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", options=specialties)
persona = st.sidebar.selectbox("Select HCP Persona / اختر شخصية الطبيب", options=personas)
response_length = st.sidebar.selectbox("Response Length / اختر طول الرد", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])
interface_mode = st.sidebar.radio("Interface Mode / اختر واجهة", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# --- Upload PDF / PPT ---
uploaded_pdf = st.sidebar.file_uploader("Upload brand PDF", type="pdf")
uploaded_ppt = st.sidebar.file_uploader("Upload brand PPT", type=["pptx", "ppt"])

# --- Extract images from PDF ---
def extract_pdf_images(pdf_file):
    images = []
    try:
        doc = fitz.open(pdf_file)
        for page in doc:
            for img in page.get_images(full=True):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                images.append(Image.open(BytesIO(image_bytes)))
    except:
        st.warning("⚠️ Could not extract images from PDF")
    return images

# --- Extract images from PPT ---
def extract_ppt_images(ppt_file):
    images = []
    try:
        prs = Presentation(ppt_file)
        for slide in prs.slides:
            for shape in slide.shapes:
                if shape.shape_type == 13:  # Picture
                    image = shape.image
                    images.append(Image.open(BytesIO(image.blob)))
    except:
        st.warning("⚠️ Could not extract images from PPT")
    return images

# --- Extracted visuals ---
pdf_images = extract_pdf_images(uploaded_pdf) if uploaded_pdf else []
ppt_images = extract_ppt_images(uploaded_ppt) if uploaded_ppt else []
all_images = pdf_images + ppt_images

# --- Display uploaded visuals ---
if all_images:
    st.subheader("Uploaded Brand Visuals")
    for img in all_images:
        st.image(img, width=300)

# --- Clear chat ---
if st.button("🗑️ Clear Chat / مسح المحادثة"):
    st.session_state.chat_history = []

# --- Chat history display ---
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()

def display_chat():
    chat_html = ""
    steps = ["Acknowledge", "Probing", "Answer", "Confirm", "Transition"]

    for msg in st.session_state.chat_history:
        time = msg.get("time", "")
        content = msg["content"].replace('\n', '<br>').strip()

        if msg["role"] == "user":
            chat_html += f"""
            <div style='display:flex; justify-content:flex-end; margin:5px;'>
                <div style='background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; border:2px solid #888; max-width:70%; display:flex; align-items:flex-start;'>
                    <div style='flex:1;'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>
                    <img src="https://img.icons8.com/emoji/48/000000/man-technologist-light-skin-tone.png" width="30" style='margin-left:10px;'>
                </div>
            </div>
            """
        else:
            pattern = r'(' + '|'.join(steps) + r')'
            parts = re.split(pattern, content)
            if parts[0].strip() and parts[0].strip() not in steps:
                parts = ["Info"] + parts
            i = 0
            while i < len(parts):
                step_name = parts[i].strip()
                text = ""
                if i + 1 < len(parts):
                    text = parts[i + 1].strip()
                if step_name not in steps + ["Info"]:
                    text = step_name + "<br>" + text
                    step_name = "Info"
                if text:
                    chat_html += f"""
                    <div style='display:flex; justify-content:flex-start; margin:5px;'>
                        <div style='background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; border:2px solid #888; max-width:70%; display:flex; align-items:flex-start;'>
                            <img src="https://img.icons8.com/emoji/48/000000/robot-emoji.png" width="30" style='margin-right:10px;'>
                            <div style='flex:1;'><b>{step_name}</b>: {text}<br><span style='font-size:10px; color:gray;'>{time}</span></div>
                        </div>
                    </div>
                    """
                i += 2
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# --- Chat input ---
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    submitted = st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})
    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)
    references = """
1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information. Approval Date: 11-9-2023. Version: GDS07/IPI02.
2. CDC Shingrix Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html
3. Strezova et al., 2022. Long-term Protection Against Herpes Zoster: https://doi.org/10.1093/ofid/ofac485
4. CDC Clinical Overview of Shingles: https://www.cdc.gov/shingles/hcp/clinical-overview/index.html
"""
    prompt = f"""
Language: {language}
User input: {user_input}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Brand: {brand}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Approved Sales Approaches:
{approaches_str}
Sales Call Flow Steps:
{flow_str}
Use APACT (Acknowledge → Probing → Answer → Confirm → Transition) technique.
Include references:
{references}
Embed the uploaded PDF/PPT visuals where relevant.
Provide actionable suggestions tailored to this persona.
Response Length: {response_length}
Response Tone: {response_tone}
"""
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "system", "content": f"You are a helpful sales assistant chatbot that responds in {language}."},{"role": "user", "content": prompt}],
        temperature=0.7
    )
    ai_output = response.choices[0].message.content
    st.session_state.chat_history.append({"role": "ai", "content": ai_output, "time": datetime.now().strftime("%H:%M")})
    display_chat()

# --- Word download ---
if DOCX_AVAILABLE and st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"] == "ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io_bytes()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")

# --- Brand leaflet link ---
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
