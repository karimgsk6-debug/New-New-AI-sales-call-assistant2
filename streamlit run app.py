# app.py
import streamlit as st
from PIL import Image
from io import BytesIO
import re
import tempfile
import base64
import os
import requests
from groq import Groq
from PyPDF2 import PdfReader
from html import escape

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

# Reference & Sales Module folders
safe_makedirs(".devcontainer/references/shingrix")
safe_makedirs(".devcontainer/references/jemperli")
safe_makedirs(".devcontainer/SalesModule/shingrix")
safe_makedirs(".devcontainer/SalesModule/jemperli")

brand_data = {
    "Shingrix": {
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "references_path": ".devcontainer/references/shingrix",
        "sales_module_path": ".devcontainer/SalesModule/shingrix"
    },
    "JEMPERLI": {
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited patient eligibility", "Access/reimbursement issues"],
        "references_path": ".devcontainer/references/jemperli",
        "sales_module_path": ".devcontainer/SalesModule/jemperli"
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


# ---------------------------- Helper: Load References ----------------------------
def load_references_for_brand(brand_name):
    base_path = brand_data[brand_name]["references_path"]
    all_text = ""
    if not os.path.exists(base_path):
        return "No local references found."

    for file in os.listdir(base_path):
        file_path = os.path.join(base_path, file)
        try:
            if file.lower().endswith(".pdf"):
                reader = PdfReader(file_path)
                for page in reader.pages:
                    all_text += page.extract_text() or ""
            elif file.lower().endswith(".txt"):
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    all_text += f.read()
        except Exception as e:
            all_text += f"\n[Error reading {file}: {e}]"
    return all_text.strip()


# ---------------------------- Medical References ----------------------------
st.markdown(f"## 📚 {brand} Medical References")
ref_path = selected_brand["references_path"]

try:
    reference_files = [f for f in os.listdir(ref_path) if f.lower().endswith((".pdf", ".txt"))]
    if reference_files:
        selected_ref = st.selectbox("Select a reference document", reference_files, key="select_reference")
        file_path = os.path.join(ref_path, selected_ref)
        if selected_ref.lower().endswith(".pdf"):
            with open(file_path, "rb") as f:
                reader = PdfReader(f)
                ref_text = "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                ref_text = f.read()

        with st.expander("🔍 View / Search in Document", expanded=False):
            st.text_area("Document Preview", ref_text[:3000] + "..." if len(ref_text) > 3000 else ref_text, height=250)
            search_keyword = st.text_input("Search keyword")
            if search_keyword:
                matches = [m.start() for m in re.finditer(search_keyword, ref_text, re.IGNORECASE)]
                st.write(f"Found {len(matches)} matches for '{search_keyword}'.")
    else:
        ref_text = "No local references found."
        st.info(ref_text)
except Exception as e:
    ref_text = "No local references found."
    st.warning(f"⚠️ Error loading references: {e}")


# ---------------------------- External References via URLs ----------------------------
st.markdown("## 🌐 Add External Medical References (URL)")
with st.expander("Add URLs for additional medical references", expanded=False):
    ext_urls = st.text_area(
        "Enter PDF/TXT URLs (one per line)",
        placeholder="https://example.com/article1.pdf\nhttps://example.com/article2.txt",
        height=120
    )
    if st.button("📥 Load External References"):
        ext_text = ""
        for url in ext_urls.splitlines():
            url = url.strip()
            if not url:
                continue
            try:
                r = requests.get(url)
                r.raise_for_status()
                content_type = r.headers.get("Content-Type", "")
                if "pdf" in content_type:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                        tmp_file.write(r.content)
                        reader = PdfReader(tmp_file.name)
                        for page in reader.pages:
                            ext_text += page.extract_text() or ""
                else:
                    ext_text += r.text
                st.success(f"Loaded reference from {url}")
            except Exception as e:
                st.error(f"Failed to load {url}: {e}")
        if ext_text:
            ref_text += "\n" + ext_text
            st.info("External references added to AI context.")
# ---------------------------- AI Chat with Sales Call Module ----------------------------
def load_sales_module_for_brand(brand_name):
    """Read all PDFs/TXT files from the brand sales module folder"""
    base_path = brand_data[brand_name]["sales_module_path"]
    all_text = ""
    if not os.path.exists(base_path):
        return "No local sales call modules found."
    
    for file in os.listdir(base_path):
        file_path = os.path.join(base_path, file)
        try:
            if file.lower().endswith(".pdf"):
                reader = PdfReader(file_path)
                for page in reader.pages:
                    all_text += page.extract_text() or ""
            elif file.lower().endswith(".txt"):
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    all_text += f.read()
        except Exception as e:
            all_text += f"\n[Error reading {file}: {e}]"
    return all_text.strip()


def generate_ai_response(user_input):
    # Load all reference contexts
    brand_reference_text = load_references_for_brand(brand)
    sales_module_text = load_sales_module_for_brand(brand)

    # Include external references added by user
    uploaded_pdf_text = st.session_state.uploaded_pdf_text or ""
    
    # Limit text size to prevent overload
    max_context_chars = 15000
    context_prompt = f"""
    Brand: {brand}
    Persona: {persona}
    Segment: {segment}
    Specialty: {specialty}
    Objective: {objective}
    Barriers: {barrier}
    
    Medical References (local + external + uploaded):
    {brand_reference_text[:5000]}
    {uploaded_pdf_text[:5000]}
    
    Sales Call Module:
    {sales_module_text[:5000]}
    """

    system_prompt = "You are a pharmaceutical AI assistant. Tailor responses using all provided references and sales call modules."

    final_prompt = f"{user_input}\n\n{context_prompt}"

    # Call the Groq AI
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": final_prompt}
        ],
        temperature=0.65
    )

    return response.choices[0].message.content
