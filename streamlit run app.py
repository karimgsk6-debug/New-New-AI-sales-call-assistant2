import streamlit as st
from PIL import Image, ImageStat
import requests
from io import BytesIO, BytesIO as io_bytes
import groq
from groq import Groq
from datetime import datetime
import PyPDF2   # safer than fitz for Streamlit Cloud
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
# GROQ client
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
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""

# ----------------------------
# Background image
# ----------------------------
BACKGROUND_URL = "https://sdmntprnortheu.oaiusercontent.com/files/00000000-7268-61f4-9aa6-71a39056c20e/raw?se=2025-09-25T15%3A42%3A47Z&sp=r&sv=2024-08-04&sr=b&scid=dfa0d35f-01ac-5224-bec7-ff9f505758dd&skoid=b32d65cd-c8f1-46fb-90df-c208671889d4&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-25T09%3A41%3A15Z&ske=2025-09-26T09%3A41%3A15Z&sks=b&skv=2024-08-04&sig=ap%2BO7ty9YJurxH528T8cPoSQD5Kh6VHdsvf/nvdkbjs%3D"

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
/* background */
.stApp {{
    background: url("{BACKGROUND_URL}") no-repeat right top fixed;
    background-size: contain;
}}

/* GSK logo */
.gsk-logo {{
    position: fixed;
    top: 60px;
    right: 16px;
    z-index: 1000;
}}

/* Title box */
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

/* disclaimer */
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
</style>
""", unsafe_allow_html=True)

# ----------------------------
# Logo, Title, Disclaimer
# ----------------------------
GSK_LOGO_URL = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
st.markdown(f"""<div class="gsk-logo"><img src="{GSK_LOGO_URL}" width="140"></div>""", unsafe_allow_html=True)

st.markdown("""<div class="title-box"><h1>💡 AI Sales Call Assistant</h1>
<p>Powered by AI to equip sales reps for smarter HCP conversations</p></div>""", unsafe_allow_html=True)

st.markdown('<p class="disclaimer">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Data
# ----------------------------
race_segments = [
    "R – Reach: Not prescribing yet",
    "A – Acquisition: Prescribes when patient asks",
    "C – Conversion: Initiates for specific profiles",
    "E – Engagement: Proactively prescribes"
]

doctor_barriers = ["HZ risk doubts","No time","Cost concerns","Efficacy doubts","Access/logistics","Patient reluctance","Other doubts"]

personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]

gsk_approaches = ["Use data","Focus on outcomes","Storytelling","Address barriers"]

sales_call_flow = ["Prepare","Engage","Create Opportunities","Influence","Drive Impact","Post Call Analysis"]

APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]

objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist"]

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
# Sidebar Filters
# ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", options=list(gsk_brands.keys()))
    segment = st.selectbox("RACE Segment", options=race_segments)
    barrier = st.multiselect("Doctor Barrier", options=doctor_barriers)
    objective = st.selectbox("Objective", options=objectives)
    specialty = st.selectbox("Specialty", options=specialties)
    persona = st.selectbox("Persona", options=personas)
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"])
    response_tone = st.selectbox("Tone", ["Formal","Casual","Friendly","Persuasive"])
    language = st.radio("Language", ["English","العربية"])
    interface_mode = st.radio("Mode", ["Chatbot","Card Dashboard","Flow Visualization"])

# brand image
if gsk_brands_images.get(brand):
    try:
        img_resp = requests.get(gsk_brands_images[brand], timeout=10)
        st.sidebar.image(Image.open(BytesIO(img_resp.content)), width=200)
    except:
        st.sidebar.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)

# ----------------------------
# PDF Upload & Summarization
# ----------------------------
st.subheader("📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = ""
        for p in reader.pages:
            full_text += (p.extract_text() or "") + "\n"
        st.session_state.uploaded_pdf_text = full_text
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d\d|Lancet|NEJM)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches)
        st.success("✅ PDF processed")

        if st.button("Summarize PDF"):
            text_for_summary = full_text[:6000]
            summary_prompt = (f"Summarize this medical document for sales reps ({brand}), in {language}. "
                              f"Focus on actionable findings and APACT relevance.\n\n{text_for_summary}")
            try:
                summary_resp = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{"role":"system","content":"You are a concise medical summarizer."},
                              {"role":"user","content":summary_prompt}],
                    temperature=0.3
                )
                st.session_state.pdf_summary = summary_resp.choices[0].message.content
            except Exception as e:
                st.session_state.pdf_summary = f"⚠️ Error summarizing PDF: {e}"

            st.markdown("### 📑 PDF Summary")
            st.write(st.session_state.pdf_summary)
    except Exception as e:
        st.error(f"PDF error: {e}")

# ----------------------------
# Clear Chat
# ----------------------------
if st.sidebar.button("🗑️ Clear Chat"):
    st.session_state.chat_history = []

# ----------------------------
# Display Chat
# ----------------------------
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()

def display_chat():
    html = ""
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n","<br>")
        for step in APACT_STEPS:
            content = content.replace(step,f"<span class='highlight'>{step}</span>")
        ts = msg.get("time","")
        if msg["role"]=="user":
            html += f"<div class='chat-bubble-user'>{content}<br><span style='font-size:10px;color:gray'>{ts}</span></div>"
        else:
            audio_html = ""
            if msg.get("audio"):
                audio_html = f"<br><audio controls><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
            html += f"<div class='chat-bubble-ai'>{content}<br><span style='font-size:10px;color:gray'>{ts}</span>{audio_html}</div>"
    chat_placeholder.markdown(html, unsafe_allow_html=True)

display_chat()

# ----------------------------
# Chat input
# ----------------------------
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    submitted = st.form_submit_button("➤")

# ----------------------------
# TTS
# ----------------------------
def synthesize_tts(text, lang):
    if not text: return None
    voice = "ar-EG-SalmaNeural" if lang=="العربية" else "en-US-JennyNeural"
    filename = f"tts_{datetime.now().strftime('%H%M%S')}.mp3"
    try:
        async def _save():
            t = edge_tts.Communicate(text, voice=voice)
            await t.save(filename)
        asyncio.run(_save())
        with open(filename,"rb") as f:
            b = f.read()
        os.remove(filename)
        return base64.b64encode(b).decode("utf-8")
    except Exception as e:
        st.warning(f"⚠️ TTS failed: {e}")
        return None

# ----------------------------
# Handle chat submission
# ----------------------------
if submitted and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})
    approaches_str="\n".join(gsk_approaches)
    flow_str=" → ".join(sales_call_flow)
    medref=st.session_state.extracted_medical_ref or "None"
    pdfsum=st.session_state.pdf_summary or "None"

    prompt=(f"Language: {language}\nUser input: {user_input}\nBrand: {brand}\n"
            f"RACE: {segment}\nBarriers: {', '.join(barrier) if barrier else 'None'}\n"
            f"Objective: {objective}\nSpecialty: {specialty}\nPersona: {persona}\n"
            f"Medical Reference: {medref}\nPDF Summary: {pdfsum}\n\n"
            f"Sales Approaches:\n{approaches_str}\n\nSales Call Flow:\n{flow_str}\n\n"
            "Use APACT (Acknowledge → Probing → Action → Confirm → Transition). "
            f"Response Length: {response_length}, Tone: {response_tone}. "
            "Provide actionable sales call suggestions and a 3–6 line script.")

    try:
        resp=client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role":"system","content":f"You are a sales assistant replying in {language}."},
                      {"role":"user","content":prompt}],
            temperature=0.7
        )
        ai_output=resp.choices[0].message.content
    except Exception as e:
        ai_output=f"⚠️ Error: {e}"

    audio_b64=synthesize_tts(ai_output, language)

    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M"),"audio":audio_b64})
    display_chat()

# ----------------------------
# Word download
# ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    latest_ai=[m["content"] for m in st.session_state.chat_history if m["role"]=="ai"]
    if latest_ai:
        doc=Document(); doc.add_heading("AI Sales Call Response",0); doc.add_paragraph(latest_ai[-1])
        buf=io_bytes(); doc.save(buf)
        st.download_button("📥 Download Word", buf.getvalue(), file_name="AI_Response.docx")

# ----------------------------
# Brand leaflet
# ----------------------------
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
