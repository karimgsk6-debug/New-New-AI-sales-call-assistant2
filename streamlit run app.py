
# app_final_ready.py — AI Sales Call Assistant (RAG + Product-Specific Call Flow)
# ------------------------------------------------------------------------------
# Enhancements:
# - RAG over references + sales module + uploaded files (PDF/TXT) with citations
# - Intent router: sales_call_flow | role_play | objection_handling | qna
# - Product-specific prompts with brand_data scaffolding
# - File uploader + live indexing cache
# - Safer secrets (no hard-coded API key)
# - Medical References & Sales Module summaries moved to MAIN INTERFACE
# - Streamlit-safe input handling via st.form(clear_on_submit=True)
# ------------------------------------------------------------------------------

import streamlit as st
import os, re, tempfile, base64, io, uuid
from datetime import datetime
from html import escape
from typing import List, Dict, Tuple, Any

# Optional imports
try:
    from groq import Groq
except Exception:
    Groq = None

try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

try:
    from gtts import gTTS
except Exception:
    gTTS = None

# Vectorization
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

# Optional better embeddings (if installed locally)
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    SBERT_AVAILABLE = True
except Exception:
    SBERT_AVAILABLE = False

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# Resources & Avatar
# -------------------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"
AI_AVATAR_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"

# -------------------------
# Initialize session_state safely
# -------------------------
def _init_session():
    defaults = {
        "chat_history": [],
        "selected_brand": "shingrix",
        "temperature": 0.8,
        "search_mode": "deep",
        "medical_summary": "",
        "sales_summary": "",
        "feedback": {},
        "language": "English",
        "hcp_persona": "Friendly",
        "tone": "executive",
        "segment": "R",
        "rag_corpus": [],         # list of dicts: {text, filename, folder, page, chunk_id}
        "rag_index_ready": False,
        "vector_backend": "tfidf",# tfidf | sbert | none
        "rag_index": None,
        "uploaded_dir": "",
        "strict_grounding": True,
        "examples_density": 3,    # number of dialog turns per stage
        "top_k": 8,
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

_init_session()

# -------------------------
# CSS for hologram avatar + chat bubbles
# -------------------------
st.markdown("""
<style>
.title-box{ background: rgba(255,255,255,0.85); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; position:relative; margin-bottom:12px; }
.title-box img.left-logo{ position:absolute; left:12px; height:48px; }
.title-box img.right-logo{ position:absolute; right:12px; height:48px; }
.chat-bubble-user{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }
.ai-message { display:flex; align-items:flex-start; gap:12px; margin:10px 0; }
.ai-avatar { width:52px; height:52px; border-radius:50%; box-shadow: 0 0 12px rgba(0,255,255,0.6); flex-shrink:0; animation:holoPulse 2.5s infinite ease-in-out; }
@keyframes holoPulse { 0% { box-shadow:0 0 8px rgba(0,255,255,0.35);} 50% { box-shadow:0 0 22px rgba(0,255,255,0.9);} 100% { box-shadow:0 0 8px rgba(0,255,255,0.35);} }
.ai-bubble { background: rgba(255,255,255,0.06); border:1px solid rgba(0,255,255,0.18); color:#E6FBFF; padding:14px; border-radius:14px; backdrop-filter: blur(6px); max-width:90%; white-space:pre-wrap; }
.citation-box{ font-size:12px; color:#bcd; margin-left:6px; margin-bottom:6px; }
.fixed-disclaimer{ font-size:12px; color:#aac; margin-top:16px; opacity:0.9; }
.step-title{ font-weight:700; margin-top:8px; color:#BFF; }
.story{ font-style:italic; margin:6px 0 10px 0; color:#DFF; }
ul.assist-list{ margin:6px 0 6px 18px; padding:0; color:#DDF; }
.objection{ background:rgba(255,248,240,0.06); padding:8px; border-radius:8px; margin:6px 0; border:1px solid rgba(255,224,198,0.08); color:#FFD; }
.user-bubble{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }
.small-muted{font-size:11px; color:#aac;}
.source-chip{display:inline-block; margin:2px 4px; padding:2px 6px; border-radius:10px; border:1px solid rgba(0,255,255,0.25); color:#CFF; font-size:11px;}
hr.dim{border:0; border-top:1px solid rgba(255,255,255,0.15); margin:8px 0 12px;}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Background helper
# -------------------------
def set_dynamic_background(image_path):
    if not os.path.exists(image_path):
        return
    try:
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
        st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background: linear-gradient(90deg, rgba(255,140,0,0.06), rgba(255,165,0,0.02)),
                        url("data:image/png;base64,{encoded}");
            background-repeat: no-repeat;
            background-position: right top;
            background-size: cover;
        }}
        </style>
        """, unsafe_allow_html=True)
    except Exception:
        pass

set_dynamic_background(BACKGROUND_PATH)

# -------------------------
# Safer secrets
# -------------------------
def get_groq_client():
    if Groq is None:
        return None
    api_key = os.getenv("GROQ_API_KEY", "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") or st.secrets.get("GROQ_API_KEY", "")
    if not api_key:
        return None
    try:
        return Groq(api_key=api_key)
    except Exception:
        return None

def use_tts(text) -> bytes:
    if not text or gTTS is None:
        return b""
    try:
        tts = gTTS(text=text, lang="en")
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp.read()
    except Exception:
        return b""

# -------------------------
# Brand data (extendable)
# -------------------------
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R", "A", "C", "E"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator", "Friendly"],
        "barriers": [
            "HCP does not consider HZ a risk",
            "No time",
            "Cost",
            "Not convinced"
        ],
        "specialties": ["GP","Derm","Cardio"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/",
        "call_flow": ["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Analyze"],
        "objections_map": {
            "efficacy": "Highlight durable protection and real-world effectiveness where available.",
            "safety": "Acknowledge adverse events and clarify safety profile and monitoring.",
            "cost": "Reframe cost vs. prevented complications and downstream savings."
        },
        "keywords": ["herpes zoster","HZ","shingles","vaccine","RZV","adjuvanted","immunogenicity","reactogenicity"]
    }
}

# -------------------------
# RAG utilities
# -------------------------
def chunk_text(text: str, max_chars: int = 900, overlap: int = 140) -> List[str]:
    if not text:
        return []
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    chunks: List[str] = []
    buf = ""
    for s in sents:
        if len(buf) + len(s) + 1 <= max_chars:
            buf = (buf + " " + s).strip()
        else:
            if buf:
                chunks.append(buf)
            # start new buffer with overlap
            if overlap > 0 and chunks:
                prev_tail = chunks[-1][-overlap:]
                buf = (prev_tail + " " + s).strip()
            else:
                buf = s
    if buf:
        chunks.append(buf.strip())
    return [c for c in chunks if c.strip()]

def read_pdf_chunks(path: str) -> List[Tuple[str,int]]:
    out: List[Tuple[str,int]] = []
    if not PdfReader:
        return out
    try:
        reader = PdfReader(path)
        for i, page in enumerate(reader.pages):
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            if t.strip():
                for ck in chunk_text(t):
                    out.append((ck, i+1))  # 1-based page
    except Exception:
        pass
    return out

def read_txt_chunks(path: str) -> List[Tuple[str,int]]:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        return [(c, None) for c in chunk_text(text)]
    except Exception:
        return []

def ingest_folder(folder: str) -> List[Dict[str, Any]]:
    docs: List[Dict[str,Any]] = []
    if not folder or not os.path.exists(folder):
        return docs
    for root, _, files in os.walk(folder):
        for fname in sorted(files):
            fpath = os.path.join(root, fname)
            if fname.lower().endswith(".pdf") and PdfReader:
                chunks = read_pdf_chunks(fpath)
                for idx, (ck, page) in enumerate(chunks):
                    docs.append({
                        "text": ck, "filename": fname, "folder": root, "page": page, "chunk_id": f"{fname}#p{page or 0}#c{idx}"
                    })
            elif fname.lower().endswith(".txt"):
                chunks = read_txt_chunks(fpath)
                for idx, (ck, page) in enumerate(chunks):
                    docs.append({
                        "text": ck, "filename": fname, "folder": root, "page": page, "chunk_id": f"{fname}#p{page or 0}#c{idx}"
                    })
    return docs

@st.cache_data(show_spinner=False)
def build_index(docs: List[Dict[str,Any]], backend: str = "tfidf"):
    texts = [d["text"] for d in docs]
    meta = [{"filename": d["filename"], "folder": d["folder"], "page": d["page"], "chunk_id": d["chunk_id"]} for d in docs]

    if backend == "sbert" and SBERT_AVAILABLE:
        model_name = "all-MiniLM-L6-v2"
        model = SentenceTransformer(model_name)
        embeddings = model.encode(texts, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)
        return {"backend": "sbert", "meta": meta, "model_name": model_name, "vectorizer": None, "matrix": embeddings}
    else:
        if not SKLEARN_AVAILABLE:
            return {"backend": "none", "meta": meta, "model_name": "", "vectorizer": None, "matrix": texts}
        vec = TfidfVectorizer(ngram_range=(1,2), max_df=0.9, min_df=1)
        mat = vec.fit_transform(texts)
        return {"backend": "tfidf", "meta": meta, "model_name": "", "vectorizer": vec, "matrix": mat}

def retrieve(query: str, index: Dict[str,Any], top_k: int = 8) -> List[Dict[str,Any]]:
    if not query or not index or not index.get("meta"):
        return []
    backend = index.get("backend","none")
    meta = index["meta"]

    if backend == "sbert" and SBERT_AVAILABLE:
        model = SentenceTransformer(index["model_name"])
        q_emb = model.encode([query], show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)
        sims = np.dot(index["matrix"], q_emb.T).ravel()
        order = sims.argsort()[::-1][:top_k]
        return [{
            "text": None,
            "score": float(sims[i]),
            **meta[i]
        } for i in order]

    elif backend == "tfidf" and SKLEARN_AVAILABLE:
        vec = index["vectorizer"]
        mat = index["matrix"]
        q_vec = vec.transform([query])
        sims = cosine_similarity(q_vec, mat).ravel()
        order = sims.argsort()[::-1][:top_k]
        return [{
            "text": None,
            "score": float(sims[i]),
            **meta[i]
        } for i in order]

    else:
        # naive fallback: keyword hits count
        scores = []
        q_terms = set(re.findall(r"\w+", query.lower()))
        for i, m in enumerate(meta):
            txt = st.session_state.rag_corpus[i]["text"].lower()
            hit = sum(1 for t in q_terms if t in txt)
            scores.append((i, hit))
        order = [i for i,_ in sorted(scores, key=lambda x:x[1], reverse=True)[:top_k]]
        return [{
            "text": None,
            "score": float(dict(scores)[i]),
            **meta[i]
        } for i in order]

def materialize_text(snippet: Dict[str,Any]) -> str:
    for d in st.session_state.rag_corpus:
        if d["chunk_id"] == snippet["chunk_id"]:
            return d["text"]
    return ""

def format_citation(sn: Dict[str,Any]) -> str:
    p = f" p.{sn['page']}" if sn.get("page") else ""
    return f"{sn['filename']}{p}"

# -------------------------
# GROQ LLM
# -------------------------
def call_llm(messages: List[Dict[str,str]], temperature: float = 0.8, max_in_tokens: int = 12000) -> str:
    client = get_groq_client()
    if not client:
        return "⚠️ Model not available: configure GROQ_API_KEY in environment or Streamlit secrets."
    try:
        trimmed_msgs = []
        for m in messages:
            c = m.get("content","")
            if len(c) > max_in_tokens:
                c = c[:max_in_tokens]
            trimmed_msgs.append({"role": m["role"], "content": c})
        resp = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=trimmed_msgs,
            temperature=temperature
        )
        content = getattr(getattr(resp.choices[0],"message",{}),"content","") or getattr(resp.choices[0],"text","")
        return content.strip()
    except Exception as e:
        return f"⚠️ LLM error: {e}"

# -------------------------
# Prompt Builders (Product-specific)
# -------------------------
def build_context_block(retrieved: List[Dict[str,Any]]) -> Tuple[str, List[str]]:
    blocks = []
    cites = []
    for sn in retrieved:
        txt = materialize_text(sn)
        if not txt.strip():
            continue
        cite = format_citation(sn)
        block = f"[Source: {cite} | Score: {sn.get('score',0):.3f}]\n{txt}"
        blocks.append(block)
        cites.append(cite)
    return "\n\n".join(blocks), list(dict.fromkeys(cites))  # unique order

def build_sales_call_flow_prompt(brand_cfg: Dict[str,Any], persona: str, segment: str, tone: str,
                                 query: str, context_block: str, examples_density: int,
                                 strict_grounding: bool) -> List[Dict[str,str]]:
    brand = brand_cfg["display"]
    call_flow = brand_cfg["call_flow"]
    barriers = brand_cfg["barriers"]
    objections_map = brand_cfg.get("objections_map", {})

    grounding_rule = (
        "Only use facts found in the CONTEXT. If a required detail is missing, say so explicitly and proceed with best practice language without inventing data."
        if strict_grounding else
        "Prioritize the CONTEXT for facts. If needed, you may fill general best-practice phrasing, but never fabricate product claims."
    )

    sys = f"""You are an elite pharma sales coach generating PRODUCT-SPECIFIC call flows for {brand}.
- Audience persona: {persona}; Segment: {segment}; Tone: {tone}.
- Frame compliant, medically sound messaging. Never create off-label claims.
- {grounding_rule}
- Structure output in rich Markdown with these top-level headings:
  1) Call Objective
  2) Opening & Rapport
  3) Discovery & Probing (persona-tailored)
  4) Value Messages (evidence-based)
  5) Objection Handling (map to common barriers)
  6) Create Opportunities & Commitment
  7) Close & Clear Next Steps
  8) Full Role-Play Script (Rep vs HCP) — ~{examples_density} turns per stage
  9) Key Risks & Compliance Reminders
  10) Citations
- Use the brand call flow stages: {", ".join(call_flow)}.
- Typical barriers: {", ".join(barriers)}. Suggested tactics: {objections_map}.
- When uncertain, add a short 'Check official reference' note.
- Cite sources as [n] and list them at the end.
"""

    usr = f"""User request: "{query}"

CONTEXT (retrieved, ranked):
{context_block}

Produce a comprehensive, end-to-end sales call scenario for {brand}, with persona-tailored probes, evidence-backed messages, and realistic dialog (Rep: / HCP:). Include actionable commitments and next steps aligned to GSO/impact. Keep it specific to {brand}.
"""
    return [{"role": "system", "content": sys}, {"role": "user", "content": usr}]

def build_role_play_prompt(brand_cfg, persona, segment, tone, query, context_block, turns=10, strict_grounding=True):
    brand = brand_cfg["display"]
    grounding_rule = (
        "Use only facts from CONTEXT; if missing, keep neutral, best-practice dialog without adding product claims."
        if strict_grounding else
        "Use CONTEXT primarily; avoid fabricating claims."
    )
    sys = f"""You simulate a realistic role-play between a Sales Rep and an HCP about {brand}.
- Persona: {persona}; Segment: {segment}; Tone: {tone}.
- {grounding_rule}
- Output as alternating lines: Rep: ... / HCP: ...
- Include probing, reframing, handling one barrier, and a clear ask & commitment."""
    usr = f"""User request: "{query}"

CONTEXT:
{context_block}

Generate ~{turns} turns, product-specific to {brand}, with natural language."""
    return [{"role":"system","content":sys},{"role":"user","content":usr}]

def build_objection_prompt(brand_cfg, persona, segment, tone, query, context_block, strict_grounding=True):
    brand = brand_cfg["display"]
    sys = f"""You craft concise objection handling for {brand}.
- Persona: {persona}; Segment: {segment}; Tone: {tone}.
- {'Use only facts from CONTEXT.' if strict_grounding else 'Use CONTEXT as primary input.'}
- Return: (1) Empathic Acknowledge (2) Clarify (3) Evidence-backed Response (4) Check for Acceptance (5) Advance/Next step (6) Micro-script examples."""
    usr = f"""Objection/topic: "{query}"

CONTEXT:
{context_block}

Provide 2-3 variations tailored to common barriers listed in brand config when relevant."""
    return [{"role":"system","content":sys},{"role":"user","content":usr}]

def build_qna_prompt(brand_cfg, persona, segment, tone, query, context_block, strict_grounding=True):
    brand = brand_cfg["display"]
    sys = f"""You answer questions about {brand} for a field sales professional.
- Persona: {persona}; Segment: {segment}; Tone: {tone}.
- {'Use only facts from CONTEXT and state if something is not available.' if strict_grounding else 'Prefer CONTEXT; avoid fabricating claims.'}
- Cite sources as [n] and list them."""
    usr = f"""Question: "{query}"

CONTEXT:
{context_block}

Provide a clear, concise, product-specific answer."""
    return [{"role":"system","content":sys},{"role":"user","content":usr}]

def detect_intent(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["sales call flow","call flow","full call","scenario","end-to-end","script"]):
        return "sales_call_flow"
    if any(k in t for k in ["role play","role-play","simulate","dialog","conversation"]):
        return "role_play"
    if any(k in t for k in ["objection","barrier","pushback","concern"]):
        return "objection_handling"
    return "qna"

def attach_citations_markdown(cites: List[str]) -> str:
    if not cites:
        return "_No citations available from indexed sources._"
    md = []
    for i, c in enumerate(cites, 1):
        md.append(f"[{i}] {c}")
    return "\n".join(md)

# -------------------------
# Summaries (reuse groq summarizer)
# -------------------------
def simple_summary(text, bullets=6):
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- "+s for s in selected])

def model_summarize(text, bullets=6):
    client = get_groq_client()
    if client:
        try:
            prompt = f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role":"user","content":prompt}],
                temperature=0.2
            )
            content = getattr(getattr(resp.choices[0],"message",{}),"content","") or getattr(resp.choices[0],"text","")
            return content
        except:
            return simple_summary(text, bullets)
    else:
        return simple_summary(text, bullets)

# -------------------------
# Sidebar — Brand selection and controls
# -------------------------
with st.sidebar.expander("Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]

    segment = st.selectbox("Segment", bconf["segments"])
    st.session_state.segment = segment

    persona_sel = st.selectbox("HCP Persona", bconf["personas"], index=0)
    st.session_state.hcp_persona = persona_sel

    st.session_state.tone = st.selectbox("Tone", ["executive","coaching","persuasive","clinical"], index=0)
    st.session_state.temperature = st.slider("Creativity (Temperature)", 0.0, 1.2, st.session_state.temperature, 0.05)
    st.session_state.strict_grounding = st.checkbox("Strict to citations (no unstated facts)", value=True)
    st.session_state.examples_density = st.slider("Example density (turns per stage)", 2, 6, st.session_state.examples_density, 1)
    st.session_state.top_k = st.slider("RAG Top-K", 3, 15, st.session_state.top_k, 1)

# -------------------------
# Index the references + sales + uploads
# -------------------------
refs_folder = bconf.get("references_path","")
sales_folder = bconf.get("sales_path","")

# Combine raw text for summarization panels
combined_refs = ""
if os.path.exists(refs_folder):
    for f in sorted(os.listdir(refs_folder)):
        if f.lower().endswith((".pdf",".txt")):
            try:
                if f.lower().endswith(".pdf") and PdfReader:
                    for ck,_ in read_pdf_chunks(os.path.join(refs_folder,f)):
                        combined_refs += ck + "\n"
                else:
                    with open(os.path.join(refs_folder,f), "r", encoding="utf-8", errors="ignore") as fh:
                        combined_refs += fh.read() + "\n"
            except Exception:
                pass

combined_sales = ""
if os.path.exists(sales_folder):
    for f in sorted(os.listdir(sales_folder)):
        if f.lower().endswith((".pdf",".txt")):
            try:
                if f.lower().endswith(".pdf") and PdfReader:
                    for ck,_ in read_pdf_chunks(os.path.join(sales_folder,f)):
                        combined_sales += ck + "\n"
                else:
                    with open(os.path.join(sales_folder,f), "r", encoding="utf-8", errors="ignore") as fh:
                        combined_sales += fh.read() + "\n"
            except Exception:
                pass

if combined_refs.strip():
    st.session_state.medical_summary = model_summarize(combined_refs, bullets=6)
else:
    st.session_state.medical_summary = st.session_state.medical_summary or ""

if combined_sales.strip():
    st.session_state.sales_summary = model_summarize(combined_sales, bullets=6)
else:
    st.session_state.sales_summary = st.session_state.sales_summary or ""

# File uploader
st.sidebar.markdown("---")
st.sidebar.markdown("### Upload additional sources")
uploads = st.sidebar.file_uploader("PDF or TXT", type=["pdf","txt"], accept_multiple_files=True)
if uploads:
    if not st.session_state.uploaded_dir:
        st.session_state.uploaded_dir = tempfile.mkdtemp(prefix="rag_uploads_")
    for up in uploads:
        up_path = os.path.join(st.session_state.uploaded_dir, up.name)
        with open(up_path, "wb") as out:
            out.write(up.read())
    st.sidebar.success("Uploaded files added. Rebuild index if needed.")

# Build corpus
def rebuild_rag():
    corpus = []
    corpus += ingest_folder(refs_folder)
    corpus += ingest_folder(sales_folder)
    if st.session_state.uploaded_dir and os.path.exists(st.session_state.uploaded_dir):
        corpus += ingest_folder(st.session_state.uploaded_dir)
    st.session_state.rag_corpus = corpus
    backend = "sbert" if SBERT_AVAILABLE else "tfidf"
    st.session_state.vector_backend = backend if (SKLEARN_AVAILABLE or SBERT_AVAILABLE) else "none"
    st.session_state.rag_index = build_index(corpus, backend=st.session_state.vector_backend)
    st.session_state.rag_index_ready = True

colA, colB, colC = st.sidebar.columns(3)
with colA:
    if st.button("Rebuild Index"):
        rebuild_rag()
with colB:
    st.write("")
with colC:
    st.caption(f"Backend: **{st.session_state.vector_backend.upper()}**")

# Auto-build once
if not st.session_state.rag_index_ready:
    rebuild_rag()

# Sources panel (in sidebar)
with st.sidebar.expander("🔎 Indexed Sources"):
    if not st.session_state.rag_corpus:
        st.markdown("_No content found in references/sales/uploads._")
    else:
        counts = {}
        for d in st.session_state.rag_corpus:
            counts[d["filename"]] = counts.get(d["filename"], 0) + 1
        st.markdown("\n".join([f"- {k}: {v} chunks" for k,v in sorted(counts.items())]))

# -------------------------
# Main Interface
# -------------------------
st.markdown(f'<h2>💡 AI Sales Call Assistant — {bconf["display"]}</h2>', unsafe_allow_html=True)

# Quick actions
qc1, qc2, qc3 = st.columns(3)
with qc1:
    if st.button("✨ Generate Sales Call Flow"):
        st.session_state["preset_input"] = "Generate a full sales call flow"
with qc2:
    if st.button("🎭 Role-play"):
        st.session_state["preset_input"] = "Role play for this product"
with qc3:
    if st.button("🛡️ Handle Objection"):
        st.session_state["preset_input"] = "Objection: cost concerns from the HCP"

# Chat form (SAFE: clear_on_submit handles input reset)
with st.form("chat_form", clear_on_submit=True):
    default_text = st.session_state.get("preset_input", "")
    user_input = st.text_area("Ask the AI assistant...", value=default_text, height=80)
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        # clear preset to avoid re-populating on next run
        st.session_state["preset_input"] = ""
        # Run AI now
        # Build context & intent
        def build_context_and_intent(uq: str):
            brand_keywords = " ".join(bconf.get("keywords", []))
            expanded_query = f"{uq} {bconf['display']} {brand_keywords}"
            retrieved = retrieve(expanded_query, st.session_state.rag_index, top_k=st.session_state.top_k)
            context_block, cite_list = build_context_block(retrieved)
            intent = detect_intent(uq)
            return context_block, cite_list, intent

        st.session_state.chat_history.append({"role":"user","content":user_input})
        ctx_block, cite_list, intent = build_context_and_intent(user_input)

        if intent == "sales_call_flow":
            msgs = build_sales_call_flow_prompt(
                brand_cfg=bconf,
                persona=st.session_state.hcp_persona,
                segment=st.session_state.segment,
                tone=st.session_state.tone,
                query=user_input,
                context_block=ctx_block,
                examples_density=st.session_state.examples_density,
                strict_grounding=st.session_state.strict_grounding
            )
        elif intent == "role_play":
            turns = 8 + max(0, st.session_state.examples_density - 3) * 2
            msgs = build_role_play_prompt(
                brand_cfg=bconf,
                persona=st.session_state.hcp_persona,
                segment=st.session_state.segment,
                tone=st.session_state.tone,
                query=user_input,
                context_block=ctx_block,
                turns=turns,
                strict_grounding=st.session_state.strict_grounding
            )
        elif intent == "objection_handling":
            msgs = build_objection_prompt(
                brand_cfg=bconf,
                persona=st.session_state.hcp_persona,
                segment=st.session_state.segment,
                tone=st.session_state.tone,
                query=user_input,
                context_block=ctx_block,
                strict_grounding=st.session_state.strict_grounding
            )
        else:
            msgs = build_qna_prompt(
                brand_cfg=bconf,
                persona=st.session_state.hcp_persona,
                segment=st.session_state.segment,
                tone=st.session_state.tone,
                query=user_input,
                context_block=ctx_block,
                strict_grounding=st.session_state.strict_grounding
            )

        answer = call_llm(msgs, temperature=st.session_state.temperature)

        if cite_list:
            answer += "\n\n---\n**Citations**\n" + attach_citations_markdown(cite_list)

        st.session_state.chat_history.append({"role":"ai","content":answer})

# -------------------------
# Display chat
# -------------------------
for entry in st.session_state.chat_history:
    if entry["role"]=="user":
        st.markdown(f'<div class="user-bubble">{escape(entry["content"])}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="ai-message">
            <img src="{AI_AVATAR_URL}" class="ai-avatar" />
            <div class="ai-bubble">{entry['content']}</div>
        </div>
        """, unsafe_allow_html=True)

# -------------------------
# MAIN INTERFACE: Summaries (moved from sidebar)
# -------------------------
st.markdown("---")
st.markdown("## Reference Summaries")
col_sum_1, col_sum_2 = st.columns(2)

with col_sum_1:
    st.markdown("### 📚 Medical References Summary")
    st.markdown(st.session_state.medical_summary or "_No references indexed yet._")

with col_sum_2:
    st.markdown("### 💼 Sales Module Summary")
    st.markdown(st.session_state.sales_summary or "_No sales module indexed yet._")

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown("""
<div class="fixed-disclaimer">
💡 This tool is for internal sales support purposes only. Medical content must be verified with official sources and local compliance guidance.
</div>
""", unsafe_allow_html=True)
