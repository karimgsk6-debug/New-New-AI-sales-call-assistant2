# app_final_merged_ready.py - Fully merged AI Sales Call Assistant with RAG references
# Features:
# - Multi-brand support: Shingrix, Jemperli, Trelegy
# - Persona + HCP personality + EXTRA_PERSONAS
# - Tone variants (executive, coaching, persuasive, clinical)
# - Persona-aware, explanatory storytelling call flows with CTAs
# - Local RAG from brand references + PDF upload
# - Audio: ElevenLabs -> gTTS fallback
# - Futuristic hologram avatar on left of every AI message
# - Feedback buttons, prompt suggestions, export options

import streamlit as st
import os
import re
import tempfile
import base64
import io
from datetime import datetime
from html import escape

# Optional imports
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
# Resources & Avatar
# -------------------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"

# -------------------------
# Session defaults
# -------------------------
def _init_session():
    defaults = {
        "chat_history": [],
        "main_input": "",
        "selected_brand": "shingrix",
        "temperature": 0.35,
        "search_mode": "deep",
        "medical_summary": "",
        "sales_summary": "",
        "uploaded_pdf_text": "",
        "pdf_summary": "",
        "feedback": {},
        "dislike_state": None,
        "language": "English",
        "hcp_persona": "Uncommitted Vaccinator",
        "hcp_personality": "Friendly",
        "tone": "executive",
        "specialty": "",
        "objective": "Awareness"
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

_init_session()

# -------------------------
# CSS for hologram avatar + chat bubbles
# -------------------------
st.markdown(
    """
    <style>
    .title-box{ background: rgba(255,255,255,0.85); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; position:relative; margin-bottom:12px; }
    .title-box img.left-logo{ position:absolute; left:12px; height:48px; }
    .title-box img.right-logo{ position:absolute; right:12px; height:48px; }

    /* User bubble */
    .chat-bubble-user{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }

    /* AI bubble with avatar on left */
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
                background: linear-gradient(90deg, rgba(255,140,0,0.06), rgba(255,165,0,0.02)),
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
        "call_flow": ["Prepare", "Engage", "Create Opportunities", "Influence", "Impact GSO", "Post-Call Analysis"],
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
        "call_flow": ["Prepare", "Engage", "Demonstrate", "Address Access", "Close"],
        "objections": {
            "device": "Offer quick practical coaching and demo materials.",
            "coverage": "Explain access options and patient support programs.",
            "effectiveness": "Share comparative outcomes framed for real-world practice."
        }
    }
}

# -------------------------
# Extended personas
# -------------------------
EXTRA_PERSONAS = ["Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"]
def get_persona_options(brand_key):
    base = brand_data.get(brand_key, {}).get("personas", [])
    return base + [p for p in EXTRA_PERSONAS if p not in base]

# -------------------------
# Helpers: file read, corpus, search
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
    q = (query or "").lower()
    for i, c in enumerate(chunks):
        if q and q in c.lower():
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
    return simple_summary(text, bullets)

# -------------------------
# Audio generation
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
# Persona profile & objection helpers
# -------------------------
def persona_profile(persona_name):
    p = (persona_name or "").lower()
    profile = {"priority":"clinician-focused", "style":"clear and helpful", "quick_win":"short actionable commitment"}
    if "evidence" in p:
        profile.update({"priority":"data & outcomes", "style":"precise, cite trial outcomes and comparative results", "quick_win":"1-slide summary of key outcomes"})
    elif "time" in p:
        profile.update({"priority":"speed & simplicity", "style":"concise, action-oriented, minimal detail", "quick_win":"nurse-ready checklist"})
    elif "skeptical" in p:
        profile.update({"priority":"safety & credibility", "style":"address objections first, use trusted sources", "quick_win":"safety data & monitoring plan"})
    elif "early" in p:
        profile.update({"priority":"innovation & differentiation", "style":"enthusiastic, highlight first-mover benefits", "quick_win":"pilot/benchmark opportunity"})
    elif "uncommitted" in p:
        profile.update({"priority":"ease & persuasion", "style":"relatable, low-friction", "quick_win":"leave-behind patient education"})
    elif "reluctant" in p:
        profile.update({"priority":"efficiency & risk reduction", "style":"evidence-lite + workflow support", "quick_win":"nurse script and time-saving tip"})
    elif "patient" in p:
        profile.update({"priority":"patient experience", "style":"storytelling and adherence focus", "quick_win":"patient leaflet and story-based hook"})
    elif "committed" in p:
        profile.update({"priority":"scale & advocacy", "style":"build on success with scaling ideas", "quick_win":"co-create local guideline prompts"})
    return profile

def objection_response(product_key, objection_key, persona):
    product = brand_data.get(product_key, {})
    base = product.get("objections", {})
    reply = base.get(objection_key, "Acknowledge the concern, offer concise evidence, and propose a low-effort next step.")
    prof = persona_profile(persona)
    if "evidence" in (persona or "").lower():
        return f"Answer (Evidence-led): {reply} Provide trial highlights and one quick citation; offer to share a 1-page evidence summary."
    if "time" in (persona or "").lower():
        return f"Answer (Time-pressured): {reply} Then offer a single-sentence script and a nurse checklist to make adoption painless."
    if "skeptical" in (persona or "").lower():
        return f"Answer (Skeptical): {reply} Start by acknowledging, then show safety data and a monitoring plan; propose a conservative pilot."
    if "early" in (persona or "").lower():
        return f"Answer (Early-adopter): {reply} Highlight differentiation and offer to co-design a small pilot with outcome monitoring."
    return f"{reply} (Tailored suggestion: {prof['quick_win']})"

# -------------------------
# RAG-based Sales Flow Generator
# -------------------------
def generate_sales_flow(prompt: str, persona_name: str, tone: str, specialty: str = None, objective: str = None):
    p = (prompt or "").lower()
    persona = persona_name or st.session_state.hcp_persona
    tone_choice = (tone or st.session_state.tone).lower()
    specialty = specialty or ""
    objective = objective or ""
    prof = persona_profile(persona)

    # Determine product
    if "shingrix" in p or "hzv" in p or "herpes zoster" in p:
        product_key = "shingrix"
    elif "jemperli" in p or "dmmr" in p or "msi-h" in p:
        product_key = "jemperli"
    elif "trelegy" in p or "copd" in p:
        product_key = "trelegy"
    else:
        product_key = st.session_state.selected_brand

    steps = brand_data.get(product_key, {}).get("call_flow", ["Prepare","Engage","Create Opportunities","Influence","Close"])
    refs_folder = brand_data.get(product_key, {}).get("references_path", "")
    sales_folder = brand_data.get(product_key, {}).get("sales_path", "")
    corpus_folders = [refs_folder, sales_folder]
    chunks, chunk_meta = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

    def retrieve_snippets(step_name, top_n=3):
        query = f"{product_key} {step_name} sales call"
        results = local_search_snippets(query, chunks, chunk_meta, top_n=top_n)
        return [r["text"] for r in results]

    parts = []
    header = f"<div class='step-title'>Tailored sales call plan — {escape(brand_data.get(product_key, {}).get('display', product_key))}</div>"
    header += f"<div>Target: <strong>{escape(persona)}</strong>"
    if specialty:
        header += f" • Specialty: <strong>{escape(specialty)}</strong>"
    if objective:
        header += f" • Objective: <strong>{escape(objective)}</strong>"
    header += f"</div>"
    header += f"<div class='story'>Insight: Focus on <strong>{escape(prof['priority'])}</strong> — communicate in a {escape(prof['style'])} style.</div>"
    parts.append(header)

    for step in steps:
        s_html = f"<div class='step-title'>{escape(step)}</div>"
        snippets = retrieve_snippets(step, top_n=3)
        for snip in snippets:
            s_html += f"<div class='story'>• {escape(snip)}</div>"
        for obj in brand_data.get(product_key, {}).get("objections", {}):
            s_html += f"<div class='objection'><strong>{obj.title()} —</strong> {escape(objection_response(product_key, obj, persona))}</div>"
        s_html += f"<div><strong>CTA ({escape(step)}):</strong> Define clear next step for HCP.</div>"
        parts.append(s_html)

    parts.append(
        "<div class='step-title'>Action Plan (Next Steps)</div>"
        "<ol class='assist-list'>"
        "<li>Send concise slide/evidence summary</li>"
        "<li>Agree pilot with defined metric</li>"
        "<li>Schedule follow-up & review outcomes</li>"
        "</ol>"
    )
    return "\n".join(parts)

def add_ai_response_from_prompt(prompt_text):
    persona_choice = st.session_state.get("hcp_persona", "")
    tone_choice = st.session_state.get("tone", "executive")
    specialty = st.session_state.get("specialty", "")
    objective = st.session_state.get("objective", "Awareness")
    ai_html = generate_sales_flow(prompt_text, persona_choice, tone_choice, specialty=specialty, objective=objective)
    st.session_state.chat_history.append({"role":"assistant","content":ai_html,"citation":""})

# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    st.title("🧠 AI Sales Assistant")
    st.selectbox("Select Brand", list(brand_data.keys()), key="selected_brand")
    st.selectbox("Select HCP Persona", get_persona_options(st.session_state.selected_brand), key="hcp_persona")
    st.selectbox("Select Tone", ["executive","coaching","persuasive","clinical"], key="tone")
    st.text_input("Specialty / Focus", key="specialty")
    st.text_input("Objective", key="objective")
    st.slider("Temperature", 0.0, 1.0, st.session_state.temperature, key="temperature")
    st.radio("Search Mode", ["deep","quick"], key="search_mode")

# -------------------------
# Main Input
# -------------------------
st.text_area("Type your sales prompt here:", value=st.session_state.main_input, key="main_input", height=120)
if st.button("Generate AI Sales Call"):
    if st.session_state.main_input.strip():
        add_ai_response_from_prompt(st.session_state.main_input.strip())

# -------------------------
# Display chat
# -------------------------
for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        st.markdown(f"<div class='user-bubble'>{escape(msg['content'])}</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            f"<div class='ai-message'><img class='ai-avatar' src='{AI_AVATAR}'/><div class='ai-bubble'>{msg['content']}</div></div>",
            unsafe_allow_html=True
        )

st.markdown("<div class='fixed-disclaimer'>© AI Sales Assistant — Internal use only. Not for external distribution.</div>", unsafe_allow_html=True)
