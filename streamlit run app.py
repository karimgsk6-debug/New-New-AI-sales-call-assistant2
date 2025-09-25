import streamlit as st
from PIL import Image
import requests
from io import BytesIO, BytesIO as io_bytes
import asyncio
import edge_tts
import tempfile
import os
from datetime import datetime
from groq import Groq

# --- Optional dependency for Word download ---
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# --- Initialize Groq client ---
client = Groq(api_key="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")  # Insert Groq API key

# --- Session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Background Image (CSS injection) ---
background_url = https://img.freepik.com/free-photo/excited-smiling-woman-holding-digital-tablet-staring-amazed-camera-after-seeing-cool-offer-online_1258-118808.jpg?semt=ais_hybrid&w=740&q=80"
page_bg_css = f"""
<style>
.stApp {{
    background: url("{background_url}") no-repeat center center fixed;
    background-size: cover;
}}
.main > div {{
    background-color: rgba(0,0,0,0.55);
    padding: 20px;
    border-radius: 12px;
}}
section[data-testid="stSidebar"] {{
    background-color: rgba(255,255,255,0.95);
}}
.disclaimer {{
    font-size: 14px;
    color: black;
    background-color: rgba(255,255,255,0.8);
    padding: 8px;
    border-radius: 6px;
}}
</style>
"""
st.markdown(page_bg_css, unsafe_allow_html=True)

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
    st.markdown('<div class="disclaimer">💡 Powered by AI to equip sales reps for smarter HCP conversations</div>', unsafe_allow_html=True)

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

# --- Summarize medical references ---
st.sidebar.subheader("📚 Medical References")
summarize_refs = st.sidebar.checkbox("Summarize uploaded medical references")
uploaded_refs = st.sidebar.file_uploader("Upload Medical References (PDF/DOCX/PPTX)", type=["pdf", "docx", "pptx"], accept_multiple_files=True)

references_summary = ""
if summarize_refs and uploaded_refs:
    references_summary = "Medical references uploaded:\n"
    for file in uploaded_refs:
        references_summary += f"- {file.name}\n"
    references_summary += "\nSummarize key points for use in HCP discussions."

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
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()

def display_chat():
    chat_html = ""
    for idx, msg in enumerate(st.session_state.chat_history):
        time = msg.get("time", "")
        content = msg["content"].replace('\n', '<br>')

        # Highlight APACT steps
        apact_steps = ["Acknowledge", "Probing", "Action", "Confirm", "Transition"]
        for step in apact_steps:
            content = content.replace(step, f"<span style='background-color:yellow; font-weight:bold;'>{step}</span>")

        if msg["role"] == "user":
            chat_html += f"""
            <div style='text-align:right; background:rgba(220,248,198,0.9); padding:10px; border-radius:15px 15px 0px 15px; margin:5px; display:inline-block; max-width:80%;'>
                {content}<span style='font-size:10px; color:gray;'><br>{time}</span>
            </div>
            """
        else:
            chat_html += f"""
            <div style='text-align:left; background:rgba(240,242,246,0.9); padding:10px; border-radius:15px 15px 15px 0px; margin:5px; display:inline-block; max-width:80%;'>
                {content}<span style='font-size:10px; color:gray;'><br>{time}</span>
            </div>
            """
            # Add voice playback if TTS exists
            if "audio" in msg:
                audio_file = msg["audio"]
                audio_html = f"""
                <audio controls style="margin-top:5px;">
                    <source src="data:audio/mp3;base64,{audio_file}" type="audio/mp3">
                </audio>
                """
                chat_html += audio_html

    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# --- Chat input ---
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    submitted = st.form_submit_button("➤")

async def generate_tts(text):
    communicate = edge_tts.Communicate(text, voice="en-US-AriaNeural")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
        await communicate.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            audio_bytes = f.read()
        os.remove(tmp_file.name)
        return audio_bytes

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})

    # --- Prepare AI prompt ---
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
Use APACT (Acknowledge → Probing → Action → Confirm → Transition) technique for handling objections.
Response Length: {response_length}
Response Tone: {response_tone}
{references_summary}
Provide actionable suggestions tailored to this persona in a friendly and professional manner.
"""

    # --- Call Groq API ---
    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": f"You are a helpful sales assistant chatbot that responds in {language}."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        ai_output = response.choices[0].message.content
    except Exception as e:
        ai_output = f"⚠️ Groq API error: {e}"

    # --- Generate voice ---
    audio_bytes = asyncio.run(generate_tts(ai_output))
    import base64
    audio_b64 = base64.b64encode(audio_bytes).decode()

    st.session_state.chat_history.append({"role": "ai", "content": ai_output, "time": datetime.now().strftime("%H:%M"), "audio": audio_b64})
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
st.markdown(f"[📄 Brand Leaflet - {brand}]({gsk_brands[brand]})")
