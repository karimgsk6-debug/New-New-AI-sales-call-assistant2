# app.py (final merged & fixed)
import streamlit as st
from PIL import Image
from io import BytesIO
import re
import tempfile
import base64
import os
from datetime import datetime
from groq import Groq
from PyPDF2 import PdfReader
from html import escape
import requests

# Optional DOCX export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ModuleNotFoundError:
    DOCX_AVAILABLE = False

# ElevenLabs availability
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except ModuleNotFoundError:
    ELEVENLABS_AVAILABLE = False

from gtts import gTTS

# ---------------------------- Secrets / Client init ----------------------------
ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    try:
        elevenlabs.api_key = ELEVENLABS_API_KEY
    except Exception:
        pass

GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = None
if GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

# ---------------------------- Page config ----------------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- Session defaults ----------------------------
if "chat_history" not in st.session_state:
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
if "prefill_input" not in st.session_state:
    st.session_state.prefill_input = ""
# Ensure main_input exists in session_state (text area will use this key)
if "main_input" not in st.session_state:
    st.session_state.main_input = ""

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Background1.jpeg"
GSK_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/gsk-logo.png"
AI_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/ai-logo.png"

CSS = f"""
<style>
body {{
    background-image: url('{BACKGROUND_URL}');
    background-attachment: fixed;
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
}}
@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(-10px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}
.title-box {{
 background: rgba(230,230,230,0.85);
 padding: 12px;
 margin: 12px auto;
 width: 1200px;
 position: relative;
 animation: fadeIn 1.2s ease-in-out;
 border-radius: 10px;
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
  max-height: 55vh;
  overflow-y: auto;
  padding: 12px;
  border-radius: 10px;
  background: rgba(255,255,255,0.85);
  margin-bottom: 20px;
}}
.chat-bubble-user, .chat-bubble-ai, .chat-bubble-audio {{
 display:block;
 padding:12px;
 margin:8px 0;
 border-radius:12px;
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
   max-width: calc(100% - 40px);
}}
.copilot-row {{
    display:flex;
    gap:8px;
    flex-wrap:wrap;
    margin-bottom:10px;
}}
.copilot-pill {{
    background: rgba(255,255,255,0.95);
    border:1px solid #ddd;
    padding:8px 12px;
    border-radius:18px;
    cursor:pointer;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
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
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- Brand Configurations ----------------------------
def safe_makedirs(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass

safe_makedirs(".devcontainer/references/shingrix")
safe_makedirs(".devcontainer/references/jemperli")
safe_makedirs(".devcontainer/references/trelegy")
safe_makedirs(".devcontainer/SalesModule/shingrix")
safe_makedirs(".devcontainer/SalesModule/jemperli")
safe_makedirs(".devcontainer/SalesModule/trelegy")

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
    },
    "trelegy": {
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Concerns about side effects", "Cost/coverage"],
        "references_path": ".devcontainer/references/trelegy/"
    }
}

specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Rheumatologist", "Internal medicine", "Oncologist", "Pulmonologist"]
objectives = ["Awareness", "Adoption", "Retention"]

# ---------------------------- Helpers ----------------------------
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

def generate_audio(text):
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        tts_text = re.sub(r'[,*]{1,}', '', text)
        if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
            audio_stream = elevenlabs.generate(text=tts_text, voice=ELEVENLABS_VOICE_ID, stream=True)
            with open(tmp_file.name, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
        else:
            tts = gTTS(text=tts_text, lang="en", slow=False)
            tts.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            audio_bytes = f.read()
        return base64.b64encode(audio_bytes).decode()
    except Exception as e:
        st.warning(f"Audio generation failed: {e}")
        return ""

def generate_ai_response(user_input, brand, persona, segment, specialty, objective, barrier_list, local_ref_text, external_text, sales_module_text):
    # Build combined context (local refs + external + sales module + uploaded pdf)
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
    elif brand.lower() == "trelegy":
        call_flow_prompt = "\n\n--- trelegy Call Flow Steps ---\n" + "\n".join([f"{k}: {v}" for k, v in trelegy_CALL_FLOW.items()])

    context_prompt = f"""
Brand: {brand}
Persona: {persona}
Segment: {segment}
Specialty: {specialty}
Objective: {objective}
Barriers: {', '.join(barrier_list) if barrier_list else 'None'}
Medical + Sales + Uploaded PDF Context (truncated):\n{combined_context[:5000]}
{call_flow_prompt}
"""

    system_prompt = "You are a pharmaceutical AI assistant. Tailor responses using references, sales modules, uploaded PDFs, and follow the structured brand-specific call flow."
    final_prompt = f"{user_input}\n\n{context_prompt}"

    # If GROQ client not available, return fallback message (so app doesn't crash)
    if client is None:
        return f"(Fallback) No GROQ client available. Using local references to build answer. Received: {user_input}"

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": final_prompt}],
            temperature=0.6
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"(AI Error) Could not generate response: {e}"

# ---------------------------- Call flows ----------------------------
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

trelegy_CALL_FLOW = {
    "Prepare": "Assess inhaler technique and adherence; identify eligible patients.",
    "Engage": "Open with symptom-based questions and real-world adherence evidence.",
    "Demonstrate": "Discuss inhaler technique and patient education points.",
    "Address Access": "Clarify formulary and reimbursement options; offer support materials.",
    "Close": "Agree on next steps, demos, or patient follow-up; document in CRM."
}

# ---------------------------- Sidebar ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", list(brand_data.keys()), index=0, key="select_brand")
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
            try:
                doc = Document()
                doc.add_heading("AI Sales Call Assistant Export", 0)
                doc.add_paragraph(f"Brand: {brand.upper()} | Date: {datetime.now().strftime('%Y-%m-%d')}")
                doc.add_paragraph(text_export)
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
                doc.save(tmp.name)
                st.download_button("⬇️ Download DOCX", open(tmp.name, "rb"), file_name=f"{brand}_chat.docx")
            except Exception as e:
                st.error(f"Could not export DOCX: {e}")
        else:
            st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{brand}_chat.txt")

if st.sidebar.button("🗑️ Clear Chat"):
    st.session_state.chat_history = []

# ---------------------------- Title / Header ----------------------------
st.markdown(f'''
<div class="title-box">
   <img src="{GSK_LOGO_URL}" width="140">
   <img src="{AI_LOGO_URL}" class="ai-logo">
   <h1>💡 AI Sales Call Assistant</h1>
   <p>Empowering reps for smarter <b style="color:#FF6F00;">{brand.upper()}</b> conversations</p>
    <button onclick="window.location.reload();" style="position:absolute;top:10px;right:10px;">🔄 Reset</button>
</div>
''', unsafe_allow_html=True)

# ---------------------------- Medical & Sales References ----------------------------
# Load local references and sales module once per render so we can pass into the AI call
local_ref_text, local_warning = load_local_references(selected_brand["references_path"])
if local_warning:
    st.info(local_warning)

external_text = load_external_references([u for u in external_urls if u.strip()]) if external_urls else ""
sales_module_text, sales_warning = load_local_references(f".devcontainer/SalesModule/{brand}")
if sales_warning:
    st.info(sales_warning)

st.markdown(f"## 📚 {brand.capitalize()} Medical References")
if local_ref_text or external_text:
    with st.expander("🔍 Preview Combined Medical References", expanded=False):
        preview_text = (local_ref_text + "\n" + external_text).strip()
        st.text_area("Medical Reference Preview", preview_text[:3000], height=250)

st.markdown(f"## 📝 Sales Call Module for {brand}")
if sales_module_text:
    with st.expander("🔍 Preview SalesModule Documents", expanded=False):
        st.text_area("Sales Module Preview", sales_module_text[:3000] + ("..." if len(sales_module_text) > 3000 else ""), height=250)

# ---------------------------- PDF Upload & Summary ----------------------------
with st.expander("📄 Upload Custom PDF for AI Context", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
    st.session_state.pdf_summary_size = st.radio("PDF Summary Size", ["Consisted", "Normal", "Detailed"], horizontal=True)
    if uploaded_pdf:
        try:
            reader = PdfReader(uploaded_pdf)
            full_text_pdf = "".join([p.extract_text() or "" for p in reader.pages])
            st.session_state.uploaded_pdf_text = full_text_pdf
            st.success(f"✅ Loaded {len(full_text_pdf)} characters from uploaded PDF.")
            bullets_count = {"Consisted": 5, "Normal": 10, "Detailed": 20}.get(st.session_state.pdf_summary_size, 10)
            try:
                if client:
                    summary_prompt = f"Summarize this document into {bullets_count} bullet points:\n{full_text_pdf[:12000]}"
                    ai_summary = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "system", "content": "You are a helpful assistant."},
                                  {"role": "user", "content": summary_prompt}],
                        temperature=0.4
                    )
                    st.session_state.pdf_summary = ai_summary.choices[0].message.content
                else:
                    fallback_bullets = re.findall(r'([A-Z][^.]{20,200})', full_text_pdf)
                    st.session_state.pdf_summary = "\n".join(fallback_bullets[:bullets_count])
            except Exception:
                fallback_bullets = re.findall(r'([A-Z][^.]{20,200})', full_text_pdf)
                st.session_state.pdf_summary = "\n".join(fallback_bullets[:bullets_count])
        except Exception as e:
            st.error(f"Error reading uploaded PDF: {e}")
    if st.session_state.pdf_summary:
        st.markdown(f'<div class="pdf-summary-box">{escape(st.session_state.pdf_summary)}</div>', unsafe_allow_html=True)

# ---------------------------- Chat container (existing history) ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for item in st.session_state.chat_history:
    if isinstance(item, dict) and item.get("role") == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(item.get("content",""))}</div>', unsafe_allow_html=True)
    elif isinstance(item, dict) and item.get("role") == "assistant":
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(item.get("content",""))}</div>', unsafe_allow_html=True)
        if item.get("audio"):
            try:
                st.audio(base64.b64decode(item["audio"]), format="audio/mp3")
            except Exception:
                pass
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Copilot suggestions (appear only when typing) ----------------------------
def make_brand_suggestions(brand, persona, barrier_list, segment, specialty, objective):
    suggestions = []
    suggestions.append(f"Generate call flow for {persona} focused on {objective}.")
    if barrier_list:
        suggestions.append(f"Handle objection: {', '.join(barrier_list[:2])} for {persona}.")
    else:
        suggestions.append(f"Identify common objections for {persona}.")
    suggestions.append(f"Summarize HCP persona insights for {persona}.")
    suggestions.append(f"Key talking points for {brand} in {segment}.")
    suggestions.append(f"Draft a short adoption message for {brand} to a {specialty}.")
    return suggestions

# Render suggestions only when user has started typing (main_input non-empty)
current_input = st.session_state.get("main_input", "")
if current_input and current_input.strip():
    suggestions = make_brand_suggestions(brand, persona, barrier, segment, specialty, objective)
    st.markdown('<div class="copilot-row">', unsafe_allow_html=True)
    for i, s in enumerate(suggestions):
        # when clicked, set the text area content (autofill) by modifying session_state["main_input"]
        if st.button(s, key=f"copilot_{i}"):
            # safe set inside a widget handler
            st.session_state.main_input = s
            # set prefill as well
            st.session_state.prefill_input = s
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Chat Input FORM (safe submit) ----------------------------
with st.form(key="chat_form", clear_on_submit=False):
    # Use the session_state main_input as controlled value
    user_text = st.text_area("Ask or continue your sales dialogue...", value=st.session_state.get("main_input", ""), key="main_textarea", height=120)
    submit = st.form_submit_button("Send")

    if submit:
        user_text = user_text.strip()
        if user_text:
            # store user message
            st.session_state.chat_history.append({"role": "user", "content": user_text})
            # reset main_input safely here
            st.session_state.main_input = ""
            st.session_state.prefill_input = ""

            # prepare references & context (already loaded above)
            local_ref_text2 = local_ref_text
            sales_module_text2 = sales_module_text
            external_text2 = external_text

            # generate AI response (uses local refs + sales module)
            ai_resp = generate_ai_response(user_text, brand, persona, segment, specialty, objective, barrier, local_ref_text2, external_text2, sales_module_text2)

            # generate audio
            audio_base64 = generate_audio(ai_resp) if ai_resp else ""

            # store assistant message with link note to references
            assistant_content = ai_resp
            # append a short footer listing which sources were used (local paths)
            sources_footer = "\n\nSources used:\n"
            sources_footer += f"- Local refs: {selected_brand['references_path']}\n"
            sources_footer += f"- Sales module: .devcontainer/SalesModule/{brand}\n"
            assistant_content = assistant_content + sources_footer

            st.session_state.chat_history.append({"role": "assistant", "content": assistant_content, "audio": audio_base64})

            # success feedback (no experimental_rerun)
            st.success("Message sent — AI response added to chat.")

# ---------------------------- Export bottom fallback ----------------------------
if st.session_state.chat_history:
    with st.expander("💾 Export / Download Chat", expanded=False):
        text_export = "\n\n".join([f"{e['role'].capitalize()}: {e['content']}" for e in st.session_state.chat_history])
        if DOCX_AVAILABLE:
            if st.button("Export as DOCX", key="export_docx"):
                try:
                    doc = Document()
                    doc.add_heading("AI Sales Call Assistant Export", 0)
                    doc.add_paragraph(f"Brand: {brand.upper()} | Date: {datetime.now().strftime('%Y-%m-%d')}")
                    doc.add_paragraph(text_export)
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
                    doc.save(tmp.name)
                    st.download_button("⬇️ Download DOCX", open(tmp.name, "rb"), file_name=f"{brand}_chat.docx")
                except Exception as e:
                    st.error(f"Could not create DOCX: {e}")
        st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{brand}_chat.txt")

# ---------------------------- Disclaimer ----------------------------
st.markdown('<div class="fixed-disclaimer">⚠️ This AI tool provides sales guidance. Verify all medical content before use. All interactions are logged.</div>', unsafe_allow_html=True)
