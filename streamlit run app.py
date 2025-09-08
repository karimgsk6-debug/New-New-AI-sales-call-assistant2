import streamlit as st
from PIL import Image
import requests
from io import BytesIO, BytesIO as io_bytes
from gtts import gTTS
import os
from datetime import datetime
from docx import Document
from groq import Groq

# --- Initialize Groq client ---
client = Groq(api_key="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")  # Replace with your Groq API key

# --- Session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Language selection ---
language = st.radio("Select Language", options=["English", "العربية"])

# --- GSK Logo ---
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

# --- Sidebar filters ---
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand", options=list(gsk_brands.keys()))
segment = st.sidebar.selectbox("Select RACE Segment", options=["R", "A", "C", "E"])
barrier = st.sidebar.multiselect("Select Doctor Barrier", options=["Barrier 1", "Barrier 2"], default=[])
objective = st.sidebar.selectbox("Select Objective", options=["Awareness", "Adoption", "Retention"])
specialty = st.sidebar.selectbox("Select Doctor Specialty", options=["GP", "Cardiologist", "Dermatologist"])
persona = st.sidebar.selectbox("Select HCP Persona", options=["Persona 1", "Persona 2"])
response_length = st.sidebar.selectbox("Response Length", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])

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
        if msg["role"] == "user":
            chat_html += f"""
            <div style='text-align:right; background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; margin:5px; display:inline-block; max-width:80%;'>
                {content}<span style='font-size:10px; color:gray;'><br>{time}</span>
            </div>
            """
        else:
            chat_html += f"""
            <div style='text-align:left; background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; margin:5px; display:inline-block; max-width:80%;'>
                {content}<span style='font-size:10px; color:gray;'><br>{time}</span>
            </div>
            """
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# --- Chat input ---
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...")
    submitted = st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})
    
    # --- Prepare AI prompt ---
    prompt = f"""
    Language: {language}
    User input: {user_input}
    RACE Segment: {segment}
    Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
    Objective: {objective}
    Brand: {brand}
    Doctor Specialty: {specialty}
    HCP Persona: {persona}
    Response Length: {response_length}
    Response Tone: {response_tone}
    """

    # --- Call Groq API ---
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

    # --- Generate AI voice ---
    tts = gTTS(ai_output, lang='en')
    audio_path = "response.mp3"
    tts.save(audio_path)
    st.audio(audio_path, format='audio/mp3')

    # --- Word download ---
    doc = Document()
    doc.add_heading("AI Sales Call Response", 0)
    doc.add_paragraph(ai_output)
    word_buffer = io_bytes()
    doc.save(word_buffer)
    st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")

# --- Brand leaflet ---
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
