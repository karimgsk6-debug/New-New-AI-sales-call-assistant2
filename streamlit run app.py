import streamlit as st
from PIL import Image, ImageStat
import requests
from io import BytesIO, BytesIO as io_bytes
import base64
from datetime import datetime
import groq
from groq import Groq
import asyncio
import edge_tts
import pdfplumber

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
# Insert your GROQ API key here
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

# ----------------------------
# Background image
# ----------------------------
BACKGROUND_URL = "https://sdmntprwestcentralus.oaiusercontent.com/files/00000000-510c-61fb-baf7-7c52e905f7eb/raw?se=2025-09-25T14%3A50%3A09Z&sp=r&sv=2024-08-04&sr=b&scid=3004c229-41b0-506e-951b-c5fb40d53b65&skoid=0da8417a-a4c3-4a19-9b05-b82cee9d8868&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-24T17%3A20%3A38Z&ske=2025-09-25T17%3A20%3A38Z&sks=b&skv=2024-08-04&sig=sJpYsR4Hg1lJGrrkNSY291QTV3Rck16ZyDUI%2Btn9SV8%3D"

# Get average brightness for text/button color adjustment
def get_brightness(url):
    try:
        response = requests.get(url)
        img = Image.open(BytesIO(response.content)).convert("L")  # grayscale
        stat = ImageStat.Stat(img)
        return stat.mean[0]
    except:
        return 255  # default bright

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
    background: rgba(250,250,250,0.2);
    backdrop-filter: blur(5px);
    padding: 10px;
    border-radius: 12px;
    margin-bottom: 15px;
    color: White;
}}
.disclaimer {{
    font-size: 15px;
    color: black;
    background: rgba(250,250,250,0.2);
    padding: 5px;
    border-radius: 6px;
}}
.chat-bubble-user {{
    text-align: right;
    background: rgba(200,200,200,0.2);
    padding: 10px;
    border-radius: 15px 15px 0px 15px;
    margin: 5px;
    display: inline-block;
    max-width: 80%;
    color: {text_color};
}}
.chat-bubble-ai {{
    text-align: left;
    background: rgba(250,250,250,0.5);
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
# Sidebar - Filters
# ----------------------------
st.sidebar.header("Filters & Options")
brands = ["Shingrix","Trelegy","Zejula"]
brand = st.sidebar.selectbox("Brand", brands)
segments = ["R – Reach","A – Acquisition","C – Conversion","E – Engagement"]
segment = st.sidebar.selectbox("RACE Segment", segments)
barriers = ["HCP does not consider HZ as risk","No time","Cost","Not convinced","Accessibility"]
barrier = st.sidebar.multiselect("Doctor Barrier", options=barriers)
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist"]
specialty = st.sidebar.selectbox("Specialty", specialties)
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
persona = st.sidebar.selectbox("Persona", personas)
response_tone = st.sidebar.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"])
response_length = st.sidebar.selectbox("Response Length", ["Short","Medium","Long"])

# ----------------------------
# PDF Upload & Summarize
# ----------------------------
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type="pdf")
show_more_toggle = st.checkbox("Show full PDF text", value=False)

if uploaded_pdf:
    pdf_text = ""
    with pdfplumber.open(uploaded_pdf) as pdf:
        for page in pdf.pages:
            pdf_text += page.extract_text() or ""
    if not show_more_toggle:
        st.session_state.uploaded_pdf_text = pdf_text[:1000]+"..."  # truncate
    else:
        st.session_state.uploaded_pdf_text = pdf_text
    st.markdown(f"**PDF Preview:** {st.session_state.uploaded_pdf_text}")

# ----------------------------
# Chat display
# ----------------------------
chat_placeholder = st.empty()
def display_chat():
    html = ""
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n","<br>")
        for step in ["Acknowledge","Probing","Action","Confirm","Transition"]:
            content = content.replace(step, f"<span class='highlight'>{step}</span>")
        if msg["role"]=="user":
            html += f"<div class='chat-bubble-user'>{content}<br><span style='font-size:10px;color:gray'>{msg.get('time','')}</span></div>"
        else:
            html += f"<div class='chat-bubble-ai'>{content}<br><span style='font-size:10px;color:gray'>{msg.get('time','')}</span>"
            if "audio" in msg and msg["audio"]:
                html += f"<br><audio controls style='margin-top:5px;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
            html += "</div>"
    chat_placeholder.markdown(html, unsafe_allow_html=True)
display_chat()

# ----------------------------
# Chat input
# ----------------------------
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    submitted = st.form_submit_button("▶️")  # ChatGPT-style send

if submitted and user_input.strip():
    st.session_state.chat_history.append({
        "role":"user","content":user_input,
        "time": datetime.now().strftime("%H:%M")
    })

    pdf_context = st.session_state.uploaded_pdf_text or "No PDF uploaded."
    prompt = f"""
User input: {user_input}
Brand: {brand}
Segment: {segment}
Barriers: {', '.join(barrier) if barrier else 'None'}
Specialty: {specialty}
Persona: {persona}
PDF Reference: {pdf_context}
Use APACT (Acknowledge → Probing → Action → Confirm → Transition) for handling objections.
Response Tone: {response_tone}, Length: {response_length}.
"""

    # AI Response
    try:
        resp = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role":"system","content":"You are a helpful AI sales assistant."},
                      {"role":"user","content":prompt}],
            temperature=0.7
        )
        ai_output = resp.choices[0].message.content
    except Exception as e:
        ai_output = f"⚠️ Error generating response: {e}"

    # Voice support
    try:
        tts = edge_tts.Communicate(ai_output, voice="en-US-JennyNeural")
        filename = f"tts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        asyncio.run(tts.save(filename))
        audio_bytes = open(filename,"rb").read()
        audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
    except Exception:
        audio_base64 = None

    st.session_state.chat_history.append({
        "role":"ai","content":ai_output,
        "time": datetime.now().strftime("%H:%M"),
        "audio": audio_base64
    })
    display_chat()

# ----------------------------
# Word download
# ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    latest_ai = [m["content"] for m in st.session_state.chat_history if m["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response",0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io_bytes()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")
