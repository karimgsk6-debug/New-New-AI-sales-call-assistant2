# app.py - AI Sales Call Assistant (FINAL - Frameworks verbatim + PDF-aware enrichment + UI)
import streamlit as st
import os, re, io, tempfile, base64
from datetime import datetime
from html import escape
import requests

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
# GROQ placeholder - keep as requested
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
    "pdf_docs": {},            # brand -> combined text
    "pdf_summaries": {},       # brand -> short bullet summary
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
        "call_flow":["PREPARE","ENGAGE","CREATE OPPORTUNITY","INFLUENCE","IMPACT GSO","ANALYSE"]
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
# Official verbatim frameworks (kept as requested)
# -------------------------
JEMPERLI_FRAMEWORK_TITLE = "IMPACT Competitive Selling Framework"
JEMPERLI_FRAMEWORK_VERBATIM = """COCO, or the commercial-oriented call objective, represents the pre-call planning step. This is where customer insights are used to identify the customer persona, as well as the call objective that includes the incremental steps to achieve a GSO. When preparing your COCO, identify a select patient type to align on and develop thought-provoking questions that will challenge status quo thinking and encourage the customer to do differently.

Anchor opens the conversation using the insights identified in the COCO to create a patient-focused narrative and align with the customer on the call objective. Using a competitive mindset, messaging is tailored to the customer by focusing on an appropriate patient-type and/or customer challenge/unmet need. A story anchors the conversation and ensures discussions remain on topic.

Engage builds off the Anchor to draw the customer in by allowing them the opportunity to respond and ask questions. Through a compelling and impactful two-way dialogue, the Engage step allows you to connect clinical data and product messages as an appropriate solution to address customer/patient needs and handle potential customer objections.

Close is the process of gaining customer agreement and commitment through clearly defined next steps that are aligned to the call objective and advance the customer journey (incremental steps) to ultimately achieve a GSO. Omni-channel activities should be considered as a follow-up to extend the customer engagement beyond Face-to-Face or Screen-to-Screen interactions. After the Close of each call, all new insights gained from the call should be recorded to inform future call objectives.
"""

SHINGRIX_FRAMEWORK_TITLE = "EMOTIVE Selling Framework"
SHINGRIX_FRAMEWORK_VERBATIM = """1-PREPARE: Link to the last Call, Create Interest and share value, Co-Identify patient profile
2-ENGAGE:
a-Rapport & Link to the last Call,
b-Co-Identify patient profile, Tell the story of this patient, Highlight the feelings, visuals in an emotive way, while painting the patient profile. As you planned, align with HCP on the patient profile,
c-Create Interest and share value, Create interest / URGENCY, build value of the Vx,
Make the HCP think about the risk that +50 patient would face if he had shingles
Use EMOTIVE selling approach to highlight the risks & patient experience
3-CREATE OPPORTUNITY:
a-Use powerful insightful questions
b-Understand the unmet needs of the patient and HCP by asking insightful questions
c-What is the risk of this patient having shingles added to his diabetes complication?
Do you have prevention measures for Shingles?
4-INFLUENCE:
a-Customize your message to match the co-identified patient
b-Be ready to handle HCP objections using APACT
Example: Cost , Time ,…..
c-Lead the call to agree with HCP on the time that he will interfere & start discussion about Shingrix with the patient.
5-IMPACT GSO: Goos sell outcome call
6-ANALYSE:
a-Did I achieve GSO, having a clear commitment of the HCP with a new experience with Shingrix? WHY?
b-What’s my next call objective?
"""

# Default GSK Competitive Selling Module (verbatim per user)
GSK_DEFAULT_TITLE = "Competitive Selling Module"
GSK_DEFAULT_VERBATIM = """1-Prepare to sell
2-Open the sales call
3-Uncover opportunities
4-Align on brand and address objections
5-Close with commitments
6-Analyse sales call and plan next steps
"""

# -------------------------
# CSS (white card style for collapsibles, orange gradient background, merged input, etc.)
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
  background: rgba(255,255,255,0.96);
  box-shadow: 0 6px 18px rgba(0,0,0,0.06);
}
.header .title { text-align:center; flex:1; }
.header img.left-logo { height:56px; border-radius:6px; }
.header .ai-logo {
  width:86px; height:86px; border-radius:50%; object-fit:cover; box-shadow:0 10px 30px rgba(0,0,0,0.16);
}

/* Collapsible white card (for summaries and frameworks) */
.collapsible-white {
  background: #ffffff; border-radius:10px; padding:14px; margin-bottom:10px;
  box-shadow: 0 8px 22px rgba(0,0,0,0.08); color:#111;
}

/* Chat container */
.chat-container {
  max-height:60vh; overflow-y:auto; padding:12px;
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

/* Feedback row */
.feedback-row { display:flex; gap:8px; margin-top:8px; align-items:center; }
.feedback-btn { background:#fff; border:1px solid #e6e9ee; padding:6px 10px; border-radius:8px; cursor:pointer; }

/* Suggestion pill */
.suggestion-pill { display:inline-block; padding:6px 12px; border-radius:20px; background:#fff; margin:4px; border:1px solid #eee; font-size:14px; cursor:pointer; }

/* merged input bubble */
.input-row {
  display:flex; gap:8px; align-items:stretch; width:100%;
  background:#ffffff; padding:8px; border-radius:12px; border:1px solid #e6e6e6;
  box-shadow:0 6px 18px rgba(0,0,0,0.06);
}
.input-textarea { flex:1; border:none; resize:none; outline:none; font-size:14px; padding:8px; }
.send-btn { background:#ff8c00; color:#fff; border:none; padding:10px 12px; border-radius:10px; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:8px; min-width:56px; }

/* footer bubble */
.footer-fixed {
  position: fixed; left:20px; right:20px; bottom:18px; z-index:9999;
  display:flex; justify-content:center; pointer-events:none;
}
.footer-bubble {
  pointer-events:auto; width:100%; max-width:1100px;
  background: #ffffff; border-radius:12px; padding:10px;
  box-shadow:0 12px 40px rgba(0,0,0,0.08); resize:vertical; overflow:auto; min-height:56px; max-height:240px; border:1px solid #e6e1d7;
}

/* small bottom-right text */
.small-bottom-right {
  position: fixed; right:36px; bottom:28px; z-index:10001; font-size:12px; color:#333;
  background: #ffffff; padding:6px 10px; border-radius:8px; border:1px solid #eee; box-shadow:0 6px 18px rgba(0,0,0,0.06);
}

/* sidebar metric */
.sidebar-metric { background: #ffffff; padding:10px; border-radius:8px; margin-bottom:8px; text-align:center; box-shadow: 0 6px 18px rgba(0,0,0,0.04); }

/* remove stray top white padding */
.block-container .element-container { padding-top: 0rem; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Helper functions (read files, summarize, search, audio, export)
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
            # fallback: try reading bytes as text
            try:
                return uploaded_file.getvalue().decode("utf-8", errors="ignore")
            except Exception:
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
    # Enhanced summary: include top sentences + counts
    if not text:
        return ""
    sents = re.split(r'(?<=[\.!\?])\s+', text)
    top = [s.strip() for s in sents if s.strip()][:bullets]
    meta = f"- Document length (approx sentences): {len(sents)}"
    lines = [meta] + [f"- {t}" for t in top]
    return "\n".join(lines)

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
# GROQ safe query (keeps placeholder)
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
# Local extraction helpers and structured generation
# -------------------------
def extract_by_patterns(full_text: str, patterns: list, keep_lines: int = 6):
    out = []
    if not full_text:
        return out
    for p in patterns:
        found = re.findall(p, full_text, re.IGNORECASE | re.DOTALL)
        if found:
            for block in found:
                if isinstance(block, tuple):
                    block = " ".join([b for b in block if b])
                parts = re.split(r'[\r\n]+|\.\s+', block)
                for part in parts:
                    t = part.strip().strip("•-–—:")
                    if len(t) > 20:
                        out.append(t)
                        if len(out) >= keep_lines:
                            return out
    return out

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
        short = re.split(r'(?<=[\.!\?])\s+', text.strip())[0][:240]
        if short not in seen:
            seen.add(short)
            bullets.append(short)
        if len(bullets) >= top_n:
            break
    return bullets

def clean_list(lst, max_items=6):
    out = []
    for it in lst:
        t = it.strip()
        if not t:
            continue
        if t not in out:
            out.append(t)
        if len(out) >= max_items:
            break
    return out

# Main generator that respects verbatim frameworks when brand matches
def generate_structured_sales_call(brand, persona, specialty, objective, local_docs, chunks, metas):
    brand_name = brand_data.get(brand, {}).get("display", brand)
    persona_label = persona or "Target persona"
    specialty_label = specialty or "Generalist"

    full_text = "\n\n".join(local_docs) if local_docs else ""

    # Patterns
    patterns_insights = [r"(?:key insights|key messages|main messages|highlights|summary)[\:\-\s]*([\s\S]{20,400})",
                         r"(?:highlights|takeaways|key messages)[\:\-\s]*([\s\S]{20,400})"]
    patterns_benefits = [r"(?:benefits|advantages|key benefits|value proposition)[\:\-\s]*([\s\S]{20,400})"]
    patterns_objections = [r"(?:objections|concerns|barriers)[\:\-\s]*([\s\S]{20,400})"]
    patterns_evidence = [r"(?:efficacy results|efficacy|results from|clinical results|trial)[\:\-\s]*([\s\S]{20,400})"]
    patterns_indication = [r"(?:indication|indicated for|indicated)[\:\-\s]*([\s\S]{10,200})"]

    key_insights = extract_by_patterns(full_text, patterns_insights, keep_lines=6)
    benefits = extract_by_patterns(full_text, patterns_benefits, keep_lines=4)
    objections = extract_by_patterns(full_text, patterns_objections, keep_lines=4)
    evidence = extract_by_patterns(full_text, patterns_evidence, keep_lines=4)
    indications = extract_by_patterns(full_text, patterns_indication, keep_lines=2)

    if len(key_insights) < 3 and chunks:
        key_insights += pick_top_insights([brand_name, persona_label, specialty_label, objective], chunks, metas, top_n=5)
    if not benefits and chunks:
        benefits += pick_top_insights(["benefit", "advantage", "value", brand_name], chunks, metas, top_n=3)
    if not objections and chunks:
        objections += pick_top_insights(["objection", "concern", "barrier", "cost", "safety"], chunks, metas, top_n=3)
    if not evidence and chunks:
        evidence += pick_top_insights(["efficacy", "trial", "study", "safety", brand_name], chunks, metas, top_n=3)
    if not indications and chunks:
        indications += pick_top_insights(["indication", "indicated", "approved for"], chunks, metas, top_n=2)

    key_insights = clean_list(key_insights, max_items=6)
    benefits = clean_list(benefits, max_items=4)
    objections = clean_list(objections, max_items=4)
    evidence = clean_list(evidence, max_items=3)
    indications = clean_list(indications, max_items=2)

    if brand.lower() == "jemperli":
        # Use IMPACT Competitive Selling Framework verbatim, then enrich under each header
        header = JEMPERLI_FRAMEWORK_TITLE
        verbatim = JEMPERLI_FRAMEWORK_VERBATIM
        # Build enriched output
        lines = [f"Assistant: Using the **{header}** for **{brand_name}** (verbatim framework shown below):", ""]
        lines.append(verbatim)
        lines.append("")  # blank line
        lines.append("Enriched bullets (from uploaded references):")
        # COCO (pre-call planning)
        lines.append("\n**COCO (Pre-call planning):**")
        lines.append(f"- Persona: {persona_label} ({specialty_label})")
        lines.append(f"- Objective: {objective}")
        lines.append(f"- Suggested patient type: {indications[0] if indications else 'Select one patient type to align on.'}")
        if key_insights:
            lines.append("- Key insights:")
            for k in key_insights:
                lines.append(f"    - {k}")
        if benefits:
            lines.append("- Key benefits to highlight:")
            for b in benefits:
                lines.append(f"    - {b}")
        if evidence:
            lines.append("- Evidence snippets:")
            for e in evidence:
                lines.append(f"    - {e}")
        if objections:
            lines.append("- Anticipated objections:")
            for o in objections:
                lines.append(f"    - {o}")
        return "\n".join(lines)

    elif brand.lower() == "shingrix":
        # Use EMOTIVE Selling Framework verbatim
        header = SHINGRIX_FRAMEWORK_TITLE
        verbatim = SHINGRIX_FRAMEWORK_VERBATIM
        lines = [f"Assistant: Using the **{header}** for **{brand_name}** (verbatim framework shown below):", ""]
        lines.append(verbatim)
        lines.append("")
        lines.append("Enriched bullets (from uploaded references):")
        # PREPARE
        lines.append("\n**PREPARE:**")
        lines.append(f"- Link to last call: [Add link or summary from CRM]")
        if key_insights:
            lines.append("- Key clinical/patient insights:")
            for k in key_insights:
                lines.append(f"    - {k}")
        lines.append(f"- Suggested patient profile: {indications[0] if indications else 'Adults ≥50 or relevant per label'}")
        # ENGAGE
        lines.append("\n**ENGAGE:**")
        if benefits:
            lines.append("- Emotive hooks & patient story bullets:")
            for b in benefits:
                lines.append(f"    - {b}")
        if evidence:
            lines.append("- Clinical data to weave into story:")
            for e in evidence:
                lines.append(f"    - {e}")
        # CREATE OPPORTUNITY
        lines.append("\n**CREATE OPPORTUNITY:**")
        lines.append("- Suggested insightful questions:")
        lines.append("    - What would happen if this patient developed shingles today?")
        lines.append("    - How do you currently assess shingles risk in patients with comorbidities?")
        # INFLUENCE
        lines.append("\n**INFLUENCE:**")
        if objections:
            lines.append("- Objections & suggested responses:")
            for o in objections:
                lines.append(f"    - {o}")
        # IMPACT GSO & ANALYSE
        lines.append("\n**IMPACT GSO:**")
        lines.append("- Agree incremental steps and next actions (e.g., start discussions, patient materials).")
        lines.append("\n**ANALYSE:**")
        lines.append("- Capture outcome, next objective, and CRM updates.")
        return "\n".join(lines)

    else:
        # Default GSK Competitive Selling Module (use verbatim header)
        header = GSK_DEFAULT_TITLE
        verbatim = GSK_DEFAULT_VERBATIM
        lines = [f"Assistant: Using the **{header}** (default GSK selling module) for **{brand_name}**:", ""]
        lines.append(verbatim)
        lines.append("")
        lines.append("Enriched bullets (from uploaded references):")
        # Map enrichment to the 6 steps
        lines.append("\n**1 - Prepare to sell**")
        lines.append(f"- Persona: {persona_label} ({specialty_label})")
        if key_insights:
            lines.append("- Key insights:")
            for k in key_insights:
                lines.append(f"    - {k}")
        lines.append("\n**2 - Open the sales call**")
        lines.append('- Suggested opening lines: "Hello Dr..., I’d like to discuss..."')
        lines.append("\n**3 - Uncover opportunities**")
        lines.append("- Insightful questions to uncover gaps:")
        lines.append('    - "What are your main challenges with this patient group?"')
        if benefits:
            lines.append("- Key solution benefits:")
            for b in benefits:
                lines.append(f"    - {b}")
        lines.append("\n**4 - Align on brand and address objections**")
        if objections:
            lines.append("- Anticipated objections and responses:")
            for o in objections:
                lines.append(f"    - {o}")
        lines.append("\n**5 - Close with commitments**")
        lines.append("- Agree on next steps and commitments (e.g., follow-up, sample, checklist).")
        lines.append("\n**6 - Analyse sales call and plan next steps**")
        lines.append("- Record insights, update CRM, set next call objective.")
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
                # store enhanced bullet summary
                st.session_state["pdf_summaries"][sel_brand] = model_summarize(st.session_state["pdf_docs"][sel_brand], bullets=8)
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
# Header (main)
# -------------------------
st.markdown("""
<div class="header">
  <div style="width:140px;"><img src="https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/845b8f1ae98e46440e840c0a906f3610dd343c9a/.devcontainer/GSK1-logo.png" class="left-logo"></div>
  <div class="title"><h2 style="margin:0">AI Sales Call Assistant</h2><div style="color:#555;font-size:13px;">APACT-guided — structured call flows</div></div>
  <div style="width:120px;text-align:right;"><img src="https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/845b8f1ae98e46440e840c0a906f3610dd343c9a/.devcontainer/AURA1.png" class="ai-logo"></div>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Main upload area & build context
# -------------------------
st.subheader("Upload reference document (main)")
uploaded_file_main = st.file_uploader("Upload PDF / TXT / DOCX (main) — added to brand context", type=["pdf","txt","docx"], key="main_upload")
if uploaded_file_main:
    content = read_file_text_from_uploaded(uploaded_file_main)
    if content:
        st.session_state["pdf_docs"].setdefault(st.session_state["selected_brand"], "")
        st.session_state["pdf_docs"][st.session_state["selected_brand"]] += "\n\n" + content
        st.session_state["pdf_summaries"][st.session_state["selected_brand"]] = model_summarize(st.session_state["pdf_docs"][st.session_state["selected_brand"]], bullets=8)
        st.success("Uploaded and summarized for brand.")
        st.rerun()

# Build local docs list (repo + uploaded)
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
# Collapsible bullet summaries (opened by default)
# -------------------------
# PDF summary (collapsible white card)
pdf_sum = st.session_state["pdf_summaries"].get(brand, "")
if not pdf_sum and brand in st.session_state["pdf_docs"]:
    pdf_sum = model_summarize(st.session_state["pdf_docs"][brand], bullets=8)
    st.session_state["pdf_summaries"][brand] = pdf_sum

# Show collapsible summary opened by default if we have content
if pdf_sum:
    with st.expander("📄 Uploaded PDF Summary (bulleted)", expanded=True):
        st.markdown(f'<div class="collapsible-white">{pdf_sum.replace("\\n","<br>")}</div>', unsafe_allow_html=True)
else:
    # Show an empty but explanatory white card telling user to upload
    with st.expander("📄 Uploaded PDF Summary (bulleted)", expanded=True):
        st.markdown('<div class="collapsible-white">No uploaded brand documents yet. Upload a PDF/TXT/DOCX in the main or sidebar upload to enable tailored outputs.</div>', unsafe_allow_html=True)

# Repository-based medical & sales summaries (collapsed)
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
    st.markdown(f'<div class="collapsible-white">{med_summary.replace("\\n","<br>") if med_summary else "- No medical references found."}</div>', unsafe_allow_html=True)

with st.expander("💼 Sales Module Summary (bulleted)", expanded=False):
    st.markdown(f'<div class="collapsible-white">{sales_summary.replace("\\n","<br>") if sales_summary else "- No sales module content found."}</div>', unsafe_allow_html=True)

# GROQ unavailable notice (non-blocking)
if st.session_state.get("groq_unavailable"):
    st.warning("⚠️ LLM (GROQ) not reachable or API key not set — running in offline/fallback mode.", icon="⚠️")

# -------------------------
# Prompt suggestions (collapsible)
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
    for i, s in enumerate(suggestions):
        if st.button(s, key=f"suggbtn_{i}"):
            st.session_state["chat_history"].append({"role":"user","text":s})
            # If it's a Generate sales call prompt, produce structured flow using verbatim frameworks where detected
            if "sales call" in s.lower() or s.lower().startswith("generate sales call") or s.lower().startswith("generate call flow"):
                ai_text = generate_structured_sales_call(brand=brand, persona=persona, specialty=specialty, objective=objective, local_docs=local_docs, chunks=chunks, metas=metas)
                audio_b64 = generate_audio_base64(ai_text)
                # Show the framework header as a collapsible white card, opened by default
                with st.expander(f"{(JEMPERLI_FRAMEWORK_TITLE if brand.lower()=='jemperli' else SHINGRIX_FRAMEWORK_TITLE if brand.lower()=='shingrix' else GSK_DEFAULT_TITLE)}", expanded=True):
                    st.markdown(f'<div class="collapsible-white">{ai_text.replace("\\n","<br>")}</div>', unsafe_allow_html=True)
                st.session_state["chat_history"].append({"role":"assistant","text":ai_text,"audio_b64":audio_b64})
                st.rerun()
            else:
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
# Chat display (no stray white gaps)
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

        # interactive feedback row
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

        # follow-up options display
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
# Merged input (textarea + send) centered above footer bubble
# -------------------------
st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
st.markdown('<div style="display:flex; justify-content:center;">', unsafe_allow_html=True)
st.markdown('<div style="width:100%; max-width:1100px;">', unsafe_allow_html=True)

st.markdown('<div class="input-row">', unsafe_allow_html=True)
main_text = st.text_area("", value=st.session_state.get("main_input",""), key="main_input_widget", height=96, placeholder="Type your message or click a suggestion...", label_visibility="collapsed")
col_send, col_space = st.columns([1,0.05])
with col_send:
    send_clicked = st.button("Send ➤", key="send_main", help="Send message")
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# handle send action
if send_clicked:
    if main_text and main_text.strip():
        st.session_state["chat_history"].append({"role":"user","text":main_text.strip()})
        trigger_phrases = ["generate sales call", "generate call flow", "sales call", "call flow"]
        lower = main_text.lower()
        if any(tp in lower for tp in trigger_phrases):
            ai_text = generate_structured_sales_call(brand=brand, persona=persona, specialty=specialty, objective=objective, local_docs=local_docs, chunks=chunks, metas=metas)
            audio_b64 = generate_audio_base64(ai_text)
            # display the framework header as a white collapsible card opened by default
            header_title = JEMPERLI_FRAMEWORK_TITLE if brand.lower()=='jemperli' else SHINGRIX_FRAMEWORK_TITLE if brand.lower()=='shingrix' else GSK_DEFAULT_TITLE
            with st.expander(header_title, expanded=True):
                st.markdown(f'<div class="collapsible-white">{ai_text.replace("\\n","<br>")}</div>', unsafe_allow_html=True)
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
# Footer bubble (fixed, resizable) and small bottom-right text
# -------------------------
st.markdown(f"""
<div class="footer-fixed" aria-hidden="false">
  <div class="footer-bubble" role="region" aria-label="Footer Bubble (resizable)">
    <div style="opacity:0.85; font-size:12px;">Footer (resizable). Use the input above to send messages. This bubble is resizable for convenience.</div>
  </div>
</div>
""", unsafe_allow_html=True)

# small bottom-right text
st.markdown('<div class="small-bottom-right">Please refer to Write Right Principles course: BUS-LGL-WRJA-001</div>', unsafe_allow_html=True)

# small footer note
st.markdown('<div style="text-align:center; margin-top:8px; font-size:12px; color:#111;">⚠️ Internal tool — outputs are grounded in uploaded and repository references. Verify clinical/compliance before external use.</div>', unsafe_allow_html=True)
