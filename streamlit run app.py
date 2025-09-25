import streamlit as st
from PIL import Image
import requests
from io import BytesIO, BytesIO as io_bytes
import groq
from groq import Groq
from datetime import datetime

# --- Optional dependency for Word download ---
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# --- Initialize Groq client ---
client = Groq(api_key="YOUR_API_KEY")  # Replace with your Groq API key

# --- Session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ----------------------------
# GSK Logo + Title + Disclaimer
# ----------------------------
logo_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"

st.markdown(f"""
<style>
.gsk-logo {{
    position: fixed;
    top: 60px;   /* 3 cm down */
    right: 20px;
    z-index: 1000;
}}
.title-box {{
    background: rgba(255,255,255,0.85);
    padding: 35px;
    border-radius: 18px;
    text-align: center;
    max-width: 75%;
    margin: 20px auto;
}}
.title-box h1 {{
    margin: 0;
    font-size: 42px;
    font-weight: 700;
}}
.title-box p {{
    margin: 8px 0 0 0;
    font-size: 22px;
}}
.disclaimer {{
    text-align: center;
    padding: 14px;
    font-size: 16px;
    font-weight: 500;
}}
</style>

<div class="gsk-logo">
    <img src="{logo_url}" width="140">
</div>

<div class="title-box">
    <h1>💡 AI Sales Call Assistant</h1>
    <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
</div>

<p class="disclaimer">⚠️ Disclaimer: For training and educational purposes only.</p>
""", unsafe_allow_html=True)

# ----------------------------
# Language Selector (Top-Left of Interface)
# ----------------------------
st.markdown("""
<style>
.language-selector {
    position: fixed;
    top: 70px;
    left: 25px;
    z-index: 1000;
    background: rgba(255,255,255,0.9);
    padding: 8px 15px;
    border-radius: 8px;
    font-weight: 600;
    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
}
</style>
""", unsafe_allow_html=True)

with st.container():
    st.markdown('<div class="language-selector">🌐 Language</div>', unsafe_allow_html=True)
    language = st.radio("", options=["English", "العربية"], horizontal=True, label_visibility="collapsed")

# ----------------------------
# Data: Brands, Segments, Barriers, Personas, Call Flow
# ----------------------------
gsk_brands = {
    "Shingrix": "https://www.gsk.com/en-gb/media/resource-centre/shingrix-leaflet",
    "Trelegy": "https://www.gsk.com/en-gb/media/resource-centre/trelegy-leaflet",
    "Zejula": "https://www.gsk.com/en-gb/media/resource-centre/zejula-leaflet",
}

gsk_brands_images = {
    "Trelegy": "https://www.example.com/trelegy.png",
    "Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Zejula": "https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png",
}

race_segments = [
    "R – Reach: Has not prescribed yet, doesn’t see vaccination as responsibility.",
    "A – Acquisition: Responds if patient initiates, somewhat convinced by data.",
    "C – Conversion: Proactively discusses with specific profiles, not all.",
    "E – Engagement: Proactively prescribes across diverse profiles.",
]

doctor_barriers = [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ Vx effective",
    "Accessibility issues",
]

objectives = ["Awareness", "Adoption", "Retention"]

specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]

personas = [
    "Uncommitted Vaccinator",
    "Reluctant Efficiency",
    "Patient Influenced",
    "Committed Vaccinator",
]

gsk_approaches = [
    "Use clinical evidence tailored to persona",
    "Highlight patient outcomes & case studies",
    "Leverage storytelling to build trust",
]

sales_call_flow = [
    "Prepare",
    "Engage",
    "Create Opportunities",
    "Influence",
    "Drive Impact",
    "Post Call Analysis",
]

# ----------------------------
# Sidebar Filters
# ----------------------------
st.sidebar.header("Filters & Options")

brand = st.sidebar.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))

# Brand image under brand selector
image_path = gsk_brands_images.get(brand)
try:
    if image_path.startswith("http"):
        response = requests.get(image_path)
        img = Image.open(BytesIO(response.content))
    else:
        img = Image.open(image_path)
    st.sidebar.image(img, width=200)
except:
    st.sidebar.warning(f"⚠️ Could not load image for {brand}. Using placeholder.")
    st.sidebar.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)

segment = st.sidebar.selectbox("Select RACE Segment / اختر شريحة RACE", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", options=doctor_barriers, default=[])
objective = st.sidebar.selectbox("Select Objective / اختر الهدف", options=objectives)
specialty = st.sidebar.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", options=specialties)
persona = st.sidebar.selectbox("Select HCP Persona / اختر شخصية الطبيب", options=personas)
response_length = st.sidebar.selectbox("Response Length / اختر طول الرد", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])
interface_mode = st.sidebar.radio("Interface Mode / اختر واجهة", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# ----------------------------
# Chat Display
# ----------------------------
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
            <div style='text-align:right; background:#dcf8c6; padding:10px;
                        border-radius:15px 15px 0px 15px; margin:5px;
                        display:inline-block; max-width:80%;'>
                {content}<span style='font-size:10px; color:gray;'><br>{time}</span>
            </div>
            """
        else:
            chat_html += f"""
            <div style='text-align:left; background:#f0f2f6; padding:10px;
                        border-radius:15px 15px 15px 0px; margin:5px;
                        display:inline-block; max-width:80%;'>
                {content}<span style='font-size:10px; color:gray;'><br>{time}</span>
            </div>
            """
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# ----------------------------
# Chat Input
# ----------------------------
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    submitted = st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})

    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)

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
Use APACT (Acknowledge → Probing → Answer → Confirm → Transition) technique for handling objections.
Response Length: {response_length}
Response Tone: {response_tone}
Provide actionable suggestions tailored to this persona in a friendly and professional manner.
"""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role": "system", "content": f"You are a helpful sales assistant chatbot that responds in {language}."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    ai_output = response.choices[0].message.content
    st.session_state.chat_history.append({"role": "ai", "content": ai_output, "time": datetime.now().strftime("%H:%M")})
    display_chat()

# ----------------------------
# Clear Chat Button (Bottom-Left Fixed)
# ----------------------------
st.markdown("""
<style>
.clear-chat {
    position: fixed;
    bottom: 25px;
    left: 25px;
    z-index: 1000;
}
</style>
""", unsafe_allow_html=True)

if st.button("🗑️ Clear Chat / مسح المحادثة", key="clear_chat_button"):
    st.session_state.chat_history = []
    display_chat()

# ----------------------------
# Word Download
# ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"] == "ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io_bytes()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")

# ----------------------------
# Brand Leaflet
# ----------------------------
st.markdown(f"[📄 Brand Leaflet - {brand}]({gsk_brands[brand]})")
