# app_final_merged.py - Fully merged AI Sales Call Assistant
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

# Soft imports
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

# Futuristic hologram avatar URL (replace if you have another)
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

# -------------------------
# Summarizer (local fallback)
# -------------------------
def model_summarize(text, bullets=6):
    # Using local simple summarizer; optional Groq could be used here if configured
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
# NEW: Enhanced generate_sales_flow (no external LLM dependency)
# Produces long, structured, persona-aware HTML response with CTAs
# -------------------------
def generate_sales_flow(prompt: str, persona_name: str, tone: str, specialty: str = None, objective: str = None):
    p = (prompt or "").lower()
    persona = persona_name or st.session_state.hcp_persona
    tone_choice = (tone or st.session_state.tone).lower()
    specialty = specialty or ""
    objective = objective or ""
    prof = persona_profile(persona)

    # local snippets (small RAG)
    snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=6) if chunks else []
    snippet_texts = [s["text"] for s in snippets]

    # Helper: produce a short evidence block if snippets available
    def evidence_block():
        if not snippet_texts:
            return ""
        out = "<div><strong>Relevant snippets from your references:</strong></div>"
        for s in snippet_texts[:3]:
            out += f"<div class='story'>• {escape(s[:300].strip())}...</div>"
        return out

    # Determine product/flow
    if "shingrix" in p or "hzv" in p or "herpes zoster" in p:
        product_key = "shingrix"
        steps = brand_data[product_key]["call_flow"]
    elif "jemperli" in p or "dmmr" in p or "msi-h" in p:
        product_key = "jemperli"
        steps = brand_data[product_key]["call_flow"]
    elif "trelegy" in p or "copd" in p:
        product_key = "trelegy"
        steps = brand_data[product_key]["call_flow"]
    else:
        # fallback to selected brand
        product_key = st.session_state.selected_brand
        steps = brand_data.get(product_key, {}).get("call_flow", ["Prepare","Engage","Create Opportunities","Influence","Close"])

    # Build HTML response
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

    # Detailed step-by-step
    for step in steps:
        s_html = ""
        step_key = step.lower()
        if "prepare" in step_key:
            s_html += f"<div class='step-title'>Prepare</div>"
            s_html += f"<div>• Identify the persona: <strong>{escape(persona)}</strong>"
            if specialty:
                s_html += f", specialty: <strong>{escape(specialty)}</strong>"
            s_html += f"</div>"
            s_html += f"<div>• Objectives: <strong>{escape(objective or 'Awareness')}</strong></div>"
            s_html += f"<div>• Patient types: <strong>Adults 50+</strong> (adjust per specialty)</div>"
            s_html += f"<div class='story'>Key insight: Shingles risk increases with age; prevention reduces severe pain & complications.</div>"
            s_html += f"<div><strong>Prep checklist:</strong><ul class='assist-list'><li>One-sentence clinic insight</li><li>Top 2 trial endpoints to cite</li><li>One-line pilot proposal</li></ul></div>"
            s_html += evidence_block()
            s_html += f"<div><strong>CTA (Prep):</strong> Email a single-slide summary and request 5 minutes to review it at start of call.</div>"

        elif "engage" in step_key:
            open_line = f'Hello, Dr. [LastName]. I am [YourName] from GSK. Quick question: how are you currently approaching shingles prevention for patients 50+?'
            if tone_choice == "executive":
                open_line = 'Hello, Dr. [LastName]. Quick question: what is the highest-leverage change we could make this quarter to protect your 50+ patients?'
            if tone_choice == "coaching":
                open_line = 'Hi Dr. [LastName], can you walk me through how you typically introduce shingles prevention in a 60s consult?'
            s_html += f"<div class='step-title'>Engage</div>"
            s_html += f"<div>• Start conversation (example): \"{escape(open_line)}\"</div>"
            s_html += f"<div>• Capture attention: \"Did you know most adults 50+ are at risk and shingles can cause long-term neuralgia?\"</div>"
            s_html += f"<div class='story'>Goal: Make the issue locally relevant; tie to the clinician's caseload or clinic KPI.</div>"
            s_html += f"<div><strong>CTA (Engage):</strong> Get agreement to explore one eligible patient cohort (e.g., next 10 patients 50+).</div>"

        elif "create" in step_key or "opportun" in step_key:
            s_html += f"<div class='step-title'>Create Opportunities</div>"
            s_html += f"<div>• Identify gaps: Ask direct diagnostic questions: 'Are there barriers in delivery, documentation, or patient acceptance?'</div>"
            s_html += f"<div>• Solution framing: Present practical solutions — nurse checklist, standing order, dedicated clinic slot.</div>"
            s_html += f"<div class='story'>Example: \"Let's pilot with 8 eligible patients using a nurse checklist and measure uptake in 4 weeks.\"</div>"
            s_html += f"<div><strong>CTA (Create):</strong> Secure agreement for a small pilot and define one metric (e.g., vaccination rate change over 4 weeks).</div>"

        elif "influence" in step_key:
            s_html += f"<div class='step-title'>Influence</div>"
            s_html += f"<div>• Present evidence: cite trial outcomes, real-world benefit, and safety profile.</div>"
            s_html += f"<div class='story'>Example pitch: 'In trial X, this vaccine reduced shingles incidence by Y% at Z months — it cuts PHN risk substantially.'</div>"
            # persona-specific objection handling sample
            s_html += f"<div><strong>Handle objections:</strong> {escape(objection_response(product_key, 'efficacy', persona))}</div>"
            s_html += f"<div><strong>CTA (Influence):</strong> Ask: 'Which of your patients is most like this vignette — can we try with one today?'</div>"

        elif "impact" in step_key or "gso" in step_key or "impact gso" in step_key:
            s_html += f"<div class='step-title'>Impact GSO</div>"
            s_html += f"<div>• Link to clinic-level outcomes: throughput, fewer follow-ups for complications, patient satisfaction.</div>"
            s_html += f"<div class='story'>Example ask: 'Would you be open to starting with your next 10 eligible patients and reviewing outcomes in 4 weeks?'</div>"
            s_html += f"<div><strong>CTA (Impact):</strong> Agree on success criteria and a 2-week check-in date; offer send-one-slide plan.</div>"

        elif "post" in step_key or "analy" in step_key or "post-call" in step_key:
            s_html += f"<div class='step-title'>Post-Call Analysis</div>"
            s_html += f"<div>• Record insights: objections, commitments, staff readiness.</div>"
            s_html += f"<div>• CRM update: Add outcomes, next steps, proposed pilot metrics.</div>"
            s_html += f"<div class='story'>Example: 'We'll email a 1-page summary with the agreed metric and schedule a 2-week check-in.'</div>"
            s_html += f"<div><strong>CTA (Post-Call):</strong> Schedule follow-up and attach leave-behind material to the calendar invite.</div>"
        else:
            s_html += f"<div class='step-title'>{escape(step)}</div>"
            s_html += f"<div class='story'>Practical example for {escape(persona)} ({escape(tone_choice)}).</div>"

        parts.append(s_html)

    # Add generic objection handling block (persona tailored)
    parts.append("<div class='step-title'>Objection Handling — Quick Wins</div>")
    common_objs = list(brand_data.get(product_key, {}).get("objections", {}).keys())[:3]
    for obj in common_objs:
        parts.append(f"<div class='objection'><strong>{obj.title()} —</strong> {escape(objection_response(product_key, obj, persona))}</div>")

    # Final CTA summary
    final_cta = (
        "<div class='step-title'>Action Plan (Next Steps)</div>"
        "<ol class='assist-list'>"
        "<li>Send 1-slide evidence summary by email (today).</li>"
        "<li>Agree pilot: start with 8–10 eligible patients, measure uptake in 4 weeks.</li>"
        "<li>Schedule a short follow-up (2-week check-in) and propose measurement metric.</li>"
        "</ol>"
        "<div><strong>Ask the HCP now:</strong> 'If I send a concise slide and the nurse checklist, can we start the pilot next week?'</div>"
    )
    parts.append(final_cta)

    return "\n".join(parts)

# -------------------------
# Chat: add_ai_response and renderers
# -------------------------
def add_ai_response_from_prompt(prompt_text):
    # Build persona, tone, specialty, objective from session or sidebar
    persona_choice = st.session_state.get("hcp_persona", "")
    tone_choice = st.session_state.get("tone", "executive")
    specialty = st.session_state.get("specialty", "")
    objective = st.session_state.get("objective", "Awareness")
    ai_html = generate_sales_flow(prompt_text, persona_choice, tone_choice, specialty=specialty, objective=objective)
    st.session_state.chat_history.append({"role":"assistant","content":ai_html,"citation":""})

HOLO_AVATAR = AI_AVATAR

def render_ai_message(message_html):
    st.markdown(
        f"""
        <div class="ai-message">
            <img src="{HOLO_AVATAR}" class="ai-avatar" />
            <div class="ai-bubble">{message_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_user_message(msg):
    st.markdown(f'<div class="user-bubble">{escape(msg)}</div>', unsafe_allow_html=True)

# -------------------------
# Sidebar: controls & selections
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]

    segment = st.selectbox("Segment", bconf["segments"])
    persona_options = get_persona_options(sel_brand)
    persona_sel = st.selectbox("HCP Persona", persona_options, index=persona_options.index(st.session_state.hcp_persona) if st.session_state.hcp_persona in persona_options else 0)
    st.session_state.hcp_persona = persona_sel

    # HCP personality (assertive, masked, friendly, details-oriented, skeptic)
    hcp_personality = st.selectbox("HCP Personality", ["Assertive", "Masked", "Friendly", "Details-oriented", "Skeptic"], index=0)
    st.session_state.hcp_personality = hcp_personality

    barrier = st.multiselect("Doctor Barrier", bconf["barriers"])
    specialty = st.selectbox("Specialty", bconf["specialties"])
    st.session_state.specialty = specialty

    objective = st.selectbox("Objective", ["Awareness", "Adoption", "Retention"])
    st.session_state.objective = objective

    st.session_state.temperature = st.slider("Temperature", 0.0, 1.0, st.session_state.temperature, 0.05)
    st.session_state.search_mode = st.selectbox("Search mode", ["deep", "shallow"])
    st.session_state.language = st.radio("Language", ["English", "Arabic"])
    st.session_state.tone = st.selectbox("Tone", ["executive", "coaching", "persuasive", "clinical"], index=["executive","coaching","persuasive","clinical"].index(st.session_state.tone) if st.session_state.tone in ["executive","coaching","persuasive","clinical"] else 0)
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
st.markdown(
    f"""
    <div class="title-box">
        <img src="{GSK_LOGO_RAW}" class="left-logo">
        <h2>💡 AI Sales Call Assistant — {brand_data[st.session_state.selected_brand]['display']}</h2>
        <img src="{AI_LOGO_RAW}" class="right-logo">
    </div>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# Load and summarize references (brand-specific)
# -------------------------
bconf = brand_data[st.session_state.selected_brand]
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
# PDF upload (brand-specific)
# -------------------------
uploaded_file = st.file_uploader("Upload PDF for summary (brand-specific)", type=["pdf"])
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
# Build corpus for local search (brand-specific folders)
# -------------------------
corpus_folders = [refs_folder, sales_folder]
chunks, chunk_meta = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# Prompt suggestions and input form
# -------------------------
chat_container = st.container()

with st.expander("💡 Prompt Suggestions (Click to Expand)", expanded=False):
    suggs = [
        f"Generate a {brand_data[st.session_state.selected_brand]['display']} sales call for {st.session_state.hcp_persona} in {st.session_state.tone} tone",
        f"How to handle an efficacy objection for {brand_data[st.session_state.selected_brand]['display']}?",
        "Short 30s script for the next call",
        "Pilot offer for 10 patients — example script"
    ]
    sugg_cols = st.columns(2)
    for i, s in enumerate(suggs):
        col = sugg_cols[i % 2]
        if col.button(s, key=f"sugg_{i}"):
            st.session_state.main_input = s

with st.form("main_input_form", clear_on_submit=True):
    user_input = st.text_area("Ask something:", st.session_state.main_input, height=96)
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role":"user","content":user_input.strip()})
        add_ai_response_from_prompt(user_input.strip())
        st.session_state.main_input = ""

# -------------------------
# Display chat history (AI avatar on left)
# -------------------------
with chat_container:
    for idx, entry in enumerate(st.session_state.chat_history):
        if entry.get("role") == "user":
            render_user_message(entry.get("content",""))
        else:
            render_ai_message(entry.get("content",""))
            if entry.get("citation"):
                st.markdown(f'<div class="citation-box">{escape(entry.get("citation"))}</div>', unsafe_allow_html=True)

            # audio (plain text)
            plain = re.sub(r"<[^>]+>", "", entry.get("content",""))[:1500]
            audio_b64 = generate_audio(plain)
            if audio_b64:
                st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")

            # feedback
            fb_cols = st.columns(3)
            key_content = entry.get("content","")
            if key_content not in st.session_state.feedback:
                if fb_cols[0].button("👍 Like", key=f"like_{idx}"):
                    st.session_state.feedback[key_content] = "like"
                if fb_cols[1].button("👎 Dislike", key=f"dislike_{idx}"):
                    st.session_state.feedback[key_content] = "dislike"
                    choices = ["Unclear", "Too long", "Not relevant"]
                    choice_cols = st.columns(len(choices))
                    for i, ch in enumerate(choices):
                        if choice_cols[i].button(ch, key=f"dislike_choice_{idx}_{i}"):
                            # quick follow-up refine
                            st.session_state.chat_history.append({"role":"assistant","content":f"<div class='step-title'>Refinement</div><div>Refining based on feedback: {escape(ch)}</div>","citation":""})
                if fb_cols[2].button("ℹ️ Need More", key=f"needmore_{idx}"):
                    st.session_state.feedback[key_content] = "need_more"
                    st.session_state.chat_history.append({"role":"assistant","content":"<div class='step-title'>Expand</div><div>Expanding the previous answer with additional detail.</div>","citation":""})

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
