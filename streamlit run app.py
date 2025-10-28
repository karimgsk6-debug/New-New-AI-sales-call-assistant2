# app.py - Final AI Sales Call Assistant (Brand-grounded, APACT, gTTS voice, GROQ placeholder)
import streamlit as st
import os, re, tempfile, base64, io
from datetime import datetime
from html import escape

# Optional libs (best-effort)
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

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# GROQ API placeholder (backend only)
# -------------------------
GROQ_API_KEY = "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"
client = None
# If/when you want to enable real GROQ, initialize client here (kept backend-only)
def query_groq_api(prompt: str) -> str:
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("add_GROQ"):
        return "GROQ not configured."
    # Place GROQ client query here when ready
    return "GROQ response placeholder."

# -------------------------
# Defaults & session_state initialization (ensure nested dicts exist)
# -------------------------
defaults = {
    "chat_history": [],          # list of dicts: {"role":"user"/"assistant","text": "...", "audio_b64": "..."}
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.62,
    "search_mode": "deep",
    "language": "English",
    "reply_style": "balanced",   # balanced, short_script, data, conversational
    "awaiting_style_pref": False,
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# ensure nested dicts exist
for nk in ["medical_summary", "sales_summary", "pdf_summary", "feedback"]:
    if nk not in st.session_state or not isinstance(st.session_state[nk], dict):
        st.session_state[nk] = {}

# -------------------------
# Brand data (includes Trelegy)
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
# CSS & layout tweaks
# -------------------------
CSS = """
<style>
/* basic aesthetic */
.title-box { background: rgba(255,255,255,0.96); padding:10px; border-radius:10px; display:flex; align-items:center; justify-content:center; margin-bottom:12px; }
.chat-container { max-height:60vh; overflow-y:auto; padding:12px; background: rgba(255,255,255,0.96); border-radius:8px; margin-bottom:160px; }
.chat-bubble-user { background:#0078D7; color:white; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto; }
.chat-bubble-ai { background:#eef9ff; color:#000; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }
.suggestions { background:#fff; border:1px solid #ddd; padding:8px; border-radius:8px; }
.input-area { position:fixed; left:20px; right:20px; bottom:18px; z-index:9999; background: rgba(255,255,255,0.98); padding:10px; border-radius:10px; box-shadow: 0 8px 30px rgba(0,0,0,0.08); }
.send-button { background:#FF6F00; color:white; padding:8px 14px; border-radius:8px; border:none; font-weight:600; cursor:pointer; }
.fixed-disclaimer { position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# -------------------------
# Helper functions for files, summarization, search, audio
# -------------------------
def read_file_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()
    except Exception:
        return ""

def build_corpus_for_folders(folders, chunk_size_sentences=3):
    """Return chunks (list of text) and metas (list of dicts)."""
    chunks, metas = [], []
    for folder in folders:
        if not folder or not os.path.exists(folder):
            continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf", ".txt"))]
        for fname in files:
            p = os.path.join(folder, fname)
            text = read_file_text(p)
            if not text: 
                continue
            sents = re.split(r'(?<=[\.!\?])\s+', text)
            for i in range(0, max(1, len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename": fname, "folder": folder, "start": i})
    return chunks, metas

def simple_summary(text: str, bullets: int = 6) -> str:
    if not text:
        return ""
    sents = re.split(r'(?<=[\.!\?])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join([f"- {s}" for s in selected])

def model_summarize(text: str, bullets: int = 6) -> str:
    """Prefer GROQ client if available; else simple summary."""
    if not text:
        return ""
    if client:
        try:
            prompt = f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                                   messages=[{"role":"user","content":prompt}],
                                                   temperature=0.2)
            return resp.choices[0].message.content
        except Exception:
            return simple_summary(text, bullets)
    return simple_summary(text, bullets)

def local_search_snippets(query: str, chunks: list, metas: list, top_n: int = 5):
    """Return top matching snippets (score,text,meta). Uses TF-IDF if available, else substring match."""
    if not chunks:
        return []
    q = query.lower().strip()
    if SKLEARN_AVAILABLE and q:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks + [query])
            chunk_vecs = vectorizer.transform(chunks)
            q_vec = vectorizer.transform([query])
            sims = linear_kernel(q_vec, chunk_vecs).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            results = []
            for idx in top_idxs:
                if sims[idx] <= 0:
                    continue
                results.append({"score": float(sims[idx]), "text": chunks[idx], "meta": metas[idx]})
            return results
        except Exception:
            pass
    # fallback substring
    out = []
    for i, c in enumerate(chunks):
        if q and q in c.lower():
            out.append({"score": 1.0, "text": c, "meta": metas[i]})
            if len(out) >= top_n:
                break
    return out

def generate_audio_base64(text: str) -> str:
    """Default gTTS-based TTS: return base64 mp3 or empty string on failure."""
    if not text or not gTTS:
        return ""
    # humanize: insert gentle ellipses between sections
    tts_text = re.sub(r'\n\s*\n', ' ... ', text)
    tts_text = tts_text.replace("\n", " ")
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=tts_text, lang="en", slow=False).save(tmp.name)
        with open(tmp.name, "rb") as fh:
            return base64.b64encode(fh.read()).decode("utf-8")
    except Exception:
        return ""

# -------------------------
# UI: title & sidebar controls
# -------------------------
st.markdown(f'<div class="title-box"><h2>💡 AI Sales Call Assistant — {brand_data[st.session_state.selected_brand]["display"]}</h2></div>', unsafe_allow_html=True)

with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand), format_func=lambda k: brand_data[k]["display"])
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]
    segment = st.selectbox("Segment", bconf["segments"])
    persona = st.selectbox("HCP Persona", bconf["personas"])
    barrier = st.multiselect("Doctor Barrier", bconf["barriers"])
    specialty = st.selectbox("Specialty", bconf["specialties"])
    objective = st.selectbox("Objective", ["Awareness","Adoption","Retention"])
    st.session_state.temperature = st.slider("Temperature", 0.0, 1.0, st.session_state.temperature, 0.05)
    st.session_state.search_mode = st.selectbox("Search mode", ["deep","shallow"])
    st.session_state.language = st.radio("Language", ["English","Arabic"])
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []

with st.sidebar.expander("🌐 Add External Reference URLs (one per line)", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT","DOCX"], horizontal=True)

# -------------------------
# Load brand-specific docs (summaries & corpus)
# -------------------------
brand = st.session_state.selected_brand
refs_folder = brand_data[brand]["references_path"]
sales_folder = brand_data[brand]["sales_path"]

# Build summaries per brand only if not present
if brand not in st.session_state["medical_summary"]:
    # read files and summarize
    combined = ""
    if os.path.exists(refs_folder):
        for f in sorted(os.listdir(refs_folder)):
            if f.lower().endswith((".pdf", ".txt")):
                combined += read_file_text(os.path.join(refs_folder, f)) + "\n"
    st.session_state["medical_summary"][brand] = model_summarize(combined, bullets=6) if combined.strip() else ""

if brand not in st.session_state["sales_summary"]:
    combined_s = ""
    if os.path.exists(sales_folder):
        for f in sorted(os.listdir(sales_folder)):
            if f.lower().endswith((".pdf", ".txt")):
                combined_s += read_file_text(os.path.join(sales_folder, f)) + "\n"
    st.session_state["sales_summary"][brand] = model_summarize(combined_s, bullets=6) if combined_s.strip() else ""

# build corpus for current brand (both refs and sales modules)
corpus_folders = []
if os.path.exists(refs_folder): corpus_folders.append(refs_folder)
if os.path.exists(sales_folder): corpus_folders.append(sales_folder)
chunks, metas = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# Prompt suggestions helper
# -------------------------
def make_suggestions(brand_key, persona_val, barriers_list, segment_val, specialty_val, objective_val):
    s = []
    s.append(f"Generate call flow for {persona_val} focused on {objective_val}.")
    if barriers_list: s.append(f"Handle objection: {', '.join(barriers_list[:2])} for {persona_val}.")
    else: s.append(f"Identify common objections for {persona_val}.")
    s.append(f"Summarize HCP persona insights for {persona_val}.")
    s.append(f"Key talking points for {brand_data[brand_key]['display']} in {segment_val}.")
    s.append(f"Draft a short adoption message for {brand_data[brand_key]['display']} to a {specialty_val}.")
    return s

# -------------------------
# APACT response builder (grounded to approved docs)
# -------------------------
def add_ai_response(prompt: str, follow_up: bool = False, context_previous: str = None):
    """
    Build APACT response grounded ONLY on the approved documents (chunks) for the selected brand.
    follow_up -> produce clarifying / deeper questions.
    """
    # search for relevant snippets from brand corpus
    snippets = local_search_snippets(prompt, chunks, metas, top_n=6)
    # We'll produce a structured APACT response; avoid exposing filenames
    out = []

    # Humanized opener
    opener = "Thanks — I hear you. Let’s make this practical." if not follow_up else "Thanks — I’ll refine this now based on your feedback."
    out.append(opener)
    out.append("")

    # APACT: Acknowledge
    out.append("**🟢 Acknowledge**")
    out.append("- I understand this is important for patient care and clinic workflow.")
    out.append("")

    # APACT: Probe (open & closed sample questions)
    out.append("**🔵 Probe — suggested questions (pick or adapt)**")
    out.append("- Open: “Can you tell me which patient groups you’re most concerned about?”")
    out.append("- Closed: “Is your main concern safety, efficacy, or access? (Reply: safety/efficacy/access)”")
    out.append("- Diagnostic: “How many eligible patients do you see weekly?”")
    out.append("")

    # APACT: Actions (use call flow from brand; include examples & multiple options)
    out.append("**🟣 Actions — call flow steps (APACT-guided) with phrasing & options**")
    reply_style = st.session_state.get("reply_style", "balanced")
    for step in brand_data[brand]["call_flow"]:
        out.append(f"**{step}**")
        # find relevant snippets mentioning step or topic
        related = []
        for s in snippets:
            t = s.get("text", "")
            if step.lower() in t.lower():
                related.append((s["score"], t))
        # fallback: any snippet if none mention the step
        if not related and snippets:
            related = [(s["score"], s["text"]) for s in snippets]
        # show up to 2 grounded bullets derived from snippets
        added = 0
        for score, text in sorted(related, key=lambda x: x[0], reverse=True)[:2]:
            short = re.split(r'(?<=[\.!\?])\s+', text.strip())[0][:240]
            if reply_style == "short_script":
                out.append(f"- Quick line: \"{short}.\" (15s)")
            elif reply_style == "data":
                out.append(f"- Data-backed line: {short} — follow with 'In internal materials we note...'")
            elif reply_style == "conversational":
                out.append(f"- Role-play: Rep: \"{short}.\" HCP: \"[response]\" — then add patient story.")
            else:  # balanced
                out.append(f"- {short} — Example phrasing: \"{short}...\"")
            added += 1
        if added == 0:
            # generic guidance if no snippet
            out.append("- Use the brand sales module's step guidance; tailor to the HCP's barrier.")
        out.append("")  # space

    # APACT: Confirm
    out.append("**🟠 Confirm**")
    out.append("- Does this direction address the HCP's main barrier? (Yes / No)")
    out.append("")

    # APACT: Transition
    out.append("**🟡 Transition**")
    out.append("- If yes, I can prepare: (A) Short script, (B) Role-play examples, (C) One-page patient checklist.")
    out.append("- Reply with A/B/C or ask me to generate it now.")
    out.append("")

    # Humanized closing + note about sources
    out.append("—")
    out.append("*All phrasing and data points above are grounded in GSK-approved internal references and sales modules uploaded for this brand.*")
    # Do NOT expose filenames; we intentionally avoid names in the response.

    ai_text = "\n".join(out)

    # Save assistant entry and generate audio
    audio_b64 = generate_audio_base64(ai_text)
    entry = {"role":"assistant", "text": ai_text, "audio_b64": audio_b64}
    st.session_state["chat_history"].append(entry)

    # If follow_up requested, create clarifying questions instead of full plan
    if follow_up:
        follow_lines = []
        follow_lines.append("Thanks — quick clarifying questions to help me improve:")
        follow_lines.append("- Which part felt off: (1) unclear, (2) not practical, (3) too technical, (4) other")
        follow_lines.append("- Preferred output: (A) Short script, (B) Data bullets, (C) Conversational role-play")
        follow_text = "\n".join(follow_lines)
        audio_b64_f = generate_audio_base64(follow_text)
        st.session_state["chat_history"].append({"role":"assistant","text":follow_text,"audio_b64":audio_b64_f})

# -------------------------
# Prompt suggestions UI (collapsible) & chat container
# -------------------------
chat_container = st.container()

with chat_container:
    # render existing chat
    for idx, entry in enumerate(st.session_state["chat_history"]):
        if entry.get("role") == "user":
            st.markdown(f'<div class="chat-bubble-user">{escape(entry["text"])}</div>', unsafe_allow_html=True)
        else:
            # assistant
            st.markdown(f'<div class="chat-bubble-ai">{escape(entry["text"]).replace("\\n","<br>")}</div>', unsafe_allow_html=True)
            # play audio if available
            audio_b64 = entry.get("audio_b64", "")
            if audio_b64:
                try:
                    st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")
                except Exception:
                    pass
            # feedback buttons (interactive)
            fb_cols = st.columns(3)
            entry_key = f"fb_{idx}"
            if entry_key not in st.session_state["feedback"]:
                if fb_cols[0].button("👍 Like", key=f"like_{idx}"):
                    st.session_state["feedback"][entry_key] = "like"
                    # optionally ask preference
                    pref_text = "Great — would you like short scripts (1), data bullets (2), or conversational examples (3)? Reply 1/2/3."
                    audio_pref = generate_audio_base64(pref_text)
                    st.session_state["chat_history"].append({"role":"assistant","text":pref_text,"audio_b64":audio_pref})
                if fb_cols[1].button("👎 Dislike", key=f"dislike_{idx}"):
                    st.session_state["feedback"][entry_key] = "dislike"
                    prev_text = entry.get("text","")
                    # generate follow-up clarifying questions
                    add_ai_response("User rejected previous answer — follow up", follow_up=True, context_previous=prev_text)
                if fb_cols[2].button("ℹ️ Need More", key=f"needmore_{idx}"):
                    st.session_state["feedback"][entry_key] = "need_more"
                    prev_text = entry.get("text","")
                    add_ai_response("User requested expansion — follow up", follow_up=True, context_previous=prev_text)

# -------------------------
# Prompt suggestions (collapsible, above fixed input)
# -------------------------
with st.expander("💡 Prompt Suggestions (click to expand)", expanded=False):
    suggs = make_suggestions(brand, persona, barrier, segment, specialty, objective)
    cols = st.columns(2)
    for i, s in enumerate(suggs):
        c = cols[i % 2]
        if c.button(s, key=f"psugg_{i}"):
            st.session_state["main_input"] = s

# -------------------------
# Chat input area (fixed at bottom)
# -------------------------
st.markdown('<div class="input-area">', unsafe_allow_html=True)
col1, col2, col3 = st.columns([8,2,1])
with col1:
    # keep main_input in session_state so suggestions can set it
    main_text = st.text_area("Your message", value=st.session_state.get("main_input",""), key="main_input_area", height=90)
with col2:
    if st.button("Send", key="send_button"):
        if main_text and main_text.strip():
            # append user entry
            st.session_state["chat_history"].append({"role":"user", "text": main_text.strip()})
            # generate AI response grounded to brand docs
            add_ai_response(main_text.strip(), follow_up=False)
            # clear input
            st.session_state["main_input"] = ""
            st.experimental_rerun()
with col3:
    if st.button("Clear", key="clear_btn"):
        st.session_state["main_input"] = ""
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Small utility displays for summaries (collapsible)
# -------------------------
with st.expander("📚 Medical References Summary (brand-specific)", expanded=False):
    md = st.session_state["medical_summary"].get(brand, "No medical references summary available.")
    st.markdown(md)

with st.expander("💼 Sales Module Summary (brand-specific)", expanded=False):
    sd = st.session_state["sales_summary"].get(brand, "No sales module summary available.")
    st.markdown(sd)

# -------------------------
# PDF upload (per brand)
# -------------------------
with st.sidebar.expander("Upload PDF for brand (optional)", expanded=False):
    up = st.file_uploader("Upload a PDF (brand-specific)", type=["pdf", "txt"])
    if up:
        try:
            if hasattr(up, "type") and up.type == "application/pdf" and PdfReader:
                reader = PdfReader(up)
                text = "".join([p.extract_text() or "" for p in reader.pages])
            else:
                # txt fallback
                text = up.getvalue().decode("utf-8", errors="ignore")
            st.session_state["pdf_summary"][brand] = model_summarize(text, bullets=6)
            st.success("Uploaded PDF summarized and saved for this brand.")
        except Exception:
            st.error("Failed to read uploaded file.")

# -------------------------
# Footer / disclaimer
# -------------------------
st.markdown("""
<div class="fixed-disclaimer">
⚠️ Internal tool — outputs are generated from GSK-approved references and sales modules uploaded in the repo. Verify clinical information before external use.
</div>
""", unsafe_allow_html=True)
