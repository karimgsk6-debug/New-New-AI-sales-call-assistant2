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
# Load GROQ API key from env (preferred)
# ----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
if not GROQ_API_KEY:
    st.warning("GROQ_API_KEY not found in environment. Set GROQ_API_KEY in env or Streamlit Secrets.")
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

# ----------------------------
# Assets & styling variables
# ----------------------------
# Background image (external URL)
BACKGROUND_URL = (
    "https://sdmntprpolandcentral.oaiusercontent.com/files/00000000-466c-620a-81c6-59c1f5c85484/raw?se=2025-09-29T08%3A50%3A13Z&sp=r&sv=2024-08-04&sr=b&scid=61b996f9-1aa8-5450-9322-8df6ba4be66c&skoid=76024c37-11e2-4c92-aa07-7e519fbe2d0f&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-29T03%3A57%3A08Z&ske=2025-09-30T03%3A57%3A08Z&sks=b&skv=2024-08-04&sig=k8xWpLn%2BpScPIMXS/CBwvn%2Blwsduznv0W2gDvCqsIRM%3D"
)
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
# UI CSS: background responsive & bottom input flixed
# ----------------------------
CSS = f"""
<style>
/* App background and responsiveness */
.stApp {{
  background: url('{BACKGROUND_URL}') no-repeat top right;
  background-size: contain;
  background-attachment: flix;
}}

/* Sidebar defaults (white, bordered controls) */
.stSidebar {{
  background-color: #dddd;
  padding: 14px;
}}
/* show borders around selection controls */
.stSidebar .stSelectbox, .stSidebar .stMultiselect, .stSidebar .stRadio, .stSidebar .stCheckbox, .stSidebar .stFileUploader {{
  border: 1px solid #ddd;
  border-radius: 10px;
  padding: 8px;
  margin-bottom: 12px;
  background-color: #fff;
}}

/* Top-right logo (3cm ~ 60px down) */
.gsk-logo {{
  position: flix;
  top: 80px;
  left: 12px;
  z-index: 1200;
}}

/* Title box */
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

/* PDF summary box style */
.pdf-summary-box {{
  background: rgba(255,255,255,0.6);
  padding: 16px;
  border-radius: 12px;
  margin-bottom: 12px;
}}

/* Chat bubble style (black font in bubbles) */
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

/* Make AI bubble include pdf summary area */
.pdf-summary-inline {{
  margin-top:8px;
  background: rgba(255,255,255,0.6);
  padding:10px;
  border-radius:10px;
}}

/* Bottom fixed input area */
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

/* small screens */
@media (max-width: 430px) {{
  .title-box h1 {{ font-size:26px; }}
  .gsk-logo img {{ width: 90px; }}
  .bottom-input {{ left:8px; right:8px; bottom:8px; padding:8px; }}
}}
/* highlight for call steps / APACT / figures */
.highlight-step {{ font-weight:700; color:#000; }}
.highlight-figure {{ font-weight:700; color:#d35400; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# small JS to scroll chat container to bottom when updated
SCROLL_JS = """
<script>
function scrollChat() {
  const el = document.getElementById('chat-area');
  if (el) el.scrollTop = el.scrollHeight;
}
setTimeout(scrollChat, 200);
</script>
"""
st.markdown(f'<div class="gsk-logo"><img src="{GSK_LOGO_URL}" width="140"></div>', unsafe_allow_html=True)

# Title + disclaimer
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
# Data definitions
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
# Sidebar filters (white background + bordered controls)
# ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown('<div style="font-weight:800; margin-bottom:8px;">Filters & Options</div>', unsafe_allow_html=True)
    brand = st.selectbox("Select Brand", options=list(gsk_brands.keys()))
    # brand image under brand name
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try:
            resp = requests.get(img_path, timeout=6)
            img = Image.open(BytesIO(resp.content))
            st.image(img, width=180)
        except Exception:
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
# PDF Upload & Summarization (top of interface)
# ----------------------------
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:2000] + "..." if len(full_text) > 2000 else full_text
        # heuristically extract references
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"
        st.success("✅ PDF processed")

        # Create AI summary prompt (use small chunk so we don't exceed token limits)
        summary_prompt = (
            "You are a concise medical summarizer for sales reps. Produce bullet points with key results, "
            "practical recommendations, and notable figures (with %s format if present). Keep it short and actionable.\n\n"
        ) + full_text[:6000]

        # Use the Groq client (with quick try/except)
        if client is None:
            st.warning("Groq client not configured: PDF auto-summarize unavailable (set GROQ_API_KEY).")
            st.session_state.pdf_summary = ""
        else:
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

        # Collapsible box with summary
        if st.session_state.pdf_summary:
            with st.expander("📑 PDF Summary (expand/collapse)", expanded=False):
                st.markdown(f'<div class="pdf-summary-box">{"<br>".join([f"- {line.strip()}" for line in st.session_state.pdf_summary.split("\\n") if line.strip()])}</div>', unsafe_allow_html=True)

        if st.session_state.extracted_medical_ref:
            st.info(f"📚 Extracted references: {st.session_state.extracted_medical_ref}")
    except Exception as e:
        st.error("PDF error: " + str(e))

# ----------------------------
# Chat area (scrollable)
# ----------------------------
st.markdown("<h3>💬 Chat</h3>", unsafe_allow_html=True)
st.markdown('<div id="chat-area" style="height:56vh; overflow:auto; padding:12px; border-radius:8px; background: rgba(255,255,255,0.6);">', unsafe_allow_html=True)

def build_ai_bubble_content(ai_text: str) -> str:
    """Return AI bubble HTML, with injected PDF summary (inline) and highlighting of steps/APACT/figures."""
    content = ai_text.replace("\n", "<br>")
    # If user asked about 'sales call flow' earlier, ensure the standard bullet steps appear bolded:
    # highlighting sales steps & APACT terms inside content
    for step in sales_call_flow:
        # word-boundary replace with bold span
        content = re.sub(rf"\b{re.escape(step)}\b", f"<span class='highlight-step'>{step}</span>", content)
    for ap in APACT_STEPS:
        content = re.sub(rf"\b{re.escape(ap)}\b", f"<span class='highlight-step'>{ap}</span>", content)
    # highlight percent figures
    for figure in re.findall(r"\d+\.?\d*%", content):
        content = content.replace(figure, f"<span class='highlight-figure'>{figure}</span>")

    pdf_html = ""
    if st.session_state.pdf_summary:
        pdf_lines = [f"- {ln.strip()}" for ln in st.session_state.pdf_summary.split("\n") if ln.strip()]
        pdf_html = "<div class='pdf-summary-inline'>" + "<br>".join(pdf_lines) + "</div>"

    return f"{content}{pdf_html}"

# helper to render chat history
def render_chat_history():
    html = ""
    for msg in st.session_state.chat_history:
        content = msg["content"]
        # user
        if msg["role"] == "user":
            html += f"<div class='chat-bubble-user'>{content}</div>"
        else:
            ai_bubble = build_ai_bubble_content(content)
            # audio if present
            audio_html = ""
            if msg.get("audio"):
                audio_html = f"<br><audio controls style='margin-top:8px;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
            html += f"<div class='chat-bubble-ai'>{ai_bubble}{audio_html}</div>"
    st.markdown(html, unsafe_allow_html=True)
    st.markdown(SCROLL_JS, unsafe_allow_html=True)

# initial render of existing history
render_chat_history()
st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# Humanized TTS (SSML + Aria for English)
# ----------------------------
async def _edge_save_async(ssml_text: str, voice: str, outpath: str):
    comm = edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts_base64(text: str, lang: str) -> Optional[str]:
    # Clean and prepare SSML
    if not text or not text.strip():
        return None
    # remove special characters that make speech choppy
    text = re.sub(r'([;:{}\[\]\*\^<>@#\$%&\|~_=/\\\+])', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    # split sentences and insert breaks for naturalness
    sentences = re.split(r'(?<=[.?!])\s+', text)
    # wrap in <speak> with prosody and breaks
    ssml_parts = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        # small heuristics to insert slight pause for clauses
        ssml_parts.append(f"<prosody rate='medium'>{s}<break time='0.35s'/></prosody>")
    ssml_text = "<speak>" + " ".join(ssml_parts) + "</speak>"

    voice = "ar-EG-SalmaNeural" if lang == "العربية" else "en-US-AriaNeural"
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        asyncio.run(_edge_save_async(ssml_text, voice, tmp_name))
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
# Helper: build smart prompt (enforce sales flow & APACT when appropriate)
# ----------------------------
def build_prompt(user_input: str, language: str) -> str:
    """
    Build a robust prompt that:
      - prioritizes PDF summary & extracted references
      - enforces use of the provided sales_call_flow when user asks for 'sales call flow'
      - enforces APACT structure when user mentions barrier/objection words
    """
    pdf_summary = st.session_state.pdf_summary or ""
    refs = st.session_state.extracted_medical_ref or "None"

    instructions = [
        "- Use uploaded PDF summary and extracted medical references as primary clinical sources where applicable.",
        "- Where clinical facts are used, cite the reference names when available.",
        "- Provide actionable sales suggestions and a short 3–6 line script the rep can say (label as 'Sample script').",
        "- Output should be in clear, professional language matching the requested tone and length."
    ]

    # detect if user explicitly asked for sales call flow
    if re.search(r"\b(sales call flow|call flow|sales flow|sales steps)\b", user_input, flags=re.I):
        # force a bullet list of the GSK steps (bolded using markdown-style **)
        # instruct to show each step as a bold bullet with 1-2 sentences actionable guidance
        instructions.append("When the user asks about the sales call flow, return the following steps as bold bullet points and short actionable guidance: "
                            + ", ".join([f"**{s}**" for s in sales_call_flow]) + ".")
    # detect objections/barriers context -> enforce APACT
    if re.search(r"\b(objection|objec|concern|barrier|hesitat|not convinced|resist)\b", user_input, flags=re.I):
        instructions.append("When addressing HCP concerns or objections, structure the response using APACT: "
                            "**Acknowledge**, **Probing**, **Action**, **Confirm**, **Transition**. Bold these APACT steps in the response.")

    # Always ask to bold APACT and call steps and figures
    instructions.append("Bold sales call steps, APACT step titles, and notable figures (e.g. 45%) in the response.")

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
# Safe Groq call with retries & fallback model list
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
                    temperature=0.7
                )
                return resp.choices[0].message.content
            except Exception as e:
                last_err = e
                err_msg = str(e).lower()
                # retry on capacity / 503
                if "over capacity" in err_msg or "503" in err_msg or "internal_server_error" in err_msg:
                    wait = base_delay * (2 ** (attempt - 1))
                    st.warning(f"Model {model} busy. Retrying in {wait}s (attempt {attempt}/{max_retries})...")
                    time.sleep(wait)
                    continue
                # authentication
                if "authentication" in err_msg or "unauthorized" in err_msg:
                    return "⚠️ Authentication error with Groq. Please check GROQ_API_KEY."
                # other errors -> return message
                return f"⚠️ Error generating response: {e}"
        # fallback to next model
        st.info(f"Switching to fallback model after {max_retries} attempts for {model}.")
    return f"⚠️ Failed to generate response after retries: {last_err}"

# ----------------------------
# Bottom fixed input area (renders as HTML block)
# ----------------------------
# We render an HTML container for the input (using Streamlit form inside for accessibility)
st.markdown(
    """
    <div class="bottom-input">
      <form id="prompt-form" action="#" onsubmit="return false" style="display:flex; width:100%;">
        <input id="user-text" type="text" placeholder="Type your message..." />
        <button id="send-btn" type="button">Send</button>
      </form>
    </div>
    <script>
    const sendBtn = document.getElementById('send-btn');
    const userInput = document.getElementById('user-text');
    sendBtn.onclick = () => {
      const val = userInput.value;
      if (!val) return;
      const payload = {text: val};
      // communicate to Streamlit via Streamlit.setComponentValue isn't available — we'll use a custom event and Streamlit's built-in text_input below as fallback
      // Trigger click on hidden native Streamlit button by setting its value:
      const hidden = window.parent.document.querySelector('input[data-st-u-testid="hidden-user-input"]');
      if (hidden) { hidden.value = val; hidden.dispatchEvent(new Event('input', { bubbles: true })); }
      userInput.value = '';
    };
    // allow Enter
    userInput.addEventListener("keypress", function(e) {
      if (e.key === "Enter") { sendBtn.click(); e.preventDefault(); }
    });
    </script>
    """,
    unsafe_allow_html=True
)

# Because we can't fully wire JS -> Python easily in all Streamlit runtimes, create a *hidden* Streamlit text_input
# that receives the value (the JS above sets it when user clicks Send). This keeps UX consistent.
# We hide label and style the input invisibly.
hidden_key = "hidden_user_input_for_js"
user_hidden = st.text_input("", key=hidden_key, label_visibility="collapsed", placeholder="")  # invisible to user

# Native fallback form (visible on mobile / if JS blocked)
with st.form("native_chat_form", clear_on_submit=True):
    native_input = st.text_input("Or type here:", key="native_input_box", label_visibility="collapsed")
    native_submit = st.form_submit_button("Send")

# unify input: prefer JS hidden input, then native input
user_text = None
# take first non-empty
if user_hidden and user_hidden.strip():
    user_text = user_hidden.strip()
    # clear hidden input (so it doesn't trigger again)
    st.session_state[hidden_key] = ""
elif native_submit and native_input and native_input.strip():
    user_text = native_input.strip()

# ----------------------------
# Handle message submission
# ----------------------------
if user_text:
    # append user
    st.session_state.chat_history.append({"role": "user", "content": user_text, "time": datetime.now().strftime("%H:%M")})
    # build prompt with smart instructions
    prompt = build_prompt(user_text, language)
    # call Groq
    ai_output = call_groq_with_retry(prompt, language)
    # synthesize TTS (non-blocking-ish, but we produce base64 synchronously)
    audio_b64 = synthesize_tts_base64(ai_output, language)
    # append AI
    st.session_state.chat_history.append({"role": "ai", "content": ai_output, "time": datetime.now().strftime("%H:%M"), "audio": audio_b64})
    # re-render chat area
    render_chat_history()

# ----------------------------
# Bottom controls (Clear + Download)
# ----------------------------
cols = st.columns([1, 1])
with cols[0]:
    if st.button("🗑️ Clear Chat"):
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

# Brand leaflet link
st.markdown(f"[📄 Brand Leaflet - {brand}]({gsk_brands[brand]})")
