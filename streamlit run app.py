# app_final.py - AI Sales Call Assistant (Merged, Persona-based Storytelling + Tone Variants)
# Features:
# - Product-specific sales flows (Shingrix, Jemperli, Trelegy)
# - Storytelling examples per call-flow step, tailored by persona and tone
# - Tone variants: executive, coaching, persuasive, clinical
# - PDF upload, local corpus search, summaries, audio generation (ElevenLabs/gTTS fallback)
# - Feedback (like/dislike/need more) with multi-turn handling
# - White AI bubbles and UI chrome
# - Generated output will NOT show any dependency/requirements lists

import streamlit as st
import os
import re
import tempfile
import base64
import io
from datetime import datetime
from html import escape

# Optional libs (soft imports)
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

try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except Exception:
    ELEVENLABS_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except Exception:
    PYTTSX3_AVAILABLE = False

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# Resources
# -------------------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

# -------------------------
# Session defaults
# -------------------------
def _init_session():
    defaults = {
        "chat_history": [],
        "main_input": "",
        "selected_brand": "shingrix",
        "temperature": 0.95,
        "search_mode": "deep",
        "medical_summary": "",
        "sales_summary": "",
        "uploaded_pdf_text": "",
        "pdf_summary": "",
        "feedback": {},
        "dislike_state": None,
        "language": "English",
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

_init_session()

# -------------------------
# CSS
# -------------------------
st.markdown(
    """
    <style>
    .title-box{ background: rgba(255,255,255,0.85); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; position:relative; margin-bottom:12px; }
    .title-box img.left-logo{ position:absolute; left:12px; height:48px; }
    .title-box img.right-logo{ position:absolute; right:12px; height:48px; }

    .chat-bubble-user{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }

    .chat-bubble-ai{
        background: #ffffff;
        color:#000;
        padding:12px 16px;
        border-radius:12px;
        box-shadow: 0 1px 6px rgba(0,0,0,0.08);
        margin:8px 0;
        max-width:90%;
        white-space:pre-wrap;
    }

    .citation-box{ font-size:12px; color:#666; margin-left:6px; margin-bottom:6px; }
    .fixed-disclaimer{ font-size:12px; color:#444; margin-top:16px; opacity:0.9; }
    .step-title{ font-weight:700; margin-top:8px; }
    .story{ font-style:italic; margin:6px 0 10px 0; }
    ul.assist-list{ margin:6px 0 6px 18px; padding:0; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# Optional background
# -------------------------
def set_dynamic_background(image_path):
    if not os.path.exists(image_path):
        return
    try:
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
        st.markdown(
            f"""
            <style>
            [data-testid="stAppViewContainer"] {{
                background: linear-gradient(90deg, rgba(255,140,0,0.12), rgba(255,165,0,0.06)),
                            url("data:image/png;base64,{encoded}");
                background-repeat: no-repeat;
                background-position: right top;
                background-size: cover;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass

set_dynamic_background(BACKGROUND_PATH)

# -------------------------
# GROQ client loader (optional)
# -------------------------
def load_groq_client():
    api_key = os.getenv("GROQ_API_KEY", "") or (st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else "")
    if not api_key or Groq is None:
        return None
    try:
        return Groq(api_key=api_key)
    except Exception:
        return None

# -------------------------
# Brand info
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
        "call_flow": ["Prepare", "Engage", "Create Opportunities", "Influence", "Impact GSO", "Analyze"],
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited eligibility", "Access/reimbursement issues"],
        "specialties": ["Oncologist", "Medical Oncologist"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli/",
        "call_flow": ["COCO", "Anchor", "Engage", "Close"],
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Side effect concerns", "Cost/coverage"],
        "specialties": ["GP", "Pulmonologist", "Respiratory Specialist"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy/",
        "call_flow": ["Prepare", "Engage", "Demonstrate", "Address Access", "Close"],
    }
}

# Ensure selected brand exists
brand_keys = list(brand_data.keys())
if st.session_state.selected_brand not in brand_keys:
    st.session_state.selected_brand = brand_keys[0]

# -------------------------
# Helper functions (file reading, corpus, summarize)
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
            sents = re.split(r'(?<=[\.\?\!])\s+', text)
            for i in range(0, max(1, len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i : i + chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename": fname, "folder": folder, "start": i})
    return chunks, metas

def local_search_snippets(query, chunks, metas, top_n=3):
    if not chunks:
        return []
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
    q = query.lower()
    for i, c in enumerate(chunks):
        if q in c.lower():
            out.append({"score": 1.0, "text": c, "meta": metas[i]})
            if len(out) >= top_n:
                break
    return out

def simple_summary(text, bullets=6):
    if not text:
        return ""
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- " + s for s in selected])

def model_summarize(text, bullets=6):
    if not text:
        return ""
    client = load_groq_client()
    if client:
        try:
            prompt = f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                                 messages=[{"role":"user","content":prompt}],
                                                 temperature=0.2)
            content = getattr(resp.choices[0].message, "content", None) or getattr(resp.choices[0], "text", "")
            return content
        except Exception:
            return simple_summary(text, bullets)
    else:
        return simple_summary(text, bullets)

def generate_audio(text):
    if not text:
        return ""
    if ELEVENLABS_AVAILABLE:
        try:
            elevenlabs.api_key = st.secrets.get("ELEVENLABS_API_KEY", "")
            audio_stream = elevenlabs.generate(text=text, voice="alloy", model="eleven_multilingual_v1", stream=True)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            with open(tmp.name, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
            with open(tmp.name, "rb") as fh:
                return base64.b64encode(fh.read()).decode()
        except Exception:
            pass
    if gTTS:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            gTTS(text=text, lang="en", slow=False).save(tmp.name)
            with open(tmp.name, "rb") as fh:
                return base64.b64encode(fh.read()).decode()
        except Exception:
            pass
    return ""

# -------------------------
# Sidebar filters + persona & tone
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]
    segment = st.selectbox("Segment", bconf["segments"])
    persona = st.selectbox("HCP Persona", bconf["personas"])
    barrier = st.multiselect("Doctor Barrier", bconf["barriers"])
    specialty = st.selectbox("Specialty", bconf["specialties"])
    objective = st.selectbox("Objective", ["Awareness", "Adoption", "Retention"])
    st.session_state.temperature = st.slider("Temperature", 0.0, 1.0, st.session_state.temperature, 0.05)
    st.session_state.search_mode = st.selectbox("Search mode", ["deep", "shallow"])
    st.session_state.language = st.radio("Language", ["English", "Arabic"])
    tone = st.selectbox("Tone", ["executive", "coaching", "persuasive", "clinical"], index=0)
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []
        st.experimental_rerun()

with st.sidebar.expander("🌐 Add External Reference URLs (one per line)", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT", "DOCX"], horizontal=True)

# -------------------------
# Title box
# -------------------------
st.markdown(f"""
<div class="title-box">
    <img src="{GSK_LOGO_RAW}" class="left-logo">
    <h2>💡 AI Sales Call Assistant — {bconf['display']}</h2>
    <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# -------------------------
# Load references and sales summaries (if folders exist)
# -------------------------
refs_folder = bconf.get("references_path", "")
sales_folder = bconf.get("sales_path", "")
combined_refs = ""
if os.path.exists(refs_folder):
    for f in sorted(os.listdir(refs_folder)):
        if f.lower().endswith((".pdf", ".txt")):
            combined_refs += read_file_text(os.path.join(refs_folder, f)) + "\n"
combined_sales = ""
if os.path.exists(sales_folder):
    for f in sorted(os.listdir(sales_folder)):
        if f.lower().endswith((".pdf", ".txt")):
            combined_sales += read_file_text(os.path.join(sales_folder, f)) + "\n"

if not st.session_state.medical_summary and combined_refs.strip():
    st.session_state.medical_summary = model_summarize(combined_refs, bullets=6)
if not st.session_state.sales_summary and combined_sales.strip():
    st.session_state.sales_summary = model_summarize(combined_sales, bullets=6)

with st.expander("📚 Medical References Summary", expanded=False):
    st.markdown(st.session_state.medical_summary or "No medical summary available.")
with st.expander("💼 Sales Module Summary", expanded=False):
    st.markdown(st.session_state.sales_summary or "No sales summary available.")

# -------------------------
# PDF Upload and summarize
# -------------------------
uploaded_file = st.file_uploader("Upload PDF for summary", type=["pdf"])
if uploaded_file is not None and PdfReader:
    try:
        reader = PdfReader(uploaded_file)
        pdf_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = pdf_text
        st.session_state.pdf_summary = model_summarize(pdf_text, bullets=6)
        st.success("PDF summarized successfully!")
    except Exception:
        st.error("Failed to read the uploaded PDF.")

if st.session_state.pdf_summary:
    with st.expander("📄 Uploaded PDF Summary", expanded=False):
        st.markdown(st.session_state.pdf_summary)

# -------------------------
# Build corpus
# -------------------------
corpus_folders = [refs_folder, sales_folder]
chunks, chunk_meta = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

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
# Storytelling generator util (now uses persona & tone)
# -------------------------
def tone_prefix(tone):
    if tone == "executive":
        return "(Executive)"
    if tone == "coaching":
        return "(Coaching)"
    if tone == "persuasive":
        return "(Persuasive)"
    return "(Clinical)"

def persona_adjust(persona):
    """Return a small tailoring string based on persona."""
    if "Uncommitted" in persona:
        return "focus on ease-of-implementation and low-effort wins"
    if "Reluctant" in persona:
        return "use concise evidence and time-saving workflows"
    if "Patient" in persona:
        return "use patient stories and adherence benefits"
    if "Committed" in persona:
        return "build on existing positive attitudes and scale adoption"
    if "Data-Driven" in persona:
        return "cite trial outcomes and response rates"
    if "Skeptical" in persona:
        return "anticipate safety questions and address them upfront"
    return "tailor to the clinician's priorities"

def make_story_for_step(step, brand_key, persona, tone, snippet=None):
    safe_snip = escape(snippet) if snippet else ""
    brand = brand_data.get(brand_key, {}).get("display", brand_key)
    persona_text = persona or "HCP"
    p_adj = persona_adjust(persona_text)
    t_pref = tone_prefix(tone)

    if step.lower().startswith("prepare"):
        story = f"<div class='step-title'>Prepare {t_pref}</div>"
        story += f"<div class='story'>Before the call: the rep reviews the clinic's patient mix and decides which quick win to lead with — {p_adj}.</div>"
        if safe_snip:
            story += f"<ul class='assist-list'><li><strong>Sales note:</strong> {safe_snip}</li></ul>"
        story += f"<div><em>Sample line:</em> 'Doctor, may I spend 60s on one practical change that helps your 60+ patients.' </div>"
        return story

    if step.lower().startswith("engage"):
        story = f"<div class='step-title'>Engage {t_pref}</div>"
        story += f"<div class='story'>Open with a question that uncovers pain points; tailor the language to the persona: {p_adj}.</div>"
        if safe_snip:
            story += f"<ul class='assist-list'><li><strong>Module tip:</strong> {safe_snip}</li></ul>"
        sample = "How are you currently identifying patients who would benefit most?"
        if tone == "executive":
            sample = "What's the simplest intervention that moves the needle for your clinic?"
        if tone == "coaching":
            sample = "Tell me how you usually introduce this option to patients — what's working?"
        if tone == "persuasive":
            sample = "Many doctors we've worked with saw immediate uptake after this one phrasing. Would you like it?"
        return story + f"<div><em>Sample line:</em> '{sample}' </div>"

    if "create" in step.lower() or "opportun" in step.lower():
        story = f"<div class='step-title'>Create Opportunities {t_pref}</div>"
        story += f"<div class='story'>Translate interest into concrete next steps — suggest a workflow, checklist or cohort approach ({p_adj}).</div>"
        if safe_snip:
            story += f"<ul class='assist-list'><li><strong>From sales module:</strong> {safe_snip}</li></ul>"
        action = "Offer a checklist and a nurse script to support recommendations."
        if tone == "executive":
            action = "Recommend a 4-week pilot focused on high-yield patients."
        if tone == "coaching":
            action = "Offer to role-play the 30s conversation with the nurse."
        return story + f"<div><em>Sample action:</em> '{action}' </div>"

    if step.lower().startswith("influence"):
        story = f"<div class='step-title'>Influence {t_pref}</div>"
        story += f"<div class='story'>Use a patient vignette and one key data point to overcome the chief barrier ({p_adj}).</div>"
        if safe_snip:
            story += f"<ul class='assist-list'><li><strong>Clinical excerpt:</strong> {safe_snip}</li></ul>"
        pitch = f"A patient 72yo avoided hospitalization after vaccination with {brand}."
        if tone == "clinical":
            pitch = f"Randomized data show a significant reduction in complication X in the relevant age group."
        return story + f"<div><em>Sample pitch:</em> '{pitch}' </div>"

    if "impact" in step.lower() or "gso" in step.lower():
        story = f"<div class='step-title'>Impact GSO {t_pref}</div>"
        story += f"<div class='story'>Frame the ask around clinic-level outcomes — patient throughput, preauthorization ease, or revenue where relevant ({p_adj}).</div>"
        if safe_snip:
            story += f"<ul class='assist-list'><li><strong>Service model:</strong> {safe_snip}</li></ul>"
        offer = "Propose a short pilot and agree success metrics."
        if tone == "persuasive":
            offer = "Propose an immediate opt-in, highlighting quick wins for the clinic and patients."
        return story + f"<div><em>Sample offer:</em> '{offer}' </div>"

    if step.lower().startswith("analy") or step.lower().startswith("post"):
        story = f"<div class='step-title'>Analyze {t_pref}</div>"
        story += f"<div class='story'>Follow-up with a concise summary, KPIs, and next meeting — keep content action-oriented ({p_adj}).</div>"
        if safe_snip:
            story += f"<ul class='assist-list'><li><strong>Reference:</strong> {safe_snip}</li></ul>"
        return story + "<div><em>Sample follow-up:</em> 'I'll email a one-page summary and propose a follow-up in two weeks.' </div>"

    # Fallback
    return f"<div class='step-title'>{escape(step)}</div><div class='story'>Short storytelling example for this step tailored to {escape(persona)} ({escape(tone)}).</div>"

# -------------------------
# Sales flow generators per brand
# -------------------------
def build_shingrix_flow(prompt, persona, tone, snippets):
    parts = []
    parts.append("<div><strong>Context:</strong> Shingrix sales call — tailored storytelling and actions.</div>")
    for idx, step in enumerate(brand_data['shingrix']['call_flow']):
        sn = snippets[idx]['text'] if idx < len(snippets) else ""
        parts.append(make_story_for_step(step, 'shingrix', persona, tone, snippet=sn))
    return "\n".join(parts)

def build_jemperli_flow(prompt, persona, tone, snippets):
    parts = []
    parts.append("<div><strong>Context:</strong> Jemperli call — COCO / Anchor / Engage / Close.</div>")
    for idx, step in enumerate(brand_data['jemperli']['call_flow']):
        sn = snippets[idx]['text'] if idx < len(snippets) else ""
        parts.append(make_story_for_step(step, 'jemperli', persona, tone, snippet=sn))
    return "\n".join(parts)

def build_trelegy_flow(prompt, persona, tone, snippets):
    parts = ["<div><strong>Context:</strong> Trelegy call — respiratory focus.</div>"]
    for idx, step in enumerate(brand_data['trelegy']['call_flow']):
        sn = snippets[idx]['text'] if idx < len(snippets) else ""
        parts.append(make_story_for_step(step, 'trelegy', persona, tone, snippet=sn))
    return "\n".join(parts)

# -------------------------
# Generate sales flow based on prompt (uses local snippets)
# -------------------------
def generate_sales_flow(prompt: str, persona: str, tone: str):
    p = prompt.lower()
    snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=6)

    if "shingrix" in p or "hzv" in p or "herpes zoster" in p:
        return build_shingrix_flow(prompt, persona, tone, snippets)

    if "jemperli" in p or "dmmr" in p or "msi-h" in p:
        return build_jemperli_flow(prompt, persona, tone, snippets)

    if "trelegy" in p or "copd" in p:
        return build_trelegy_flow(prompt, persona, tone, snippets)

    # Default generic structure
    default_steps = ["Prepare", "Engage", "Create Opportunities", "Influence", "Close"]
    parts = [f"<div><strong>Context:</strong> General sales call — tailored to {escape(persona)} ({escape(tone)}).</div>"]
    for idx, step in enumerate(default_steps):
        sn = snippets[idx]['text'] if idx < len(snippets) else ""
        parts.append(make_story_for_step(step, st.session_state.selected_brand, persona, tone, snippet=sn))
    return "\n".join(parts)

# -------------------------
# AI RESPONSE builder (integrates module and optional LLM)
# -------------------------
def add_ai_response(prompt, follow_up=False, dislike_choice=None):
    snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=6)
    persona_choice = persona
    tone_choice = tone
    flow_html = generate_sales_flow(prompt, persona_choice, tone_choice)

    header = "<div class='step-title'>Acknowledge</div><div>Thank you — I understand. Below is a stepwise call plan with examples.</div>"
    confirm = "<div class='step-title'>Confirm</div><div>Does this fit your needs? Reply 'Yes' to get a 30s script and a 1-page leave-behind.</div>"

    citation_files = ", ".join(sorted({s.get('meta',{}).get('filename','local') for s in snippets if s}))
    citation_html = f"<div class='citation-box'><strong>Sources:</strong> {escape(citation_files)}</div>" if citation_files else ""

    ai_html = "\n".join([header, flow_html, confirm, citation_html])
    st.session_state.chat_history.append({"role": "assistant", "content": ai_html, "citation": citation_files})

# -------------------------
# Build corpus from selected brand folders
# -------------------------
refs_folder = brand_data[st.session_state.selected_brand].get("references_path", "")
sales_folder = brand_data[st.session_state.selected_brand].get("sales_path", "")
corpus_folders = [refs_folder, sales_folder]
chunks, chunk_meta = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# Chat UI
# -------------------------
chat_container = st.container()

with st.expander("💡 Prompt Suggestions (Click to Expand)", expanded=False):
    suggs = make_suggestions(st.session_state.selected_brand, persona, barrier, segment, specialty, objective)
    sugg_cols = st.columns(3)
    for i, s in enumerate(suggs):
        col = sugg_cols[i % 3]
        if col.button(s, key=f"sugg_{i}"):
            st.session_state.main_input = s

with st.form("main_input_form", clear_on_submit=True):
    user_input = st.text_area("Ask something:", st.session_state.main_input, height=96)
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role": "user", "content": user_input.strip()})
        add_ai_response(user_input.strip())
        st.session_state.main_input = ""

with chat_container:
    for idx, entry in enumerate(st.session_state.chat_history):
        if entry.get("role") == "user":
            st.markdown(f'<div class="chat-bubble-user">{escape(entry.get("content",""))}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-ai">{entry.get("content","")}</div>', unsafe_allow_html=True)
            if entry.get("citation"):
                st.markdown(f'<div class="citation-box">{escape(entry.get("citation"))}</div>', unsafe_allow_html=True)
            audio_b64 = generate_audio(re.sub(r"<[^>]+>", "", entry.get("content",""))[:2000])
            if audio_b64:
                st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")

            # Feedback buttons
            fb_cols = st.columns(3)
            key_content = entry.get("content", "")
            if key_content not in st.session_state.feedback:
                if fb_cols[0].button("👍 Like", key=f"like_{idx}"):
                    st.session_state.feedback[key_content] = "like"
                if fb_cols[1].button("👎 Dislike", key=f"dislike_{idx}"):
                    st.session_state.feedback[key_content] = "dislike"
                    choices = ["Unclear", "Too long", "Not relevant"]
                    choice_cols = st.columns(len(choices))
                    for i, ch in enumerate(choices):
                        if choice_cols[i].button(ch, key=f"dislike_choice_{idx}_{i}"):
                            add_ai_response("Follow-up based on user dislike", follow_up=True, dislike_choice=ch)
                if fb_cols[2].button("ℹ️ Need More", key=f"needmore_{idx}"):
                    st.session_state.feedback[key_content] = "need_more"
                    add_ai_response("The user requested more information; expand the previous answer.", follow_up=True)

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown(
    """
    <div class="fixed-disclaimer">
    💡 This tool is for internal sales support purposes only. All medical info should be verified from official sources.
    </div>
    """,
    unsafe_allow_html=True,
)
