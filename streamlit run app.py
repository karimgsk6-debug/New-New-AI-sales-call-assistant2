# app.py - Final AI Sales Call Assistant (organized UI, APACT, grounded to brand docs,
#             resizable prompt bubble, interactive feedback, gTTS voice, export to DOCX/TXT)
import streamlit as st
import os, re, io, tempfile, base64
from datetime import datetime
from html import escape

# Optional imports (best-effort)
try:
    from PyPDF2 import PdfReader
except:
    PdfReader = None

try:
    from gtts import gTTS
except:
    gTTS = None

try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False

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
# GROQ placeholder (backend)
# -------------------------
GROQ_API_KEY = "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"
client = None
# If/when you enable Groq, initialize client here.
def query_groq_api(prompt: str) -> str:
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("add_GROQ"):
        return "GROQ not configured."
    # Implement GROQ call here when ready
    return "GROQ placeholder response."

# -------------------------
# Defensive session_state initialization
# -------------------------
defaults = {
    "chat_history": [],        # list of {"role":"user"/"assistant", "text":..., "audio_b64":...}
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.62,
    "search_mode": "deep",
    "language": "English",
    "reply_style": "balanced",  # balanced, short_script, data, conversational
    "awaiting_style_pref": False,
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# ensure nested dicts exist
for nk in ("medical_summary", "sales_summary", "pdf_summary", "feedback"):
    if nk not in st.session_state or not isinstance(st.session_state[nk], dict):
        st.session_state[nk] = {}

# -------------------------
# Brand config (includes Trelegy)
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
# CSS & UI styling (including resizable prompt box)
# -------------------------
st.markdown("""
<style>
/* layout */
.title-box { background: rgba(255,255,255,0.96); padding:14px; border-radius:10px; margin-bottom:12px; text-align:center; }
.section-bubble { background:#fbfcfe; border:1px solid #e8eef6; padding:12px; border-radius:10px; margin-bottom:10px; }
.chat-container { max-height:56vh; overflow-y:auto; padding:12px; background: rgba(255,255,255,0.96); border-radius:8px; margin-bottom:140px; }
.chat-bubble-user { background:#0078D7; color:white; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto; }
.chat-bubble-ai { background:#eef9ff; color:#000; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }
.resizable-suggestions { position: fixed; left: 20px; right: 20px; bottom: 120px; height: 160px; background: #fff; border:1px solid #ddd; padding:10px; border-radius:8px; resize: vertical; overflow: auto; z-index:9998; box-shadow:0 8px 30px rgba(0,0,0,0.06); }
.suggestion-pill { display:inline-block; padding:6px 10px; border-radius:18px; background:#f6f8fa; margin:4px; border:1px solid #e6e9ee; cursor:pointer; }
.input-area { position: fixed; left:20px; right:20px; bottom:18px; z-index:9999; background: rgba(255,255,255,0.98); padding:10px; border-radius:10px; box-shadow:0 8px 30px rgba(0,0,0,0.06); display:flex; gap:8px; align-items:flex-end; }
.send-button { background:#FF6F00; color:white; padding:8px 14px; border-radius:8px; border:none; font-weight:600; cursor:pointer; }
.fixed-disclaimer { position: fixed; left:0; right:0; bottom:0; background: rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }
.citation-note { font-size:13px; color:#333; background:#fbfbff; padding:8px; border-left:4px solid #0078D7; border-radius:6px; margin-top:8px; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Helper functions
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
    """Prefer GROQ if available; otherwise simple summary."""
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
    if not chunks or not query:
        return []
    q = query.lower().strip()
    if SKLEARN_AVAILABLE:
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
    out = []
    for i, c in enumerate(chunks):
        if q in c.lower():
            out.append({"score": 1.0, "text": c, "meta": metas[i]})
            if len(out) >= top_n:
                break
    return out

def generate_audio_base64(text: str) -> str:
    """Use gTTS (Google) by default; return base64 mp3, else empty string."""
    if not text or not gTTS:
        return ""
    tts_text = re.sub(r'\n\s*\n', ' ... ', text)
    tts_text = tts_text.replace("\n", " ")
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=tts_text, lang="en", slow=False).save(tmp.name)
        with open(tmp.name, "rb") as fh:
            return base64.b64encode(fh.read()).decode("utf-8")
    except Exception:
        return ""

def export_call_flow_bytes(text: str, fmt: str = "docx"):
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_brand = st.session_state.get("selected_brand", "brand")
    if fmt == "docx" and DOCX_AVAILABLE:
        doc = Document()
        doc.add_heading(f"{brand_data[safe_brand]['display']} — Generated Call Flow", level=2)
        for line in text.splitlines():
            doc.add_paragraph(line)
        bio = io.BytesIO()
        doc.save(bio)
        bio.seek(0)
        filename = f"{safe_brand}_callflow_{now}.docx"
        return bio.read(), filename
    else:
        b = text.encode("utf-8")
        filename = f"{safe_brand}_callflow_{now}.txt"
        return b, filename

# -------------------------
# UI: Title box and Sidebar controls
# -------------------------
st.markdown(f'<div class="title-box"><h2>💡 AI Sales Call Assistant — {brand_data[st.session_state["selected_brand"]]["display"]}</h2><div style="color:#666;font-size:14px;">APACT-guided, grounded in GSK-approved docs</div></div>', unsafe_allow_html=True)

with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state["selected_brand"]), format_func=lambda k: brand_data[k]["display"])
    st.session_state["selected_brand"] = sel_brand
    bconf = brand_data[sel_brand]
    # persona/segment selectors for suggestions context
    persona = st.selectbox("HCP Persona", bconf.get("personas", []))
    segment = st.selectbox("Segment", bconf.get("segments", []))
    barrier = st.multiselect("Doctor Barrier", bconf.get("barriers", []))
    specialty = st.selectbox("Specialty", bconf.get("specialties", []))
    objective = st.selectbox("Objective", ["Awareness","Adoption","Retention"])
    st.session_state["temperature"] = st.slider("Temperature", 0.0, 1.0, st.session_state["temperature"], 0.05)
    st.session_state["search_mode"] = st.selectbox("Search mode", ["deep","shallow"])
    st.session_state["language"] = st.radio("Language", ["English","Arabic"])
    if st.button("🗑️ Clear Chat"):
        st.session_state["chat_history"] = []

with st.sidebar.expander("Add External Reference URLs (one per line)", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("Export Options", expanded=False):
    export_format = st.radio("Default export format", ["DOCX","TXT"], index=0 if DOCX_AVAILABLE else 1)

# -------------------------
# Load Brand Summaries & Corpus (only when needed)
# -------------------------
brand = st.session_state["selected_brand"]
refs_folder = brand_data[brand]["references_path"]
sales_folder = brand_data[brand]["sales_path"]

# medical summary per brand
if brand not in st.session_state["medical_summary"]:
    combined_refs = ""
    if os.path.exists(refs_folder):
        for f in sorted(os.listdir(refs_folder)):
            if f.lower().endswith((".pdf", ".txt")):
                combined_refs += read_file_text(os.path.join(refs_folder, f)) + "\n"
    st.session_state["medical_summary"][brand] = model_summarize(combined_refs, bullets=6) if combined_refs.strip() else ""

# sales summary per brand
if brand not in st.session_state["sales_summary"]:
    combined_sales = ""
    if os.path.exists(sales_folder):
        for f in sorted(os.listdir(sales_folder)):
            if f.lower().endswith((".pdf", ".txt")):
                combined_sales += read_file_text(os.path.join(sales_folder, f)) + "\n"
    st.session_state["sales_summary"][brand] = model_summarize(combined_sales, bullets=6) if combined_sales.strip() else ""

# build corpus for grounding
corpus_folders = [p for p in (refs_folder, sales_folder) if os.path.exists(p)]
chunks, metas = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# Prompt suggestion generator
# -------------------------
def make_suggestions(brand_key, persona_val, barriers_list, segment_val, specialty_val, objective_val):
    s=[]
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
# APACT response builder (grounded)
# -------------------------
def add_ai_response(prompt: str, follow_up: bool=False, context_previous: str=None):
    """
    Create an APACT-structured response grounded in brand docs (chunks).
    If follow_up=True produce clarifying Qs instead of full plan.
    """
    # retrieve snippets from corpus
    snippets = local_search_snippets(prompt, chunks, metas, top_n=6)
    out_lines = []
    opener = "Thanks — I hear you. Let’s tackle this together." if not follow_up else "Thanks — I’ll refine this based on your feedback."
    out_lines.append(opener)
    out_lines.append("")

    # Acknowledge
    out_lines.append("**🟢 Acknowledge**")
    out_lines.append("- I understand why this matters for patient care and clinic workflow.")
    out_lines.append("")

    # Probe
    out_lines.append("**🔵 Probe — suggested questions**")
    out_lines.append("- Open: 'Can you tell me which patients you're most worried about?'")
    out_lines.append("- Closed: 'Is your main concern safety, efficacy, or access? (Reply: safety/efficacy/access)'")
    out_lines.append("- Diagnostic: 'How many eligible patients do you see per week?'")
    out_lines.append("")

    # Actions: use brand call_flow
    out_lines.append("**🟣 Actions — call flow steps with example phrasing**")
    reply_style = st.session_state.get("reply_style","balanced")
    for step in brand_data[brand]["call_flow"]:
        out_lines.append(f"**{step}**")
        # prefer snippets that mention the step, else any top snippets
        relevant = []
        for s in snippets:
            text = s.get("text","")
            if step.lower() in text.lower():
                relevant.append((s["score"], text))
        if not relevant:
            relevant = [(s["score"], s["text"]) for s in snippets]
        if relevant:
            for score, text in sorted(relevant, key=lambda x: x[0], reverse=True)[:2]:
                short = re.split(r'(?<=[\.!\?])\s+', text.strip())[0][:240]
                if reply_style == "short_script":
                    out_lines.append(f"- Quick line: \"{short}.\" (15s)")
                elif reply_style == "data":
                    out_lines.append(f"- Data-backed: {short} — follow with 'In internal materials we note...'")
                elif reply_style == "conversational":
                    out_lines.append(f"- Role-play: Rep: \"{short}.\" HCP: \"[response]\"")
                else:
                    out_lines.append(f"- {short} — Example phrasing: \"{short}...\"")
        else:
            out_lines.append("- Refer to the sales module for examples tailored to this step.")
        out_lines.append("")

    # Confirm & Transition
    out_lines.append("**🟠 Confirm**")
    out_lines.append("- Does this direction address the HCP's main barrier? (Yes / No)")
    out_lines.append("")
    out_lines.append("**🟡 Transition**")
    out_lines.append("- If yes, I can prepare: (A) Short script, (B) Role-play examples, (C) One-page patient checklist. Reply with A/B/C.")
    out_lines.append("")
    out_lines.append("—")
    out_lines.append("*All phrasing is grounded in GSK-approved internal references and sales modules uploaded for this brand.*")

    ai_text = "\n".join(out_lines)
    audio_b64 = generate_audio_base64(ai_text)
    assistant_entry = {"role":"assistant", "text": ai_text, "audio_b64": audio_b64}
    st.session_state["chat_history"].append(assistant_entry)

    # if follow_up requested, add clarifying Qs as a separate assistant message
    if follow_up:
        follow = []
        follow.append("Quick clarifying questions to help me improve:")
        if context_previous:
            prev_short = re.split(r'(?<=[\.!\?])\s+', context_previous.strip())
            ctx = prev_short[0] if prev_short else context_previous.strip()
            follow.append(f"- About the previous suggestion: \"{ctx[:140]}...\" — which part felt off? (unclear / not practical / too technical / other)")
        follow.append("- Choose: (A) unclear, (B) not enough practical steps, (C) too technical, (D) other")
        follow.append("- Preferred output: (1) Short script, (2) Data bullets, (3) Conversational examples")
        follow_text = "\n".join(follow)
        audio_b64_f = generate_audio_base64(follow_text)
        st.session_state["chat_history"].append({"role":"assistant", "text": follow_text, "audio_b64": audio_b64_f})

# -------------------------
# UI: Medical & Sales bubbles (collapsible)
# -------------------------
with st.expander("📚 Medical References Summary (brand-specific)", expanded=True):
    md = st.session_state["medical_summary"].get(brand, "")
    if md:
        st.markdown(f"<div class='section-bubble'>{md}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='section-bubble'>No medical references found for this brand.</div>", unsafe_allow_html=True)

with st.expander("💼 Sales Module Summary (brand-specific)", expanded=True):
    sd = st.session_state["sales_summary"].get(brand, "")
    if sd:
        st.markdown(f"<div class='section-bubble'>{sd}</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='section-bubble'>No sales module content found for this brand.</div>", unsafe_allow_html=True)

# -------------------------
# PDF Upload & Summary bubble
# -------------------------
with st.expander("📄 Upload PDF / TXT (brand-specific) & Summary", expanded=False):
    uploaded_file = st.file_uploader("Upload PDF or TXT for quick summarization", type=["pdf","txt"])
    if uploaded_file:
        try:
            if hasattr(uploaded_file, "type") and uploaded_file.type == "application/pdf" and PdfReader:
                reader = PdfReader(uploaded_file)
                pdf_text = "".join([p.extract_text() or "" for p in reader.pages])
            else:
                pdf_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
            st.session_state["pdf_summary"][brand] = model_summarize(pdf_text, bullets=6)
            st.success("Uploaded file summarized and saved for this brand.")
        except Exception:
            st.error("Failed to read uploaded file.")
    if st.session_state["pdf_summary"].get(brand):
        st.markdown(f"<div class='section-bubble'>{st.session_state['pdf_summary'][brand]}</div>", unsafe_allow_html=True)

# -------------------------
# Chat container (display messages)
# -------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for idx, entry in enumerate(st.session_state["chat_history"]):
    role = entry.get("role", "assistant")
    text = entry.get("text", "")
    if role == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑‍💼 {escape(text)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 {escape(text).replace("\\n","<br>")}</div>', unsafe_allow_html=True)
        # audio playback
        if entry.get("audio_b64"):
            try:
                st.audio(io.BytesIO(base64.b64decode(entry["audio_b64"])), format="audio/mp3")
            except Exception:
                pass
        # export buttons (DOCX if available else TXT) and feedback buttons
        col1, col2, col3, col4 = st.columns([1,1,1,4])
        with col1:
            bytes_data, fname = export_call_flow_bytes(text, fmt="docx" if DOCX_AVAILABLE and export_format=="DOCX" else "txt")
            mime = "application/octet-stream" if fname.endswith(".docx") else "text/plain"
            st.download_button("⬇ Export", data=bytes_data, file_name=fname, mime=mime, key=f"export_{idx}")
        with col2:
            # always provide TXT alternative
            txt_bytes, txt_name = export_call_flow_bytes(text, fmt="txt")
            st.download_button("⬇ Export TXT", data=txt_bytes, file_name=txt_name, mime="text/plain", key=f"export_txt_{idx}")
        with col3:
            fb_key = f"fb_{idx}"
            if fb_key not in st.session_state["feedback"]:
                if st.button("👍 Like", key=f"like_{idx}"):
                    st.session_state["feedback"][fb_key] = "like"
                    # ask for style preference
                    pref_text = "Great — preference? Reply with 1 for short scripts, 2 for data bullets, 3 for conversational examples."
                    st.session_state["chat_history"].append({"role":"assistant","text":pref_text, "audio_b64": generate_audio_base64(pref_text)})
                if st.button("👎 Dislike", key=f"dislike_{idx}"):
                    st.session_state["feedback"][fb_key] = "dislike"
                    # follow up clarifying questions
                    add_ai_response("User disliked previous response — follow up", follow_up=True, context_previous=text)
                if st.button("ℹ️ Need More", key=f"needmore_{idx}"):
                    st.session_state["feedback"][fb_key] = "need_more"
                    add_ai_response("User requested more details — follow up", follow_up=True, context_previous=text)
            else:
                st.markdown(f"Feedback: **{st.session_state['feedback'][fb_key]}**")
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Resizable Prompt Suggestions bubble (visual) + actionable buttons underneath
# -------------------------
suggestions = make_suggestions(brand, persona, barrier, segment, specialty, objective)

# Visual resizable suggestions box (CSS controlled)
st.markdown('<div class="resizable-suggestions">', unsafe_allow_html=True)
st.markdown("<strong>Prompt Suggestions — drag to resize</strong><br><small>Click a suggestion button below to set input and run it.</small>", unsafe_allow_html=True)
pills_html = " ".join([f'<span class="suggestion-pill">{escape(s)}</span>' for s in suggestions])
st.markdown(pills_html, unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Actionable suggestion buttons (Streamlit)
btn_cols = st.columns(min(5, len(suggestions)))
for i, s in enumerate(suggestions):
    if btn_cols[i % len(btn_cols)].button(s, key=f"act_sugg_{i}"):
        st.session_state["main_input"] = s
        # immediately run the suggestion
        st.session_state["chat_history"].append({"role":"user","text": s})
        add_ai_response(s)
        st.experimental_rerun()

# -------------------------
# Input area (fixed bottom)
# -------------------------
st.markdown('<div class="input-area">', unsafe_allow_html=True)
col_text, col_send, col_pref = st.columns([8,1,1])
with col_text:
    # show the main input (populated by suggestion buttons)
    main_text = st.text_area("", value=st.session_state.get("main_input",""), key="main_input_widget", height=84, placeholder="Type message here or click a prompt suggestion...")
with col_send:
    if st.button("Send", key="send_main"):
        if main_text and main_text.strip():
            st.session_state["chat_history"].append({"role":"user", "text": main_text.strip()})
            add_ai_response(main_text.strip(), follow_up=False)
            st.session_state["main_input"] = ""
            st.experimental_rerun()
with col_pref:
    if st.button("Clear", key="clear_main"):
        st.session_state["main_input"] = ""
        st.experimental_rerun()
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Bottom expanding accordions with Summaries for reference (collapsible)
# -------------------------
with st.expander("Show references used (medical summary)", expanded=False):
    st.markdown(st.session_state["medical_summary"].get(brand, "No medical summary available."))

with st.expander("Show sales module summary", expanded=False):
    st.markdown(st.session_state["sales_summary"].get(brand, "No sales summary available."))

with st.expander("Uploaded PDF summary (brand-specific)", expanded=False):
    st.markdown(st.session_state["pdf_summary"].get(brand, ""))

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown("""
<div class="fixed-disclaimer">
⚠️ Internal tool — outputs are grounded in GSK-approved internal references and sales modules uploaded in the repo. Verify clinical information before external use.
</div>
""", unsafe_allow_html=True)
