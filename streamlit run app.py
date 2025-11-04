# app.py - AI Sales Call Assistant (FINAL FIXED FOR SAFE st.experimental_rerun)
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
# Brand configuration & verbatim frameworks
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

GSK_DEFAULT_TITLE = "Competitive Selling Module"
GSK_DEFAULT_VERBATIM = """1-Prepare to sell
2-Open the sales call
3-Uncover opportunities
4-Align on brand and address objections
5-Close with commitments
6-Analyse sales call and plan next steps
"""

# -------------------------
# CSS: gradient background, white cards, copilot fixed input, sticky disclaimer
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
  width:92px; height:92px; border-radius:50%; object-fit:cover; box-shadow:0 12px 36px rgba(0,0,0,0.16);
}

/* Collapsible white card */
.collapsible-white {
  background: #ffffff; border-radius:10px; padding:14px; margin-bottom:10px;
  box-shadow: 0 8px 22px rgba(0,0,0,0.08); color:#111;
}

/* Chat container */
.chat-container {
  max-height:calc(100vh - 420px); overflow-y:auto; padding:12px;
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

/* Copilot fixed input area (above disclaimer) */
.copilot-fixed {
  position: fixed;
  left: 24px;
  right: 24px;
  bottom: 110px; /* above sticky disclaimer */
  z-index: 10010;
  display:flex;
  justify-content:center;
  pointer-events: auto;
}
.copilot-box {
  width:100%; max-width:1100px;
  background:#ffffff; border-radius:12px; padding:8px; box-shadow:0 12px 30px rgba(0,0,0,0.12);
  border:1px solid #e8e5df;
  display:flex; flex-direction:column; gap:8px;
}

/* top row of suggestions inside copilot */
.copilot-suggestions { display:flex; gap:8px; flex-wrap:wrap; }

/* input row merged */
.copilot-input-row { display:flex; gap:8px; align-items:center; }
.copilot-textarea { flex:1; border:none; outline:none; resize:none; padding:8px; font-size:14px; }
.copilot-btn { background:#ff8c00; color:#fff; border:none; padding:10px 14px; border-radius:10px; cursor:pointer; }

/* Sticky disclaimer bubble (always visible) */
.disclaimer-sticky {
  position: fixed;
  left: 24px;
  right: 24px;
  bottom: 18px;
  z-index: 10000;
  display:flex;
  justify-content:center;
  pointer-events: auto;
}
.disclaimer-bubble {
  width:100%; max-width:1100px;
  background: #ffffff; border-radius:12px; padding:10px;
  box-shadow:0 12px 40px rgba(0,0,0,0.08); border:1px solid #e6e1d7;
  display:flex; justify-content:space-between; align-items:center; gap:12px;
}

/* small bottom-right text */
.small-bottom-right {
  position: fixed; right:36px; bottom:80px; z-index:10011; font-size:12px; color:#333;
  background: #ffffff; padding:6px 10px; border-radius:8px; border:1px solid #eee; box-shadow:0 6px 18px rgba(0,0,0,0.06);
}

/* sidebar metric */
.sidebar-metric { background: #ffffff; padding:10px; border-radius:8px; margin-bottom:8px; text-align:center; box-shadow: 0 6px 18px rgba(0,0,0,0.04); }

/* ensure no extra top padding in blocks */
.block-container .element-container { padding-top: 0rem; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Utility functions (read files, summarise, local search, audio, export)
# -------------------------
def read_file_text_from_uploaded(uploaded_file):
    try:
        if hasattr(uploaded_file, "type") and "pdf" in (uploaded_file.type or "") and PdfReader:
            reader = PdfReader(uploaded_file)
            return "".join([p.extract_text() or "" for p in reader.pages])
        elif hasattr(uploaded_file, "type") and uploaded_file.type == "text/plain":
            return uploaded_file.getvalue().decode("utf-8", errors="ignore")
        elif hasattr(uploaded_file, "type") and uploaded_file.type in ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"] and DOCX_AVAILABLE:
            # docx reading via python-docx not available when streaming file-like; fallback
            try:
                doc = Document(uploaded_file)
                return "\n".join([p.text for p in doc.paragraphs])
            except Exception:
                return uploaded_file.getvalue().decode("utf-8", errors="ignore")
        else:
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
# GROQ safe query
# -------------------------
def query_groq_safe(prompt: str, context_docs: list, max_tokens: int = 700):
    if not GROQ_API_KEY or GROQ_API_KEY == "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":
        st.session_state["groq_unavailable"] = True
        return None
    context_text = "\n\n".join([d for d in context_docs if d])
    payload = {
        "prompt": f"Use the following reference material to create a practical, example-driven sales call plan. Follow the framework steps exactly and provide practical instructions, example phrases, probing questions, and suggested next actions. Only return the assistant response.\n\nReferences:\n{context_text}\n\nUser prompt:\n{prompt}",
        "max_output_tokens": max_tokens
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
    try:
        r = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        resp = r.json()
        # Try common fields
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
# Local extraction & structured generator (brand-responsive)
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

def generate_structured_sales_call(brand, persona, specialty, objective, local_docs, chunks, metas):
    """
    Brand-responsive: uses verbatim framework header for Shingrix/Jemperli/Trelegy mapping,
    then attempts to create a rich, practical plan. If GROQ available, call LLM with guided prompt;
    otherwise, create local-extraction enriched guidance.
    """
    brand_key = brand.lower()
    brand_name = brand_data.get(brand_key, {}).get("display", brand)
    persona_label = persona or "Target persona"
    specialty_label = specialty or "Generalist"
    full_text = "\n\n".join(local_docs) if local_docs else ""

    # Determine framework
    if brand_key == "jemperli":
        framework_title = JEMPERLI_FRAMEWORK_TITLE
        framework_verbatim = JEMPERLI_FRAMEWORK_VERBATIM
        steps = ["COCO", "Anchor", "Engage", "Close"]
    elif brand_key == "shingrix":
        framework_title = SHINGRIX_FRAMEWORK_TITLE
        framework_verbatim = SHINGRIX_FRAMEWORK_VERBATIM
        steps = ["PREPARE","ENGAGE","CREATE OPPORTUNITY","INFLUENCE","IMPACT GSO","ANALYSE"]
    else:
        framework_title = GSK_DEFAULT_TITLE
        framework_verbatim = GSK_DEFAULT_VERBATIM
        steps = ["Prepare to sell","Open the sales call","Uncover opportunities","Align on brand and address objections","Close with commitments","Analyse sales call and plan next steps"]

    # If GROQ available, build a guided prompt using the verbatim framework and context
    if GROQ_API_KEY and GROQ_API_KEY != "Add_GROQ_API_here" and not st.session_state.get("groq_unavailable"):
        # Build framework steps block for LLM
        framework_block = framework_verbatim + "\n\n"
        prompt = f"""
You are a sales coach for pharmaceutical reps. Use the framework below EXACTLY as section headers (do not modify headers). Build a practical, example-driven, step-by-step sales call plan for the rep.

Brand: {brand_name}
Persona: {persona_label}
Specialty: {specialty_label}
Call objective: {objective}

Framework (verbatim):
{framework_block}

References (internal docs may follow):
{full_text}

For each framework step:
- Explain what the rep should *do* (3-6 practical actions)
- Provide 1-2 example phrases (short) to open/transition/close
- Give 1 probing question the rep can ask
- Suggest 1 measurable next action to record in CRM

Return strictly the assistant response (no citations, no extra commentary). Use bullet points and clear headers.
"""
        groq_out = query_groq_safe(prompt, local_docs, max_tokens=900)
        if groq_out:
            return f"Assistant: Using the **{framework_title}** for **{brand_name}** (verbatim framework used as guidance):\n\n{groq_out}"
        # else fallback to local
    # Local-extraction fallback (build rich guidance using extracted bullets)
    # extract various elements
    patterns_insights = [r"(?:key insights|key messages|main messages|highlights|summary)[\:\-\s]*([\s\S]{20,400})"]
    patterns_benefits = [r"(?:benefits|advantages|key benefits|value proposition)[\:\-\s]*([\s\S]{20,400})"]
    patterns_objections = [r"(?:objections|concerns|barriers)[\:\-\s]*([\s\S]{20,400})"]
    patterns_evidence = [r"(?:efficacy|results|trial|outcome|safety|study)[\:\-\s]*([\s\S]{20,400})"]
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

    # Build a rich response manually using the framework steps
    out_lines = [f"Assistant: Using the **{framework_title}** for **{brand_name}** (verbatim framework used as guidance):", ""]
    out_lines.append(framework_verbatim)
    out_lines.append("")
    out_lines.append("Enriched practical guidance (examples, probing questions, and next actions):")
    out_lines.append("")

    # For each step, generate practical bullets
    if brand_key == "jemperli":
        # COCO
        out_lines.append("**COCO (Pre-call planning):**")
        out_lines.append(f"- Persona: {persona_label} ({specialty_label})")
        out_lines.append(f"- Objective: {objective}")
        out_lines.append(f"- Suggested patient type: {indications[0] if indications else 'Select a patient type to align on.'}")
        out_lines.append("- Actions:")
        out_lines.append("    - Review last call notes & CRM flags for similar patients.")
        out_lines.append('    - Draft 2 thought-provoking questions to challenge status quo (example below).')
        out_lines.append("- Example probing question: \"What would you change about current care for this patient if we could reduce treatment burden?\"")
        out_lines.append("")

        out_lines.append("**Anchor (Open the conversation):**")
        out_lines.append("- Actions:")
        out_lines.append('    - Start with the patient story based on COCO insights and align on the call objective.')
        out_lines.append('    - Example opening: "Dr. X, based on our last discussion, I want to focus on patients who... Is that OK?"')
        out_lines.append("")

        out_lines.append("**Engage (Two-way dialogue):**")
        out_lines.append("- Actions:")
        out_lines.append("    - Use open questions, listen, and reflect; connect clinical data where appropriate.")
        out_lines.append('    - Example phrase: "Tell me how you manage patients like Mrs. D — what is your biggest concern?"')
        out_lines.append("    - Suggested data to reference: " + (evidence[0] if evidence else "trial results or label data relevant to efficacy/safety."))
        out_lines.append("")

        out_lines.append("**Close (Commit & next steps):**")
        out_lines.append("- Actions:")
        out_lines.append("    - Agree on a measurable incremental step (e.g., identify one eligible patient to start the discussion).")
        out_lines.append('    - Example close: "Can we agree you will discuss this with one eligible patient this week and I will follow up?"')
        out_lines.append("    - Next action to record: set follow-up date and CRM note.")
        out_lines.append("")
    elif brand_key == "shingrix":
        out_lines.append("**PREPARE:**")
        out_lines.append("- Actions:")
        out_lines.append("    - Link to last call & identify eligible patient types (e.g., adults ≥50, patients with comorbidities).")
        out_lines.append('    - Example opening prep line: "I reviewed our last call regarding older adults at risk — I want to focus on prevention."')
        if key_insights:
            out_lines.append("- Key clinical insights to use:")
            for k in key_insights:
                out_lines.append(f"    - {k}")
        out_lines.append("")

        out_lines.append("**ENGAGE:**")
        out_lines.append("- Actions (emotive):")
        out_lines.append("    - Build rapport, tell the patient story, highlight feelings and impact (pain, quality of life).")
        out_lines.append('    - Example question: "Imagine if a 65-year-old diabetic patient developed shingles — how might that affect their daily life?"')
        out_lines.append("    - Use vivid language: 'excruciating pain, lasting impact on sleep & mobility.'")
        out_lines.append("")

        out_lines.append("**CREATE OPPORTUNITY:**")
        out_lines.append("- Actions:")
        out_lines.append("    - Ask powerful, insightful questions to reveal unmet needs.")
        out_lines.append('    - Example probe: "How do you currently discuss prevention in chronic disease reviews?"')
        if benefits:
            out_lines.append("- Benefits to highlight:")
            for b in benefits:
                out_lines.append(f"    - {b}")
        out_lines.append("")

        out_lines.append("**INFLUENCE:**")
        out_lines.append("- Actions:")
        out_lines.append("    - Tailor message to co-identified patient; handle objections via APACT (Acknowledge, Probe, Advise, Confirm, Transition).")
        if objections:
            out_lines.append("- Anticipated objections & short responses:")
            for o in objections:
                out_lines.append(f"    - {o} — Suggested reply: 'I understand — here's the evidence and a practical way to mitigate.'")
        out_lines.append("")

        out_lines.append("**IMPACT GSO & ANALYSE:**")
        out_lines.append("- Actions:")
        out_lines.append("    - Secure a commitment (e.g., discuss Shingrix with the next eligible patient).")
        out_lines.append("    - CRM action: log commitment, set follow-up date, record barriers and agreed next steps.")
        out_lines.append("")
    else:
        # default competitive module
        out_lines.append("**1 - Prepare to sell**")
        out_lines.append("- Actions:")
        out_lines.append("    - Gather patient examples, recent clinic data, and prior call notes.")
        out_lines.append("    - Example: identify 2 patients who would benefit most.")
        out_lines.append("")

        out_lines.append("**2 - Open the sales call**")
        out_lines.append("- Actions:")
        out_lines.append('    - Use an attention opener linking to patient need: "Can I share a quick case?"')
        out_lines.append("    - Example opening phrase and quick value statement.")
        out_lines.append("")

        out_lines.append("**3 - Uncover opportunities**")
        out_lines.append("- Actions:")
        out_lines.append("    - Ask insightful questions to surface unmet needs.")
        out_lines.append('    - Example probe: "What is your process for identifying patients who would benefit from this therapy?"')
        out_lines.append("")

        out_lines.append("**4 - Align on brand and address objections**")
        out_lines.append("- Actions:")
        out_lines.append("    - Map key benefits to the patient's unmet needs and preempt common objections.")
        if objections:
            out_lines.append("- Objections & suggested responses:")
            for o in objections:
                out_lines.append(f"    - {o} — Suggested reply: provide data or a practical workaround.")
        out_lines.append("")

        out_lines.append("**5 - Close with commitments**")
        out_lines.append("- Actions:")
        out_lines.append('    - Ask for a commitment: "Would you be willing to try this with one patient and feedback?"')
        out_lines.append("    - Set a specific next step and timeline.")
        out_lines.append("")

        out_lines.append("**6 - Analyse sales call and plan next steps**")
        out_lines.append("- Actions:")
        out_lines.append("    - Capture insights in CRM, set follow-up objectives, and iterate.")
        out_lines.append("")

    if not (key_insights or benefits or evidence or indications):
        out_lines.append("**Note:** I could not find uploaded brand-specific documents to enrich this call fully. Upload the brand sales/medical PDFs for a richer, evidence-based plan.")
    return "\n".join(out_lines)

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
    uploaded_side = st.file_uploader("Upload file for brand context", type=["pdf","txt","docx"], key="sidebar_upload")
    if uploaded_side:
        text = read_file_text_from_uploaded(uploaded_side)
        if text:
            st.session_state["pdf_docs"].setdefault(sel_brand, "")
            st.session_state["pdf_docs"][sel_brand] += "\n\n" + text
            st.session_state["pdf_summaries"][sel_brand] = model_summarize(st.session_state["pdf_docs"][sel_brand], bullets=8)
            st.success("Sidebar file added and summarized.")
        else:
            st.error("Could not read file.")

    st.markdown("---")
    st.subheader("Export / Reset")
    export_format = st.selectbox("Export format", ["DOCX" if DOCX_AVAILABLE else "TXT", "TXT"])
    if st.button("🗑️ Clear chat"):
        st.session_state["chat_history"] = []
        st.session_state["followup_options"] = {}
        st.session_state["feedback_stats"] = {"like":0,"dislike":0,"need_more":0}

# -------------------------
# Header (main)
# -------------------------
st.markdown("""
<div class="header">
  <div style="width:140px;"><img src="https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/845b8f1ae98e46440e840c0a906f3610dd343c9a/.devcontainer/GSK1-logo.png" class="left-logo"></div>
  <div class="title"><h2 style="margin:0">AI Sales Call Assistant</h2><div style="color:#555;font-size:13px;">APACT-guided — structured call flows</div></div>
  <div style="width:140px;text-align:right;"><img src="https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/845b8f1ae98e46440e840c0a906f3610dd343c9a/.devcontainer/AURA1.png" class="ai-logo"></div>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Main upload area & rerun
# -------------------------
uploaded_file_main = st.file_uploader("Upload PDF / TXT / DOCX (main) — added to brand context", type=["pdf","txt","docx"], key="main_upload")
if uploaded_file_main:
    content = read_file_text_from_uploaded(uploaded_file_main)
    if content:
        st.session_state["pdf_docs"].setdefault(st.session_state["selected_brand"], "")
        st.session_state["pdf_docs"][st.session_state["selected_brand"]] += "\n\n" + content
        st.session_state["pdf_summaries"][st.session_state["selected_brand"]] = model_summarize(
            st.session_state["pdf_docs"][st.session_state["selected_brand"]], bullets=8
        )
        st.success("Uploaded and summarized for brand.")
    else:
        st.error("Could not read uploaded file.")

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
# PDF summary (collapsible, opened by default)
# -------------------------
pdf_sum = st.session_state["pdf_summaries"].get(brand, "")
if not pdf_sum and brand in st.session_state["pdf_docs"]:
    pdf_sum = model_summarize(st.session_state["pdf_docs"][brand], bullets=8)
    st.session_state["pdf_summaries"][brand] = pdf_sum

if pdf_sum:
    with st.expander("📄 Uploaded PDF Summary (bulleted)", expanded=True):
        st.markdown(f'<div class="collapsible-white">{pdf_sum.replace("\\n","<br>")}</div>', unsafe_allow_html=True)
else:
    with st.expander("📄 Uploaded PDF Summary (bulleted)", expanded=True):
        st.markdown('<div class="collapsible-white">No uploaded brand documents yet. Upload a PDF/TXT/DOCX in the main or sidebar upload to enable tailored outputs.</div>', unsafe_allow_html=True)

# Repository-based summaries collapsed
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

if st.session_state.get("groq_unavailable"):
    st.warning("⚠️ LLM (GROQ) not reachable or API key not set — running in offline/fallback mode.", icon="⚠️")

# -------------------------
# Prompt suggestions & copilot fixed input (bottom) - suggestions inside the copilot box
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

copilot_suggestions = make_suggestions(brand, persona, barrier, segment, specialty, objective)

# Render chat history area (main) - placed above fixed copilot input
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

        # feedback and followups
        followup_key = f"followup_{idx}"
        st.markdown('<div class="feedback-row">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1,1,1,6])
        with c1:
            if st.button("👍 Like", key=f"like_{idx}"):
                st.session_state["feedback_stats"]["like"] += 1
                pref_text = "Thanks! Quick preference: 1) Short scripts, 2) Data bullets, 3) Role-plays — reply 1/2/3."
                st.session_state["chat_history"].append({"role":"assistant","text":pref_text,"audio_b64":generate_audio_base64(pref_text)})
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
                
        with c4:
            fb_val = st.session_state.get("feedback", {}).get(f"fb_{idx}", "")
            if fb_val:
                st.markdown(f"**Feedback:** {fb_val}")
        st.markdown('</div>', unsafe_allow_html=True)

        # followup options block
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
                    
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Copilot fixed input box (suggestions + input + send) - fixed above sticky disclaimer
# -------------------------
# Build the copilot box HTML using Streamlit layout primitives for functionality
copilot_container = st.empty()
with copilot_container.container():
    st.markdown('<div class="copilot-fixed">', unsafe_allow_html=True)
    st.markdown('<div class="copilot-box">', unsafe_allow_html=True)

    # Suggestions row
    cols = st.columns([1,6,1])
    with cols[1]:
        st.markdown('<div class="copilot-suggestions">', unsafe_allow_html=True)
        # Render suggestion buttons
        for i, s in enumerate(copilot_suggestions):
            if st.button(s, key=f"copilot_sugg_{i}"):
                # populate main_input and auto-send
                st.session_state["main_input"] = s
                # emulate sending immediately
                # note: can't call st.rerun() here and then use send_clicked logic below - instead push to history and generate
                st.session_state["chat_history"].append({"role":"user","text":s})
                # handle generate sales call specially
                if any(tp in s.lower() for tp in ["generate sales call","generate call flow","call flow"]):
                    # require uploaded docs or repo files for a rich response; otherwise warn
                    if not local_docs:
                        warn_text = "No brand documents found. Upload the brand PDF/TXT/DOCX to generate a tailored sales call."
                        st.session_state["chat_history"].append({"role":"assistant","text":warn_text})
                        
                    ai_text = generate_structured_sales_call(brand=brand, persona=persona, specialty=specialty, objective=objective, local_docs=local_docs, chunks=chunks, metas=metas)
                    st.session_state["chat_history"].append({"role":"assistant","text":ai_text,"audio_b64":generate_audio_base64(ai_text)})
                    
                else:
                    ai_out = query_groq_safe(s, local_docs)
                    if ai_out:
                        st.session_state["chat_history"].append({"role":"assistant","text":ai_out,"audio_b64":generate_audio_base64(ai_out)})
                    else:
                        snippets = local_search_snippets(s, chunks, metas, top_n=5)
                        if snippets:
                            ai_text = "**Relevant excerpts:**\n" + "\n".join([f"- {sn['text'][:200]}..." for sn in snippets])
                        else:
                            ai_text = "I couldn't find direct references locally. Please upload relevant documents or rephrase the question."
                        st.session_state["chat_history"].append({"role":"assistant","text":ai_text,"audio_b64":generate_audio_base64(ai_text)})
                    
        st.markdown('</div>', unsafe_allow_html=True)

    # Input row
    st.markdown('<div class="copilot-input-row">', unsafe_allow_html=True)
    # Use a text_area bound to session_state for persistent content
    main_text = st.text_area("", value=st.session_state.get("main_input",""), key="copilot_main_input", height=84, placeholder="Type your message, or click a suggestion... (e.g. 'Generate sales call')", label_visibility="collapsed")
    send_col, empty_col = st.columns([0.18,0.02])
    with send_col:
        if st.button("Send ➤", key="copilot_send"):
            user_msg = main_text.strip()
            if not user_msg:
                # do nothing
                pass
            else:
                st.session_state["chat_history"].append({"role":"user","text":user_msg})
                # handle trigger phrases
                triggers = ["generate sales call","generate call flow","sales call","call flow"]
                if any(t in user_msg.lower() for t in triggers):
                    # require documents for tailored outputs
                    if not local_docs:
                        warn_text = "No brand documents found. Upload the brand PDF/TXT/DOCX to generate a tailored sales call."
                        st.session_state["chat_history"].append({"role":"assistant","text":warn_text})
                        st.session_state["main_input"] = ""
                        
                    ai_text = generate_structured_sales_call(brand=brand, persona=persona, specialty=specialty, objective=objective, local_docs=local_docs, chunks=chunks, metas=metas)
                    st.session_state["chat_history"].append({"role":"assistant","text":ai_text,"audio_b64":generate_audio_base64(ai_text)})
                    st.session_state["main_input"] = ""
                    
                else:
                    ai_out = query_groq_safe(user_msg, local_docs)
                    if ai_out:
                        st.session_state["chat_history"].append({"role":"assistant","text":ai_out,"audio_b64":generate_audio_base64(ai_out)})
                    else:
                        snippets = local_search_snippets(user_msg, chunks, metas, top_n=5)
                        if snippets:
                            ai_text = "**Relevant excerpts:**\n" + "\n".join([f"- {s['text'][:200]}..." for s in snippets])
                        else:
                            ai_text = "I couldn't find direct references locally. Please upload relevant documents or rephrase the question."
                        st.session_state["chat_history"].append({"role":"assistant","text":ai_text,"audio_b64":generate_audio_base64(ai_text)})
                    st.session_state["main_input"] = ""
                    
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Sticky resizable disclaimer bubble (always visible)
# -------------------------
st.markdown("""
<div class="disclaimer-sticky" aria-hidden="false">
  <div class="disclaimer-bubble" role="region" aria-label="Disclaimer (sticky)">
    <div style="font-size:13px; color:#111;">
      ⚠️ Internal tool — outputs are grounded in uploaded and repository references. Verify clinical and compliance information before external use.
    </div>
    <div style="font-size:13px; color:#333; opacity:0.9;">
      <b>Contact:</b> Compliance Team • <span style="margin-left:10px">GROQ key: {key_state}</span>
    </div>
  </div>
</div>
""".format(key_state=("set" if GROQ_API_KEY and GROQ_API_KEY != "Add_GROQ_API_here" else "not set")), unsafe_allow_html=True)

# small bottom-right reference text
st.markdown('<div class="small-bottom-right">Please refer to Write Right Principles course: BUS-LGL-WRJA-001</div>', unsafe_allow_html=True)

# -------------------------
# Small footer note (non-fixed)
# -------------------------
st.markdown('<div style="text-align:center; margin-top:8px; font-size:12px; color:#111;">&nbsp;</div>', unsafe_allow_html=True)
