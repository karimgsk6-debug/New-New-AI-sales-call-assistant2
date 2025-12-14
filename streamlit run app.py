# app_final_merged_predictive.py - Fully merged, predictive AI Sales Call Assistant
import streamlit as st
import os, re, tempfile, base64, io
from datetime import datetime
from html import escape

# Soft imports
try:
    from groq import Groq
except:
    Groq = None

try:
    from PyPDF2 import PdfReader
except:
    PdfReader = None

try:
    from gtts import gTTS
except:
    gTTS = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except:
    SKLEARN_AVAILABLE = False

try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except:
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
# CSS for avatar & chat
# -------------------------
st.markdown("""
<style>
.title-box{ background: rgba(255,255,255,0.85); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; position:relative; margin-bottom:12px; }
.title-box img.left-logo{ position:absolute; left:12px; height:48px; }
.title-box img.right-logo{ position:absolute; right:12px; height:48px; }

.ai-message { display:flex; align-items:flex-start; gap:12px; margin:10px 0; }
.ai-avatar { width:52px; height:52px; border-radius:50%; box-shadow: 0 0 12px rgba(0,255,255,0.6); flex-shrink:0; animation:holoPulse 2.5s infinite ease-in-out; }
@keyframes holoPulse { 0% { box-shadow:0 0 8px rgba(0,255,255,0.35);} 50% { box-shadow:0 0 22px rgba(0,255,255,0.9);} 100% { box-shadow:0 0 8px rgba(0,255,255,0.35);} }
.ai-bubble { background: rgba(255,255,255,0.06); border:1px solid rgba(0,255,255,0.18); color:#E6FBFF; padding:14px; border-radius:14px; backdrop-filter: blur(6px); max-width:90%; white-space:pre-wrap; }

.user-bubble{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }

.citation-box{ font-size:12px; color:#bcd; margin-left:6px; margin-bottom:6px; }
.fixed-disclaimer{ font-size:12px; color:#aac; margin-top:16px; opacity:0.9; }
.step-title{ font-weight:700; margin-top:8px; color:#BFF; }
.story{ font-style:italic; margin:6px 0 10px 0; color:#DFF; }
.objection{ background:rgba(255,248,240,0.06); padding:8px; border-radius:8px; margin:6px 0; border:1px solid rgba(255,224,198,0.08); color:#FFD; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Background
# -------------------------
def set_background(image_path):
    if not os.path.exists(image_path): return
    try:
        with open(image_path,"rb") as f:
            enc=base64.b64encode(f.read()).decode()
        st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background: linear-gradient(90deg, rgba(255,140,0,0.06), rgba(255,165,0,0.02)),
                        url("data:image/png;base64,{enc}");
            background-repeat:no-repeat;
            background-position:right top;
            background-size:cover;
        }}
        </style>""",unsafe_allow_html=True)
    except: pass
set_background(BACKGROUND_PATH)

# -------------------------
# GROQ client loader
# -------------------------
def load_groq_client():
    key = os.getenv("GROQ_API_KEY","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") or (st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else "")
    if not key or not Groq: return None
    try: return Groq(api_key=key)
    except: return None

# -------------------------
# Brand, persona & helper functions
# -------------------------
brand_data = {
    "shingrix": {
        "display":"Shingrix",
        "segments":["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas":["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers":["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
        "specialties":["GP","Dermatologist","Cardiology","Endocrinology","Immunology","Internal Medicine","Rheumatology"],
        "references_path":".devcontainer/references/shingrix/",
        "sales_path":".devcontainer/SalesModule/shingrix/",
        "call_flow":["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Analyze"],
        "objections":{"efficacy":"Focus on durable protection and age-agnostic efficacy evidence.",
                      "safety":"Acknowledge common AEs, contrast with shingles complications.",
                      "cost":"Frame cost as prevention of downstream complications."}
    },
    "jemperli": {
        "display":"Jemperli",
        "segments":["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas":["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers":["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties":["Oncologist","Medical Oncologist"],
        "references_path":".devcontainer/references/jemperli/",
        "sales_path":".devcontainer/SalesModule/jemperli/",
        "call_flow":["COCO","Anchor","Engage","Close"],
        "objections":{"efficacy":"Discuss durable responses in dMMR/MSI-H patients.",
                      "safety":"Share safety profile and monitoring guidance.",
                      "access":"Offer starter kits or initiation support and reimbursement pathways."}
    },
    "trelegy": {
        "display":"Trelegy",
        "segments":["Awareness","Diagnosis","Adoption","Adherence"],
        "personas":["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers":["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties":["GP","Pulmonologist","Internal Medicine","Respiratory Specialist"],
        "references_path":".devcontainer/references/trelegy/",
        "sales_path":".devcontainer/SalesModule/trelegy/",
        "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"],
        "objections":{"device":"Offer quick practical coaching and demo materials.",
                      "coverage":"Explain access options and patient support programs.",
                      "effectiveness":"Share comparative outcomes framed for real-world practice."}
    }
}

EXTRA_PERSONAS = ["Evidence-led","Time-pressured","Skeptical","Early-adopter"]
def get_persona_options(brand_key):
    base = brand_data.get(brand_key, {}).get("personas", [])
    return base + [p for p in EXTRA_PERSONAS if p not in base]

# -------------------------
# File reading, corpus, search
# -------------------------
def read_file_text(path):
    if not os.path.exists(path): return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path,"r",encoding="utf-8",errors="ignore") as f: return f.read()
    except: return ""

def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas = [],[]
    for folder in folders:
        if not folder or not os.path.exists(folder): continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf",".txt"))]
        for fname in files:
            p = os.path.join(folder,fname)
            text = read_file_text(p)
            if not text: continue
            sents = re.split(r'(?<=[\.\?\!])\s+', text)
            for i in range(0,max(1,len(sents)),chunk_size_sentences):
                chunk=" ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename":fname,"folder":folder,"start":i})
    return chunks, metas

def local_search_snippets(query,chunks,metas,top_n=3):
    if not chunks: return []
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks+[query])
            chunk_vecs = vectorizer.transform(chunks)
            q_vec = vectorizer.transform([query])
            sims = linear_kernel(q_vec,chunk_vecs).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            return [{"score":float(sims[idx]),"text":chunks[idx],"meta":metas[idx]} for idx in top_idxs if sims[idx]>0]
        except: pass
    return [{"score":1.0,"text":c,"meta":metas[i]} for i,c in enumerate(chunks) if query.lower() in c.lower()][:top_n]

def simple_summary(text,bullets=6):
    if not text: return ""
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    return "\n".join(["- "+s for s in sents[:bullets]])

def model_summarize(text,bullets=6):
    if not text: return ""
    client = load_groq_client()
    if client:
        try:
            prompt=f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
                        messages=[{"role":"user","content":prompt}],
                        temperature=0.2)
            content = getattr(resp.choices[0].message,"content",None) or getattr(resp.choices[0],"text","")
            return content
        except: return simple_summary(text,bullets)
    return simple_summary(text,bullets)

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
            return base64.b64encode(open(tmp.name,"rb").read()).decode()
        except: pass
    if gTTS:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False,suffix=".mp3")
            gTTS(text=text,lang="en",slow=False).save(tmp.name)
            return base64.b64encode(open(tmp.name,"rb").read()).decode()
        except: pass
    return ""

# -------------------------
# Persona & tone
# -------------------------
def persona_profile(name):
    p=name.lower()
    profiles = {
        "evidence": {"priority":"data & outcomes","style":"precise, cite trials","quick_win":"1-slide key outcomes"},
        "time":{"priority":"speed & simplicity","style":"concise, action-oriented","quick_win":"nurse-ready checklist"},
        "skeptical":{"priority":"safety & credibility","style":"address objections first","quick_win":"safety data & monitoring"},
        "early":{"priority":"innovation","style":"enthusiastic, highlight benefits","quick_win":"pilot/benchmark opportunity"},
        "uncommitted":{"priority":"ease & persuasion","style":"relatable, low-friction","quick_win":"patient education"},
        "reluctant":{"priority":"efficiency","style":"evidence-lite + workflow support","quick_win":"nurse script"},
        "patient":{"priority":"patient experience","style":"storytelling, adherence focus","quick_win":"patient leaflet"},
        "committed":{"priority":"scale & advocacy","style":"build on success","quick_win":"co-create guideline prompts"}
    }
    for k,v in profiles.items():
        if k in p: return v
    return {"priority":"clinician-focused","style":"clear and helpful","quick_win":"short actionable commitment"}

def tone_prefix(t):
    t=(t or "").lower()
    return {"executive":"(Executive)","coaching":"(Coaching)","persuasive":"(Persuasive)"}.get(t,"(Clinical)")

# -------------------------
# Story + steps
# -------------------------
def make_story_for_step(step,brand_key,persona_name,tone,snippet=None):
    safe_snip = escape(snippet) if snippet else ""
    brand = brand_data.get(brand_key,{}).get("display",brand_key)
    prof = persona_profile(persona_name)
    t_pref = tone_prefix(tone)
    if "prepare" in step.lower():
        return f"<div class='step-title'>Prepare {t_pref}</div><div>Hook: Lead with {prof['priority']}.</div><div class='story'>Example: Doctor, an insight: {safe_snip}</div>"
    if "engage" in step.lower():
        return f"<div class='step-title'>Engage {t_pref}</div><div>Hook: Discovery focused on persona ({prof['style']}).</div><div class='story'>Example: {safe_snip or 'Ask about current approach.'}</div>"
    if "create" in step.lower() or "opportun" in step.lower():
        return f"<div class='step-title'>Create Opportunities {t_pref}</div><div>Hook: Convert interest into concrete next step ({prof['quick_win']}).</div><div class='story'>Example: {safe_snip or 'Pilot with 5 patients.'}</div>"
    if "influence" in step.lower():
        return f"<div class='step-title'>Influence {t_pref}</div><div>Hook: Persona-aware pitch with real example.</div><div class='story'>Example: {safe_snip or f'Patient improved after {brand}.'}</div>"
    if "impact" in step.lower() or "gso" in step.lower():
        return f"<div class='step-title'>Impact GSO {t_pref}</div><div>Hook: Clinic-level benefit.</div><div class='story'>Example: {safe_snip or 'Propose pilot and metrics.'}</div>"
    if "analy" in step.lower() or "post" in step.lower():
        return f"<div class='step-title'>Analyze {t_pref}</div><div>Hook: Reinforce partnership, summarize outcomes.</div><div class='story'>Example: {safe_snip or 'Send 1-page summary.'}</div>"
    return f"<div class='step-title'>{escape(step)}</div><div class='story'>Example: {safe_snip}</div>"

# -------------------------
# Objection handling
# -------------------------
def objection_response(product_key,objection_key,persona):
    product=brand_data.get(product_key,{})
    base=product.get("objections",{})
    reply=base.get(objection_key,"Acknowledge concern, offer concise evidence, propose next step.")
    prof=persona_profile(persona)
    if "evidence" in persona.lower():
        return f"{reply} Provide trial highlights and 1-page evidence summary."
    if "time" in persona.lower():
        return f"{reply} Offer single-sentence script and nurse checklist."
    if "skeptical" in persona.lower():
        return f"{reply} Show safety data and propose conservative pilot."
    if "early" in persona.lower():
        return f"{reply} Highlight differentiation and co-design pilot."
    return f"{reply} (Quick win: {prof['quick_win']})"

# -------------------------
# Predictive sales flow
# -------------------------
def generate_sales_flow(prompt,persona_name,tone):
    p=prompt.lower()
    snippets=local_search_snippets(prompt,chunks,chunk_meta,top_n=6) if 'chunks' in globals() else []
    flow=brand_data.get(st.session_state.selected_brand,{}).get("call_flow",[])
    html=""
    for step in flow:
        snippet_text = snippets.pop(0)['text'] if snippets else ""
        html+=make_story_for_step(step,st.session_state.selected_brand,persona_name,tone,snippet_text)
    return html

# -------------------------
# Chat rendering
# -------------------------
def render_ai_message(msg_text):
    st.markdown(f"""
    <div class='ai-message'>
        <img src='{AI_AVATAR}' class='ai-avatar'/>
        <div class='ai-bubble'>{msg_text}</div>
    </div>
    """,unsafe_allow_html=True)

def render_user_message(msg_text):
    st.markdown(f"<div class='user-bubble'>{escape(msg_text)}</div>",unsafe_allow_html=True)

# -------------------------
# Sidebar + chat input
# -------------------------
with st.sidebar:
    st.selectbox("Brand",options=list(brand_data.keys()),index=0,key="selected_brand")
    st.selectbox("Persona",options=get_persona_options(st.session_state.selected_brand),index=0,key="hcp_persona")
    st.selectbox("Tone",options=["executive","coaching","persuasive"],key="tone")
    st.slider("Temperature",0.1,1.0,0.95,0.05,key="temperature")
    uploaded_file = st.file_uploader("Upload PDF or TXT", type=["pdf","txt"])
    if uploaded_file:
        text = read_file_text(uploaded_file.name)
        st.session_state.uploaded_pdf_text = text
        st.session_state.pdf_summary = model_summarize(text,bullets=6)
        st.markdown(f"<div class='story'>{st.session_state.pdf_summary}</div>",unsafe_allow_html=True)

st.text_area("Enter HCP input:",key="main_input",height=100)
if st.button("Send"):
    user_text = st.session_state.main_input.strip()
    if user_text:
        render_user_message(user_text)
        ai_resp = generate_sales_flow(user_text,st.session_state.hcp_persona,st.session_state.tone)
        render_ai_message(ai_resp)
        st.session_state.chat_history.append({"user":user_text,"ai":ai_resp})
        st.session_state.main_input=""

st.markdown("<div class='fixed-disclaimer'>💡 Internal sales support only. Verify all medical info.</div>",unsafe_allow_html=True)
