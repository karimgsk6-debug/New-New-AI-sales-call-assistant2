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
    text = re.sub(r'[.,*]', '', text)
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
  background: rgba(240,240,240,0.7);
  padding: 15px;
  border-radius: 16px;
  text-align: left;
  margin: 12px auto;
  width: 850px;
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
safe_makedirs(".devcontainer/SalesModule/SHINGRIX")
safe_makedirs(".devcontainer/SalesModule/JEMPERLI")

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
    "COCO": "Pre-call planning using customer insights, select patient type, develop thought-provoking questions.",
    "Anchor": "Open conversation with a patient-focused narrative, tailor messaging to the HCP challenge/unmet need.",
    "Engage": "Draw customer in through two-way dialogue, connect clinical data and product messages.",
    "Close": "Gain agreement, define next steps, extend engagement via omni-channel, record insights."
}

SHINGRIX_CALL_FLOW = {
    "Prepare": "Plan the call: identify persona, objectives, patient types, key insights.",
    "Engage": "Start conversation, capture attention, set discussion context.",
    "Create Opportunities": "Identify gaps or unmet needs; introduce solutions with clinical/product data.",
    "Influence": "Present evidence, handle objections, highlight value and outcomes.",
    "Impact GSO": "Link discussion to incremental steps and overall GSO; clarify next steps.",
    "Post-Call Analysis": "Record insights, update CRM, evaluate metrics to inform future calls."
}

# ---------------------------- Load Medical References ----------------------------
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
            r = requests.get(url)
            if r.status_code == 200:
                all_text += r.text + "\n"
            else:
                all_text += f"\n[Could not fetch {url}]"
        except Exception as e:
            all_text += f"\n[Error fetching {url}: {e}]"
    return all_text

# ---------------------------- Medical Reference Section ----------------------------
st.markdown(f"## 📚 {brand} Medical References")
local_ref_text, local_warning = load_local_references(selected_brand["references_path"])
if local_warning:
    st.info(local_warning)

with st.expander("🌐 Add External Reference URLs", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()
external_text = load_external_references([u for u in external_urls if u.strip()])

# Preview combined medical reference
if local_ref_text or external_text:
    with st.expander("🔍 Preview Combined Medical References", expanded=False):
        st.text_area("Medical Reference Preview", (local_ref_text + "\n" + external_text)[:3000], height=250)

# ---------------------------- Sales Call Module ----------------------------
st.markdown(f"## 📝 Sales Call Module for {brand}")
sales_module_text, sales_warning = load_local_references(".devcontainer/SalesModule")
if sales_warning:
    st.info(sales_warning)
if sales_module_text:
    with st.expander("🔍 Preview SalesModule Documents", expanded=False):
        st.text_area(
            "Sales Module Preview",
            sales_module_text[:3000] + "..." if len(sales_module_text) > 3000 else sales_module_text,
            height=250
        )
        sales_search_keyword = st.text_input("Search keyword in sales modules")
        if sales_search_keyword:
            matches = [m.start() for m in re.finditer(sales_search_keyword, sales_module_text, re.IGNORECASE)]
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

# ---------------------------- AI Chat ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for item in st.session_state.chat_history:
    if isinstance(item, tuple) and len(item) == 3:
        user_msg, ai_msg, audio = item
        st.markdown(f'<div class="chat-bubble-user">{escape(user_msg)}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="chat-bubble-ai">{escape(ai_msg)}</div>', unsafe_allow_html=True)
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

# ---------------------------- AI Response Generation ----------------------------
def generate_ai_response(user_input):
    combined_context = (local_ref_text + "\n" + external_text + "\n" + sales_module_text + "\n" + st.session_state.uploaded_pdf_text)[:15000]

    call_flow_prompt = ""
    if brand.upper() == "JEMPERLI":
        call_flow_prompt = "\n\n--- JEMPERLI Call Flow Steps ---\n"
        for step, desc in JEMPERLI_CALL_FLOW.items():
            call_flow_prompt += f"{step}: {desc}\n"
    elif brand.upper() == "SHINGRIX":
        call_flow_prompt = "\n\n--- Shingrix Call Flow Steps ---\n"
        for step, desc in SHINGRIX_CALL_FLOW.items():
            call_flow_prompt += f"{step}: {desc}\n"

    context_prompt = f"""
Brand: {brand}
Persona: {persona}
Segment: {segment}
Specialty: {specialty}
Objective: {objective}
Barriers: {barrier}
Medical + Sales + Uploaded PDF Context:\n{combined_context[:5000]}
{call_flow_prompt}
"""
    system_prompt = "You are a pharmaceutical AI assistant. Tailor responses using references, sales modules, uploaded PDFs, and follow the structured brand-specific call flow."
    final_prompt = f"{user_input}\n\n{context_prompt}"

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": final_prompt}],
        temperature=0.65
    )
    return response.choices[0].message.content

if send and chat_input.strip():
    ai_resp = generate_ai_response(chat_input.strip())
    audio_base64 = generate_audio(ai_resp)
    st.session_state.chat_history.append((chat_input.strip(), ai_resp, audio_base64))

# ---------------------------- Export ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("📥 Export Chat to Word"):
        doc = Document()
        doc.add_heading("AI Sales Call Assistant Chat Export", 0)
        for user_msg, ai_msg, audio in st.session_state.chat_history:
            doc.add_paragraph(f"User: {user_msg}")
            doc.add_paragraph(f"AI: {ai_msg}\n")
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            bytes_data = f.read()
            b64 = base64.b64encode(bytes_data).decode()
            href = f'<a href="data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{b64}" download="AI_Chat.docx">Click to download Word file</a>'
            st.markdown(href, unsafe_allow_html=True)
