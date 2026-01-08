# app_final_enhanced.py - AI Sales Call Assistant (Enhanced with APACT & TTS + enriched examples)
import streamlit as st
import os, re, tempfile, base64, io
from datetime import datetime
from html import escape

# Soft imports
try:
    from groq import Groq
except Exception: Groq = None
try:
    from PyPDF2 import PdfReader
except Exception: PdfReader = None
try:
    from gtts import gTTS
except Exception: gTTS = None
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except Exception: SKLEARN_AVAILABLE = False
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except Exception: ELEVENLABS_AVAILABLE = False

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
st.markdown("""
<style>
.title-box{ background: rgba(255,255,255,0.75); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; position:relative; margin-bottom:12px; }
.title-box img.left-logo{ position:absolute; left:12px; height:48px; }
.title-box img.right-logo{ position:absolute; right:12px; height:48px; }
.chat-bubble-user{ background: rgba(0,0,0,0.08); color:#1111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }
.chat-bubble-ai{ background: #ffffff; color:#000; padding:12px 16px; border-radius:12px; box-shadow: 0 1px 6px rgba(0,0,0,0.085); margin:8px 0; max-width:90%; white-space:pre-wrap; }
.citation-box{ font-size:12px; color:#666; margin-left:6px; margin-bottom:6px; }
.fixed-disclaimer{ font-size:12px; color:#444; margin-top:16px; opacity:0.9; }
.step-title{ font-weight:700; margin-top:8px; }
.story{ font-style:italic; margin:6px 0 10px 0; }
ul.assist-list{ margin:6px 0 6px 18px; padding:0; }
.objection{ background:#fff8f0; padding:8px; border-radius:8px; margin:6px 0; border:1px solid #ffe0c6;}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Dynamic background
# -------------------------
def set_dynamic_background(image_path):
    if not os.path.exists(image_path): return
    try:
        with open(image_path,"rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
        st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background: linear-gradient(90deg, rgba(255,140,0,0.08), rgba(255,165,0,0.03)),
                        url("data:image/png;base64,{encoded}");
            background-repeat:no-repeat;
            background-position:right top;
            background-size:cover;
        }}
        </style>
        """, unsafe_allow_html=True)
    except: pass
set_dynamic_background(BACKGROUND_PATH)

# -------------------------
# GROQ client (optional)
# -------------------------
def load_groq_client():
    api_key = os.getenv("GROQ_API_KEY", "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") or (st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else "")
    if not api_key or Groq is None: return None
    try: return Groq(api_key=api_key)
    except: return None

# -------------------------
# Brand & persona data
# -------------------------
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "specialties": ["GP","Dermatologist","Cardiology","Endocrinology","Immunology","Internal Medicine","Rheumatology"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/",
        "call_flow": ["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Analyze"],
        "objections": {"efficacy":"Focus on durable protection and age-agnostic efficacy evidence.","safety":"Acknowledge common AEs, contrast with shingles risk.","cost":"Frame cost as prevention of complications and reduce workload."}
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas": ["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers":["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties":["Oncologist","Medical Oncologist"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli/",
        "call_flow": ["COCO","Anchor","Engage","Close"],
        "objections": {"efficacy":"Discuss durable responses in dMMR/MSI-H, select patients carefully.","safety":"Share safety profile and monitoring guidance.","access":"Offer starter kits and reimbursement pathways."}
    },
    "trelegy": {
        "display": "Trelegy",
        "segments":["Awareness","Diagnosis","Adoption","Adherence"],
        "personas":["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers":["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties":["GP","Pulmonologist","Internal Medicine","Respiratory Specialist"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy/",
        "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"],
        "objections": {"device":"Offer quick coaching and demo materials.","coverage":"Explain access options.","effectiveness":"Share comparative outcomes for real-world practice."}
    }
}

EXTRA_PERSONAS = ["Evidence-led","Time-pressured","Skeptical","Early-adopter"]
def get_persona_options(brand_key):
    base = brand_data.get(brand_key, {}).get("personas", [])
    return base + [p for p in EXTRA_PERSONAS if p not in base]

# -------------------------
# File reading, corpus, local search
# -------------------------
def read_file_text(path):
    if not os.path.exists(path): return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            return "".join([p.extract_text() or "" for p in PdfReader(path).pages])
        else:
            with open(path,"r",encoding="utf-8",errors="ignore") as fh:
                return fh.read()
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
            for i in range(0,max(1,len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk: chunks.append(chunk); metas.append({"filename":fname,"folder":folder,"start":i})
    return chunks, metas

def local_search_snippets(query, chunks, metas, top_n=3):
    if not chunks: return []
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks + [query])
            sims = linear_kernel(vectorizer.transform([query]), vectorizer.transform(chunks)).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            return [{"score":float(sims[i]),"text":chunks[i],"meta":metas[i]} for i in top_idxs if sims[i]>0]
        except: pass
    # fallback simple substring match
    q = query.lower(); out=[]
    for i, c in enumerate(chunks):
        if q in c.lower(): out.append({"score":1.0,"text":c,"meta":metas[i]}); 
        if len(out)>=top_n: break
    return out

def simple_summary(text, bullets=6):
    if not text: return ""
    sents = [s.strip() for s in re.split(r'(?<=[\.\?\!])\s+', text) if s.strip()]
    return "\n".join([f"- {s}" for s in sents[:bullets]])

def model_summarize(text, bullets=6):
    if not text: return ""
    client = load_groq_client()
    if client:
        try:
            prompt = f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                                 messages=[{"role":"user","content":prompt}],
                                                 temperature=0.2)
            content = getattr(resp.choices[0].message,"content", None) or getattr(resp.choices[0],"text","")
            return content
        except: return simple_summary(text, bullets)
    return simple_summary(text, bullets)

# -------------------------
# TTS generation
# -------------------------
def generate_audio(text):
    if not text: return ""
    if ELEVENLABS_AVAILABLE:
        try:
            elevenlabs.api_key = st.secrets.get("ELEVENLABS_API_KEY", "")
            audio_stream = elevenlabs.generate(text=text, voice="alloy", model="eleven_multilingual_v1", stream=True)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            with open(tmp.name,"wb") as f:
                for chunk in audio_stream: f.write(chunk)
            return base64.b64encode(open(tmp.name,"rb").read()).decode()
        except: pass
    if gTTS:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False,suffix=".mp3")
            gTTS(text=text, lang="en", slow=False).save(tmp.name)
            return base64.b64encode(open(tmp.name,"rb").read()).decode()
        except: pass
    return ""

# -------------------------
# Persona profiles
# -------------------------
def persona_profile(persona_name):
    p = persona_name.lower()
    mapping = {
        "evidence": {"priority":"data & outcomes","style":"precise, cite trial outcomes","quick_win":"1-slide key outcomes"},
        "time": {"priority":"speed & simplicity","style":"concise, action-oriented","quick_win":"nurse-ready checklist"},
        "skeptical":{"priority":"safety & credibility","style":"address objections first","quick_win":"safety data & monitoring plan"},
        "early":{"priority":"innovation & differentiation","style":"enthusiastic, highlight first-mover","quick_win":"co-design small pilot"},
        "uncommitted":{"priority":"ease & persuasion","style":"relatable, low-friction","quick_win":"patient education leave-behind"},
        "reluctant":{"priority":"efficiency & risk reduction","style":"evidence-lite + workflow","quick_win":"nurse script & time-saving tip"},
        "patient":{"priority":"patient experience","style":"storytelling & adherence","quick_win":"patient leaflet & story-based hook"},
        "committed":{"priority":"scale & advocacy","style":"build on success with scaling ideas","quick_win":"co-create local guideline prompts"}
    }
    for k in mapping:
        if k in p: return mapping[k]
    return {"priority":"clinician-focused","style":"clear & helpful","quick_win":"short actionable commitment"}

# -------------------------
# Tone prefix
# -------------------------
def tone_prefix(t):
    return {"executive":"(Executive)","coaching":"(Coaching)","persuasive":"(Persuasive)","clinical":"(Clinical)"}.get(t,"(Clinical)")

# -------------------------
# Generate enriched story step
# -------------------------
def make_story_for_step(step, brand_key, persona_name, tone, snippet=None):
    safe_snip = escape(snippet) if snippet else ""
    brand = brand_data.get(brand_key,{}).get("display",brand_key)
    prof = persona_profile(persona_name)
    t_pref = tone_prefix(tone)
    examples = {
        "Prepare": [
            f"Lead with an insight: {prof['priority']}",
            "Offer 30s hook highlighting clinic benefit",
            "Reference a key trial or patient trend"
        ],
        "Engage":[
            "Ask current workflow: How do you manage eligible patients?",
            "Use persona-aware discovery: What's your top challenge this month?",
            "Probe adoption pain points with gentle questions"
        ],
        "Create Opportunities":[
            "Pilot program: Track 8 patients for 4 weeks",
            "Offer nurse script or checklist for adoption",
            "Agree on one measurable metric for next visit"
        ],
        "Influence":[
            f"Share patient vignette: 72yo benefited from {brand}",
            "Highlight trial outcome relevant to persona",
            "Ask which patients mirror this scenario"
        ],
        "Impact GSO":[
            "Propose clinic-level pilot for 10 patients",
            "Emphasize low effort & high throughput",
            "Offer 1-slide summary for opt-in"
        ],
        "Analyze":[
            "Email 1-page summary with metrics",
            "Propose 2-week follow-up",
            "Highlight quick wins & next actions"
        ]
    }
    ex_list = examples.get(step.split()[0], ["Generic actionable example"])
    ex_html = "<ul>"+ "".join([f"<li>{escape(e)}</li>" for e in ex_list])+"</ul>"
    return f"<div class='step-title'>{escape(step)} {t_pref}</div><div>{ex_html}</div>"

# -------------------------
# APACT objection handling
# -------------------------
def objection_response_apact(product_key, objection_key, persona):
    base = brand_data.get(product_key,{}).get("objections",{})
    reply = base.get(objection_key,"Acknowledge concern, provide evidence, propose next step.")
    prof = persona_profile(persona)
    A = f"Acknowledge: I understand your concern about {objection_key}."
    P = "Probe: Could you tell me more about your specific experience or concerns?"
    A2 = f"Action: Here's what others have done to address {objection_key} — {reply}"
    C = "Confirm: Does this address your concern adequately?"
    T = "Transition: Let's move to next step in the workflow."
    return f"{A}\n{P}\n{A2}\n{C}\n{T} (Persona-tailored: {prof['quick_win']})"

# -------------------------
# Sales flow generator
# -------------------------
def generate_sales_flow(prompt, persona_name, tone):
    p = prompt.lower()
    snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=6)
    for brand_key in brand_data:
        if brand_key in p:
            flow = brand_data[brand_key]["call_flow"]
            parts = [f"<div><strong>Context:</strong> {brand_data[brand_key]['display']} — tailored to {escape(persona_name)} ({escape(tone)})</div>"]
            for i, step in enumerate(flow):
                sn = snippets[i]["text"] if i < len(snippets) else ""
                parts.append(make_story_for_step(step, brand_key, persona_name, tone, snippet=sn))
            # Objections with APACT
            parts.append("<div class='step-title'>Objection Handling (APACT)</div>")
            for obj in brand_data[brand_key]["objections"]:
                parts.append(f"<div class='objection'><strong>{obj.title()} —</strong> {escape(objection_response_apact(brand_key,obj,persona_name))}</div>")
            return "\n".join(parts)
    # default
    default_steps = ["Prepare","Engage","Create Opportunities","Influence","Close"]
    parts = [f"<div><strong>Context:</strong> General sales call — tailored to {escape(persona_name)} ({escape(tone)})</div>"]
    for step in default_steps: parts.append(make_story_for_step(step,"shingrix",persona_name,tone))
    return "\n".join(parts)

# -------------------------
# Sidebar UI
# -------------------------
st.sidebar.title("AI Sales Call Assistant")
st.sidebar.selectbox("Select Brand", options=list(brand_data.keys()), key="selected_brand")
persona_sel = st.sidebar.selectbox("Select Persona", options=get_persona_options(st.session_state.selected_brand))
tone_sel = st.sidebar.selectbox("Select Tone", options=["executive","coaching","persuasive","clinical"])
prompt_input = st.sidebar.text_area("Your prompt / question", key="main_input", height=120)

if st.sidebar.button("Generate Sales Call"):
    if prompt_input.strip():
        chunks, chunk_meta = build_corpus_for_folders([brand_data[st.session_state.selected_brand]["references_path"]])
        html_content = generate_sales_flow(prompt_input, persona_sel, tone_sel)
        st.session_state.chat_history.append({"user":prompt_input,"ai":html_content})
        st.experimental_rerun()

# -------------------------
# Main chat UI
# -------------------------
st.markdown(f"""
<div class='title-box'>
    <img class='left-logo' src='{GSK_LOGO_RAW}' />
    <div style='font-weight:800; font-size:24px'>AI Sales Call Assistant</div>
    <img class='right-logo' src='{AI_LOGO_RAW}' />
</div>
""", unsafe_allow_html=True)

for i, chat in enumerate(st.session_state.chat_history):
    st.markdown(f"<div class='chat-bubble-user'>{escape(chat['user'])}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='chat-bubble-ai'>{chat['ai']}</div>", unsafe_allow_html=True)
    # TTS button
    audio_b64 = generate_audio(chat['ai'])
    if audio_b64:
        st.audio(base64.b64decode(audio_b64), format="audio/mp3")

st.markdown("<div class='fixed-disclaimer'>⚠️ This tool is for educational sales training purposes only.</div>", unsafe_allow_html=True)
