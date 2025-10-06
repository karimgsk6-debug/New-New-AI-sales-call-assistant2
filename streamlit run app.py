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

from gtts import gTTS

ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "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")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    elevenlabs.api_key = ELEVENLABS_API_KEY
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

@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(-10px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.title-box {{
  background: rgba(240,240,240,0.7);
  padding: 15px;
  border-radius: 16px;
  text-align: left;
  margin: 12px auto;
  width: 850px;
  position: relative;
  animation: fadeIn 1.2s ease-in-out;
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

# ensure directory structure exists
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

# ---------------------------- Helper: Load Local & External References ----------------------------
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
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT", "DOCX"], horizontal=True)
    if st.button("💾 Export Chat"):
        text_export = "\n\n".join([f"{e['role'].capitalize()}: {e['content']}" for e in st.session_state.chat_history])
        if export_format == "DOCX" and DOCX_AVAILABLE:
            doc = Document()
            doc.add_heading("AI Sales Call Assistant Export", 0)
            doc.add_paragraph(f"Brand: {brand.upper()} | Date: {datetime.now().strftime('%Y-%m-%d')}")
            doc.add_paragraph(text_export)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            doc.save(tmp.name)
            st.download_button("⬇️ Download DOCX", open(tmp.name, "rb"), file_name=f"{brand}_chat.docx")
        else:
            st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{brand}_chat.txt")
    # Clear Chat button (no confirmation as requested)
    # ---------------------------- Clear Chat Button ----------------------------
    if st.sidebar.button("🗑️ Clear Chat"):
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

# ---------------------------- Medical References (Local + External) ----------------------------
st.markdown(f"## 📚 {brand.capitalize()} Medical References")
local_ref_text, local_warning = load_local_references(selected_brand["references_path"])
if local_warning:
    st.info(local_warning)

# external_text loaded from sidebar external_urls
external_text = load_external_references([u for u in external_urls if u.strip()])

if local_ref_text or external_text:
    with st.expander("🔍 Preview Combined Medical References", expanded=False):
        preview_text = (local_ref_text + "\n" + external_text).strip()
        st.text_area("Medical Reference Preview", preview_text[:3000], height=250)

# ---------------------------- Sales Call Module (per-brand SalesModule folder) ----------------------------
st.markdown(f"## 📝 Sales Call Module for {brand}")
sales_module_path = f".devcontainer/SalesModule/{brand}"
sales_module_text, sales_warning = load_local_references(sales_module_path)
if sales_warning:
    st.info(sales_warning)
if sales_module_text:
    with st.expander("🔍 Preview SalesModule Documents", expanded=False):
        st.text_area(
            "Sales Module Preview",
            sales_module_text[:3000] + "..." if len(sales_module_text) > 3000 else sales_module_text,
            height=250
        )
        sales_search_keyword = st.text_input("Search keyword in sales modules", key="sales_search_keyword")
        if sales_search_keyword:
            matches = [m.start() for m in re.finditer(sales_search_keyword, sales_module_text, re.IGNORECASE)]
            st.write(f"Found {len(matches)} matches for '{sales_search_keyword}'.")

# ---------------------------- PDF Upload & Summary ----------------------------
with st.expander("📄 Upload Custom PDF for AI Context", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
    st.session_state.pdf_summary_size = st.radio("PDF Summary Size", ["Consisted", "Normal", "Detailed"], horizontal=True)
    if uploaded_pdf:
        try:
            reader = PdfReader(uploaded_pdf)
            full_text = "".join([p.extract_text() or "" for p in reader.pages])
            st.session_state.uploaded_pdf_text = full_text
            st.success(f"✅ Loaded {len(full_text)} characters from uploaded PDF.")
            # Create summary using Groq model (fallback to simple extraction if model call fails)
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
                # fallback: extract candidate sentences
                fallback_bullets = re.findall(r'([A-Z][^.]{20,200})', full_text)
                st.session_state.pdf_summary = "\n".join(fallback_bullets[:bullets_count])
        except Exception as e:
            st.error(f"Error reading uploaded PDF: {e}")
    if st.session_state.pdf_summary:
        st.markdown(f'<div class="pdf-summary-box">{escape(st.session_state.pdf_summary)}</div>', unsafe_allow_html=True)

# ---------------------------- Call Flows (kept from earlier) ----------------------------
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

# ---------------------------- Audio Generation ----------------------------
def generate_audio(text):
    """Generate TTS audio for the AI response"""
    for step in ["Acknowledge", "Probing", "Action", "Confirm", "Transition"]:
        text = text.replace(step, f"{step} ...")
    # remove some punctuation for clearer TTS
    text = re.sub(r'[,*]', '', text)
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        if ELEVENLABS_AVAILABLE:
            # generate via ElevenLabs
            audio_stream = elevenlabs.generate(text=text, voice=ELEVENLABS_VOICE_ID, stream=True)
            with open(tmp_file.name, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
        else:
            # fallback to gTTS
            tts = gTTS(text=text, lang="en", slow=True)
            tts.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            audio_bytes = f.read()
            audio_base64 = base64.b64encode(audio_bytes).decode()
        return audio_base64
    except Exception as e:
        st.warning(f"Audio generation failed: {e}")
        return ""

# ---------------------------- AI Response Generation ----------------------------
def generate_ai_response(user_input):
    # Build combined context from local refs, external refs, sales module, uploaded pdf
    combined_context = "\n".join([
        local_ref_text or "",
        external_text or "",
        sales_module_text or "",
        st.session_state.uploaded_pdf_text or ""
    ])[:15000]

    # include call flow depending on brand
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

    system_prompt = "You are a pharmaceutical AI assistant. Tailor responses using references, sales modules, uploaded PDFs, and follow the structured brand-specific call flow."
    final_prompt = f"{user_input}\n\n{context_prompt}"

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": final_prompt}],
            temperature=0.65
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"AI generation failed: {e}")
        # fallback simple echo / structured template
        fallback = f"(Fallback) Based on brand {brand}, persona {persona}: {user_input}"
        return fallback

# ---------------------------- Chat UI ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for item in st.session_state.chat_history:
    if isinstance(item, dict) and item.get("role") == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(item.get("content",""))}</div>', unsafe_allow_html=True)
    elif isinstance(item, dict) and item.get("role") == "assistant":
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(item.get("content",""))}</div>', unsafe_allow_html=True)
        if item.get("audio"):
            # display audio player
            try:
                st.audio(base64.b64decode(item["audio"]), format="audio/mp3")
            except Exception:
                pass
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Chat Input ----------------------------
# Use chat_input for a simple bottom input
user_input = st.chat_input("Ask or continue your sales dialogue...")
if user_input:
    # store user message
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    # generate AI response
    ai_resp = generate_ai_response(user_input)
    # generate audio
    audio_base64 = generate_audio(ai_resp) if ai_resp else ""
    # store assistant message
    st.session_state.chat_history.append({"role": "assistant", "content": ai_resp, "audio": audio_base64})
    # rerun to show message immediately
    st.experimental_rerun()

# ---------------------------- Export (bottom fallback if not used in sidebar) ----------------------------
# Keep export options accessible also in main area if desired
if st.session_state.chat_history:
    with st.expander("Export / Download Chat", expanded=False):
        text_export = "\n\n".join([f"{e['role'].capitalize()}: {e['content']}" for e in st.session_state.chat_history])
        if DOCX_AVAILABLE:
            if st.button("Export as DOCX"):
                doc = Document()
                doc.add_heading("AI Sales Call Assistant Export", 0)
                doc.add_paragraph(f"Brand: {brand.upper()} | Date: {datetime.now().strftime('%Y-%m-%d')}")
                doc.add_paragraph(text_export)
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
                doc.save(tmp.name)
                st.download_button("⬇️ Download DOCX", open(tmp.name, "rb"), file_name=f"{brand}_chat.docx")
        st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{brand}_chat.txt")

# ---------------------------- Disclaimer ----------------------------
st.markdown("""
<div class="fixed-disclaimer">
⚠️ For internal GSK use only. This AI assistant is designed to support field force preparation and must not be used for direct promotional communication with HCPs.
</div>
""", unsafe_allow_html=True)
