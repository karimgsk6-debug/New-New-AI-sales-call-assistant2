import streamlit as st
from PIL import Image, ImageStat
import requests
from io import BytesIO, BytesIO as io_bytes
import groq
from groq import Groq
from datetime import datetime
import pdfplumber
import asyncio
import edge_tts
import base64
import re

# ----------------------------
# Optional Word download
# ----------------------------
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# ----------------------------
# GROQ client
# ----------------------------
client = Groq(api_key="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")

# ----------------------------
# Session state
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "extracted_medical_ref" not in st.session_state:
    st.session_state.extracted_medical_ref = ""

# ----------------------------
# Background image
# ----------------------------
BACKGROUND_URL = "https://sdmntprnortheu.oaiusercontent.com/files/00000000-7268-61f4-9aa6-71a39056c20e/raw?se=2025-09-25T15%3A15%3A06Z&sp=r&sv=2024-08-04&sr=b&scid=6870570a-c416-5cac-816d-8f43608d4723&skoid=b32d65cd-c8f1-46fb-90df-c208671889d4&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-25T03%3A34%3A38Z&ske=2025-09-26T03%3A34%3A38Z&sks=b&skv=2024-08-04&sig=zeUa/UVyTIdgz6/Qm5s/D47aOZrYQj/LJX9T60q%2BXBw%3D"

def get_brightness(url):
    try:
        response = requests.get(url)
        img = Image.open(BytesIO(response.content)).convert("L")
        stat = ImageStat.Stat(img)
        return stat.mean[0]
    except:
        return 255

brightness = get_brightness(BACKGROUND_URL)
text_color = "black" if brightness > 130 else "white"
button_bg = "#FFA500" if brightness > 130 else "#FF8C00"

st.markdown(f"""
<style>
.stApp {{
    background: url("{BACKGROUND_URL}") no-repeat center top fixed;
    background-size: cover;
}}
.title-box {{
    background: rgba(255,255,255,0.7);
    backdrop-filter: blur(1px);
    padding: 15px;
    border-radius: 12px;
    margin-bottom: 15px;
    color: black;
}}
.disclaimer {{
    font-size: 12px;
    color: black;
    background: rgba(255,255,255,0.7);
    padding: 6px;
    border-radius: 6px;
}}
.chat-bubble-user {{
    text-align: right;
    background: rgba(220,248,198,0.85);
    padding: 10px;
    border-radius: 15px 15px 0px 15px;
    margin: 5px;
    display: inline-block;
    max-width: 80%;
    color: {text_color};
}}
.chat-bubble-ai {{
    text-align: left;
    background: rgba(240,242,246,0.7);
    padding: 10px;
    border-radius: 15px 15px 15px 0px;
    margin: 5px;
    display: inline-block;
    max-width: 80%;
    color: {text_color};
}}
.highlight {{
    font-weight: bold;
    background-color: yellow;
    color: black;
    padding: 2px 4px;
    border-radius: 4px;
}}
.chat-input-container {{
    display: flex;
    margin-top: 10px;
}}
.chat-input-container input {{
    flex:1;
    padding:10px;
    border-radius:20px;
    border:none;
    outline:none;
    backdrop-filter: blur(8px);
    background-color: rgba(255,255,255,0.4);
    color: {text_color};
}}
.chat-input-container button {{
    margin-left:5px;
    border:none;
    border-radius:50%;
    width:45px;
    height:45px;
    cursor:pointer;
    font-weight:bold;
    background-color: {button_bg};
    color: white;
}}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Title & disclaimer
# ----------------------------
logo_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
col1, col2 = st.columns([1,5])
with col1:
    st.image(logo_url, width=120)
with col2:
    st.markdown(
        "<div class='title-box'><h2>💡 AI Sales Call Assistant</h2>"
        "<p>Powered by AI to equip sales reps for smarter HCP conversations</p></div>",
        unsafe_allow_html=True
    )
    st.markdown("<p class='disclaimer'>⚠️ Disclaimer: For training and educational purposes only.</p>", unsafe_allow_html=True)

# ----------------------------
# Brand & filters
# ----------------------------
gsk_brands = {"Shingrix":"https://example.com/shingrix-leaflet",
              "Trelegy":"https://example.com/trelegy-leaflet",
              "Zejula":"https://example.com/zejula-leaflet"}
gsk_brands_images = {"Shingrix":"https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
                     "Trelegy":"https://www.example.com/trelegy.png",
                     "Zejula":"https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png"}

race_segments = [
    "R – Reach: Did not start to prescribe yet and don't believe vaccination is their responsibility.",
    "A – Acquisition: Prescribe to patient who initiates discussion but convinced about data.",
    "C – Conversion: Proactively initiate discussion with specific patient profile.",
    "E – Engagement: Proactively prescribe to different patient profiles"
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
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
gsk_approaches = ["Use data-driven evidence","Focus on patient outcomes","Leverage storytelling techniques"]
sales_call_flow = ["Prepare","Engage","Create Opportunities","Influence","Drive Impact","Post Call Analysis"]

# ----------------------------
# Sidebar filters
# ----------------------------
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand / اختر العلامة التجارية", list(gsk_brands.keys()))
segment = st.sidebar.selectbox("Select RACE Segment / اختر شريحة RACE", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", doctor_barriers)
objective = st.sidebar.selectbox("Select Objective / اختر الهدف", objectives)
specialty = st.sidebar.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", specialties)
persona = st.sidebar.selectbox("Select HCP Persona / اختر شخصية الطبيب", personas)
response_length = st.sidebar.selectbox("Response Length / اختر طول الرد", ["Short","Medium","Long"])
response_tone = st.sidebar.selectbox("Response Tone / اختر نبرة الرد", ["Formal","Casual","Friendly","Persuasive"])
interface_mode = st.sidebar.radio("Interface Mode / اختر واجهة", ["Chatbot","Card Dashboard","Flow Visualization"])

# ----------------------------
# PDF upload & reference
# ----------------------------
uploaded_pdf = st.file_uploader("Upload PDF for AI reference / تحميل PDF للرجوع إليه", type="pdf")
show_more_toggle = st.checkbox("Show full PDF text / عرض النص الكامل للـ PDF", value=False)
if uploaded_pdf:
    pdf_text=""
    with pdfplumber.open(uploaded_pdf) as pdf:
        for page in pdf.pages:
            pdf_text += page.extract_text() or ""
    st.session_state.uploaded_pdf_text = pdf_text if show_more_toggle else pdf_text[:1000]+"..."
    matches = re.findall(r"(?:CDC|FDA|Guideline|Study|202\d)[^.\n]*", pdf_text, flags=re.I)
    st.session_state.extracted_medical_ref = ", ".join(matches) if matches else ""
    st.markdown(f"**PDF Preview:** {st.session_state.uploaded_pdf_text}")
    if st.session_state.extracted_medical_ref:
        st.info(f"📄 Extracted Medical Reference(s): {st.session_state.extracted_medical_ref}")

# ----------------------------
# Brand image
# ----------------------------
try:
    img_url = gsk_brands_images.get(brand)
    if img_url.startswith("http"):
        img = Image.open(BytesIO(requests.get(img_url).content))
        st.image(img,width=200)
except:
    st.image("https://via.placeholder.com/200x100.png?text=No+Image",width=200)

# ----------------------------
# Clear chat
# ----------------------------
if st.button("🗑️ Clear Chat / مسح المحادثة"):
    st.session_state.chat_history=[]

# ----------------
