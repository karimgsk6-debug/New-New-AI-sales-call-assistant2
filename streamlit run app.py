# app.py - AI Sales Call Assistant (final merged)
import streamlit as st
import os, re, io, tempfile, base64
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
# GROQ Placeholder (backend variable)
# -------------------------
GROQ_API_KEY = "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"
# client = None  # reserved for GROQ initialization later

# -------------------------
# Defensive session_state initialization
# -------------------------
defaults = {
    "chat_history": [],  # list of {"role":"user"/"assistant", "text":..., "audio_b64":...}
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
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "specialties": ["GP", "Dermatologist", "Geriatrician"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/",
        "call_flow": ["Prepare", "Engage", "Create Opportunities", "Influence", "Impact GSO", "Post-call Analysis"]
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited eligibility", "Access/reimbursement issues"],
        "specialties": ["Oncologist", "Medical Oncologist"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli/",
        "call_flow": ["COCO", "Anchor", "Engage", "Close"]
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Side effect concerns", "Cost/coverage"],
        "specialties": ["GP", "Pulmonologist", "Respiratory Specialist"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy/",
        "call_flow": ["Prepare", "Engage", "Demonstrate", "Address Access", "Close"]
    }
}

# -------------------------
# CSS (includes resizable combined field)
# -------------------------
st.markdown("""
<style>
/* Title */
.title-box { background: rgba(255,255,255,0.96); padding:14px; border-radius:10px; margin-bottom:12px; text-align:center; box-shadow:0 3px 8px rgba(0,0,0,0.05); }

/* Sections */
.section-bubble { background:#fbfcfe; border:1px solid #e8eef6; padding:12px; border-radius:10px; margin-bottom:10px; }
.chat-container { max-height:56vh; overflow-y:auto; padding:12px; background: rgba(255,255,255,0.96); border-radius:8px; margin-bottom:160px; }
.chat-bubble-user { background:#0078D7; color:white; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto; }
.chat-bubble-ai { background:#eef9ff; color:#000; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }

/* Bottom fixed combined box */
.combined-fixed { position: fixed; left:20px; right:20px; bottom:18px; z-index:9999; background: rgba(255,255,255,0.98); padding:12px; border-radius:10px; box-shadow: 0 8px 30px rgba(0,0,0,0.06); }
.resizable-combined { resize: vertical; overflow: auto; border:1px solid #ddd; padding:10px; border-radius:8px; background:#fff; min-height:96px; max-height:360px; }
.suggestion-pill { display:inline-block; padding:6px 10px; border-radius:18px; background:#f6f8fa; margin:4px; border:1px solid #e6e9ee; cursor:default; }
.input-row { display:flex; gap:8px; margin-top:8px; align-items:flex-end; }
.send-button { background:#FF6F00; color:white; padding:8px 14px; border-radius:8px; border:none; font-weight:600; cursor:pointer; }

/* Footer */
.fixed-disclaimer { position: fixed; left:0; right:0; bottom:0; background: rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }
.citation-note { font-size:13px; color:#333; background:#fbfbff; padding:8px; border-left:4px solid #0078D7; border-radius:6px; margin-top:8px; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Helper functions: file read, summary, search, tts, export
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

def simple_summary(text: str, bullets: int = 6) -> str:
    if not text:
        return ""
    sents = re.split(r'(?<=[\.!\?])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join([f"- {s}" for s in selected])

def model_summarize(text: str, bullets: int = 6) -> str:
    # Placeholder: use GROQ if available; otherwise simple summary
    if not text:
        return ""
    # If a client/GROQ were available, you'd call it here.
    return simple_summary(text, bullets)

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
    """Use gTTS by default; return base64 mp3 or empty string if failed."""
    if not text or not gTTS:
        return ""
    # Add gentle spoken pauses for APACT sections
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
# Sidebar controls
# -------------------------
st.sidebar.title("Filters & Options")
brand_options = list(brand_data.keys())
sel_brand = st.sidebar.selectbox("Brand", brand_options, index=brand_options.index(st.session_state["selected_brand"]),
                                format_func=lambda k: brand_data[k]["display"])
st.session_state["selected_brand"] = sel_brand
bconf = brand_data[sel_brand]
persona = st.sidebar.selectbox("HCP Persona", bconf.get("personas", []))
segment = st.sidebar.selectbox("Segment", bconf.get("segments", []))
barrier = st.sidebar.multiselect("Doctor Barrier", bconf.get("barriers", []))
specialty = st.sidebar.selectbox("Specialty", bconf.get("specialties", []))
objective = st.sidebar.selectbox("Objective", ["Awareness", "Adoption", "Retention"])
st.session_state["temperature"] = st.sidebar.slider("Temperature", 0.0, 1.0, st.session_state["temperature"], 0.05)
st.session_state["search_mode"] = st.sidebar.selectbox("Search mode", ["deep", "shallow"])
st.session_state["language"] = st.sidebar.radio("Language", ["English", "Arabic"])
if st.sidebar.button("🗑️ Clear Chat"):
    st.session_state["chat_history"] = []
with st.sidebar.expander("Add External Reference URLs (one per line)", expanded=False):
    _ = st.text_area("Enter URLs (one per line)")

with st.sidebar.expander("Export Options", expanded=False):
    export_format = st.radio("Default export format", ["DOCX", "TXT"], index=0 if DOCX_AVAILABLE else 1)

# -------------------------
# Title
# -------------------------
st.markdown(f'<div class="title-box"><h2>💡 AI Sales Call Assistant — {brand_data[sel_brand]["display"]}</h2><div style="color:#666;font-size:14px;">APACT-guided responses grounded in approved brand documents</div></div>', unsafe_allow_html=True)

# -------------------------
# Build per-brand summaries & corpus (only when needed)
# -------------------------
brand = st.session_state["selected_brand"]
refs_folder = brand_data[brand]["references_path"]
sales_folder = brand_data[brand]["sales_path"]

# medical summary per brand (cached in session)
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

# build corpus
corpus_folders = [p for p in (refs_folder, sales_folder) if os.path.exists(p)]
chunks, metas = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

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
# APACT response builder + interactive feedback
# -------------------------
def add_ai_response(prompt: str, follow_up: bool = False, context_previous: str = None):
    """
    Create an APACT-structured response grounded in brand docs.
    If follow_up=True produce clarifying questions.
    """
    snippets = local_search_snippets(prompt, chunks, metas, top_n=6)
    out_lines = []
    opener = "Thanks — I hear you. Let’s tackle this together." if not follow_up else "Thanks — I want to refine this for you."
    out_lines.append(f"*{opener}*")
    out_lines.append("")

    # Opening lines
    out_lines.append("**Opening lines you can use**")
    out_lines.append("- 'I appreciate you bringing this up — it's an important point that often affects patient decisions.'")
    out_lines.append("- 'That's a fair question. Let me walk you through what we've seen in practice.'")
    out_lines.append("")

    if not follow_up:
        # Acknowledge
        out_lines.append("**🟢 Acknowledge**")
        out_lines.append("- I understand the concern and why it matters for patient care and workflow.")
        out_lines.append("")

        # Probe
        out_lines.append("**🔵 Probe — sample questions**")
        out_lines.append("- Open: 'Can you tell me more about which patients you're most worried about?'")
        out_lines.append("- Closed: 'Is your main worry safety, efficacy, or reimbursement? (Reply safety/efficacy/reimbursement)'")
        out_lines.append("- Diagnostic: 'How many eligible patients do you see per week?'")
        out_lines.append("")

        # Actions
        out_lines.append("**🟣 Actions — practical steps (APACT) based on sales module**")
        reply_style = st.session_state.get("reply_style", "balanced")
        for step in brand_data[brand]["call_flow"]:
            out_lines.append(f"**{step}**")
            # pick relevant snippets
            relevant = []
            for s in snippets:
                t = s.get("text", "")
                if step.lower() in t.lower() or any(word.lower() in t.lower() for word in [persona.lower(), specialty.lower(), objective.lower()]):
                    relevant.append((s["score"], t))
            relevant.sort(key=lambda x: x[0], reverse=True)
            if relevant:
                for rscore, rtext in relevant[:2]:
                    short = re.split(r'(?<=[\.!\?])\s+', rtext.strip())[0][:220]
                    if reply_style == "short_script":
                        out_lines.append(f"- Quick line: \"{short}.\" (15s)")
                    elif reply_style == "data":
                        out_lines.append(f"- Data point: {short} — follow with 'In internal materials...'")
                    elif reply_style == "conversational":
                        out_lines.append(f"- Role-play: Rep: \"{short}.\" HCP: \"[response]\"")
                    else:
                        out_lines.append(f"- {short} — Example phrasing: \"{short}...\"")
            else:
                out_lines.append("- Refer to the sales module guidance for tailored phrasing.")
            out_lines.append("")
        # Confirm & Transition
        out_lines.append("**🟠 Confirm**")
        out_lines.append("- Does this direction address the HCP's main barrier in your next visit? (Yes / No)")
        out_lines.append("")
        out_lines.append("**🟡 Transition**")
        out_lines.append("- If yes, I can prepare A) Short script, B) Role-play examples, or C) One-page checklist. Reply with A/B/C.")
        out_lines.append("")
        out_lines.append("*Grounded in internal GSK-approved medical references & sales modules.*")
    else:
        # follow-up clarifying questions
        out_lines.append("**Follow-up — tell me more so I can improve**")
        if context_previous:
            prev_short = re.split(r'(?<=[\.!\?])\s+', context_previous.strip())
            prev_snippet = prev_short[0] if prev_short else context_previous.strip()
            out_lines.append(f"- About previous: \"{prev_snippet[:140]}...\" — which part felt off? (unclear / not practical / too technical / other)")
        out_lines.append("- Quick choices: (A) unclear, (B) not enough practical steps, (C) too technical, (D) other")
        out_lines.append("- Preferred output: (1) Short script, (2) Data-backed bullets, (3) Conversational examples")
        out_lines.append("- Example: reply '2' to add study numbers, '3' for role-play examples.")

    ai_text = "\n".join(out_lines)
    audio_b64 = generate_audio_base64(ai_text)
    assistant_entry = {"role": "assistant", "text": ai_text, "audio_b64": audio_b64}
    st.session_state["chat_history"].append(assistant_entry)

    # If follow_up, add clarifying prompt message as separate assistant message for interactivity
    if follow_up:
        follow_lines = ["Please choose one: (A) unclear, (B) not practical, (C) too technical, (D) other. Or reply with preferred output: 1/2/3."]
        follow_text = "\n".join(follow_lines)
        st.session_state["chat_history"].append({"role": "assistant", "text": follow_text, "audio_b64": generate_audio_base64(follow_text)})

# -------------------------
# UI: Summaries (collapsible)
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

# PDF upload & summarise
with st.expander("📄 Upload a PDF / TXT (brand-specific) and summarize", expanded=False):
    uploaded_file = st.file_uploader("Upload PDF or TXT", type=["pdf", "txt"])
    if uploaded_file:
        try:
            if hasattr(uploaded_file, "type") and uploaded_file.type == "application/pdf" and PdfReader:
                reader = PdfReader(uploaded_file)
                pdf_text = "".join([p.extract_text() or "" for p in reader.pages])
            else:
                pdf_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
            st.session_state["pdf_summary"][brand] = model_summarize(pdf_text, bullets=6)
            st.success("Uploaded file summarized and stored for this brand.")
        except Exception:
            st.error("Failed to read the uploaded file.")
    if st.session_state["pdf_summary"].get(brand):
        st.markdown(f"<div class='section-bubble'>{st.session_state['pdf_summary'][brand]}</div>", unsafe_allow_html=True)

# -------------------------
# Chat history display
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
        # export and feedback buttons
        c1, c2, c3, c4 = st.columns([1,1,1,4])
        with c1:
            bytes_data, fname = export_call_flow_bytes(text, fmt="docx" if (DOCX_AVAILABLE and export_format == "DOCX") else "txt")
            mime = "application/octet-stream" if fname.endswith(".docx") else "text/plain"
            st.download_button("⬇ Export", data=bytes_data, file_name=fname, mime=mime, key=f"export_{idx}")
        with c2:
            txt_bytes, txt_name = export_call_flow_bytes(text, fmt="txt")
            st.download_button("⬇ Export TXT", data=txt_bytes, file_name=txt_name, mime="text/plain", key=f"export_txt_{idx}")
        with c3:
            fb_key = f"fb_{idx}"
            if fb_key not in st.session_state["feedback"]:
                if st.button("👍 Like", key=f"like_{idx}"):
                    st.session_state["feedback"][fb_key] = "like"
                    pref = "Great — preference? Reply 1 for short scripts, 2 for data bullets, 3 for conversational examples."
                    st.session_state["chat_history"].append({"role": "assistant", "text": pref, "audio_b64": generate_audio_base64(pref)})
                if st.button("👎 Dislike", key=f"dislike_{idx}"):
                    st.session_state["feedback"][fb_key] = "dislike"
                    # ask follow up
                    add_ai_response("User disliked previous response — follow up", follow_up=True, context_previous=text)
                    # re-render
                    st.experimental_rerun = getattr(st, "experimental_rerun", None)
                    # call st.rerun once triggered by button; avoid unconditional call
                    try:
                        st.rerun()
                    except Exception:
                        pass
                if st.button("ℹ️ Need More", key=f"needmore_{idx}"):
                    st.session_state["feedback"][fb_key] = "need_more"
                    add_ai_response("User requested more detail — follow up", follow_up=True, context_previous=text)
                    try:
                        st.rerun()
                    except Exception:
                        pass
            else:
                st.markdown(f"Feedback: **{st.session_state['feedback'][fb_key]}**")
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Combined resizable bottom box (suggestions + input) - fixed
# -------------------------
suggestions = make_suggestions(brand, persona, barrier, segment, specialty, objective)

st.markdown('<div class="combined-fixed">', unsafe_allow_html=True)
st.markdown('<div class="resizable-combined">', unsafe_allow_html=True)

# Collapsible suggestions inside combined box
with st.expander("💡 Prompt Suggestions (click to expand)", expanded=False):
    st.markdown("<div style='margin-bottom:8px;'>Click a suggestion to populate the input and run it.</div>", unsafe_allow_html=True)
    # show pills visually
    pills_html = " ".join([f'<span class="suggestion-pill">{escape(s)}</span>' for s in suggestions])
    st.markdown(pills_html, unsafe_allow_html=True)
    # actionable buttons
    cols = st.columns(min(4, max(1, len(suggestions))))
    for i, s in enumerate(suggestions):
        if cols[i % len(cols)].button(s, key=f"sugg_btn_{i}"):
            # set main_input and run
            st.session_state["main_input"] = s
            st.session_state["chat_history"].append({"role": "user", "text": s})
            add_ai_response(s)
            try:
                st.rerun()
            except Exception:
                pass

st.markdown("<hr style='margin:10px 0'>", unsafe_allow_html=True)

# Input area inside combined box
main_text = st.text_area("Type your message here (or click a suggestion)", value=st.session_state.get("main_input", ""), key="main_input_widget", height=96)
# action row
a1, a2, a3 = st.columns([1,1,1])
with a1:
    if st.button("Send", key="combined_send"):
        if main_text and main_text.strip():
            st.session_state["chat_history"].append({"role": "user", "text": main_text.strip()})
            add_ai_response(main_text.strip(), follow_up=False)
            st.session_state["main_input"] = ""
            try:
                st.rerun()
            except Exception:
                pass
with a2:
    if st.button("Clear", key="combined_clear"):
        st.session_state["main_input"] = ""
        # clear input widget by rerunning
        try:
            st.rerun()
        except Exception:
            pass
with a3:
    if st.button("Set Reply Style (1-short,2-data,3-convers)", key="set_style"):
        # ask user to reply 1/2/3 in the chat — set awaiting flag
        st.session_state["awaiting_style_pref"] = True
        prompt = "Which reply style do you prefer? Reply with 1 for short scripts, 2 for data bullets, 3 for conversational examples."
        st.session_state["chat_history"].append({"role": "assistant", "text": prompt, "audio_b64": generate_audio_base64(prompt)})
        try:
            st.rerun()
        except Exception:
            pass

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# If user replied while awaiting style preference, capture it
if st.session_state.get("awaiting_style_pref"):
    # look at last user message if exists
    last_user = None
    for e in reversed(st.session_state["chat_history"]):
        if e.get("role") == "user":
            last_user = e.get("text", "").lower()
            break
    if last_user:
        if "1" in last_user or "short" in last_user:
            st.session_state["reply_style"] = "short_script"
            st.session_state["awaiting_style_pref"] = False
            ack = "Got it — I'll favor short scripts going forward."
            st.session_state["chat_history"].append({"role": "assistant", "text": ack, "audio_b64": generate_audio_base64(ack)})
            try:
                st.rerun()
            except Exception:
                pass
        elif "2" in last_user or "data" in last_user:
            st.session_state["reply_style"] = "data"
            st.session_state["awaiting_style_pref"] = False
            ack = "Got it — I'll prioritize data-backed bullets going forward."
            st.session_state["chat_history"].append({"role": "assistant", "text": ack, "audio_b64": generate_audio_base64(ack)})
            try:
                st.rerun()
            except Exception:
                pass
        elif "3" in last_user or "convers" in last_user:
            st.session_state["reply_style"] = "conversational"
            st.session_state["awaiting_style_pref"] = False
            ack = "Great — I'll include more conversational examples and role-plays."
            st.session_state["chat_history"].append({"role": "assistant", "text": ack, "audio_b64": generate_audio_base64(ack)})
            try:
                st.rerun()
            except Exception:
                pass

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown("""
<div class="fixed-disclaimer">
⚠️ Internal tool — outputs are grounded in GSK-approved internal references and sales modules stored in the repository. Verify clinical info before external use.
</div>
""", unsafe_allow_html=True)
