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
# Assets & styling
# ----------------------------
BACKGROUND_URL = ("https://sdmntprukwest.oaiusercontent.com/files/00000000-abd4-6243-82cf-168367664603/raw?se=2025-09-27T20%3A50%3A12Z&sp=r&sv=2024-08-04&sr=b&scid=ecda9bff-da85-5e32-ac41-b08c14ba28cf&skoid=d9a3f0e9-8380-4267-a144-3f27388a5c5d&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-27T12%3A41%3A14Z&ske=2025-09-28T12%3A41%3A14Z&sks=b&skv=2024-08-04&sig=oXICxZIQ74jEr/fZxSZH/TmBnN8eb/3bsNRGRUHTsf0%3D")
GSK_LOGO_URL = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"

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
button_bg = "#FFA500" if brightness > 130 else "#FF8C00"

# ----------------------------
# CSS (full-page background + plain chat)
# ----------------------------
CSS = f"""
<style>
.stApp {{
    background: url('{BACKGROUND_URL}') no-repeat top right;
    background-size: cover;
    background-attachment: fixed;
}}
.stSidebar {{
    background-color: rgba(255,255,255,0.9);
    padding: 14px;
}}
.stSidebar .stSelectbox, .stSidebar .stMultiselect, .stSidebar .stRadio, .stSidebar .stCheckbox, .stSidebar .stFileUploader {{
    border: 1px solid #ddd;
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
.title-box h1 {{ margin: 0; font-size: 38px; font-weight: 800; }}
.title-box p {{ margin: 8px 0 0 0; font-size: 18px; font-weight: 500; }}
.disclaimer {{ text-align:center; padding:10px; font-size:14px; font-weight:500; }}
#chat-container {{
    height:60vh;
    overflow:auto;
    padding:12px;
    border-radius:8px;
    background: rgba(255,255,255,0.6);
    color: {text_color};
    font-size: 16px;
    line-height: 1.5;
}}
.bottom-bar {{
    position: fixed;
    bottom: 12px;
    width: 96%;
    left: 2%;
    z-index: 1000;
    display:flex;
    gap:12px;
    align-items:center;
}}
.chat-input {{
    flex: 1;
}}
.clear-btn, .download-btn {{
    min-width: 140px;
}}
@media (max-width: 800px) {{
    .title-box h1 {{ font-size: 28px; }}
    .gsk-logo img {{ width: 110px; }}
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------
# Sidebar collapse/expand JS
# ----------------------------
SIDEBAR_JS = """
<script>
(function() {
  const app = document.querySelector('.stApp');
  const sidebar = document.querySelector('[data-testid="stSidebar"]');
  if (!app || !sidebar) return;

  function adjustBg() {
    const expanded = sidebar.getAttribute('aria-expanded') === 'true';
    app.style.backgroundSize = 'cover';
  }

  adjustBg();

  const mo = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.attributeName === 'aria-expanded') adjustBg();
    }
  });
  mo.observe(sidebar, { attributes: true });
})();
</script>
"""
st.markdown(SIDEBAR_JS, unsafe_allow_html=True)

# ----------------------------
# Auto-scroll JS
# ----------------------------
SCROLL_JS = """
<script>
function scrollChat() {
  const container = document.getElementById('chat-container');
  if (container) container.scrollTop = container.scrollHeight;
}
setTimeout(scrollChat, 200);
</script>
"""

# ----------------------------
# Top-right logo + title + disclaimer
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
# Top-left language selector
# ----------------------------
st.markdown(
    """
    <div style="position:fixed; top:76px; left:18px; z-index:1000; background: rgba(255,255,255,0.95); padding:6px 10px; border-radius:8px;">
    """,
    unsafe_allow_html=True,
)
language = st.radio("", options=["English", "العربية"], horizontal=True, label_visibility="collapsed")
st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# Sidebar content (brands, filters)
# ----------------------------
gsk_brands = {
    "Shingrix": "https://www.shingrix.com/",
    "Trelegy": "https://www.trelegy.com/",
    "Zejula": "https://www.zejula.com/",
}
gsk_brands_images = {
    "Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Trelegy": "https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
    "Zejula": "https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png",
}

race_segments = [
    "R – Reach: Not prescribing yet; doesn't see vaccination responsibility.",
    "A – Acquisition: Prescribes when patient asks; convinced by data.",
    "C – Conversion: Initiates for specific profiles; not across all profiles.",
    "E – Engagement: Proactively prescribes across multiple patient profiles.",
]
doctor_barriers = [
    "HCP does not consider HZ a risk",
    "No time for discussion",
    "Cost concerns",
    "Not convinced of efficacy",
    "Accessibility/Logistics",
    "Patient reluctance",
    "Other clinical doubts",
]
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
gsk_approaches = [
    "Use data-driven evidence (local + global studies)",
    "Focus on patient outcomes & quality of life",
    "Leverage brief storytelling and peer endorsement",
    "Address practical barriers (access, scheduling, cost solutions)",
]
sales_call_flow = [
    "Prepare: Data & patient profiles",
    "Engage: Opening question & rapport",
    "Create Opportunities: Identify eligible patients",
    "Influence: Present tailored evidence & handle objections",
    "Drive Impact: Secure next steps (prescription/scheduling)",
    "Post Call Analysis: Document & follow up",
]
APACT_STEPS = ["Acknowledge", "Probing", "Action", "Confirm", "Transition"]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]

with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown('<div style="font-weight:800; margin-bottom:8px;">Filters & Options</div>', unsafe_allow_html=True)
    brand = st.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try:
            resp = requests.get(img_path, timeout=8)
            img = Image.open(BytesIO(resp.content))
            st.image(img, width=200)
        except Exception:
            st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)

    segment = st.selectbox("Select RACE Segment / اختر شريحة RACE", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective / اختر الهدف", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", options=specialties)
    persona = st.selectbox("Select HCP Persona / اختر شخصية الطبيب", options=personas)
    response_length = st.selectbox("Response Length / اختر طول الرد", ["Short", "Medium", "Long"])
    response_tone = st.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])
    interface_mode = st.radio("Interface Mode / اختر واجهة", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# ----------------------------
# PDF Upload
# ----------------------------
st.subheader("📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
show_more_toggle = st.checkbox("Show full PDF text", value=False)
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text if show_more_toggle else full_text[:1000] + "..."
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else ""
        st.success("✅ PDF processed")
    except Exception as e:
        st.error(f"PDF error: {e}")

st.markdown("### PDF Preview / Summary")
st.write(st.session_state.uploaded_pdf_text or "No PDF uploaded.")

# ----------------------------
# Chat rendering (plain text)
# ----------------------------
def render_chat_html() -> str:
    html = '<div id="chat-container">'
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n", "<br>")
        for step in APACT_STEPS:
            content = content.replace(step, f"<span class='highlight'>{step}</span>")
        html += f"{content}<br><span style='font-size:10px;color:gray'>{msg.get('time','')}</span><br><br>"
    html += '</div>'
    return html

st.subheader("💬 Chatbot Interface")
st.markdown(render_chat_html(), unsafe_allow_html=True)
st.markdown(SCROLL_JS, unsafe_allow_html=True)

# ----------------------------
# Chat input & handle submission
# ----------------------------
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message... / اكتب رسالتك هنا", key="user_input_box")
    submitted = st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})
    st.markdown(render_chat_html(), unsafe_allow_html=True)
    st.markdown(SCROLL_JS, unsafe_allow_html=True)
    # Build prompt and call Groq
    prompt_lines = [
        f"Language: {language}",
        f"User input: {user_input}",
        f"Brand: {brand}",
        f"RACE Segment: {segment}",
        f"Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}",
        f"Objective: {objective}",
        f"Doctor Specialty: {specialty}",
        f"HCP Persona: {persona}",
        f"Medical Reference(s): {st.session_state.extracted_medical_ref or 'None'}",
        f"Uploaded PDF (preview): {st.session_state.uploaded_pdf_text or 'No PDF uploaded.'}",
        "Approved Sales Approaches:\n" + "\n".join(gsk_approaches),
        "Sales Call Flow Steps:\n" + " → ".join(sales_call_flow),
        "Use APACT technique for handling objections.",
        f"Response Length: {response_length}",
        f"Response Tone: {response_tone}",
    ]
    prompt = "\n".join(prompt_lines)

    # Groq call with retry
    def call_groq_with_retry(prompt: str, language: str, max_retries: int = 4, base_delay: int = 2) -> str:
        models = ["meta-llama/llama-4-scout-17b-16e-instruct", "meta-llama/llama-4-scout-13b-instruct"]
        last_err = None
        for model in models:
            for attempt in range(1, max_retries + 1):
                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "system", "content": f"You are a helpful sales assistant that responds in {language}."},
                                  {"role": "user", "content": prompt}],
                        temperature=0.7,
                    )
                    return resp.choices[0].message.content
                except Exception as e:
                    last_err = e
                    msg = str(e).lower()
                    if "503" in msg or "over capacity" in msg or "internal_server_error" in msg:
                        wait = base_delay * (2 ** (attempt - 1))
                        st.warning(f"Model {model} busy. Retrying in {wait}s (attempt {attempt}/{max_retries})...")
                        time.sleep(wait)
                        continue
                    else:
                        return f"⚠️ Error generating response: {e}"
        return f"⚠️ Failed to get response: {last_err}"

    ai_output = call_groq_with_retry(prompt, language)
    st.session_state.chat_history.append({"role": "ai", "content": ai_output, "time": datetime.now().strftime("%H:%M")})
    st.markdown(render_chat_html(), unsafe_allow_html=True)
    st.markdown(SCROLL_JS, unsafe_allow_html=True)

# ----------------------------
# Bottom controls: Clear & Download
# ----------------------------
cols = st.columns([1, 1])
with cols[0]:
    if st.button("🗑️ Clear Chat / مسح المحادثة"):
        st.session_state.chat_history = []
        st.session_state.uploaded_pdf_text = ""
        st.session_state.extracted_medical_ref = ""
        st.session_state.pdf_summary = ""
        st.experimental_rerun()
with cols[1]:
    if DOCX_AVAILABLE and st.session_state.chat_history:
        latest_ai = [m["content"] for m in st.session_state.chat_history if m["role"] == "ai"]
        if latest_ai:
            doc = Document()
            doc.add_heading("AI Sales Call Responses", 0)
            for idx, txt in enumerate(latest_ai, 1):
                doc.add_heading(f"Response {idx}", level=1)
                doc.add_paragraph(txt)
            word_buffer = io_bytes()
            doc.save(word_buffer)
            st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_responses.docx")
