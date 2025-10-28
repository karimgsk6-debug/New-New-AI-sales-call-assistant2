# app.py - AI Sales Call Assistant (Final merged + visual enhancements)
import streamlit as st
import os, re, io, tempfile, base64
from datetime import datetime
from html import escape

# Optional libraries (best-effort)
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
# Page config & assets
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# -------------------------
# GROQ placeholder (backend; not shown in UI)
# -------------------------
GROQ_API_KEY = "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"

# -------------------------
# Session defaults
# -------------------------
defaults = {
    "chat_history": [],  # list of dicts: {"role":"user"/"assistant", "text":..., "audio_b64":...}
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.7,
    "search_mode": "deep",
    "language": "English",
    "reply_style": "balanced",  # balanced, short_script, data, conversational
    "awaiting_style_pref": False,
    "call_count": 0,
    "export_count": 0,
    "feedback_stats": {"like": 0, "dislike": 0, "need_more": 0},
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# nested dicts for brand summaries
for name in ("medical_summary", "sales_summary", "pdf_summary"):
    if name not in st.session_state or not isinstance(st.session_state[name], dict):
        st.session_state[name] = {}

# -------------------------
# Brand config
# -------------------------
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas": ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
        "specialties": ["GP","Dermatologist","Geriatrician"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/",
        "call_flow": ["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Post-call Analysis"]
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas": ["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties": ["Oncologist","Medical Oncologist"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli/",
        "call_flow": ["COCO","Anchor","Engage","Close"]
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness","Diagnosis","Adoption","Adherence"],
        "personas": ["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers": ["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties": ["GP","Pulmonologist","Respiratory Specialist"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy/",
        "call_flow": ["Prepare","Engage","Demonstrate","Address Access","Close"]
    }
}

# -------------------------
# CSS (dark blurred orange gradient + UI polish)
# -------------------------
st.markdown(f"""
<style>
/* Blurred orange gradient background **/
[data-testid="stAppViewContainer"] {{
  background: linear-gradient(120deg, rgba(240,140,0,0.12), rgba(240,85,0,0.12)), url('{REPO_RAW_BASE}/background1.png');
  background-size: cover;
  background-position: center;
  backdrop-filter: blur(8px);
}}

/* Header */
.header {{
  display:flex; align-items:center; justify-content:space-between;
  padding:10px 16px; border-radius:10px;
  background: linear-gradient(90deg, rgba(0,0,0,0.55), rgba(0,0,0,0.35));
  color: #fff;
  margin-bottom:12px;
}}
.header .title {{
  text-align:center; flex:1; margin-left:8px; margin-right:8px;
}}
.header img.left-logo {{ height:56px; }}
.header img.right-logo {{ height:56px; }}

/* Summary & sections */
.section-bubble {{
  background: rgba(255,255,255,0.06);
  border-radius: 10px;
  padding:12px;
  margin-bottom:10px;
  color: #ffff;
}}

/* Chat */
.chat-container {{
  max-height:56vh;
  overflow-y:auto;
  padding:12px;
  background: rgba(0,0,0,0.45);
  border-radius:8px;
  margin-bottom:200px;
  color: #fff;
}}
.chat-bubble-user {{
  background: linear-gradient(90deg,#0078D7,#0066C8);
  color:white;
  padding:12px;
  border-radius:12px;
  margin:8px 0;
  max-width:78%;
  margin-left:auto;
}}
.chat-bubble-ai {{
  background: linear-gradient(90deg,#fff5eb, #fff1e6);
  color:#1b1b1b;
  padding:12px;
  border-radius:12px;
  margin:8px 0;
  max-width:78%;
}}

/* Feedback row under assistant msg */
.feedback-row {{
  display:flex; gap:8px; margin-top:8px; align-items:center;
}}
.feedback-btn {{
  background: rgba(255,255,255,0.08);
  color: #fff;
  padding:6px 10px;
  border-radius:8px;
  border: none;
  cursor: pointer;
}}

/* bottom combined fixed */
.combined-fixed {{
  position: fixed; left:20px; right:20px; bottom:18px; z-index:9999;
  background: rgba(0,0,0,0.6);
  padding:12px; border-radius:10px;
  box-shadow: 0 12px 40px rgba(0,0,0,0.45);
}}
.resizable-combined {{
  resize: vertical; overflow: auto; border:1px solid rgba(255,255,255,0.06);
  padding:10px; border-radius:8px; background: rgba(255,255,255,0.02);
  min-height:120px; max-height:420px;
}}

/* suggestion pills */
.suggestion-pill {{
  display:inline-block; padding:6px 12px; border-radius:20px; background: rgba(255,255,255,0.04);
  margin:4px; border:1px solid rgba(255,255,255,0.03); color:#fff;
}}

/* mini-dashboard */
.mini-dashboard {{
  display:flex; gap:18px; justify-content:center; margin-bottom:10px; color: #ff;
}}
.mini-dashboard div {{
  background: rgba(255,255,255,0.05);
  padding:10px 14px; border-radius:10px; text-align:center;
}}

/* footer disclaimer */
.fixed-disclaimer {{
  position: fixed; left:0; right:0; bottom:0; background: rgba(0,0,0,0.7);
  padding:10px; color:#fff; text-align:center; z-index:9997;
}}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Helper functions
# -------------------------
def read_file_text(path):
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

def simple_summary(text, bullets=6):
    if not text:
        return ""
    sents = re.split(r'(?<=[\.!\?])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join([f"- {s}" for s in selected])

def model_summarize(text, bullets=6):
    # Placeholder for a real LLM summarization; currently returns simple summary
    if not text:
        return ""
    # Build a more structured summary with bold titles
    bullets_text = simple_summary(text, bullets)
    if not bullets_text:
        return ""
    # Assemble with bold headings
    parts = [
        "**Key Findings**",
        bullets_text,
        "**Clinical Insights**",
        "- Review the most clinically relevant points above.",
        "**Action Points**",
        "- Use the above lines as short scripts or data bullets in the call."
    ]
    return "\n\n".join(parts)

def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas = [], []
    for folder in folders:
        if not folder or not os.path.exists(folder): continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf", ".txt"))]
        for fname in files:
            p = os.path.join(folder, fname)
            text = read_file_text(p)
            if not text: continue
            sents = re.split(r'(?<=[\.!\?])\s+', text)
            for i in range(0, max(1, len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename": fname, "folder": folder, "start": i})
    return chunks, metas

def local_search_snippets(query, chunks, metas, top_n=5):
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
                if sims[idx] <= 0: continue
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

def generate_audio_base64(text):
    if not text or not gTTS:
        return ""
    # Add gentle pauses between sections
    tts_text = re.sub(r'\n\s*\n', ' ... ', text)
    tts_text = tts_text.replace("\n", " ")
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        gTTS(text=tts_text, lang="en", slow=False).save(tmp.name)
        with open(tmp.name, "rb") as fh:
            return base64.b64encode(fh.read()).decode("utf-8")
    except Exception:
        return ""

def export_call_flow_bytes(text, fmt="docx"):
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
# Sidebar (filters, upload, export, clear)
# -------------------------
with st.sidebar:
    st.image(GSK_LOGO_RAW, width=150)
    st.markdown("")  # spacer
    st.subheader("Options")
    brand_keys = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_keys, index=brand_keys.index(st.session_state["selected_brand"]), format_func=lambda k: brand_data[k]["display"])
    st.session_state["selected_brand"] = sel_brand
    bconf = brand_data[sel_brand]

    persona = st.selectbox("HCP Persona", bconf.get("personas", []))
    segment = st.selectbox("Segment", bconf.get("segments", []))
    barrier = st.multiselect("Doctor Barrier", bconf.get("barriers", []))
    specialty = st.selectbox("Specialty", bconf.get("specialties", []))
    objective = st.selectbox("Objective", ["Awareness", "Adoption", "Retention"])
    st.session_state["temperature"] = st.slider("Temperature", 0.0, 1.0, st.session_state["temperature"], 0.05)
    st.session_state["search_mode"] = st.selectbox("Search mode", ["deep", "shallow"])
    st.session_state["language"] = st.radio("Language", ["English", "Arabic"])

    st.markdown("---")
    st.subheader("Export")
    export_format = st.selectbox("Export format", ["DOCX" if DOCX_AVAILABLE else "TXT", "TXT"])
    if st.button("Export latest assistant answer"):
        # find last assistant message
        last = None
        for e in reversed(st.session_state["chat_history"]):
            if e.get("role") == "assistant":
                last = e.get("text", "")
                break
        if last:
            bts, fname = export_call_flow_bytes(last, fmt="docx" if export_format == "DOCX" and DOCX_AVAILABLE else "txt")
            st.download_button("Download export", data=bts, file_name=fname)
            st.session_state["export_count"] += 1
        else:
            st.warning("No assistant content to export.")

    st.markdown("---")
    with st.expander("Upload PDF/TXT (brand-specific)", expanded=False):
        uploaded_file = st.file_uploader("Upload a PDF or TXT", type=["pdf", "txt"], key="sidebar_upload")
        if uploaded_file:
            try:
                if hasattr(uploaded_file, "type") and uploaded_file.type == "application/pdf" and PdfReader:
                    reader = PdfReader(uploaded_file)
                    pdf_text = "".join([p.extract_text() or "" for p in reader.pages])
                else:
                    pdf_text = uploaded_file.getvalue().decode("utf-8", errors="ignore")
                # store summary per brand
                st.session_state["pdf_summary"][sel_brand] = model_summarize(pdf_text, bullets=6)
                st.success("Uploaded file summarized and stored for this brand.")
            except Exception:
                st.error("Failed to read the uploaded file.")

    st.markdown("---")
    if st.button("🗑️ Clear Chat (all)"):
        st.session_state["chat_history"] = []
        st.session_state["feedback"] = {}
        st.experimental_rerun()

# -------------------------
# Header + mini-dashboard
# -------------------------
st.markdown(f"""
<div class="header">
  <div style="width:140px;"><img src="{GSK_LOGO_RAW}" class="left-logo" alt="GSK logo"></div>
  <div class="title"><h2 style="margin:0; color:#fff">AI Sales Call Assistant</h2><div style="color:#ffd9b3;font-size:13px;">APACT-guided — grounded in GSK-approved materials • {brand_data[st.session_state['selected_brand']]['display']}</div></div>
  <div style="width:140px;text-align:right;"><img src="{AI_LOGO_RAW}" class="right-logo" alt="AI logo"></div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="mini-dashboard">
  <div><b>📞 Calls:</b><br>{st.session_state.get('call_count',0)}</div>
  <div><b>📤 Exports:</b><br>{st.session_state.get('export_count',0)}</div>
  <div><b>⭐ Feedback:</b><br>👍 {st.session_state['feedback_stats'].get('like',0)} | ℹ️ {st.session_state['feedback_stats'].get('need_more',0)} | 👎 {st.session_state['feedback_stats'].get('dislike',0)}</div>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Load brand summaries & corpus (brand-specific)
# -------------------------
brand = st.session_state["selected_brand"]
refs_folder = brand_data[brand]["references_path"]
sales_folder = brand_data[brand]["sales_path"]

# Medical summary (only if not already computed)
if brand not in st.session_state["medical_summary"]:
    combined_refs = ""
    if os.path.exists(refs_folder):
        for f in sorted(os.listdir(refs_folder)):
            if f.lower().endswith((".pdf", ".txt")):
                combined_refs += read_file_text(os.path.join(refs_folder, f)) + "\n"
    st.session_state["medical_summary"][brand] = model_summarize(combined_refs, bullets=6) if combined_refs.strip() else ""

# Sales module summary
if brand not in st.session_state["sales_summary"]:
    combined_sales = ""
    if os.path.exists(sales_folder):
        for f in sorted(os.listdir(sales_folder)):
            if f.lower().endswith((".pdf", ".txt")):
                combined_sales += read_file_text(os.path.join(sales_folder, f)) + "\n"
    st.session_state["sales_summary"][brand] = model_summarize(combined_sales, bullets=6) if combined_sales.strip() else ""

# build corpus for search
corpus_folders = [p for p in (refs_folder, sales_folder) if os.path.exists(p)]
chunks, metas = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# Prompt suggestions generator
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
# APACT response builder + interactive feedback
# -------------------------
def add_ai_response(prompt, follow_up=False, context_previous=None):
    snippets = local_search_snippets(prompt, chunks, metas, top_n=6)
    out_lines = []
    opener = "Thanks — I hear you. Let’s tackle this together." if not follow_up else "Thanks for the feedback — I want to make this more useful."
    out_lines.append(f"**{opener}**\n")

    # Opening lines
    out_lines.append("**Opening lines you can use:**")
    out_lines.append("- 'I appreciate you bringing this up — it's an important point that often affects patient decisions.'")
    out_lines.append("- 'That's a fair question. Let me walk you through what we've seen in practice.'")
    out_lines.append("")

    if not follow_up:
        out_lines.append("**🟢 Acknowledge**")
        out_lines.append("- I understand the concern and why it matters for patient care and workflow.")
        out_lines.append("")
        out_lines.append("**🔵 Probe — sample questions**")
        out_lines.append("- Open: 'Can you tell me more about which patients you're most worried about?'")
        out_lines.append("- Closed: 'Is your main worry safety, efficacy, or reimbursement? (reply safety/efficacy/reimbursement)'")
        out_lines.append("- Diagnostic: 'How many eligible patients do you see per week?'")
        out_lines.append("")
        out_lines.append("**🟣 Actions — practical steps (APACT)**")
        reply_style = st.session_state.get("reply_style", "balanced")
        for step in brand_data[brand]["call_flow"]:
            out_lines.append(f"**{step}**")
            relevant = []
            for s in snippets:
                text = s.get("text", "")
                if step.lower() in text.lower() or any(word.lower() in text.lower() for word in [persona.lower(), specialty.lower(), objective.lower()]):
                    relevant.append((s["score"], text))
            relevant.sort(key=lambda x: x[0], reverse=True)
            if relevant:
                for rscore, rtext in relevant[:2]:
                    short = re.split(r'(?<=[\.!\?])\s+', rtext.strip())[0][:220]
                    if reply_style == "short_script":
                        out_lines.append(f"- Quick line: \"{short}.\" (15s)")
                    elif reply_style == "data":
                        out_lines.append(f"- Data point: {short} — follow with 'In our materials...'")
                    elif reply_style == "conversational":
                        out_lines.append(f"- Role-play: Rep: \"{short}.\" HCP: \"[response]\"")
                    else:
                        out_lines.append(f"- {short} — Example phrasing: \"{short}...\"")
            else:
                out_lines.append("- Refer to the sales module for step-specific phrasing.")
            out_lines.append("")
        out_lines.append("**🟠 Confirm**")
        out_lines.append("- Does this direction address the HCP's main barrier? (Yes / No)")
        out_lines.append("")
        out_lines.append("**🟡 Transition**")
        out_lines.append("- If yes, I can prepare a short script, role-play examples or a one-page checklist — tell me which.")
        out_lines.append("")
        out_lines.append("*Grounded in internal GSK-approved medical references & sales modules.*")
    else:
        out_lines.append("**Follow-up — tell me more so I can improve**")
        if context_previous:
            prev_short = re.split(r'(?<=[\.!\?])\s+', context_previous.strip())
            prev_snippet = prev_short[0] if prev_short else context_previous.strip()
            out_lines.append(f"- About previous: \"{prev_snippet[:140]}...\" — which part felt off? (unclear / not practical / too technical / other)")
        out_lines.append("- Quick choices: (A) unclear, (B) not enough practical steps, (C) too technical, (D) other")
        out_lines.append("- Preferred output: (1) Short script, (2) Data bullets, (3) Conversational examples")
        out_lines.append("- Example: reply '2' to add study numbers, '3' for role-play examples.")

    ai_text = "\n".join(out_lines)
    audio_b64 = generate_audio_base64(ai_text)
    st.session_state["chat_history"].append({"role": "assistant", "text": ai_text, "audio_b64": audio_b64})
    st.session_state["call_count"] = st.session_state.get("call_count", 0) + 1

    if follow_up:
        follow_text = "Please choose: (A) unclear, (B) not practical, (C) too technical, (D) other — or reply 1/2/3 for output style."
        st.session_state["chat_history"].append({"role": "assistant", "text": follow_text, "audio_b64": generate_audio_base64(follow_text)})

# -------------------------
# Show medical & sales summaries
# -------------------------
with st.expander("📚 Medical References Summary", expanded=True):
    md = st.session_state["medical_summary"].get(brand, "")
    if md:
        st.markdown(f'<div class="section-bubble">{md.replace("\\n","<br>")}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="section-bubble">No medical references found for this brand.</div>', unsafe_allow_html=True)

with st.expander("💼 Sales Module Summary", expanded=True):
    sd = st.session_state["sales_summary"].get(brand, "")
    if sd:
        st.markdown(f'<div class="section-bubble">{sd.replace("\\n","<br>")}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="section-bubble">No sales module content found for this brand.</div>', unsafe_allow_html=True)

# -------------------------
# Chat display
# -------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for idx, entry in enumerate(st.session_state["chat_history"]):
    role = entry.get("role", "assistant")
    text = entry.get("text", "")
    if role == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑‍💼 {escape(text)}</div>', unsafe_allow_html=True)
    else:
        # assistant bubble (render newlines)
        st.markdown(f'<div class="chat-bubble-ai">🤖 {escape(text).replace("\\n","<br>")}</div>', unsafe_allow_html=True)
        # audio playback
        if entry.get("audio_b64"):
            try:
                st.audio(io.BytesIO(base64.b64decode(entry["audio_b64"])), format="audio/mp3")
            except Exception:
                pass
        # feedback row (inline)
        fb_key = f"fb_{idx}"
        st.markdown('<div class="feedback-row">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1,1,1,6])
        with c1:
            if st.button("👍 Like", key=f"like_{idx}"):
                st.session_state["feedback_stats"]["like"] += 1
                # quick preference prompt
                pref_text = "Great — preference? Reply with 1 for short scripts, 2 for data bullets, 3 for conversational examples."
                st.session_state["chat_history"].append({"role":"assistant","text":pref_text,"audio_b64":generate_audio_base64(pref_text)})
                try:
                    st.experimental_rerun()
                except Exception:
                    pass
        with c2:
            if st.button("👎 Dislike", key=f"dislike_{idx}"):
                st.session_state["feedback_stats"]["dislike"] += 1
                # follow-up clarifying question
                add_ai_response("User disliked previous response — follow up", follow_up=True, context_previous=text)
                try:
                    st.experimental_rerun()
                except Exception:
                    pass
        with c3:
            if st.button("ℹ️ Need More", key=f"needmore_{idx}"):
                st.session_state["feedback_stats"]["need_more"] += 1
                add_ai_response("User requested more detail — follow up", follow_up=True, context_previous=text)
                try:
                    st.experimental_rerun()
                except Exception:
                    pass
        with c4:
            fb_val = st.session_state.get("feedback", {}).get(fb_key, "")
            if fb_val:
                st.markdown(f"**Feedback:** {fb_val}")
        st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Combined bottom area: suggestions + input (resizable)
# -------------------------
suggestions = make_suggestions(brand, persona, barrier, segment, specialty, objective)

st.markdown('<div class="combined-fixed">', unsafe_allow_html=True)
st.markdown('<div class="resizable-combined">', unsafe_allow_html=True)

with st.expander("💡 Prompt Suggestions (click to expand)", expanded=False):
    st.markdown("<div style='margin-bottom:8px;color:#ffff;'>Click a suggestion to populate & send.</div>", unsafe_allow_html=True)
    # show pills
    pills_html = " ".join([f'<span class="suggestion-pill">{escape(s)}</span>' for s in suggestions])
    st.markdown(pills_html, unsafe_allow_html=True)
    # actionable suggestion buttons (outside form)
    btn_cols = st.columns(min(4, len(suggestions)))
    for i, s in enumerate(suggestions):
        if btn_cols[i % len(btn_cols)].button(s, key=f"suggbtn_{i}"):
            st.session_state["main_input"] = s
            st.session_state["chat_history"].append({"role":"user","text":s})
            add_ai_response(s)
            try:
                st.experimental_rerun()
            except Exception:
                pass

# text input and send
main_text = st.text_area("Type your message or click suggestion", value=st.session_state.get("main_input",""), key="main_input_widget", height=96)
c_send, c_clear, c_style = st.columns([1,1,1])
with c_send:
    if st.button("Send", key="send_main"):
        if main_text and main_text.strip():
            st.session_state["chat_history"].append({"role":"user", "text": main_text.strip()})
            add_ai_response(main_text.strip())
            st.session_state["main_input"] = ""
            try:
                st.experimental_rerun()
            except Exception:
                pass
with c_clear:
    if st.button("Clear input", key="clear_main_btn"):
        st.session_state["main_input"] = ""
        try:
            st.experimental_rerun()
        except Exception:
            pass
with c_style:
    if st.button("Set reply style", key="set_reply_style"):
        st.session_state["awaiting_style_pref"] = True
        prompt = "Which reply style do you prefer? Reply 1 for short scripts, 2 for data bullets, 3 for conversational examples."
        st.session_state["chat_history"].append({"role":"assistant","text":prompt,"audio_b64":generate_audio_base64(prompt)})
        try:
            st.experimental_rerun()
        except Exception:
            pass

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# If user provided preference while awaiting, capture it
if st.session_state.get("awaiting_style_pref"):
    last_user = ""
    for e in reversed(st.session_state["chat_history"]):
        if e.get("role") == "user":
            last_user = e.get("text","").lower()
            break
    if last_user:
        if "1" in last_user or "short" in last_user:
            st.session_state["reply_style"] = "short_script"
            st.session_state["awaiting_style_pref"] = False
            ack = "Got it — I'll favor short scripts going forward."
            st.session_state["chat_history"].append({"role":"assistant","text":ack,"audio_b64":generate_audio_base64(ack)})
            try:
                st.experimental_rerun()
            except Exception:
                pass
        elif "2" in last_user or "data" in last_user:
            st.session_state["reply_style"] = "data"
            st.session_state["awaiting_style_pref"] = False
            ack = "Got it — I'll prioritize data-backed bullets going forward."
            st.session_state["chat_history"].append({"role":"assistant","text":ack,"audio_b64":generate_audio_base64(ack)})
            try:
                st.experimental_rerun()
            except Exception:
                pass
        elif "3" in last_user or "convers" in last_user:
            st.session_state["reply_style"] = "conversational"
            st.session_state["awaiting_style_pref"] = False
            ack = "Great — I'll include more conversational examples and role-plays."
            st.session_state["chat_history"].append({"role":"assistant","text":ack,"audio_b64":generate_audio_base64(ack)})
            try:
                st.experimental_rerun()
            except Exception:
                pass

# Footer disclaimer
# -------------------------
st.markdown(f"""
<div class="fixed-disclaimer">
⚠️ Internal tool — outputs are grounded in GSK-approved internal references and sales modules stored in the repository. Verify clinical information and compliance before external use.
</div>
""", unsafe_allow_html=True)
