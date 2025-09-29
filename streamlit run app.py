# app.py
import os
import re
import time
import base64
import tempfile
import asyncio
from io import BytesIO, BytesIO as io_bytes
from datetime import datetime
from typing import Optional

import streamlit as st
from PIL import Image, ImageStat
import requests
import PyPDF2
import edge_tts

# Groq client (optional if you set API key)
try:
    import groq
    from groq import Groq
except Exception:
    Groq = None  # code will gracefully handle missing Groq package

# Optional Word download
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
# ---------- CONFIG ----------
# Replace with your key (recommended: set as environment variable)
# e.g. export GROQ_API_KEY="your_real_key"
# ----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")  # or set here as a string (not recommended)
if GROQ_API_KEY and Groq is not None:
    client = Groq(api_key=GROQ_API_KEY)
else:
    client = None

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
# Assets & variables
# ----------------------------
# Background image URL (use your preferred image)
BACKGROUND_URL = (
    "https://sdmntprpolandcentral.oaiusercontent.com/files/00000000-466c-620a-81c6-59c1f5c85484/raw?se=2025-09-29T08%3A50%3A13Z&sp=r&sv=2024-08-04&sr=b&scid=61b996f9-1aa8-5450-9322-8df6ba4be66c&skoid=76024c37-11e2-4c92-aa07-7e519fbe2d0f&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-29T03%3A57%3A08Z&ske=2025-09-30T03%3A57%3A08Z&sks=b&skv=2024-08-04&sig=k8xWpLn%2BpScPIMXS/CBwvn%2Blwsduznv0W2gDvCqsIRM%3D"
    "se=2025-09-27T16%3A42%3A35Z&sp=r&sv=2024-08-04&sr=b&scid=5258dbc1-6382-5fec-a8d5-ad7bcc18750b"
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

# ----------------------------
# Styles: background + layout + fixed bottom input
# ----------------------------
CSS = f"""
<style>
/* Use data-testid selectors for Streamlit structure */
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-attachment: fixed;
  background-size: contain;
}}
/* Sidebar white background to keep readability */
[data-testid="stSidebar"] > div:first-child {{
  background: rgba(255,255,255,0.98);
  padding: 12px;
}}
/* show visible borders around controls */
[data-testid="stSidebar"] .stSelectbox, [data-testid="stSidebar"] .stMultiselect,
[data-testid="stSidebar"] .stRadio, [data-testid="stSidebar"] .stCheckbox,
[data-testid="stSidebar"] .stFileUploader {{
  border: 1px solid #ddd;
  border-radius: 10px;
  padding: 6px;
  margin-bottom: 12px;
  background-color: #fff;
}}

/* Top-right logo (approx 3cm down) */
.gsk-logo {{
  position: fixed;
  top: 60px;
  right: 16px;
  z-index: 1200;
}}

/* Title box */
.title-box {{
  background: rgba(255,255,255,0.96);
  padding: 30px;
  border-radius: 16px;
  text-align: center;
  max-width: 90%;
  margin: 12px auto;
}}
.title-box h1 {{ margin:0; font-size:36px; font-weight:800; }}
.title-box p {{ margin:6px 0 0 0; font-size:18px; }}

/* PDF summary styled box */
.pdf-summary-box {{
  background: rgba(255,255,255,0.96);
  padding: 14px;
  border-radius: 12px;
  margin-bottom: 12px;
}}

/* Chat area container */
.chat-container {{
  height: 60vh;
  overflow: auto;
  padding: 12px;
  border-radius: 10px;
  background: rgba(255,255,255,0.7);
}}

/* Chat bubbles */
.chat-bubble-user, .chat-bubble-ai {{
  display:block;
  padding:12px;
  border-radius:12px;
  margin:8px 0;
  max-width: 92%;
  word-wrap: break-word;
  color: black; /* black text in bubbles */
}}
.chat-bubble-user {{ background: #eef9e6; margin-left:auto; }}
.chat-bubble-ai {{ background: #f5f7fa; margin-right:auto; }}

/* Inline PDF snippet inside AI bubble */
.pdf-summary-inline {{
  margin-top:8px;
  background: rgba(255,255,255,0.94);
  padding:10px;
  border-radius:8px;
}}

/* Bottom-fixed input bar */
.bottom-bar {{
  position: fixed;
  bottom: 12px;
  left: 16px;
  right: 16px;
  z-index: 2000;
  background: rgba(255,255,255,0.95);
  padding:10px;
  border-radius:12px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.08);
  display:flex;
  gap:12px;
  align-items:center;
}}
.bottom-bar input[type="text"] {{
  flex:1;
  padding:10px 12px;
  border-radius:10px;
  border:1px solid #ddd;
}}
.bottom-bar button {{
  min-width:110px;
  padding:8px 12px;
  background:#ff8c00;
  border:none;
  color:white;
  border-radius:8px;
  font-weight:600;
  cursor:pointer;
}}

/* mobile tweaks */
@media (max-width: 430px) {{
  .title-box h1 {{ font-size:24px; }}
  .gsk-logo img {{ width:90px; }}
  .chat-container {{ height: 52vh; }}
  .bottom-bar {{ left:8px; right:8px; bottom:8px; }}
}}
/* Highlight classes for generated content (call steps / APACT / figures) */
.highlight-step {{ font-weight:700; color:#000; }}
.highlight-figure {{ font-weight:700; color:#d35400; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# JS to adjust background-size when sidebar toggles (improves responsiveness)
SIDEBAR_JS = """
<script>
(function(){
  const sidebar = document.querySelector('[data-testid="stSidebar"]');
  const app = document.querySelector('[data-testid="stAppViewContainer"]');
  if(!sidebar || !app) return;
  function updateBg(){
    const expanded = sidebar.getAttribute('aria-expanded') === 'true';
    app.style.backgroundSize = expanded ? 'auto 85%' : 'auto 100%';
  }
  updateBg();
  new MutationObserver(updateBg).observe(sidebar, { attributes: true });
})();
</script>
"""
st.markdown(SIDEBAR_JS, unsafe_allow_html=True)

# small JS to auto-scroll chat container to bottom when new messages are added
SCROLL_JS = """
<script>
function scrollChat() {
  const el = document.getElementById('chat-container');
  if (el) el.scrollTop = el.scrollHeight;
}
setTimeout(scrollChat, 200);
</script>
"""
st.markdown(f'<div class="gsk-logo"><img src="{GSK_LOGO_URL}" width="140"></div>', unsafe_allow_html=True)

# ----------------------------
# Title + disclaimer
# ----------------------------
st.markdown(
    """
    <div class="title-box">
      <h1>💡 AI Sales Call Assistant</h1>
      <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown('<p style="text-align:center;font-weight:600;">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Language selector (keeps value in session_state)
# ----------------------------
st.session_state.language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"], index=0, horizontal=True, key="language_radio")

# ----------------------------
# Data definitions (brands, segments, etc.)
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
gsk_approaches = [
    "Use data-driven evidence (local + global studies)",
    "Focus on patient outcomes & quality of life",
    "Leverage brief storytelling and peer endorsement",
    "Address practical barriers (access, scheduling, cost solutions)"
]
sales_call_flow = ["Prepare", "Engage", "Create opportunity", "Influence", "Impact GSO", "Analyze / Post call analysis"]
APACT_STEPS = ["Acknowledge", "Probing", "Action", "Confirm", "Transition"]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = [
    "GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist",
    "Rheumatologist", "Internal Medicine", "Diabetologist", "Neurologist", "Pneumologist"
]

# ----------------------------
# Sidebar UI (filters & brand image under name)
# ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown('<div style="font-weight:800; margin-bottom:6px;">Filters & Options</div>', unsafe_allow_html=True)
    brand = st.selectbox("Select Brand", options=list(gsk_brands.keys()))
    # display brand image under brand name
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try:
            resp = requests.get(img_path, timeout=6)
            img = Image.open(BytesIO(resp.content))
            st.image(img, width=180)
        except Exception:
            st.image("https://via.placeholder.com/180x90.png?text=No+Image", width=180)

    segment = st.selectbox("Select RACE Segment", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty", options=specialties)
    persona = st.selectbox("Select HCP Persona", options=personas)
    response_length = st.selectbox("Response Length", options=["Short", "Medium", "Long"])
    response_tone = st.selectbox("Response Tone", options=["Formal", "Casual", "Friendly", "Persuasive"])
    interface_mode = st.radio("Interface Mode", options=["Chatbot", "Card Dashboard", "Flow Visualization"])

# ----------------------------
# PDF Upload & Summarization (top of interface)
# ----------------------------
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:2000] + "..." if len(full_text) > 2000 else full_text
        # heuristic extraction of references
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|JAMA|BMJ)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"
        st.success("✅ PDF processed")

        # Auto-summarize (if Groq configured)
        if client is None:
            st.warning("Groq client not configured: set GROQ_API_KEY to enable auto summarization.")
            st.session_state.pdf_summary = ""
        else:
            summary_prompt = (
                "Summarize the following medical document into concise bullet points with practical recommendations and any notable figures. "
                "Keep it actionable for a sales rep. \n\n"
            ) + full_text[:6000]
            try:
                resp = client.chat.completions.create(
                    model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{"role": "system", "content": "You are a concise medical summarizer."},
                              {"role": "user", "content": summary_prompt}],
                    temperature=0.25,
                )
                st.session_state.pdf_summary = resp.choices[0].message.content
            except Exception as e:
                st.warning(f"PDF summarization failed: {e}")
                st.session_state.pdf_summary = ""

        # Show collapsible summary
        if st.session_state.pdf_summary:
            with st.expander("📑 PDF Summary (expand/collapse)", expanded=False):
                st.markdown(f'<div class="pdf-summary-box">{"<br>".join([f"- {ln.strip()}" for ln in st.session_state.pdf_summary.split("\\n") if ln.strip()])}</div>', unsafe_allow_html=True)

        if st.session_state.extracted_medical_ref:
            st.info(f"📚 Extracted references: {st.session_state.extracted_medical_ref}")

    except Exception as e:
        st.error(f"PDF processing error: {e}")

# ----------------------------
# Chat display area (scrollable)
# ----------------------------
st.markdown("<h3>💬 Chat</h3>", unsafe_allow_html=True)
st.markdown('<div id="chat-container" class="chat-container">', unsafe_allow_html=True)

def highlight_and_inject(content: str) -> str:
    # highlight sales_call_flow steps and APACT steps and percent figures
    for step in sales_call_flow:
        content = re.sub(rf"\b{re.escape(step)}\b", f"<span class='highlight-step'>{step}</span>", content)
    for ap in APACT_STEPS:
        content = re.sub(rf"\b{re.escape(ap)}\b", f"<span class='highlight-step'>{ap}</span>", content)
    for figure in re.findall(r"\d+\.?\d*%", content):
        content = content.replace(figure, f"<span class='highlight-figure'>{figure}</span>")
    return content

def render_chat_history():
    html = ""
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            html += f"<div class='chat-bubble-user'>{msg['content']}</div>"
        else:
            ai_content = highlight_and_inject(msg["content"].replace("\n", "<br>"))
            # inline PDF summary in AI bubble if available
            pdf_html = ""
            if st.session_state.pdf_summary:
                lines = [f"- {ln.strip()}" for ln in st.session_state.pdf_summary.split("\n") if ln.strip()]
                pdf_html = "<div class='pdf-summary-inline'>" + "<br>".join(lines) + "</div>"
            audio_html = ""
            if msg.get("audio"):
                audio_html = f"<br><audio controls style='margin-top:8px;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
            html += f"<div class='chat-bubble-ai'>{ai_content}{pdf_html}{audio_html}</div>"
    st.markdown(html, unsafe_allow_html=True)
    st.markdown(SCROLL_JS, unsafe_allow_html=True)

# initial render
render_chat_history()
st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# TTS (humanized) using edge-tts (SSML + prosody)
# ----------------------------
async def edge_save_async(ssml_text: str, voice: str, outpath: str):
    comm = edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts_base64(text: str, lang: str) -> Optional[str]:
    if not text or not text.strip():
        return None
    # Clean text to avoid choppy output
    text = re.sub(r'([;:{}\[\]\*\^<>@#\$%&\|~_=/\\\+])', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # create SSML with small breaks between sentences
    sentences = re.split(r'(?<=[.?!])\s+', text)
    ssml_segments = [f"<prosody rate='medium'>{s}<break time='0.3s'/></prosody>" for s in sentences if s.strip()]
    ssml = "<speak>" + " ".join(ssml_segments) + "</speak>"
    voice = "ar-EG-SalmaNeural" if lang == "العربية" else "en-US-AriaNeural"
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        asyncio.run(edge_save_async(ssml, voice, tmp_name))
        with open(tmp_name, "rb") as f:
            b = f.read()
        return base64.b64encode(b).decode("utf-8")
    except Exception as e:
        st.warning(f"TTS failed: {e}")
        return None
    finally:
        try:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
        except Exception:
            pass

# ----------------------------
# Build prompt function (enforce sales flow & APACT when relevant)
# ----------------------------
def build_prompt(user_input: str, language: str) -> str:
    pdf_summary = st.session_state.pdf_summary or ""
    refs = st.session_state.extracted_medical_ref or "None"
    instructions = [
        "- Use the uploaded PDF summary and extracted medical references as primary sources for clinical claims where applicable.",
        "- Cite reference names when possible (e.g., CDC, NEJM) and include short actionable takeaways for reps.",
        "- Provide a short 'Sample script' (3-6 lines) the rep can say.",
        "- Match the requested tone and length."
    ]
    # If asking about sales call flow -> enforce GSK flow as bold bullets and short guidance
    if re.search(r"\b(sales call flow|call flow|sales flow|sales steps)\b", user_input, flags=re.I):
        steps_text = ", ".join([f"**{s}**" for s in sales_call_flow])
        instructions.append(f"When asked for 'sales call flow', return the steps as bold bullet points in this exact order: {steps_text}. Provide 1-2 short action lines per step.")
    # If the user mentions objections/barrier terms -> enforce APACT
    if re.search(r"\b(objection|concern|barrier|hesitat|not convinced|resist)\b", user_input, flags=re.I):
        instructions.append("When handling objections, structure the response using APACT: **Acknowledge**, **Probing**, **Action**, **Confirm**, **Transition**. Bold the APACT step titles.")
    # Always ask to bold steps, APACT, and notable figures
    instructions.append("Bold sales steps, APACT titles, and any notable numeric figures (e.g., 45%).")
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
        "Instructions:",
        *instructions,
        "",
        "PDF Summary (if any):",
        pdf_summary or "None",
        "",
        "Extracted references:",
        refs,
        "",
        f"Response length: {response_length}, tone: {response_tone}"
    ]
    return "\n".join(prompt_lines)

# ----------------------------
# Groq call with retries
# ----------------------------
def call_groq_with_retry(prompt: str, language: str, max_retries: int = 3, base_delay: int = 2):
    if client is None:
        return "⚠️ AI service not configured (GROQ_API_KEY missing). Please set GROQ_API_KEY in the environment."
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
                    temperature=0.7
                )
                return resp.choices[0].message.content
            except Exception as e:
                last_err = e
                err_msg = str(e).lower()
                # retry on capacity issues
                if "over capacity" in err_msg or "503" in err_msg or "internal_server_error" in err_msg:
                    wait = base_delay * (2 ** (attempt - 1))
                    st.warning(f"Model {model} busy. Retrying in {wait}s (attempt {attempt}/{max_retries})...")
                    time.sleep(wait)
                    continue
                if "authentication" in err_msg or "unauthorized" in err_msg:
                    return "⚠️ Authentication error with Groq. Check GROQ_API_KEY."
                return f"⚠️ Error generating response: {e}"
        st.info(f"Switching to fallback model after {max_retries} attempts for {model}.")
    return f"⚠️ Failed after retries: {last_err}"

# ----------------------------
# Bottom prompt (single form) - fixed at bottom via CSS
# ----------------------------
# Use a Streamlit form for accessibility and to avoid duplicated inputs
with st.form("bottom_chat_form", clear_on_submit=True):
    user_text = st.text_input("Type your message...", key="bottom_prompt_input", label_visibility="collapsed")
    submitted = st.form_submit_button("Send")

# ----------------------------
# Handle submission
# ----------------------------
if submitted and user_text and user_text.strip():
    # append user message
    st.session_state.chat_history.append({"role": "user", "content": user_text.strip(), "time": datetime.now().strftime("%H:%M")})
    # build prompt
    prompt = build_prompt(user_text.strip(), st.session_state.language)
    # call model
    ai_output = call_groq_with_retry(prompt, st.session_state.language)
    # synthesize TTS audio (more natural SSML voice)
    audio_b64 = synthesize_tts_base64(ai_output, st.session_state.language)
    # append ai response
    st.session_state.chat_history.append({"role": "ai", "content": ai_output, "time": datetime.now().strftime("%H:%M"), "audio": audio_b64})
    # rerender chat area
    render_chat_history()
    # keep page scrolled to bottom
    st.experimental_rerun()

# ----------------------------
# Bottom controls area (Clear, Download)
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
# Quick "Sales Flow" button (optional convenience)
# ----------------------------
if st.button("Show GSK Sales Call Flow"):
    # create bold bullet points using simple markup (user wants bold in AI bubble—this is a quick action)
    flow_lines = [f"**{s}**: 1-2 line actionable guidance." for s in sales_call_flow]
    flow_text = "\n".join(flow_lines)
    st.session_state.chat_history.append({"role": "ai", "content": flow_text, "time": datetime.now().strftime("%H:%M"), "audio": None})
    render_chat_history()

# Brand leaflet link
st.markdown(f"[📄 Brand Leaflet - {brand}]({gsk_brands[brand]})")

# ----------------------------
# End of file
# ----------------------------
