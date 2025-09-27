import streamlit as st
from PIL import Image
import requests
from io import BytesIO, BytesIO as io_bytes
import PyPDF2
from gtts import gTTS
import base64
import os
from datetime import datetime
import groq
from groq import Groq

# --- Initialize Groq client ---
client = Groq(api_key="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")

# --- Session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Language selector (top-left corner) ---
col_lang, col_empty = st.columns([1, 8])
with col_lang:
    language = st.radio("🌐 Language", options=["English", "العربية"])

# --- GSK Logo (top-right corner, pushed down) ---
logo_local_path = "images/gsk_logo.png"
logo_fallback_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
st.markdown(
    """
    <style>
        [data-testid="stSidebar"] {
            background-color: #FF6600 !important; /* GSK Orange */
            background-size: cover;
        }
        .stApp {
            background: url("https://sdmntprsouthcentralus.oaiusercontent.com/files/00000000-a9b4-61f7-b2cf-05a782087038/raw?se=2025-09-27T15%3A35%3A52Z&sp=r&sv=2024-08-04&sr=b&scid=134c6041-1913-5d1b-9974-a2aba92201a7&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-27T05%3A09%3A07Z&ske=2025-09-28T05%3A09%3A07Z&sks=b&skv=2024-08-04&sig=7aQFm5RhZ9epNykQFKn7PqPerMyorga4a47YrmyCvo8%3D") no-repeat center center fixed;
            background-size: cover;
        }
        .logo-container {
            position: absolute;
            top: 60px;  /* push down 3 cm approx */
            right: 20px;
            z-index: 999;
        }
    </style>
    <div class="logo-container">
        <img src="https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png" width="120">
    </div>
    """,
    unsafe_allow_html=True
)

# --- Disclaimer fixed center ---
st.markdown("<h4 style='text-align:center; color:white;'>For Internal Training Use Only</h4>", unsafe_allow_html=True)

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

# --- Sidebar filters ---
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))

# Show brand image under brand name
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

segment = st.sidebar.selectbox("Select RACE Segment / اختر شريحة RACE", [
    "R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"
])
barrier = st.sidebar.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ Vx effective",
    "Accessibility issues"
], default=[])
objective = st.sidebar.selectbox("Select Objective / اختر الهدف", ["Awareness", "Adoption", "Retention"])
specialty = st.sidebar.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"])
persona = st.sidebar.selectbox("Select HCP Persona / اختر شخصية الطبيب", [
    "Uncommitted Vaccinator",
    "Reluctant Efficiency",
    "Patient Influenced",
    "Committed Vaccinator"
])
response_length = st.sidebar.selectbox("Response Length / اختر طول الرد", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])
interface_mode = st.sidebar.radio("Interface Mode / اختر واجهة", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# --- Clear chat button inside interface ---
if st.button("🗑️ Clear Chat / مسح المحادثة"):
    st.session_state.chat_history = []

# --- PDF Upload and Summarize ---
uploaded_pdf = st.file_uploader("📄 Upload PDF", type=["pdf"])
if uploaded_pdf is not None:
    pdf_reader = PyPDF2.PdfReader(uploaded_pdf)
    text_content = ""
    for page in pdf_reader.pages:
        text_content += page.extract_text() + "\n"

    if st.button("Summarize PDF"):
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "system", "content": "Summarize the following document."},
                      {"role": "user", "content": text_content}]
        )
        summary = response.choices[0].message.content
        st.write("### 📑 Summary:")
        st.write(summary)

# --- Chat interface ---
st.subheader("💬 Chatbot Interface")
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
            chat_html += f"<div style='text-align:right; background:#dcf8c6; padding:10px; border-radius:15px; margin:5px; display:inline-block; max-width:80%;'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>"
        else:
            chat_html += f"<div style='text-align:left; background:#f0f2f6; padding:10px; border-radius:15px; margin:5px; display:inline-block; max-width:80%;'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    submitted = st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})

    prompt = f"""
Language: {language}
User input: {user_input}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Brand: {brand}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Sales Call Flow Steps: Prepare → Engage → Create Opportunities → Influence → Drive Impact → Post Call Analysis
Use APACT (Acknowledge → Probing → Answer → Confirm → Transition) for objections.
Response Length: {response_length}
Response Tone: {response_tone}
"""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "system", "content": f"You are a helpful sales assistant chatbot that responds in {language}."},
                  {"role": "user", "content": prompt}],
        temperature=0.7
    )
    ai_output = response.choices[0].message.content

    st.session_state.chat_history.append({"role": "ai", "content": ai_output, "time": datetime.now().strftime("%H:%M")})

    # TTS playback (English + Arabic)
    tts = gTTS(ai_output, lang="ar" if language == "العربية" else "en")
    tts_path = "ai_response.mp3"
    tts.save(tts_path)
    with open(tts_path, "rb") as f:
        audio_bytes = f.read()
    b64 = base64.b64encode(audio_bytes).decode()
    st.markdown(f"""
        <audio autoplay controls>
        <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
    """, unsafe_allow_html=True)

    display_chat()

# --- Brand leaflet ---
st.markdown(f"[📖 Brand Leaflet - {brand}]({gsk_brands[brand]})")
