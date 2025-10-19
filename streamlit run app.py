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

ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    elevenlabs.api_key = ELEVENLABS_API_KEY
else:
    ELEVENLABS_AVAILABLE = False

# ---------------------------- CONFIG ----------------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- Robust Session Defaults ----------------------------
DEFAULTS = {
    "chat_history": [],
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "voice_pref": "Old Male",
    "language": "English",
    "pdf_summary_size": "Normal",
    "chat_input": "",
    "chat_input_box": "",
    "feedback_log": [],            # list of dicts: {"msg_idx", "feedback", "time"}
    "suggestion_index": 0,         # pointer into PROMPT_FLOW
    "user_preferences": {},        # will store inferred prefs from feedback (tone, length)
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------- Assets (background adapts to theme) ----------------------------
BACKGROUND_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Background1.jpeg"
GSK_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/GSK-logo.png"
AI_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/AURA.png"

# ---------------------------- Adaptive CSS (light/dark via prefers-color-scheme) ----------------------------
CSS = f"""
<style>
:root {{
  --bg: #ffffff;
  --muted: #f5f7fb;
  --text: #0b1726;
  --primary: #0078D7;
  --card: rgba(255,255,255,0.95);
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #0b0f14;
    --muted: rgba(255,255,255,0.02);
    --text: #e6eef8;
    --primary: #1ea7ff;
    --card: rgba(9,12,16,0.75);
  }}
}}
html, body [data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-attachment: fixed;
  background-size: cover;
  background-color: var(--bg);
}}

@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(-8px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}

.title-box {{
  background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(255,255,255,0.85));
  padding: 12px;
  border-radius: 12px;
  text-align: left;
  margin: 12px auto;
  width: 1200px;
  position: relative;
  animation: fadeIn 0.9s ease-in-out;
  box-shadow: 0 6px 18px rgba(2,6,23,0.06);
}}

@media (prefers-color-scheme: dark) {{
  .title-box {{
    background: linear-gradient(180deg, rgba(15,18,22,0.9), rgba(9,12,16,0.85));
    box-shadow: none;
  }}
}}

.title-box img.ai-logo {{
    position: absolute;
    top: 8px;
    right: 12px;
    width: 130px;
}}

.pdf-summary-box {{
  background: rgba(230,240,255,0.9); 
  padding: 12px; 
  border-radius: 12px; 
  margin-bottom: 12px;
  white-space: pre-line;
  border: 1px solid rgba(0,0,0,0.04);
}}

.chat-container {{
  max-height: 62vh;
  overflow-y: auto;
  padding: 18px;
  border-radius: 12px;
  background: var(--card);
  margin-bottom: 120px;
  border: 1px solid rgba(0,0,0,0.04);
}}

.chat-bubble-user, .chat-bubble-ai {{
  display:block;
  padding:12px;
  border-radius:12px;
  margin:12px 0;
  max-width: 90%;
  word-wrap: break-word;
}}

.chat-bubble-user {{
  background: var(--primary);
  color: white;
  margin-left: auto;
  box-shadow: 0 4px 12px rgba(2,6,23,0.08);
}}
.chat-bubble-ai {{
  background: linear-gradient(180deg, rgba(217,240,255,0.9), rgba(227,247,255,0.95));
  color: var(--text);
  margin-right: auto;
}}

.fixed-chat-input {{
    position: fixed;
    bottom: 18px;
    left: 24px;
    right: 24px;
    z-index: 10002;
    background: var(--card);
    padding: 10px;
    border-radius: 10px;
    box-shadow: 0 10px 30px rgba(2,6,23,0.08);
}}

.fixed-chat-input textarea {{
    width: 100%;
    min-height: 64px;
    max-height: 240px;
    resize: vertical;
    border-radius: 8px;
}}

.send-button {{
    position: absolute;
    right: 12px;
    bottom: 12px;
}}

.prompt-suggestions {{
  display:flex;
  gap:10px;
  padding:10px;
  margin:6px 0 10px 0;
  position: sticky;
  bottom: 100px; /* sits just above fixed input */
  background: rgba(255,255,255,0.92);
  border-radius: 12px;
  z-index: 9998;
  align-items:center;
  box-shadow: 0 8px 20px rgba(2,6,23,0.06);
}}
@media (prefers-color-scheme: dark) {{
  .prompt-suggestions {{
    background: rgba(12,14,17,0.85);
  }}
}}
.suggestion-pill {{
  display:flex;
  align-items:center;
  gap:8px;
  padding:8px 14px;
  border-radius:999px;
  background: var(--primary);
  color: white;
  cursor:pointer;
  font-size:14px;
}}
.suggestion-pill.secondary {{
  background: transparent;
  color: var(--text);
  border: 1px solid rgba(0,0,0,0.06);
}}
.feedback-row {{
  display:flex;
  gap:8px;
  margin-top:8px;
}}
.feedback-btn {{
  padding:8px 10px;
  border-radius:8px;
  border: none;
  cursor:pointer;
  background:#f0f0f0;
}}
.feedback-btn:hover {{ background: var(--primary); color: white; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ Client ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "")
if not GROQ_API_KEY:
    st.warning("⚠️ Missing GROQ_API_KEY in Streamlit Secrets")
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Ensure directories ----------------------------
def safe_makedirs(path):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass

safe_makedirs(".devcontainer/references/shingrix")
safe_makedirs(".devcontainer/references/jemperli")
safe_makedirs(".devcontainer/SalesModule/shingrix")
safe_makedirs(".devcontainer/SalesModule/jemperli")

# ---------------------------- Brand data ----------------------------
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

# ---------------------------- Helpers: load references ----------------------------
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
                for p in reader.pages:
                    text_all += p.extract_text() or ""
            elif file.lower().endswith(".txt"):
                with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                    text_all += fh.read()
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
        text_export = "\n\n".join([f"{e['role'].capitalize()}: {e['content']}" for e in st.session_state.chat_history if isinstance(e, dict)])
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
                st.error(f"Export DOCX failed: {e}")
        else:
            st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{brand}_chat.txt")

if st.sidebar.button("🗑️ Clear Chat"):
    st.session_state.chat_history = []
    st.session_state.update({"chat_input": "", "chat_input_box": ""})
    st.experimental_rerun()

# ---------------------------- Title / Header ----------------------------
st.markdown(f'''
<div class="title-box">
    <img src="{GSK_LOGO_URL}" width="140">
    <img src="{AI_LOGO_URL}" class="ai-logo">
    <h1>💡 AI Sales Call Assistant</h1>
    <p>Empowering reps for smarter <b style="color:#FF6F00;">{brand.upper()}</b> conversations</p>
</div>
''', unsafe_allow_html=True)

# ---------------------------- Load references and sales module previews ----------------------------
local_ref_text, local_warning = load_local_references(selected_brand["references_path"])
if local_warning:
    st.info(local_warning)

external_text = load_external_references([u for u in external_urls if u.strip()])

sales_module_path = f".devcontainer/SalesModule/{brand}"
sales_module_text, sales_warning = load_local_references(sales_module_path)
if sales_warning:
    st.info(sales_warning)

# ---------------------------- PROMPT FLOW (Copilot-like aggregated suggestions) ----------------------------
PROMPT_FLOW = [
    "Generate call flow for this HCP",
    "Specify patient profile",
    "Add probing questions for barriers",
    "Emotive vaccination value",
    "Assertive questions to gain commitment",
    "Patient-oriented engagement",
    "Cost-benefit value approach",
    "Handle barrier for patient profile",
    "Summarize key evidence for quick mention",
    "Ask for next steps / commitment"
]

def get_current_suggestions(count=2):
    idx = st.session_state.get("suggestion_index", 0) % len(PROMPT_FLOW)
    return [PROMPT_FLOW[(idx + i) % len(PROMPT_FLOW)] for i in range(count)]

def advance_suggestion_index(step=1):
    st.session_state.update({"suggestion_index": (st.session_state.get("suggestion_index", 0) + step) % len(PROMPT_FLOW)})

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

# ---------------------------- Call flows (kept) ----------------------------
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

# ---------------------------- Audio helpers ----------------------------
def enhance_text_for_tts(text):
    text = re.sub(r',', ', ', text)
    text = re.sub(r'\.', '. ', text)
    text = re.sub(r'\?', '? ', text)
    text = re.sub(r'!', '! ', text)
    text = re.sub(r'\s+', ' ', text)
    return text

def generate_audio_base64(text):
    if not text:
        return ""
    text_for_tts = enhance_text_for_tts(text)[:3000]
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        if ELEVENLABS_AVAILABLE:
            audio_stream = elevenlabs.generate(text=text_for_tts, voice=ELEVENLABS_VOICE_ID, stream=True)
            with open(tmp_file.name, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
        else:
            tts = gTTS(text=text_for_tts, lang="en", slow=True)
            tts.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""

# ---------------------------- Adaptive instructions from feedback ----------------------------
def construct_feedback_style_instructions():
    """
    Convert feedback_log into simple style adjustments:
    - If recent likes dominate -> keep tone/length
    - If recent dislikes -> switch tone or shorten/lengthen
    - If many 'need_more' -> produce more alternatives by default
    """
    fb = st.session_state.get("feedback_log", [])
    if not fb:
        return ""
    last_n = fb[-6:]  # last few feedback entries
    counts = {"like": 0, "dislike": 0, "need_more": 0}
    for e in last_n:
        f = str(e.get("feedback","")).lower()
        if "like" in f: counts["like"] += 1
        if "dislike" in f: counts["dislike"] += 1
        if "need" in f or "more" in f: counts["need_more"] += 1
    instructions = []
    if counts["like"] > counts["dislike"]:
        instructions.append("Preserve the current tone and structure (user liked recent replies).")
    if counts["dislike"] > counts["like"]:
        instructions.append("Adjust tone: be more concise and change phrasing; avoid prior structure.")
    if counts["need_more"] >= 1:
        instructions.append("Offer at least 2 brief alternative phrasings where relevant.")
    return " ".join(instructions)

# ---------------------------- AI generation (with feedback influence) ----------------------------
def sanitize_user_input(text):
    return escape(text.strip())

def is_safe_content(text):
    blockers = ["sex", "violence", "attack", "terror"]
    return not any(b in text.lower() for b in blockers)

def generate_ai_response_user(user_input):
    safe_prompt = sanitize_user_input(user_input)
    if not is_safe_content(safe_prompt):
        return "(⚠️ Unsafe prompt blocked)"

    # combined context
    combined_context = "\n".join([local_ref_text or "", external_text or "", sales_module_text or "", st.session_state.uploaded_pdf_text or ""])[:15000]

    call_flow_prompt = ""
    if brand.lower() == "jemperli":
        call_flow_prompt = "\n\n--- jemperli Call Flow Steps ---\n" + "\n".join([f"{k}: {v}" for k, v in jemperli_CALL_FLOW.items()])
    elif brand.lower() == "shingrix":
        call_flow_prompt = "\n\n--- shingrix Call Flow Steps ---\n" + "\n".join([f"{k}: {v}" for k, v in shingrix_CALL_FLOW.items()])

    feedback_instructions = construct_feedback_style_instructions()

    context_prompt = f"""
Brand: {brand}
Persona: {persona}
Segment: {segment}
Specialty: {specialty}
Objective: {objective}
Barriers: {', '.join(barrier) if barrier else 'None'}
Medical + Sales + Uploaded PDF Context (truncated):\n{combined_context[:4000]}
{call_flow_prompt}
User feedback guidance: {feedback_instructions}
"""
    system_prompt = "You are a concise pharmaceutical sales assistant. Use context to answer succinctly and practically."
    final_prompt = f"{safe_prompt}\n\n{context_prompt}"

    # Adapt simple params based on feedback (affects model temperature / length suggestions)
    temperature = 0.6
    if "Adjust tone" in feedback_instructions:
        temperature = 0.45
    if "Offer at least 2 brief alternative" in feedback_instructions:
        temperature = 0.75

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": final_prompt}],
            temperature=temperature
        )
        return response.choices[0].message.content
    except Exception:
        # fallback
        return f"(Fallback) Based on brand {brand}, persona {persona}: {user_input}"

# ---------------------------- Generate alternatives (Need more options) ----------------------------
def generate_more_options_for(idx, base_text, n=2):
    prompt = f"Provide {n} brief alternative phrasings to use in a sales call for the following response, labeled 'Alternative 1' etc:\n\n{base_text}"
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": "You are a helpful assistant creating short alternative phrasings."},
                      {"role": "user", "content": prompt}],
            temperature=0.8
        )
        alt_text = response.choices[0].message.content
    except Exception:
        alt_text = "\n".join([f"Alternative {i+1}: {base_text} (variant {i+1})" for i in range(n)])
    # parse alternatives
    alts = [a.strip() for a in re.split(r'\n{1,}', alt_text) if a.strip()]
    insert_pos = idx + 1
    for alt in alts[:n]:
        st.session_state.chat_history.insert(insert_pos, {"role": "assistant", "content": alt, "audio": generate_audio_base64(alt), "meta": "alternative"})
        insert_pos += 1

# ---------------------------- Chat container (display) ----------------------------
chat_container = st.container()
with chat_container:
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for idx, entry in enumerate(st.session_state.chat_history):
        if not isinstance(entry, dict):
            continue
        if entry.get("role") == "user":
            st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(entry.get("content",""))}</div>', unsafe_allow_html=True)
        else:
            content_html = escape(entry.get("content",""))
            st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {content_html}</div>', unsafe_allow_html=True)
            if entry.get("audio"):
                try:
                    st.audio(base64.b64decode(entry["audio"]), format="audio/mp3")
                except Exception:
                    pass

            # Feedback buttons under each assistant message
            cols = st.columns([1,1,1,1])
            with cols[0]:
                if st.button("👍 Like", key=f"like_{idx}"):
                    st.session_state.feedback_log.append({"msg_idx": idx, "feedback": "like", "time": datetime.utcnow().isoformat()})
                    st.success("Recorded 👍 — AI will keep similar style.")
            with cols[1]:
                if st.button("👎 Dislike", key=f"dislike_{idx}"):
                    st.session_state.feedback_log.append({"msg_idx": idx, "feedback": "dislike", "time": datetime.utcnow().isoformat()})
                    st.warning("Recorded 👎 — AI will adjust tone/structure.")
            with cols[2]:
                if st.button("🔄 Need More", key=f"more_{idx}"):
                    st.session_state.feedback_log.append({"msg_idx": idx, "feedback": "need_more", "time": datetime.utcnow().isoformat()})
                    st.info("Generating alternatives...")
                    generate_more_options_for(idx, entry.get("content",""), n=2)
                    # advance suggestions
                    advance_suggestion_index(1)
                    st.experimental_rerun()
            with cols[3]:
                if st.button("✍️ Suggest edit", key=f"edit_{idx}"):
                    st.session_state.feedback_log.append({"msg_idx": idx, "feedback": "suggest_edit", "time": datetime.utcnow().isoformat()})
                    st.info("Suggestion recorded.")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Suggestion bar (above bottom input) ----------------------------
with st.container():
    suggs = get_current_suggestions(count=2)
    st.markdown('<div class="prompt-suggestions">', unsafe_allow_html=True)
    # display primary suggestion as pill and secondary as lighter pill
    col1, col2, col3 = st.columns([1,1,6])
    with col1:
        if st.button(suggs[0], key="sugg_primary"):
            st.session_state.update({"chat_input": suggs[0], "chat_input_box": suggs[0]})
            advance_suggestion_index(1)
    with col2:
        if st.button(suggs[1], key="sugg_secondary"):
            st.session_state.update({"chat_input": suggs[1], "chat_input_box": suggs[1]})
            advance_suggestion_index(1)
    with col3:
        st.markdown("<small>Tip: tapping a suggestion populates the input — suggestions automatically rotate after each send.</small>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Fixed bottom chat input ----------------------------
with st.container():
    st.markdown('<div class="fixed-chat-input">', unsafe_allow_html=True)
    # read/writable text area; key is chat_input_box to avoid overwriting chat_input while rendering
    chat_input_value = st.text_area("", value=st.session_state.get("chat_input_box",""), key="chat_input_box", placeholder="Ask or continue your sales dialogue...", height=76)
    send_col1, send_col2 = st.columns([8,1])
    with send_col2:
        if st.button("Send", key="send_button"):
            user_text = chat_input_value.strip()
            if user_text:
                # Append user message
                st.session_state.chat_history.append({"role": "user", "content": user_text})
                # Generate AI response (uses feedback guidance)
                ai_resp = generate_ai_response_user(user_text)
                audio_b64 = generate_audio_base64(ai_resp)
                st.session_state.chat_history.append({"role": "assistant", "content": ai_resp, "audio": audio_b64})
                # Advance suggestions automatically
                advance_suggestion_index(1)
                # Clear chat inputs safely
                st.session_state.update({"chat_input": "", "chat_input_box": ""})
                # Rerun to show results immediately
                st.experimental_rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Exports / References (structured) ----------------------------
with st.container():
    st.markdown("## 📚 Medical & Sales References")
    if local_ref_text or external_text:
        with st.expander("🔍 Preview Combined Medical References", expanded=False):
            preview_text = (local_ref_text + "\n" + external_text).strip()
            st.text_area("Medical Reference Preview", preview_text[:3000], height=200)
    if sales_module_text:
        with st.expander("🔍 Preview Sales Module Documents", expanded=False):
            st.text_area("Sales Module Preview", sales_module_text[:3000] + ("..." if len(sales_module_text) > 3000 else ""), height=200)

    if st.button("Export Medical References (structured)"):
        medical_refs = [
            {"title": "Sample Study A", "url": "https://example.com/studyA", "context": "Practice-changing outcomes summary"},
            {"title": "Sample Report B", "url": "https://example.com/reportB", "context": "Barriers analysis and solutions"},
        ]
        export_text = "### Medical References Export\n\n"
        export_text += f"- Brand: {brand}\n- Persona: {persona}\n- Segment: {segment}\n- Barriers: {', '.join(barrier) if barrier else 'None'}\n- Exported: {datetime.utcnow().isoformat()}\n\n"
        for ref in medical_refs:
            export_text += f"- **{ref['title']}**\n  - URL: {ref['url']}\n  - Context: {ref['context']}\n\n"
        st.download_button("Download Medical References", data=export_text, file_name="medical_references.md", mime="text/markdown")

    if st.button("Export Sales Call Module (structured)"):
        sales_module = {
            "HCP Persona": persona,
            "Key Barriers": barrier or ["None listed"],
            "Suggested Approach": ["Emphasize patient eligibility", "Highlight cost-benefit outcomes"],
            "Sample Call Flow": ["Intro -> Probe -> Objection Handling -> Commitment -> Close"]
        }
        export_text = "### Sales Call Module Export\n\n"
        export_text += f"- Brand: {brand}\n- Persona: {persona}\n- Segment: {segment}\n- Barriers: {', '.join(barrier) if barrier else 'None'}\n- Exported: {datetime.utcnow().isoformat()}\n\n"
        for key, value in sales_module.items():
            export_text += f"- **{key}**: {', '.join(value) if isinstance(value, list) else value}\n"
        st.download_button("Download Sales Call Module", data=export_text, file_name="sales_call_module.md", mime="text/markdown")

# ---------------------------- Export chat optional area ----------------------------
if st.session_state.chat_history:
    with st.expander("Export / Download Chat", expanded=False):
        text_export = "\n\n".join([f"{e['role'].capitalize()}: {e['content']}" for e in st.session_state.chat_history if isinstance(e, dict)])
        if DOCX_AVAILABLE:
            if st.button("Export as DOCX"):
                try:
                    doc = Document()
                    doc.add_heading("AI Sales Call Assistant Export", 0)
                    doc.add_paragraph(f"Brand: {brand.upper()} | Date: {datetime.now().strftime('%Y-%m-%d')}")
                    doc.add_paragraph(text_export)
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
                    doc.save(tmp.name)
                    st.download_button("⬇️ Download DOCX", open(tmp.name, "rb"), file_name=f"{brand}_chat.docx")
                except Exception as e:
                    st.error(f"Export DOCX failed: {e}")
        st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{brand}_chat.txt")

# ---------------------------- Footer disclaimer ----------------------------
st.markdown(f"""
<div class="fixed-disclaimer">
<b>Disclaimer:</b> ⚠️This AI Sales Call Assistant is intended for educational and informational purposes only. 
It does not replace official medical references, product labeling, or company-approved materials. 
Always verify with the latest approved product information and compliance guidance before use.
</div>
""", unsafe_allow_html=True)
