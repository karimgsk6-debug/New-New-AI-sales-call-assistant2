import streamlit as st
from PIL import Image
import requests
from io import BytesIO, BytesIO as io_bytes
import groq
from groq import Groq
from datetime import datetime
import pdfplumber
import asyncio
import edge_tts
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
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "extracted_medical_ref" not in st.session_state:
    st.session_state.extracted_medical_ref = ""

# --- Language ---
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
    "Shingrix": "https://example.com/shingrix-leaflet",
    "Trelegy": "https://example.com/trelegy-leaflet",
    "Zejula": "https://example.com/zejula-leaflet",
}
gsk_brands_images = {
    "Trelegy": "https://www.example.com/trelegy.png",
    "Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Zejula": "https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png",
}

# --- Filters & options (updated HCP segments & barriers) ---
race_segments = [
    "R – Reach: Did not start to prescribe yet and don't believe vaccination is their responsibility.",
    "A – Acquisition: Prescribe to patient who initiates discussion but convinced about data.",
    "C – Conversion: Proactively initiate discussion with specific patient profile.",
    "E – Engagement: Proactively prescribe to different patient profiles."
]
doctor_barriers = [
    "HCP does not consider HZ as risk",
    "No time for discussion",
    "Cost concerns",
    "Not convinced of efficacy",
    "Accessibility/Logistics",
    "Patient reluctance",
    "Other clinical doubts"
]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]
personas = [
    "Uncommitted Vaccinator",
    "Reluctant Efficiency",
    "Patient Influenced",
    "Committed Vaccinator"
]
gsk_approaches = [
    "Use data-driven evidence",
    "Focus on patient outcomes",
    "Leverage storytelling techniques"
]
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

# --- PDF Upload & automatic medical reference extraction ---
uploaded_pdf = st.file_uploader("Upload PDF for AI reference / تحميل PDF للرجوع إليه", type="pdf")
show_more_toggle = st.checkbox("Show full PDF text / عرض النص الكامل للـ PDF", value=False)

if uploaded_pdf:
    pdf_text = ""
    with pdfplumber.open(uploaded_pdf) as pdf:
        for page in pdf.pages:
            pdf_text += page.extract_text() or ""
    st.session_state.uploaded_pdf_text = pdf_text if show_more_toggle else pdf_text[:1000]+"..."
    
    # Extract medical references
    matches = re.findall(r"(?:CDC|FDA|Guideline|Study|202\d)[^.\n]*", pdf_text, flags=re.I)
    st.session_state.extracted_medical_ref = ", ".join(matches) if matches else ""
    
    st.markdown(f"**PDF Preview:** {st.session_state.uploaded_pdf_text}")
    if st.session_state.extracted_medical_ref:
        st.info(f"📄 Extracted Medical Reference(s): {st.session_state.extracted_medical_ref}")

# --- Display brand image safely ---
image_path = gsk_brands_images.get(brand)
try:
    if image_path.startswith("http"):
        response = requests.get(image_path)
        img = Image.open(BytesIO(response.content))
    else:
        img = Image.open(image_path)
    st.image(img, width=200)
except:
    st.warning(f"⚠️ Could not load image for {brand}. Using placeholder.")
    st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)

# --- Clear chat ---
if st.button("🗑️ Clear Chat / مسح المحادثة"):
    st.session_state.chat_history = []

# --- Chat history display ---
st.subheader("💬 Chatbot Interface / واجهة الدردشة")
chat_placeholder = st.empty()

def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time", "")
        content = msg["content"].replace('\n', '<br>')
        apact_steps = ["Acknowledge", "Probing", "Answer", "Confirm", "Transition"]
        for step in apact_steps:
            content = content.replace(step, f"<b>{step}</b><br>")

        if msg["role"] == "user":
            chat_html += f"""
            <div style='text-align:right; background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; margin:5px; display:inline-block; max-width:80%;'>
                {content}<span style='font-size:10px; color:gray;'><br>{time}</span>
            </div>
            """
        else:
            audio_html = f"<br><audio controls style='margin-top:5px;'><source src='data:audio/mp3;base64,{msg.get('audio','')}' type='audio/mp3'></audio>" if msg.get('audio') else ""
            chat_html += f"""
            <div style='text-align:left; background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; margin:5px; display:inline-block; max-width:80%;'>
                {content}<span style='font-size:10px; color:gray;'><br>{time}</span>{audio_html}
            </div>
            """
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# --- Chat input using Streamlit form ---
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message / اكتب رسالتك هنا", key="user_input_box")
    submitted = st.form_submit_button("➤")

async def generate_tts(text, lang):
    voice = "en-US-JennyNeural" if lang == "English" else "ar-EG-SalmaNeural"
    tts = edge_tts.Communicate(text, voice=voice)
    filename = f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
    await tts.save(filename)
    audio_bytes = open(filename,"rb").read()
    return base64.b64encode(audio_bytes).decode("utf-8")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})
    
    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)
    medical_ref_str = st.session_state.extracted_medical_ref or "None"

    prompt = f"""
Language: {language}
User input: {user_input}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None
