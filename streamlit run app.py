# app.py
import os
import re
import time
import base64
import tempfile
import asyncio
from typing import Optional
from datetime import datetime
from io import BytesIO, BytesIO as io_bytes

import streamlit as st
from PIL import Image, ImageStat
import requests
import PyPDF2

# Try import edge_tts (text-to-speech). If not available, we will continue without audio.
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except Exception:
    EDGE_TTS_AVAILABLE = False

# Try import Groq (AI). If not available, app continues in degraded mode.
try:
    import groq
    from groq import Groq
    GROQ_AVAILABLE = True
except Exception:
    Groq = None
    GROQ_AVAILABLE = False

# Optional Word export
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
# GROQ API key (prefer env var)
# ----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")  # set your key in env or here for testing
client = Groq(api_key=GROQ_API_KEY) if (GROQ_API_KEY and GROQ_AVAILABLE) else None
if client is None and GROQ_API_KEY:
    # If user set key but groq not installed, warn
    if not GROQ_AVAILABLE:
        st.warning("Groq package not installed; AI disabled. Install `groq` to enable model calls.")
else:
    if client is None:
        st.info("AI (Groq) not configured. Set GROQ_API_KEY and install groq to enable AI features.")

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
# Assets & UI styling
# ----------------------------
# Replace this with your background URL if you want
BACKGROUND_URL = (
    "https://www.shutterstock.com/image-photo/excited-girl-white-shirt-using-260nw-708132598.jpg"
)
# GSK logo
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"

def safe_get_brightness(url: str) -> int:
    try:
        r = requests.get(url, timeout=6)
        img = Image.open(BytesIO(r.content)).convert("L")
        stat = ImageStat.Stat(img)
        return int(stat.mean[0])
    except Exception:
        return 255

brightness = safe_get_brightness(BACKGROUND_URL)
text_color = "black" if brightness > 130 else "white"

# CSS with placeholder for background URL
CSS = f"""
<style>
.stApp {
background: url('{BACKGROUND_URL}') no-repeat top right;
background-size: calc(120% - 280px) auto;
transition: background-size 0.3s ease;
}
/* Keep sidebar white for readability */
[data-testid="stSidebar"] > div:first-child {
  background: rgba(255,255,255,0.96);
  padding: 12px;
  border-radius: 8px;
}

/* Sidebar control borders (visible) */
[data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stMultiselect,
[data-testid="stSidebar"] .stRadio, [data-testid="stSidebar"] .stCheckbox,
[data-testid="stSidebar"] .stFileUploader {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 8px;
  margin-bottom: 12px;
  background-color: #fff;
}

/* GSK logo top-right moved down ~60px */
.gsk-logo {
  position: flixed;
  top: 60px;
  right: 16px;
  z-index: 1200;
}

/* Title box */
.title-box {
  background: rgba(255,255,255,0.92);
  padding: 30px;
  border-radius: 14px;
  text-align: center;
  max-width: 85%;
  margin: 12px auto;
}
.title-box h1 { margin: 0; font-size: 38px; font-weight: 800; }
.title-box p { margin: 8px 0 0 0; font-size: 16px; }

/* PDF summary box */
.pdf-summary-box {
  background: rgba(255,255,255,0.94);
  padding: 14px;
  border-radius: 12px;
  margin-bottom: 12px;
}

/* Chat container */
.chat-container {
  height: 58vh;
  overflow:auto;
  padding:12px;
  border-radius:10px;
  background: rgba(255,255,255,0.7);
}

/* Chat bubbles (responsive) */
.chat-bubble-user, .chat-bubble-ai {
  display:block;
  padding:12px;
  margin:8px 0;
  border-radius:12px;
  max-width: 92%;
  word-wrap: break-word;
  color: #000;
}
.chat-bubble-user { background: #eef9e6; margin-left:auto; }
.chat-bubble-ai { background: #f5f7fa; margin-right:auto; }

/* inline pdf snippet inside AI bubble */
.pdf-summary-inline {
  margin-top:8px;
  background: rgba(255,255,255,0.96);
  padding:10px;
  border-radius:8px;
}

/* bottom fixed input bar */
.bottom-fixed {
  position: fixed;
  bottom: 12px;
  left: 16px;
  right: 16px;
  z-index: 2000;
  background: rgba(255,255,255,0.95);
  padding:10px;
  border-radius:12px;
  display:flex;
  gap:10px;
  align-items:center;
  box-shadow: 0 6px 18px rgba(0,0,0,0.06);
}
.bottom-fixed input[type="text"] {
  flex:1;
  padding:10px 12px;
  border-radius:10px;
  border:1px solid #ddd;
}
.bottom-fixed button {
  min-width:120px;
  padding:8px 12px;
  border-radius:8px;
  border:none;
  background:#ff8c00;
  color:white;
  font-weight:600;
}

/* small screens */
@media (max-width: 600px) {
  .title-box h1 { font-size: 26px; }
  .gsk-logo img { width: 90px; }
  .chat-container { height: 50vh; }
  .bottom-fixed { left:8px; right:8px; bottom:8px; }
}

/* highlights for AI-rendered content */
.highlight-step { font-weight:700; color:#000; }
.highlight-figure { font-weight:700; color:#d35400; }
</style>
"""
CSS = CSS.replace("__BG_URL__", BACKGROUND_URL)
st.markdown(CSS, unsafe_allow_html=True)

# Small JS: adjust background-size based on sidebar expand/collapse, and auto-scroll chat
SIDEBAR_JS = """
<script>
(function(){
  const sidebar = document.querySelector('[data-testid="stSidebar"]');
  const app = document.querySelector('.app-bg');
  if(!sidebar || !app) return;
  function updateBg() {
    const expanded = sidebar.getAttribute('aria-expanded') === 'true';
    app.style.backgroundSize = expanded ? 'auto 85%' : 'auto 100%';
  }
  updateBg();
  new MutationObserver(updateBg).observe(sidebar, { attributes: true });
})();
</script>
"""
st.markdown(SIDEBAR_JS, unsafe_allow_html=True)

SCROLL_JS = """
<script>
function scrollChat() {
  const el = document.getElementById('chat-container');
  if (el) el.scrollTop = el.scrollHeight;
}
setTimeout(scrollChat, 200);
</script>
"""

# Render GSK logo and title
st.markdown(f'<div class="gsk-logo"><img src="{GSK_LOGO_URL}" width="140" /></div>', unsafe_allow_html=True)
st.markdown('<div class="title-box"><h1>💡 AI Sales Call Assistant</h1><p>Powered by AI to equip sales reps for smarter HCP conversations</p></div>', unsafe_allow_html=True)
st.markdown('<p style="text-align:center;font-weight:600;">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Data & updated call flow / APACT
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

race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy", "Accessibility/Logistics", "Patient reluctance", "Other clinical doubts"]
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
# updated sales call flow per your request
sales_call_flow = ["Prepare the call", "Engage", "Create opportunities", "Impact GSO (Good sell outcome)", "Influence", "Analyze / Post call analysis"]
APACT_STEPS = ["Acknowledge", "Probing", "Action", "Confirm", "Transition"]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist", "Rheumatologist", "Internal Medicine", "Diabetologist", "Neurologist", "Pneumologist"]

# ----------------------------
# Sidebar (filters + brand image)
# ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown('<div style="font-weight:800; margin-bottom:8px;">Filters & Options</div>', unsafe_allow_html=True)
    brand = st.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
    # brand image under the brand name
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try:
            resp = requests.get(img_path, timeout=6)
            img = Image.open(BytesIO(resp.content))
            st.image(img, width=180)
        except Exception:
            st.image("https://via.placeholder.com/180x90.png?text=No+Image", width=180)
    segment = st.selectbox("Select RACE Segment / اختر شريحة RACE", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective / اختر الهدف", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", options=specialties)
    persona = st.selectbox("Select HCP Persona / اختر شخصية الطبيب", options=personas)
    response_length = st.selectbox("Response Length / اختر طول الرد", ["Short", "Medium", "Long"])
    response_tone = st.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])
    interface_mode = st.radio("Interface Mode / اختر واجهة", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# ----------------------------
# PDF Upload & Summarization
# ----------------------------
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:2000] + "..." if len(full_text) > 2000 else full_text
        # extract likely refs
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"

        # Summarize in safe chunks. If client present use AI; otherwise fallback
        chunk_size = 4000
        chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        summaries = []
        if client:
            for i, chunk in enumerate(chunks[:3]):  # limit to first 3 chunks
                try:
                    resp = client.chat.completions.create(
                        model="meta-llama/llama-4-scout-13b-instruct",
                        messages=[{"role":"system","content":"You summarize clinical/medical text into concise bullet points for sales reps."},
                                  {"role":"user","content":chunk}],
                        temperature=0.25
                    )
                    s = resp.choices[0].message.content.strip()
                    if s:
                        summaries.append(s)
                except Exception as e:
                    # if one chunk fails, continue with others
                    summaries.append("")  # keep alignment
        else:
            # fallback heuristic: take first sentences with keywords and first 5 sentences
            sentences = re.split(r'(?<=[.?!])\s+', full_text)
            important = []
            for s in sentences:
                if len(important) >= 6:
                    break
                if re.search(r'\b(significant|increase|decrease|risk|efficacy|%|percent|patients|study)\b', s, flags=re.I):
                    important.append(s.strip())
            if not important:
                important = sentences[:6]
            summaries = ["\n".join(important)]
        st.session_state.pdf_summary = "\n".join([s for s in summaries if s]).strip()
        st.success("✅ PDF processed.")
    except Exception as e:
        st.error("PDF processing error: " + str(e))

# show collapsible PDF summary box if present
if st.session_state.pdf_summary:
    with st.expander("📑 PDF Summary (expand / collapse)", expanded=False):
        lines = [ln.strip() for ln in st.session_state.pdf_summary.split("\n") if ln.strip()]
        bullets = "\n".join([f"- {ln}" for ln in lines])
        st.markdown(f'<div class="pdf-summary-box">{bullets}</div>', unsafe_allow_html=True)
        if st.session_state.extracted_medical_ref:
            st.info(f"📚 Extracted references: {st.session_state.extracted_medical_ref}")

# ----------------------------
# Utilities: highlight/render
# ----------------------------
def md_bold_to_html(s: str) -> str:
    # convert **bold** style to <b> for display
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)

def highlight_figures(s: str) -> str:
    # highlight percent figures
    for fig in re.findall(r"\d+\.?\d*%", s):
        s = s.replace(fig, f"<span class='highlight-figure'>{fig}</span>")
    return s

def render_chat():
    html = '<div id="chat-container" class="chat-container">'
    for msg in st.session_state.chat_history:
        content = msg["content"]
        # convert markdown bold -> html <b>
        content = md_bold_to_html(content)
        content = highlight_figures(content)
        # ensure line breaks
        content = content.replace("\n", "<br>")
        if msg["role"] == "user":
            html += f"<div class='chat-bubble-user'>{content}</div>"
        else:
            # include inline PDF summary if available
            pdf_html = ""
            if st.session_state.pdf_summary:
                pdf_lines = [f"- {ln.strip()}" for ln in st.session_state.pdf_summary.split("\n") if ln.strip()]
                pdf_html = "<div class='pdf-summary-inline'>" + "<br>".join(pdf_lines) + "</div>"
            audio_html = ""
            if msg.get("audio"):
                audio_html = f"<br><audio controls style='margin-top:8px;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
            html += f"<div class='chat-bubble-ai'>{content}{pdf_html}{audio_html}</div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)
    st.markdown(SCROLL_JS, unsafe_allow_html=True)

# initial chat render
st.markdown("<h3>💬 Chat</h3>", unsafe_allow_html=True)
render_chat()

# ----------------------------
# Humanized TTS (edge-tts) - returns base64 mp3 string or None
# ----------------------------
async def _edge_save_async(ssml_text: str, voice: str, outpath: str):
    comm = edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts_base64(text: str, lang: str) -> Optional[str]:
    if not EDGE_TTS_AVAILABLE:
        return None
    if not text or not text.strip():
        return None
    # Remove problematic characters for read-out, but keep sentence endings.
    safe_text = re.sub(r'([@#\$%&\*\^_=<>/\\\[\]\{\}\|~`])', '', text)
    # Insert small SSML prosody segments for natural pauses
    sentences = re.split(r'(?<=[.?!])\s+', safe_text)
    ssml_parts = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        # add small pause
        ssml_parts.append(f"<prosody rate='medium'>{s}<break time='0.55s'/></prosody>")
    ssml = "<speak>" + " ".join(ssml_parts) + "</speak>"
    voice = "ar-EG-SalmaNeural" if lang == "العربية" else "en-US-AriaNeural"
    tmpf = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name = tmpf.name
    tmpf.close()
    try:
        asyncio.run(_edge_save_async(ssml, voice, tmp_name))
        with open(tmp_name, "rb") as f:
            b = f.read()
        return base64.b64encode(b).decode("utf-8")
    except Exception as e:
        # if TTS fails, return None but do not crash
        st.warning(f"TTS generation failed: {e}")
        return None
    finally:
        try:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
        except Exception:
            pass

# ----------------------------
# Build AI prompt ensuring sales flow & APACT usage
# ----------------------------
def build_prompt(user_input: str, language: str) -> str:
    pdf_summary = st.session_state.pdf_summary or ""
    refs = st.session_state.extracted_medical_ref or "None"
    instructions = [
        "Use the uploaded PDF summary and extracted references as primary clinical sources where applicable.",
        "When making clinical claims, cite reference names if available.",
        "Provide actionable sales suggestions and a short 'Sample script' (3–6 lines) the rep can say.",
        "Match the requested tone and response length."
    ]
    # enforce sales call flow formatting when user asks for call flow
    if re.search(r"\b(sales call flow|call flow|sales flow|sales steps)\b", user_input, flags=re.I):
        steps_str = "\n".join([f"- **{s}**: 1-2 short actionable suggestions." for s in sales_call_flow])
        instructions.append(f"When asked for sales call flow, return the steps exactly in this order as bold bullets:\n{steps_str}")
    # enforce APACT when user asks about objections
    if re.search(r"\b(objection|concern|barrier|hesitat|not convinced|resist)\b", user_input, flags=re.I):
        instructions.append("When handling objections, structure the response using APACT: **Acknowledge**, **Probing**, **Action**, **Confirm**, **Transition**. Bold the APACT titles.")
    # combine
    prompt = "\n".join([
        f"Language: {language}",
        f"User input: {user_input}",
        f"Brand: {brand}",
        f"RACE Segment: {segment}",
        f"Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}",
        f"Objective: {objective}",
        f"Doctor Specialty: {specialty}",
        f"HCP Persona: {persona}",
        "",
        "Instructions:",
        *instructions,
        "",
        "PDF Summary (if any):",
        pdf_summary or "None",
        "",
        "Extracted References:",
        refs,
        "",
        f"Response Tone: {response_tone}, Length: {response_length}"
    ])
    return prompt

# ----------------------------
# Call Groq with simple retry/fallback
# ----------------------------
def call_groq_with_retry(prompt: str, language: str, max_retries: int = 3) -> str:
    if client is None:
        return "⚠️ AI service not configured. Set GROQ_API_KEY and install groq to enable AI responses."
    models = ["meta-llama/llama-4-scout-17b-16e-instruct", "meta-llama/llama-4-scout-13b-instruct"]
    last_err = None
    for model in models:
        for attempt in range(1, max_retries + 1):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": f"You are a helpful sales assistant that responds in {language}."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7
                )
                return resp.choices[0].message.content
            except Exception as e:
                last_err = e
                msg = str(e).lower()
                if any(x in msg for x in ["over capacity", "503", "internal_server_error"]):
                    wait = 2 ** attempt
                    time.sleep(wait)
                    continue
                if "authentication" in msg or "unauthorized" in msg:
                    return "⚠️ Authentication error with Groq. Check GROQ_API_KEY."
                # for other errors break to try fallback model
                break
    return f"⚠️ AI call failed after retries. Last error: {last_err}"

# ----------------------------
# Bottom input form (no experimental_rerun)
# ----------------------------
st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
with st.form("user_form", clear_on_submit=True):
    user_text = st.text_input("Type your message here…", key="user_input", placeholder="Ask about sales call steps, objections handling, sample scripts…")
    submitted = st.form_submit_button("Send")

if submitted and user_text and user_text.strip():
    # Append user message
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_text.strip(),
        "time": datetime.now().strftime("%H:%M")
    })
    # Build prompt and call AI (non-blocking to UI)
    prompt = build_prompt(user_text.strip(), st.session_state.language)
    ai_text = call_groq_with_retry(prompt, st.session_state.language)
    # Synthesize TTS if available (returns base64), don't crash if it fails
    audio_b64 = None
    try:
        audio_b64 = synthesize_tts_base64(ai_text, st.session_state.language) if EDGE_TTS_AVAILABLE else None
    except Exception:
        try:
            # last-ditch: smaller SSML via fallback function
            audio_b64 = synthesize_tts_base64(ai_text, st.session_state.language) if EDGE_TTS_AVAILABLE else None
        except Exception:
            audio_b64 = None
    # Append AI response
    st.session_state.chat_history.append({
        "role": "ai",
        "content": ai_text,
        "time": datetime.now().strftime("%H:%M"),
        "audio": audio_b64
    })
    # Re-render chat area (no rerun)
    render_chat()

# ----------------------------
# Bottom controls (Clear / Download)
# ----------------------------
cols = st.columns([1, 1])
with cols[0]:
    if st.button("🗑️ Clear Chat / مسح المحادثة"):
        st.session_state.chat_history = []
        st.session_state.uploaded_pdf_text = ""
        st.session_state.extracted_medical_ref = ""
        st.session_state.pdf_summary = ""
        # re-render cleared chat
        render_chat()
with cols[1]:
    if DOCX_AVAILABLE and st.session_state.chat_history:
        if st.button("📥 Download Chat as Word"):
            doc = Document()
            doc.add_heading("AI Sales Call Assistant Chat", 0)
            for msg in st.session_state.chat_history:
                role = "User" if msg["role"] == "user" else "AI"
                doc.add_paragraph(f"{role} [{msg.get('time','')}]")
                # plain-text the content
                content = re.sub(r"<[^>]+>", "", msg["content"])
                doc.add_paragraph(content)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            doc.save(tmp.name)
            tmp.close()
            with open(tmp.name, "rb") as f:
                data = f.read()
            b64 = base64.b64encode(data).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="chat_history.docx">⬇️ Download Chat History</a>'
            st.markdown(href, unsafe_allow_html=True)

# Quick helper button to append the GSK sales call flow (formatted)
if st.button("Show GSK Sales Call Flow"):
    flow_text = "\n".join([f"**{i+1}. {s}** — 1-2 short actions" for i, s in enumerate(sales_call_flow)])
    st.session_state.chat_history.append({
        "role": "ai",
        "content": flow_text,
        "time": datetime.now().strftime("%H:%M"),
        "audio": None
    })
    render_chat()

# Brand leaflet link at bottom
st.markdown(f"[📄 Brand Leaflet - {brand}]({gsk_brands.get(brand, '#')})")
