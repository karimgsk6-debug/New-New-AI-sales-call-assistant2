import streamlit as st
import os
import re
import tempfile
import base64
import io
from datetime import datetime
from html import escape

# Soft imports (optional)
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
# Resources & Avatar
# -------------------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

# Futuristic hologram avatar URL (replace with your asset if desired)
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"

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
        "hcp_persona": "Friendly",
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
# GROQ client loader
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
        "call_flow": ["Prepare", "Engage", "Create Opportunities", "Influence", "Impact GSO", "Analyze"],
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

# Extended persona set
EXTRA_PERSONAS = ["Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"]
def get_persona_options(brand_key):
    base = brand_data.get(brand_key, {}).get("personas", [])
    combined = base + [p for p in EXTRA_PERSONAS if p not in base]
    return combined

# -------------------------
# Helpers: file reading, corpus building, local search, summarise
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

# -------------------------
# Audio generation (ElevenLabs > gTTS fallback)
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
# Persona profiles
# -------------------------
def persona_profile(persona_name):
    p = persona_name.lower()
    profile = {"priority":"", "style":"", "quick_win":""}
    if "evidence" in p:
        profile["priority"] = "data & outcomes"
        profile["style"] = "precise, cite trial outcomes and comparative results"
        profile["quick_win"] = "share 1-slide summary of key outcomes"
        return profile
    if "time" in p:
        profile["priority"] = "speed & simplicity"
        profile["style"] = "concise, action-oriented, minimal detail"
        profile["quick_win"] = "provide nurse-ready checklist or script"
        return profile
    if "skeptical" in p:
        profile["priority"] = "safety & credibility"
        profile["style"] = "address objections first, use trusted sources"
        profile["quick_win"] = "provide safety data and monitoring plan"
        return profile
    if "early" in p:
        profile["priority"] = "innovation & differentiation"
        profile["style"] = "enthusiastic, highlight first-mover benefits"
        profile["quick_win"] = "offer pilot/benchmark opportunity"
        return profile
    if "uncommitted" in p:
        profile["priority"] = "ease & persuasion"
        profile["style"] = "relatable, low-friction"
        profile["quick_win"] = "leave-behind patient education"
        return profile
    if "reluctant" in p:
        profile["priority"] = "efficiency & risk reduction"
        profile["style"] = "evidence-lite + workflow support"
        profile["quick_win"] = "nurse script and time-saving tip"
        return profile
    if "patient" in p:
        profile["priority"] = "patient experience"
        profile["style"] = "storytelling and adherence focus"
        profile["quick_win"] = "patient leaflet and story-based hook"
        return profile
    if "committed" in p:
        profile["priority"] = "scale & advocacy"
        profile["style"] = "build on success with scaling ideas"
        profile["quick_win"] = "co-create local guideline prompts"
        return profile
    profile["priority"] = "clinician-focused"
    profile["style"] = "clear and helpful"
    profile["quick_win"] = "short actionable commitment"
    return profile

# -------------------------
# Tone helper
# -------------------------
def tone_prefix(t):
    t = (t or "").lower()
    if t == "executive":
        return "(Executive)"
    if t == "coaching":
        return "(Coaching)"
    if t == "persuasive":
        return "(Persuasive)"
    return "(Clinical)"

# -------------------------
# Story + step builder
# -------------------------
def make_story_for_step(step, brand_key, persona_name, tone, snippet=None):
    safe_snip = escape(snippet) if snippet else ""
    brand = brand_data.get(brand_key, {}).get("display", brand_key)
    prof = persona_profile(persona_name)
    t_pref = tone_prefix(tone)

    if step.lower().startswith("prepare"):
        return (
            f"<div class='step-title'>Prepare {t_pref}</div>"
            f"<div>Hook: Lead with one sharp insight relevant to this clinic—{prof['priority']}.</div>"
            f"<div class='story'>Example: \"Doctor, I reviewed your clinic mix — there's an easy way to reach more of your 60+ patients without adding admin time.\"</div>"
            f"<div>Micro-action: Offer a one-line opener the rep can use now: \"Can I share a 30s change that helps your at-risk patients?\"</div>"
        )

    if step.lower().startswith("engage"):
        sample = "How are you handling eligible patients today?"
        if tone == "executive":
            sample = "What's the single highest-leverage change for your patients this quarter?"
        if tone == "coaching":
            sample = "Walk me through how you'd introduce this option in a 60s visit."
        if tone == "persuasive":
            sample = "A simple phrasing that lifted uptake in similar clinics is: 'This reduces your patients' risk of painful complications.' Want the line?"
        return (
            f"<div class='step-title'>Engage {t_pref}</div>"
            f"<div>Hook: Open with focused discovery tied to the persona ({prof['style']}).</div>"
            f"<div class='story'>Example: \"{sample}\"</div>"
            f"<div>Micro-action: Ask for a commitment to try a quick workflow change with one patient cohort.</div>"
        )

    if "create" in step.lower() or "opportun" in step.lower():
        action = "offer a nurse-ready checklist"
        if tone == "executive":
            action = "suggest a 4-week pilot with predefined KPIs"
        if tone == "coaching":
            action = "offer a role-play to prepare the team"
        return (
            f"<div class='step-title'>Create Opportunities {t_pref}</div>"
            f"<div>Hook: Convert interest into a concrete next step that fits the persona's quick wins ({prof['quick_win']}).</div>"
            f"<div class='story'>Example action: \"Let's pilot with 8 eligible patients and review results in 4 weeks.\"</div>"
            f"<div>Micro-action: Agree on the single metric you'll measure.</div>"
        )

    if step.lower().startswith("influence"):
        pitch = f"A patient 72yo avoided complications after receiving {brand}."
        if tone == "clinical":
            pitch = "Key trial outcomes show durable protection in the target group — highlight the most relevant endpoint."
        return (
            f"<div class='step-title'>Influence {t_pref}</div>"
            f"<div>Hook: Use one tight patient vignette + one fact the persona values.</div>"
            f"<div class='story'>Example: \"{pitch}\"</div>"
            f"<div>Micro-action: Ask the HCP which of their patients is most like the vignette.</div>"
        )

    if "impact" in step.lower() or "gso" in step.lower():
        offer = "Propose a short pilot and agree success metrics."
        if tone == "persuasive":
            offer = "Secure an immediate opt-in by emphasizing quick wins and low effort."
        return (
            f"<div class='step-title'>Impact GSO {t_pref}</div>"
            f"<div>Hook: Frame the ask by clinic-level benefit (throughput, fewer follow-ups for complications).</div>"
            f"<div class='story'>Example: \"Would you be open to starting with your next 10 eligible patients and reviewing outcomes?\"</div>"
            f"<div>Micro-action: Offer to send a single-slide plan that makes it effortless to say yes.</div>"
        )

    if step.lower().startswith("analy") or step.lower().startswith("post"):
        return (
            f"<div class='step-title'>Analyze {t_pref}</div>"
            f"<div>Hook: Reinforce partnership — summarize outcomes and give a clear next meeting request.</div>"
            f"<div class='story'>Example: \"I'll email a 1-page summary with the agreed metric and propose a 2-week check-in.\"</div>"
            f"<div>Micro-action: Schedule the follow-up before leaving the clinic.</div>"
        )

    return f"<div class='step-title'>{escape(step)}</div><div class='story'>Practical, persona-aware example for {escape(persona_name)} ({escape(tone)}).</div>"

# -------------------------
# Objection handling per product & persona
# -------------------------
def objection_response(product_key, objection_key, persona):
    product = brand_data.get(product_key, {})
    base = product.get("objections", {})
    reply = base.get(objection_key, "Acknowledge the concern, offer concise evidence, and propose a low-effort next step.")
    prof = persona_profile(persona)

    if "evidence" in persona.lower():
        return f"Answer (Evidence-led): {reply} Provide trial highlights and one quick citation; offer to share a 1-page evidence summary."
    if "time" in persona.lower():
        return f"Answer (Time-pressured): {reply} Then offer a single-sentence script and a nurse checklist to make adoption painless."
    if "skeptical" in persona.lower():
        return f"Answer (Skeptical): {reply} Start by acknowledging, then show safety data and a monitoring plan; propose a conservative pilot."
    if "early" in persona.lower():
        return f"Answer (Early-adopter): {reply} Highlight differentiation and offer to co-design a small pilot with outcome monitoring."
    return f"{reply} (Tailored suggestion: {prof['quick_win']})"

# -------------------------
# Sales flow generation
# -------------------------
def generate_sales_flow(prompt: str, persona_name: str, tone: str):
    p = (prompt or "").lower()
    snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=6) if chunks else []

    # Shingrix flow
    if "shingrix" in p or "hzv" in p or "herpes zoster" in p:
        flow = brand_data["shingrix"]["call_flow"]
        parts = [f"<div><strong>Context:</strong> Shingrix — tailored to {escape(persona_name)} ({escape(tone)})</div>"]
        for i, step in enumerate(flow):
            sn = snippets[i]["text"] if i < len(snippets) else ""
            parts.append(make_story_for_step(step, "shingrix", persona_name, tone, snippet=sn))
        parts.append("<div class='step-title'>Objection Handling</div>")
        for obj in ["efficacy", "safety", "cost"]:
            parts.append(f"<div class='objection'><strong>{obj.title()} —</strong> {escape(objection_response('shingrix', obj, persona_name))}</div>")
        return "\n".join(parts)

    # Jemperli flow
    if "jemperli" in p or "dmmr" in p or "msi-h" in p:
        flow = brand_data["jemperli"]["call_flow"]
        parts = [f"<div><strong>Context:</strong> Jemperli — tailored to {escape(persona_name)} ({escape(tone)})</div>"]
        for i, step in enumerate(flow):
            sn = snippets[i]["text"] if i < len(snippets) else ""
            parts.append(make_story_for_step(step, "jemperli", persona_name, tone, snippet=sn))
        parts.append("<div class='step-title'>Objection Handling</div>")
        for obj in ["efficacy", "safety", "access"]:
            parts.append(f"<div class='objection'><strong>{obj.title()} —</strong> {escape(objection_response('jemperli', obj, persona_name))}</div>")
        return "\n".join(parts)

    # Trelegy flow
    if "trelegy" in p or "copd" in p:
        flow = brand_data["trelegy"]["call_flow"]
        parts = [f"<div><strong>Context:</strong> Trelegy — tailored to {escape(persona_name)} ({escape(tone)})</div>"]
        for i, step in enumerate(flow):
            sn = snippets[i]["text"] if i < len(snippets) else ""
            parts.append(make_story_for_step(step, "trelegy", persona_name, tone, snippet=sn))
        parts.append("<div class='step-title'>Objection Handling</div>")
        for obj in ["device", "coverage", "effectiveness"]:
            parts.append(f"<div class='objection'><strong>{obj.title()} —</strong> {escape(objection_response('trelegy', obj, persona_name))}</div>")
        return "\n".join(parts)

    # Default generic flow
    default_steps = ["Prepare", "Engage", "Create Opportunities", "Influence", "Close"]
    parts = [f"<div><strong>Context:</strong> General sales call — tailored to {escape(persona_name)} ({escape(tone)})</div>"]
    for i, step in enumerate(default_steps):
        sn = snippets[i]["text"] if i < len(snippets) else ""
        parts.append(make_story_for_step(step, st.session_state.selected_brand, persona_name, tone, snippet=sn))
    parts.append("<div class='step-title'>Objection Handling</div>")
    parts.append(f"<div class='objection'><strong>Common —</strong> Acknowledge concern, present one concise evidence point, propose a low-effort pilot.</div>")
    return "\n".join(parts)

# -------------------------
# AI response builder + chat history
# -------------------------
def add_ai_response(prompt_text, follow_up=False, dislike_choice=None):
    persona_choice = st.session_state.hcp_persona if st.session_state.get("hcp_persona") else persona
    tone_choice = st.session_state.tone if st.session_state.get("tone") else tone

    header = f"<div class='step-title'>Acknowledge</div><div>Thanks — I'll give a concise, action-oriented call plan tailored to a {escape(persona_choice)} ({escape(tone_choice)} tone).</div>"
    flow_html = generate_sales_flow(prompt_text, persona_choice, tone_choice)
    confirm = "<div class='step-title'>Next step</div><div>If this fits, reply 'Yes' and I'll draft a 30s call script and one-page leave-behind you can use today.</div>"

    ai_html = "\n".join([header, flow_html, confirm])
    st.session_state.chat_history.append({"role": "assistant", "content": ai_html, "citation": ""})

# -------------------------
# Avatar & message renderers
# -------------------------
HOLO_AVATAR = AI_AVATAR

def render_ai_message(message_html):
    """Render AI HTML content with avatar on the left."""
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
# Sidebar filters & controls
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]

    segment = st.selectbox("Segment", bconf["segments"])
    persona_options = get_persona_options(sel_brand)
    persona_sel = st.selectbox("HCP Persona", persona_options, index=0)
    st.session_state.hcp_persona = persona_sel

    # HCP personality (assertive, masked, friendly, details-oriented, skeptic)
    hcp_personality = st.selectbox("HCP Personality", ["Assertive", "Masked", "Friendly", "Details-oriented", "Skeptic"])
    st.session_state.hcp_personality = hcp_personality

    barrier = st.multiselect("Doctor Barrier", bconf["barriers"])
    specialty = st.selectbox("Specialty", bconf["specialties"])
    objective = st.selectbox("Objective", ["Awareness", "Adoption", "Retention"])
    st.session_state.temperature = st.slider("Temperature", 0.0, 1.0, st.session_state.temperature, 0.05)
    st.session_state.search_mode = st.selectbox("Search mode", ["deep", "shallow"])
    st.session_state.language = st.radio("Language", ["English", "Arabic"])
    st.session_state.tone = st.selectbox("Tone", ["executive", "coaching", "persuasive", "clinical"], index=0)
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
        <h2>💡 AI Sales Call Assistant — {bconf['display']}</h2>
        <img src="{AI_LOGO_RAW}" class="right-logo">
    </div>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# Load references and summarize
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
# PDF upload (per brand)
# -------------------------
uploaded_file = st.file_uploader("Upload PDF for summary (brand-specific)", type=["pdf"])
if uploaded_file and PdfReader:
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
# Build corpus for selected brand (used for local_search_snippets)
# -------------------------
corpus_folders = [refs_folder, sales_folder]
chunks, chunk_meta = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# Prompt suggestions & main input form
# -------------------------
chat_container = st.container()

with st.expander("💡 Prompt Suggestions (Click to Expand)", expanded=False):
    suggs = [
        f"Generate a {bconf['display']} sales call for {st.session_state.hcp_persona} in {st.session_state.tone} tone",
        f"How to handle an efficacy objection for {bconf['display']}?",
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
        st.session_state.chat_history.append({"role": "user", "content": user_input.strip()})
        add_ai_response(user_input.strip())
        st.session_state.main_input = ""

# -------------------------
# Display chat (with avatar for AI)
# -------------------------
with chat_container:
    for idx, entry in enumerate(st.session_state.chat_history):
        if entry.get("role") == "user":
            render_user_message(entry.get("content", ""))
        else:
            # assistant content contains HTML fragments already
            render_ai_message(entry.get("content", ""))
            if entry.get("citation"):
                st.markdown(f'<div class="citation-box">{escape(entry.get("citation"))}</div>', unsafe_allow_html=True)

            # audio: strip HTML tags
            plain = re.sub(r"<[^>]+>", "", entry.get("content", ""))[:1500]
            audio_b64 = generate_audio(plain)
            if audio_b64:
                st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")

            # Feedback
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
                    add_ai_response("User requested more details; expand the previous answer.", follow_up=True)

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
