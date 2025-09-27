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
GROQ_API_KEY = "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"  # <- replace
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
BACKGROUND_URL = ("https://sdmntprsouthcentralus.oaiusercontent.com/files/00000000-a9b4-61f7-b2cf-05a782087038/raw?se=2025-09-27T16%3A42%3A35Z&sp=r&sv=2024-08-04&sr=b&scid=5258dbc1-6382-5fec-a8d5-ad7bcc18750b&skoid=b928fb90-500a-412f-a661-1ece57a7c318&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-26T17%3A22%3A36Z&ske=2025-09-27T17%3A22%3A36Z&sks=b&skv=2024-08-04&sig=eSrtOWb2e5Fm4%2Bpg7z1kf2I0XJ2H3I/Mqc5df0aOFSk%3D"
)
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
# CSS (responsive background + sidebar white + filter borders + UI)
# ----------------------------
CSS = f"""
<style>
/* Main app background (will be dynamically resized by JS when sidebar toggles) */
.stApp {{
    background: url('{BACKGROUND_URL}') no-repeat top right;
    background-size: contain;
    background-attachment: fixed;
}}

/* Sidebar default white and padding */
.stSidebar {{
    background-color: #fff;
    padding: 14px;
}}

/* Visible borders for filter controls */
.stSidebar .stSelectbox, .stSidebar .stMultiselect, .stSidebar .stRadio, .stSidebar .stCheckbox, .stSidebar .stFileUploader {{
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 8px;
    margin-bottom: 12px;
    background-color: #fff;
}}

/* Title & layout */
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

/* Chat bubbles */
.chat-bubble-user {{
    text-align: right;
    background: rgba(220,248,198,0.95);
    padding: 12px;
    border-radius: 15px 15px 0 15px;
    margin: 6px;
    display: inline-block;
    max-width: 80%;
    color: {text_color};
}}
.chat-bubble-ai {{
    text-align: left;
    background: rgba(240,242,246,0.95);
    padding: 12px;
    border-radius: 15px 15px 15px 0;
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

/* Bottom bar */
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

/* small responsive tweaks */
@media (max-width: 800px) {{
    .title-box h1 {{ font-size: 28px; }}
    .gsk-logo img {{ width: 110px; }}
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# small JS to observe sidebar expand/collapse and adjust background-size for better visibility
SIDEBAR_JS = """
<script>
(function() {
  function setBgSize(expanded) {
    const el = document.querySelector('.stApp');
    if (!el) return;
    if (expanded) {
      el.style.backgroundSize = 'auto 90%';
    } else {
      el.style.backgroundSize = 'auto 100%';
    }
  }
  // find sidebar
  const sidebar = document.querySelector('[data-testid="stSidebar"]');
  if (!sidebar) return;
  // initial
  setBgSize(sidebar.getAttribute('aria-expanded') === 'true');
  // observer
  const mo = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.attributeName === 'aria-expanded') {
        setBgSize(sidebar.getAttribute('aria-expanded') === 'true');
      }
    }
  });
  mo.observe(sidebar, { attributes: true });
})();
</script>
"""
st.markdown(SIDEBAR_JS, unsafe_allow_html=True)

# small JS to auto-scroll chat container to bottom; chat container will have id 'chat-container'
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
# Top-left language selector (kept visible)
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
# Data definitions
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

# ----------------------------
# Sidebar content (brand + filters) with bordered controls
# ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown('<div style="font-weight:800; margin-bottom:8px;">Filters & Options</div>', unsafe_allow_html=True)
    brand = st.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
    # brand image under brand selector
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
# PDF upload & summarize moved to main interface (above chat)
# ----------------------------
st.subheader("📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
show_more_toggle = st.checkbox("Show full PDF text", value=False)
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text if show_more_toggle else full_text[:1000] + "..."
        # extract likely references
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else ""
        st.success("✅ PDF processed")
        if st.button("Summarize PDF"):
            text_for_summary = full_text[:6000]
            summary_prompt = (
                f"Summarize this medical document for sales reps for {brand}. Focus on actionable findings, key results and practical recommendations. Language: {language}.\n\n"
                + text_for_summary
            )
            try:
                summary_resp = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{"role": "system", "content": "You are a concise medical summarizer for sales teams."},
                              {"role": "user", "content": summary_prompt}],
                    temperature=0.3,
                )
                st.session_state.pdf_summary = summary_resp.choices[0].message.content
            except Exception as e:
                st.session_state.pdf_summary = f"⚠️ Error summarizing PDF: {e}"
            st.markdown("### 📑 PDF Summary")
            st.write(st.session_state.pdf_summary)
            if st.session_state.extracted_medical_ref:
                st.info(f"📚 Extracted references: {st.session_state.extracted_medical_ref}")
    except Exception as e:
        st.error(f"PDF error: {e}")

st.markdown("### PDF Preview / Summary")
st.write(st.session_state.uploaded_pdf_text or "No PDF uploaded.")

# ----------------------------
# Chat display area (give container id for JS scrolling)
# ----------------------------
st.subheader("💬 Chatbot Interface")
# We render the chat inside a div with fixed height and overflow so scroll works
chat_style = """
<div id="chat-container" style="height:60vh; overflow:auto; padding:12px; border-radius:8px; background: rgba(255,255,255,0.6);">
"""
chat_end = "</div>"
# build chat html
def render_chat_html() -> str:
    html = chat_style
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n", "<br>")
        for step in APACT_STEPS:
            content = content.replace(step, f"<span class='highlight'>{step}</span>")
        ts = msg.get("time", "")
        if msg.get("role") == "user":
            html += f"<div class='chat-bubble-user'>{content}<br><span style='font-size:10px;color:gray'>{ts}</span></div>"
        else:
            audio_html = ""
            if msg.get("audio"):
                audio_html = f"<br><audio controls style='margin-top:8px;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
            html += f"<div class='chat-bubble-ai'>{content}<br><span style='font-size:10px;color:gray'>{ts}</span>{audio_html}</div>"
    html += chat_end
    return html

st.markdown(render_chat_html(), unsafe_allow_html=True)
# inject scroll JS so it always scrolls to bottom after chat renders
st.markdown(SCROLL_JS, unsafe_allow_html=True)

# ----------------------------
# TTS helper (edge-tts) — strips punctuation for more natural voice
# ----------------------------
def synthesize_tts_base64(text: str, lang: str) -> Optional[str]:
    text = (text or "").strip()
    if not text:
        return None
    # remove characters that produce choppy speech when spoken by TTS
    clean_text = re.sub(r'([;:{}\[\]\*\^<>@#\$%&\|~_=/\\\+])', '', text)
    # keep sentence punctuation but remove trailing excessive punctuation
    clean_text = re.sub(r'\s+', ' ', clean_text)
    # Optionally remove commas/semicolons to make it less choppy:
    clean_text = clean_text.replace(',', '')
    # select voice
    voice = "ar-EG-SalmaNeural" if lang == "العربية" else "en-US-JennyNeural"
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        async def _save():
            comm = edge_tts.Communicate(clean_text, voice=voice)
            await comm.save(tmp_name)
        asyncio.run(_save())
        with open(tmp_name, "rb") as f:
            b = f.read()
        return base64.b64encode(b).decode("utf-8")
    except Exception as e:
        # log and return None if TTS fails
        st.warning(f"⚠️ TTS failed: {e}")
        return None
    finally:
        try:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
        except Exception:
            pass

# ----------------------------
# Groq call with exponential backoff and fallback model
# ----------------------------
def call_groq_with_retry(prompt: str, language: str, max_retries: int = 4, base_delay: int = 2) -> str:
    models = [
        "meta-llama/llama-4-scout-17b-16e-instruct",  # primary
        "meta-llama/llama-4-scout-13b-instruct",      # fallback smaller
    ]
    last_err = None
    for model in models:
        for attempt in range(1, max_retries + 1):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": f"You are a helpful sales assistant that responds in {language}."},
                        {"role": "user", "content": prompt},
                    ],
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
                    # non-retryable error: return message
                    return f"⚠️ Error generating response: {e}"
        # try next model after retries exhausted
        st.info(f"Switching to fallback model after {max_retries} attempts: {model}")
    # all attempts failed
    return f"⚠️ Failed to get response: {last_err}"

# ----------------------------
# Bottom bar: input, clear, download (fixed)
# ----------------------------
# We'll present the bottom controls using columns to layout input + buttons
st.markdown(
    """
    <div class="bottom-bar">
      <div style="flex:1;">
      <!-- placeholder for Streamlit form -->
      </div>
      <div style="display:flex; gap:10px;">
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message... / اكتب رسالتك هنا", key="user_input_box")
    submitted = st.form_submit_button("➤")

# ----------------------------
# Handle submission
# ----------------------------
if submitted and user_input.strip():
    # append user message
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})
    # re-render chat
    st.markdown(render_chat_html(), unsafe_allow_html=True)
    st.markdown(SCROLL_JS, unsafe_allow_html=True)

    # build prompt
    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)
    medical_ref_str = st.session_state.extracted_medical_ref or "None"
    pdf_summary_text = st.session_state.pdf_summary or "None"
    pdf_preview = st.session_state.uploaded_pdf_text or "No PDF uploaded."

    prompt_lines = [
        f"Language: {language}",
        f"User input: {user_input}",
        f"Brand: {brand}",
        f"RACE Segment: {segment}",
        f"Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}",
        f"Objective: {objective}",
        f"Doctor Specialty: {specialty}",
        f"HCP Persona: {persona}",
        f"Medical Reference(s): {medical_ref_str}",
        "",
        "Uploaded PDF (preview):",
        pdf_preview,
        "",
        "PDF AI Summary (if available):",
        pdf_summary_text,
        "",
        "Approved Sales Approaches:",
        approaches_str,
        "",
        "Sales Call Flow Steps:",
        flow_str,
        "",
        "Use APACT (Acknowledge → Probing → Action → Confirm → Transition) technique for handling objections.",
        f"Response Length: {response_length}",
        f"Response Tone: {response_tone}",
        "Provide actionable sales-call suggestions and a short 3–6 line script the rep can say. Clearly label APACT steps in the script."
    ]
    prompt = "\n".join(prompt_lines)

    # call Groq with retries
    ai_output = call_groq_with_retry(prompt, language)

    # synthesize TTS
    audio_b64 = synthesize_tts_base64(ai_output, language)

    # append AI
    st.session_state.chat_history.append({"role": "ai", "content": ai_output, "time": datetime.now().strftime("%H:%M"), "audio": audio_b64})

    # render chat and scroll
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
            st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Responses.docx")

# ----------------------------
# Brand leaflet link
# ----------------------------
st.markdown(f"[📄 Brand Leaflet - {brand}]({gsk_brands[brand]})")
