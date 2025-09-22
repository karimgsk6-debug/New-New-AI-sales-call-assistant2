"""
AI Sales Call Assistant – Streamlit‑Cloud ready
Author:  GSK Digital Solutions
Date:    2025‑09‑22
"""

import os
import io
import re
from datetime import datetime

import streamlit as st
from PIL import Image
from docx import Document
from gtts import gTTS
from groq import Groq
from PyPDF2 import PdfReader

# --------------------------------------------------------------------------- #
# 1. APP CONFIGURATION
# --------------------------------------------------------------------------- #
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# --------------------------------------------------------------------------- #
# 2. ENVIRONMENT / API KEYS
# --------------------------------------------------------------------------- #
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    st.error("❌ GROQ_API_KEY not found. Add it as an environment secret.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

# --------------------------------------------------------------------------- #
# 3. HELPER FUNCTIONS
# --------------------------------------------------------------------------- #
def extract_text_from_docx(file):
    """Return all paragraph text from a DOCX file."""
    doc = Document(file)
    return "\n".join(p.text for p in doc.paragraphs)

def extract_text_from_pdf(file):
    """Return extracted text from a PDF file."""
    reader = PdfReader(file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

def generate_tts(text, lang="en"):
    """Return an in‑memory MP3 file created by gTTS."""
    try:
        tts = gTTS(text=text, lang=lang)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp
    except Exception as exc:
        st.warning(f"⚠️ TTS error: {exc}")
        return None

def remove_emojis_for_tts(text):
    """Strip all emoji characters from a string."""
    emoji_pattern = re.compile(
        "[" 
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002700-\U000027BF"
        "\U0001F900-\U0001F9FF"
        "\U00002600-\U000026FF"
        "\U00002B00-\U00002BFF"
        "\U00002300-\U000023FF"
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub("", text)

def ask_ai(prompt: str) -> str:
    """
    Wrapper for the Groq chat model.
    Tries the large model first, then falls back to the 8B variant.
    """
    prompt += "\nRespond in a lively, engaging style with emojis when appropriate."
    model = "llama-3.1-70b-versatile"
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a fun, helpful AI medical sales assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=1000
            )
            return response.choices[0].message.content
        except Exception:
            if attempt == 0:
                model = "llama-3.1-8b-instant"
            else:
                raise
    raise RuntimeError("Unable to get a response from Groq")

# --------------------------------------------------------------------------- #
# 4. SESSION STATE
# --------------------------------------------------------------------------- #
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "uploaded_docs" not in st.session_state:
    st.session_state.uploaded_docs = ""

if "last_audio" not in st.session_state:
    st.session_state.last_audio = None

# --------------------------------------------------------------------------- #
# 5. LANGUAGE SELECTION
# --------------------------------------------------------------------------- #
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])

# --------------------------------------------------------------------------- #
# 6. GSK LOGO
# --------------------------------------------------------------------------- #
logo_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
col_logo, col_title = st.columns([1, 5])
with col_logo:
    try:
        logo_img = Image.open("images/gsk_logo.png")
        st.image(logo_img, width=120)
    except Exception:
        st.image(logo_url, width=120)
with col_title:
    st.title("🧠 AI Sales Call Assistant")

# --------------------------------------------------------------------------- #
# 7. SIDEBAR FILTERS
# --------------------------------------------------------------------------- #
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

# --------------------------------------------------------------------------- #
# 8. DOCUMENT UPLOAD
# --------------------------------------------------------------------------- #
st.subheader("📤 Upload Supporting Documents")
uploaded_file = st.file_uploader("Upload PDF or DOCX", type=["pdf", "docx"])

if uploaded_file:
    file_ext = uploaded_file.name.split(".")[-1].lower()
    extracted_text = ""

    if file_ext == "docx":
        extracted_text = extract_text_from_docx(uploaded_file)
    elif file_ext == "pdf":
        extracted_text = extract_text_from_pdf(uploaded_file)

    # Trim to a reasonable chunk for the LLM
    st.session_state.uploaded_docs = extracted_text[:8000]

    if extracted_text:
        st.subheader("📄 Extracted Text")
        preview = extracted_text[:2000] + ("..." if len(extracted_text) > 2000 else "")
        st.write(preview)

# --------------------------------------------------------------------------- #
# 9. CLEAR CHAT BUTTON
# --------------------------------------------------------------------------- #
if st.button("🧹 Clear Chat"):
    st.session_state.chat_history = []
    st.session_state.last_audio = None

# --------------------------------------------------------------------------- #
# 10. CHAT DISPLAY
# --------------------------------------------------------------------------- #
chat_placeholder = st.empty()

def render_chat():
    chat_html = """
    <div id="chat_container" style="max-height:500px; overflow-y:auto; padding:5px;">
    """
    for msg in st.session_state.chat_history:
        time_stamp = msg.get("time", "")
        content = msg["content"].replace("\n", "<br>")
        if msg["role"] == "user":
            chat_html += f"""
            <div style="display:flex; justify-content:flex-end; align-items:flex-end; margin-bottom:5px;">
                <div style="background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; max-width:70%;">
                    {content}<br>
                    <span style="font-size:10px; color:gray;">{time_stamp} ✅✅</span>
                </div>
                <div style="font-size:35px; margin-left:5px;">🚹</div>
            </div>
            """
        else:
            chat_html += f"""
            <div style="display:flex; justify-content:flex-start; align-items:flex-start; margin-bottom:5px;">
                <div style="font-size:35px; margin-right:5px;">🤖</div>
                <div style="background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; max-width:70%;">
                    {content}<br>
                    <span style="font-size:10px; color:gray;">{time_stamp}</span>
                </div>
            </div>
            """
    chat_html += """
    </div>
    <script>
      const chat = document.getElementById('chat_container');
      if (chat) chat.scrollTop = chat.scrollHeight;
    </script>
    """
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

render_chat()

# --------------------------------------------------------------------------- #
# 11. AUDIO PLAYBACK (if available)
# --------------------------------------------------------------------------- #
if st.session_state.last_audio:
    st.audio(st.session_state.last_audio, format="audio/mp3")

# --------------------------------------------------------------------------- #
# 12. MESSAGE FORM
# --------------------------------------------------------------------------- #
with st.form("chat_form", clear_on_submit=True):
    col_msg, col_send = st.columns([8, 1])
    with col_msg:
        user_input = st.text_input("Type your message…", key="user_input_box", placeholder="Enter your question")
    with col_send:
        # Use a plain emoji button – no external image needed
        submitted = st.form_submit_button(label="📤", help="Send")

# --------------------------------------------------------------------------- #
# 13. PROCESS USER MESSAGE
# --------------------------------------------------------------------------- #
if submitted and user_input.strip():
    st.session_state.chat_history.append(
        {"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")}
    )

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

    Use the **GSK Sales Call Module**:
    1. Prepare (before the call)
    2. ENGAGE (build rapport)
    3. CREATE OPPORTUNITY
    4. INFLUENCE
    5. IMPACT / Good Sell Outcome
    6. Post-call Analysis

    Handle objections using **APACT**:
    - Acknowledge
    - Probe
    - Action
    - Confirm
    - Transition to next step or call

    Respond professionally, concisely, and in a lively style with emojis for chat display.
    """

    ai_output = ask_ai(prompt)

    st.session_state.chat_history.append(
        {"role": "ai", "content": ai_output, "time": datetime.now().strftime("%H:%M")}
    )

    # Generate TTS (trim to 2k chars to avoid gTTS errors)
    safe_text = remove_emojis_for_tts(ai_output)[:2000]
    audio_fp = generate_tts(safe_text)

    if audio_fp:
        st.session_state.last_audio = audio_fp

    render_chat()

# --------------------------------------------------------------------------- #
# 14. DOWNLOAD LATEST AI RESPONSE AS WORD
# --------------------------------------------------------------------------- #
if st.session_state.chat_history:
    latest_ai = [m["content"] for m in st.session_state.chat_history if m["role"] == "ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", level=0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io.BytesIO()
        doc.save(word_buffer)
        word_buffer.seek(0)

        st.download_button(
            label="📥 Download as Word (.docx)",
            data=word_buffer,
            file_name="AI_Response.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
