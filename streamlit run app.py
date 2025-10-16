# app.py
import streamlit as st
from PIL import Image
from io import BytesIO
import re
import tempfile
import base64
import os
from groq import Groq
from PyPDF2 import PdfReader
from html import escape
import requests
from datetime import datetime
import json

# Optional DOCX export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

# ---------------------------- TTS Setup ----------------------------
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except ModuleNotFoundError:
    ELEVENLABS_AVAILABLE = False

# gTTS fallback
from gtts import gTTS

ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")

if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    try:
        elevenlabs.api_key = ELEVENLABS_API_KEY
    except Exception:
        ELEVENLABS_AVAILABLE = False
else:
    ELEVENLABS_AVAILABLE = False

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
if "chat_key" not in st.session_state:
    st.session_state.chat_key = 0
if "user_id" not in st.session_state:
    st.session_state.user_id = "anonymous"

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
  background-size: auto 130%;
}}

@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(-10px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.title-box {{
  background: rgba(230,230,230,0.7);
  padding: 10px;
  border-radius: 15px;
  text-align: left;
  margin: 12px auto;
  width: 1100px;
  position: relative;
  animation: fadeIn 1.0s ease-in-out;
}}

.title-box img.ai-logo {{
    position: absolute;
    top: 10px;
    right: 15px;
    width: 120px;
}}

.pdf-summary-box {{
  background: #E6F0FF; 
  padding: 12px; 
  border-radius: 14px; 
  margin-bottom: 12px;
  white-space: pre-line;
  color: #012a4a;
}}

.chat-container {{
  max-height: 60vh;
  overflow-y: auto;
  padding: 12px;
  border-radius: 10px;
  background: rgba(240,240,240,0.7);
  margin-bottom: 20px;
}}

.chat-bubble-user, .chat-bubble-ai, .chat-bubble-audio {{
  display:block;
  padding:12px;
  border-radius:12px;
  margin:12px 0;
  max-width: 90%;
  word-wrap: break-word;
}}

.chat-bubble-user {{ background: #0078D7; color:white; margin-left:auto; }}
.chat-bubble-ai {{ background: #d9f0ff; margin-right:auto; color:#000; }}
.chat-bubble-audio {{ background: #e2e2e2; margin-right:auto; font-size:0.95em; padding:10px; margin-top:12px; }}

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

.fixed-disclaimer {{
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: rgba(255, 255, 255, 0.95);
    color: #444;
    text-align: center;
    font-size: 13px;
    padding: 8px;
    border-top: 2px solid #FF6F00;
    z-index: 9999;
    animation: fadeIn 1.5s ease-in-out;
}}

section[data-testid="stSidebar"] .st-expanderHeader {{
    color: #FF6F00 !important;
    font-weight: 700;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ Client ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
if not GROQ_API_KEY:
    st.warning("⚠️ Missing GROQ_API_KEY in Streamlit Secrets")
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Brand Configurations ----------------------------
def safe_makedirs(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        st.warning(f"⚠️ Could not create folder {path}: {e}")

safe_makedirs(".devcontainer/references/shingrix")
safe_makedirs(".devcontainer/references/jemperli")
safe_makedirs(".devcontainer/SalesModule/shingrix")
safe_makedirs(".devcontainer/SalesModule/jemperli")

brand_data = {
    "shingrix": {
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "references_path": ".devcontainer/references/shingrix/"
    },
    "jemperli": {
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited patient eligibility", "Access/reimbursement issues"],
        "references_path": ".devcontainer/references/jemperli/"
    }
}

specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Rheumatologist", "Internal medicine", "Oncologist"]
objectives = ["Awareness", "Adoption", "Retention"]

# ---------------------------- Moderation Module (embedded) ----------------------------
AUDIT_LOG = ".prompt_audit_log.jsonl"

BLACKLIST_TERMS = [
    r"\boff-?label\b", r"\bunapproved\b", r"\bunauthoriz(?:ed|ed)\b",
    r"\bcure\b", r"\bmiracle\b", r"\bfree trial\b", r"\bdiscount\b",
    r"\bprice\b", r"\bcompare\b.*\bcompetitor\b", r"\bdosage\b", r"\bprescribe\b",
]

SENSITIVE_PATIENT_PATTERNS = [
    r"\bdiagnos(?:e|is|ing)\b", r"\bprescrib(?:e|ing|ed)\b",
    r"\bpatient\b", r"\bunder-?\d+\b", r"\bchild(?:ren)?\b", r"\bage\b"
]

BYPASS_PATTERNS = [
    r"ignore (?:previous|earlier) instructions",
    r"disregard (?:rules|policy)",
    r"bypass (?:filter|moderation)",
    r"act as if you are"
]

ALLOWED_STARTS = [
    "Explain the approved indications for",
    "Summarise approved clinical evidence for",
    "List contraindications for",
    "Provide the approved dosing guidance for"
]

REWRITE_TEMPLATES = {
    "age_question": "Provide approved age indications and age-based guidance for the product.",
    "off_label": "Provide only approved indications and evidence; do not include off-label uses.",
    "prescribe": "Provide high-level educational information; do not provide prescribing advice."
}

def _log_audit(entry):
    entry["timestamp"] = datetime.utcnow().isoformat()
    try:
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass

def _matches_any(patterns, text):
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE):
            return True, p
    return False, None

def external_moderation_check(prompt: str, provider: str = None):
    # Placeholder: implement provider-specific moderation (OpenAI/Groq) if desired.
    # Return: {"flagged": False, "reasons": [], "score": 0.0}
    return {"flagged": False, "reasons": [], "score": 0.0}

def suggest_rewrite(prompt: str, tag: str) -> str:
    return REWRITE_TEMPLATES.get(tag, "Provide a high-level, approved-scope summary relevant to the product and indications.")

def brand_terms():
    return list(brand_data.keys()) + ["gsk"]

def moderate_prompt(prompt: str, user_id: str = None, external_provider: str = None):
    original = prompt or ""
    prompt_norm = re.sub(r'\s+', ' ', original.strip())

    matched_black, black_pat = _matches_any(BLACKLIST_TERMS, prompt_norm)
    if matched_black:
        reason = f"Blacklisted term matched: {black_pat}"
        suggestion = suggest_rewrite(prompt_norm, "off_label")
        _log_audit({"prompt": original, "action": "block", "reason": reason, "rule": black_pat, "user_id": user_id})
        return {"action": "block", "reason": reason, "rewrite": suggestion, "details": {"matched_pattern": black_pat}}

    matched_bypass, bypass_pat = _matches_any(BYPASS_PATTERNS, prompt_norm)
    if matched_bypass:
        reason = f"Bypass attempt detected: {bypass_pat}"
        _log_audit({"prompt": original, "action": "block", "reason": reason, "user_id": user_id})
        return {"action": "block", "reason": reason, "rewrite": None, "details": {"matched_pattern": bypass_pat}}

    matched_sensitive, sens_pat = _matches_any(SENSITIVE_PATIENT_PATTERNS, prompt_norm)
    if matched_sensitive:
        reason = f"Sensitive clinical intent detected: {sens_pat}"
        suggestion = suggest_rewrite(prompt_norm, "prescribe")
        _log_audit({"prompt": original, "action": "review", "reason": reason, "rule": sens_pat, "user_id": user_id})
        return {"action": "review", "reason": reason, "rewrite": suggestion, "details": {"matched_pattern": sens_pat}}

    comp_match = re.search(r'\b(compare|vs\.|versus)\b.*\b(competitor|brand name|price)\b', prompt_norm, flags=re.IGNORECASE)
    if comp_match:
        reason = "Competitive comparison or pricing request detected"
        _log_audit({"prompt": original, "action": "block", "reason": reason, "user_id": user_id})
        return {"action": "block", "reason": reason, "rewrite": None, "details": {"match": comp_match.group(0)}}

    if external_provider:
        ext = external_moderation_check(prompt_norm, provider=external_provider)
        if ext.get("flagged"):
            reason = f"External moderation flagged: {ext.get('reasons')}"
            _log_audit({"prompt": original, "action": "block", "reason": reason, "details": ext, "user_id": user_id})
            return {"action": "block", "reason": reason, "rewrite": None, "details": ext}

    starts_ok = any(prompt_norm.lower().startswith(s.lower()) for s in ALLOWED_STARTS)
    # allow but suggest improved template if not starting with allowed phrase
    if not starts_ok:
        _log_audit({"prompt": original, "action": "allow", "reason": "Template suggestion", "user_id": user_id})
        # No block by default, but provide optional suggestion through caller
        return {"action": "allow", "reason": "Prompt passed checks", "rewrite": None, "details": {}}

    _log_audit({"prompt": original, "action": "allow", "reason": "No issues detected", "user_id": user_id})
    return {"action": "allow", "reason": "No issues detected", "rewrite": None, "details": {}}


# ---------------------------- Local references loader ----------------------------
def load_local_references(folder_path):
    text_all = ""
    warning = None
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
            elif file.lower().endswith(".txt"):
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text_all += f.read()
        except Exception as e:
            text_all += f"\n[Error reading {file}: {e}]"
    return text_all.strip(), None

def load_external_references(url_list):
    all_text = ""
    for url in url_list:
        try:
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                all_text += r.text + "\n"
            else:
                all_text += f"\n[Could not fetch {url} (status {r.status_code})]"
        except Exception as e:
            all_text += f"\n[Error fetching {url}: {e}]"
    return all_text

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

with st.sidebar.expander("🌐 Add External Reference URLs", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)", key="external_urls").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT", "DOCX"], horizontal=True, key="export_format")
    if st.button("💾 Export Chat", key="export_chat_btn"):
        text_export = "\n\n".join([f"{e['role'].capitalize()}: {e['content']}" for e in st.session_state.chat_history])
        if export_format == "DOCX" and DOCX_AVAILABLE:
            doc = Document()
            doc.add_heading("AI Sales Call Assistant Export", 0)
            doc.add_paragraph(f"Brand: {brand.upper()} | Date: {datetime.now().strftime('%Y-%m-%d')}")
            doc.add_paragraph(text_export)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            doc.save(tmp.name)
            with open(tmp.name, "rb") as f:
                st.download_button("⬇️ Download DOCX", f, file_name=f"{brand}_chat.docx", key="download_docx")
        else:
            st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{brand}_chat.txt", key="download_txt")

# Clear Chat Button
if st.sidebar.button("🗑️ Clear Chat", key="clear_chat_btn"):
    st.session_state.chat_history = []
    st.rerun()

# ---------------------------- Title ----------------------------
st.markdown(f'''
<div class="title-box">
    <img src="{GSK_LOGO_URL}" width="140">
    <img src="{AI_LOGO_URL}" class="ai-logo">
    <h1>💡 AI Sales Call Assistant</h1>
    <p>Empowering reps for smarter <b style="color:#FF6F00;">{brand.upper()}</b> conversations</p>
</div>
''', unsafe_allow_html=True)

# ---------------------------- Medical References ----------------------------
st.markdown(f"## 📚 {brand.capitalize()} Medical References")
local_ref_text, local_warning = load_local_references(selected_brand["references_path"])
if local_warning and "No files found" not in local_warning:
    st.info(local_warning)

external_text = load_external_references([u for u in external_urls if u.strip()])

if local_ref_text or external_text:
    with st.expander("🔍 Preview Combined Medical References", expanded=False):
        preview_text = (local_ref_text + "\n" + external_text).strip()
        st.text_area("Medical Reference Preview", preview_text[:3000], height=250, key="ref_preview")

# ---------------------------- Sales Call Module ----------------------------
st.markdown(f"## 📝 Sales Call Module for {brand}")
sales_module_path = f".devcontainer/SalesModule/{brand}"
sales_module_text, sales_warning = load_local_references(sales_module_path)
if sales_warning and "No files found" not in sales_warning:
    st.info(sales_warning)
if sales_module_text:
    with st.expander("🔍 Preview SalesModule Documents", expanded=False):
        st.text_area("Sales Module Preview", sales_module_text[:3000] + "..." if len(sales_module_text) > 3000 else sales_module_text, height=250, key="sales_preview")
        sales_search_keyword = st.text_input("Search keyword in sales modules", key="sales_search_keyword")
        if sales_search_keyword:
            matches = [m.start() for m in re.finditer(sales_search_keyword, sales_module_text, re.IGNORECASE)]
            st.write(f"Found {len(matches)} matches for '{sales_search_keyword}'.")

# ---------------------------- PDF Upload & Summary ----------------------------
with st.expander("📄 Upload Custom PDF for AI Context", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"], key="upload_pdf")
    # PDF Summary Size Selector (safe assignment)
pdf_summary_size = st.radio(
    "PDF Summary Size",
    ["Consisted", "Normal", "Detailed"],
    horizontal=True,
    key="pdf_summary_size"
)

# Store selection in session_state if needed
st.session_state["pdf_summary_size_value"] = pdf_summary_size

    if uploaded_pdf:
        try:
            reader = PdfReader(uploaded_pdf)
            full_text = "".join([p.extract_text() or "" for p in reader.pages])
            st.session_state.uploaded_pdf_text = full_text
            st.success(f"✅ Loaded {len(full_text)} characters from uploaded PDF.")
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
        except Exception as e:
            st.error(f"Error reading uploaded PDF: {e}")
    if st.session_state.pdf_summary:
        st.markdown(f'<div class="pdf-summary-box">{escape(st.session_state.pdf_summary)}</div>', unsafe_allow_html=True)

# ---------------------------- Call Flows ----------------------------
jemperli_CALL_FLOW = {
    "COCO": "Pre-call planning using customer insights, select patient type, develop thought-provoking questions.",
    "Anchor": "Open conversation with a patient-focused narrative, tailor messaging to the HCP challenge/unmet need.",
    "Engage": "Draw customer in through two-way dialogue, connect clinical data and product messages.",
    "Close": "Gain agreement, define next steps, extend engagement via omni-channel, record insights."
}

shingrix_CALL_FLOW = {
    "Prepare": "Plan the call: identify persona, objectives, patient types, key insights.",
    "Engage": "Start conversation, capture attention, set discussion context.",
    "Create Opportunities": "Identify gaps or unmet needs; introduce solutions with clinical/product data.",
    "Influence": "Present evidence, handle objections, highlight value and outcomes.",
    "Impact GSO": "Link discussion to incremental steps and overall GSO; clarify next steps.",
    "Post-Call Analysis": "Record insights, update CRM, evaluate metrics to inform future calls."
}

# ---------------------------- AI response formatting ----------------------------
GSK_ORANGE = "#FF671F"

def format_ai_response_for_display(text):
    """Clean and format AI output for visual display with numbered, orange bold titles and bullets."""
    import html
    txt = html.escape(text)
    txt = re.sub(r'[*_#/\\]+', '', txt)  # strip markdown-like characters
    txt = re.sub(r'\s+', ' ', txt).strip()

    # Split into sections by known titles (preserve order)
    title_pattern = r'(?i)(?=\b(?:Prepare|Engage|Influence|Create Opportunities|Anchor|Close|Confirm|Transition|Action|Post-Call Analysis|Impact GSO|COCO)\b)'
    sections = re.split(title_pattern, txt)
    formatted_html = ""
    section_number = 1

    for section in sections:
        if not section.strip():
            continue
        # detect title at start
        m = re.match(r'(?i)\b(Prepare|Engage|Influence|Create Opportunities|Anchor|Close|Confirm|Transition|Action|Post-Call Analysis|Impact GSO|COCO)\b', section)
        if m:
            title = m.group(0).strip()
            body = section[len(title):].strip()
            formatted_html += f"<p><b style='color:{GSK_ORANGE};font-size:16px'>{section_number}️⃣ {title}</b><br>"
            # split body into bullets by sentence punctuation
            bullets = [b.strip() for b in re.split(r'(?<=[.?!])\s+', body) if b.strip()]
            for b in bullets:
                # remove trailing punctuation for display clarity
                b_clean = re.sub(r'[.?!]+$', '', b)
                formatted_html += f"• {b_clean}<br>"
            formatted_html += "</p>"
            section_number += 1
        else:
            # fallback text
            formatted_html += f"<p>{section.strip()}</p>"
    return formatted_html

# ---------------------------- Audio generation (humanized) ----------------------------
def generate_audio(text):
    """
    Generate expressive male voice with pauses and title recognition.
    ElevenLabs if available (best quality), else gTTS fallback.
    Avoids pronouncing punctuation; adds pauses after titles, sentences and commas.
    Returns base64-encoded mp3 bytestring or empty string on failure.
    """
    import re, tempfile, base64, html
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    # Clean and structure text
    t = re.sub(r'[*/\\#@~^_\[\]\(\)\{\}<>+=:;"`|]', '', text)  # remove symbols not to be spoken
    t = re.sub(r'[-–—]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()

    # Add SSML-like break placeholders
    t = re.sub(r'\.\s*', '. <break time="600ms"/> ', t)
    t = re.sub(r',\s*', ', <break time="300ms"/> ', t)
    t = re.sub(r';\s*', '; <break time="300ms"/> ', t)

    # Add long pause after titles
    section_titles = [
        "Prepare", "Engage", "Create Opportunities", "Influence",
        "Impact GSO", "Post-Call Analysis", "Anchor", "Close",
        "COCO", "Confirm", "Transition", "Action"
    ]
    for title in section_titles:
        t = re.sub(rf'\b{re.escape(title)}\b[:\-–]?', f"{title}. <break time='1000ms'/> ", t, flags=re.IGNORECASE)

    try:
        if ELEVENLABS_AVAILABLE:
            # Use ElevenLabs with voice settings to emphasize titles and natural pacing.
            try:
                from elevenlabs import VoiceSettings
                voice_settings = VoiceSettings(
                    stability=0.30,
                    similarity_boost=0.9,
                    style=0.6,
                    use_speaker_boost=True
                )
            except Exception:
                voice_settings = {"stability": 0.30, "similarity_boost": 0.9, "style": 0.6}

            # Craft instruction prefix to instruct not to read punctuation and to pause
            instruction = (
                "Speak in a confident, warm male voice. "
                "Do not read punctuation aloud. "
                "Pause briefly after commas, longer after periods, and pause longer after section titles. "
                "Deliver content clearly as if presenting to healthcare professionals.\n\n"
            )
            formatted_text = instruction + t

            # Generate audio stream from ElevenLabs
            audio_stream = elevenlabs.generate(
                text=formatted_text,
                voice=ELEVENLABS_VOICE_ID,
                model="eleven_multilingual_v2",
                stream=True,
                voice_settings=voice_settings if isinstance(voice_settings, dict) else None
            )
            with open(tmp.name, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
        else:
            # gTTS fallback - simulate pauses using ellipses
            t_fallback = re.sub(r'<break time="(\d+)ms"/>', ' ... ', t)
            # Ensure it's not too slow/long; slow=False to sound natural
            tts = gTTS(text=t_fallback, lang="en", slow=False)
            tts.save(tmp.name)

        with open(tmp.name, "rb") as f:
            audio_bytes = f.read()
        return base64.b64encode(audio_bytes).decode()
    except Exception as e:
        st.warning(f"Audio generation failed: {e}")
        return ""

# ---------------------------- AI Response Generation ----------------------------
def generate_ai_response(user_input):
    """
    Call Groq / local model (client) with context, then optimize text for speech/display.
    """
    combined_context = "\n".join([
        local_ref_text or "",
        external_text or "",
        sales_module_text or "",
        st.session_state.uploaded_pdf_text or ""
    ])[:15000]

    call_flow_prompt = ""
    if brand.lower() == "jemperli":
        call_flow_prompt = "\n\n--- jemperli Call Flow Steps ---\n" + "\n".join([f"{k}: {v}" for k, v in jemperli_CALL_FLOW.items()])
    elif brand.lower() == "shingrix":
        call_flow_prompt = "\n\n--- shingrix Call Flow Steps ---\n" + "\n".join([f"{k}: {v}" for k, v in shingrix_CALL_FLOW.items()])

    context_prompt = f"""
Brand: {brand}
Persona: {persona}
Segment: {segment}
Specialty: {specialty}
Objective: {objective}
Barriers: {', '.join(barrier) if barrier else 'None'}
Medical + Sales + Uploaded PDF Context (truncated):\n{combined_context[:5000]}
{call_flow_prompt}
"""

    system_prompt = "You are a pharmaceutical AI assistant. Generate structured, conversational responses suitable for spoken delivery. Use short sentences, add brief pauses, and be precise and compliant."

    final_prompt = f"{user_input}\n\n{context_prompt}"

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": final_prompt}],
            temperature=0.6
        )
        ai_text = response.choices[0].message.content

        # Optimize for speech
        ai_text = re.sub(r'\[.*?\]|\(.*?\)', '', ai_text)  # remove bracketed text
        ai_text = re.sub(r'https?://\S+|www\.\S+', '', ai_text)  # remove URLs
        ai_text = re.sub(r'\s+', ' ', ai_text).strip()
        # Replace some punctuation with commas for smoother speech and add pauses
        ai_text = ai_text.replace(';', ',').replace(':', ',')
        ai_text = re.sub(r'([.!?])', r'\1 ...', ai_text)  # add audible pause markers
        # Prepend an opening phrase and append a short summary prompt for clarity in speech
        ai_text = f"Here’s what I recommend. ... {ai_text} ... In summary, emphasize these points."
        return ai_text
    except Exception as e:
        st.error(f"AI generation failed: {e}")
        return f"(Fallback) Based on brand {brand}, persona {persona}: {user_input}"

# ---------------------------- Chat Rendering ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for entry in st.session_state.chat_history:
    role = entry.get("role")
    content = entry.get("content", "")
    audio = entry.get("audio", "")
    if role == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(content)}</div>', unsafe_allow_html=True)
    elif role == "assistant":
        # Show formatted HTML response (numbered titles in orange)
        try:
            formatted_html = format_ai_response_for_display(content)
            st.markdown(f'<div class="chat-bubble-ai">{formatted_html}</div>', unsafe_allow_html=True)
        except Exception:
            st.markdown(f'<div class="chat-bubble-ai">{escape(content)}</div>', unsafe_allow_html=True)
        if audio:
            try:
                st.markdown(f'<div class="chat-bubble-audio">🔊 AI Voice:<br><audio controls src="data:audio/mp3;base64,{audio}"></audio></div>', unsafe_allow_html=True)
            except Exception:
                pass
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Chat Input (safe unique key) ----------------------------
# Increase chat_key by 1 to make unique widget id on each render
st.session_state.chat_key = st.session_state.get("chat_key", 0) + 1
user_input = st.chat_input("Ask or continue your sales dialogue...", key=f"main_chat_input_{st.session_state.chat_key}")

if user_input:
    # Moderate the prompt
    mod = moderate_prompt(user_input, user_id=st.session_state.get("user_id", "unknown"), external_provider=None)
    if mod["action"] == "block":
        st.error(f"Prompt blocked: {mod['reason']}")
    elif mod["action"] == "review":
        st.warning(f"Prompt requires human review: {mod['reason']}. Suggested rewrite: {mod.get('rewrite')}")
        # Optional: enqueue to review dashboard; show suggestion for user to re-submit
    else:
        # Use rewrite if moderation suggested one (rewrite may be None)
        prompt_to_send = mod.get("rewrite") or user_input

        # Save user message
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        # Generate AI response
        ai_resp = generate_ai_response(prompt_to_send)
        # Generate audio
        audio_b64 = generate_audio(ai_resp) if ai_resp else ""
        # Save assistant message
        st.session_state.chat_history.append({"role": "assistant", "content": ai_resp, "audio": audio_b64})
        # Rerun to render chat immediately (safe modern API)
        st.rerun()

# ---------------------------- Export / Download Chat (main area) ----------------------------
if st.session_state.chat_history:
    with st.expander("Export / Download Chat", expanded=False):
        text_export = "\n\n".join([f"{e['role'].capitalize()}: {e['content']}" for e in st.session_state.chat_history])
        if DOCX_AVAILABLE:
            if st.button("Export as DOCX", key="export_docx_main"):
                doc = Document()
                doc.add_heading("AI Sales Call Assistant Export", 0)
                doc.add_paragraph(f"Brand: {brand.upper()} | Date: {datetime.now().strftime('%Y-%m-%d')}")
                doc.add_paragraph(text_export)
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
                doc.save(tmp.name)
                with open(tmp.name, "rb") as f:
                    st.download_button("⬇️ Download DOCX", f, file_name=f"{brand}_chat.docx", key="download_docx2")
        st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{brand}_chat.txt", key="download_txt_main")

# ---------------------------- Disclaimer ----------------------------
st.markdown("""
<style>
.fixed-disclaimer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: rgba(255, 255, 255, 0.95);
    color: #444;
    text-align: center;
    font-size: 12px;
    padding: 8px;
    border-top: 2px solid #FF6F00;
    z-index: 9999;
}
</style>
<div class="fixed-disclaimer">
<b>Disclaimer:</b> ⚠️ For internal GSK use only. This AI assistant is designed to support field force preparation and must not be used for direct promotional communication with HCPs. Always verify with approved product information and compliance guidance.
</div>
""", unsafe_allow_html=True)
