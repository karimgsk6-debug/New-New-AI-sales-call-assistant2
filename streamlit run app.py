# app.py
import streamlit as st
from PIL import Image, ImageStat
import requests
from io import BytesIO, BytesIO as io_bytes
import groq
from groq import Groq
from datetime import datetime
import PyPDF2
import asyncio
import edge_tts
import base64
import re
import os
import tempfile
import time
from typing import Optional

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", page_icon="💡", layout="wide")

# ----------------------------
# Optional Word download (docx)
# ----------------------------
try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# ----------------------------
# GROQ client (replace with your key)
# ----------------------------
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# ----------------------------
# Session state defaults
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
# Assets & styling variables
# ----------------------------
BACKGROUND_URL = "https://sdmntprwestus2.oaiusercontent.com/files/00000000-8938-61f8-9ad4-67d8ede9c081/raw?se=2025-09-27T22%3A16%3A30Z&sp=r&sv=2024-08-04&sr=b&scid=0a78f1b4-0cf9-5f7d-a678-1ae2eeda8012&skoid=f05d6a75-3c59-41ae-be2c-51a75f29841e&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-27T05%3A28%3A39Z&ske=2025-09-28T05%3A28%3A39Z&sks=b&skv=2024-08-04&sig=Gvl5QQwvTZI0Qs0v7Sn0TgfX1O4ho395g/SXEsJEDoc%3D"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"

def get_brightness(url: str) -> int:
    try:
        r = requests.get(url, timeout=8)
        img = Image.open(BytesIO(r.content)).convert("L")
        stat = ImageStat.Stat(img)
        return int(stat.mean[0])
    except Exception:
        return 255

brightness = get_brightness(BACKGROUND_URL)
text_color = "black" if brightness > 130 else "white"

# ----------------------------
# CSS styling
# ----------------------------
CSS = f"""
<style>
.stApp {{
    background: url('{BACKGROUND_URL}') no-repeat top right;
    background-size: cover;
    background-attachment: fixed;
}}
.stSidebar {{
    background-color: #fff;
    padding: 14px;
}}
.stSidebar .stSelectbox, .stSidebar .stMultiselect, .stSidebar .stRadio, .stSidebar .stCheckbox, .stSidebar .stFileUploader {{
    border: 2px solid #ddd;
    border-radius: 10px;
    padding: 8px;
    margin-bottom: 12px;
    background-color: #fff;
}}
.gsk-logo {{
    position: flix;
    top: 80px;
    right: 16px;
    z-index: 1000;
}}
.title-box {{
    background: rgba(255,255,255,0.6);
    padding: 28px;
    border-radius: 14px;
    text-align: center;
    max-width: 85%;
    margin: 12px auto;
}}
.title-box h1 {{ margin: 0; font-size: 38px; font-weight: 800; }}
.title-box p {{ margin: 8px 0 0 0; font-size: 18px; font-weight: 500; }}
.pdf-summary-box {{
    background: rgba(255,255,255,0.95);
    border-radius: 14px;
    padding: 16px;
    margin: 12px 0;
}}
.disclaimer {{ text-align:center; padding:10px; font-size:14px; font-weight:500; }}
.chat-bubble-user, .chat-bubble-ai {{
    padding: 12px;
    border-radius: 15px;
    margin: 6px 0;
    display: inline-block;
    max-width: 95%;
    word-wrap: break-word;
    color:black;
}}
.chat-bubble-user {{ text-align:right; background: rgba(220,248,198,0.95); }}
.chat-bubble-ai {{ text-align:left; background: rgba(240,242,246,0.95); }}
.highlight {{ font-weight: bold; background-color: yellow; color: black; padding: 2px 4px; border-radius: 4px; }}
.bottom-bar {{
    position: fixed;
    bottom: 12px;
    width: 96%;
    left: 2%;
    z-index: 1000;
    display:flex; gap:12px; align-items:center;
}}
.chat-input {{ flex: 1; }}
.clear-btn, .download-btn {{ min-width: 140px; }}
@media (max-width: 430px) {{
    .title-box h1 {{ font-size: 26px; }}
    .gsk-logo img {{ width: 90px; }}
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------
# Top-right logo + title
# ----------------------------
st.markdown(f'<div class="gsk-logo"><img src="{GSK_LOGO_URL}" width="140" /></div>', unsafe_allow_html=True)
st.markdown(
    """
    <div class="title-box">
      <h1>💡 AI Sales Call Assistant</h1>
      <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown('<p class="disclaimer">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Language selector
# ----------------------------
language = st.radio("", options=["English", "العربية"], horizontal=True, label_visibility="collapsed")

# ----------------------------
# GSK data
# ----------------------------
gsk_brands = {"Shingrix":"https://www.shingrix.com/", "Trelegy":"https://www.trelegy.com/", "Zejula":"https://www.zejula.com/"}
gsk_brands_images = {
    "Shingrix":"https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Trelegy":"https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
    "Zejula":"https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png"
}
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy","Accessibility/Logistics","Patient reluctance","Other clinical doubts"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
gsk_approaches = ["Use data-driven evidence (local + global studies)","Focus on patient outcomes & quality of life","Leverage brief storytelling and peer endorsement","Address practical barriers (access, scheduling, cost solutions)"]
sales_call_flow = ["**Prepare**: Data & patient profiles","**Engage**: Opening & rapport","**Create Opportunities**: Identify eligible patients","**Influence**: Present evidence & handle objections","**Impact GSO**: Secure next steps","**Analyze & Post Call Analysis**"]
APACT_STEPS = ["**Acknowledge**","**Probing**","**Action**","**Confirm**","**Transition**"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist","Rheumatologist","Internal Medicine","Diabetologist","Neurologists","Pneumologist"]

# ----------------------------
# Sidebar filters
# ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown('<div style="font-weight:800; margin-bottom:8px;">Filters & Options</div>', unsafe_allow_html=True)
    brand = st.selectbox("Select Brand", options=list(gsk_brands.keys()))
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try:
            resp = requests.get(img_path, timeout=8)
            img = Image.open(BytesIO(resp.content))
            st.image(img, width=200)
        except:
            st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)
    segment = st.selectbox("Select RACE Segment", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty", options=specialties)
    persona = st.selectbox("Select HCP Persona", options=personas)
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"])
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"])
    interface_mode = st.radio("Interface Mode", ["Chatbot","Card Dashboard","Flow Visualization"])

# ----------------------------
# PDF upload and summary with box & expand
# ----------------------------
st.subheader("📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:2000]+"..." if len(full_text)>2000 else full_text
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"
        st.success("✅ PDF processed")
        # Auto summary using Groq
        summary_prompt = f"Summarize this medical document into bullet points with key results, practical recommendations, and figures. Language: {language}.\n\n{full_text[:6000]}"
        summary_resp = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role":"system","content":"You are a concise medical summarizer."},{"role":"user","content":summary_prompt}],
            temperature=0.3
        )
        st.session_state.pdf_summary = summary_resp.choices[0].message.content

        with st.expander("Expand / Collapse PDF Summary", expanded=False):
            st.markdown(f'<div class="pdf-summary-box">', unsafe_allow_html=True)
            for line in st.session_state.pdf_summary.split("\n"):
                if line.strip():
                    st.markdown(f"- {line.strip()}", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        st.info(f"📚 Extracted references: {st.session_state.extracted_medical_ref}")
    except Exception as e:
        st.error(f"PDF error: {e}")

# ----------------------------
# TTS helper (humanized)
# ----------------------------
def synthesize_tts_base64(text: str, lang: str) -> Optional[str]:
    text = re.sub(r'([;:{}\[\]\*\^<>@#\$%&\|~_=/\\\+])','',text)
    text = re.sub(r'\s+',' ', text).strip()
    if not text:
        return None
    sentences = re.split(r'(?<=[.?!]) +', text)
    ssml_text = "<speak>" + " ".join([f"<prosody rate='medium'>{s}<break time='0.4s'/></prosody>" for s in sentences]) + "</speak>"
    voice = "ar-EG-SalmaNeural" if lang=="العربية" else "en-US-AriaNeural"
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        async def _save():
            comm = edge_tts.Communicate(ssml_text, voice=voice)
            await comm.save(tmp_name)
        asyncio.run(_save())
        with open(tmp_name,"rb") as f:
            b = f.read()
        return base64.b64encode(b).decode("utf-8")
    finally:
        if os.path.exists(tmp_name): os.remove(tmp_name)

# ----------------------------
# Chat form
# ----------------------------
st.subheader("💬 Chatbot Interface")
def render_chat_html() -> str:
    html = ""
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n","<br>")
        if msg["role"]=="user":
            html += f"<div class='chat-bubble-user'>{content}</div>"
        else:
            audio_html = ""
            if msg.get("audio"):
                audio_html = f"<br><audio controls style='margin-top:8px;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
            html += f"<div class='chat-bubble-ai'>{content}{audio_html}</div>"
    return html

st.markdown(render_chat_html(), unsafe_allow_html=True)

with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    submitted = st.form_submit_button("➤")

# ----------------------------
# Handle submission
# ----------------------------
if submitted and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})
    prompt_lines = [
        f"Language: {language}",
        f"User input: {user_input}",
        f"Brand: {brand}",
        f"RACE Segment: {segment}",
        f"Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}",
        f"Objective: {objective}",
        f"Doctor Specialty: {specialty}",
        f"HCP Persona: {persona}",
        "Instructions for AI:",
        "- Use the uploaded PDF and extracted references as primary sources for clinical info.",
        "- Cite references explicitly if possible.",
        "- Follow APACT technique for objections.",
        "- Bold **sales call steps**, APACT steps, and figures.",
        "- Provide actionable sales suggestions.",
        "- Response length: {response_length}, Tone: {response_tone}",
        "PDF Summary:\n" + (st.session_state.pdf_summary or "None"),
        "References:\n" + (st.session_state.extracted_medical_ref or "None")
    ]
    prompt = "\n".join(prompt_lines)
    ai_output = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role":"system","content":"You are a helpful sales assistant."},{"role":"user","content":prompt}],
        temperature=0.7
    ).choices[0].message.content
    audio_b64 = synthesize_tts_base64(ai_output, language)
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M"),"audio":audio_b64})
    st.markdown(render_chat_html(), unsafe_allow_html=True)

# ----------------------------
# Bottom controls
# ----------------------------
cols = st.columns([1,1])
with cols[0]:
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history=[]
        st.session_state.uploaded_pdf_text=""
        st.session_state.extracted_medical_ref=""
        st.session_state.pdf_summary=""
        st.experimental_rerun()
with cols[1]:
    if DOCX_AVAILABLE and st.session_state.chat_history:
        latest_ai = [m["content"] for m in st.session_state.chat_history if m["role"]=="ai"]
        if latest_ai:
            doc = Document()
            doc.add_heading("AI Sales Call Responses",0)
            for idx,txt in enumerate(latest_ai,1):
                doc.add_heading(f"Response {idx}",level=1)
                doc.add_paragraph(txt)
            word_buffer = io_bytes()
            doc.save(word_buffer)
            st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Responses.docx")

# ----------------------------
# Brand leaflet
# ----------------------------
st.markdown(f"[📄 Brand Leaflet - {brand}]({gsk_brands[brand]})")
