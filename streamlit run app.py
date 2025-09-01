import streamlit as st
from PIL import Image
import requests
from io import BytesIO, BytesIO as io_bytes
import base64
import groq
from groq import Groq
from datetime import datetime

# --- Optional dependency for PDF ---
try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    st.warning("⚠️ PyMuPDF not installed. PDF extraction disabled.")
    PDF_SUPPORT = False

# --- Optional dependency for PPT ---
try:
    from pptx import Presentation
    PPT_SUPPORT = True
except ImportError:
    st.warning("⚠️ python-pptx not installed. PPT extraction disabled.")
    PPT_SUPPORT = False

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
uploaded_pdf = st.sidebar.file_uploader("Upload brand PDF", type="pdf") if PDF_SUPPORT else None
uploaded_ppt = st.sidebar.file_uploader("Upload brand PPT", type=["pptx", "ppt"]) if PPT_SUPPORT else None

# --- Extract text and images from PDF ---
def extract_pdf_text_and_images(pdf_file):
    data = []
    if not PDF_SUPPORT or not pdf_file:
        return data
    try:
        import fitz
        doc = fitz.open(pdf_file)
        for page_number, page in enumerate(doc, start=1):
            page_text = page.get_text()
            for img_index, img in enumerate(page.get_images(full=True), start=1):
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                img_obj = Image.open(BytesIO(image_bytes))
                data.append({"type": "PDF", "page": page_number, "text": page_text[:500], "image": img_obj})
    except:
        st.warning("⚠️ Could not extract PDF text/images")
    return data

# --- Extract text and images from PPT ---
def extract_ppt_text_and_images(ppt_file):
    data = []
    if not PPT_SUPPORT or not ppt_file:
        return data
    try:
        from pptx import Presentation
        prs = Presentation(ppt_file)
        for slide_number, slide in enumerate(prs.slides, start=1):
            slide_text = ""
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    slide_text += shape.text + " "
            for shape in slide.shapes:
                if shape.shape_type == 13:  # Picture
                    image = shape.image
                    img_obj = Image.open(BytesIO(image.blob))
                    data.append({"type": "PPT", "slide": slide_number, "text": slide_text[:500], "image": img_obj})
    except:
        st.warning("⚠️ Could not extract PPT text/images")
    return data

# --- Combine visuals ---
pdf_data = extract_pdf_text_and_images(uploaded_pdf)
ppt_data = extract_ppt_text_and_images(uploaded_ppt)
all_visuals = pdf_data + ppt_data

# --- Function to select relevant images ---
def get_relevant_images(user_question, visuals, top_n=3):
    relevance = []
    question_words = set(user_question.lower().split())
    for v in visuals:
        text_words = set(v["text"].lower().split())
        score = len(question_words & text_words)
        relevance.append((score, v["image"]))
    relevance.sort(key=lambda x: x[0], reverse=True)
    top_images = [img for score, img in relevance if score > 0][:top_n]
    return top_images

# --- Clear chat ---
if st.button("🗑️ Clear Chat / مسح المحادثة"):
    st.session_state.chat_history = []

# --- Chat display ---
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()
def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time", "")
        content = msg["content"].replace('\n', '<br>')
        for step in ["Acknowledge", "Probing", "Answer", "Confirm", "Transition"]:
            content = content.replace(step, f"<b>{step}</b><br>")
        chat_html += f"<div style='text-align:{'right' if msg['role']=='user' else 'left'}; background:{'#dcf8c6' if msg['role']=='user' else '#f0f2f6'}; padding:10px; border-radius:15px; margin:5px; display:inline-block; max-width:80%;'>{content}<span style='font-size:10px; color:gray;'><br>{time}</span></div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)
display_chat()

# --- Chat input ---
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    submitted = st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})
    relevant_images = get_relevant_images(user_input, all_visuals, top_n=3)

    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)
    references = """
1. SHINGRIX Egyptian Drug Authority Approved Prescribing Information. Approval Date: 11-9-2023.
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
Use APACT technique.
Include references:
{references}
Embed only the most relevant uploaded PDF/PPT visuals (top 3) in the response.
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
    # Embed relevant visuals
    for img in relevant_images:
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        ai_output += f'<br><img src="data:image/png;base64,{img_str}" width="300">'

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
