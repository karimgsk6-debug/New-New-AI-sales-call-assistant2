import os
import io
import re
import streamlit as st
from PIL import Image
from docx import Document
import pdfplumber
from pptx import Presentation
from gtts import gTTS
from groq import Groq
from datetime import datetime

# ----------------------------
# App Configuration
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ----------------------------
# Groq API Setup
# ----------------------------
GROQ_API_KEY = "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"  # Replace with your key
client = Groq(api_key=GROQ_API_KEY)

# ----------------------------
# Helper Functions
# ----------------------------
def extract_text_from_docx(file):
    doc = Document(file)
    return "\n".join([p.text for p in doc.paragraphs])

def extract_text_from_pdf(file):
    text = ""
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text += page.extract_text() or ""
    return text

def extract_text_from_pptx(file):
    prs = Presentation(file)
    text_runs = []
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text_runs.append(shape.text)
    return "\n".join(text_runs)

def generate_tts(text):
    try:
        tts = gTTS(text=text, lang="en")
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception:
        return None

def remove_emojis_for_tts(text):
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002700-\U000027BF"  # dingbats
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U00002600-\U000026FF"  # miscellaneous symbols
        "\U00002B00-\U00002BFF"  # arrows
        "\U00002300-\U000023FF"  # miscellaneous technical
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub(r'', text)

def ask_ai(prompt):
    prompt += "\nRespond in a lively, engaging style with emojis when appropriate."
    try:
        response = client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role": "system", "content": "You are a fun, helpful AI medical sales assistant."},
                      {"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=1000
        )
    except Exception:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": "You are a fun, helpful AI medical sales assistant."},
                      {"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=1000
        )
    return response.choices[0].message.content

# ----------------------------
# Session State
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = ""
if "last_audio" not in st.session_state:
    st.session_state.last_audio = None

# ----------------------------
# Language
# ----------------------------
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])

# ----------------------------
# GSK Logo
# ----------------------------
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

# ----------------------------
# Filters
# ----------------------------
st.sidebar.header("Filters & Options")
gsk_brands = ["Shingrix", "Trelegy", "Zejula"]
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
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
response_lengths = ["Short", "Medium", "Long"]
response_tones = ["Formal", "Casual", "Friendly", "Persuasive"]
interface_modes = ["Chatbot", "Card Dashboard", "Flow Visualization"]

brand = st.sidebar.selectbox("Select Brand / اختر العلامة التجارية", gsk_brands)
segment = st.sidebar.selectbox("Select RACE Segment / اختر شريحة RACE", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", doctor_barriers)
objective = st.sidebar.selectbox("Select Objective / اختر الهدف", objectives)
specialty = st.sidebar.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", specialties)
persona = st.sidebar.selectbox("Select HCP Persona / اختر شخصية الطبيب", personas)
response_length = st.sidebar.selectbox("Response Length / اختر طول الرد", response_lengths)
response_tone = st.sidebar.selectbox("Response Tone / اختر نبرة الرد", response_tones)
interface_mode = st.sidebar.radio("Interface Mode / اختر واجهة", interface_modes)

# ----------------------------
# Upload Documents
# ----------------------------
st.subheader("📤 Upload Supporting Documents")
uploaded_file = st.file_uploader("Upload PDF, DOCX, or PPTX", type=["pdf", "docx", "pptx"])
if uploaded_file:
    file_ext = uploaded_file.name.split(".")[-1].lower()
    extracted_text = ""

    if file_ext == "docx":
        extracted_text = extract_text_from_docx(uploaded_file)
    elif file_ext == "pdf":
        extracted_text = extract_text_from_pdf(uploaded_file)
    elif file_ext == "pptx":
        extracted_text = extract_text_from_pptx(uploaded_file)

    st.session_state.uploaded_docs = extracted_text[:8000]

    if extracted_text:
        st.subheader("📄 Extracted Text")
        st.write(extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else ""))

# ----------------------------
# Clear Chat Button
# ----------------------------
if st.button("🧹 Clear Chat"):
    st.session_state.chat_history = []
    st.session_state.last_audio = None

# ----------------------------
# Display Chat with Robotic Avatars & Auto-scroll
# ----------------------------
st.subheader("💬 Chat with AI")
chat_placeholder = st.empty()

def display_chat():
    chat_html = "<div id='chat_container' style='max-height:500px; overflow-y:auto; padding:5px;'>"
    for msg in st.session_state.chat_history:
        time = msg.get("time", "")
        content = msg["content"].replace('\n', '<br>')
        if msg["role"] == "user":
            chat_html += f"""
            <div style='display:flex; justify-content:flex-end; align-items:flex-end; margin-bottom:5px;'>
                <div style='background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; max-width:70%'>{content}<br>
                <span style='font-size:10px; color:gray;'>{time}</span></div>
                <div style='font-size:35px; margin-left:5px;'>🚹</div>
            </div>"""
        else:
            chat_html += f"""
            <div style='display:flex; justify-content:flex-start; align-items:flex-start; margin-bottom:5px;'>
                <div style='font-size:35px; margin-right:5px;'>🤖</div>
                <div style='background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; max-width:70%'>{content}<br>
                <span style='font-size:10px; color:gray;'>{time}</span></div>
            </div>"""
    chat_html += "</div>"
    # Auto-scroll
    chat_html += """
    <script>
    var chatContainer = document.getElementById('chat_container');
    if (chatContainer) { chatContainer.scrollTop = chatContainer.scrollHeight; }
    </script>
    """
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# ----------------------------
# Fixed Bottom Input Box with Voice Bar Above and Send Icon
# ----------------------------
if st.session_state.last_audio:
    st.audio(st.session_state.last_audio, format="audio/mp3")

with st.form("chat_form", clear_on_submit=True):
    col1, col2 = st.columns([8,1])
    with col1:
        user_input = st.text_input(
            "Type your message...", 
            key="user_input_box", 
            placeholder="Type your message ▶️"
        )
    with col2:
        submitted = st.form_submit_button("▶️")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})

    # References & GSK Sales Call + APCT technique
    references = (
        "1. CDC Shingrix Recommendations: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html\n"
        "2. CDC Clinical Overview of Shingles: https://www.cdc.gov/shingles/hcp/clinical-overview/index.html\n"
        "3. WHO Vaccine Overview: https://www.who.int/news-room/fact-sheets/detail/shingles"
    )

    prompt = f"""
Language: {language}
User input: {user_input}
Brand: {brand}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Uploaded Docs Context: {st.session_state.uploaded_docs}
References:
{references}

Use the GSK Sales Call Module structure and APCT technique (Acknowledge, Probe, Challenge, Takeaway) for handling objections.
Respond professionally, concisely, and in a lively style with emojis for the chat display.
"""
    ai_output = ask_ai(prompt)
    st.session_state.chat_history.append({"role": "ai", "content": ai_output, "time": datetime.now().strftime("%H:%M")})

    # Generate AI voice without emojis
    voice_text = remove_emojis_for_tts(ai_output)
    audio_fp = generate_tts(voice_text)
    if audio_fp:
        st.session_state.last_audio = audio_fp

    display_chat()

# ----------------------------
# Download as Word
# ----------------------------
if st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io.BytesIO()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")
