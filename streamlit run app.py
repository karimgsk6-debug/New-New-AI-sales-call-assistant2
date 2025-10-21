# app.py - Final merged version with fixes and Copilot dropdown
import streamlit as st
from PIL import Image
import re, os, tempfile, base64, requests
from io import BytesIO
from datetime import datetime
from groq import Groq
from PyPDF2 import PdfReader
from html import escape
from gtts import gTTS

# Optional DOCX export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

# ---------------------------- Page config ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ---------- Repo info for linking files ----------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_BLOB_BASE = f"https://github.com/{REPO_USER}/{REPO_NAME}/blob/{COMMIT}/.devcontainer"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"

# ---------------------------- Assets (raw URLs) ----------------------------
BACKGROUND_URL = REPO_RAW_BASE + "/.devcontainer/background1.png"
# logos provided in main branch as requested
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# ---------------------------- Session defaults ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "voice_pref" not in st.session_state:
    st.session_state.voice_pref = "Old Male"
# do NOT pre-create a 'language' key that conflicts with widget key; we will read widget value into a variable
if "pdf_summary_size" not in st.session_state:
    st.session_state.pdf_summary_size = "Normal"
if "main_input" not in st.session_state:
    st.session_state.main_input = ""
# track selected brand key
if "selected_brand" not in st.session_state:
    st.session_state.selected_brand = "trelegy"

# ---------------------------- CSS / layout ----------------------------
CSS = f"""
<style>
/* Background for the whole app */
.stApp {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-attachment: fixed;
  background-position: center;
}}

/* Header */
.header {{
  background: rgba(255,255,255,0.92);
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 10px;
  display:flex;
  align-items:center;
  justify-content:center;
  position:relative;
}}
.header img.left-logo {{ position:absolute; left:16px; width:120px; height:auto; }}
.header img.right-logo {{ position:absolute; right:16px; width:120px; height:auto; }}
.header h1 {{ margin:0; font-size:20px; }}

/* Chat container */
.chat-container {{
  max-height: 56vh;
  overflow-y:auto;
  padding:12px;
  border-radius:10px;
  background: rgba(255,255,255,0.92);
  margin-bottom: 120px;
}}
.chat-bubble-user {{ background:#0078D7; color:white; padding:12px; border-radius:10px; margin:8px 0; max-width:75%; margin-left:auto; }}
.chat-bubble-ai {{ background:#d9f0ff; color:#000; padding:12px; border-radius:10px; margin:8px 0; max-width:75%; }}

/* Collapsed suggestions expander handled by Streamlit (no extra CSS needed),
   but style the visible suggestions box for uniformity */
.suggestions-inline {{ background: rgba(255,255,255,0.95); padding:8px; border-radius:8px; box-shadow:0 4px 10px rgba(0,0,0,0.06); }}
.suggestion-pill {{ background:#fff; border:1px solid #ddd; padding:8px 12px; border-radius:18px; cursor:pointer; margin:4px; display:inline-block; }}
.suggestion-pill:hover {{ background:#f2f6ff; }}

/* fixed input area */
.input-area {{ position: fixed; left:24px; right:24px; bottom:18px; z-index:9999; display:flex; gap:10px; align-items:flex-end; }}
.input-area textarea {{ width:100%; min-height:72px; max-height:200px; padding:10px; border-radius:8px; border:1px solid #ccc; resize:vertical; }}
.input-area button {{ height:44px; padding:0 16px; border-radius:8px; border:none; background:#FF6F00; color:white; cursor:pointer; }}

/* disclaimer */
.fixed-disclaimer {{ position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ client init (safe) ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = None
if GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

# ---------------------------- Brands ----------------------------
brand_data = {
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Concerns about side effects", "Cost/coverage"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy"
    },
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix"
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited patient eligibility", "Access/reimbursement issues"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli"
    }
}

specialties = ["GP", "Pulmonologist", "Internal medicine", "Oncologist"]
objectives = ["Awareness", "Adoption", "Retention"]

# ---------------------------- Helper functions ----------------------------
def load_local_references_and_files(folder_path):
    text_all = ""
    files_list = []
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return "", []
    files = [f for f in os.listdir(folder_path) if f.lower().endswith((".pdf", ".txt"))]
    for f in files:
        files_list.append(f)
        fp = os.path.join(folder_path, f)
        try:
            if f.lower().endswith(".pdf"):
                reader = PdfReader(fp)
                for p in reader.pages:
                    text_all += p.extract_text() or ""
            else:
                with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                    text_all += fh.read()
        except Exception as e:
            text_all += f"\n[Error reading {f}: {e}]"
    return text_all, files_list

def load_external_references(url_list):
    all_text = ""
    for url in url_list:
        try:
            r = requests.get(url, timeout=6)
            if r.status_code == 200:
                all_text += r.text + "\n"
        except:
            pass
    return all_text

# ElevenLabs presence
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except ModuleNotFoundError:
    ELEVENLABS_AVAILABLE = False

ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    try:
        elevenlabs.api_key = ELEVENLABS_API_KEY
    except:
        pass

def generate_audio(text):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        tts_text = re.sub(r'[,*]{1,}', '', text)
        if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
            audio_stream = elevenlabs.generate(text=tts_text, voice=ELEVENLABS_VOICE_ID, stream=True)
            with open(tmp.name, "wb") as f:
                for ch in audio_stream:
                    f.write(ch)
        else:
            tts = gTTS(text=tts_text, lang="en", slow=False)
            tts.save(tmp.name)
        with open(tmp.name, "rb") as fh:
            return base64.b64encode(fh.read()).decode()
    except Exception as e:
        st.warning(f"Audio generation failed: {e}")
        return ""

# ---------------------------- Sidebar ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    # widget keys should not conflict with manual session_state assignment
    sel_brand_key = st.selectbox("Brand", sorted(list(brand_data.keys())), index=list(sorted(brand_data.keys())).index(st.session_state.get("selected_brand","trelegy")))
    st.session_state.selected_brand = sel_brand_key
    sel_brand = brand_data[sel_brand_key]
    segment = st.selectbox("Segment", sel_brand["segments"], key="segment")
    persona = st.selectbox("HCP Persona", sel_brand["personas"], key="persona")
    barrier = st.multiselect("Doctor Barrier", sel_brand["barriers"], key="barrier")
    specialty = st.selectbox("Specialty", specialties, key="specialty")
    objective = st.selectbox("Objective", objectives, key="objective")
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"], key="response_tone")
    response_length = st.selectbox("Response Length", ["Short", "Medium", "Long"], key="response_length")
    # language radio: capture into a variable (don't set st.session_state['language'] directly)
    selected_language = st.radio("Language", ["English", "Arabic"], horizontal=True, key="widget_language")
    # persist only as variable if needed; do not assign to same key that widget used.
    # Move clear chat into sidebar
    if st.button("🗑️ Clear Chat", key="clear_chat"):
        st.session_state.chat_history = []

with st.sidebar.expander("🌐 Add External Reference URLs", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT", "DOCX"], horizontal=True)

# ---------------------------- Header ----------------------------
st.markdown(f"""
<div class="header">
  <img src="{GSK_LOGO_RAW}" class="left-logo">
  <h1>💡 AI Sales Call Assistant — {brand_data[st.session_state.selected_brand]['display']}</h1>
  <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# ---------------------------- Load local refs & sales module text & file list ----------
local_refs_text, local_ref_files = load_local_references_and_files(brand_data[st.session_state.selected_brand]["references_path"])
sales_text, sales_files = load_local_references_and_files(brand_data[st.session_state.selected_brand]["sales_path"])
external_text = load_external_references([u for u in external_urls if u.strip()]) if 'external_urls' in locals() else ""

# ---------------------------- PDF upload & summary -------------
with st.expander("📄 Upload Custom PDF for AI Context", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
    st.session_state.pdf_summary_size = st.radio("PDF Summary Size", ["Consisted", "Normal", "Detailed"], horizontal=True, key="pdf_size_widget")
    if uploaded_pdf:
        try:
            reader = PdfReader(uploaded_pdf)
            full_text = "".join([p.extract_text() or "" for p in reader.pages])
            st.session_state.uploaded_pdf_text = full_text
            st.success(f"Loaded {len(full_text)} characters from uploaded PDF.")
            bullets_count = {"Consisted":5,"Normal":10,"Detailed":20}.get(st.session_state.pdf_summary_size,10)
            if client:
                try:
                    summ_prompt = f"Summarize into {bullets_count} bullet points:\n{full_text[:12000]}"
                    summ = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                                         messages=[{"role":"user","content":summ_prompt}], temperature=0.4)
                    st.session_state.pdf_summary = summ.choices[0].message.content
                except Exception:
                    sts = re.findall(r'([A-Z][^.]{20,200})', full_text)
                    st.session_state.pdf_summary = "\n".join(sts[:bullets_count])
            else:
                sts = re.findall(r'([A-Z][^.]{20,200})', full_text)
                st.session_state.pdf_summary = "\n".join(sts[:bullets_count])
        except Exception as e:
            st.error(f"Error reading uploaded PDF: {e}")
    if st.session_state.pdf_summary:
        st.markdown(f"<div style='background:#E6F0FF;padding:10px;border-radius:8px;white-space:pre-line'>{escape(st.session_state.pdf_summary)}</div>", unsafe_allow_html=True)

# ---------------------------- Chat container (history) ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for msg in st.session_state.chat_history:
    if msg.get("role") == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)
        if msg.get("audio"):
            try:
                st.audio(base64.b64decode(msg["audio"]), format="audio/mp3")
            except:
                pass
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Copilot suggestions (collapsed expander above chat input) ------------
def build_suggestions_for_brand(brand_key, persona, barrier_list, segment, specialty, objective):
    s = []
    s.append(f"Generate call flow for {persona} focused on {objective}.")
    if barrier_list:
        s.append(f"Handle objection: {', '.join(barrier_list[:2])} for {persona}.")
    else:
        s.append(f"Identify common objections for {persona}.")
    s.append(f"Summarize HCP persona insights for {persona}.")
    s.append(f"Key talking points for {brand_data[brand_key]['display']} in {segment}.")
    s.append(f"Draft a short adoption message for {brand_data[brand_key]['display']} to a {specialty}.")
    return s

with st.expander("Copilot Suggestions (click to autofill)", expanded=False):
    suggestions = build_suggestions_for_brand(st.session_state.selected_brand, persona, barrier, segment, specialty, objective)
    st.markdown('<div class="suggestions-inline">', unsafe_allow_html=True)
    cols = st.columns([1]*3)
    # render pills as streamlit buttons grouped
    for i, s in enumerate(suggestions):
        # Use button; clicking sets session_state.main_input safely and reruns
        if cols[i % 3].button(s, key=f"sugg_{i}"):
            st.session_state.main_input = s
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Chat input form (editable) ----------------------------
with st.form(key="chat_form", clear_on_submit=False):
    # Use st.session_state['main_input'] as the controlled default
    text_val = st.text_area("Message (editable)", value=st.session_state.get("main_input",""), key="chat_input_area", height=120)
    submit = st.form_submit_button("Send")
    if submit:
        user_text = text_val.strip()
        if user_text:
            # append user
            st.session_state.chat_history.append({"role":"user","content":user_text})
            # clear main_input (safe - not a widget key)
            st.session_state.main_input = ""

            # Build combined context text
            combined_context = "\n".join([
                local_refs_text or "",
                sales_text or "",
                external_text or "",
                st.session_state.uploaded_pdf_text or ""
            ])[:15000]

            # Call flow per brand
            call_flow_prompt = ""
            if st.session_state.selected_brand.lower() == "jemperli":
                call_flow_prompt = "\n".join([f"{k}: {v}" for k, v in jemperli_CALL_FLOW.items()])
            elif st.session_state.selected_brand.lower() == "shingrix":
                call_flow_prompt = "\n".join([f"{k}: {v}" for k, v in shingrix_CALL_FLOW.items()])
            elif st.session_state.selected_brand.lower() == "trelegy":
                call_flow_prompt = "\n".join([f"{k}: {v}" for k, v in trelegy_CALL_FLOW.items()])

            system_prompt = "You are a pharmaceutical AI assistant. Use references, sales modules and uploaded PDFs to tailor responses."
            final_prompt = f"{user_text}\n\nBrand: {st.session_state.selected_brand}\nPersona: {persona}\nSegment: {segment}\nSpecialty: {specialty}\nObjective: {objective}\nBarriers: {', '.join(barrier) if barrier else 'None'}\n\n{call_flow_prompt}\n\nContext (truncated):\n{combined_context[:5000]}"

            # generate AI response (safe)
            if client:
                try:
                    resp = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role":"system","content":system_prompt},
                                  {"role":"user","content":final_prompt}],
                        temperature=0.6
                    )
                    assistant_text = resp.choices[0].message.content
                except Exception as e:
                    assistant_text = f"(AI Error) {e}"
            else:
                assistant_text = f"(Fallback) Based on local refs: {user_text}"

            # Build sources footer with links to top 3 files
            def make_links(files_list, repo_subpath):
                out = []
                for fname in files_list[:3]:
                    blob = f"{REPO_BLOB_BASE}/{repo_subpath}/{fname}"
                    out.append(f"- [{fname}]({blob})")
                return "\n".join(out) if out else ""

            refs_links = make_links(local_ref_files, f"references/{st.session_state.selected_brand}")
            sales_links = make_links(sales_files, f"SalesModule/{st.session_state.selected_brand}")
            sources_footer = "\n\n**Sources:**\n"
            if refs_links:
                sources_footer += f"\n**References:**\n{refs_links}"
            if sales_links:
                sources_footer += f"\n\n**Sales Modules:**\n{sales_links}"
            assistant_with_sources = assistant_text + sources_footer

            # generate audio (best-effort)
            audio_b64 = ""
            try:
                audio_b64 = generate_audio(assistant_text)
            except:
                audio_b64 = ""

            st.session_state.chat_history.append({"role":"assistant","content":assistant_with_sources,"audio":audio_b64})

# ---------------------------- Export / Download Chat ----------
if st.session_state.chat_history:
    with st.expander("💾 Export / Download Chat", expanded=False):
        text_export = "\n\n".join([f"{e['role'].capitalize()}: {e['content']}" for e in st.session_state.chat_history])
        st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{st.session_state.selected_brand}_chat.txt")
        if DOCX_AVAILABLE:
            if st.button("Export as DOCX"):
                try:
                    doc = Document()
                    doc.add_heading("AI Sales Call Assistant Export", 0)
                    doc.add_paragraph(f"Brand: {st.session_state.selected_brand.upper()} | Date: {datetime.now().strftime('%Y-%m-%d')}")
                    for e in st.session_state.chat_history:
                        doc.add_paragraph(f"{e['role'].capitalize()}: {e['content']}")
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
                    doc.save(tmp.name)
                    with open(tmp.name, "rb") as fh:
                        st.download_button("⬇️ Download DOCX", fh.read(), file_name=f"{st.session_state.selected_brand}_chat.docx")
                except Exception as e:
                    st.error(f"Could not export DOCX: {e}")

# ---------------------------- Call flows (kept) ----------------------------
jemperli_CALL_FLOW = {
    "COCO": "Pre-call planning using customer insights...",
    "Anchor": "Open conversation with a patient-focused narrative...",
    "Engage": "Draw customer in through two-way dialogue...",
    "Close": "Gain agreement, define next steps..."
}
shingrix_CALL_FLOW = {
    "Prepare": "Plan the call: identify persona, objectives...",
    "Engage": "Start conversation, capture attention...",
    "Create Opportunities": "Identify gaps or unmet needs...",
    "Influence": "Present evidence, handle objections..."
}
trelegy_CALL_FLOW = {
    "Prepare": "Assess inhaler technique and adherence...",
    "Engage": "Open with symptom-based questions...",
    "Demonstrate": "Discuss inhaler technique and education...",
    "Address Access": "Clarify formulary and reimbursement options...",
    "Close": "Agree on next steps..."
}

# ---------------------------- Disclaimer ----------------------------
st.markdown('<div class="fixed-disclaimer">⚠️ This AI tool provides informational guidance only. Verify all medical content with approved references before use.</div>', unsafe_allow_html=True)
