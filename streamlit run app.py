# app.py
import streamlit as st
from io import BytesIO
import re
import tempfile
import base64
import os
from groq import Groq
from PyPDF2 import PdfReader
from html import escape
import requests

# Optional docx export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False

# ---------------------------- TTS Setup ----------------------------
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except ModuleNotFoundError:
    ELEVENLABS_AVAILABLE = False

from gtts import gTTS

ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    elevenlabs.api_key = ELEVENLABS_API_KEY
else:
    ELEVENLABS_AVAILABLE = False

def generate_audio(text):
    """Generate TTS audio for the AI response"""
    for step in ["Acknowledge", "Probing", "Action", "Confirm", "Transition"]:
        text = text.replace(step, f"{step} ...")
    text = re.sub(r'[{},*]', '', text)
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    if ELEVENLABS_AVAILABLE:
        audio_stream = elevenlabs.generate(text=text, voice=ELEVENLABS_VOICE_ID, stream=True)
        with open(tmp_file.name, "wb") as f:
            for chunk in audio_stream:
                f.write(chunk)
    else:
        tts = gTTS(text=text, lang="en", slow=True)
        tts.save(tmp_file.name)
    with open(tmp_file.name, "rb") as f:
        audio_bytes = f.read()
        audio_base64 = base64.b64encode(audio_bytes).decode()
    return audio_base64

# ---------------------------- App config ----------------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- Session defaults ----------------------------
if "chat_history" not in st.session_state or not isinstance(st.session_state.chat_history, list):
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "voice_pref" not in st.session_state:
    st.session_state.voice_pref = "Old Male"
if "language" not in st.session_state:
    st.session_state.language = "English"
if "pdf_summary_size" not in st.session_state:
    st.session_state.pdf_summary_size = "Normal"

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Background1.jpeg"
GSK_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/GSK-logo.png"
AI_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/AURA.png"

# ---------------------------- CSS ----------------------------
CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-attachment: fixed;
  background-size: auto 140%;
}}
.title-box {{
  background: rgba(240,240,240,0.8);
  padding: 15px;
  border-radius: 16px;
  text-align: left;
  margin: 12px auto;
  width: 900px;
  position: relative;
}}
.title-box img.ai-logo {{
    position: absolute;
    top: 5px;
    right: 10px;
    width: 90px;
}}
.pdf-summary-box {{
  background: #E6F0FF; 
  padding: 12px; 
  border-radius: 14px; 
  margin-bottom: 12px;
  white-space: pre-line;
}}
.chat-container {{
  max-height: 65vh;
  overflow-y: auto;
  padding: 12px;
  border-radius: 10px;
  background: rgba(255,255,255,0.6);
  margin-bottom: 12px;
}}
.chat-bubble-user, .chat-bubble-ai, .chat-bubble-audio {{
  display:block;
  padding:12px;
  border-radius:12px;
  margin:12px 0;
  max-width: 86%;
  word-wrap: break-word;
}}
.chat-bubble-user {{ background: #0078D7; color:white; margin-left:auto; }}
.chat-bubble-ai {{ background: #d9f0ff; margin-right:auto; color:#000; }}
.chat-bubble-audio {{ background: #e2e2e2; margin-right:auto; font-size:0.9em; padding:10px; margin-top:12px; }}
.fixed-chat-input {{
    position: fixed;
    bottom: 120px; /* leave space for pdf summary and disclaimer */
    left: 20px;
    right: 20px;
    z-index: 10002;
}}
.fixed-chat-input textarea {{
    width: 100%;
    min-height: 60px;
    max-height: 180px;
    resize: vertical;
}}
.send-button {{
    position: fixed;
    bottom: 120px;
    right: 30px;
    z-index: 10003;
    height: 40px;
    width: 100px;
}}
.call-flow-box {{
  background: rgba(255,255,255,0.95);
  padding: 10px;
  border-radius: 10px;
  margin-bottom: 8px;
}}
.disclaimer {{
  font-size: 0.85em;
  color: #444;
  margin-top: 8px;
  opacity: 0.9;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ client ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
if not GROQ_API_KEY:
    st.warning("⚠️ Missing GROQ_API_KEY in Streamlit Secrets")
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Safe folder creation ----------------------------
def safe_makedirs(path):
    try:
        if os.path.exists(path):
            if not os.path.isdir(path):
                st.warning(f"⚠️ Path exists but is not a directory: {path}")
                return False
            return True
        os.makedirs(path, exist_ok=True)
        return True
    except Exception as e:
        st.warning(f"⚠️ Could not create folder {path}: {e}")
        return False

# ensure base folders
safe_makedirs(".devcontainer/references/shingrix")
safe_makedirs(".devcontainer/references/jemperli")
safe_makedirs(".devcontainer/SalesModule/SHINGRIX")
safe_makedirs(".devcontainer/SalesModule/JEMPERLI")

# ---------------------------- Brand config & call flows ----------------------------
brand_data = {
    "Shingrix": {
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "references_path": ".devcontainer/references/shingrix/"
    },
    "JEMPERLI": {
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited patient eligibility", "Access/reimbursement issues"],
        "references_path": ".devcontainer/references/jemperli/"
    }
}

JEMPERLI_CALL_FLOW = {
    "COCO": "Pre-call planning using customer insights to identify persona and call objective. Select a patient type and develop thought-provoking questions.",
    "Anchor": "Open the conversation using COCO insights: create a patient-focused narrative, align on the call objective and tailor messaging to the HCP's unmet need.",
    "Engage": "Build two-way dialogue, connect clinical data and product messages as appropriate, and handle objections.",
    "Close": "Gain agreement, propose clear next steps aligned to the objective, consider omni-channel follow-up, and record insights."
}

SHINGRIX_CALL_FLOW = {
    "Prepare": "Plan the call: identify customer persona, call objectives, and patient types; gather insights to inform messaging.",
    "Engage": "Open the conversation to connect and capture attention; use insights to set context and align with the HCP.",
    "Create Opportunities": "Identify gaps or unmet needs and present clinical/product data as tailored solutions.",
    "Influence": "Present evidence, handle objections, and highlight product value and outcomes to influence decisions.",
    "Impact GSO": "Link discussion to incremental steps and the Good Sell Outcome; clarify next steps and commitments.",
    "Post-Call Analysis": "Record insights, update CRM, and evaluate success metrics to inform future calls."
}

specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Rheumatologist", "Internal medicine", "Oncologist"]
objectives = ["Awareness", "Adoption", "Retention"]

# ---------------------------- Sidebar filters ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", list(brand_data.keys()), key="select_brand")
    selected_brand = brand_data[brand]
    segment = st.selectbox("Segment", selected_brand["segments"], key="select_segment")
    persona = st.selectbox("HCP Persona", selected_brand["personas"], key="select_persona")
    barrier = st.multiselect("Doctor Barrier", selected_brand["barriers"], key="select_barrier")
    specialty = st.selectbox("Specialty", specialties, key="select_specialty")
    objective = st.selectbox("Objective", objectives, key="select_objective")
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"], key="select_tone")
    response_length = st.selectbox("Response Length", ["Short", "Medium", "Long"], key="select_length")
    st.session_state.language = st.radio("Language", ["English", "Arabic"], horizontal=True, key="select_language")

# ---------------------------- Title ----------------------------
st.markdown(f'''
<div class="title-box">
    <img src="{GSK_LOGO_URL}" width="140">
    <img src="{AI_LOGO_URL}" class="ai-logo">
    <h1>💡 AI Sales Call Assistant</h1>
    <p>Empowering reps for smarter {brand} conversations</p>
</div>
''', unsafe_allow_html=True)

# ---------------------------- Helpers: load local refs & urls ----------------------------
def load_local_references(folder_path):
    text_all = ""
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return "", f"⚠️ Folder does not exist: {folder_path}"
    files = [f for f in os.listdir(folder_path) if f.lower().endswith((".pdf", ".txt"))]
    if not files:
        return "", f"ℹ️ No files found in {folder_path}"
    for file in files:
        file_path = os.path.join(folder_path, file)
        try:
            if file.lower().endswith(".pdf"):
                reader = PdfReader(file_path)
                for page in reader.pages:
                    text_all += page.extract_text() or ""
            else:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text_all += f.read()
        except Exception as e:
            text_all += f"\n[Error reading {file}: {e}]"
    return text_all.strip(), None

def load_external_references(url_list):
    all_text = ""
    for url in url_list:
        url = url.strip()
        if not url:
            continue
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            content_type = r.headers.get("Content-Type", "").lower()
            if "pdf" in content_type or url.lower().endswith(".pdf"):
                from io import BytesIO
                try:
                    reader = PdfReader(BytesIO(r.content))
                    for page in reader.pages:
                        all_text += page.extract_text() or ""
                except Exception:
                    all_text += f"\n[Could not extract PDF text from {url}]"
            else:
                all_text += r.text + "\n"
        except Exception as e:
            all_text += f"\n[Error fetching {url}: {e}]"
    return all_text

# ---------------------------- Collapsible resource panels ----------------------------
# Medical references (collapsible)
with st.expander("📚 Medical References (local + external)", expanded=False):
    st.write("Local folder:", selected_brand["references_path"])
    local_ref_text, local_warning = load_local_references(selected_brand["references_path"])
    if local_warning:
        st.info(local_warning)
    # Collapsible preview inside panel
    if local_ref_text:
        with st.expander("🔍 Preview Local Medical References", expanded=False):
            st.text_area("Local Medical Reference Preview", local_ref_text[:4000] + ("..." if len(local_ref_text) > 4000 else ""), height=240)
    # External URLs (collapsible input is the panel itself)
    external_urls_input = st.text_area("Add external medical reference URLs (one per line)", height=120)
    external_urls = [u.strip() for u in (external_urls_input or "").splitlines() if u.strip()]
    external_text = load_external_references(external_urls) if external_urls else ""
    if external_text:
        with st.expander("🔍 Preview External Medical References", expanded=False):
            st.text_area("External Medical Reference Preview", external_text[:4000] + ("..." if len(external_text) > 4000 else ""), height=240)

# Always-visible PDF summary area
st.markdown("### 📄 Uploaded PDF Summary (always visible)")
st.text_area("PDF Summary", st.session_state.pdf_summary or "No PDF uploaded or no summary available.", height=140)

# SalesModule (collapsible)
with st.expander("🧩 Sales Call Module (local)", expanded=False):
    sales_folder = f".devcontainer/SalesModule/{brand.upper()}"
    st.write("SalesModule folder:", sales_folder)
    safe_makedirs(sales_folder)
    sales_module_text, sales_warning = load_local_references(sales_folder)
    if sales_warning:
        st.info(sales_warning + " — default call flow will be used when files are missing.")
    if sales_module_text:
        with st.expander("🔍 Preview SalesModule Documents", expanded=False):
            st.text_area("SalesModule Preview", sales_module_text[:4000] + ("..." if len(sales_module_text) > 4000 else ""), height=260)
    # allow adding external sales module URLs (optional)
    sales_urls_input = st.text_area("Optional: Add SalesModule URLs (one per line)", height=100)
    sales_urls = [u.strip() for u in (sales_urls_input or "").splitlines() if u.strip()]
    sales_external_text = load_external_references(sales_urls) if sales_urls else ""
    if sales_external_text:
        with st.expander("🔍 Preview External SalesModule Content", expanded=False):
            st.text_area("SalesModule External Preview", sales_external_text[:4000] + ("..." if len(sales_external_text) > 4000 else ""), height=260)

# ---------------------------- Chat rendering area ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for item in st.session_state.chat_history:
    if isinstance(item, tuple) and len(item) == 3:
        user_msg, ai_html, audio_b64 = item
        st.markdown(f'<div class="chat-bubble-user">{escape(user_msg)}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="chat-bubble-ai">{ai_html}</div>', unsafe_allow_html=True)
        st.markdown(f'''
            <div class="chat-bubble-audio">
            🔊 AI Voice:<br>
            <audio controls src="data:audio/mp3;base64,{audio_b64}"></audio>
            </div>
        ''', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Permanent disclaimer below chat
st.markdown('<div class="disclaimer">⚠️ <em>This AI tool may occasionally make mistakes. Please validate all generated messages and call flows against GSK-approved materials before use.</em></div>', unsafe_allow_html=True)

# ---------------------------- Fixed chat input ----------------------------
st.markdown('<div class="fixed-chat-input">', unsafe_allow_html=True)
with st.form(key="chat_form", clear_on_submit=True):
    chat_input = st.text_area("Your Message", key="chat_input", placeholder="Type your message here...")
    send = st.form_submit_button("Send")
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Helpers for building HTML blocks ----------------------------
def build_call_flow_block(brand_name):
    # Returns numbered emoji + bold HTML for the brand call flow (descriptions only)
    html = '<div class="call-flow-box">'
    html += '<p><em>Here\'s the structured sales call flow based on your selected brand and context:</em></p>'
    steps = []
    if brand_name.upper() == "JEMPERLI":
        steps = list(JEMPERLI_CALL_FLOW.items())
        emoji_map = {"COCO":"🟩","Anchor":"🟦","Engage":"🟨","Close":"🟥"}
    else:
        steps = list(SHINGRIX_CALL_FLOW.items())
        emoji_map = {}
        # create rotating emoji list for Shingrix
        ems = ["🟩","🟦","🟨","🟧","🟥","🟪"]
        for i, (k, v) in enumerate(steps):
            emoji_map[k] = ems[i % len(ems)]
    # number and render
    for idx, (step_name, desc) in enumerate(steps, start=1):
        emoji = emoji_map.get(step_name, "🔹")
        html += f'<p>{emoji} <strong>{idx}. {escape(step_name)}:</strong> {escape(desc)}</p>'
    html += "</div>"
    return html

def build_apact_html():
    apact = [
        ("Acknowledge", "Acknowledge the HCP's concern."),
        ("Probing", "Ask clarifying questions to understand the root cause."),
        ("Action", "Provide a concise action or evidence-based response."),
        ("Confirm", "Confirm the HCP's understanding/agreement."),
        ("Transition", "Transition to next steps or follow-up.")
    ]
    html = '<div class="call-flow-box"><p><strong>Objection handling (APACT):</strong></p>'
    for name, desc in apact:
        html += f'<p>🔹 <strong>{escape(name)}:</strong> {escape(desc)}</p>'
    html += "</div>"
    return html

# ---------------------------- Generate AI response ----------------------------
def generate_ai_response(user_input):
    # assemble combined context (local + external + sales module + uploaded pdf)
    combined_parts = []
    if 'local_ref_text' in locals() and local_ref_text:
        combined_parts.append(local_ref_text)
    if 'external_text' in locals() and external_text:
        combined_parts.append(external_text)
    if 'sales_module_text' in locals() and sales_module_text:
        combined_parts.append(sales_module_text)
    if sales_external_text:
        combined_parts.append(sales_external_text)
    if st.session_state.uploaded_pdf_text:
        combined_parts.append(st.session_state.uploaded_pdf_text)
    combined_context = "\n\n".join(combined_parts)[:15000]

    # ask model to produce examples and phrasing for the selected brand
    system_prompt = (
        "You are a pharmaceutical sales coach for field reps. Use the provided Medical and Sales Module context "
        "to craft practical, step-by-step sales call dialogue and example phrasing tailored to the selected persona, specialty, and barriers. "
        "If the user asks about objection handling, present a brief APACT structure. Keep outputs concise and actionable."
    )
    user_prompt = (
        f"Request: {user_input}\n\n"
        f"Brand: {brand}\nPersona: {persona}\nSpecialty: {specialty}\nSegment: {segment}\nBarriers: {barrier}\nObjective: {objective}\n\n"
        "Using the context, provide (A) a short set of example lines or bullets the rep can use for each step of the brand call flow, "
        "and (B) short suggested next steps. Label the examples clearly under an 'Examples:' heading. Keep it practical."
    )

    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt + "\n\nContext (truncated):\n" + combined_context[:8000]}
            ],
            temperature=0.6
        )
        ai_raw = resp.choices[0].message.content or ""
    except Exception as e:
        ai_raw = f"[Error calling model: {e}]"

    # Build call flow block (numbered + emoji + bold) from static call flow dicts
    call_flow_html = build_call_flow_block(brand)

    # If the user asks about objections, include APACT block
    apact_html = ""
    if re.search(r'\b(objection|concern|handle|apact|how to respond|how to handle)\b', user_input, re.IGNORECASE):
        apact_html = build_apact_html()

    # Prepare AI body: escape and convert paragraphs
    body_paragraphs = []
    for para in ai_raw.splitlines():
        p = para.strip()
        if not p:
            continue
        body_paragraphs.append(escape(p))
    ai_body_html = "<br>".join(body_paragraphs) if body_paragraphs else "<em>No examples generated.</em>"

    # Compose final assistant HTML: intro call flow, examples header, model content
    assistant_html = call_flow_html
    if apact_html:
        assistant_html += apact_html
    assistant_html += '<div class="call-flow-box"><p><strong>Examples:</strong></p>'
    assistant_html += f'<div>{ai_body_html}</div></div>'

    # also return plain text for audio generation (strip HTML)
    plain_text = re.sub(r'<[^>]+>', '', assistant_html)
    return assistant_html, plain_text

# ---------------------------- Handle sending / storing message ----------------------------
if send and chat_input and chat_input.strip():
    ai_html, ai_plain = generate_ai_response(chat_input.strip())
    audio_b64 = generate_audio(ai_plain)
    st.session_state.chat_history.append((chat_input.strip(), ai_html, audio_b64))

# ---------------------------- Export to Word ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("📥 Export Chat to Word"):
        doc = Document()
        doc.add_heading("AI Sales Call Assistant Chat Export", 0)
        for user_msg, ai_html, audio in st.session_state.chat_history:
            plain_ai = re.sub(r'<[^>]+>', '', ai_html)
            doc.add_paragraph(f"User: {user_msg}")
            doc.add_paragraph(f"AI: {plain_ai}\n")
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            bytes_data = f.read()
            b64 = base64.b64encode(bytes_data).decode()
            href = f'<a href="data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{b64}" download="AI_Chat.docx">Click to download Word file</a>'
            st.markdown(href, unsafe_allow_html=True)
