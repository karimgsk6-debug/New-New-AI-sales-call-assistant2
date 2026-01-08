# app_final_merged_groq_rag_apact.py - Full AI Sales Call Assistant

import streamlit as st
import os, re, io, tempfile, base64
from html import escape
from datetime import datetime

# -------------------------
# Soft imports
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
# GROQ API summarizer
# -------------------------
def load_groq_client():
    api_key = os.getenv("GROQ_API_KEY", "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") or (st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else "")
    if not api_key or Groq is None:
        return None
    try:
        return Groq(api_key=api_key)
    except Exception:
        return None

def model_summarize(text, bullets=6):
    if not text:
        return ""
    client = load_groq_client()
    if client:
        try:
            prompt = f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt}],
                temperature=0.2
            )
            content = getattr(resp.choices[0].message, "content", None) or getattr(resp.choices[0], "text", "")
            return content
        except Exception:
            pass
    # fallback simple summary
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- " + s for s in selected])

# -------------------------
# File reader & corpus builder
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

# -------------------------
# Audio generator
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
# Brand data & persona helpers
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
    }
}
EXTRA_PERSONAS = ["Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"]

def get_persona_options(brand_key):
    base = brand_data.get(brand_key, {}).get("personas", [])
    combined = base + [p for p in EXTRA_PERSONAS if p not in base]
    return combined

def persona_profile(persona_name):
    p = persona_name.lower()
    profile = {"priority":"", "style":"", "quick_win":""}
    if "evidence" in p:
        profile.update({"priority":"data & outcomes","style":"precise, cite trial outcomes","quick_win":"1-slide summary"})
    elif "time" in p:
        profile.update({"priority":"speed & simplicity","style":"concise, action-oriented","quick_win":"nurse checklist"})
    elif "skeptical" in p:
        profile.update({"priority":"safety & credibility","style":"address objections first","quick_win":"safety data"})
    elif "early" in p:
        profile.update({"priority":"innovation & differentiation","style":"enthusiastic","quick_win":"pilot opportunity"})
    elif "uncommitted" in p:
        profile.update({"priority":"ease & persuasion","style":"relatable","quick_win":"patient education"})
    elif "reluctant" in p:
        profile.update({"priority":"efficiency & risk reduction","style":"evidence-lite","quick_win":"nurse script"})
    elif "patient" in p:
        profile.update({"priority":"patient experience","style":"storytelling","quick_win":"patient leaflet"})
    elif "committed" in p:
        profile.update({"priority":"scale & advocacy","style":"build on success","quick_win":"co-create guidelines"})
    else:
        profile.update({"priority":"clinician-focused","style":"clear and helpful","quick_win":"short actionable commitment"})
    return profile

# -------------------------
# APACT objection handler
# -------------------------
def objection_response(product_key, objection_key, persona):
    product = brand_data.get(product_key, {})
    base = product.get("objections", {})
    reply = base.get(objection_key, "Acknowledge concern, offer concise evidence, propose a low-effort next step.")
    prof = persona_profile(persona)
    if "evidence" in persona.lower():
        return f"Answer (Evidence-led): {reply} Provide trial highlights and 1-page summary."
    if "time" in persona.lower():
        return f"Answer (Time-pressured): {reply} Offer single-sentence script & checklist."
    if "skeptical" in persona.lower():
        return f"Answer (Skeptical): {reply} Show safety data & monitoring plan, propose pilot."
    if "early" in persona.lower():
        return f"Answer (Early-adopter): {reply} Highlight differentiation & co-design small pilot."
    return f"{reply} (Tailored: {prof['quick_win']})"

# -------------------------
# Story + step generator
# -------------------------
def make_story_for_step(step, brand_key, persona_name, tone, snippet=None):
    prof = persona_profile(persona_name)
    snip_html = f"<div>Snippet: {escape(snippet)}</div>" if snippet else ""
    return f"<div class='step-title'>{escape(step)} ({escape(tone)})</div><div>Hook: {prof['priority']}</div><div>Example: {prof['style']}</div><div>Micro-action: {prof['quick_win']}</div>{snip_html}"

# -------------------------
# Generate AI flow
# -------------------------
def generate_sales_flow(prompt: str, persona_name: str, tone: str):
    snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=6)
    flow = brand_data.get("shingrix", {}).get("call_flow", [])
    parts = []
    for i, step in enumerate(flow):
        sn = snippets[i]["text"] if i < len(snippets) else ""
        parts.append(make_story_for_step(step, "shingrix", persona_name, tone, snippet=sn))
    # APACT objections
    parts.append("<div class='step-title'>Objection Handling</div>")
    for obj in ["efficacy","safety","cost"]:
        parts.append(f"<div class='objection'><strong>{obj.title()} —</strong> {escape(objection_response('shingrix', obj, persona_name))}</div>")
    return "\n".join(parts)

# -------------------------
# Add AI response to chat
# -------------------------
def add_ai_response(prompt_text):
    persona_choice = persona
    tone_choice = tone
    header = f"<div class='step-title'>Acknowledge</div><div>Action-oriented call plan tailored to {escape(persona_choice)} ({escape(tone_choice)} tone)</div>"
    flow_html = generate_sales_flow(prompt_text, persona_choice, tone_choice)
    confirm = "<div class='step-title'>Next step</div><div>If acceptable, reply 'Yes' and draft 30s script + 1-page leave-behind.</div>"
    ai_html = "\n".join([header, flow_html, confirm])
    st.session_state.chat_history.append({"role":"assistant","content":ai_html,"citation":""})

# -------------------------
# UI: input + chat display
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
