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
import edge_tts

# Groq client (optional)
try:
    import groq
    from groq import Groq
except Exception:
    Groq = None

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
# Replace with your key or set environment variable GROQ_API_KEY
# ----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")  # set in environment or replace here (not recommended)
client = Groq(api_key=GROQ_API_KEY) if (GROQ_API_KEY and Groq is not None) else None

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
# Assets & styling variables
# ----------------------------
# Background image (external URL). Keep using your external link; update if needed.
BACKGROUND_URL = (
    "https://www.shutterstock.com/image-photo/excited-girl-white-shirt-using-260nw-708132598.jpg"
)
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"

def get_brightness(url: str) -> int:
    try:
        r = requests.get(url, timeout=6)
        img = Image.open(BytesIO(r.content)).convert("L")
        stat = ImageStat.Stat(img)
        return int(stat.mean[0])
    except Exception:
        return 255

brightness = get_brightness(BACKGROUND_URL)
text_color = "black" if brightness > 130 else "white"

# ----------------------------
# CSS + JS (responsive background that adapts to sidebar expand/collapse)
# ----------------------------
CSS = f"""
<style>
/* App background & placement */
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-attachment: fixed;
  background-size: auto 150%;
  transition: background-size 0.18s ease;
}}

/* Sidebar style (white, visible borders on controls) */
[data-testid="stSidebar"] > div:first-child {{
  background: #ffffff;
  padding: 10px;
  border-left: 0;
}}
/* border-like appearance for common controls in sidebar */
[data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stMultiselect,
[data-testid="stSidebar"] .stRadio, [data-testid="stSidebar"] .stCheckbox,
[data-testid="stSidebar"] .stFileUploader {{
  border: 1px solid #e6e6e6;
  border-radius: 10px;
  padding: 8px;
  margin-bottom: 10px;
  background-color: #dddd;
}}

/* Title box */
.title-box {{
  background: rgba(240,240,240,0.6);
  padding: 20px;
  border-radius: 14px;
  text-align: center;
  max-width: 75%;
  margin: 12px auto;
}}
.title-box h1 {{ margin:0; font-size:36px; font-weight:800; color:#000; }}
.title-box p {{ margin:6px 0 0 0; font-size:20px; color:#000; }}

/* PDF summary box style */
.pdf-summary-box {{
  background: rgba(255,255,255,0.9);
  padding: 14px;
  border-radius: 12px;
  margin-bottom: 12px;
  border: 1px solid #eee;
}}

/* Chat bubbles (responsive to message length) */
.chat-container {{
  height: 56vh;
  overflow:auto;
  padding:12px;
  border-radius:10px;
  background: rgba(255,255,255,0.8);
}}
.chat-bubble-user, .chat-bubble-ai {{
  display:block;
  padding:12px;
  border-radius:12px;
  margin:8px 0;
  max-width: 90%;
  word-wrap: break-word;
  color: black;
}}
.chat-bubble-user {{ background: #eef9e6; margin-left: auto; }}
.chat-bubble-ai {{ background: #f5f7fa; margin-right: auto; }}

/* Inline PDF snippet inside AI bubble */
.pdf-summary-inline {{
  margin-top:8px;
  background: rgba(255,255,255,0.97);
  padding:10px;
  border-radius:8px;
  border: 1px solid #eee;
}}

/* Bottom fixed input bar */
.bottom-bar {{
  position: fixed;
  bottom: 12px;
  left: 16px;
  right: 16px;
  z-index: 1200;
  background: rgba(255,255,255,0.98);
  padding:10px;
  border-radius:10px;
  box-shadow: 0 6px 20px rgba(0,0,0,0.06);
  display:flex;
  gap:12px;
  align-items:center;
}}
.bottom-bar input[type="text"] {{
  flex:1;
  padding:10px 12px;
  border-radius:8px;
  border:1px solid #ddd;
  outline:none;
}}
.bottom-bar button {{
  min-width:100px;
  padding:8px 12px;
  border-radius:8px;
  background:#ff8c00;
  color:white;
  border:none;
  font-weight:600;
  cursor:pointer;
}}

/* small screens */
@media (max-width: 430px) {{
  .title-box h1 {{ font-size:24px; }}
  .chat-container {{ height:48vh; }}
  .bottom-bar {{ left:8px; right:8px; bottom:8px; padding:8px; }}
}}

/* highlight for call steps / APACT / figures */
.highlight-step {{ font-weight:700; color:#000; }}
.highlight-figure {{ font-weight:700; color:#d35400; }}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)

# JS: observe sidebar expand/collapse and change background-size so image grows when sidebar collapsed
SIDEBAR_JS = """
<script>
(function(){
  const sidebar = document.querySelector('[data-testid="stSidebar"]');
  const app = document.querySelector('[data-testid="stAppViewContainer"]');
  if(!sidebar || !app) return;
  function updateBg() {
    const expanded = sidebar.getAttribute('aria-expanded') === 'true';
    app.style.backgroundSize = expanded ? 'auto 90%' : 'auto 100%';
  }
  updateBg();
  const mo = new MutationObserver(updateBg);
  mo.observe(sidebar, { attributes: true });
})();
</script>
"""
st.markdown(SIDEBAR_JS, unsafe_allow_html=True)

# small JS to auto-scroll the chat container when new messages appended
SCROLL_JS = """
<script>
function scrollChat(){
  const el = document.querySelector('.chat-container');
  if (el) el.scrollTop = el.scrollHeight;
}
setTimeout(scrollChat, 200);
</script>
"""

# top-left GSK logo and centered title
st.markdown(f'<div style="position:auto; left:30px; top:80px; z-index:1200;"><img src="{GSK_LOGO_URL}" width="140" /></div>', unsafe_allow_html=True)
st.markdown('<div class="title-box"><h1>💡 AI Sales Call Assistant</h1><p>Powered by AI to equip reps for smarter HCP conversations</p></div>', unsafe_allow_html=True)
st.markdown('<p style="text-align:center;font-weight:600;">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# GSK data / UI lists
# ----------------------------
gsk_brands = {
    "Shingrix": "https://www.shingrix.com/",
    "Trelegy": "https://www.trelegy.com/",
    "Zejula": "https://www.zejula.com/"
}
gsk_brands_images = {
    "Shingrix":"https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Trelegy":"https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
    "Zejula":"https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png"
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
gsk_approaches = [
    "Use data-driven evidence (local + global studies)",
    "Focus on patient outcomes & quality of life",
    "Leverage brief storytelling and peer endorsement",
    "Address practical barriers (access, scheduling, cost solutions)"
]
# Updated call flow per your request
sales_call_flow = [
    "Prepare the call",
    "Engage",
    "Create opportunities",
    "Impact GSO (Good sell outcome)",
    "Influence",
    "Analyze and post call analysis"
]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]
objectives = ["Awareness","Adoption","Retention"]
specialties = [
    "GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist",
    "Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"
]

# ----------------------------
# Sidebar: Filters & Options (brand image under brand selector)
# ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown('<div style="font-weight:800; margin-bottom:8px;">Filters & Options</div>', unsafe_allow_html=True)
    brand = st.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
    # brand image right under selector
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
    response_length = st.selectbox("Response Length / اختر طول الرد", ["Short","Medium","Long"])
    response_tone = st.selectbox("Response Tone / اختر نبرة الرد", ["Formal","Casual","Friendly","Persuasive"])
    interface_mode = st.radio("Interface Mode / اختر واجهة", ["Chatbot","Card Dashboard","Flow Visualization"])

# ----------------------------
# PDF Upload & Summarization (top area)
# ----------------------------
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:2000] + "..." if len(full_text) > 2000 else full_text
        # heuristically extract references
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"
        st.success("✅ PDF processed")

        # chunk & summarize to avoid token overflow
        chunk_size = 5000
        chunks = [full_text[i:i+chunk_size] for i in range(0, len(full_text), chunk_size)]
        summaries = []
        if client is None:
            st.warning("Groq client not configured: PDF auto-summarize unavailable. Set GROQ_API_KEY.")
            st.session_state.pdf_summary = ""
        else:
            for chunk in chunks:
                summary_prompt = (
                    "You are a concise medical summarizer for sales reps. Produce short bullet points with key results, "
                    "practical recommendations, and notable figures (include % if present). Keep it actionable.\n\n"
                ) + chunk[:6000]
                try:
                    resp = client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        messages=[{"role":"system","content":"You are a concise medical summarizer."},{"role":"user","content":summary_prompt}],
                        temperature=0.2
                    )
                    summaries.append(resp.choices[0].message.content)
                except Exception as e:
                    st.warning(f"Chunk summarization warning: {e}")
            st.session_state.pdf_summary = "\n".join(summaries).strip()

        # show collapsible summary box
        if st.session_state.pdf_summary:
            with st.expander("📑 PDF Summary (expand/collapse)", expanded=False):
                lines = [f"- {ln.strip()}" for ln in st.session_state.pdf_summary.split("\n") if ln.strip()]
                st.markdown(f'<div class="pdf-summary-box">{"<br>".join(lines)}</div>', unsafe_allow_html=True)
        if st.session_state.extracted_medical_ref:
            st.info(f"📚 Extracted references: {st.session_state.extracted_medical_ref}")

    except Exception as e:
        st.error("PDF error: " + str(e))

# ----------------------------
# Helper: render chat history
# ----------------------------
def highlight_and_inject(content: str) -> str:
    # Bold/enhance sales_call_flow and APACT steps inside the AI text
    for step in sales_call_flow:
        content = re.sub(rf"\b{re.escape(step)}\b", f"<span class='highlight-step'>{step}</span>", content)
    for ap in APACT_STEPS:
        content = re.sub(rf"\b{re.escape(ap)}\b", f"<span class='highlight-step'>{ap}</span>", content)
    for figure in re.findall(r"\d+\.?\d*%", content):
        content = content.replace(figure, f"<span class='highlight-figure'>{figure}</span>")
    return content

def build_ai_bubble_content(ai_text: str) -> str:
    content = ai_text.replace("\n", "<br>")
    content = highlight_and_inject(content)
    pdf_html = ""
    if st.session_state.pdf_summary:
        pdf_lines = [f"- {ln.strip()}" for ln in st.session_state.pdf_summary.split("\n") if ln.strip()]
        pdf_html = "<div class='pdf-summary-inline'>" + "<br>".join(pdf_lines[:8]) + ("<br>..." if len(pdf_lines) > 8 else "") + "</div>"
    return f"{content}{pdf_html}"

def render_chat_history():
    html = ""
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            html += f"<div class='chat-bubble-user'>{msg['content']}</div>"
        else:
            ai_content = build_ai_bubble_content(msg["content"])
            audio_html = ""
            if msg.get("audio"):
                audio_html = f"<br><audio controls style='margin-top:8px; width:100%;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
            html += f"<div class='chat-bubble-ai'>{ai_content}{audio_html}</div>"
    st.markdown(f'<div class="chat-container">{html}</div>', unsafe_allow_html=True)
    st.markdown(SCROLL_JS, unsafe_allow_html=True)

# initial render
st.markdown("<h3>💬 Chat</h3>", unsafe_allow_html=True)
render_chat_history()

# ----------------------------
# TTS (humanized) using edge-tts + SSML
# ----------------------------
async def _edge_save_async(ssml_text: str, voice: str, outpath: str):
    comm = edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts_humanized(text: str, lang: str) -> Optional[str]:
    if not text or not text.strip():
        return None
    # Clean punctuation that causes choppiness, but preserve sentence ends for pauses
    text = re.sub(r'[;:{}\[\]\*\^<>@#\$%&\|~_/\\]+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # split into sentences and build SSML with prosody + pauses
    sentences = re.split(r'(?<=[.?!])\s+', text)
    parts = []
    for s in sentences:
        s = s.strip()
        if s:
            parts.append(f"<prosody rate='medium'>{s}<break time='0.45s'/></prosody>")
    ssml = "<speak>" + " ".join(parts) + "</speak>"
    voice = "ar-EG-SalmaNeural" if lang == "العربية" else "en-US-AriaNeural"
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        asyncio.run(_edge_save_async(ssml, voice, tmp_name))
        with open(tmp_name, "rb") as f:
            b = f.read()
        return base64.b64encode(b).decode("utf-8")
    except Exception as e:
        st.warning("TTS generation failed: " + str(e))
        return None
    finally:
        try:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
        except Exception:
            pass

# ----------------------------
# Build assistant prompt (priority: PDF summary & references; enforce call flow & APACT)
# ----------------------------
def build_prompt(user_input: str, language: str) -> str:
    pdf_summary = st.session_state.pdf_summary or ""
    refs = st.session_state.extracted_medical_ref or "None"
    instructions = [
        "- Use uploaded PDF summary and extracted medical references as primary sources for clinical claims when possible.",
        "- Cite references when available (e.g., CDC, NEJM).",
        "- Provide a concise sample script (3–6 lines) labeled 'Sample script'.",
        "- Match requested tone and length."
    ]
    # If asking about the call flow
    if re.search(r"\b(sales call flow|call flow|sales flow|sales steps)\b", user_input, flags=re.I):
        steps_txt = ", ".join([f"**{s}**" for s in sales_call_flow])
        instructions.append(f"When user asks for 'sales call flow', return bold bullet points in this order: {steps_txt}, with 1-2 action lines each.")
    # If user asks about objections -> enforce APACT structure
    if re.search(r"\b(objection|concern|barrier|hesitat|not convinced|resist)\b", user_input, flags=re.I):
        instructions.append("When addressing objections, structure response using APACT: **Acknowledge**, **Probing**, **Action**, **Confirm**, **Transition**. Bold the APACT step titles.")
    instructions.append("Bold call steps, APACT titles, and any notable figures (e.g., 45%).")

    prompt_lines = [
        f"Language: {language}",
        f"User input: {user_input}",
        f"Brand: {brand}",
        f"RACE Segment: {segment}",
        f"Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}",
        f"Objective: {objective}",
        f"Doctor Specialty: {specialty}",
        f"HCP Persona: {persona}",
        "",
        "Instructions for the assistant:",
        *instructions,
        "",
        "PDF Summary (if any):",
        pdf_summary or "None",
        "",
        "Extracted References:",
        refs,
        "",
        f"Response Tone: {response_tone}, Length: {response_length}"
    ]
    return "\n".join(prompt_lines)

# ----------------------------
# Groq call with retries & fallback
# ----------------------------
def call_groq_with_retry(prompt: str, language: str, max_retries: int = 3, base_delay: int = 2):
    if client is None:
        return "⚠️ AI service not configured. Set GROQ_API_KEY in environment to enable AI generation."
    models = [
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "meta-llama/llama-4-scout-13b-instruct",
    ]
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
                    temperature=0.65
                )
                return resp.choices[0].message.content
            except Exception as e:
                last_err = e
                err_msg = str(e).lower()
                if "over capacity" in err_msg or "503" in err_msg or "internal_server_error" in err_msg:
                    wait = base_delay * (2 ** (attempt - 1))
                    st.warning(f"Model {model} busy. Retrying in {wait}s (attempt {attempt}/{max_retries})...")
                    time.sleep(wait)
                    continue
                if "authentication" in err_msg or "unauthorized" in err_msg:
                    return "⚠️ Authentication error with Groq. Please check GROQ_API_KEY."
                # other non-retriable errors: return message
                return f"⚠️ Error generating response: {e}"
        st.info(f"Switching to fallback model after {max_retries} attempts for {model}.")
    return f"⚠️ AI call failed after retries. Last error: {last_err}"

# ----------------------------
# Bottom input (fixed) - form to avoid duplicate boxes
# ----------------------------
with st.form("bottom_chat_form", clear_on_submit=True):
    user_text = st.text_input("Type your message... / اكتب رسالتك هنا", key="bottom_prompt_input", label_visibility="collapsed")
    submitted = st.form_submit_button("Send")

if submitted and user_text and user_text.strip():
    # append user message
    st.session_state.chat_history.append({"role":"user","content":user_text.strip(),"time":datetime.now().strftime("%H:%M")})
    render_chat_history()

    # build prompt and call AI
    prompt = build_prompt(user_text.strip(), st.session_state.language)
    ai_output = call_groq_with_retry(prompt, st.session_state.language)
    # synthesize TTS (best-effort)
    audio_b64 = synthesize_tts_humanized(ai_output, st.session_state.language)
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M"), "audio": audio_b64})
    render_chat_history()

# ----------------------------
# Bottom controls: Clear Chat and Export
# ----------------------------
cols = st.columns([1,1])
with cols[0]:
    if st.button("🗑️ Clear Chat / مسح المحادثة"):
        st.session_state.chat_history = []
        st.session_state.uploaded_pdf_text = ""
        st.session_state.extracted_medical_ref = ""
        st.session_state.pdf_summary = ""
        st.experimental_rerun()
with cols[1]:
    if DOCX_AVAILABLE and st.session_state.chat_history:
        if st.button("📥 Export Chat (.docx)"):
            doc = Document()
            doc.add_heading("AI Sales Call Assistant Chat History", 0)
            for msg in st.session_state.chat_history:
                role = "User" if msg["role"]=="user" else "AI"
                doc.add_paragraph(f"{role} [{msg.get('time','')}]:")
                # strip HTML from AI content for Word
                text_content = re.sub(r'<.*?>', '', msg["content"])
                doc.add_paragraph(text_content)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            doc.save(tmp.name)
            tmp.close()
            with open(tmp.name, "rb") as f:
                data = f.read()
            st.download_button("⬇️ Download .docx", data=data, file_name="chat_history.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

# quick button to show the sales call flow as a pre-built AI reply (convenience)
if st.button("Show GSK Sales Call Flow"):
    flow_lines = [f"**{s}**: Short actionable guidance for this step." for s in sales_call_flow]
    flow_text = "\n\n".join(flow_lines)
    st.session_state.chat_history.append({"role":"ai","content":flow_text,"time":datetime.now().strftime("%H:%M"), "audio": None})
    render_chat_history()

# brand leaflet link (footer)
st.markdown(f"[📄 Brand Leaflet - {brand}]({gsk_brands[brand]})")
