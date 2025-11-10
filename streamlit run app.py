# app.py - AI Sales Call Assistant (Final: right-anchored shifting background + fixed input)
import streamlit as st
import os, re, tempfile, base64, io, json, sys
from datetime import datetime
from html import escape

# Optional libs (best-effort)
try:
    from groq import Groq
except:
    Groq = None

try:
    from PyPDF2 import PdfReader
except:
    PdfReader = None

try:
    from gtts import gTTS
except:
    gTTS = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except:
    SKLEARN_AVAILABLE = False

try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except:
    ELEVENLABS_AVAILABLE = False

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# Asset paths (local) - your provided background
# -------------------------
BACKGROUND_LOCAL_PATH = ".devcontainer/Visuals/MR mentor final1.png"
GSK_LOGO_LOCAL = ".devcontainer/GSK1-logo.png"
AI_LOGO_LOCAL = ".devcontainer/AURA1.png"

# -------------------------
# Helper: encode image to base64 if available
# -------------------------
def encode_image_to_base64(path):
    try:
        if os.path.exists(path):
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode()
    except Exception:
        pass
    return None

BG_BASE64 = encode_image_to_base64(BACKGROUND_LOCAL_PATH)
GSK_BASE64 = encode_image_to_base64(GSK_LOGO_LOCAL)
AI_BASE64 = encode_image_to_base64(AI_LOGO_LOCAL)

# -------------------------
# CSS: right-anchored background (shift-only on sidebar changes) + fixed input area
# -------------------------
# Shift-only behavior: when sidebar expanded, move bg-left by sidebar width; brightness/size unchanged.
BG_CSS = ""
if BG_BASE64:
    BG_CSS = f"background-image: url('data:image/png;base64,{BG_BASE64}');"
else:
    # fallback to no background-image
    BG_CSS = ""

CSS = f"""
<style>
/* App base + bubble styles */
[data-testid="stAppViewContainer"] {{
  background: linear-gradient(120deg, #fff7f0 0%, #fffefc 40%);
}}
.title-box {{
  background: rgba(255,255,255,0.88);
  padding: 10px;
  border-radius: 10px;
  display:flex;
  align-items:center;
  justify-content:center;
  position:relative;
  margin-bottom:10px;
  z-index: 10;
}}
.title-box img.left-logo {{ position:absolute; left:10px; height:56px; }}
.title-box img.right-logo {{ position:absolute; right:10px; height:56px; }}
.chat-bubble-user {{ background:#0078D7; color:white; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }}
.chat-bubble-ai {{ background:#eef9ff; color:#000; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }}
.citation-box {{ background:#fbfbff; border-left:4px solid #0078D7; padding:8px; margin-top:8px; border-radius:6px; font-size:13px; white-space:pre-wrap; }}

/* Right anchored background container (shift-only) */
#bg-right {{
  position: fixed;
  top: 80px;
  bottom: 0;
  right: 0px; /* will be shifted via JS when sidebar opens */
  width: 36vw;
  max-width: 760px;
  min-width: 240px;
  {BG_CSS}
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center right;
  pointer-events: none;
  z-index: 1;
  transition: right 220ms ease;
}}
@media (max-width: 1000px) {{
  #bg-right {{ display:none; }}
}}

/* Fixed input / prompt suggestion area at bottom */
#fixed-input {{
  position: fixed;
  left: 240px; /* leave room for sidebar - JS will update if needed */
  right: 20px;
  bottom: 18px;
  z-index: 9999;
  display:flex;
  gap:8px;
  align-items:flex-end;
  background: rgba(255,255,255,0.92);
  padding: 10px;
  border-radius: 10px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.06);
}}
#fixed-input textarea {{
  width: 100%;
  min-height:72px;
  max-height:220px;
  padding:10px;
  border-radius:8px;
  border:1px solid #ddd;
  resize: vertical;
  font-size: 14px;
}}
.send-button {{
  height:44px;
  padding:0 14px;
  border-radius:8px;
  border:none;
  background:#FF6F00;
  color:white;
  cursor:pointer;
  font-weight:600;
}}
.suggestion-pill {{
  background:#fff;
  border:1px solid #ddd;
  padding:8px 12px;
  border-radius:20px;
  margin:6px;
  cursor:pointer;
  display:inline-block;
}}
.suggestion-pill:hover {{ background:#f0f8ff; }}

.fixed-disclaimer {{
  position:fixed; bottom:0; left:0; right:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997;
}}
</style>

<!-- bg container -->
<div id="bg-right"></div>

<script>
(function() {{
  // Find sidebar and app container - best-effort selectors for Streamlit DOM
  function querySidebar() {{
    return document.querySelector('[data-testid="stSidebar"]') ||
           document.querySelector('section[aria-label="Sidebar"]') ||
           document.querySelector('.css-1d391kg');
  }}

  function updateBgPosition() {{
    const bg = document.getElementById('bg-right');
    const sidebar = querySidebar();
    if (!bg) return;
    if (sidebar) {{
      const rect = sidebar.getBoundingClientRect();
      // shift the background left by sidebar width (shift-only)
      const newRight = window.innerWidth - rect.left;
      // clamp so it doesn't go off-screen
      bg.style.right = (newRight > 0 ? newRight : 0) + 'px';
      // ensure fixed-input left aligns after sidebar
      const fixedInput = document.getElementById('fixed-input');
      if (fixedInput) {{
        fixedInput.style.left = (rect.right + 14) + 'px';
      }}
    }} else {{
      bg.style.right = '0px';
      const fixedInput = document.getElementById('fixed-input');
      if (fixedInput) {{
        fixedInput.style.left = '20px';
      }}
    }}
  }}

  setTimeout(updateBgPosition, 400);
  const observer = new MutationObserver(function() {{ updateBgPosition(); }});
  observer.observe(document.body, {{ attributes: true, childList: true, subtree: true }});
  window.addEventListener('resize', updateBgPosition);
}})();
</script>
"""

st.markdown(CSS, unsafe_allow_html=True)

# -------------------------
# Safe placeholder for GROQ (model) client
# -------------------------
GROQ_API_KEY = "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"
client = None
if Groq and GROQ_API_KEY and GROQ_API_KEY != "add_your_GROQ_API_here":
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

# -------------------------
# Session defaults
# -------------------------
defaults = {
    "chat_history": [],  # elements: {"role":"user"/"assistant","content":str,"meta":{}}
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.9,
    "search_mode": "deep",
    "medical_summary": "",
    "sales_summary": "",
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "feedback": {},
    "language": "English",
    # dislike multi-turn flow: None or dict(stage:int, target_idx:int, reason:str, refinement_choice:str)
    "dislike_flow": None,
}
for k,v in defaults.items():
    st.session_state.setdefault(k, v)

# -------------------------
# Brand config (unchanged)
# -------------------------
brand_data = {
    "shingrix": {
        "display":"Shingrix",
        "segments":["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas":["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers":["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
        "specialties":["GP","Dermatologist","Geriatrician"],
        "references_path":".devcontainer/references/shingrix/",
        "sales_path":".devcontainer/SalesModule/shingrix/",
        "call_flow":["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Post-call Analysis"]
    },
    "jemperli": {
        "display":"Jemperli",
        "segments":["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas":["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers":["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties":["Oncologist","Medical Oncologist"],
        "references_path":".devcontainer/references/jemperli/",
        "sales_path":".devcontainer/SalesModule/jemperli/",
        "call_flow":["COCO","Anchor","Engage","Close"]
    },
    "trelegy": {
        "display":"Trelegy",
        "segments":["Awareness","Diagnosis","Adoption","Adherence"],
        "personas":["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers":["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties":["GP","Pulmonologist","Respiratory Specialist"],
        "references_path":".devcontainer/references/trelegy/",
        "sales_path":".devcontainer/SalesModule/trelegy/",
        "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"]
    }
}

# -------------------------
# Utility functions (summarize, audio, local search)
# -------------------------
def read_file_text(path):
    if not os.path.exists(path): return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()
    except Exception:
        return ""

def simple_summary(text, bullets=6):
    if not text: return ""
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- " + s for s in selected])

def model_summarize(text, bullets=6):
    if not text: return ""
    if client:
        try:
            prompt = f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt}],
                temperature=0.2)
            return resp.choices[0].message.content
        except Exception:
            return simple_summary(text, bullets)
    else:
        return simple_summary(text, bullets)

def generate_audio(text):
    if not text: return ""
    if ELEVENLABS_AVAILABLE:
        try:
            elevenlabs.api_key = st.secrets.get("ELEVENLABS_API_KEY", "ELEVENLABS_API_KEY_HERE")
            audio_stream = elevenlabs.generate(text=text, voice="alloy", model="eleven_multilingual_v1", stream=True)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            with open(tmp.name, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
            with open(tmp.name, "rb") as fh:
                return base64.b64encode(fh.read()).decode()
        except Exception:
            pass
    if gTTS:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            gTTS(text=text, lang="en", slow=False).save(tmp.name)
            with open(tmp.name, "rb") as fh:
                return base64.b64encode(fh.read()).decode()
        except Exception:
            pass
    return ""

def ai_generate(prompt, temperature=None):
    temp = st.session_state.temperature if temperature is None else temperature
    if client:
        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt}],
                temperature=float(temp)
            )
            return resp.choices[0].message.content
        except Exception as e:
            return "⚠️ Model error or unavailable: " + str(e)
    else:
        # offline fallback
        short = prompt[:700] + ("..." if len(prompt) > 700 else "")
        return ("⚙️ Offline mode: model not connected. "
                "Simulated concise response based on prompt start:\n\n" + short)

# Local search utilities
def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas = [], []
    for folder in folders:
        if not folder or not os.path.exists(folder): continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf",".txt"))]
        for fname in files:
            p = os.path.join(folder, fname)
            text = read_file_text(p)
            if not text: continue
            sents = re.split(r'(?<=[\.\?\!])\s+', text)
            for i in range(0, max(1, len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename": fname, "folder": folder, "start": i})
    return chunks, metas

def local_search_snippets(query, chunks, metas, top_n=3):
    if not chunks: return []
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks + [query])
            chunk_vecs = vectorizer.transform(chunks)
            q_vec = vectorizer.transform([query])
            sims = linear_kernel(q_vec, chunk_vecs).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            results = []
            for idx in top_idxs:
                if sims[idx] <= 0: continue
                results.append({"score": float(sims[idx]), "text": chunks[idx], "meta": metas[idx]})
            return results
        except Exception:
            pass
    q = query.lower()
    out = []
    for i, c in enumerate(chunks):
        if q in c.lower():
            out.append({"score": 1.0, "text": c, "meta": metas[i]})
            if len(out) >= top_n: break
    return out

# -------------------------
# Sidebar controls
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]
    segment = st.selectbox("Segment", bconf["segments"])
    persona = st.selectbox("HCP Persona", bconf["personas"])
    barrier = st.multiselect("Doctor Barrier", bconf["barriers"])
    specialty = st.selectbox("Specialty", bconf["specialties"])
    objective = st.selectbox("Objective", ["Awareness", "Adoption", "Retention"])
    st.session_state.temperature = st.slider("Temperature", 0.0, 1.0, st.session_state.temperature, 0.05)
    st.session_state.search_mode = st.selectbox("Search mode", ["deep", "shallow"])
    st.session_state.language = st.radio("Language", ["English", "Arabic"])
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []
        st.session_state.feedback = {}
        st.session_state.dislike_flow = None
        # rerun to refresh UI positions
        st.rerun()

with st.sidebar.expander("🌐 Add External Reference URLs (one per line)", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT", "DOCX"], horizontal=True)

# -------------------------
# Title box (use embedded logos if available)
# -------------------------
left_logo_html = f'<img src="data:image/png;base64,{GSK_BASE64}" class="left-logo">' if GSK_BASE64 else ''
right_logo_html = f'<img src="data:image/png;base64,{AI_BASE64}" class="right-logo">' if AI_BASE64 else ''

st.markdown(f"""
<div class="title-box">
{left_logo_html}
<h2>💡 AI Sales Call Assistant — {brand_data[st.session_state.selected_brand]['display']}</h2>
{right_logo_html}
</div>
""", unsafe_allow_html=True)

# -------------------------
# Load and summarize local references
# -------------------------
refs_folder = bconf["references_path"]
sales_folder = bconf["sales_path"]
combined_refs = ""
if os.path.exists(refs_folder):
    for f in sorted(os.listdir(refs_folder)):
        if f.lower().endswith((".pdf", ".txt")):
            combined_refs += read_file_text(os.path.join(refs_folder, f)) + "\n"
combined_sales = ""
if os.path.exists(sales_folder):
    for f in sorted(os.listdir(sales_folder)):
        if f.lower().endswith((".pdf", ".txt")):
            combined_sales += read_file_text(os.path.join(sales_folder, f)) + "\n"

if not st.session_state.medical_summary and combined_refs.strip():
    st.session_state.medical_summary = model_summarize(combined_refs, bullets=6)
if not st.session_state.sales_summary and combined_sales.strip():
    st.session_state.sales_summary = model_summarize(combined_sales, bullets=6)

with st.expander("📚 Medical References Summary", expanded=False):
    st.markdown(st.session_state.medical_summary or "No medical summary available.")
with st.expander("💼 Sales Module Summary", expanded=False):
    st.markdown(st.session_state.sales_summary or "No sales summary available.")

# -------------------------
# PDF Upload & summarization (main view)
# -------------------------
uploaded_file = st.file_uploader("📄 Upload PDF for summary (optional)", type=["pdf"])
if uploaded_file and PdfReader:
    try:
        reader = PdfReader(uploaded_file)
        pdf_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = pdf_text
        st.session_state.pdf_summary = model_summarize(pdf_text, bullets=6)
        st.success("PDF summarized successfully!")
    except Exception:
        st.error("Could not extract PDF text. Make sure the PDF is text-based.")
if st.session_state.pdf_summary:
    with st.expander("📄 Uploaded PDF Summary", expanded=False):
        st.markdown(st.session_state.pdf_summary)

# -------------------------
# Build corpus for local search
# -------------------------
corpus_folders = [refs_folder, sales_folder]
chunks, chunk_meta = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# Prompt suggestions helper
# -------------------------
def make_suggestions(brand_key, persona_val, barriers_list, segment_val, specialty_val, objective_val):
    s = []
    s.append(f"Generate call flow for {persona_val} focused on {objective_val}.")
    if barriers_list:
        s.append(f"Handle objection: {', '.join(barriers_list[:2])} for {persona_val}.")
    else:
        s.append(f"Identify common objections for {persona_val}.")
    s.append(f"Summarize HCP persona insights for {persona_val}.")
    s.append(f"Key talking points for {brand_data[brand_key]['display']} in {segment_val}.")
    s.append(f"Draft a short adoption message for {brand_data[brand_key]['display']} to a {specialty_val}.")
    return s

# -------------------------
# Core chat / APACT helper
# -------------------------
def build_apact_response(prompt, include_snippets=True):
    snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=4) if include_snippets else []
    citation = "\n".join([f"{s['meta']['filename']} ({s['score']:.2f})" for s in snippets]) if snippets else ""
    response_lines = []
    response_lines.append("**Acknowledge:** Thank you — I understand the request.")
    response_lines.append("**Probing:** Could you confirm if you'd like a high-level summary or step-by-step guidance?")
    response_lines.append("**Actions:** Based on available sales modules and references, suggested steps:")
    for step in bconf["call_flow"]:
        step_snips = [s['text'] for s in snippets if step.lower() in s['text'].lower()]
        if step_snips:
            response_lines.append(f"**{step}:**")
            for sn in step_snips:
                response_lines.append(f"- {sn}")
        else:
            response_lines.append(f"**{step}:** - Refer to the sales module for details.")
    response_lines.append("**Confirm:** Does this address the objective? If not, click Dislike and tell me what's off.")
    response_lines.append("\n*Tailored using sales modules & available references.*")
    ai_text = "\n".join(response_lines)
    meta = {"citation": citation} if citation else {}
    st.session_state.chat_history.append({"role":"assistant","content":ai_text,"meta":meta})

# -------------------------
# Fixed bottom input & prompt suggestions (rendered via HTML container)
# We'll render the input UI in the fixed container and handle its actions via the streamlit form below.
# -------------------------
# Show prompt suggestions pinned above the input area (rendered within main area too)
with st.expander("💡 Prompt Suggestions (click to add to input)", expanded=False):
    suggs = make_suggestions(st.session_state.selected_brand, persona, barrier, segment, specialty, objective)
    sugg_cols = st.columns(3)
    for i, s in enumerate(suggs):
        col = sugg_cols[i % 3]
        if col.button(s, key=f"sugg_{i}"):
            st.session_state.main_input = s

# Main input form - still using st.form but its visible input will be in normal layout.
# We'll also render the fixed container markup (it will pick up textarea's content).
with st.form("main_input_form", clear_on_submit=False):
    # the actual textarea used by user (we won't duplicate via JS)
    user_input = st.text_area("Your question:", value=st.session_state.main_input, key="main_textarea", height=100)
    send = st.form_submit_button("Send")
    # For UX: when user clicks send, we process below

    if send and user_input and user_input.strip():
        # If in dislike flow stage 2 with refinement options, treat this as typed clarification
        df = st.session_state.dislike_flow
        if df and df.get("stage") == 2 and df.get("target_idx") is not None and df.get("refinement_choice"):
            # typed clarification provided along with previous refinement choice - generate refined answer
            target_idx = df["target_idx"]
            reason = df.get("reason")
            refinement_choice = df.get("refinement_choice")
            original_entry = st.session_state.chat_history[target_idx] if 0 <= target_idx < len(st.session_state.chat_history) else None
            original_content = original_entry["content"] if original_entry else ""
            user_clarify = user_input.strip()
            prompt = (f"Original answer:\n{original_content}\n\n"
                      f"User feedback reason: {reason}\n"
                      f"Refinement requested: {refinement_choice}\n"
                      f"User clarification: {user_clarify}\n\n"
                      "Please generate a refined, improved, concise answer addressing the user's refinement choice.")
            refined = ai_generate(prompt)
            st.session_state.chat_history.append({"role":"user","content": f"(Refinement) {user_clarify}"})
            st.session_state.chat_history.append({"role":"assistant","content": refined})
            st.session_state.feedback[original_content] = f"dislike->{reason}->{refinement_choice}"
            st.session_state.dislike_flow = None
            st.session_state.main_input = ""
            st.experimental_rerun() if False else st.rerun()
        else:
            # Normal message flow
            st.session_state.chat_history.append({"role":"user","content": user_input.strip()})
            # build enriched prompt with local snippets
            snippets = local_search_snippets(user_input.strip(), chunks, chunk_meta, top_n=4)
            sn_text = "\n".join([f"- {s['text']}" for s in snippets]) if snippets else ""
            model_prompt = f"{user_input.strip()}\n\nRelevant snippets:\n{sn_text}\n\nProvide a clear, actionable reply."
            ai_resp = ai_generate(model_prompt)
            st.session_state.chat_history.append({"role":"assistant","content": ai_resp, "meta": {"snippets": snippets}})
            st.session_state.main_input = ""
            # re-run to ensure fixed input stays at bottom and JS recalculates positions
            st.rerun()

# -------------------------
# Display chat history with feedback controls and dislike multi-turn (buttons)
# -------------------------
for idx, entry in enumerate(st.session_state.chat_history):
    if entry["role"] == "user":
        st.markdown(f'<div class="chat-bubble-user">{escape(entry["content"])}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">{escape(entry["content"])}</div>', unsafe_allow_html=True)
        meta = entry.get("meta") or {}
        if meta.get("citation"):
            st.markdown(f'<div class="citation-box">{escape(meta["citation"])}</div>', unsafe_allow_html=True)
        elif meta.get("snippets"):
            stext = "\n".join([f"{s['meta']['filename']} ({s['score']:.2f})" for s in meta.get("snippets", [])])
            if stext:
                st.markdown(f'<div class="citation-box">{escape(stext)}</div>', unsafe_allow_html=True)

        # audio
        audio_b64 = generate_audio(entry["content"])
        if audio_b64:
            st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")

        # Feedback controls & multi-turn dislike flow:
        df = st.session_state.dislike_flow
        is_target = df and df.get("target_idx") == idx

        if not df:
            cols = st.columns([1,1,1])
            if cols[0].button("👍 Like", key=f"like_{idx}"):
                st.session_state.feedback[entry["content"]] = "like"
                st.success("✅ Saved: Like")
            if cols[1].button("👎 Dislike", key=f"dislike_{idx}"):
                st.session_state.feedback[entry["content"]] = "dislike"
                # start stage 1: ask reason
                st.session_state.dislike_flow = {"stage": 1, "target_idx": idx, "reason": None, "refinement_choice": None}
                st.session_state.chat_history.append({"role":"assistant", "content": "Thanks for your feedback — what didn't you like about the response? Choose one: Unclear / Too long / Not relevant / Missing important info", "meta": {"options": ["Unclear","Too long","Not relevant","Missing important info"]}})
                st.rerun()
            if cols[2].button("ℹ️ Need More", key=f"needmore_{idx}"):
                st.session_state.feedback[entry["content"]] = "need_more"
                expand_prompt = f"Expand the following answer with more examples, practical steps and clarity:\n\n{entry['content']}"
                extra = ai_generate(expand_prompt)
                st.session_state.chat_history.append({"role":"assistant","content": extra})
                st.rerun()

        elif is_target and df.get("stage") == 1:
            # present reason buttons (from the assistant message's meta "options" if present)
            st.markdown("**Which of these best describes the issue?**")
            rcols = st.columns(4)
            reasons = ["Unclear", "Too long", "Not relevant", "Missing important info"]
            for i, reason in enumerate(reasons):
                if rcols[i].button(reason, key=f"reason_{idx}_{i}"):
                    st.session_state.dislike_flow["reason"] = reason
                    st.session_state.dislike_flow["stage"] = 2
                    # append targeted follow-up question with options for refinement
                    if reason == "Unclear":
                        follow_q = "Would you like me to Simplify or Rephrase?"
                        opts = ["Simplify", "Rephrase"]
                    elif reason == "Too long":
                        follow_q = "Would you like a Short summary or Bullet points?"
                        opts = ["Short summary", "Bullet points"]
                    elif reason == "Not relevant":
                        follow_q = "Would you like me to Focus on a specific Topic or Objective?"
                        opts = ["Focus topic", "Focus objective"]
                    else:
                        follow_q = "Which category should I add? (Clinical data / Practical steps / Examples / References)"
                        opts = ["Clinical data", "Practical steps", "Examples", "References"]
                    st.session_state.chat_history.append({"role":"assistant", "content": follow_q, "meta": {"options": opts}})
                    st.rerun()

        elif is_target and df.get("stage") == 2:
            # show refinement option buttons based on last assistant meta
            last_assistant = st.session_state.chat_history[-1]
            options = last_assistant.get("meta", {}).get("options", [])
            if options:
                st.markdown("**Choose a refinement option:**")
                opt_cols = st.columns(len(options))
                for i, opt in enumerate(options):
                    if opt_cols[i].button(opt, key=f"refine_{idx}_{i}"):
                        st.session_state.dislike_flow["refinement_choice"] = opt
                        # generate refined answer
                        target_entry = st.session_state.chat_history[df["target_idx"]]
                        original_content = target_entry["content"]
                        reason = st.session_state.dislike_flow.get("reason")
                        refinement_choice = st.session_state.dislike_flow.get("refinement_choice")
                        prompt = (f"Original assistant answer:\n{original_content}\n\n"
                                  f"User feedback reason: {reason}\n"
                                  f"Refinement requested: {refinement_choice}\n\n"
                                  "Please generate a refined, concise, actionable answer addressing the user's choice.")
                        refined = ai_generate(prompt)
                        st.session_state.chat_history.append({"role":"assistant","content": refined})
                        st.session_state.feedback[original_content] = f"dislike->{reason}->{refinement_choice}"
                        st.session_state.dislike_flow = None
                        st.rerun()
            else:
                st.markdown("You can also type a short clarification in the input box below to refine the answer.")

# -------------------------
# Render fixed bottom input container HTML (so it visually stays pinned)
# but actual form is the one above (textarea with key "main_textarea").
# The following creates a copy of the send button UI to visually align with CSS.
# -------------------------
FIXED_HTML = """
<div id="fixed-input">
  <textarea id="fixed-textarea" placeholder="Type your message here..." aria-label="Input"></textarea>
  <div style="display:flex; flex-direction:column; gap:8px;">
    <button class="send-button" id="fixed-send">Send</button>
    <div style="display:flex; gap:6px; justify-content:flex-end;">
      <div class="suggestion-pill" id="pill-1">Quick: call flow</div>
      <div class="suggestion-pill" id="pill-2">Quick: handle objection</div>
    </div>
  </div>
</div>

<script>
(function(){{
  // sync the visible fixed textarea with Streamlit's hidden textarea (main_textarea)
  const fixed = document.getElementById('fixed-textarea');
  const send = document.getElementById('fixed-send');

  // try to find the Streamlit textarea element (textarea[data-testid])
  function findStreamlitTextarea() {{
    // streamlit's textarea has id that includes 'main_textarea' as the key we set,
    // but DOM structure varies, so query for textarea elements and pick one we can set
    const ta = Array.from(document.querySelectorAll('textarea')).find(t => t.getAttribute('id') && t.getAttribute('id').includes('main_textarea'));
    return ta || document.querySelector('textarea');
  }}

  const stTA = findStreamlitTextarea();

  if (stTA) {{
    // initialize fixed textarea with current st textarea value
    fixed.value = stTA.value || "";

    // when user types in fixed -> update st's textarea
    fixed.addEventListener('input', (e) => {{
      stTA.value = e.target.value;
      stTA.dispatchEvent(new Event('input', {{ bubbles: true }}));
    }});

    // if user types in the underlying textarea, reflect back to fixed (best-effort)
    stTA.addEventListener('input', (e) => {{
      fixed.value = stTA.value;
    }});
  }}

  // clicking send should trigger an Enter keypress on the st textarea to submit the form
  send.addEventListener('click', () => {{
    if (stTA) {{
      // ensure value synced
      stTA.value = fixed.value;
      stTA.dispatchEvent(new Event('input', {{ bubbles: true }}));
      // find the form's submit button (button with text 'Send' inside form) - best-effort
      const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim().toLowerCase()==='send');
      if (btn) {{
        btn.click();
      }} else {{
        // fallback: try to submit the first form
        const form = document.querySelector('form');
        if (form) form.requestSubmit();
      }}
    }}
  }});

  // quick suggestion pills to prefill input
  const pill1 = document.getElementById('pill-1');
  const pill2 = document.getElementById('pill-2');
  pill1.addEventListener('click', () => {{
    if (stTA) {{
      stTA.value = 'Generate call flow for selected persona.';
      stTA.dispatchEvent(new Event('input', {{ bubbles: true }}));
      fixed.value = stTA.value;
    }}
  }});
  pill2.addEventListener('click', () => {{
    if (stTA) {{
      stTA.value = 'Handle objection: cost concerns for this persona.';
      stTA.dispatchEvent(new Event('input', {{ bubbles: true }}));
      fixed.value = stTA.value;
    }}
  }});
}})();
</script>
"""
st.markdown(FIXED_HTML, unsafe_allow_html=True)

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown("""
<div class="fixed-disclaimer">
💡 This tool is for internal sales support purposes only. Verify all clinical details with official sources.
</div>
""", unsafe_allow_html=True)
