# app.py
import os
import re
import time
import base64
import tempfile
import asyncio
from datetime import datetime
from io import BytesIO, BytesIO as io_bytes

import streamlit as st
from PIL import Image, ImageStat
import requests
import PyPDF2
import edge_tts

# Groq client
try:
    import groq
    from groq import Groq
except Exception as e:
    st.error("groq package not found. Install groq to enable AI. Error: " + str(e))
    raise

# Optional docx export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", page_icon="💡", layout="wide")

# ----------------------------
# GROQ API key
# ----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

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
if "language" not in st.session_state:
    st.session_state.language = "English"

# ----------------------------
# Assets & styling
# ----------------------------
BACKGROUND_URL = "https://sdmntprcentralus.oaiusercontent.com/files/00000000-b734-61f5-a93b-9ba88dbca3ee/raw?se=2025-09-29T12%3A57%3A58Z&sp=r&sv=2024-08-04&sr=b&scid=824d4bff-2b7f-5840-ab88-6b299849a7f3&skoid=add8ee7d-5fc7-451e-b06e-a82b2276cf62&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-29T06%3A35%3A36Z&ske=2025-09-30T06%3A35%3A36Z&sks=b&skv=2024-08-04&sig=INZ//zwicD0PpLeRFxvyL6kj3i6KdFnF3ZYZudrjqKw%3D"
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
text_color = "black" if brightness > 140 else "white"

CSS = f"""
<style>
.stApp {{
  background: url('{BACKGROUND_URL}') no-repeat top right;
    background-size: calc(200% - 280px) auto;
  background-attachment: flix;
  transition: background-size 0.3s ease;
}}
.stSidebar {{
  background-color: #dddd;
  padding: 14px;
}}
.stSidebar .stSelectbox, .stSidebar .stMultiselect, .stSidebar .stRadio, .stSidebar .stCheckbox, .stSidebar .stFileUploader {{
  border: 1px solid #fff;
  border-radius: 10px;
  padding: 8px;
  margin-bottom: 12px;
  background-color: #dddd;
}}
.gsk-logo {{
  position: flix;
  top: 60px;
  left: 10px;
  z-index: 1200;
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
  background: rgba(255,255,255,0.6);
  padding: 20px;
  border-radius: 12px;
  margin-bottom: 12px;
}}
.chat-bubble-user, .chat-bubble-ai {{
  padding: 12px;
  border-radius: 12px;
  margin: 8px 0;
  display: block;
  max-width: 95%;
  word-wrap: break-word;
  color: black;
}}
.chat-bubble-user {{ background:#f1f8e9; margin-left: auto; }}
.chat-bubble-ai {{ background:#f5f7fa; margin-right: auto; }}
.pdf-summary-inline {{
  margin-top:8px;
  background: rgba(255,255,255,0.6);
  padding:10px;
  border-radius:10px;
}}
.bottom-input {{
  position: fixed;
  bottom: 12px;
  left: 16px;
  right: 16px;
  z-index: 2000;
  display:flex;
  gap:12px;
  align-items:center;
  background: rgba(255,255,255,0.6);
  padding:10px;
  border-radius:12px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.08);
}}
.bottom-input input[type="text"] {{
  width: 100%;
  padding: 10px 14px;
  border-radius: 12px;
  border: 1px solid #ddd;
  outline: none;
}}
.bottom-input button {{
  min-width:120px;
  padding: 8px 14px;
  border-radius: 8px;
  border: none;
  background: #ff8c00;
  color: white;
  font-weight:600;
}}
@media (max-width: 430px) {{
  .title-box h1 {{ font-size:26px; }}
  .gsk-logo img {{ width: 90px; }}
  .bottom-input {{ left:8px; right:8px; bottom:8px; padding:8px; }}
}}
.highlight-step {{ font-weight:700; color:#000; }}
.highlight-figure {{ font-weight:700; color:#d35400; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(f'<div class="gsk-logo"><img src="{GSK_LOGO_URL}" width="140"></div>', unsafe_allow_html=True)

# ----------------------------
# Title & disclaimer
# ----------------------------
st.markdown("""
<div class="title-box">
  <h1>💡 AI Sales Call Assistant</h1>
  <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
</div>
""", unsafe_allow_html=True)
st.markdown('<p style="text-align:center;font-weight:600;">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Sidebar filters
# ----------------------------
gsk_brands = {
    "Shingrix": "https://www.shingrix.com/",
    "Trelegy": "https://www.trelegy.com/",
    "Zejula": "https://www.zejula.com/"
}
gsk_brands_images = {
    "Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Trelegy": "https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
    "Zejula": "https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png",
}
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = [
    "HCP does not consider HZ a risk",
    "No time for discussion",
    "Cost concerns",
    "Not convinced of efficacy",
    "Accessibility/Logistics",
    "Patient reluctance",
    "Other clinical doubts"
]
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist",
               "Rheumatologist", "Internal Medicine", "Diabetologist", "Neurologist", "Pneumologist"]

with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown('<div style="font-weight:800; margin-bottom:8px;">Filters & Options</div>', unsafe_allow_html=True)
    brand = st.selectbox("Select Brand", options=list(gsk_brands.keys()))
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try:
            resp = requests.get(img_path, timeout=6)
            img = Image.open(BytesIO(resp.content))
            st.image(img, width=180)
        except:
            st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=180)
    segment = st.selectbox("Select RACE Segment", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty", options=specialties)
    persona = st.selectbox("Select HCP Persona", options=personas)
    response_length = st.selectbox("Response Length", ["Short", "Medium", "Long"])
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])
    interface_mode = st.radio("Interface Mode", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# ----------------------------
# PDF upload & summarization
# ----------------------------
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:2000] + "..." if len(full_text) > 2000 else full_text
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"

        # Summarization
        summary_prompt = (
            "You are a concise medical summarizer for sales reps. Produce bullet points with key results, "
            "practical recommendations, and notable figures (with % format if present). Keep it short and actionable.\n\n"
        ) + full_text[:6000]

        if client:
            try:
                resp = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{"role": "system", "content": "You are a concise medical summarizer."},
                              {"role": "user", "content": summary_prompt}],
                    temperature=0.25,
                )
                st.session_state.pdf_summary = resp.choices[0].message.content
            except Exception as e:
                st.warning(f"PDF summarization error: {e}")
                st.session_state.pdf_summary = ""
        else:
            st.warning("Groq client not configured: PDF auto-summarize unavailable.")
            st.session_state.pdf_summary = ""

        if st.session_state.pdf_summary:
            with st.expander("📑 PDF Summary (expand/collapse)", expanded=False):
                st.markdown(f'<div class="pdf-summary-box">{"<br>".join([f"- {line.strip()}" for line in st.session_state.pdf_summary.split("\\n") if line.strip()])}</div>', unsafe_allow_html=True)

        if st.session_state.extracted_medical_ref:
            st.info(f"📚 Extracted references: {st.session_state.extracted_medical_ref}")
    except Exception as e:
        st.error("PDF error: " + str(e))

# ----------------------------
# Chat & TTS
# ----------------------------
async def synthesize_tts_base64(text: str, lang: str = "English") -> str:
    if not text.strip(): return None
    voice = "en-US-AriaNeural" if lang == "English" else "ar-EG-SalmaNeural"
    try:
        with tempfile.NamedTemporaryFile(delete=True, suffix=".mp3") as tmpfile:
            comm = edge_tts.Communicate(text, voice)
            await comm.save(tmpfile.name)
            tmpfile.seek(0)
            return base64.b64encode(tmpfile.read()).decode("utf-8")
    except Exception as e:
        st.warning(f"TTS failed: {e}")
        return None

def render_chat_history():
    html = ""
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            html += f'<div class="chat-bubble-user">{msg["content"]}</div>'
        else:
            audio_html = ""
            if msg.get("audio"):
                audio_html = f'<br><audio controls style="margin-top:8px;"><source src="data:audio/mp3;base64,{msg["audio"]}" type="audio/mp3"></audio>'
            html += f'<div class="chat-bubble-ai">{msg["content"]}{audio_html}</div>'
    st.markdown(html, unsafe_allow_html=True)

def build_prompt(user_input: str) -> str:
    pdf_summary = st.session_state.pdf_summary or ""
    refs = st.session_state.extracted_medical_ref or "None"
    return f"""Language: {st.session_state.language}
User input: {user_input}
Brand: {brand}
RACE Segment: {segment}
Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Doctor Specialty: {specialty}
HCP Persona: {persona}

Instructions:
- Use PDF summary and references
- Bold steps, APACT, and figures

PDF Summary:
{pdf_summary}

References:
{refs}
"""

def call_groq_with_retry(prompt: str, max_retries=3, delay=2):
    if not client: return "⚠️ AI service not configured."
    last_err = None
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role":"user","content":prompt}],
                temperature=0.7
            )
            return resp.choices[0].message.content
        except Exception as e:
            last_err = e
            time.sleep(delay*(2**attempt))
    return f"⚠️ AI call failed after retries: {last_err}"

# Input handling
user_input = st.text_input("Type your message here")
if st.button("Send") and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input})
    prompt = build_prompt(user_input)
    ai_output = call_groq_with_retry(prompt)
    audio_b64 = asyncio.run(synthesize_tts_base64(ai_output))
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"audio":audio_b64})
    render_chat_history()

# ----------------------------
# Clear / Download
# ----------------------------
cols = st.columns(2)
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
                doc.add_heading(f"Response {idx}",1)
                doc.add_paragraph(txt)
            word_buffer=io_bytes()
            doc.save(word_buffer)
            st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(),file_name="AI_Responses.docx")

# Brand leaflet
st.markdown(f"[📄 Brand Leaflet - {brand}]({gsk_brands[brand]})")
