import streamlit as st
from PIL import Image
from io import BytesIO, BytesIO as io_bytes
import fitz
from pptx import Presentation
import base64
import groq
from groq import Groq
from datetime import datetime
import re
import time
import html  # for escaping

# Optional Word export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# Initialize Groq client
client = Groq(api_key="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")

# Session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Language selection
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])

# GSK Logo
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

# Brands
gsk_brands = {
    "Shingrix": "https://www.cdc.gov/shingles/hcp/clinical-overview",
    "Trelegy": "https://www.gsk.com/en-gb/products/trelegy/",
    "Zejula": "https://www.gsk.com/en-gb/products/zejula/"
}

# Filters/options
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

# Sidebar filters
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

# Upload PDF/PPT
uploaded_pdf = st.sidebar.file_uploader("Upload brand PDF", type="pdf")
uploaded_ppt = st.sidebar.file_uploader("Upload brand PPT", type=["pptx", "ppt"])

# Extract PDF images
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

# Extract PPT images
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

pdf_images = extract_pdf_images(uploaded_pdf) if uploaded_pdf else []
ppt_images = extract_ppt_images(uploaded_ppt) if uploaded_ppt else []
all_images = pdf_images + ppt_images

# Display visuals
if all_images:
    st.subheader("Uploaded Brand Visuals")
    for img in all_images:
        st.image(img, width=300)

# Clear chat
if st.button("🗑️ Clear Chat / مسح المحادثة"):
    st.session_state.chat_history = []

# Chat placeholder
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()

def display_chat(typing_effect=True, delay=0.2):
    chat_html = "<div id='chat-container' style='max-height:600px; overflow-y:auto; padding:10px;'>"
    for msg in st.session_state.chat_history:
        content = msg["content"]
        time_msg = msg.get("time","")
        # Split AI messages into steps if needed
        if msg["role"] == "ai":
            steps = re.split(r"(Acknowledge|Probing|Answer|Confirm|Transition)", content)
            steps = [s.strip() for s in steps if s.strip()]
        else:
            steps = [content]

        for step in steps:
            step_safe = html.escape(step).replace("\n","<br>")
            if msg["role"]=="ai":
                step_safe = re.sub(r"(Acknowledge|Probing|Answer|Confirm|Transition)", r"<b>\1</b>", step_safe)

            # Sender styling
            if msg["role"]=="user":
                icon_url = "https://img.icons8.com/emoji/48/000000/person-emoji.png"
                align="right"
                bg_color="#dcf8c6"
                border_radius="15px 15px 0px 15px"
            else:
                icon_url = "https://img.icons8.com/emoji/48/000000/robot-emoji.png"
                align="left"
                bg_color="#f0f2f6"
                border_radius="15px 15px 15px 0px"

            # Bubble HTML
            chat_html += f"""
            <div style='display:flex; justify-content:{'flex-end' if align=='right' else 'flex-start'}; margin:5px;'>
                <div style='background:{bg_color}; padding:10px; border-radius:{border_radius}; max-width:80%; display:flex; align-items:flex-start; border:2px solid #888;'>
                    <img src="{icon_url}" width="30" style='margin-right:10px;'>
                    <div style='flex:1;'>{step_safe}<div style='font-size:10px; color:gray; text-align:right;'>{time_msg}</div></div>
                </div>
            </div>
            """
            chat_placeholder.markdown(chat_html, unsafe_allow_html=True)
            if typing_effect and msg["role"]=="ai":
                time.sleep(delay)
    chat_html += "</div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# Chat input
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    submitted = st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})

    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)
    references = """
1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information.
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
        messages=[{"role":"system","content":f"You are a helpful sales assistant chatbot that responds in {language}."},
                  {"role":"user","content":prompt}],
        temperature=0.7
    )
    ai_output = response.choices[0].message.content
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M")})
    display_chat()

# Word download
if DOCX_AVAILABLE and st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response",0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io_bytes()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")

# Brand leaflet
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
