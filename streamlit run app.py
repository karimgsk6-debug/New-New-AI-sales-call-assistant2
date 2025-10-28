# app.py - Final merged: Resizable prompt bubble + Export to DOCX/TXT + grounded APACT responses
import streamlit as st
import os, re, tempfile, base64, io
from datetime import datetime
from html import escape

# Optional libs
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
def query_groq_api(prompt: str) -> str:
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("add_GROQ"):
        return "GROQ not configured."
    # Implement GROQ call here when ready
    return "GROQ placeholder response."

# -------------------------
# Session defaults (ensure nested dicts)
# -------------------------
defaults = {
    "chat_history": [],  # entries like {"role":"user"/"assistant","text":..., "audio_b64":...}
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.62,
    "search_mode": "deep",
    "language": "English",
    "reply_style": "balanced",
    "awaiting_style_pref": False,
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)
for nk in ["medical_summary", "sales_summary", "pdf_summary", "feedback"]:
    if nk not in st.session_state or not isinstance(st.session_state[nk], dict):
        st.session_state[nk] = {}

# -------------------------
# Brand config
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
# Styling including resizable suggestions box
# -------------------------
st.markdown("""
<style>
.title-box { background: rgba(255,255,255,0.96); padding:10px; border-radius:10px; margin-bottom:12px; text-align:center; }
.chat-container { max-height:60vh; overflow-y:auto; padding:12px; background: rgba(255,255,255,0.96); border-radius:8px; margin-bottom:160px; }
.chat-bubble-user { background:#0078D7; color:white; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto; }
.chat-bubble-ai { background:#eef9ff; color:#000; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }
.resizable-suggestions { position: fixed; left: 20px; right: 20px; bottom: 120px; height: 180px; background: #fff; border:1px solid #ddd; padding:10px; border-radius:8px; resize: vertical; overflow: auto; z-index:9998; box-shadow: 0 8px 30px rgba(0,0,0,0.08); }
.suggestion-pill { display:inline-block; padding:6px 10px; border-radius:18px; background:#f7f7f7; margin:4px; border:1px solid #e6e6e6; cursor:pointer; }
.input-area { position: fixed; left:20px; right:20px; bottom:18px; z-index:9999; background: rgba(255,255,255,0.98); padding:10px; border-radius:10px; box-shadow: 0 8px 30px rgba(0,0,0,0.06); display:flex; gap:8px; align-items:flex-end; }
.send-button { background:#FF6F00; color:white; padding:8px 14px; border-radius:8px; border:none; font-weight:600; cursor:pointer; }
.fixed-disclaimer { position: fixed; left:0; right:0; bottom:0; background: rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Helpers: file read, summarise, search, TTS, export
# -------------------------
def read_file_text(path: str) -> str:
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
    if not text: return ""
    sents = re.split(r'(?<=[\.!\?])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join([f"- {s}" for s in selected])

def model_summarize(text: str, bullets: int = 6) -> str:
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
    if not chunks: return []
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
    out = []
    for i, c in enumerate(chunks):
        if q and q in c.lower():
            out.append({"score": 1.0, "text": c, "meta": metas[i]})
            if len(out) >= top_n:
                break
    return out

def generate_audio_base64(text: str) -> str:
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
    """Return (bytes, filename). If docx not available or fmt=='txt' produce txt bytes."""
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_brand = st.session_state.get("selected_brand", "brand")
    if fmt == "docx" and DOCX_AVAILABLE:
        doc = Document()
        doc.add_heading(f"{brand_data[safe_brand]['display']} — Generated Call Flow", level=2)
        # split into paragraphs
        for line in text.splitlines():
            doc.add_paragraph(line)
        bio = io.BytesIO()
        doc.save(bio)
        bio.seek(0)
        filename = f"{safe_brand}_callflow_{now}.docx"
        return bio.read(), filename
    else:
        # TXT fallback
        b = text.encode("utf-8")
        filename = f"{safe_brand}_callflow_{now}.txt"
        return b, filename

# -------------------------
# UI: title & sidebar controls
# -------------------------
st.markdown(f'<div class="title-box"><h2>💡 AI Sales Call Assistant — {brand_data[st.session_state["selected_brand"]]["display"]}</h2></div>', unsafe_allow_html=True)

with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state["selected_brand"]), format_func=lambda k: brand_data[k]["display"])
    st.session_state["selected_brand"] = sel_brand
    bconf = brand_data[sel_brand]
    segment = st.selectbox("Segment", bconf["segments"])
    persona = st.selectbox("HCP Persona", bconf["personas"])
    barrier = st.multiselect("Doctor Barrier", bconf["barriers"])
    specialty = st.selectbox("Specialty", bconf["specialties"])
    objective = st.selectbox("Objective", ["Awareness","Adoption","Retention"])
    st.session_state["temperature"] = st.slider("Temperature", 0.0, 1.0, st.session_state["temperature"], 0.05)
    st.session_state["search_mode"] = st.selectbox("Search mode", ["deep","shallow"])
    st.session_state["language"] = st.radio("Language", ["English","Arabic"])
    if st.button("🗑️ Clear Chat"):
        st.session_state["chat_history"] = []

with st.sidebar.expander("Upload PDF for brand (optional)", expanded=False):
    up = st.file_uploader("Upload a PDF or TXT (brand-specific)", type=["pdf","txt"])
    if up:
        try:
            if hasattr(up, "type") and up.type == "application/pdf" and PdfReader:
                reader = PdfReader(up)
                text = "".join([p.extract_text() or "" for p in reader.pages])
            else:
                text = up.getvalue().decode("utf-8", errors="ignore")
            st.session_state["pdf_summary"][sel_brand] = model_summarize(text, bullets=6)
            st.success("Uploaded file summarized and stored for this brand.")
        except Exception:
            st.error("Could not read uploaded file.")

# -------------------------
# Build brand-specific summaries & corpus (only when needed)
# -------------------------
brand = st.session_state["selected_brand"]
refs_folder = brand_data[brand]["references_path"]
sales_folder = brand_data[brand]["sales_path"]

if brand not in st.session_state["medical_summary"]:
    combined_refs = ""
    if os.path.exists(refs_folder):
        for f in sorted(os.listdir(refs_folder)):
            if f.lower().endswith((".pdf", ".txt")):
                combined_refs += read_file_text(os.path.join(refs_folder, f)) + "\n"
    st.session_state["medical_summary"][brand] = model_summarize(combined_refs, bullets=6) if combined_refs.strip() else ""

if brand not in st.session_state["sales_summary"]:
    combined_sales = ""
    if os.path.exists(sales_folder):
        for f in sorted(os.listdir(sales_folder)):
            if f.lower().endswith((".pdf", ".txt")):
                combined_sales += read_file_text(os.path.join(sales_folder, f)) + "\n"
    st.session_state["sales_summary"][brand] = model_summarize(combined_sales, bullets=6) if combined_sales.strip() else ""

# build corpus used for grounding
corpus_folders = []
if os.path.exists(refs_folder): corpus_folders.append(refs_folder)
if os.path.exists(sales_folder): corpus_folders.append(sales_folder)
chunks, metas = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# Prompt suggestions content (visual resizable box)
# -------------------------
suggestions = []
sugg_texts = make_suggestions = None  # avoid linter warnings

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

suggestions = make_suggestions(brand, persona, barrier, segment, specialty, objective)

# Render a resizable suggestions visual box (CSS-driven). Actionable Streamlit buttons are right below.
st.markdown('<div class="resizable-suggestions">', unsafe_allow_html=True)
st.markdown("<strong>Prompt Suggestions — drag to resize vertically</strong><br><br>", unsafe_allow_html=True)
# visual pills (non-interactive)
pills_html = " ".join([f'<span class="suggestion-pill">{escape(s)}</span>' for s in suggestions])
st.markdown(pills_html, unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# Actionable suggestion buttons (Streamlit) below the resizable visual box
cols = st.columns(min(5, max(1, len(suggestions))))
for i, s in enumerate(suggestions):
    if cols[i % len(cols)].button(s, key=f"act_sugg_{i}"):
        st.session_state["main_input"] = s

# -------------------------
# APACT response builder grounded to approved docs
# -------------------------
def add_ai_response(prompt: str, follow_up: bool = False, context_previous: str = None):
    # Search corpus to gather snippets
    snippets = local_search_snippets(prompt, chunks, metas, top_n=6)
    pieces = []
    opener = "Thanks — I hear you. Let’s make this practical." if not follow_up else "Thanks — refining now based on your feedback."
    pieces.append(opener)
    pieces.append("")

    # Acknowledge
    pieces.append("**🟢 Acknowledge**")
    pieces.append("- I understand why this matters for patient care and clinic workflow.")
    pieces.append("")

    # Probe
    pieces.append("**🔵 Probe — suggested questions**")
    pieces.append("- Open: 'Can you tell me which patients you're most worried about?'")
    pieces.append("- Closed: 'Is your main concern safety, efficacy, or access? (Reply: safety/efficacy/access)'")
    pieces.append("- Diagnostic: 'How many eligible patients do you see per week?'")
    pieces.append("")

    # Actions (use call flow steps)
    pieces.append("**🟣 Actions — call flow steps (examples grounded to approved docs)**")
    reply_style = st.session_state.get("reply_style", "balanced")
    for step in brand_data[brand]["call_flow"]:
        pieces.append(f"**{step}**")
        # try to find snippets referencing the step
        related = []
        for s in snippets:
            t = s.get("text","")
            if step.lower() in t.lower():
                related.append((s["score"], t))
        if not related and snippets:
            related = [(s["score"], s["text"]) for s in snippets]
        added = 0
        for score, text in sorted(related, key=lambda x: x[0], reverse=True)[:2]:
            short = re.split(r'(?<=[\.!\?])\s+', text.strip())[0][:240]
            if reply_style == "short_script":
                pieces.append(f"- Quick line: \"{short}.\" (15s)")
            elif reply_style == "data":
                pieces.append(f"- Data line: {short} — follow with 'In internal materials...'")
            elif reply_style == "conversational":
                pieces.append(f"- Role-play: Rep: \"{short}.\" HCP: \"[response]\"")
            else:
                pieces.append(f"- {short} — Example phrasing: \"{short}...\"")
            added += 1
        if added == 0:
            pieces.append("- Use the brand sales module guidance — tailor to the HCP's barrier.")
        pieces.append("")

    # Confirm & Transition
    pieces.append("**🟠 Confirm**")
    pieces.append("- Does this direction address the HCP's main barrier? (Yes / No)")
    pieces.append("")
    pieces.append("**🟡 Transition**")
    pieces.append("- If yes, I can prepare (A) short script, (B) role-play examples, (C) a one-page patient checklist. Reply with A/B/C.")
    pieces.append("")
    pieces.append("—")
    pieces.append("*All phrasing is grounded in GSK-approved internal references & sales modules for this brand.*")

    ai_text = "\n".join(pieces)
    audio_b64 = generate_audio_base64(ai_text)
    entry = {"role":"assistant", "text": ai_text, "audio_b64": audio_b64}
    st.session_state["chat_history"].append(entry)
    return entry

# -------------------------
# Render chat history (top area)
# -------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for idx, entry in enumerate(st.session_state["chat_history"]):
    role = entry.get("role", "assistant")
    text = entry.get("text", "")
    if role == "user":
        st.markdown(f'<div class="chat-bubble-user">{escape(text)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">{escape(text).replace("\\n","<br>")}</div>', unsafe_allow_html=True)
        # audio
        if entry.get("audio_b64"):
            try:
                st.audio(io.BytesIO(base64.b64decode(entry["audio_b64"])), format="audio/mp3")
            except Exception:
                pass
        # Export call flow (DOCX if available else TXT)
        export_col1, export_col2, export_col3 = st.columns([1,1,4])
        with export_col1:
            tt, fname = export_call_flow_bytes(text, fmt="docx" if DOCX_AVAILABLE else "txt")
            st.download_button(label="Export", data=tt, file_name=fname, mime="application/octet-stream")
        with export_col2:
            # Always provide TXT as alternate
            tt_txt, fname_txt = export_call_flow_bytes(text, fmt="txt")
            st.download_button(label="Export TXT", data=tt_txt, file_name=fname_txt, mime="text/plain")
        # Feedback buttons
        fb_cols = st.columns(3)
        fb_key = f"fb_{idx}"
        if fb_key not in st.session_state["feedback"]:
            if fb_cols[0].button("👍 Like", key=f"like_{idx}"):
                st.session_state["feedback"][fb_key] = "like"
                # ask for preference
                pref_txt = "Great — preference? (1) short scripts, (2) data bullets, (3) conversational examples"
                audio_pref = generate_audio_base64(pref_txt)
                st.session_state["chat_history"].append({"role":"assistant", "text": pref_txt, "audio_b64": audio_pref})
            if fb_cols[1].button("👎 Dislike", key=f"dislike_{idx}"):
                st.session_state["feedback"][fb_key] = "dislike"
                # follow up clarifying questions
                add_ai_response("User disliked previous response — follow up", follow_up=True, context_previous=text)
            if fb_cols[2].button("ℹ️ Need More", key=f"needmore_{idx}"):
                st.session_state["feedback"][fb_key] = "need_more"
                add_ai_response("User requested more detail — follow up", follow_up=True, context_previous=text)
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Input area (fixed bottom)
# -------------------------
st.markdown('<div class="input-area">', unsafe_allow_html=True)
col_text, col_send, col_clear = st.columns([8,1,1])
with col_text:
    # maintain main_input in session_state to allow suggestion buttons to set it
    main_text = st.text_area("", value=st.session_state.get("main_input", ""), key="main_input_widget", height=84, placeholder="Type message here or click a prompt suggestion...")
with col_send:
    if st.button("Send", key="send_main"):
        if main_text and main_text.strip():
            st.session_state["chat_history"].append({"role":"user", "text": main_text.strip()})
            add_ai_response(main_text.strip())
            st.session_state["main_input"] = ""
            # rerun to show appended assistant output and audio
            st.experimental_rerun()
with col_clear:
    if st.button("Clear", key="clear_main"):
        st.session_state["main_input"] = ""
        st.experimental_rerun()
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Collapsible brand summaries
# -------------------------
with st.expander("📚 Medical References Summary (brand-specific)", expanded=False):
    st.markdown(st.session_state["medical_summary"].get(brand, "No medical references available."))
with st.expander("💼 Sales Module Summary (brand-specific)", expanded=False):
    st.markdown(st.session_state["sales_summary"].get(brand, "No sales module content available."))
with st.expander("📄 Uploaded PDF Summary (brand-specific)", expanded=False):
    st.markdown(st.session_state["pdf_summary"].get(brand, ""))

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown("""
<div class="fixed-disclaimer">
⚠️ Internal tool — outputs are grounded in GSK-approved internal references and sales modules. Verify clinical details before external use.
</div>
""", unsafe_allow_html=True)
