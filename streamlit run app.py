import streamlit as st
from PIL import Image
import requests
from io import BytesIO, BytesIO as io_bytes
import base64
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
client = Groq(api_key="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")  # 🔑 Insert your Groq API key here

# --- Background image ---
bg_url = "https://img.freepik.com/premium-photo/girl-with-phone-orange-background_868783-14060.jpg?w=360"
st.markdown(
    f"""
    <style>
    .stApp {{
        background: url("{bg_url}") no-repeat center center fixed;
        background-size: cover;
        color: white;
    }}
    .title-box {{
        background: rgba(0, 0, 0, 0.5);
        padding: 15px;
        border-radius: 12px;
        margin-bottom: 15px;
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
        color: black;
    }}
    .chat-bubble-ai {{
        text-align: left;
        background: rgba(240,242,246,0.7);
        padding: 10px;
        border-radius: 15px 15px 15px 0px;
        margin: 5px;
        display: inline-block;
        max-width: 80%;
        color: black;
    }}
    .highlight {{
        font-weight: bold;
        background-color: yellow;
        color: black;
        padding: 2px 4px;
        border-radius: 4px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Language ---
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])

# --- GSK Logo & Title ---
logo_local_path = "images/gsk_logo.png"
logo_fallback_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
col1, col2 = st.columns([1, 5])
with col1:
    try:
        logo_img = Image.open(logo_local_path)
        st.image(logo_img, width=120)
    except:
        st.image(logo_fallback_url, width=120)
with col2:
    st.markdown(
        "<div class='title-box'><h2>💡 AI Sales Call Assistant</h2>"
        "<p>Powered by AI to equip sales reps for smarter HCP conversations</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<p class='disclaimer'>⚠️ Disclaimer: For training and educational purposes only.</p>", unsafe_allow_html=True)

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

# --- Filters & options ---
race_segments = [
    "R – Reach: Did not start to prescribe yet and Don't believe vaccination is their responsibility.",
    "A – Acquisition: Prescribes when patient asks, but needs more conviction.",
    "C – Conversion: Proactively initiates discussion with some patients.",
    "E – Engagement: Proactively prescribes across patient profiles."
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
brand = st.sidebar.selectbox("Select Brand", options=list(gsk_brands.keys()))
segment = st.sidebar.selectbox("Select RACE Segment", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barrier", options=doctor_barriers, default=[])
objective = st.sidebar.selectbox("Select Objective", options=objectives)
specialty = st.sidebar.selectbox("Select Doctor Specialty", options=specialties)
persona = st.sidebar.selectbox("Select HCP Persona", options=personas)
response_length = st.sidebar.selectbox("Response Length", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])
interface_mode = st.sidebar.radio("Interface Mode", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# --- Display brand image ---
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
if st.button("🗑️ Clear Chat"):
    st.session_state.chat_history = []

# --- Chat history display ---
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()

def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time", "")
        content = msg["content"].replace('\n', '<br>')

        # Highlight APACT steps
        apact_steps = ["Acknowledge", "Probing", "Action", "Confirm", "Transition"]
        for step in apact_steps:
            content = content.replace(step, f"<span class='highlight'>{step}</span>")

        if msg["role"] == "user":
            chat_html += f"<div class='chat-bubble-user'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>"
        else:
            chat_html += f"<div class='chat-bubble-ai'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span>"

            # Add voice playback for AI response
            if "audio" in msg:
                chat_html += f"<br><audio controls style='margin-top:5px;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"

            chat_html += "</div>"

    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# --- Chat input form ---
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    submitted = st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})
    
    # --- AI prompt ---
    prompt = f"""
Language: {language}
User input: {user_input}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Brand: {brand}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Sales Call Flow: {' → '.join(sales_call_flow)}
Use APACT (Acknowledge → Probing → Action → Confirm → Transition) technique.
Response Length: {response_length}
Response Tone: {response_tone}
Provide actionable suggestions tailored to this persona in a professional manner.
"""

    # --- Groq API call ---
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role": "system", "content": f"You are a helpful AI sales assistant that responds in {language}."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    ai_output = response.choices[0].message.content

    # --- Voice synthesis ---
    try:
        tts_response = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=ai_output
        )
        audio_bytes = tts_response.read()
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
    except Exception:
        audio_base64 = None

    st.session_state.chat_history.append({
        "role": "ai",
        "content": ai_output,
        "time": datetime.now().strftime("%H:%M"),
        "audio": audio_base64
    })

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

# --- Brand leaflet ---
st.markdown(f"[📑 Brand Leaflet - {brand}]({gsk_brands[brand]})")
