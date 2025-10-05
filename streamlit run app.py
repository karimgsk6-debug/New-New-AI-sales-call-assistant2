# app.py
import streamlit as st
from io import BytesIO
import re, os, tempfile, base64
from html import escape
from PyPDF2 import PdfReader
import requests
from groq import Groq

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
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")  # change to your preferred voice ID
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    elevenlabs.api_key = ELEVENLABS_API_KEY
else:
    ELEVENLABS_AVAILABLE = False

def generate_audio(text):
    text = re.sub(r'[{},*]', '', text)
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    if ELEVENLABS_AVAILABLE:
        audio_stream = elevenlabs.generate(text=text, voice=ELEVENLABS_VOICE_ID, stream=True)
        with open(tmp_file.name, "wb") as f:
            for chunk in audio_stream:
                f.write(chunk)
    else:
        tts = gTTS(text=text, lang="en", slow=False)
        tts.save(tmp_file.name)
    with open(tmp_file.name, "rb") as f:
        audio_bytes = f.read()
        audio_base64 = base64.b64encode(audio_bytes).decode()
    return audio_base64

# ---------------------------- App config ----------------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- Session defaults ----------------------------
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state: st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state: st.session_state.pdf_summary = ""
if "voice_pref" not in st.session_state: st.session_state.voice_pref = "Old Male"
if "language" not in st.session_state: st.session_state.language = "English"
if "pdf_summary_size" not in st.session_state: st.session_state.pdf_summary_size = "Normal"

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
.disclaimer-fixed {{
  position: fixed;
  top: 10px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 10010;
  background: rgba(255,255,255,0.8);
  padding: 12px 20px;
  border-radius: 8px;
  text-align:center;
  box-shadow: 0 2px 8px rgba(0,0,0,0.7);
  font-weight: bold;
  font-size: 30px;
  color: black;
}}
.title-box {{
  background: rgba(230,230,230,0.7);
  padding: 5px;
  border-radius: 15px;
  text-align: left;
  margin: 80px auto 12px;
  width: 1500px;
  position: relative;
}}
.title-box img.ai-logo {{
    position: absolute;
    top: 5px;
    right: 10px;
    width: 150px;
}}
.pdf-summary-box {{
  background: #E6F0FF; 
  padding: 12px; 
  border-radius: 14px; 
  margin-bottom: 12px;
  white-space: pre-line;
}}
.chat-container {{
  max-height: 55vh;
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
    bottom: 110px;
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
    bottom: 110px;
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
.footer-space {{ height: 160px; }}
.orange-step {{ color: #FF6900; font-weight:bold; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ client ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
if not GROQ_API_KEY:
    st.warning("⚠️ Missing GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ---------------------------- Helper functions ----------------------------
def safe_makedirs(path):
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except Exception as e:
        st.warning(f"⚠️ Could not create folder {path}: {e}")
        return False

def load_local_references(folder_path):
    text_all = ""
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return "", f"⚠️ Folder does not exist: {folder_path}"
    files = [f for f in os.listdir(folder_path) if f.lower().endswith((".pdf", ".txt"))]
    if not files: return "", f"ℹ️ No files found in {folder_path}"
    for file in files:
        try:
            file_path = os.path.join(folder_path, file)
            if file.lower().endswith(".pdf"):
                reader = PdfReader(file_path)
                for page in reader.pages:
                    text_all += page.extract_text() or ""
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    text_all += f.read()
        except Exception as e:
            text_all += f"\n[Error reading {file}: {e}]"
    return text_all.strip(), None

def load_external_references(url_list):
    all_text = ""
    for url in url_list:
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            if "pdf" in r.headers.get("Content-Type","").lower() or url.lower().endswith(".pdf"):
                reader = PdfReader(BytesIO(r.content))
                for page in reader.pages:
                    all_text += page.extract_text() or ""
            else:
                all_text += r.text + "\n"
        except Exception as e:
            all_text += f"\n[Error fetching {url}: {e}]"
    return all_text

# ---------------------------- Brand Data & Call Flows ----------------------------
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
    "COCO": "Pre-call planning using customer insights to identify persona and call objective. Select a patient type and prepare thought-provoking questions.",
    "Anchor": "Open the conversation using COCO insights; create a patient-focused narrative and align on the call objective.",
    "Engage": "Build two-way dialogue; connect clinical data and product messages and handle objections.",
    "Close": "Gain agreement, set clear next steps, consider omni-channel follow-up and record insights."
}

SHINGRIX_CALL_FLOW = {
    "Prepare": "Plan the call: identify persona, call objectives and select patient types; gather insights to inform messaging.",
    "Engage": "Open the conversation to connect and capture attention; set context using insights.",
    "Create Opportunities": "Identify gaps/unmet needs and present tailored clinical/product data as solutions.",
    "Influence": "Present evidence, handle objections, and highlight value and outcomes.",
    "Impact GSO": "Clarify next steps and link to incremental steps that achieve the Good Sell Outcome.",
    "Post-Call Analysis": "Record insights, update CRM and evaluate success metrics to inform future calls."
}

# ---------------------------- Sidebar filters ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", list(brand_data.keys()), index=0)
    selected_brand = brand_data[brand]
    segment = st.selectbox("Segment", selected_brand["segments"])
    persona = st.selectbox("HCP Persona", selected_brand["personas"])
    barrier = st.multiselect("Doctor Barrier", selected_brand["barriers"])
    specialty = st.selectbox("Specialty", ["GP","Cardiologist","Dermatologist","Endocrinologist","Rheumatologist","Internal medicine","Oncologist"])
    objective = st.selectbox("Objective", ["Awareness","Adoption","Retention"])
    st.session_state.language = st.radio("Language", ["English","Arabic"], horizontal=True)

# ---------------------------- Fixed top-center disclaimer ----------------------------
st.markdown(f'''
<div class="disclaimer-fixed">
⚠️ AI Assistant for <strong>{brand}</strong><br>
AI can make mistakes, validate all responses against GSK-approved materials.
</div>
''', unsafe_allow_html=True)

# ---------------------------- Title ----------------------------
st.markdown(f'''
<div class="title-box">
    <img src="{GSK_LOGO_URL}" width="150">
    <img src="{AI_LOGO_URL}" class="ai-logo">
    <h1>💡 AI Sales Call Assistant</h1>
    <p>Empowering reps for smarter <strong>{brand}</strong> conversations</p>
</div>
''', unsafe_allow_html=True)

# ---------------------------- Load References ----------------------------
local_ref_text, local_warning = load_local_references(selected_brand["references_path"])
sales_folder = f".devcontainer/SalesModule/{brand.upper()}"
safe_makedirs(sales_folder)
sales_module_text, sales_warning = load_local_references(sales_folder)

# ---------------------------- Collapsible reference panels ----------------------------
with st.expander("📚 Medical References (local + external)", expanded=False):
    st.write("Local folder:", selected_brand["references_path"])
    if local_warning: st.info(local_warning)
    if local_ref_text:
        with st.expander("🔍 Preview Local Medical References"):
            st.text_area("Local Medical Reference Preview", local_ref_text[:4000], height=240)
    external_urls_input = st.text_area("Add external medical reference URLs (one per line)", height=120)
    external_urls = [u.strip() for u in (external_urls_input or "").splitlines() if u.strip()]
    external_text = load_external_references(external_urls) if external_urls else ""
    if external_text:
        with st.expander("🔍 Preview External Medical References"):
            st.text_area("External Medical Reference Preview", external_text[:4000], height=240)

# ---------------------------- PDF summary (always visible) ----------------------------
st.markdown("### 📄 Uploaded PDF Summary (always visible)")
st.text_area("PDF Summary", st.session_state.pdf_summary or "No PDF uploaded or no summary available.", height=140)

# ---------------------------- SalesModule panel ----------------------------
with st.expander("🧩 Sales Call Module (local + external)", expanded=False):
    st.write("SalesModule folder:", sales_folder)
    if sales_warning: st.info(sales_warning)
    if sales_module_text:
        with st.expander("🔍 Preview SalesModule Documents"):
            st.text_area("SalesModule Preview", sales_module_text[:4000], height=260)
    sales_urls_input = st.text_area("Optional: Add external SalesModule URLs (one per line)", height=100)
    sales_urls = [u.strip() for u in (sales_urls_input or "").splitlines() if u.strip()]
    sales_external_text = load_external_references(sales_urls) if sales_urls else ""
    if sales_external_text:
        with st.expander("🔍 Preview External SalesModule Content"):
            st.text_area("SalesModule External Preview", sales_external_text[:4000], height=260)

# ---------------------------- Chat input ----------------------------
st.markdown('<div class="chat-container" id="chat-container">', unsafe_allow_html=True)
for chat in st.session_state.chat_history:
    if chat["role"] == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(chat["content"])}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(chat["content"])}</div>', unsafe_allow_html=True)
        if "audio" in chat:
            audio_html = f'''
            <audio controls class="chat-bubble-audio">
                <source src="data:audio/mp3;base64,{chat["audio"]}" type="audio/mp3">
            Your browser does not support the audio element.
            </audio>'''
            st.markdown(audio_html, unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

user_input = st.text_area("Ask AI about the sales call", key="chat_input", height=60)
if st.button("Send", key="send_button") and user_input.strip():
    # ------------------- AI Response Generation -------------------
    # Here you would call your LLM or Groq client and generate collapsible call steps
    # Example placeholder:
    ai_text = f"Generated call steps for {brand}, Segment: {segment}, Persona: {persona}, Barrier: {barrier}"
    audio_b64 = generate_audio(ai_text)
    st.session_state.chat_history.append({"role":"user","content":user_input})
    st.session_state.chat_history.append({"role":"ai","content":ai_text,"audio":audio_b64})
    st.experimental_rerun()

st.markdown('<div class="footer-space"></div>', unsafe_allow_html=True)
