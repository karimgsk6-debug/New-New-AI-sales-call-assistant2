# app.py
import streamlit as st
from PIL import Image
import re, os, tempfile, base64, requests
from io import BytesIO
from datetime import datetime
from groq import Groq
from PyPDF2 import PdfReader
from html import escape
from gtts import gTTS

# ---------------------------- Config ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ---------- Repo info for linking files ----------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_BLOB_BASE = f"https://github.com/{REPO_USER}/{REPO_NAME}/blob/{COMMIT}/.devcontainer"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"

# ---------------------------- Assets (raw URLs) ----------------------------
BACKGROUND_URL = REPO_RAW_BASE + "/.devcontainer/background1.png"
GSK_LOGO_URL = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer/gsk-logo.png"
AI_LOGO_URL = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer/ai-logo.png"

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
if "main_input" not in st.session_state:
    st.session_state.main_input = ""
if "copilot_suggestions" not in st.session_state:
    st.session_state.copilot_suggestions = []

# ---------------------------- CSS / layout ----------------------------
CSS = f"""
<style>
body {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-attachment: fixed;
  background-position: center;
}}
.header {{
  background: rgba(255,255,255,0.85);
  padding: 10px;
  border-radius: 8px;
  margin-bottom: 12px;
  display:flex;
  align-items:center;
  justify-content:center;
  position:relative;
}}
.header img.left-logo {{ position:absolute; left:16px; width:130px; }}
.header img.right-logo {{ position:absolute; right:16px; width:130px; }}
.header h1 {{ margin:0; font-size:22px; }}
.chat-container {{
  max-height: 55vh;
  overflow-y:auto;
  padding:12px;
  border-radius:10px;
  background: rgba(255,255,255,0.9);
  margin-bottom: 90px;
}}
.chat-bubble-user {{ background:#0078D7; color:white; padding:12px; border-radius:10px; margin:8px 0; max-width:75%; margin-left:auto; }}
.chat-bubble-ai {{ background:#d9f0ff; color:#000; padding:12px; border-radius:10px; margin:8px 0; max-width:75%; }}
.copilot-row {{ display:flex; gap:8px; flex-wrap:wrap; margin-bottom:8px; }}
.copilot-pill {{ background:#fff; border:1px solid #ddd; padding:8px 12px; border-radius:20px; cursor:pointer; }}
.fixed-input {{ position:fixed; left:24px; right:24px; bottom:18px; z-index:9999; background:transparent; }}
.fixed-input textarea {{ width:100%; min-height:72px; max-height:180px; resize:vertical; padding:10px; border-radius:8px; border:1px solid #ccc; }}
.send-row {{ position:fixed; right:30px; bottom:20px; z-index:9999; }}
.fixed-disclaimer {{ position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:6px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; }}
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

# ---------------------------- Brands (all) ----------------------------
brand_data = {
    "shingrix": {
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix"
    },
    "jemperli": {
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited patient eligibility", "Access/reimbursement issues"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli"
    },
    "trelegy": {
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Concerns about side effects", "Cost/coverage"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy"
    }
}

specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Rheumatologist", "Internal medicine", "Oncologist", "Pulmonologist"]
objectives = ["Awareness", "Adoption", "Retention"]

# ---------------------------- Helpers: load local refs + list files for links ----------------------------
def load_local_references_and_files(folder_path):
    """Return (combined_text, list_of_filenames)"""
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

# ---------------------------- Audio (ElevenLabs / gTTS fallback) ----------------------------
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

# ---------------------------- Call flows ----------------------------
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
    "Influence": "Present evidence, handle objections...",
    "Impact GSO": "Link discussion to incremental steps...",
    "Post-Call Analysis": "Record insights..."
}
trelegy_CALL_FLOW = {
    "Prepare": "Assess inhaler technique and adherence...",
    "Engage": "Open with symptom-based questions...",
    "Demonstrate": "Discuss inhaler technique and education...",
    "Address Access": "Clarify formulary and reimbursement options...",
    "Close": "Agree on next steps..."
}

# ---------------------------- Sidebar (filters + clear + language) ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", sorted(list(brand_data.keys())), index=0)
    selected_brand = brand_data[brand]
    segment = st.selectbox("Segment", selected_brand["segments"])
    persona = st.selectbox("HCP Persona", selected_brand["personas"])
    barrier = st.multiselect("Doctor Barrier", selected_brand["barriers"])
    specialty = st.selectbox("Specialty", specialties)
    objective = st.selectbox("Objective", objectives)
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])
    response_length = st.selectbox("Response Length", ["Short", "Medium", "Long"])
    st.session_state.language = st.radio("Language", ["English", "Arabic"], horizontal=True)
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []

with st.sidebar.expander("🌐 Add External Reference URLs", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT", "DOCX"], horizontal=True)

# ---------------------------- Header ----------------------------
st.markdown(f"""
<div class="header">
  <img src="{GSK_LOGO_URL}" class="left-logo">
  <h1>💡 AI Sales Call Assistant — {brand.upper()}</h1>
  <img src="{AI_LOGO_URL}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# ---------------------------- Load local references & sales modules (and get filenames) ----------
local_refs_text, local_ref_files = load_local_references_and_files(selected_brand["references_path"])
sales_text, sales_files = load_local_references_and_files(selected_brand["sales_path"])
external_text = load_external_references([u for u in external_urls if u.strip()]) if external_urls else ""

# ---------------------------- PDF upload & summary (simple) -------------
with st.expander("📄 Upload Custom PDF for AI Context", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
    st.session_state.pdf_summary_size = st.radio("PDF Summary Size", ["Consisted", "Normal", "Detailed"], horizontal=True)
    if uploaded_pdf:
        try:
            reader = PdfReader(uploaded_pdf)
            full_text = "".join([p.extract_text() or "" for p in reader.pages])
            st.session_state.uploaded_pdf_text = full_text
            st.success(f"Loaded {len(full_text)} characters from uploaded PDF.")
            # naive summary fallback - real model summary if client available
            bullets_count = {"Consisted":5,"Normal":10,"Detailed":20}.get(st.session_state.pdf_summary_size,10)
            if client:
                try:
                    summ_prompt = f"Summarize into {bullets_count} bullet points:\n{full_text[:12000]}"
                    summ = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                                         messages=[{"role":"user","content":summ_prompt}], temperature=0.4)
                    st.session_state.pdf_summary = summ.choices[0].message.content
                except Exception:
                    # fallback trivial extraction
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
        # show assistant and sources footer if present
        content = msg.get("content","")
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(content)}</div>', unsafe_allow_html=True)
        if msg.get("audio"):
            try:
                st.audio(base64.b64decode(msg["audio"]), format="audio/mp3")
            except:
                pass
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Copilot suggestions (appear only after typing) --------------
def build_copilot_suggestions(brand, persona, barrier_list, segment, specialty, objective):
    s = []
    s.append(f"Generate call flow for {persona} focused on {objective}.")
    if barrier_list:
        s.append(f"Handle objection: {', '.join(barrier_list[:2])} for {persona}.")
    else:
        s.append(f"Identify common objections for {persona}.")
    s.append(f"Summarize HCP persona insights for {persona}.")
    s.append(f"Key talking points for {brand} in {segment}.")
    s.append(f"Draft a short adoption message for {brand} to a {specialty}.")
    return s

# controlled input area (text_area) + suggestion pills
user_text = st.text_area("Ask or continue your sales dialogue...", value=st.session_state.get("main_input",""), key="main_input", height=120)

# show suggestions only when user has typed something
if user_text and user_text.strip():
    pills = build_copilot_suggestions(brand, persona, barrier, segment, specialty, objective)
    cols = st.container()
    st.markdown('<div class="copilot-row">', unsafe_allow_html=True)
    for i, p in enumerate(pills):
        # clicking a pill sets the input via session_state
        if st.button(p, key=f"pill_{i}"):
            st.session_state["main_input"] = p
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Send (form) - safe handling ----------------------------
with st.form(key="chat_form", clear_on_submit=False):
    # use the session value in the textarea for controlled behavior
    text_val = st.text_area("Message (editable):", value=st.session_state.get("main_input",""), key="form_input_area", height=100)
    submit = st.form_submit_button("Send")
    if submit:
        text_val = text_val.strip()
        if text_val:
            # append user
            st.session_state.chat_history.append({"role":"user","content":text_val})
            # reset main_input and form field
            st.session_state.main_input = ""
            # build combined context (local + sales + external + uploaded pdf)
            combined = "\n".join([
                local_refs_text or "",
                sales_text or "",
                external_text or "",
                st.session_state.uploaded_pdf_text or ""
            ])[:15000]

            # build call flow prompt depending on brand
            call_flow_prompt = ""
            if brand.lower() == "jemperli":
                call_flow_prompt = "\n--- Jemperli Call Flow ---\n" + "\n".join([f"{k}: {v}" for k,v in jemperli_CALL_FLOW.items()])
            elif brand.lower() == "shingrix":
                call_flow_prompt = "\n--- Shingrix Call Flow ---\n" + "\n".join([f"{k}: {v}" for k,v in shingrix_CALL_FLOW.items()])
            elif brand.lower() == "trelegy":
                call_flow_prompt = "\n--- Trelegy Call Flow ---\n" + "\n".join([f"{k}: {v}" for k,v in trelegy_CALL_FLOW.items()])

            system_prompt = "You are a pharmaceutical AI assistant. Use references, sales modules and uploaded PDFs to tailor responses."
            final_prompt = f"{text_val}\n\nBrand: {brand}\nPersona: {persona}\nSegment: {segment}\nSpecialty: {specialty}\nObjective: {objective}\nBarriers: {', '.join(barrier) if barrier else 'None'}\n\n{call_flow_prompt}\n\nContext (truncated):\n{combined[:5000]}"

            # call model (safe)
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
                assistant_text = f"(Fallback) Based on local refs: {text_val}"

            # attach sources footer (top 3 files from local refs & sales modules)
            def make_links(path_list, repo_subpath):
                links = []
                for fname in path_list[:3]:
                    blob = f"{REPO_BLOB_BASE}/{repo_subpath}/{fname}"
                    links.append(f"- [{fname}]({blob})")
                return "\n".join(links) if links else ""

            refs_links = make_links(local_ref_files, "references/" + brand)
            sales_links = make_links(sales_files, "SalesModule/" + brand)
            sources_footer = "\n\n**Sources:**\n"
            if refs_links:
                sources_footer += f"\n**References:**\n{refs_links}"
            if sales_links:
                sources_footer += f"\n\n**Sales Modules:**\n{sales_links}"
            assistant_with_sources = assistant_text + sources_footer

            # generate audio (best effort)
            audio_b64 = ""
            try:
                audio_b64 = generate_audio(assistant_text)
            except:
                audio_b64 = ""

            st.session_state.chat_history.append({"role":"assistant","content":assistant_with_sources,"audio":audio_b64})

# ---------------------------- Export buttons (bottom) ----------------------------
if st.session_state.chat_history:
    with st.expander("💾 Export / Download Chat", expanded=False):
        text_export = "\n\n".join([f"{e['role'].capitalize()}: {e['content']}" for e in st.session_state.chat_history])
        if st.button("Download TXT"):
            st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{brand}_chat.txt")
        if 'python-docx' in str(st.runtime.exists()):  # just a small guard; if python-docx installed user will see option
            pass
        # Always show TXT. DOCX requires python-docx; we avoid runtime dependency check here.

# ---------------------------- Disclaimer ----------------------------
st.markdown('<div class="fixed-disclaimer">⚠️ This AI tool is for informational purposes only. Verify with approved medical references.</div>', unsafe_allow_html=True)
