import streamlit as st
import os
import re
import tempfile
import base64
import io
from datetime import datetime
from html import escape

# -------------------------
# Optional/soft imports
# -------------------------
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

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# Resources
# -------------------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
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
    .title-box{ background: rgba(255,255,255,0.75); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; position:relative; margin-bottom:12px; }
    .title-box img.left-logo{ position:absolute; left:12px; height:48px; }
    .title-box img.right-logo{ position:absolute; right:12px; height:48px; }

    .chat-bubble-user{ background: rgba(0,0,0,0.08); color:#1111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }

    .chat-bubble-ai{
        background: #ffffff;
        color:#000;
        padding:12px 16px;
        border-radius:12px;
        box-shadow: 0 1px 6px rgba(0,0,0,0.085);
        margin:8px 0;
        max-width:90%;
        white-space:pre-wrap;
    }

    .citation-box{ font-size:12px; color:#666; margin-left:6px; margin-bottom:6px; }
    .fixed-disclaimer{ font-size:12px; color:#444; margin-top:16px; opacity:0.9; }
    .step-title{ font-weight:700; margin-top:8px; }
    .story{ font-style:italic; margin:6px 0 10px 0; }
    ul.assist-list{ margin:6px 0 6px 18px; padding:0; }
    .objection{ background:#fff8f0; padding:8px; border-radius:8px; margin:6px 0; border:1px solid #ffe0c6;}
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# Background helper
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
                background: linear-gradient(90deg, rgba(255,140,0,0.08), rgba(255,165,0,0.03)),
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
# GROQ client (optional)
# -------------------------
def load_groq_client():
    api_key = os.getenv("GROQ_API_KEY", "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") or (st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else "")
    if not api_key or Groq is None:
        return None
    try:
        return Groq(api_key=api_key)
    except Exception:
        return None

# -------------------------
# Brand data
# -------------------------
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "specialties": ["GP", "Dermatologist", "Cardiology", "Endocrinology", "Immunology", "Internal Medicine", "Rheumatology"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/",
        "call_flow": ["Prepare", "Assess", "Create Opportunities", "Tailor", "Impact", "Close"],
        "objections": {
            "efficacy": "Focus on durable protection and age-agnostic efficacy evidence.",
            "safety": "Acknowledge common AEs, then contrast with risk of complications from shingles.",
            "cost": "Frame cost as prevention of downstream complications and reduce clinic workload."
        }
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
        "objections": {
            "efficacy": "Discuss durable responses in dMMR/MSI-H and appropriate patient selection.",
            "safety": "Share safety profile and monitoring guidance to reduce perceived risk.",
            "access": "Offer starter kits or initiation support and reimbursement pathways."
        }
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Side effect concerns", "Cost/coverage"],
        "specialties": ["GP", "Pulmonologist", "Internal Medicine", "Respiratory Specialist"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy/",
        "call_flow": ["Prepare", "Assess", "Create Opportunities", "Tailor", "Impact", "Close"],
        "objections": {
            "device": "Offer quick practical coaching and demo materials.",
            "coverage": "Explain access options and patient support programs.",
            "effectiveness": "Share comparative outcomes framed for real-world practice."
        }
    }
}

# -------------------------
# Persona helper
# -------------------------
EXTRA_PERSONAS = ["Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"]
def get_persona_options(brand_key):
    base = brand_data.get(brand_key, {}).get("personas", [])
    return list(dict.fromkeys(base + EXTRA_PERSONAS))

# -------------------------
# File reading & corpus
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
    return [{"score":1.0,"text":c,"meta":metas[i]} for i,c in enumerate(chunks) if query.lower() in c.lower()][:top_n]

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

# -------------------------
# Audio
# -------------------------
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
# Sidebar: filters
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]

    segment = st.selectbox("Segment", bconf["segments"])
    persona_options = get_persona_options(sel_brand)
    persona = st.selectbox("HCP Persona", persona_options)
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
# Load references and sales summaries
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
# PDF upload
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
# Persona & tone helpers, APACT flow
# -------------------------
def persona_profile(persona_name):
    """Return dict describing priorities, language style, quick wins for the persona."""
    p = persona_name.lower()
    profile = {"priority":"", "style":"", "quick_win":""}

    if "evidence" in p or "evidence-led" in p:
        profile["priority"] = "data & outcomes"
        profile["style"] = "precise, cite trial outcomes and comparative results"
        profile["quick_win"] = "show a 1-slide summary of key outcomes"
        return profile

    if "time" in p or "time-pressured" in p:
        profile["priority"] = "speed & simplicity"
        profile["style"] = "concise, action-oriented"
        profile["quick_win"] = "provide single-sentence scripts or checklists"
        return profile

    if "skeptical" in p:
        profile["priority"] = "safety & credibility"
        profile["style"] = "address objections first"
        profile["quick_win"] = "provide safety and trial data upfront"
        return profile

    if "early" in p or "early-adopter" in p:
        profile["priority"] = "innovation & differentiation"
        profile["style"] = "enthusiastic, highlight innovation"
        profile["quick_win"] = "pilot opportunity or co-create plan"

    # Default fallback
    profile.update({"priority":"clinician-focused","style":"clear & actionable","quick_win":"one-page leave-behind"})
    return profile

def objection_response(product_key, objection_key, persona):
    product = brand_data.get(product_key, {})
    base = product.get("objections", {})
    reply = base.get(objection_key, "Acknowledge concern, offer concise evidence, propose next step.")
    prof = persona_profile(persona)
    if "evidence" in persona.lower():
        return f"{reply} Provide trial highlights and 1-slide summary."
    if "time" in persona.lower():
        return f"{reply} Offer single-sentence script & checklist."
    if "skeptical" in persona.lower():
        return f"{reply} Show safety data & monitoring plan, propose pilot."
    if "early" in persona.lower():
        return f"{reply} Highlight differentiation & co-design small pilot."
    return f"{reply} (Tailored: {prof['quick_win']})"

def make_story_for_step(step, brand_key, persona_name, tone, snippet=None):
    prof = persona_profile(persona_name)
    snip_html = f"<div>Snippet: {escape(snippet)}</div>" if snippet else ""
    return f"<div class='step-title'>{escape(step)} ({escape(tone)})</div><div>Hook: {prof['priority']}</div><div>Example: {prof['style']}</div><div>Micro-action: {prof['quick_win']}</div>{snip_html}"

def generate_sales_flow(prompt: str, persona_name: str, tone: str, brand_key: str):
    snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=6)
    flow = brand_data.get(brand_key, {}).get("call_flow", [])
    parts = []
    for i, step in enumerate(flow):
        sn = snippets[i]["text"] if i < len(snippets) else ""
        parts.append(make_story_for_step(step, brand_key, persona_name, tone, snippet=sn))
    # APACT objections
    parts.append("<div class='step-title'>Objection Handling</div>")
    for obj in ["efficacy","safety","cost"]:
        parts.append(f"<div class='objection'><strong>{obj.title()} —</strong> {escape(objection_response(brand_key, obj, persona_name))}</div>")
    return "\n".join(parts)

def add_ai_response(prompt_text):
    header = f"<div class='step-title'>Acknowledge</div><div>Action-oriented call plan tailored to {escape(persona)} ({escape(tone)} tone)</div>"
    flow_html = generate_sales_flow(prompt_text, persona, tone, st.session_state.selected_brand)
    confirm = "<div class='step-title'>Next step</div><div>If acceptable, reply 'Yes' and draft 30s script + 1-page leave-behind.</div>"
    ai_html = "\n".join([header, flow_html, confirm])
    st.session_state.chat_history.append({"role":"assistant","content":ai_html,"citation":""})

# -------------------------
# Chat input & display
# -------------------------
chat_container = st.container()
with st.form("main_input_form", clear_on_submit=True):
    user_input = st.text_area("Ask something:", st.session_state.main_input, height=96)
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role":"user","content":user_input.strip()})
        add_ai_response(user_input.strip())
        st.session_state.main_input = ""

with chat_container:
    for idx, entry in enumerate(st.session_state.chat_history):
        if entry.get("role")=="user":
            st.markdown(f'<div class="chat-bubble-user">{escape(entry.get("content",""))}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-ai">{entry.get("content","")}</div>', unsafe_allow_html=True)
            plain = re.sub(r"<[^>]+>","",entry.get("content",""))[:1500]
            audio_b64 = generate_audio(plain)
            if audio_b64:
                st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")

st.markdown('<div class="fixed-disclaimer">💡 For internal sales support only. Verify medical info from official sources.</div>', unsafe_allow_html=True)
