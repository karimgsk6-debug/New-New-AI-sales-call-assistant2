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
    # remove problematic punctuation for smoother TTS
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

# ---------------------------- CONFIG ----------------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- Session Defaults ----------------------------
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
  margin-bottom: 20px;
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
    bottom: 20px;
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
    bottom: 20px;
    right: 30px;
    z-index: 10003;
    height: 40px;
    width: 100px;
}}
.call-flow-box {{
  background: rgba(255,255,255,0.9);
  padding: 10px;
  border-radius: 10px;
  margin-bottom: 8px;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ Client ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
if not GROQ_API_KEY:
    st.warning("⚠️ Missing GROQ_API_KEY in Streamlit Secrets")
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Helper: Safe Folder Creation ----------------------------
def safe_makedirs(path):
    # ensure parent directories created where needed; don't error if file exists but not dir
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

# create base folders
safe_makedirs(".devcontainer/references/shingrix")
safe_makedirs(".devcontainer/references/jemperli")
safe_makedirs(".devcontainer/SalesModule/SHINGRIX")
safe_makedirs(".devcontainer/SalesModule/JEMPERLI")

# ---------------------------- Brand Configurations ----------------------------
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

specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Rheumatologist", "Internal medicine", "Oncologist"]
objectives = ["Awareness", "Adoption", "Retention"]

# ---------------------------- Sidebar ----------------------------
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

# ---------------------------- Sales Call Flows ----------------------------
JEMPERLI_CALL_FLOW = {
    "COCO": "Pre-call planning using customer insights to identify persona and call objective. Select a patient type and prepare thought-provoking questions to challenge the status quo.",
    "Anchor": "Open the conversation using COCO insights; create a patient-focused narrative and align on the call objective. Tailor messaging to the HCP challenge/unmet need.",
    "Engage": "Build a two-way dialogue that connects clinical data and product messages to address patient/customer needs and handle objections.",
    "Close": "Gain agreement and commitment through clear next steps aligned to the call objective; consider omni-channel follow-up and record new insights."
}

SHINGRIX_CALL_FLOW = {
    "Prepare": "Identify the customer persona, call objectives, and select patient types. Gather insights to inform messaging.",
    "Engage": "Open the conversation to connect and capture attention; set context and use insights to align with the HCP.",
    "Create Opportunities": "Identify gaps/unmet needs and present tailored clinical/product data as solutions.",
    "Influence": "Present evidence, handle objections, and highlight value/outcomes to influence decisions.",
    "Impact GSO": "Clarify next steps and link to incremental steps that achieve the Good Sell Outcome (GSO).",
    "Post-Call Analysis": "Record insights, update CRM, and evaluate performance to refine future calls."
}

# ---------------------------- Helper: Load local references (PDF/TXT) ----------------------------
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

# ---------------------------- Helper: Load external references from URLs ----------------------------
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
                # parse pdf bytes
                from io import BytesIO
                try:
                    reader = PdfReader(BytesIO(r.content))
                    for page in reader.pages:
                        all_text += page.extract_text() or ""
                except Exception:
                    # fallback: include raw bytes notice
                    all_text += f"\n[Could not extract PDF text from {url}]"
            else:
                all_text += r.text + "\n"
        except Exception as e:
            all_text += f"\n[Error fetching {url}: {e}]"
    return all_text

# ---------------------------- Medical Reference Section (local + external) ----------------------------
st.markdown(f"## 📚 {brand} Medical References")
local_ref_text, local_warning = load_local_references(selected_brand["references_path"])
if local_warning:
    st.info(local_warning)

# Collapsible external URL input
with st.expander("🌐 Add External Medical Reference URLs (collapsible)", expanded=False):
    external_urls_input = st.text_area("Enter public PDF/TXT URLs (one per line)", height=120)
external_urls = [u.strip() for u in (external_urls_input or "").splitlines() if u.strip()]
external_text = load_external_references(external_urls) if external_urls else ""

# Combined preview
if (local_ref_text and local_ref_text.strip()) or (external_text and external_text.strip()):
    with st.expander("🔍 Preview Combined Medical References", expanded=False):
        st.text_area("Medical Reference Preview", (local_ref_text + "\n\n" + external_text)[:4000], height=260)

# ---------------------------- Sales Call Module Section ----------------------------
st.markdown(f"## 📝 Sales Call Module for {brand}")
sales_module_folder = f".devcontainer/SalesModule/{brand.upper()}"
# ensure brand-specific sales module folder exists
safe_makedirs(sales_module_folder)
sales_module_text, sales_warning = load_local_references(sales_module_folder)
if sales_warning:
    # if missing, create user-friendly fallback but let user know
    st.info(sales_warning + " — using default call flow content if needed.")
    # fallback text will be empty string, the call-flow dict will be used when generating responses
    sales_module_text = ""
if sales_module_text:
    with st.expander("🔍 Preview SalesModule Documents", expanded=False):
        st.text_area("Sales Module Preview", sales_module_text[:4000] + ("..." if len(sales_module_text) > 4000 else ""), height=260)
        sales_search_keyword = st.text_input("Search keyword in SalesModule", key="search_sales")
        if sales_search_keyword:
            matches = [m.start() for m in re.finditer(re.escape(sales_search_keyword), sales_module_text, re.IGNORECASE)]
            st.write(f"Found {len(matches)} matches for '{sales_search_keyword}'.")

# ---------------------------- PDF Upload & Summary ----------------------------
with st.expander("📄 Upload Custom PDF for AI Context", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
    st.session_state.pdf_summary_size = st.radio("PDF Summary Size", ["Consisted", "Normal", "Detailed"], horizontal=True)
    if uploaded_pdf:
        reader = PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text
        bullets_count = {"Consisted": 5, "Normal": 10, "Detailed": 20}.get(st.session_state.pdf_summary_size, 10)
        try:
            summary_prompt = f"Summarize this document into {bullets_count} bullet points:\n{full_text[:12000]}"
            ai_summary = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": "You are a helpful assistant."},
                          {"role": "user", "content": summary_prompt}],
                temperature=0.4
            )
            st.session_state.pdf_summary = ai_summary.choices[0].message.content
        except Exception:
            fallback_bullets = re.findall(r'([A-Z][^.]{20,200})', full_text)
            st.session_state.pdf_summary = "\n".join(fallback_bullets[:bullets_count])
    if st.session_state.pdf_summary:
        st.markdown(f'<div class="pdf-summary-box">{escape(st.session_state.pdf_summary)}</div>', unsafe_allow_html=True)

# ---------------------------- AI Chat Rendering ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for item in st.session_state.chat_history:
    if isinstance(item, tuple) and len(item) == 3:
        user_msg, ai_msg_html, audio = item
        # user bubble (escaped)
        st.markdown(f'<div class="chat-bubble-user">{escape(user_msg)}</div>', unsafe_allow_html=True)
        # ai bubble (we already build HTML for ai messages)
        st.markdown(f'<div class="chat-bubble-ai">{ai_msg_html}</div>', unsafe_allow_html=True)
        # audio bubble
        st.markdown(f'''
            <div class="chat-bubble-audio">
            🔊 AI Voice:<br>
            <audio controls src="data:audio/mp3;base64,{audio}"></audio>
            </div>
        ''', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Chat Input ----------------------------
st.markdown('<div class="fixed-chat-input">', unsafe_allow_html=True)
with st.form(key="chat_form", clear_on_submit=True):
    chat_input = st.text_area("Your Message", key="chat_input", placeholder="Type your message here...")
    send = st.form_submit_button("Send")
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- APACT helper ----------------------------
def build_apact_html():
    # APACT headers bold + emoji
    apact_steps = [("Acknowledge", "Acknowledge the HCP concern."), 
                   ("Probing", "Ask clarifying questions to understand the root cause."), 
                   ("Action", "Provide a concise action or evidence-based response."), 
                   ("Confirm", "Confirm the HCP's understanding/agreement."), 
                   ("Transition", "Transition to next steps or follow-up.")]
    html = ""
    for name, desc in apact_steps:
        html += f'<p>🔹 <strong>{escape(name)}:</strong> {escape(desc)}</p>'
    return html

# ---------------------------- Build call-flow HTML helper ----------------------------
def build_call_flow_html(brand_name):
    html = '<div class="call-flow-box">'
    if brand_name.upper() == "JEMPERLI":
        for step, desc in JEMPERLI_CALL_FLOW.items():
            emoji = {
                "COCO": "🟩",
                "Anchor": "🟦",
                "Engage": "🟨",
                "Close": "🟥"
            }.get(step, "🔹")
            html += f'<p>{emoji} <strong>{escape(step)}:</strong> {escape(desc)}</p>'
    elif brand_name.upper() == "SHINGRIX":
        emoji_map = ["🟩","🟦","🟨","🟧","🟥","🟪"]
        i = 0
        for step, desc in SHINGRIX_CALL_FLOW.items():
            emoji = emoji_map[i % len(emoji_map)]
            i += 1
            html += f'<p>{emoji} <strong>{escape(step)}:</strong> {escape(desc)}</p>'
    else:
        html += "<p><strong>Call flow:</strong> Use brand-specific guidance.</p>"
    html += "</div>"
    return html

# ---------------------------- Generate AI response ----------------------------
def generate_ai_response(user_input):
    # Combine context
    combined_context = "\n\n".join([
        local_ref_text or "",
        external_text or "",
        sales_module_text or "",
        st.session_state.uploaded_pdf_text or ""
    ])[:15000]

    # Build base system prompt and user prompt for the model (keeps it concise)
    system_prompt = (
        "You are a pharmaceutical sales coach for reps. Use the provided Medical and Sales Module context "
        "to craft practical, step-by-step sales call dialogue, tailored to the selected persona, specialty, and barriers. "
        "If the user asks about objection handling, structure the advice using the APACT framework."
    )
    user_prompt = (
        f"User request: {user_input}\n\n"
        f"Context (truncated):\n{combined_context[:8000]}\n\n"
        f"Persona: {persona}\nBrand: {brand}\nSpecialty: {specialty}\nSegment: {segment}\nBarriers: {barrier}\nObjective: {objective}\n"
    )

    # Ask the model to produce a practical call flow and example lines
    model_instructions = (
        "Produce: 1) A short, practical call structure following the brand's call flow steps. "
        "2) Example lines the rep can use for each step. Keep it actionable and concise."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt + "\n\n" + model_instructions}
            ],
            temperature=0.6
        )
        ai_text = response.choices[0].message.content or ""
    except Exception as e:
        ai_text = f"[Error calling model: {e}]"

    # Build formatted HTML with call-flow (emoji + bold) at top of the assistant message
    call_flow_html = build_call_flow_html(brand)

    # If the user asked about an objection, prepend APACT formatted block
    apact_html = ""
    if re.search(r'\b(objection|concern|handle|how to respond|apact)\b', user_input, re.IGNORECASE):
        apact_html = '<div class="call-flow-box"><p><strong>Objection handling (APACT):</strong></p>'
        apact_html += build_apact_html()
        apact_html += "</div>"

    # Convert ai_text to safe HTML paragraphs
    # We'll replace consecutive newlines with paragraph breaks
    safe_lines = []
    for paragraph in ai_text.splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        safe_lines.append(escape(paragraph))
    ai_body_html = "<br>".join(safe_lines) if safe_lines else ""

    # Full assistant HTML: call flow + APACT (if any) + AI body
    assistant_html = call_flow_html + (apact_html if apact_html else "") + f"<div>{ai_body_html}</div>"

    return assistant_html, ai_text  # return HTML (for display) and plain text (for audio)

# ---------------------------- Handle Send ----------------------------
if send and chat_input and chat_input.strip():
    # generate AI response
    ai_html, ai_plain = generate_ai_response(chat_input.strip())
    # generate audio
    audio_b64 = generate_audio(ai_plain)
    # append to chat history: store (user_text, ai_html, audio)
    st.session_state.chat_history.append((chat_input.strip(), ai_html, audio_b64))
    # clear the input after send (form has clear_on_submit=True)
    # (Streamlit will clear automatically because form param was set)

# ---------------------------- Export ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("📥 Export Chat to Word"):
        doc = Document()
        doc.add_heading("AI Sales Call Assistant Chat Export", 0)
        for user_msg, ai_html, audio in st.session_state.chat_history:
            # convert ai_html -> plain text for doc export by stripping tags (simple approach)
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
