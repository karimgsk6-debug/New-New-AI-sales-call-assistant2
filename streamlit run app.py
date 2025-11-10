# app.py - AI Sales Call Assistant (Full, merged, ready-to-run)
import streamlit as st
import os, re, tempfile, base64, io, json
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

# Repo raw base for assets (keeps your previous structure)
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
BACKGROUND_REL = ".devcontainer/Visuals/MR mentor final1.png"
BACKGROUND_URL = f"https://github.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/blob/ef6947d67d0a851afc9674feb013bb7634df7a5e/.devcontainer/Visuals/MR%20mentor%20final1.png"
GSK_LOGO_RAW = f"{REPO_RAW_BASE}/GSK1-logo.png"
AI_LOGO_RAW = f"{REPO_RAW_BASE}/AURA1.png"

# -------------------------
# Session defaults
# -------------------------
defaults = {
    "chat_history": [],  # list of {"role":"user"/"assistant","content":str,"meta":{}}
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.9,
    "search_mode": "deep",
    "medical_summary": "",
    "sales_summary": "",
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "feedback": {},  # mapping content -> like/dislike/need_more
    "language": "English",
    # states for dislike multi-turn flow
    "dislike_flow": None,  # None or dict with keys: stage (1/2), target_idx, reason, refinement_choice
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# -------------------------
# CSS + right-anchored background + JS to respond to sidebar width changes
# -------------------------
CSS = f"""
<style>
/* Basic app styling and chat bubbles */
[data-testid="stAppViewContainer"] {{ background: linear-gradient(120deg, #fff7f0, #fffefc 40%); }}
.title-box {{
  background: rgba(255,255,255,0.85);
  padding: 10px;
  border-radius: 10px;
  display:flex;
  align-items:center;
  justify-content:center;
  position:relative;
  margin-bottom:10px;
}}
.title-box img.left-logo {{ position:absolute; left:12px; height:58px; }}
.title-box img.right-logo {{ position:absolute; right:12px; height:58px; }}
.chat-bubble-user {{ background:#0078D7; color:white; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }}
.chat-bubble-ai {{ background:#eef9ff; color:#000; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }}
.citation-box {{ background:#fbfbff; border-left:4px solid #0078D7; padding:8px; margin-top:8px; border-radius:6px; font-size:13px; white-space:pre-wrap; }}
.fixed-disclaimer {{ position:fixed; bottom:0; left:0; right:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }}

/* Right anchored background image container */
#bg-right {{
  position: fixed;
  top: 80px;
  bottom: 0;
  right: 0; /* updated dynamically via JS to account for sidebar width */
  width: 35vw; /* default width */
  max-width: 720px;
  min-width: 200px;
  background-image: url('{BACKGROUND_URL}');
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center right;
  opacity: 0.75;
  pointer-events: none;
  z-index: 1;
  transition: right 220ms ease, width 220ms ease, opacity 220ms ease;
  filter: saturate(0.95) contrast(0.95);

@media (max-width: 1000px) {{
  #bg-right {{ display:none; }}
}}
</style>

<!-- JS to observe sidebar width changes and adjust the right-anchored BG container -->
<script>
(function() {{
  function querySidebar() {{
    // Try multiple selectors for streamlit sidebar container (best effort)
    return document.querySelector('[data-testid="stSidebar"]') ||
           document.querySelector('section[aria-label="Sidebar"]') ||
           document.querySelector('.css-1d391kg'); // fallback
  }}

  function updateBgPosition() {{
    const bg = document.getElementById('bg-right');
    const sidebar = querySidebar();
    if (!bg) return;
    if (sidebar) {{
      const rect = sidebar.getBoundingClientRect();
      // position background right to the sidebar (so it shrinks when sidebar expands)
      bg.style.right = (window.innerWidth - rect.left) + 'px';
      // optionally reduce width when sidebar takes a lot of space
      const used = rect.width / window.innerWidth;
      if (used > 0.35) {{
        bg.style.width = '20vw';
      }} else if (used > 0.18) {{
        bg.style.width = '28vw';
      }} else {{
        bg.style.width = '35vw';
      }}
    }} else {{
      // no sidebar found; stick to right 0
      bg.style.right = '0px';
      bg.style.width = '35vw';
    }}
  }}

  // initial call after a small delay for Streamlit render
  setTimeout(updateBgPosition, 400);

  // observe layout changes to update background
  const observer = new MutationObserver(function(m) {{
    updateBgPosition();
  }});

  observer.observe(document.body, {{ attributes: true, childList: true, subtree: true }});
  window.addEventListener('resize', updateBgPosition);
}})();
</script>

<div id="bg-right"></div>
"""
st.markdown(CSS, unsafe_allow_html=True)

# -------------------------
# Initialize GROQ client (safe placeholder)
# -------------------------
GROQ_API_KEY = "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"
client = None
if Groq and GROQ_API_KEY and GROQ_API_KEY != "add_your_GROQ_API_here":
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

# -------------------------
# Brand config (keeps your original data)
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
# Utility functions
# -------------------------
def read_file_text(path):
    if not os.path.exists(path): return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path,"r",encoding="utf-8",errors="ignore") as fh:
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
    """Generate AI response with fallback text if model not available."""
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
        # Offline fallback — produce a helpful structured canned reply
        return ("⚙️ Offline mode: model not connected. "
                "Here's a concise simulated response based on prompt start:\n\n"
                + (prompt[:800] + ("\n\n... (truncated)")))

# Local search utilities for references
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
# Sidebar controls (filters & options)
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

with st.sidebar.expander("🌐 Add External Reference URLs (one per line)", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT", "DOCX"], horizontal=True)

# -------------------------
# Title box
# -------------------------
st.markdown(f"""
<div class="title-box">
<img src="{GSK_LOGO_RAW}" class="left-logo">
<h2>💡 AI Sales Call Assistant — {brand_data[sel_brand]['display']}</h2>
<img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# -------------------------
# Load references & sales content (if available locally)
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
# PDF upload & summarization (in main interface)
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
# Build corpus (for local search)
# -------------------------
corpus_folders = [refs_folder, sales_folder]
chunks, chunk_meta = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# Prompt suggestion helper
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
# Add AI response and helper for APACT style
# -------------------------
def build_apact_response(prompt, follow_up=False, include_snippets=True):
    snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=4) if include_snippets else []
    citation = "\n".join([f"{s['meta']['filename']} ({s['score']:.2f})" for s in snippets]) if snippets else ""
    response_lines = []

    if not follow_up:
        # APACT structure
        response_lines.append("**Acknowledge:** Thank you — I understand the request.")
        response_lines.append("**Probing:** Could you confirm if you'd like a high-level summary or step-by-step guidance?")
        response_lines.append("**Actions:** Based on available sales modules and references, suggested steps:")
        for step in bconf["call_flow"]:
            # include snippet if matches
            step_snips = [s['text'] for s in snippets if step.lower() in s['text'].lower()]
            if step_snips:
                response_lines.append(f"**{step}:**")
                for sn in step_snips:
                    response_lines.append(f"- {sn}")
            else:
                response_lines.append(f"**{step}:** - Refer to the sales module for details.")
        response_lines.append("**Confirm:** Does this address the objective? If not, click Dislike and tell me what's off.")
        response_lines.append("\n*Tailored using sales modules & available references.*")
    else:
        # follow-up prompt for dislike handling — will be replaced by specific multi-turn questions
        response_lines.append("Thanks for the feedback — let's refine this. Which of the following best describes the issue?")
        response_lines.append("- Unclear")
        response_lines.append("- Too long")
        response_lines.append("- Not relevant")
        response_lines.append("- Missing important info")

    ai_text = "\n".join(response_lines)
    meta = {"citation": citation} if citation else {}
    st.session_state.chat_history.append({"role": "assistant", "content": ai_text, "meta": meta})

# -------------------------
# UI: prompt suggestions + input form
# -------------------------
with st.expander("💡 Prompt Suggestions (click to expand)", expanded=False):
    suggs = make_suggestions(sel_brand, persona, barrier, segment, specialty, objective)
    sugg_cols = st.columns(3)
    for i, s in enumerate(suggs):
        col = sugg_cols[i % 3]
        if col.button(s, key=f"sugg_{i}"):
            st.session_state.main_input = s

# Main input form (handles normal messages and dislike-flow refinement responses)
with st.form("main_input_form", clear_on_submit=True):
    user_input = st.text_area("💬 Ask something:", st.session_state.main_input, height=80)
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        # If currently in dislike multi-turn stage 2 (user clicked a refinement button earlier),
        # we will treat the user's typed input as an optional free-text clarification and generate refined response.
        if st.session_state.dislike_flow and st.session_state.dislike_flow.get("stage") == 2 and st.session_state.dislike_flow.get("target_idx") is not None:
            # Generate refined answer using stored reason/refinement_choice plus user free-text
            df = st.session_state.dislike_flow
            original_entry = st.session_state.chat_history[df["target_idx"]]
            original_content = original_entry["content"]
            reason = df.get("reason")
            refinement_choice = df.get("refinement_choice")
            user_clarify = user_input.strip()
            prompt = (
                f"Original answer:\n{original_content}\n\n"
                f"User feedback reason: {reason}\n"
                f"Refinement requested: {refinement_choice}\n"
                f"User added clarification: {user_clarify}\n\n"
                "Please produce a refined, improved answer tailored to the feedback."
            )
            refined = ai_generate(prompt)
            # append user typed clarification and refined AI
            st.session_state.chat_history.append({"role":"user","content": f"(Refinement input) {user_clarify}"})
            st.session_state.chat_history.append({"role":"assistant","content": refined})
            # reset dislike flow
            st.session_state.dislike_flow = None
            st.session_state.main_input = ""
        else:
            # normal user question flow
            st.session_state.chat_history.append({"role":"user","content": user_input.strip()})
            # create an APACT-style answer including snippets
            prompt = user_input.strip()
            # try to use local snippets to enrich prompt for model
            snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=4)
            sn_text = "\n".join([f"- {s['text']}" for s in snippets]) if snippets else ""
            model_prompt = f"{prompt}\n\nRelevant snippets:\n{sn_text}\n\nProvide a clear, actionable reply."
            ai_resp = ai_generate(model_prompt)
            st.session_state.chat_history.append({"role":"assistant","content": ai_resp, "meta": {"snippets": snippets}})
            st.session_state.main_input = ""

# -------------------------
# Display chat history and feedback controls (including multi-turn Dislike)
# -------------------------
chat_container = st.container()
with chat_container:
    for idx, entry in enumerate(st.session_state.chat_history):
        if entry["role"] == "user":
            st.markdown(f'<div class="chat-bubble-user">{escape(entry["content"])}</div>', unsafe_allow_html=True)
        else:
            # assistant messages may contain markdown like **Acknowledge:** — allow it but escape to avoid script injection
            st.markdown(f'<div class="chat-bubble-ai">{escape(entry["content"])}</div>', unsafe_allow_html=True)

            # show citation/snippets if present
            meta = entry.get("meta") or {}
            if meta.get("citation"):
                st.markdown(f'<div class="citation-box">{escape(meta["citation"])}</div>', unsafe_allow_html=True)
            elif meta.get("snippets"):
                # present small list of filenames/scores if snippets exist
                stext = "\n".join([f"{s['meta']['filename']} ({s['score']:.2f})" for s in meta.get("snippets", [])])
                if stext:
                    st.markdown(f'<div class="citation-box">{escape(stext)}</div>', unsafe_allow_html=True)

            # audio playback (best-effort)
            audio_b64 = generate_audio(entry["content"])
            if audio_b64:
                st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")

            # Feedback UI & Multi-turn Dislike handling:
            # If this message is the target of an ongoing dislike flow, show the multi-turn buttons accordingly
            current_df = st.session_state.dislike_flow
            is_target = (current_df and current_df.get("target_idx") == idx)

            if not current_df:
                # standard feedback buttons for messages that haven't been rated yet
                fb_cols = st.columns([1,1,1])
                if fb_cols[0].button("👍 Like", key=f"like_{idx}"):
                    st.session_state.feedback[entry["content"]] = "like"
                    st.success("✅ Feedback saved. Glad you liked it!")
                if fb_cols[1].button("👎 Dislike", key=f"dislike_{idx}"):
                    st.session_state.feedback[entry["content"]] = "dislike"
                    # start a dislike flow: stage 1 (choose reason)
                    st.session_state.dislike_flow = {"stage": 1, "target_idx": idx, "reason": None, "refinement_choice": None}
                    # append assistant prompt asking for reason (first stage)
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": "Thanks for the feedback — what didn't you like about the response? Please pick one:",
                        "meta": {}
                    })
                    # rerun so UI updates to show buttons for reasons
                    st.rerun()
                if fb_cols[2].button("ℹ️ Need More", key=f"needmore_{idx}"):
                    st.session_state.feedback[entry["content"]] = "need_more"
                    # auto-expand previous content with more depth
                    expand_prompt = f"Expand the following answer with more examples and step-by-step guidance:\n\n{entry['content']}"
                    extra = ai_generate(expand_prompt)
                    st.session_state.chat_history.append({"role": "assistant", "content": extra})
                    st.rerun()

            elif is_target and current_df.get("stage") == 1:
                # Present reason buttons: Unclear, Too long, Not relevant, Missing important info
                st.markdown("**Please tell me which best describes the issue:**")
                rcols = st.columns(4)
                reasons = ["Unclear", "Too long", "Not relevant", "Missing important info"]
                for i, reason in enumerate(reasons):
                    if rcols[i].button(reason, key=f"reason_{idx}_{i}"):
                        # save reason and proceed to refinement stage 2
                        st.session_state.dislike_flow["reason"] = reason
                        st.session_state.dislike_flow["stage"] = 2
                        # append a targeted follow-up question depending on reason
                        if reason == "Unclear":
                            follow_q = "Would you like me to simplify or rephrase it? (Choose one)"
                            opts = ["Simplify", "Rephrase"]
                        elif reason == "Too long":
                            follow_q = "Would you like a short summary or bullet points?"
                            opts = ["Short summary", "Bullet points"]
                        elif reason == "Not relevant":
                            follow_q = "Would you like me to focus on a specific topic or objective?"
                            opts = ["Focus topic", "Focus objective"]
                        else:  # Missing important info
                            follow_q = "What category of information is missing? (Choose one)"
                            opts = ["Clinical data", "Practical steps", "Examples", "References"]

                        st.session_state.chat_history.append({"role":"assistant","content": follow_q, "meta": {"options": opts}})
                        st.rerun()

            elif is_target and current_df.get("stage") == 2:
                # Show refinement choices from last assistant message's meta options if present
                last_assistant = st.session_state.chat_history[-1]
                options = last_assistant.get("meta", {}).get("options", [])
                if options:
                    st.markdown("**Choose one of the refinement options:**")
                    opts_cols = st.columns(len(options))
                    for i, opt in enumerate(options):
                        if opts_cols[i].button(opt, key=f"refine_{idx}_{i}"):
                            # record refinement choice and generate refined response
                            st.session_state.dislike_flow["refinement_choice"] = opt
                            df = st.session_state.dislike_flow
                            target_entry = st.session_state.chat_history[df["target_idx"]]
                            original_content = target_entry["content"]
                            reason = df.get("reason")
                            refinement_choice = df.get("refinement_choice")
                            # build prompt for refinement
                            prompt = (
                                f"Original assistant answer:\n{original_content}\n\n"
                                f"User feedback reason: {reason}\n"
                                f"Refinement requested: {refinement_choice}\n\n"
                                "Please generate a refined improved answer addressing the user's choice. Keep it concise and actionable."
                            )
                            refined = ai_generate(prompt)
                            # append refined answer and clear dislike flow
                            st.session_state.chat_history.append({"role":"assistant","content": refined})
                            # mark feedback final
                            st.session_state.feedback[entry["content"]] = f"dislike->{reason}->{refinement_choice}"
                            st.session_state.dislike_flow = None
                            st.rerun()
                else:
                    # fallback: allow user to type clarification (if options not found)
                    st.write("You may type a short clarification in the input box below to refine the answer.")
                    # The text submitted via the input form will be used as clarification (handled earlier)

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown("""
<div class="fixed-disclaimer">
💡 This tool is for internal sales support purposes only. All clinical or medical information should be verified from official sources.
</div>
""", unsafe_allow_html=True)
