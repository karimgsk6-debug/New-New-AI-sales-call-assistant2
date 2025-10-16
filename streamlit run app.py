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
from gtts import gTTS

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
  background-size: auto 130%;
}}
.title-box {{
  background: rgba(230,230,230,0.7);
  padding: 10px;
  border-radius: 15px;
  text-align: left;
  margin: 12px auto;
  width: 1300px;
  position: relative;
}}
.title-box img.ai-logo {{
    position: absolute;
    top: 10px;
    right: 15px;
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
  max-height: 65vh;
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
    font-size: 14px;
    padding: 8px;
    border-top: 2px solid #FF6F00;
    z-index: 9999;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ Client ----------------------------
GROQ_API_KEY = "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"  # <-- Hardcoded key
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Brand Configurations ----------------------------
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

# ---------------------------- Sidebar ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", list(brand_data.keys()))
    selected_brand = brand_data[brand]
    segment = st.selectbox("Segment", selected_brand["segments"])
    persona = st.selectbox("HCP Persona", selected_brand["personas"])
    barrier = st.multiselect("Doctor Barrier", selected_brand["barriers"])
    specialty = st.selectbox("Specialty", specialties)
    objective = st.selectbox("Objective", objectives)
    st.session_state.language = st.radio("Language", ["English", "Arabic"], horizontal=True)

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

# ---------------------------- Load Local & External References ----------------------------
def load_local_references(folder_path):
    text_all = ""
    if not os.path.exists(folder_path):
        return ""
    files = [f for f in os.listdir(folder_path) if f.lower().endswith((".pdf", ".txt"))]
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
        except Exception:
            pass
    return text_all.strip()

def load_external_references(url_list):
    all_text = ""
    for url in url_list:
        try:
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                all_text += r.text + "\n"
        except:
            pass
    return all_text

local_ref_text = load_local_references(selected_brand["references_path"])
external_text = load_external_references([u for u in external_urls if u.strip()])

if local_ref_text or external_text:
    with st.expander(f"📚 {brand.capitalize()} Medical References", expanded=False):
        preview_text = (local_ref_text + "\n" + external_text).strip()
        st.text_area("Medical Reference Preview", preview_text[:3000], height=250)

# ---------------------------- PDF Upload & Summary ----------------------------
with st.expander("📄 Upload PDF for AI Context", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
    if uploaded_pdf:
        reader = PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text
        bullets_count = 10
        try:
            summary_prompt = f"Summarize this document into {bullets_count} bullet points:\n{full_text[:12000]}"
            ai_summary = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "system", "content": "You are a helpful assistant."},
                          {"role": "user", "content": summary_prompt}],
                temperature=0.4
            )
            st.session_state.pdf_summary = ai_summary.choices[0].message.content
        except:
            fallback_bullets = re.findall(r'([A-Z][^.]{20,200})', full_text)
            st.session_state.pdf_summary = "\n".join(fallback_bullets[:bullets_count])
    if st.session_state.pdf_summary:
        st.markdown(f'<div class="pdf-summary-box">{escape(st.session_state.pdf_summary)}</div>', unsafe_allow_html=True)

# ---------------------------- Audio Generation ----------------------------
def generate_audio(text):
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        if ELEVENLABS_AVAILABLE:
            audio_stream = elevenlabs.generate(text=text, voice=ELEVENLABS_VOICE_ID, stream=True)
            with open(tmp_file.name, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
        else:
            tts = gTTS(text=text, lang="en", slow=True)
            tts.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except:
        return ""

# ---------------------------- AI Response ----------------------------
def generate_ai_response(user_input):
    combined_context = "\n".join([local_ref_text, external_text, st.session_state.uploaded_pdf_text])[:15000]
    final_prompt = f"{user_input}\n\nContext:\n{combined_context[:5000]}"
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "You are a pharmaceutical AI assistant."},
                      {"role": "user", "content": final_prompt}],
            temperature=0.65
        )
        return response.choices[0].message.content
    except:
        return f"(Fallback) {user_input}"

# ---------------------------- Chat UI ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for item in st.session_state.chat_history:
    role = item.get("role")
    content = item.get("content")
    if role == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(content)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(content)}</div>', unsafe_allow_html=True)
        if item.get("audio"):
            st.audio(base64.b64decode(item["audio"]), format="audio/mp3")
st.markdown('</div>', unsafe_allow_html=True)

user_input = st.chat_input("Ask or continue your sales dialogue...")
if user_input:
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    ai_resp = generate_ai_response(user_input)
    audio_base64 = generate_audio(ai_resp)
    st.session_state.chat_history.append({"role": "assistant", "content": ai_resp, "audio": audio_base64})
    st.rerun()

# ---------------------------- Export Options (Bottom Fallback) ----------------------------
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
st.markdown(f"""
<div class="fixed-disclaimer">
<b>Disclaimer:</b> ⚠️This AI Sales Call Assistant is intended for educational and informational purposes only. 
It does not replace official medical references, product labeling, or company-approved materials. 
Always verify with the latest approved product information and compliance guidance before use.
</div>
""", unsafe_allow_html=True)
