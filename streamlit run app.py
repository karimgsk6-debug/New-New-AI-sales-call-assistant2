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
# Background (from commit), logos from main branch raw URLs provided by user
BACKGROUND_URL = REPO_RAW_BASE + "/.devcontainer/background1.png"
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
if "language" not in st.session_state:
    st.session_state.language = "English"
if "pdf_summary_size" not in st.session_state:
    st.session_state.pdf_summary_size = "Normal"
if "main_input" not in st.session_state:
    st.session_state.main_input = ""
if "selected_brand" not in st.session_state:
    st.session_state.selected_brand = "trelegy"

# ---------------------------- CSS / layout ----------------------------
CSS = f"""
<style>
/* Background */
.stApp {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-attachment: fixed;
  background-position: center;
}}

/* Header */
.header {{
  background: rgba(255,255,255,0.9);
  padding: 12px;
  border-radius: 8px;
  margin-bottom: 10px;
  display:flex;
  align-items:center;
  justify-content:center;
  position:relative;
}}
.header img.left-logo {{ position:absolute; left:18px; width:120px; height:auto; }}
.header img.right-logo {{ position:absolute; right:18px; width:120px; height:auto; }}
.header h1 {{ margin:0; font-size:20px; }}

/* Chat */
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

/* Suggestions dropdown (always visible block above chat input) */
.suggestions-box {{
  position: fixed;
  left: 24px;
  right: 24px;
  bottom: 110px; /* above the input area */
  z-index: 9998;
  background: rgba(255,255,255,0.95);
  padding: 8px;
  border-radius: 8px;
  box-shadow: 0 4px 10px rgba(0,0,0,0.08);
  max-width: calc(100% - 48px);
}}
.suggestion-section-title {{ font-weight:700; margin:0 0 6px 0; }}
.suggestion-list {{ display:flex; gap:8px; flex-wrap:wrap; }}
.suggestion-pill {{
  background:#fff;
  border:1px solid #ddd;
  padding:8px 12px;
  border-radius:18px;
  cursor:pointer;
  display:inline-block;
}}
.suggestion-pill:hover {{ background:#f2f6ff; box-shadow:0 2px 6px rgba(0,0,0,0.06); }}

/* Input area fixed at bottom */
.input-area {{
  position: fixed;
  left:24px;
  right:24px;
  bottom:18px;
  z-index:9999;
  display:flex;
  gap:10px;
  align-items:flex-end;
}}
.input-area textarea {{
  width:100%;
  min-height:72px;
  max-height:200px;
  padding:10px;
  border-radius:8px;
  border:1px solid #ccc;
  resize:vertical;
}}
.input-area button {{
  height:44px;
  padding:0 16px;
  border-radius:8px;
  border:none;
  background:#FF6F00;
  color:white;
  cursor:pointer;
}}
.tooltip {{ font-size:12px; color:#555; }}
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

# Audio support
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
    sel_brand_key = st.selectbox("Brand", sorted(list(brand_data.keys())), index=sorted(list(brand_data.keys())).index(st.session_state.get("selected_brand","trelegy")))
    st.session_state.selected_brand = sel_brand_key
    sel_brand = brand_data[sel_brand_key]
    segment = st.selectbox("Segment", sel_brand["segments"], key="segment")
    persona = st.selectbox("HCP Persona", sel_brand["personas"], key="persona")
    barrier = st.multiselect("Doctor Barrier", sel_brand["barriers"], key="barrier")
    specialty = st.selectbox("Specialty", specialties, key="specialty")
    objective = st.selectbox("Objective", objectives, key="objective")
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"], key="response_tone")
    response_length = st.selectbox("Response Length", ["Short", "Medium", "Long"], key="response_length")
    st.session_state.language = st.radio("Language", ["English", "Arabic"], horizontal=True, key="language")
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

# ---------------------------- Load references + sales module content ----------
local_refs_text, local_ref_files = load_local_references_and_files(brand_data[st.session_state.selected_brand]["references_path"])
sales_text, sales_files = load_local_references_and_files(brand_data[st.session_state.selected_brand]["sales_path"])
external_text = load_external_references([u for u in external_urls if u.strip()]) if 'external_urls' in locals() else ""

# ---------------------------- PDF upload & summary -------------
with st.expander("📄 Upload Custom PDF for AI Context", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
    st.session_state.pdf_summary_size = st.radio("PDF Summary Size", ["Consisted", "Normal", "Detailed"], horizontal=True)
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

# ---------------------------- Copilot suggestions (always visible dropdown block) ------------
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

# Always-visible suggestions block above the input
suggestions = build_suggestions_for_brand(st.session_state.selected_brand, persona, barrier, segment, specialty, objective)
suggestions_html = '<div class="suggestions-box">'
suggestions_html += '<div class="suggestion-section-title">Copilot Suggestions (click to autofill)</div>'
suggestions_html += '<div class="suggestion-list">'
for i, s in enumerate(suggestions):
    # include tooltip via title attribute
    title = "Click to autofill the chat box with this suggestion (you can edit before sending)"
    # create a form button per suggestion so clicking sets session_state safely
    suggestions_html += f'<form method="post"><button name="fill" value="{i}" class="suggestion-pill" title="{title}">{escape(s)}</button></form>'
suggestions_html += '</div></div>'
# Render suggestions HTML (we will intercept POST via query params below)
st.markdown(suggestions_html, unsafe_allow_html=True)

# ---------------------------- Handle suggestion POST (autofill) ----------------------------
# Streamlit cannot directly read form POSTs from raw HTML; use st.experimental_get_query_params workaround:
# When a suggestion form posts, the browser will add ?fill=<index> to URL if we implement using link; however HTML form POST from markdown won't modify URL.
# Alternative safe approach: render suggestion as st.button widgets instead, which is simpler and reliable.
# We'll show a hidden container of buttons below (but visually same) to capture clicks reliably.

st.write("")  # spacer
cols_placeholder = st.container()
with cols_placeholder:
    st.markdown('<div style="display:none">', unsafe_allow_html=True)  # hide the redundant button row visually (we use CSS above)
    for i, s in enumerate(suggestions):
        if st.button(f"__suggest_capture__{i}", key=f"sugg_btn_{i}"):
            # set the main input to the suggestion (autofill) and focus (user can edit)
            st.session_state.main_input = s
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Input area (fixed) ----------------------------
# Use a text_area and a Send button. Buttons set session_state on click and cause a rerun so the text_area will reflect updated value.
input_col = st.empty()
with input_col:
    st.markdown(f"""
    <div class="input-area">
      <textarea id="main_textarea" placeholder="Type your question or continue your sales dialogue..." rows="4">{escape(st.session_state.get('main_input',''))}</textarea>
      <button id="send_button">Send</button>
    </div>
    <script>
    // Wire the Send button to set the 'main_input' via Streamlit URL param and force a reload
    const sendBtn = window.parent.document.getElementById('send_button');
    const ta = window.parent.document.getElementById('main_textarea');
    if(sendBtn && ta) {{
      sendBtn.onclick = () => {{
        const val = ta.value;
        // set a query param to pass the text back to Streamlit
        const url = new URL(window.location.href);
        url.searchParams.set('chat_text', val);
        window.location.href = url.toString();
      }};
    }}
    // Also, when user focuses the textarea and types, sync value to sessionStorage so we can rehydrate after reload
    if(ta) {{
      ta.addEventListener('input', () => {{
        try {{ sessionStorage.setItem('pending_chat', ta.value); }} catch(e){{}}
      }});
    }}
    // On load, rehydrate from sessionStorage if present
    try {{
      const pending = sessionStorage.getItem('pending_chat');
      if(pending && (!ta.value || ta.value.trim()==="")) ta.value = pending;
    }} catch(e){{}}
    </script>
    """, unsafe_allow_html=True)

# ---------------------------- Handle chat_text from URL param (Send action) ----------------------------
query_params = st.experimental_get_query_params()
if "chat_text" in query_params:
    user_text = query_params["chat_text"][0]
    user_text = user_text.strip()
    # clear the param by rerouting without it (to avoid duplications)
    if user_text:
        # append user message
        st.session_state.chat_history.append({"role":"user","content":user_text})
        # clear pending store (so textarea clears)
        try:
            # cannot access browser sessionStorage from python; but we clear our server-side main_input
            st.session_state.main_input = ""
        except:
            pass

        # Build combined context
        combined_context = "\n".join([
            local_refs_text or "",
            sales_text or "",
            external_text or "",
            st.session_state.uploaded_pdf_text or ""
        ])[:15000]

        # call flow depending on brand
        call_flow_prompt = ""
        if st.session_state.selected_brand.lower() == "jemperli":
            call_flow_prompt = "\n".join([f"{k}: {v}" for k,v in jemperli_CALL_FLOW.items()])
        elif st.session_state.selected_brand.lower() == "shingrix":
            call_flow_prompt = "\n".join([f"{k}: {v}" for k,v in shingrix_CALL_FLOW.items()])
        elif st.session_state.selected_brand.lower() == "trelegy":
            call_flow_prompt = "\n".join([f"{k}: {v}" for k,v in trelegy_CALL_FLOW.items()])

        system_prompt = "You are a pharmaceutical AI assistant. Tailor responses using references, sales modules, and uploaded PDFs."
        final_prompt = f"{user_text}\n\nBrand: {st.session_state.selected_brand}\nPersona: {persona}\nSegment: {segment}\nSpecialty: {specialty}\nObjective: {objective}\nBarriers: {', '.join(barrier) if barrier else 'None'}\n\n{call_flow_prompt}\n\nContext (truncated):\n{combined_context[:5000]}"

        # generate AI response (safe)
        assistant_text = ""
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

        # create sources footer (top 3 files)
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

        # generate audio
        audio_b64 = ""
        try:
            audio_b64 = generate_audio(assistant_text)
        except:
            audio_b64 = ""

        st.session_state.chat_history.append({"role":"assistant","content":assistant_with_sources,"audio":audio_b64})

        # Remove chat_text param by rerouting (so it doesn't resend on refresh)
        st.experimental_set_query_params()

# ---------------------------- Export buttons (bottom) ----------------------------
if st.session_state.chat_history:
    with st.expander("💾 Export / Download Chat", expanded=False):
        text_export = "\n\n".join([f"{e['role'].capitalize()}: {e['content']}" for e in st.session_state.chat_history])
        st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{st.session_state.selected_brand}_chat.txt")

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
st.markdown('<div class="fixed-disclaimer">⚠️ This AI tool is for informational purposes only. Verify with approved medical references and company guidance.</div>', unsafe_allow_html=True)
