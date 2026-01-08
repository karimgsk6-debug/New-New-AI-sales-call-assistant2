# app_final_enhanced.py - AI Sales Call Assistant (Enhanced)
# Features: enriched Engage step, clean summaries, TTS button

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
# GROQ client
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

# -------------------------
# Persona helpers
# -------------------------
EXTRA_PERSONAS = ["Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"]

def get_persona_options(brand_key):
    base = brand_data.get(brand_key, {}).get("personas", [])
    combined = base + [p for p in EXTRA_PERSONAS if p not in base]
    return combined

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
        profile["style"] = "concise, action-oriented, minimal detail"
        profile["quick_win"] = "offer a nurse-ready script or checklist"
        return profile

    if "skeptical" in p:
        profile["priority"] = "safety & credibility"
        profile["style"] = "address objections first, use trusted sources"
        profile["quick_win"] = "provide safety data and monitoring plan"
        return profile

    if "early" in p or "early-adopter" in p:
        profile["priority"] = "innovation & differentiation"
        profile["style"] = "enthusiastic, highlight first-mover benefits"
        profile["quick_win"] = "offer pilot/benchmark opportunity"
        return profile

    # fallback for original personas
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
# Tone helpers
# -------------------------
def tone_prefix(t):
    return {"executive":"(Executive)", "coaching":"(Coaching)", "persuasive":"(Persuasive)"}.get(t, "(Clinical)")

# -------------------------
# Summary helpers
# -------------------------
def simple_summary(text, bullets=6):
    if not text:
        return ""
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    return "\n".join(["- " + s for s in sents[:bullets]])

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
            # clean repeated garbage
            content = re.sub(r"[\x00-\x1f]+", "", content)
            return content
        except Exception:
            return simple_summary(text, bullets)
    else:
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
# Enriched story builder
# -------------------------
def make_story_for_step(step, brand_key, persona_name, tone, snippet=None):
    safe_snip = escape(snippet) if snippet else ""
    brand = brand_data.get(brand_key, {}).get("display", brand_key)
    prof = persona_profile(persona_name)
    t_pref = tone_prefix(tone)

    if step.lower().startswith("engage"):
        examples = [
            "How are you currently identifying eligible patients?",
            "What obstacles prevent more patients from receiving the vaccine?",
            "Which patients do you feel least confident in counseling?",
            "Are there workflow gaps impacting patient adherence?",
            "Which recent cases made you reconsider treatment options?",
            "How could additional support improve your clinic efficiency?"
        ]
        if tone == "executive":
            examples = ["Which single initiative would most improve your patients' outcomes?"] + examples[:2]
        if tone == "coaching":
            examples = ["Walk me through a patient consultation in your clinic today."] + examples[:3]
        if tone == "persuasive":
            examples = ["A phrasing that increased uptake: 'This reduces patients’ risk of severe complications.'"] + examples[2:4]

        ex_html = "".join([f"<div>• {e}</div>" for e in examples])

        return (
            f"<div class='step-title'>Engage {t_pref}</div>"
            f"<div>Hook: Open with focused discovery tied to the persona ({prof['style']}).</div>"
            f"<div class='story'>Examples of insightful questions to uncover unmet needs:</div>"
            f"{ex_html}"
            f"<div>Micro-action: Commit to exploring one workflow improvement with a small patient cohort.</div>"
        )

    # fallback: keep existing logic for other steps...
    return f"<div class='step-title'>{escape(step)}</div><div class='story'>Practical, persona-aware example for {escape(persona_name)} ({escape(tone)}).</div>"

# -------------------------
# (Rest of the code — objection handling, generate_sales_flow, chat UI, etc.)
# -------------------------
# Keep existing logic for objection_response(), generate_sales_flow(), add_ai_response()
# The only key change is make_story_for_step() enriches Engage, summaries are cleaned, audio button remains under each AI response


# -------------------------
# Objection handling per product & persona
# -------------------------
def objection_response(product_key, objection_key, persona):
    """Return a short, persona-aware objection handling snippet for the product."""
    product = brand_data.get(product_key, {})
    base = product.get("objections", {})
    # Base reply (concise)
    reply = base.get(objection_key, "Acknowledge the concern, offer concise evidence, and propose a low-effort next step.")
    prof = persona_profile(persona)

    # Tailor by persona
    if "evidence" in persona.lower():
        return f"Answer (Evidence-led): {reply} Provide trial highlights and one quick citation; offer to share a 1-page evidence summary."
    if "time" in persona.lower():
        return f"Answer (Time-pressured): {reply} Then offer a single-sentence script and a nurse checklist to make adoption painless."
    if "skeptical" in persona.lower():
        return f"Answer (Skeptical): {reply} Start by acknowledging, then show safety data and a monitoring plan; propose a conservative pilot."
    if "early" in persona.lower():
        return f"Answer (Early-adopter): {reply} Highlight differentiation and offer to co-design a small pilot with outcome monitoring."
    # default
    return f"{reply} (Tailored suggestion: {prof['quick_win']})"

# -------------------------
# Sales flow generators (use small local snippets but NOT copy module text)
# -------------------------
def generate_sales_flow(prompt: str, persona_name: str, tone: str):
    p = prompt.lower()
    snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=6)

    # choose flow per product keywords
    if "shingrix" in p or "hzv" in p or "herpes zoster" in p:
        flow = brand_data["shingrix"]["call_flow"]
        parts = [f"<div><strong>Context:</strong> Shingrix — tailored to {escape(persona_name)} ({escape(tone)})</div>"]
        for i, step in enumerate(flow):
            sn = snippets[i]["text"] if i < len(snippets) else ""
            parts.append(make_story_for_step(step, "shingrix", persona_name, tone, snippet=sn))
        # add objection handling section
        parts.append("<div class='step-title'>Objection Handling</div>")
        # sample common objections
        for obj in ["efficacy", "safety", "cost"]:
            parts.append(f"<div class='objection'><strong>{obj.title()} —</strong> {escape(objection_response('shingrix', obj, persona_name))}</div>")
        return "\n".join(parts)

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

    # default flow
    default_steps = ["Prepare", "Engage", "Create Opportunities", "Influence", "Close"]
    parts = [f"<div><strong>Context:</strong> General sales call — tailored to {escape(persona_name)} ({escape(tone)})</div>"]
    for i, step in enumerate(default_steps):
        sn = snippets[i]["text"] if i < len(snippets) else ""
        parts.append(make_story_for_step(step, st.session_state.selected_brand, persona_name, tone, snippet=sn))
    # generic objection handling suggestion
    parts.append("<div class='step-title'>Objection Handling</div>")
    parts.append(f"<div class='objection'><strong>Common —</strong> Acknowledge concern, present one concise evidence point, propose a low-effort pilot.</div>")
    return "\n".join(parts)

# -------------------------
# Build the AI response and append to chat history
# -------------------------
def add_ai_response(prompt_text, follow_up=False, dislike_choice=None):
    # create persona & tone context
    persona_choice = persona
    tone_choice = tone

    # small acknowledge + tailored flow
    header = f"<div class='step-title'>Acknowledge</div><div>Thanks — I'll give a concise, action-oriented call plan tailored to a {escape(persona_choice)} ({escape(tone_choice)} tone).</div>"
    flow_html = generate_sales_flow(prompt_text, persona_choice, tone_choice)

    confirm = "<div class='step-title'>Next step</div><div>If this fits, reply 'Yes' and I'll draft a 30s call script and one-page leave-behind you can use today.</div>"

    # store and return
    ai_html = "\n".join([header, flow_html, confirm])
    st.session_state.chat_history.append({"role": "assistant", "content": ai_html, "citation": ""})

# -------------------------
# UI: prompt suggestions + input + chat display
# -------------------------
chat_container = st.container()

with st.expander("💡 Prompt Suggestions (Click to Expand)", expanded=False):
    suggs = [
        f"Generate a {bconf['display']} sales call for {persona} in {tone} tone",
        "How to handle an efficacy objection for Shingrix?",
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

with chat_container:
    for idx, entry in enumerate(st.session_state.chat_history):
        if entry.get("role") == "user":
            st.markdown(f'<div class="chat-bubble-user">{escape(entry.get("content",""))}</div>', unsafe_allow_html=True)
        else:
            # assistant content is HTML
            st.markdown(f'<div class="chat-bubble-ai">{entry.get("content","")}</div>', unsafe_allow_html=True)
            if entry.get("citation"):
                st.markdown(f'<div class="citation-box">{escape(entry.get("citation"))}</div>', unsafe_allow_html=True)
            # audio (first 1500 chars without html tags)
            plain = re.sub(r"<[^>]+>", "", entry.get("content",""))[:1500]
            audio_b64 = generate_audio(plain)
            if audio_b64:
                st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")

            # feedback buttons
            fb_cols = st.columns(3)
            key_content = entry.get("content", "")
            if key_content not in st.session_state.feedback:
                if fb_cols[0].button("👍 Like", key=f"like_{idx}"):
                    st.session_state.feedback[key_content] = "like"
                if fb_cols[1].button("👎 Dislike", key=f"dislike_{idx}"):
                    st.session_state.feedback[key_content] = "dislike"
                    # provide immediate refinement choices
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
