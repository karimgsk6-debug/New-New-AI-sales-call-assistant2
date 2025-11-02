# app.py - AI Sales Call Assistant (FINAL with structural sales-call flows + polished UI)
import streamlit as st
import os, re, io, tempfile, base64
from datetime import datetime
from html import escape
import requests

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
# GROQ placeholder - replace to enable LLM responses
# -------------------------
GROQ_API_KEY = "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"
GROQ_API_URL = "https://api.groq.ai/v1/llm"

# -------------------------
# Session defaults
# -------------------------
defaults = {
    "chat_history": [],
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.62,
    "search_mode": "deep",
    "language": "English",
    "reply_style": "balanced",
    "pdf_docs": {},
    "pdf_summaries": {},
    "followup_options": {},
    "feedback_stats": {"like":0,"dislike":0,"need_more":0},
    "groq_unavailable": False
}
for k,v in defaults.items():
    st.session_state.setdefault(k, v)
for nk in ("medical_summary","sales_summary","pdf_summary","feedback"):
    st.session_state.setdefault(nk, {})

# -------------------------
# Brand configuration
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
# CSS - orange linear gradient + UI polish + merged input
# -------------------------
st.markdown("""
<style>
/* Background */
[data-testid="stAppViewContainer"] {
  background: linear-gradient(135deg, #ff8c00, #ffcc70);
  background-attachment: fixed;
}

/* Header */
.header {
  display:flex; align-items:center; justify-content:space-between; gap:12px;
  padding:10px 18px; border-radius:10px; margin-bottom:8px;
  background: rgba(255,255,255,0.92);
  box-shadow: 0 6px 18px rgba(0,0,0,0.06);
}
.header .title { text-align:center; flex:1; }
.header img.left-logo { height:56px; border-radius:8px; }
.header .ai-logo {
  width:80px; height:80px; border-radius:50%; object-fit:cover; box-shadow:0 6px 18px rgba(0,0,0,0.12);
}

/* summary bubble */
.section-bubble {
  background: rgba(255,255,255,0.98);
  border-radius:10px; padding:12px; margin-bottom:10px;
  box-shadow: 0 6px 18px rgba(11,22,55,0.06);
  color:#111;
}

/* Chat container */
.chat-container {
  max-height:56vh; overflow-y:auto; padding:12px;
  background: rgba(255,255,255,0.95); border-radius:8px; margin-bottom:12px;
}
.chat-bubble-user {
  background: linear-gradient(90deg,#0078D7,#0066C8); color:white; padding:12px;
  border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto;
  box-shadow:0 2px 6px rgba(0,0,0,0.08);
}
.chat-bubble-ai {
  background: linear-gradient(90deg,#fff8e6,#fff3d9); color:#111; padding:12px;
  border-radius:12px; margin:8px 0; max-width:78%;
  box-shadow:0 2px 6px rgba(0,0,0,0.04);
}

/* feedback row */
.feedback-row { display:flex; gap:8px; margin-top:8px; align-items:center; }
.feedback-btn { background:#fff; border:1px solid #e6e9ee; padding:6px 10px; border-radius:8px; cursor:pointer; }

/* Prompt suggestions (inline pills) */
.suggestion-pill { display:inline-block; padding:6px 12px; border-radius:20px; background:#fff3e0; margin:4px; border:1px solid #ffd59a; font-size:14px; cursor:pointer; }

/* Combined merged input bubble */
.input-row {
  display:flex; gap:8px; align-items:stretch;
  background:#fff; padding:8px; border-radius:12px; border:1px solid #e6e6e6;
  box-shadow:0 6px 18px rgba(0,0,0,0.06);
}
.input-textarea {
  flex:1; border:none; resize:none; outline:none; font-size:14px; padding:8px;
}
.send-btn {
  background:#ff8c00; color:#fff; border:none; padding:10px 12px; border-radius:10px; cursor:pointer;
  display:flex; align-items:center; justify-content:center; gap:8px; min-width:56px;
}
.send-btn:active { transform:translateY(1px); }

/* Fixed resizable footer bubble */
.footer-fixed {
  position: fixed; left:20px; right:20px; bottom:18px; z-index:9999;
  display:flex; justify-content:space-between; gap:12px; align-items:flex-end;
  pointer-events:none; /* child handles events */
}
.footer-bubble {
  pointer-events:auto;
  margin:0 auto; width:100%; max-width:1100px;
  background: rgba(255,255,255,0.98); border-radius:12px; padding:10px;
  box-shadow:0 12px 40px rgba(0,0,0,0.08); resize:vertical; overflow:auto; min-height:56px; max-height:220px;
  border:1px solid #e6e1d7;
}

/* small bottom-right fixed text (write-right course) */
.small-bottom-right {
  position: fixed; right:36px; bottom:28px; z-index:10001; font-size:12px; color:#333;
  background: rgba(255,255,255,0.95); padding:6px 10px; border-radius:8px; border:1px solid #eee;
  box-shadow:0 6px 18px rgba(0,0,0,0.06);
}

/* Sidebar metrics */
.sidebar-metric { background: rgba(255,255,255,0.95); padding:10px; border-radius:8px; margin-bottom:8px; text-align:center; }

/* remove stray paddings */
.block-container .element-container { padding-top: 0rem; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Helper functions (file read, summarise, local search, audio, export)
# -------------------------
def read_file_text_from_uploaded(uploaded_file):
    try:
        if hasattr(uploaded_file, "type") and "pdf" in (uploaded_file.type or "") and PdfReader:
            reader = PdfReader(uploaded_file)
            return "".join([p.extract_text() or "" for p in reader.pages])
        elif hasattr(uploaded_file, "type") and uploaded_file.type == "text/plain":
            return uploaded_file.getvalue().decode("utf-8", errors="ignore")
        elif hasattr(uploaded_file, "type") and uploaded_file.type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"] and DOCX_AVAILABLE:
            doc = Document(uploaded_file)
            return "\n".join([p.text for p in doc.paragraphs])
        else:
            return ""
    except Exception:
        return ""

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

def generate_audio_base64(text: str) -> str:
    if not text or not gTTS:
        return ""
    tts_text = re.sub(r'\n\s*\n', ' ... ', text).replace("\n", " ")
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
# GROQ safe query with graceful fallback
# -------------------------
def query_groq_safe(prompt: str, context_docs: list, max_tokens: int = 600):
    if not GROQ_API_KEY or GROQ_API_KEY == "Add_GROQ_API_here":
        st.session_state["groq_unavailable"] = True
        return None
    context_text = "\n\n".join([d for d in context_docs if d])
    payload = {
        "prompt": f"Use the following reference material to answer the user question concisely. Only provide the assistant response — do not paste references.\n\nReferences:\n{context_text}\n\nUser question: {prompt}",
        "max_output_tokens": max_tokens
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    try:
        r = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=12)
        r.raise_for_status()
        resp = r.json()
        out = resp.get("output_text") or resp.get("result") or resp.get("text") or None
        if not out:
            out = str(resp)
        st.session_state["groq_unavailable"] = False
        return out
    except Exception as e:
        print("GROQ call failed:", e)
        st.session_state["groq_unavailable"] = True
        return None

# -------------------------
# Structured Sales Call generator (defined early to avoid NameError)
# -------------------------
def pick_top_insights(query_terms, chunks, metas, top_n=3):
    if not chunks:
        return []
    matches = []
    for i, c in enumerate(chunks):
        if any(term.lower() in c.lower() for term in query_terms):
            matches.append((c, metas[i]))
    if not matches:
        for i, c in enumerate(chunks):
            if any(word.lower() in c.lower() for word in query_terms):
                matches.append((c, metas[i]))
    seen = set()
    bullets = []
    for text, meta in matches:
        short = re.split(r'(?<=[\.!\?])\s+', text.strip())[0][:220]
        if short not in seen:
            seen.add(short)
            bullets.append(short)
        if len(bullets) >= top_n:
            break
    return bullets

def generate_structured_sales_call(brand, persona, specialty, objective, local_docs, chunks, metas):
    brand_name = brand_data.get(brand, {}).get("display", brand)
    persona_label = persona or "Target persona"
    specialty_label = specialty or "Generalist"

    uploaded_summary = st.session_state.get("pdf_summaries", {}).get(brand, "")
    repo_med = st.session_state.get("medical_summary", {}).get(brand, "")
    repo_sales = st.session_state.get("sales_summary", {}).get(brand, "")

    insights = []
    if uploaded_summary:
        insights = [line.strip("- ").strip() for line in uploaded_summary.splitlines() if line.strip()]
    elif repo_med:
        insights = [line.strip("- ").strip() for line in repo_med.splitlines() if line.strip()]

    if len(insights) < 3 and chunks:
        extra = pick_top_insights([brand_name, persona_label, specialty_label, objective], chunks, metas, top_n=5)
        insights.extend(extra)
    final_insights = []
    for s in insights:
        if s and s not in final_insights:
            final_insights.append(s)
        if len(final_insights) >= 6:
            break

    patient_types = "Adults ≥50 years old" if brand.lower() == "shingrix" else "Appropriate patient population per label"

    evidence = []
    if repo_med:
        evidence = [l.strip("- ").strip() for l in repo_med.splitlines() if l.strip()][:3]
    if not evidence and uploaded_summary:
        evidence = [l.strip("- ").strip() for l in uploaded_summary.splitlines() if l.strip()][:3]
    if not evidence and chunks:
        evidence = pick_top_insights([brand_name, "efficacy", "safety", "trial"], chunks, metas, top_n=3)

    objections = pick_top_insights(["efficacy", "safety", "cost", "reimbursement", "side effects"], chunks, metas, top_n=3)
    if not objections:
        objections = [
            "I understand the concern about efficacy — present trial evidence and recommended guidance.",
            "Safety profile is strong; direct HCP resources are available.",
            "We can discuss access and reimbursement pathways."
        ]

    lines = []
    lines.append(f"Assistant: Here's a tailored sales call flow for the **{brand_name}**, targeting an **{persona_label}** persona, specifically a **{specialty_label}**:\n")
    lines.append("**Prepare:**\n")
    lines.append(f"1. Identify the persona: {persona_label} ({specialty_label})")
    lines.append(f"2. Objectives: {objective} — awareness/adoption of {brand_name} and its benefits")
    lines.append(f"3. Patient types: {patient_types}")
    lines.append("4. Key insights:")
    if final_insights:
        for it in final_insights[:6]:
            lines.append(f"    - {it}")
    else:
        lines.append("    - No uploaded references found. Upload PDFs for tailored insights.")
    lines.append("")

    lines.append("**Engage:**\n")
    lines.append('1. Start conversation: "Hello, Dr. [Last Name]. I\'m [Your Name] from GSK. How are you today?"')
    if brand.lower() == "shingrix":
        lines.append('2. Capture attention: "I\'d like to discuss a topic that\'s relevant to your patients: shingles prevention. Are you familiar with the risks and consequences of shingles in adults ≥50 years old?"')
    else:
        lines.append('2. Capture attention: "I\'d like to discuss a treatment option that may benefit some of your patients. Are you familiar with the latest evidence?"')
    lines.append(f'3. Set discussion context: "As a {specialty_label}, you likely see patients who are at risk — I\'d like to share information about {brand_name}."')
    lines.append("")

    lines.append("**Create Opportunities:**\n")
    lines.append('1. Identify gaps or unmet needs: "What are your current strategies for addressing this condition in your patients?"')
    if evidence:
        ev_short = evidence[0]
        lines.append(f'2. Introduce solutions with clinical/product data: "{brand_name} — {ev_short}."')
    else:
        lines.append(f'2. Introduce solutions with clinical/product data: "{brand_name} — provide product benefits and guideline recommendations."')
    lines.append('3. Highlight key benefits: "By recommending {brand}, you can help prevent complications and improve patient outcomes."'.format(brand=brand_name))
    lines.append("")

    lines.append("**Influence:**\n")
    if evidence:
        lines.append(f'1. Present evidence: "{evidence[0]}"')
    else:
        lines.append("1. Present evidence: Refer to internal clinical summaries and trials.")
    lines.append("2. Handle objections:")
    for ob in objections[:3]:
        lines.append(f'    - "{ob}"')
    lines.append('3. Highlight value and outcomes: "Preventing the condition improves quality of life and reduces downstream care burden."')
    lines.append("")

    lines.append("**Impact GSO:**\n")
    lines.append('1. Link discussion to incremental steps: "What steps can we take together to increase vaccination/treatment rates in your practice?"')
    lines.append('2. Clarify next steps: "I can provide additional resources and follow up in the next few weeks. Would you like me to follow up?"')
    lines.append("")

    lines.append("**Post-Call Analysis:**\n")
    lines.append("1. Record insights: Document objections, interest level, and follow-up actions.")
    lines.append("2. Update CRM: Log call details and next steps.")
    lines.append("3. Evaluate metrics: Track adoption rates and plan improvements.")

    return "\n".join(lines)

# -------------------------
# Sidebar (logos, filters, dashboard, uploads)
# -------------------------
with st.sidebar:
    st.markdown("<div style='display:flex;justify-content:center;align-items:center;'>", unsafe_allow_html=True)
    st.markdown("<img src='https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/845b8f1ae98e46440e840c0a906f3610dd343c9a/.devcontainer/GSK1-logo.png' style='height:64px'>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("Brand & Filters")
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state["selected_brand"]), format_func=lambda k: brand_data[k]["display"])
    st.session_state["selected_brand"] = sel_brand
    bconf = brand_data[sel_brand]
    persona = st.selectbox("HCP Persona", bconf.get("personas", []))
    segment = st.selectbox("Segment", bconf.get("segments", []))
    barrier = st.multiselect("Doctor Barrier", bconf.get("barriers", []))
    specialty = st.selectbox("Specialty", bconf.get("specialties", []))
    objective = st.selectbox("Objective", ["Awareness", "Adoption", "Retention"])

    st.markdown("---")
    st.subheader("📊 Dashboard")
    st.markdown(f"<div class='sidebar-metric'><b>Calls</b><br>{len([m for m in st.session_state['chat_history'] if m.get('role')=='assistant'])}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sidebar-metric'><b>Uploaded docs</b><br>{len(st.session_state['pdf_docs'])}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sidebar-metric'><b>Likes</b><br>{st.session_state['feedback_stats']['like']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sidebar-metric'><b>Dislikes</b><br>{st.session_state['feedback_stats']['dislike']}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='sidebar-metric'><b>Regens</b><br>{st.session_state['feedback_stats']['need_more']}</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Upload (brand)")
    with st.expander("Upload PDF / TXT / DOCX (sidebar)"):
        uploaded_side = st.file_uploader("Upload file for brand context", type=["pdf","txt","docx"], key="sidebar_upload")
        if uploaded_side:
            text = read_file_text_from_uploaded(uploaded_side)
            if text:
                st.session_state["pdf_docs"].setdefault(sel_brand, "")
                st.session_state["pdf_docs"][sel_brand] += "\n\n" + text
                st.session_state["pdf_summaries"][sel_brand] = model_summarize(st.session_state["pdf_docs"][sel_brand], bullets=6)
                st.success("Sidebar file added and summarized.")
                st.rerun()
            else:
                st.error("Could not read file.")

    st.markdown("---")
    st.subheader("Export / Reset")
    export_format = st.selectbox("Export format", ["DOCX" if DOCX_AVAILABLE else "TXT", "TXT"])
    if st.button("🗑️ Clear chat"):
        st.session_state["chat_history"] = []
        st.session_state["followup_options"] = {}
        st.session_state["feedback_stats"] = {"like":0,"dislike":0,"need_more":0}
        st.rerun()

# -------------------------
# Header (main) with enlarged circular AI logo
# -------------------------
st.markdown("""
<div class="header">
  <div style="width:140px;"><img src="https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/845b8f1ae98e46440e840c0a906f3610dd343c9a/.devcontainer/GSK1-logo.png" class="left-logo"></div>
  <div class="title"><h2 style="margin:0">AI Sales Call Assistant</h2><div style="color:#555;font-size:13px;">APACT-guided — structured call flows</div></div>
  <div style="width:100px;text-align:right;"><img src="https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/845b8f1ae98e46440e840c0a906f3610dd343c9a/.devcontainer/AURA1.png" class="ai-logo"></div>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Main upload area & summaries (collapsible)
# -------------------------
st.subheader("Upload reference document (main)")
uploaded_file_main = st.file_uploader("Upload PDF / TXT / DOCX (main) — added to brand context", type=["pdf","txt","docx"], key="main_upload")
if uploaded_file_main:
    content = read_file_text_from_uploaded(uploaded_file_main)
    if content:
        st.session_state["pdf_docs"].setdefault(st.session_state["selected_brand"], "")
        st.session_state["pdf_docs"][st.session_state["selected_brand"]] += "\n\n" + content
        st.session_state["pdf_summaries"][st.session_state["selected_brand"]] = model_summarize(st.session_state["pdf_docs"][st.session_state["selected_brand"]], bullets=6)
        st.success("Uploaded and summarized for brand.")
        st.rerun()

# -------------------------
# Build local context + chunks
# -------------------------
brand = st.session_state["selected_brand"]
refs_folder = brand_data[brand]["references_path"]
sales_folder = brand_data[brand]["sales_path"]

local_docs = []
if os.path.exists(refs_folder):
    for f in sorted(os.listdir(refs_folder)):
        if f.lower().endswith((".pdf", ".txt")):
            local_docs.append(read_file_text(os.path.join(refs_folder, f)))
if os.path.exists(sales_folder):
    for f in sorted(os.listdir(sales_folder)):
        if f.lower().endswith((".pdf", ".txt")):
            local_docs.append(read_file_text(os.path.join(sales_folder, f)))
if brand in st.session_state["pdf_docs"]:
    local_docs.append(st.session_state["pdf_docs"][brand])

chunks, metas = build_corpus_for_folders([p for p in (refs_folder, sales_folder) if os.path.exists(p)], chunk_size_sentences=3)

# -------------------------
# Summaries as bullets inside collapsible bubbles
# -------------------------
med_summary = st.session_state["medical_summary"].get(brand, "")
if not med_summary:
    combined = "\n".join([d for d in local_docs]) if local_docs else ""
    med_summary = model_summarize(combined, bullets=6) if combined else ""
    st.session_state["medical_summary"][brand] = med_summary

sales_summary = st.session_state["sales_summary"].get(brand, "")
if not sales_summary:
    combined_sales = "\n".join([d for d in local_docs]) if local_docs else ""
    sales_summary = model_summarize(combined_sales, bullets=6) if combined_sales else ""
    st.session_state["sales_summary"][brand] = sales_summary

with st.expander("📚 Medical Summary (bulleted)", expanded=False):
    st.markdown(f'<div class="section-bubble">{med_summary if med_summary else "- No medical references found."}</div>', unsafe_allow_html=True)

with st.expander("💼 Sales Module Summary (bulleted)", expanded=False):
    st.markdown(f'<div class="section-bubble">{sales_summary if sales_summary else "- No sales module content found."}</div>', unsafe_allow_html=True)

# Non-blocking GROQ notice
if st.session_state.get("groq_unavailable"):
    st.warning("⚠️ LLM (GROQ) not reachable or API key not set — running in offline fallback mode.", icon="⚠️")

# -------------------------
# Prompt suggestions (collapsible) - no empty bubble below it
# -------------------------
def make_suggestions(brand_key, persona_val, barriers_list, segment_val, specialty_val, objective_val):
    s=[]
    s.append("Generate sales call")
    s.append(f"Generate call flow for {persona_val} focusing on {objective_val}")
    if barriers_list:
        s.append(f"Handle objection: {', '.join(barriers_list[:2])}")
    s.append(f"Quick adoption message for {brand_data[brand_key]['display']} to a {specialty_val}")
    s.append("Short role-play example (rep <> HCP)")
    return s

suggestions = make_suggestions(brand, persona, barrier, segment, specialty, objective)
with st.expander("💡 Prompt Suggestions (click to expand)", expanded=False):
    st.markdown("<div style='margin-bottom:8px;color:#333;'>Click a suggestion to auto-send it.</div>", unsafe_allow_html=True)
    # Render pills as buttons (no empty box)
    for i, s in enumerate(suggestions):
        if st.button(s, key=f"suggbtn_{i}"):
            # trigger generation
            if "sales call" in s.lower() or s.lower().startswith("generate sales call") or s.lower().startswith("generate call flow"):
                st.session_state["chat_history"].append({"role":"user","text":s})
                ai_text = generate_structured_sales_call(brand=brand, persona=persona, specialty=specialty, objective=objective, local_docs=local_docs, chunks=chunks, metas=metas)
                audio_b64 = generate_audio_base64(ai_text)
                st.session_state["chat_history"].append({"role":"assistant","text":ai_text,"audio_b64":audio_b64})
                st.rerun()
            else:
                st.session_state["chat_history"].append({"role":"user","text":s})
                ai_resp = query_groq_safe(s, local_docs)
                if ai_resp:
                    audio_b64 = generate_audio_base64(ai_resp)
                    st.session_state["chat_history"].append({"role":"assistant","text":ai_resp,"audio_b64":audio_b64})
                else:
                    snippets = local_search_snippets(s, chunks, metas, top_n=5)
                    if snippets:
                        ai_text = "**Summary from references:**\n" + "\n".join([f"- {sn['text'][:200]}..." for sn in snippets])
                    else:
                        ai_text = "I couldn't find direct references locally. Please refine the prompt or upload relevant docs."
                    audio_b64 = generate_audio_base64(ai_text)
                    st.session_state["chat_history"].append({"role":"assistant","text":ai_text,"audio_b64":audio_b64})
                st.rerun()

# -------------------------
# Chat container display (no stray white bubble above)
# -------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for idx, entry in enumerate(st.session_state["chat_history"]):
    role = entry.get("role","assistant")
    text = entry.get("text","")
    if role == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑‍💼 {escape(text)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 {escape(text).replace("\\n","<br>")}</div>', unsafe_allow_html=True)
        if entry.get("audio_b64"):
            try:
                st.audio(io.BytesIO(base64.b64decode(entry["audio_b64"])), format="audio/mp3")
            except Exception:
                pass

        # feedback row (interactive)
        followup_key = f"followup_{idx}"
        st.markdown('<div class="feedback-row">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1,1,1,6])
        with c1:
            if st.button("👍 Like", key=f"like_{idx}"):
                st.session_state["feedback_stats"]["like"] += 1
                pref_text = "Thanks! Quick preference: 1) Short scripts, 2) Data bullets, 3) Role-plays — reply 1/2/3."
                st.session_state["chat_history"].append({"role":"assistant","text":pref_text,"audio_b64":generate_audio_base64(pref_text)})
                st.rerun()
        with c2:
            if st.button("👎 Dislike", key=f"dislike_{idx}"):
                st.session_state["feedback_stats"]["dislike"] += 1
                if not st.session_state.get("groq_unavailable") and GROQ_API_KEY and GROQ_API_KEY != "Add_GROQ_API_here":
                    fu_prompt = f"Generate 3 very short closed follow-up questions (each 5-10 words) to clarify or improve this assistant response:\n\n\"{text}\"\n\nReturn them as separate lines."
                    fu_resp = query_groq_safe(fu_prompt, local_docs, max_tokens=120)
                    opts = [line.strip() for line in re.split(r'[\r\n]+', fu_resp)] if fu_resp else []
                    opts = [o for o in opts if o][:3]
                    if not opts:
                        opts = ["Make it shorter", "Focus on objections", "Add data points"]
                else:
                    opts = ["Make it shorter & punchy", "Focus on objections handling", "Add more persuasive language"]
                st.session_state["followup_options"][followup_key] = opts
                st.rerun()
        with c3:
            if st.button("🔄 Regenerate", key=f"reg_{idx}"):
                st.session_state["feedback_stats"]["need_more"] += 1
                context_docs = local_docs.copy()
                regen_prompt = f"Regenerate and expand this assistant answer for clarity and practical steps:\n\nOriginal answer:\n{text}"
                ai_out = query_groq_safe(regen_prompt, context_docs)
                if ai_out:
                    audio_b64 = generate_audio_base64(ai_out)
                    st.session_state["chat_history"].append({"role":"assistant","text":ai_out,"audio_b64":audio_b64})
                else:
                    new_text = text + "\n\n[Regenerated: more actionable steps would be added here.]"
                    st.session_state["chat_history"].append({"role":"assistant","text":new_text,"audio_b64":generate_audio_base64(new_text)})
                st.rerun()
        with c4:
            fb_val = st.session_state.get("feedback", {}).get(f"fb_{idx}", "")
            if fb_val:
                st.markdown(f"**Feedback:** {fb_val}")
        st.markdown('</div>', unsafe_allow_html=True)

        # follow-up options if exist
        if st.session_state.get("followup_options", {}).get(followup_key):
            st.markdown("💡 **Refine this answer — choose one:**")
            fopts = st.session_state["followup_options"][followup_key]
            fcols = st.columns(len(fopts))
            for i, opt in enumerate(fopts):
                if fcols[i].button(opt, key=f"{followup_key}_opt_{i}"):
                    st.session_state["feedback_stats"]["need_more"] += 1
                    guided_prompt = f"User requested: '{opt}'. Regenerate and adapt the previous assistant answer to address that. Original answer:\n\n{text}"
                    ai_out = query_groq_safe(guided_prompt, local_docs)
                    if ai_out:
                        audio_b64 = generate_audio_base64(ai_out)
                        st.session_state["chat_history"].append({"role":"assistant","text":ai_out,"audio_b64":audio_b64})
                    else:
                        new_text = text + f"\n\n[Regenerated to address: {opt}]"
                        st.session_state["chat_history"].append({"role":"assistant","text":new_text,"audio_b64":generate_audio_base64(new_text)})
                    st.session_state["followup_options"].pop(followup_key, None)
                    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Merged input (textarea + send button) positioned above footer bubble
# -------------------------
st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)  # slight spacer
st.markdown('<div style="display:flex; justify-content:center;">', unsafe_allow_html=True)
st.markdown('<div style="width:100%; max-width:1100px;">', unsafe_allow_html=True)

# Render merged input
st.markdown('<div class="input-row">', unsafe_allow_html=True)
main_text = st.text_area("", value=st.session_state.get("main_input",""), key="main_input_widget", height=96, placeholder="Type your message or click a suggestion...", label_visibility="collapsed")
# Put send button to the right
col1, col2 = st.columns([8,1])
with col2:
    send_clicked = st.button("Send ➤", key="send_main", help="Send message")
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# When Send clicked: treat input and triggers
if send_clicked:
    if main_text and main_text.strip():
        st.session_state["chat_history"].append({"role":"user","text":main_text.strip()})
        trigger_phrases = ["generate sales call", "generate call flow", "sales call", "call flow"]
        lower = main_text.lower()
        if any(tp in lower for tp in trigger_phrases):
            ai_text = generate_structured_sales_call(brand=brand, persona=persona, specialty=specialty, objective=objective, local_docs=local_docs, chunks=chunks, metas=metas)
            audio_b64 = generate_audio_base64(ai_text)
            st.session_state["chat_history"].append({"role":"assistant","text":ai_text,"audio_b64":audio_b64})
            st.session_state["main_input"] = ""
            st.rerun()
        else:
            ai_out = query_groq_safe(main_text.strip(), local_docs)
            if ai_out:
                audio_b64 = generate_audio_base64(ai_out)
                st.session_state["chat_history"].append({"role":"assistant","text":ai_out,"audio_b64":audio_b64})
            else:
                snippets = local_search_snippets(main_text.strip(), chunks, metas, top_n=5)
                if snippets:
                    ai_text = "**Relevant excerpts:**\n" + "\n".join([f"- {s['text'][:220]}..." for s in snippets])
                else:
                    ai_text = "I couldn't find direct references locally. Please upload relevant documents or rephrase the question."
                audio_b64 = generate_audio_base64(ai_text)
                st.session_state["chat_history"].append({"role":"assistant","text":ai_text,"audio_b64":audio_b64})
            st.session_state["main_input"] = ""
            st.rerun()

# -------------------------
# Fixed resizable footer bubble (contains nothing but provides background for input)
# and bottom-right small text moved per request
# -------------------------
st.markdown(f"""
<div class="footer-fixed" aria-hidden="false">
  <div class="footer-bubble" role="region" aria-label="Footer Bubble (resizable)">
    <!-- intentionally blank container to provide resizable footer bubble and avoid white line -->
    <div style="opacity:0.6; font-size:12px;">Footer (resizable bubble). Use the top input bubble to send messages. This footer is resizable.</div>
  </div>
</div>
""", unsafe_allow_html=True)

# small bottom-right fixed text
st.markdown('<div class="small-bottom-right">Please refer to Write Right Principles course: BUS-LGL-WRJA-001</div>', unsafe_allow_html=True)

# -------------------------
# Small footer note (non-fixed)
# -------------------------
st.markdown('<div style="text-align:center; margin-top:8px; font-size:12px; color:#111;">⚠️ Internal tool — outputs are grounded in uploaded and repository references. Verify clinical/compliance before external use.</div>', unsafe_allow_html=True)
