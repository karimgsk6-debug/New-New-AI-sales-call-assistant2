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
# Optional Word download
# ----------------------------
try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# ----------------------------
# GROQ client
# ----------------------------
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# ----------------------------
# Session state defaults
# ----------------------------
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state: st.session_state.uploaded_pdf_text = ""
if "extracted_medical_ref" not in st.session_state: st.session_state.extracted_medical_ref = ""
if "pdf_summary" not in st.session_state: st.session_state.pdf_summary = ""

# ----------------------------
# Assets & styling variables
# ----------------------------
BACKGROUND_URL = "https://sdmntprwestus2.oaiusercontent.com/files/00000000-8938-61f8-9ad4-67d8ede9c081/raw?se=2025-09-27T22%3A16%3A30Z&sp=r&sv=2024-08-04&sr=b&scid=0a78f1b4-0cf9-5f7d-a678-1ae2eeda8012&skoid=f05d6a75-3c59-41ae-be2c-51a75f29841e&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-27T05%3A28%3A39Z&ske=2025-09-28T05%3A28%3A39Z&sks=b&skv=2024-08-04&sig=Gvl5QQwvTZI0Qs0v7Sn0TgfX1O4ho395g/SXEsJEDoc%3D"
GSK_LOGO_URL = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"

def get_brightness(url: str) -> int:
    try:
        r = requests.get(url, timeout=8)
        img = Image.open(BytesIO(r.content)).convert("L")
        stat = ImageStat.Stat(img)
        return int(stat.mean[0])
    except:
        return 255

brightness = get_brightness(BACKGROUND_URL)
text_color = "black" if brightness > 130 else "white"
user_bubble_bg = "rgba(220,248,198,0.95)" if brightness>130 else "rgba(0,128,0,0.7)"
ai_bubble_bg = "rgba(240,242,246,0.95)" if brightness>130 else "rgba(255,255,255,0.3)"

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
    position: fixed;
    top: 60px;
    right: 16px;
    z-index: 1000;
}}
.title-box {{
    background: rgba(255,255,255,0.96);
    padding: 28px;
    border-radius: 14px;
    text-align: center;
    max-width: 85%;
    margin: 12px auto;
}}
.title-box h1 {{ margin: 0; font-size: 38px; font-weight: 800; color:{text_color}; }}
.title-box p {{ margin: 8px 0 0 0; font-size: 18px; font-weight: 500; color:{text_color}; }}
.disclaimer {{ text-align:center; padding:10px; font-size:14px; font-weight:500; color:{text_color}; }}
.chat-bubble-user, .chat-bubble-ai {{
    padding: 12px;
    border-radius: 15px;
    margin: 6px 0;
    display: inline-block;
    max-width: 95%;
    word-wrap: break-word;
}}
.chat-bubble-user {{ text-align:right; background:{user_bubble_bg}; color:{text_color}; }}
.chat-bubble-ai {{ text-align:left; background:{ai_bubble_bg}; color:{text_color}; }}
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
# Logo & Title
# ----------------------------
st.markdown(f'<div class="gsk-logo"><img src="{GSK_LOGO_URL}" width="140" /></div>', unsafe_allow_html=True)
st.markdown(
    f"""
    <div class="title-box">
      <h1>💡 AI Sales Call Assistant</h1>
      <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
    </div>
    """, unsafe_allow_html=True)
st.markdown(f'<p class="disclaimer">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Language selector
# ----------------------------
language = st.radio("", options=["English", "العربية"], horizontal=True, label_visibility="collapsed")

# ----------------------------
# Filters (brands, segments, barriers, HCP specialties)
# ----------------------------
gsk_brands = {"Shingrix":"https://www.shingrix.com/","Trelegy":"https://www.trelegy.com/","Zejula":"https://www.zejula.com/"}
gsk_brands_images = {"Shingrix":"https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
                     "Trelegy":"https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
                     "Zejula":"https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png"}

race_segments = ["R – Reach","A – Acquisition","C – Conversion","E – Engagement"]
doctor_barriers = ["HCP does not consider HZ a risk","No time","Cost concerns","Not convinced","Accessibility","Patient reluctance","Other clinical doubts"]
specialties=["GP","Cardiologist","Dermatologist","Rheumatologist","Internal Medicine","Diabetologist","Endocrinologist","Pneumologist","Neurologist"]

with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Select Brand", options=list(gsk_brands.keys()))
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try: st.image(Image.open(BytesIO(requests.get(img_path).content)), width=200)
        except: st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)
    segment = st.selectbox("Select RACE Segment", options=race_segments)
    barrier = st.multiselect("Doctor Barrier", options=doctor_barriers, default=[])
    specialty = st.selectbox("HCP Specialty", options=specialties)

# ----------------------------
# PDF upload & bullet-point summary
# ----------------------------
st.subheader("📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
show_more_toggle = st.checkbox("Show full PDF text", value=False)
if uploaded_pdf:
    try:
        reader=PyPDF2.PdfReader(uploaded_pdf)
        full_text="".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text=full_text if show_more_toggle else full_text[:1000]+"..."
        matches=re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref=", ".join(matches) if matches else ""
        # Summarize PDF into bullet points
        summary_prompt = f"Summarize the following medical document in bullet points with real figures if available:\n\n{full_text[:6000]}"
        resp = client.chat.completions.create(model="meta-llama/llama-4-scout-17b-16e-instruct",
                                              messages=[{"role":"system","content":"You are a concise medical summarizer."},
                                                        {"role":"user","content":summary_prompt}],
                                              temperature=0.3)
        st.session_state.pdf_summary="\n• ".join(resp.choices[0].message.content.split("\n"))
        st.markdown("### 📑 PDF Summary")
        st.write("• "+st.session_state.pdf_summary)
    except Exception as e:
        st.error(f"PDF error: {e}")

# ----------------------------
# Chat rendering
# ----------------------------
def render_chat_html():
    html=""
    for msg in st.session_state.chat_history:
        content=msg["content"].replace("\n","<br>")
        for step in ["Acknowledge","Probing","Action","Confirm","Transition"]:
            content=content.replace(step,f"<span class='highlight'>{step}</span>")
        if msg["role"]=="user":
            html+=f"<div class='chat-bubble-user'>{content}</div>"
        else:
            audio_html=""
            if msg.get("audio"):
                audio_html=f"<br><audio controls style='margin-top:8px;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
            html+=f"<div class='chat-bubble-ai'>{content}{audio_html}</div>"
    return html

st.markdown(render_chat_html(), unsafe_allow_html=True)

# ----------------------------
# TTS helper
# ----------------------------
def synthesize_tts_base64(text:str, lang:str)->Optional[str]:
    text=re.sub(r'([;:{}\[\]\*\^<>@#\$%&\|~_=/\\\+])','',text)
    clean_text=re.sub(r'\s+',' ', text).strip()
    if not clean_text: return None
    voice="ar-EG-SalmaNeural" if lang=="العربية" else "en-US-JennyNeural"
    tmp=tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name=tmp.name
    tmp.close()
    try:
        async def _save():
            comm=edge_tts.Communicate(clean_text, voice=voice)
            await comm.save(tmp_name)
        asyncio.run(_save())
        with open(tmp_name,"rb") as f: b=f.read()
        return base64.b64encode(b).decode("utf-8")
    finally:
        if os.path.exists(tmp_name): os.remove(tmp_name)

# ----------------------------
# Chat submission form
# ----------------------------
with st.form("chat_form", clear_on_submit=True):
    user_input=st.text_input("Type your message...", key="user_input_box")
    submitted=st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})
    # Build prompt including PDF summary & references
    prompt=f"User input: {user_input}\nPDF Summary: {st.session_state.pdf_summary}\nReferences: {st.session_state.extracted_medical_ref}\nInclude call flow steps and APACT."
    resp=client.chat.completions.create(model="meta-llama/llama-4-scout-17b-16e-instruct",
                                        messages=[{"role":"system","content":"You are a helpful sales assistant."},
                                                  {"role":"user","content":prompt}],
                                        temperature=0.7)
    ai_output=resp.choices[0].message.content
    audio_b64=synthesize_tts_base64(ai_output, language)
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M"),"audio":audio_b64})
    st.markdown(render_chat_html(), unsafe_allow_html=True)

# ----------------------------
# Bottom bar: Clear & Download
# ----------------------------
cols=st.columns([1,1])
with cols[0]:
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history=[]
        st.session_state.uploaded_pdf_text=""
        st.session_state.extracted_medical_ref=""
        st.session_state.pdf_summary=""
        st.experimental_rerun()
with cols[1]:
    if DOCX_AVAILABLE and st.session_state.chat_history:
        latest_ai=[m["content"] for m in st.session_state.chat_history if m["role"]=="ai"]
        if latest_ai:
            doc=Document()
            doc.add_heading("AI Sales Call Responses",0)
            for idx,txt in enumerate(latest_ai,1):
                doc.add_heading(f"Response {idx}",level=1)
                doc.add_paragraph(txt)
            buf=io_bytes()
            doc.save(buf)
            st.download_button("📥 Download as Word", buf.getvalue(), file_name="AI_Responses.docx")
