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
import os

# ----------------------------
# PAGE CONFIG
# ----------------------------
st.set_page_config(
    page_title="AI Sales Call Assistant",
    page_icon="💡",
    layout="wide"
)

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
# GROQ client (replace with your key if needed)
# ----------------------------
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

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
# Background image (girl on right)
# ----------------------------
BACKGROUND_URL = "https://sdmntprnortheu.oaiusercontent.com/files/00000000-7268-61f4-9aa6-71a39056c20e/raw?se=2025-09-25T15%3A15%3A06Z&sp=r&sv=2024-08-04&sr=b&scid=6870570a-c416-5cac-816d-8f43608d4723&skoid=b32d65cd-c8f1-46fb-90df-c208671889d4&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-25T03%3A34%3A38Z&ske=2025-09-26T03%3A34%3A38Z&sks=b&skv=2024-08-04&sig=zeUa/UVyTIdgz6/Qm5s/D47aOZrYQj/LJX9T60q%2BXBw%3D"

def get_brightness(url):
    try:
        r = requests.get(url, timeout=10)
        img = Image.open(BytesIO(r.content)).convert("L")
        stat = ImageStat.Stat(img)
        return stat.mean[0]
    except Exception:
        return 255

brightness = get_brightness(BACKGROUND_URL)
text_color = "black" if brightness > 130 else "white"
button_bg = "#FFA500" if brightness > 130 else "#FF8C00"

st.markdown(f"""
<style>
/* background image */
.stApp {{
    background: url("{BACKGROUND_URL}") no-repeat right top fixed;
    background-size: contain;
}}

/* top-right fixed GSK logo (3 cm down ~60px) */
.gsk-logo {{
    position: fixed;
    top: 60px;   /* ~3 cm below Streamlit bar */
    right: 16px;
    z-index: 1000;
}}

/* enlarged, weighted title box centered */
.title-box {{
    background: rgba(255,255,255,0.90);
    padding: 35px;
    border-radius: 18px;
    text-align: center;
    max-width: 80%;
    margin: 12px auto;
}}
.title-box h1 {{
    margin: 0;
    font-size: 42px;
    font-weight: 800;
}}
.title-box p {{
    margin: 8px 0 0 0;
    font-size: 20px;
    font-weight: 500;
}}

/* disclaimer centered and prominent */
.disclaimer {{
    text-align: center;
    padding: 12px;
    font-size: 15px;
    font-weight: 500;
    margin-bottom: 10px;
}}

/* chat bubbles */
.chat-bubble-user {{
    text-align: right;
    background: rgba(220,248,198,0.95);
    padding: 12px;
    border-radius: 15px 15px 0px 15px;
    margin: 6px;
    display: inline-block;
    max-width: 80%;
    color: {text_color};
}}
.chat-bubble-ai {{
    text-align: left;
    background: rgba(240,242,246,0.95);
    padding: 12px;
    border-radius: 15px 15px 15px 0px;
    margin: 6px;
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
    padding:12px;
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
/* sidebar bold header */
.sidebar-bold {{
    background: rgba(255,255,255,0.85);
    padding: 10px;
    border-radius: 8px;
    font-weight:700;
    margin-bottom:8px;
}}
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Top fixed GSK logo (image)
# ----------------------------
GSK_LOGO_URL = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
st.markdown(f"""
<div class="gsk-logo">
    <img src="{GSK_LOGO_URL}" width="140" style="display:block;">
</div>
""", unsafe_allow_html=True)

# ----------------------------
# Title box & disclaimer (kept centered & enlarged)
# ----------------------------
st.markdown("""
<div class="title-box">
    <h1>💡 AI Sales Call Assistant</h1>
    <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
</div>
""", unsafe_allow_html=True)

st.markdown('<p class="disclaimer">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Brand & metadata (updated URLs + images)
# ----------------------------
gsk_brands = {
    "Shingrix": "https://www.shingrix.com/",
    "Trelegy": "https://www.trelegy.com/",
    "Zejula": "https://www.zejula.com/"
}
gsk_brands_images = {
    "Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Trelegy": "https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
    "Zejula": "https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png"
}

# ----------------------------
# Updated HCP segments, barriers, personas, call flow, APACT, approaches, specialties
# ----------------------------
race_segments = [
    "R – Reach: Not prescribing yet; doesn't see vaccination responsibility.",
    "A – Acquisition: Prescribes when patient asks; convinced by data.",
    "C – Conversion: Initiates for specific profiles; not across all profiles.",
    "E – Engagement: Proactively prescribes across multiple patient profiles."
]

doctor_barriers = [
    "HCP does not consider HZ a risk",
    "No time for discussion",
    "Cost concerns",
    "Not convinced of efficacy",
    "Accessibility/Logistics",
    "Patient reluctance",
    "Other clinical doubts"
]

personas = [
    "Uncommitted Vaccinator",
    "Reluctant Efficiency",
    "Patient Influenced",
    "Committed Vaccinator"
]

gsk_approaches = [
    "Use data-driven evidence (local + global studies)",
    "Focus on patient outcomes & QoL",
    "Leverage brief storytelling and peer endorsement",
    "Address practical barriers (access, scheduling, cost solutions)"
]

sales_call_flow = [
    "Prepare: Data + patient profiles",
    "Engage: Opening question & rapport",
    "Create Opportunities: Identify eligible patients",
    "Influence: Present tailored evidence & handle objections",
    "Drive Impact: Secure next steps (prescription/scheduling)",
    "Post Call Analysis: Document & follow up"
]

# APACT steps label kept for highlighting within replies
APACT_STEPS = ["Acknowledge", "Probing", "Action", "Confirm", "Transition"]

objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]

# ----------------------------
# Sidebar: expander with bold header and filters
# ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown('<div class="sidebar-bold">Filters & Options</div>', unsafe_allow_html=True)
    brand = st.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
    segment = st.selectbox("Select RACE Segment / اختر شريحة RACE", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective / اختر الهدف", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", options=specialties)
    persona = st.selectbox("Select HCP Persona / اختر شخصية الطبيب", options=personas)
    response_length = st.selectbox("Response Length / اختر طول الرد", ["Short", "Medium", "Long"])
    response_tone = st.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])
    language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])
    interface_mode = st.radio("Interface Mode / اختر واجهة", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# show brand image if available
image_path = gsk_brands_images.get(brand)
try:
    if image_path and image_path.startswith("http"):
        resp = requests.get(image_path, timeout=10)
        img = Image.open(BytesIO(resp.content))
        st.sidebar.image(img, width=200)
except Exception:
    st.sidebar.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)

# ----------------------------
# PDF Upload & medical reference extraction
# ----------------------------
uploaded_pdf = st.file_uploader("Upload PDF for AI reference / تحميل PDF للرجوع إليه", type="pdf")
show_more_toggle = st.checkbox("Show full PDF text / عرض النص الكامل للـ PDF", value=False)

if uploaded_pdf:
    pdf_text = ""
    with pdfplumber.open(uploaded_pdf) as pdf:
        for page in pdf.pages:
            pdf_text += page.extract_text() or ""
    st.session_state.uploaded_pdf_text = pdf_text if show_more_toggle else (pdf_text[:1000] + "...")
    # extract likely references: CDC, FDA, Guideline, Study, Journal, 20xx
    matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|202[0-9]|201[0-9]|Lancet|NEJM)[^.\n]*", pdf_text, flags=re.I)
    st.session_state.extracted_medical_ref = ", ".join(matches) if matches else ""
    st.markdown(f"**PDF Preview:** {st.session_state.uploaded_pdf_text}")
    if st.session_state.extracted_medical_ref:
        st.info(f"📄 Extracted Medical Reference(s): {st.session_state.extracted_medical_ref}")

# ----------------------------
# Clear chat button
# ----------------------------
if st.sidebar.button("🗑️ Clear Chat / مسح المحادثة"):
    st.session_state.chat_history = []

# ----------------------------
# Chat display area
# ----------------------------
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()

def display_chat():
    html = ""
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n", "<br>")
        # highlight APACT steps
        for step in APACT_STEPS:
            content = content.replace(step, f"<span class='highlight'>{step}</span>")
        timestamp = msg.get("time", "")
        if msg["role"] == "user":
            html += f"<div class='chat-bubble-user'>{content}<br><span style='font-size:10px;color:gray'>{timestamp}</span></div>"
        else:
            audio_html = ""
            if msg.get("audio"):
                audio_html = f"<br><audio controls style='margin-top:8px;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
            html += f"<div class='chat-bubble-ai'>{content}<br><span style='font-size:10px;color:gray'>{timestamp}</span>{audio_html}</div>"
    chat_placeholder.markdown(html, unsafe_allow_html=True)

display_chat()

# ----------------------------
# Chat input form
# ----------------------------
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message... / اكتب رسالتك هنا", key="user_input_box")
    submitted = st.form_submit_button("➤")

# ----------------------------
# TTS helper (sync wrapper using asyncio.run)
# ----------------------------
def synthesize_tts(text, lang):
    """
    Returns base64-encoded mp3 bytes of synthesized speech.
    lang: "English" or "العربية"
    """
    if not text or len(text.strip()) == 0:
        return None
    # choose voice
    if lang == "العربية":
        voice = "ar-EG-SalmaNeural"  # Arabic (Egypt) — adjust if you prefer other Arabic voices
    else:
        voice = "en-US-JennyNeural"
    filename = f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
    try:
        async def _save():
            communicate = edge_tts.Communicate(text, voice=voice)
            await communicate.save(filename)
        asyncio.run(_save())
        with open(filename, "rb") as f:
            audio_b = f.read()
        # cleanup file
        try:
            os.remove(filename)
        except Exception:
            pass
        return base64.b64encode(audio_b).decode("utf-8")
    except Exception as e:
        # If edge_tts fails, return None and continue gracefully
        st.error(f"⚠️ TTS error: {e}")
        return None

# ----------------------------
# Handle submitted input
# ----------------------------
if submitted and user_input.strip():
    # append user
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_input,
        "time": datetime.now().strftime("%H:%M")
    })

    # prepare prompt
    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)
    medical_ref_str = st.session_state.extracted_medical_ref or "None"

    prompt = f"""Language: {language}
User input: {user_input}
Brand: {brand}
RACE Segment: {segment}
Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Medical Reference: {medical_ref_str}

Approved Sales Approaches:
{approaches_str}

Sales Call Flow Steps:
{flow_str}

Use APACT (Acknowledge → Probing → Action → Confirm → Transition) technique for handling objections.
Response Length: {response_length}
Response Tone: {response_tone}
Provide actionable sales call suggestions and a short script (3–6 lines) the rep can say. Include the APACT steps clearly labeled.
"""

    # call Groq API (wrap in try/except)
    try:
        resp = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": f"You are a helpful sales assistant that responds in {language}."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        ai_output = resp.choices[0].message.content
    except Exception as e:
        ai_output = f"⚠️ Error generating response: {e}"

    # Generate TTS in selected language
    audio_b64 = synthesize_tts(ai_output, language)

    st.session_state.chat_history.append({
        "role": "ai",
        "content": ai_output,
        "time": datetime.now().strftime("%H:%M"),
        "audio": audio_b64
    })

    # display updated chat
    display_chat()

# ----------------------------
# Word download of latest AI response
# ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    latest_ai = [m["content"] for m in st.session_state.chat_history if m["role"] == "ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io_bytes()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")

# ----------------------------
# Brand leaflet link
# ----------------------------
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
