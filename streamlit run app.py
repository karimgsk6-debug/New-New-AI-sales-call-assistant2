# app.py - AI Sales Call Assistant (Final integrated, ready-to-run)
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
# Page config & assets
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
BACKGROUND_URL = REPO_RAW_BASE + "/background1.png"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# -------------------------
# GROQ API (set your key)
# -------------------------
GROQ_API_KEY = "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"  # <-- replace with your GROQ API key
GROQ_API_URL = "https://api.groq.ai/v1/llm"

# -------------------------
# Session defaults
# -------------------------
defaults = {
    "chat_history": [],  # list of dicts {"role":"user"/"assistant", "text":..., "audio_b64":...}
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.62,
    "search_mode": "deep",
    "language": "English",
    "reply_style": "balanced",
    "awaiting_style_pref": False,
    "pdf_docs": {},           # {brand: combined text}
    "pdf_summaries": {},      # {brand: summary}
    "followup_options": {},   # dynamic followups per message
    "feedback_stats": {"like":0,"dislike":0,"need_more":0}
}
for k,v in defaults.items():
    st.session_state.setdefault(k,v)

# Ensure nested dicts exist
for nk in ("medical_summary", "sales_summary", "pdf_summary", "feedback"):
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
# CSS / visuals
# -------------------------
st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}}
.header {{display:flex; align-items:center; justify-content:space-between; gap:12px; background: linear-gradient(90deg, rgba(255,255,255,0.92), rgba(255,255,255,0.85)); padding:10px 18px; border-radius:10px; margin-bottom:12px; box-shadow: 0 6px 18px rgba(0,0,0,0.06);}}
.header .title {{ text-align:center; flex:1; }}
.header img.left-logo, .header img.right-logo {{ height:56px; }}
.section-bubble {{ background: rgba(255,255,255,0.95); border-radius: 10px; padding:12px; margin-bottom:10px; box-shadow: 0 6px 18px rgba(11,22,55,0.04); }}
.chat-container {{ max-height:50vh; overflow-y:auto; padding:12px; background: rgba(255,255,255,0.95); border-radius:8px; margin-bottom:60px; }}
.chat-bubble-user {{ background: linear-gradient(90deg,#0078D7,#0066C8); color:white; padding:12px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto; box-shadow:0 2px 6px rgba(0,0,0,0.08); }}
.chat-bubble-ai {{ background: linear-gradient(90deg,#eef9ff,#e6f4ff); color:#000; padding:12px; border-radius:12px; margin:8px 0; max-width:78%; box-shadow:0 2px 6px rgba(0,0,0,0.04); }}
.feedback-row {{ display:flex; gap:8px; margin-top:8px; align-items:center; }}
.feedback-btn {{ background:#fff; border:1px solid #e6e9ee; padding:6px 10px; border-radius:8px; cursor:pointer; }}
.combined-fixed {{ position: fixed; left:20px; right:20px; bottom:18px; z-index:9999; background: rgba(255,255,255,0.98); padding:12px; border-radius:10px; box-shadow:0 12px 40px rgba(0,0,0,0.08); }}
.resizable-combined {{ resize: vertical; overflow: auto; border:1px solid #ddd; padding:10px; border-radius:8px; background:#fff; min-height:110px; max-height:400px; }}
.suggestion-pill {{ display:inline-block; padding:6px 12px; border-radius:20px; background:#f6f8fa; margin:4px; border:1px solid #e6e9ee; font-size:14px; cursor:pointer; }}
.fixed-small-text {{ font-size:12px; color:#555; margin-top:4px; text-align:right; }}
.fixed-disclaimer {{ position: fixed; left:0; right:0; bottom:0; background: rgba(255,255,255,0.7); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:13px; z-index:9997; }}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Utility functions: read, summarize, TF-IDF local search, audio, export
# -------------------------
def read_file_text_from_uploaded(uploaded_file):
    try:
        if hasattr(uploaded_file, "type") and "pdf" in uploaded_file.type and PdfReader:
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
    # Placeholder for a real LLM summarization; currently falls back to simple summary
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
            if not text: continue
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
    # insert gentle audible pauses
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
# Query GROQ (LLM) helper - uses uploaded + local context; returns text
# -------------------------
def query_groq(prompt: str, context_docs: list, max_tokens: int = 600) -> str:
    # Build a prompt that instructs LLM to answer concisely and not include reference dumps
    context_text = "\n\n".join([d for d in context_docs if d])
    payload = {
        "prompt": f"Use the following reference material to answer the user question concisely. Only provide the assistant response — do not paste or expose the reference documents.\n\nReferences:\n{context_text}\n\nUser question: {prompt}",
        "max_output_tokens": max_tokens
    }
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"} if GROQ_API_KEY and GROQ_API_KEY != "Add_GROQ_API_here" else {}
    if not headers:
        # No GROQ key: return a fallback placeholder answer
        return "GROQ API key not configured — this is a demo response. Upload references and set GROQ_API_KEY to enable full LLM answers."
    try:
        r = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=20)
        r.raise_for_status()
        resp = r.json()
        # Depending on GROQ response format, use output_text or something similar
        return resp.get("output_text") or resp.get("result") or str(resp)
    except Exception as e:
        return f"Error querying GROQ API: {e}"

# -------------------------
# Sidebar: Brand selection and (optional) brand-specific upload
# -------------------------
with st.sidebar:
    st.image(GSK_LOGO_RAW, width=150)
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
    st.subheader("Upload (brand-specific)")
    with st.expander("Upload PDF/TXT (brand)") :
        uploaded_side = st.file_uploader("Upload a PDF or TXT (sidebar)", type=["pdf","txt"], key="sidebar_upload")
        if uploaded_side:
            text = read_file_text_from_uploaded(uploaded_side)
            if text:
                st.session_state["pdf_docs"].setdefault(sel_brand, "")
                st.session_state["pdf_docs"][sel_brand] += "\n\n" + text
                st.session_state["pdf_summaries"][sel_brand] = model_summarize(st.session_state["pdf_docs"][sel_brand], bullets=6)
                st.success("Sidebar file added to brand reference and summarized.")
            else:
                st.error("Could not read uploaded file.")

    st.markdown("---")
    st.subheader("Export / Clear")
    export_format = st.selectbox("Export format", ["DOCX" if DOCX_AVAILABLE else "TXT", "TXT"])
    if st.button("🗑️ Clear Chat (all)"):
        st.session_state["chat_history"] = []
        st.session_state["followup_options"] = {}
        st.session_state["feedback_stats"] = {"like":0,"dislike":0,"need_more":0}
        st.rerun()

# -------------------------
# Header
# -------------------------
st.markdown(f"""
<div class="header">
  <div style="width:140px;"><img src="{GSK_LOGO_RAW}" class="left-logo"></div>
  <div class="title">
    <h1 style="margin:0">💡 AI Sales Call Assistant</h1>
    <div style="color:#666;font-size:14px;">{brand_data[st.session_state['selected_brand']]['display']} — APACT-guided</div>
  </div>
  <div style="width:140px;text-align:right;"><img src="{AI_LOGO_RAW}" class="right-logo"></div>
</div>
""", unsafe_allow_html=True)

# -------------------------
# MAIN UPLOAD area (moved to main interface) + show summaries
# -------------------------
st.subheader("📄 Upload Reference Documents (PDF / TXT / DOCX)")
uploaded_file_main = st.file_uploader("Upload a PDF / TXT / DOCX to use as reference (appears in context for answers)", type=["pdf","txt","docx"], key="main_upload")
if uploaded_file_main:
    content = read_file_text_from_uploaded(uploaded_file_main)
    if content:
        st.session_state["pdf_docs"].setdefault(st.session_state["selected_brand"], "")
        st.session_state["pdf_docs"][st.session_state["selected_brand"]] += "\n\n" + content
        st.session_state["pdf_summaries"][st.session_state["selected_brand"]] = model_summarize(st.session_state["pdf_docs"][st.session_state["selected_brand"]], bullets=6)
        st.success("Uploaded document added to context and summarized for brand.")
        st.rerun()

# -------------------------
# Build local corpus from repo + uploaded docs
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

# include uploaded brand docs if present
if brand in st.session_state["pdf_docs"]:
    local_docs.append(st.session_state["pdf_docs"][brand])

# build search corpus chunks+meta for local search
chunks, metas = build_corpus_for_folders([p for p in (refs_folder, sales_folder) if os.path.exists(p)], chunk_size_sentences=3)

# -------------------------
# Medical & Sales Summaries (smart bullets)
# -------------------------
st.subheader("Summaries")
col_med, col_sales = st.columns(2)
with col_med:
    st.markdown("**📚 Medical Summary**")
    med_text = st.session_state["medical_summary"].get(brand, "")
    if not med_text:
        combined = "\n".join([d for d in local_docs])
        med_text = model_summarize(combined, bullets=6) if combined else ""
        st.session_state["medical_summary"][brand] = med_text
    st.markdown(f'<div class="section-bubble">{med_text if med_text else "No medical references found."}</div>', unsafe_allow_html=True)
with col_sales:
    st.markdown("**💼 Sales Module Summary**")
    sales_text = st.session_state["sales_summary"].get(brand, "")
    if not sales_text:
        combined_sales = "\n".join([d for d in local_docs])
        sales_text = model_summarize(combined_sales, bullets=6) if combined_sales else ""
        st.session_state["sales_summary"][brand] = sales_text
    st.markdown(f'<div class="section-bubble">{sales_text if sales_text else "No sales module content found."}</div>', unsafe_allow_html=True)

# -------------------------
# Prompt suggestions (collapsible bubble) — above chat
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

suggestions = make_suggestions(brand, persona, barrier, segment, specialty, objective)
with st.expander("💡 Prompt Suggestions (click to expand)", expanded=False):
    st.markdown("<div style='margin-bottom:8px;color:#333;'>Click a suggestion to auto-send it.</div>", unsafe_allow_html=True)
    pills_html = " ".join([f'<span class="suggestion-pill">{escape(s)}</span>' for s in suggestions])
    st.markdown(pills_html, unsafe_allow_html=True)
    btn_cols = st.columns(min(4, len(suggestions)))
    for i, s in enumerate(suggestions):
        if btn_cols[i % len(btn_cols)].button(s, key=f"suggbtn_{i}"):
            st.session_state["chat_history"].append({"role":"user", "text": s})
            context_docs = local_docs.copy()
            ai_resp = query_groq(s, context_docs) if GROQ_API_KEY and GROQ_API_KEY != "Add_GROQ_API_here" else None
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
# Chat display
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

        # Inline feedback row with dynamic followups
        fb_key = f"fb_{idx}"
        st.markdown('<div class="feedback-row">', unsafe_allow_html=True)
        c1, c2, c3, c4 = st.columns([1,1,1,6])
        with c1:
            if st.button("👍 Like", key=f"like_{idx}"):
                st.session_state["feedback_stats"]["like"] += 1
                # optional short preference probe
                pref_text = "Thanks! Quick preference: 1) Short scripts, 2) Data bullets, 3) Role-plays — reply with 1/2/3."
                st.session_state["chat_history"].append({"role":"assistant","text":pref_text,"audio_b64":generate_audio_base64(pref_text)})
                st.rerun()
        with c2:
            if st.button("👎 Dislike", key=f"dislike_{idx}"):
                st.session_state["feedback_stats"]["dislike"] += 1
                followup_key = f"followup_{idx}"
                if GROQ_API_KEY and GROQ_API_KEY != "Add_GROQ_API_here":
                    fu_prompt = f"Generate 3 very short closed follow-up questions (each 5-10 words) to clarify or improve this assistant response:\n\n\"{text}\"\n\nReturn them as separate lines."
                    fu_resp = query_groq(fu_prompt, local_docs, max_tokens=150)
                    opts = [line.strip() for line in re.split(r'[\r\n]+', fu_resp) if line.strip()][:3]
                    if not opts:
                        opts = ["Make it shorter", "Focus on objections", "Add data points"]
                else:
                    opts = ["Make it shorter & punchy", "Focus on objections handling", "Add more persuasive language"]
                st.session_state["followup_options"][followup_key] = opts
                st.rerun()
        with c3:
            if st.button("🔄 Regenerate", key=f"more_{idx}"):
                st.session_state["feedback_stats"]["need_more"] += 1
                context_docs = local_docs.copy()
                regen_prompt = f"Please regenerate and expand this assistant answer for clarity and more practical steps:\n\nOriginal answer:\n{text}"
                if GROQ_API_KEY and GROQ_API_KEY != "Add_GROQ_API_here":
                    new_resp = query_groq(regen_prompt, context_docs)
                    audio_b64 = generate_audio_base64(new_resp)
                    st.session_state["chat_history"].append({"role":"assistant","text":new_resp,"audio_b64":audio_b64})
                else:
                    new_resp = text + "\n\n[Regenerated: please provide more details about implementation and examples.]"
                    audio_b64 = generate_audio_base64(new_resp)
                    st.session_state["chat_history"].append({"role":"assistant","text":new_resp,"audio_b64":audio_b64})
                st.rerun()
        with c4:
            fb_val = st.session_state.get("feedback", {}).get(fb_key, "")
            if fb_val:
                st.markdown(f"**Feedback:** {fb_val}")
        st.markdown('</div>', unsafe_allow_html=True)

        # Display follow-up options if present
        followup_key = f"followup_{idx}"
        if st.session_state.get("followup_options", {}).get(followup_key):
            st.markdown("💡 **Refine this answer — choose one:**")
            fcols = st.columns(len(st.session_state["followup_options"][followup_key]))
            for i, q in enumerate(st.session_state["followup_options"][followup_key]):
                if fcols[i].button(q, key=f"{followup_key}_opt_{i}"):
                    st.session_state["feedback_stats"]["need_more"] += 1
                    context_docs = local_docs.copy()
                    guided_prompt = f"User selected follow-up: '{q}'. Please regenerate the previous assistant answer to address that request, be concise and actionable.\n\nOriginal answer:\n{text}"
                    if GROQ_API_KEY and GROQ_API_KEY != "Add_GROQ_API_here":
                        new_text = query_groq(guided_prompt, context_docs)
                        audio_b64 = generate_audio_base64(new_text)
                        st.session_state["chat_history"].append({"role":"assistant","text":new_text,"audio_b64":audio_b64})
                    else:
                        new_text = text + f"\n\n[Regenerated for: {q}]"
                        audio_b64 = generate_audio_base64(new_text)
                        st.session_state["chat_history"].append({"role":"assistant","text":new_text,"audio_b64":audio_b64})
                    st.session_state["followup_options"].pop(followup_key, None)
                    st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Bottom input area (fixed) + small fixed text
# -------------------------
st.markdown('<div class="combined-fixed">', unsafe_allow_html=True)
st.markdown('<div class="resizable-combined">', unsafe_allow_html=True)

# Input box
main_text = st.text_area("Type your message or click a suggestion", value=st.session_state.get("main_input",""), key="main_input_widget", height=96)

c_send, c_clear, c_export = st.columns([1,1,1])
with c_send:
    if st.button("Send", key="send_main"):
        if main_text and main_text.strip():
            st.session_state["chat_history"].append({"role":"user", "text": main_text.strip()})
            context_docs = local_docs.copy()
            if GROQ_API_KEY and GROQ_API_KEY != "Add_GROQ_API_here":
                ai_text = query_groq(main_text.strip(), context_docs)
            else:
                snippets = local_search_snippets(main_text.strip(), chunks, metas, top_n=5)
                if snippets:
                    ai_text = "Relevant excerpts:\n" + "\n".join([f"- {s['text'][:220]}..." for s in snippets])
                else:
                    ai_text = "I couldn't find direct references locally. Please upload relevant documents or rephrase the question."
            audio_b64 = generate_audio_base64(ai_text)
            st.session_state["chat_history"].append({"role":"assistant","text":ai_text,"audio_b64":audio_b64})
            st.session_state["main_input"] = ""
            st.rerun()
with c_clear:
    if st.button("Clear input", key="clear_main_btn"):
        st.session_state["main_input"] = ""
        st.rerun()
with c_export:
    if st.button("Export latest assistant answer", key="export_btn"):
        last = None
        for e in reversed(st.session_state["chat_history"]):
            if e.get("role") in ("assistant","ai"):
                last = e.get("text","")
                break
        if last:
            bts, fname = export_call_flow_bytes(last, fmt="docx" if export_format == "DOCX" and DOCX_AVAILABLE else "txt")
            st.download_button("Download export", data=bts, file_name=fname)
            st.success("Export prepared.")
        else:
            st.warning("No assistant content to export.")

# small fixed text under input (required)
st.markdown('<div class="fixed-small-text">Please refer to Write Right Principles course: BUS-LGL-WRJA-001</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Mini dashboard (simple)
# -------------------------
st.markdown("---")
st.markdown(f"""
<div style="display:flex; gap:18px; justify-content:center; margin-bottom:10px;">
  <div style="background:#fff;padding:8px 12px;border-radius:8px;">💬 Calls: {len([m for m in st.session_state['chat_history'] if m.get('role')=='assistant'])}</div>
  <div style="background:#fff;padding:8px 12px;border-radius:8px;">📄 Uploaded Docs: {len(st.session_state['pdf_docs'])}</div>
  <div style="background:#fff;padding:8px 12px;border-radius:8px;">👍 {st.session_state['feedback_stats']['like']}</div>
  <div style="background:#fff;padding:8px 12px;border-radius:8px;">👎 {st.session_state['feedback_stats']['dislike']}</div>
  <div style="background:#fff;padding:8px 12px;border-radius:8px;">🔄 {st.session_state['feedback_stats']['need_more']}</div>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Footer disclaimer (fixed)
# -------------------------
st.markdown(f'<div class="fixed-disclaimer">⚠️ Internal tool — outputs are grounded in uploaded and repository references. Verify clinical/compliance before external use.</div>', unsafe_allow_html=True)
