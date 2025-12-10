# app_final_merged_complete.py - Fully merged AI Sales Call Assistant (Hologram avatar, personas, tones, objections, prompts, PDF, audio)
import streamlit as st
import os, re, tempfile, base64, io
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
        "chat_history": [], "main_input": "", "selected_brand": "shingrix", "temperature": 0.95,
        "search_mode": "deep", "medical_summary": "", "sales_summary": "", "uploaded_pdf_text": "",
        "pdf_summary": "", "feedback": {}, "dislike_state": None, "language": "English",
        "hcp_persona": "Friendly", "hcp_personality": "Friendly", "tone": "executive"
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)
_init_session()

# -------------------------
# CSS
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
# Background
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
        </style>""", unsafe_allow_html=True)
    except Exception: pass
set_dynamic_background(BACKGROUND_PATH)

# -------------------------
# GROQ client
# -------------------------
def load_groq_client():
    api_key = os.getenv("GROQ_API_KEY","") or (st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else "")
    if not api_key or Groq is None: return None
    try: return Groq(api_key=api_key)
    except Exception: return None

# -------------------------
# Brand data
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
                 "specialties":["Oncologist","Medical Oncologist"],
                 "references_path":".devcontainer/references/jemperli/","sales_path":".devcontainer/SalesModule/jemperli/",
                 "call_flow":["COCO","Anchor","Engage","Close"],
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
EXTRA_PERSONAS=["Evidence-led","Time-pressured","Skeptical","Early-adopter"]
def get_persona_options(brand_key):
    base = brand_data.get(brand_key, {}).get("personas", [])
    return base + [p for p in EXTRA_PERSONAS if p not in base]

# -------------------------
# Helpers: file reading, summarizing, local search
# -------------------------
def read_file_text(path):
    if not os.path.exists(path): return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path,"r",encoding="utf-8",errors="ignore") as fh: return fh.read()
    except: return ""

def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas=[],[]
    for folder in folders:
        if not folder or not os.path.exists(folder): continue
        files=[f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf",".txt"))]
        for fname in files:
            p=os.path.join(folder,fname)
            text=read_file_text(p)
            if not text: continue
            sents = re.split(r'(?<=[\.\?\!])\s+', text)
            for i in range(0, max(1,len(sents)), chunk_size_sentences):
                chunk=" ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk: chunks.append(chunk); metas.append({"filename":fname,"folder":folder,"start":i})
    return chunks, metas

def local_search_snippets(query,chunks,metas,top_n=3):
    if not chunks: return []
    if SKLEARN_AVAILABLE:
        try:
            vectorizer=TfidfVectorizer(stop_words="english").fit(chunks+[query])
            chunk_vecs=vectorizer.transform(chunks)
            q_vec=vectorizer.transform([query])
            sims=linear_kernel(q_vec,chunk_vecs).flatten()
            top_idxs=sims.argsort()[::-1][:top_n]
            results=[]
            for idx in top_idxs:
                if sims[idx]<=0: continue
                results.append({"score":float(sims[idx]),"text":chunks[idx],"meta":metas[idx]})
            return results
        except: pass
    out=[]; q=query.lower()
    for i,c in enumerate(chunks):
        if q in c.lower(): out.append({"score":1.0,"text":c,"meta":metas[i]})
        if len(out)>=top_n: break
    return out

def simple_summary(text,bullets=6):
    if not text: return ""
    sents=re.split(r'(?<=[\.\?\!])\s+',text)
    selected=[s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- "+s for s in selected])

def model_summarize(text, bullets=6):
    if not text: return ""
    client=load_groq_client()
    if client:
        try:
            prompt=f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp=client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":prompt}], temperature=0.2)
            content=getattr(resp.choices[0].message,"content",None) or getattr(resp.choices[0],"text","")
            return content
        except: return simple_summary(text, bullets)
    return simple_summary(text, bullets)

# -------------------------
# Audio
# -------------------------
def generate_audio(text):
    if not text: return ""
    if ELEVENLABS_AVAILABLE:
        try:
            elevenlabs.api_key=st.secrets.get("ELEVENLABS_API_KEY","")
            audio_stream=elevenlabs.generate(text=text,voice="alloy",model="eleven_multilingual_v1",stream=True)
            tmp=tempfile.NamedTemporaryFile(delete=False,suffix=".mp3")
            with open(tmp.name,"wb") as f:
                for chunk in audio_stream: f.write(chunk)
            with open(tmp.name,"rb") as fh: return base64.b64encode(fh.read()).decode()
        except: pass
    if gTTS:
        try:
            tmp=tempfile.NamedTemporaryFile(delete=False,suffix=".mp3")
            gTTS(text=text,lang="en",slow=False).save(tmp.name)
            with open(tmp.name,"rb") as fh: return base64.b64encode(fh.read()).decode()
        except: pass
    return ""

# -------------------------
# Persona & tone helpers
# -------------------------
def persona_profile(persona_name):
    p=persona_name.lower(); profile={"priority":"","style":"","quick_win":""}
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

def tone_prefix(t):
    t=(t or "").lower()
    if t=="executive": return "(Executive)"
    if t=="coaching": return "(Coaching)"
    if t=="persuasive": return "(Persuasive)"
    return "(Clinical)"

# -------------------------
# Story & objection builders
# -------------------------
def make_story_for_step(step, brand_key, persona_name, tone, snippet=None):
    safe_snip = escape(snippet) if snippet else ""
    brand = brand_data.get(brand_key, {}).get("display", brand_key)
    prof = persona_profile(persona_name)
    t_pref = tone_prefix(tone)

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
    if "influence" in step.lower() or "impact" in step.lower():
        return f"<div class='step-title'>Influence {t_pref}</div><div>Share key data snippet: \"{safe_snip}\"</div><div>Micro-action: Ask doctor to commit to patient identification or guideline review.</div>"
    if "close" in step.lower() or "analyze" in step.lower():
        return f"<div class='step-title'>Close/Analyze {t_pref}</div><div>Wrap-up discussion, confirm action, summarize learning points.</div>"
    return f"<div class='step-title'>{step} {t_pref}</div><div>General tip: Keep it aligned with {prof['priority']} and persona style ({prof['style']}).</div>"

def show_objections(brand_key):
    obs = brand_data.get(brand_key, {}).get("objections", {})
    if not obs: return
    st.markdown("<div><b>Objection Handling:</b></div>", unsafe_allow_html=True)
    for k,v in obs.items():
        st.markdown(f"<div class='objection'><b>{k.title()}:</b> {v}</div>", unsafe_allow_html=True)

# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    st.image(GSK_LOGO_RAW,width=120)
    st.title("AI Sales Assistant")
    st.selectbox("Select Brand", options=list(brand_data.keys()), index=list(brand_data.keys()).index(st.session_state.selected_brand), key="selected_brand")
    st.selectbox("Persona", options=get_persona_options(st.session_state.selected_brand), key="hcp_persona")
    st.selectbox("Tone", options=["executive","coaching","persuasive"], key="tone")
    st.slider("Creativity (Temperature)",0.1,1.0,value=st.session_state.temperature,step=0.05,key="temperature")
    st.file_uploader("Upload PDF for Summarization", type=["pdf","txt"], key="uploaded_pdf")
    st.button("Generate PDF Summary", on_click=lambda: st.session_state.update({"pdf_summary": model_summarize(read_file_text(st.session_state.uploaded_pdf.name) if st.session_state.uploaded_pdf else "", bullets=6)}))
    st.markdown("---")

# -------------------------
# Main UI
# -------------------------
st.markdown(f"""
<div class="title-box">
<img class="left-logo" src="{GSK_LOGO_RAW}">
<img class="right-logo" src="{AI_LOGO_RAW}">
<h2 style='margin:0;color:#000;'>AI Sales Call Assistant</h2>
</div>
""", unsafe_allow_html=True)

st.image(AI_AVATAR, width=120, caption="Holographic AI")

# Chat history
for msg in st.session_state.chat_history:
    if msg["sender"]=="user":
        st.markdown(f"<div class='user-bubble'>{escape(msg['text'])}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='ai-message'><img class='ai-avatar' src='{AI_AVATAR}'><div class='ai-bubble'>{msg['text']}</div></div>", unsafe_allow_html=True)

st.text_area("Your message:", key="main_input", height=80)
if st.button("Send"):
    user_text = st.session_state.main_input.strip()
    if user_text:
        st.session_state.chat_history.append({"sender":"user","text":user_text})
        # Generate response: pick call step
        brand_key = st.session_state.selected_brand
        persona = st.session_state.hcp_persona
        tone = st.session_state.tone
        steps = brand_data.get(brand_key,{}).get("call_flow",["Prepare","Engage","Create Opportunities","Influence","Close"])
        snippet=""
        if st.session_state.pdf_summary: snippet=st.session_state.pdf_summary
        ai_response="\n".join([make_story_for_step(step,brand_key,persona,tone,snippet) for step in steps])
        st.session_state.chat_history.append({"sender":"ai","text":ai_response})
        st.session_state.main_input=""

# Show objections
show_objections(st.session_state.selected_brand)

st.markdown("<div class='fixed-disclaimer'>⚠️ All content is AI-assisted and for sales simulation only.</div>", unsafe_allow_html=True)
