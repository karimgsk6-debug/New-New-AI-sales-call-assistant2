# app_final_full.py - Fully merged AI Sales Call Assistant (Hologram avatar, personas, tones, objections, PDF/audio)
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
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"

# -------------------------
# Session defaults
# -------------------------
def _init_session():
    defaults = {
        "chat_history": [], "main_input": "", "selected_brand": "shingrix",
        "temperature": 0.95, "search_mode": "deep", "medical_summary": "",
        "sales_summary": "", "uploaded_pdf_text": "", "pdf_summary": "",
        "feedback": {}, "dislike_state": None, "language": "English",
        "hcp_persona": "Friendly", "hcp_personality": "Friendly", "tone": "executive"
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
</style>
""", unsafe_allow_html=True)

# -------------------------
# Background helper
# -------------------------
def set_dynamic_background(image_path):
    if not os.path.exists(image_path): return
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
    except: pass

set_dynamic_background(BACKGROUND_PATH)

# -------------------------
# GROQ client loader
# -------------------------
def load_groq_client():
    api_key = os.getenv("GROQ_API_KEY", "") or (st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else "")
    if not api_key or Groq is None: return None
    try: return Groq(api_key=api_key)
    except: return None

# -------------------------
# Brand & persona data
# -------------------------
brand_data = {
    "shingrix": {"display":"Shingrix","segments":["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
                 "personas":["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
                 "barriers":["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
                 "specialties":["GP","Dermatologist","Cardiology","Endocrinology","Immunology","Internal Medicine","Rheumatology"],
                 "references_path":".devcontainer/references/shingrix/","sales_path":".devcontainer/SalesModule/shingrix/",
                 "call_flow":["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Analyze"],
                 "objections":{"efficacy":"Focus on durable protection and age-agnostic efficacy evidence.",
                               "safety":"Acknowledge common AEs, then contrast with risk of complications from shingles.",
                               "cost":"Frame cost as prevention of downstream complications and reduce clinic workload."}},
    "jemperli": {"display":"Jemperli","segments":["Target Identification","Trial Adoption","Routine Use","Advocacy"],
                 "personas":["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
                 "barriers":["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
                 "specialties":["Oncologist","Medical Oncologist"], "references_path":".devcontainer/references/jemperli/",
                 "sales_path":".devcontainer/SalesModule/jemperli/","call_flow":["COCO","Anchor","Engage","Close"],
                 "objections":{"efficacy":"Discuss durable responses in dMMR/MSI-H and appropriate patient selection.",
                               "safety":"Share safety profile and monitoring guidance to reduce perceived risk.",
                               "access":"Offer starter kits or initiation support and reimbursement pathways."}},
    "trelegy": {"display":"Trelegy","segments":["Awareness","Diagnosis","Adoption","Adherence"],
                "personas":["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
                "barriers":["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
                "specialties":["GP","Pulmonologist","Internal Medicine","Respiratory Specialist"],
                "references_path":".devcontainer/references/trelegy/","sales_path":".devcontainer/SalesModule/trelegy/",
                "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"],
                "objections":{"device":"Offer quick practical coaching and demo materials.",
                              "coverage":"Explain access options and patient support programs.",
                              "effectiveness":"Share comparative outcomes framed for real-world practice."}}
}

EXTRA_PERSONAS = ["Evidence-led","Time-pressured","Skeptical","Early-adopter"]
def get_persona_options(brand_key):
    base = brand_data.get(brand_key, {}).get("personas", [])
    return base + [p for p in EXTRA_PERSONAS if p not in base]

# -------------------------
# Helpers: file reading, corpus, search, summarize
# -------------------------
def read_file_text(path):
    if not os.path.exists(path): return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh: return fh.read()
    except: return ""

def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas = [], []
    for folder in folders:
        if not folder or not os.path.exists(folder): continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf",".txt"))]
        for fname in files:
            p = os.path.join(folder,fname)
            text = read_file_text(p)
            if not text: continue
            sents = re.split(r'(?<=[\.\?\!])\s+', text)
            for i in range(0, max(1,len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk: chunks.append(chunk); metas.append({"filename":fname,"folder":folder,"start":i})
    return chunks, metas

def local_search_snippets(query,chunks,metas,top_n=3):
    if not chunks: return []
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks+[query])
            chunk_vecs = vectorizer.transform(chunks)
            q_vec = vectorizer.transform([query])
            sims = linear_kernel(q_vec, chunk_vecs).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            results=[]
            for idx in top_idxs:
                if sims[idx]<=0: continue
                results.append({"score":float(sims[idx]),"text":chunks[idx],"meta":metas[idx]})
            return results
        except: pass
    out=[]
    q=query.lower()
    for i,c in enumerate(chunks):
        if q in c.lower(): out.append({"score":1.0,"text":c,"meta":metas[i]})
        if len(out)>=top_n: break
    return out

def simple_summary(text, bullets=6):
    if not text: return ""
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- "+s for s in selected])

def model_summarize(text, bullets=6):
    client = load_groq_client()
    if client:
        try:
            prompt=f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile",messages=[{"role":"user","content":prompt}],temperature=0.2)
            content = getattr(resp.choices[0].message,"content",None) or getattr(resp.choices[0],"text","")
            return content
        except: return simple_summary(text, bullets)
    else: return simple_summary(text, bullets)

# -------------------------
# Audio generation
# -------------------------
def generate_audio(text):
    if not text: return ""
    if ELEVENLABS_AVAILABLE:
        try:
            elevenlabs.api_key = st.secrets.get("ELEVENLABS_API_KEY","")
            audio_stream = elevenlabs.generate(text=text,voice="alloy",model="eleven_multilingual_v1",stream=True)
            tmp = tempfile.NamedTemporaryFile(delete=False,suffix=".mp3")
            with open(tmp.name,"wb") as f:
                for chunk in audio_stream: f.write(chunk)
            with open(tmp.name,"rb") as fh: return base64.b64encode(fh.read()).decode()
        except: pass
    if gTTS:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False,suffix=".mp3")
            gTTS(text=text, lang="en", slow=False).save(tmp.name)
            with open(tmp.name,"rb") as fh: return base64.b64encode(fh.read()).decode()
        except: pass
    return ""

# -------------------------
# Persona profiles
# -------------------------
def persona_profile(persona_name):
    p=persona_name.lower()
    profile={"priority":"","style":"","quick_win":""}
    if "evidence" in p: profile.update({"priority":"data & outcomes","style":"precise, cite trial outcomes and comparative results","quick_win":"share 1-slide summary of key outcomes"}); return profile
    if "time" in p: profile.update({"priority":"speed & simplicity","style":"concise, action-oriented, minimal detail","quick_win":"provide nurse-ready checklist or script"}); return profile
    if "skeptical" in p: profile.update({"priority":"safety & credibility","style":"address objections first, use trusted sources","quick_win":"provide safety data and monitoring plan"}); return profile
    if "early" in p: profile.update({"priority":"innovation & differentiation","style":"enthusiastic, highlight first-mover benefits","quick_win":"offer pilot/benchmark opportunity"}); return profile
    if "uncommitted" in p: profile.update({"priority":"ease & persuasion","style":"relatable, low-friction","quick_win":"leave-behind patient education"}); return profile
    if "reluctant" in p: profile.update({"priority":"efficiency & risk reduction","style":"evidence-lite + workflow support","quick_win":"nurse script and time-saving tip"}); return profile
    if "patient" in p: profile.update({"priority":"patient experience","style":"storytelling and adherence focus","quick_win":"patient leaflet and story-based hook"}); return profile
    if "committed" in p: profile.update({"priority":"scale & advocacy","style":"build on success with scaling ideas","quick_win":"co-create local guideline prompts"}); return profile
    profile.update({"priority":"clinician-focused","style":"clear and helpful","quick_win":"short actionable commitment"})
    return profile

# -------------------------
# Tone helper
# -------------------------
def tone_prefix(t):
    t = (t or "").lower()
    if t=="executive": return "(Executive)"
    if t=="coaching": return "(Coaching)"
    if t=="persuasive": return "(Persuasive)"
    return "(Clinical)"

# -------------------------
# Story/step builder
# -------------------------
def make_story_for_step(step, brand_key, persona_name, tone, snippet=None):
    safe_snip=escape(snippet) if snippet else ""
    brand=brand_data.get(brand_key,{}).get("display",brand_key)
    prof=persona_profile(persona_name)
    t_pref=tone_prefix(tone)
    if step.lower().startswith("prepare"):
        return f"<div class='step-title'>Prepare {t_pref}</div><div>Hook: Lead with one sharp insight relevant to this clinic—{prof['priority']}.</div><div class='story'>Example: \"Doctor, I reviewed your clinic mix — there's an easy way to reach more of your 60+ patients without adding admin time.\"</div><div>Micro-action: Offer a one-line opener the rep can use now: \"Can I share a 30s change that helps your at-risk patients?\"</div>"
    if step.lower().startswith("engage"):
        sample="How are you handling eligible patients today?"
        if tone=="executive": sample="What's the single highest-leverage change for your patients this quarter?"
        if tone=="coaching": sample="Walk me through how you'd introduce this option in a 60s visit."
        if tone=="persuasive": sample="A simple phrasing that lifted uptake in similar clinics is: 'This reduces your patients' risk of painful complications.' Want the line?"
        return f"<div class='step-title'>Engage {t_pref}</div><div>Hook: Open with focused discovery tied to the persona ({prof['style']}).</div><div class='story'>Example: \"{sample}\"</div><div>Micro-action: Ask for a commitment to try a quick workflow change with one patient cohort.</div>"
    if "create" in step.lower() or "opportun" in step.lower():
        action="offer a nurse-ready checklist"
        if tone=="executive": action="suggest a 4-week pilot with predefined KPIs"
        if tone=="coaching": action="offer a role-play to prepare the team"
        return f"<div class='step-title'>Create Opportunities {t_pref}</div><div>Hook: Convert interest into a concrete next step that fits the persona's quick wins ({prof['quick_win']}).</div><div class='story'>Example action: \"Let's pilot with 8 eligible patients and review results in 4 weeks.\"</div><div>Micro-action: {action}</div>"
    if snippet:
        return f"<div class='step-title'>{step} {t_pref}</div><div>{safe_snip}</div>"
    return f"<div class='step-title'>{step} {t_pref}</div><div>Generic guidance for this step.</div>"

# -------------------------
# Objection handler
# -------------------------
def objection_response(objection, brand_key, persona_name, tone):
    brand=brand_data.get(brand_key,{})
    base=brand.get("objections",{})
    prof=persona_profile(persona_name)
    txt=base.get(objection.lower(),"Address concern professionally.")
    return f"<div class='objection'>{txt} (Persona: {prof['style']}, Tone: {tone_prefix(tone)})</div>"

# -------------------------
# Add AI response
# -------------------------
def add_ai_response(user_text, follow_up=False, dislike_choice=None):
    brand_key = st.session_state.selected_brand
    persona_name = st.session_state.hcp_persona
    tone = st.session_state.tone
    if follow_up:
        reply=f"Follow-up response based on user feedback ({dislike_choice or 'expand'})."
    else:
        # Search snippets
        snippets = local_search_snippets(user_text, st.session_state.get("chunks",[]), st.session_state.get("chunk_meta",[]),top_n=2)
        snippet_text = "\n".join([s["text"] for s in snippets]) if snippets else ""
        reply = make_story_for_step("Prepare",brand_key,persona_name,tone,snippet=snippet_text)
    st.session_state.chat_history.append({"role":"assistant","content":reply})

# -------------------------
# Renderers
# -------------------------
def render_ai_message(message_html):
    st.markdown(f'<div class="ai-message"><img src="{AI_AVATAR}" class="ai-avatar" /><div class="ai-bubble">{message_html}</div></div>', unsafe_allow_html=True)
def render_user_message(msg):
    st.markdown(f'<div class="user-bubble">{escape(msg)}</div>', unsafe_allow_html=True)

# -------------------------
# Sidebar filters & controls
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    persona_options = get_persona_options(sel_brand)
    persona_sel = st.selectbox("HCP Persona", persona_options)
    st.session_state.hcp_persona = persona_sel
    hcp_personality = st.selectbox("HCP Personality", ["Assertive", "Masked", "Friendly", "Details-oriented", "Skeptic"])
    st.session_state.hcp_personality = hcp_personality
    st.session_state.tone = st.selectbox("Tone", ["executive", "coaching", "persuasive", "clinical"])
    if st.button("🗑️ Clear Chat"): st.session_state.chat_history = []; st.experimental_rerun()

# -------------------------
# Title box
# -------------------------
bconf = brand_data[st.session_state.selected_brand]
st.markdown(f"""
<div class="title-box">
<img src="{GSK_LOGO_RAW}" class="left-logo">
<h2>💡 AI Sales Call Assistant — {bconf['display']}</h2>
<img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# -------------------------
# PDF upload
# -------------------------
uploaded_file = st.file_uploader("Upload PDF for summary (brand-specific)", type=["pdf"])
if uploaded_file and PdfReader:
    try:
        reader = PdfReader(uploaded_file)
        pdf_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = pdf_text
        st.session_state.pdf_summary = model_summarize(pdf_text, bullets=6)
        st.success("PDF summarized successfully!")
    except: st.error("Failed to read the uploaded PDF.")
if st.session_state.pdf_summary:
    with st.expander("📄 Uploaded PDF Summary", expanded=False): st.markdown(st.session_state.pdf_summary)

# -------------------------
# Build corpus
# -------------------------
chunks, chunk_meta = build_corpus_for_folders([bconf.get("references_path",""),bconf.get("sales_path","")], chunk_size_sentences=3)
st.session_state.chunks = chunks
st.session_state.chunk_meta = chunk_meta

# -------------------------
# Prompt suggestions (collapsible)
# -------------------------
with st.expander("💡 Prompt Suggestions", expanded=False):
    col1,col2,col3 = st.columns(3)
    suggestions = ["Generate sales opener","Handle objection: efficacy","Handle objection: safety","Summarize key benefit","Provide quick win tip"]
    for s in suggestions:
        for c in [col1,col2,col3]:
            if c.button(s): st.session_state.main_input = s

# -------------------------
# Main chat
# -------------------------
chat_container = st.container()
with st.form("main_input_form", clear_on_submit=True):
    user_input = st.text_area("Ask something:", st.session_state.main_input, height=96)
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role": "user", "content": user_input.strip()})
        add_ai_response(user_input.strip())
        st.session_state.main_input = ""

with chat_container:
    for idx, entry in enumerate(st.session_state.chat_history):
        if entry["role"] == "user": render_user_message(entry["content"])
        else:
            render_ai_message(entry["content"])
            plain = re.sub(r"<[^>]+>", "", entry.get("content", ""))[:1500]
            audio_b64 = generate_audio(plain)
            if audio_b64: st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")
            # Feedback buttons
            fb_cols = st.columns(3)
            key_content = entry["content"]
            if key_content not in st.session_state.feedback:
                if fb_cols[0].button("👍 Like", key=f"like_{idx}"): st.session_state.feedback[key_content] = "like"
                if fb_cols[1].button("👎 Dislike", key=f"dislike_{idx}"):
                    st.session_state.feedback[key_content] = "dislike"
                    for i, ch in enumerate(["Unclear","Too long","Not relevant"]):
                        if st.columns(3)[i].button(ch, key=f"dislike_choice_{idx}_{i}"): add_ai_response("Follow-up based on user dislike", follow_up=True, dislike_choice=ch)
                if fb_cols[2].button("ℹ️ Need More", key=f"needmore_{idx}"): st.session_state.feedback[key_content] = "need_more"; add_ai_response("Expand previous answer", follow_up=True)

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown('<div class="fixed-disclaimer">💡 This tool is for internal sales support purposes only. All medical info should be verified from official sources.</div>', unsafe_allow_html=True)
