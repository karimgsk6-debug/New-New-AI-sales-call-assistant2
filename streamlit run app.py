# app_final_merged_smart.py - AI Sales Call Assistant (Smarter + RAG)
import streamlit as st
import os, re, io, base64, tempfile
from datetime import datetime
from html import escape

# Soft imports
try: from groq import Groq
except: Groq = None
try: from PyPDF2 import PdfReader
except: PdfReader = None
try: from gtts import gTTS
except: gTTS = None
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except: SKLEARN_AVAILABLE = False
try: import elevenlabs; ELEVENLABS_AVAILABLE=True
except: ELEVENLABS_AVAILABLE=False

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# -------------------------
# Initialize session state
# -------------------------
def _init_session():
    defaults = {
        "chat_history": [], "main_input": "", "selected_brand": "shingrix",
        "temperature": 0.95, "search_mode": "deep", "medical_summary": "",
        "sales_summary": "", "uploaded_pdf_text": "", "pdf_summary": "",
        "feedback": {}, "dislike_state": None, "language": "English",
        "hcp_persona": "Friendly", "hcp_personality": "Friendly", "tone": "executive",
        "chunks": [], "chunk_meta": []
    }
    for k,v in defaults.items():
        st.session_state.setdefault(k,v)
_init_session()

# -------------------------
# Brand configuration
# -------------------------
brand_data = {
    "shingrix": {
        "display":"Shingrix","segments":["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas":["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers":["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
        "specialties":["GP","Dermatologist","Cardiology","Endocrinology","Immunology","Internal Medicine","Rheumatology"],
        "references_path":".devcontainer/references/shingrix/","sales_path":".devcontainer/SalesModule/shingrix/",
        "call_flow":["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Analyze"],
        "objections":{"efficacy":"Focus on durable protection and age-agnostic efficacy evidence.",
                      "safety":"Acknowledge common AEs, then contrast with risk of complications from shingles.",
                      "cost":"Frame cost as prevention of downstream complications and reduce clinic workload."}
    },
    "jemperli": {
        "display":"Jemperli","segments":["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas":["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers":["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties":["Oncologist","Medical Oncologist"],
        "references_path":".devcontainer/references/jemperli/","sales_path":".devcontainer/SalesModule/jemperli/",
        "call_flow":["COCO","Anchor","Engage","Close"],
        "objections":{"efficacy":"Discuss durable responses in dMMR/MSI-H and appropriate patient selection.",
                      "safety":"Share safety profile and monitoring guidance to reduce perceived risk.",
                      "access":"Offer starter kits or initiation support and reimbursement pathways."}
    },
    "trelegy": {
        "display":"Trelegy","segments":["Awareness","Diagnosis","Adoption","Adherence"],
        "personas":["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers":["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties":["GP","Pulmonologist","Internal Medicine","Respiratory Specialist"],
        "references_path":".devcontainer/references/trelegy/","sales_path":".devcontainer/SalesModule/trelegy/",
        "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"],
        "objections":{"device":"Offer quick practical coaching and demo materials.",
                      "coverage":"Explain access options and patient support programs.",
                      "effectiveness":"Share comparative outcomes framed for real-world practice."}
    }
}

EXTRA_PERSONAS = ["Evidence-led","Time-pressured","Skeptical","Early-adopter"]
def get_persona_options(brand_key):
    base = brand_data.get(brand_key,{}).get("personas",[])
    combined = base + [p for p in EXTRA_PERSONAS if p not in base]
    return combined

# -------------------------
# File processing and RAG helpers
# -------------------------
def read_file_text(path):
    if not os.path.exists(path): return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
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
            for i in range(0,max(1,len(sents)),chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename":fname,"folder":folder,"start":i})
    return chunks, metas

def local_search_snippets(query,chunks,metas,top_n=4):
    if not chunks: return []
    out = []
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks+[query])
            chunk_vecs = vectorizer.transform(chunks)
            q_vec = vectorizer.transform([query])
            sims = linear_kernel(q_vec,chunk_vecs).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            for idx in top_idxs:
                if sims[idx]<=0: continue
                out.append({"score":float(sims[idx]),"text":chunks[idx],"meta":metas[idx]})
            return out
        except: pass
    # fallback exact search
    q=query.lower()
    for i,c in enumerate(chunks):
        if q in c.lower(): out.append({"score":1.0,"text":c,"meta":metas[i]})
        if len(out)>=top_n: break
    return out

def model_summarize(text, bullets=6):
    if not text: return ""
    client = None
    api_key = os.getenv("GROQ_API_KEY") or (st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else "")
    if Groq and api_key:
        try: client = Groq(api_key)
        except: pass
    if client:
        try:
            prompt = f"Summarize into {bullets} bullet points:\n{text[:12000]}"
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                                 messages=[{"role":"user","content":prompt}],
                                                 temperature=0.2)
            return getattr(resp.choices[0].message,"content","") or getattr(resp.choices[0],"text","")
        except: pass
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    return "\n".join(["- "+s for s in sents[:bullets]])

# -------------------------
# Persona & tone helpers
# -------------------------
def persona_profile(persona_name):
    p=persona_name.lower()
    profile={"priority":"","style":"","quick_win":""}
    if "evidence" in p: profile.update({"priority":"data & outcomes","style":"precise, cite trial outcomes","quick_win":"share 1-slide summary"}); return profile
    if "time" in p: profile.update({"priority":"speed & simplicity","style":"concise, action-oriented","quick_win":"provide nurse checklist"}); return profile
    if "skeptical" in p: profile.update({"priority":"safety & credibility","style":"address objections first","quick_win":"provide safety data"}); return profile
    if "early" in p: profile.update({"priority":"innovation & differentiation","style":"enthusiastic, highlight first-mover benefits","quick_win":"offer pilot"}); return profile
    if "uncommitted" in p: profile.update({"priority":"ease & persuasion","style":"relatable","quick_win":"leave-behind patient education"}); return profile
    if "reluctant" in p: profile.update({"priority":"efficiency","style":"evidence-lite","quick_win":"nurse script"}); return profile
    if "patient" in p: profile.update({"priority":"patient experience","style":"storytelling","quick_win":"patient leaflet"}); return profile
    if "committed" in p: profile.update({"priority":"scale & advocacy","style":"build on success","quick_win":"co-create guideline prompts"}); return profile
    profile.update({"priority":"clinician-focused","style":"clear and helpful","quick_win":"short actionable commitment"})
    return profile

def tone_prefix(t):
    t=(t or "").lower()
    return {"executive":"(Executive)","coaching":"(Coaching)","persuasive":"(Persuasive)"}.get(t,"(Clinical)")

# -------------------------
# Sales call flow builder using RAG
# -------------------------
def make_story_for_step(step, brand_key, persona_name, tone, snippet=None):
    brand = brand_data.get(brand_key,{}).get("display",brand_key)
    prof = persona_profile(persona_name)
    t_pref = tone_prefix(tone)
    snippet_text = snippet or ""
    return f"<div class='step-title'>{escape(step)} {t_pref}</div><div>Persona style: {prof['style']}</div><div class='story'>Example: {escape(snippet_text)}</div>"

def objection_response(product_key,objection_key,persona):
    product = brand_data.get(product_key,{})
    base = product.get("objections",{})
    reply = base.get(objection_key,"Acknowledge concern, offer concise evidence, propose next step.")
    prof = persona_profile(persona)
    return f"{reply} Tailored: {prof['quick_win']}"

def generate_sales_flow(prompt,persona_name,tone):
    chunks = st.session_state.chunks
    metas = st.session_state.chunk_meta
    snippets = local_search_snippets(prompt,chunks,metas,top_n=6)
    bkey = st.session_state.selected_brand
    flow = brand_data.get(bkey,{}).get("call_flow",["Prepare","Engage","Create Opportunities","Influence","Close"])
    parts=[f"<div><strong>Context:</strong> {bkey.title()} — tailored to {escape(persona_name)} ({escape(tone)})</div>"]
    for i,step in enumerate(flow):
        sn = snippets[i]["text"] if i<len(snippets) else ""
        parts.append(make_story_for_step(step,bkey,persona_name,tone,snippet=sn))
    parts.append("<div class='step-title'>Objection Handling</div>")
    for obj in brand_data.get(bkey,{}).get("objections",{}):
        parts.append(f"<div class='objection'><strong>{obj.title()} —</strong> {escape(objection_response(bkey,obj,persona_name))}</div>")
    return "\n".join(parts)

# -------------------------
# Add AI response
# -------------------------
def add_ai_response(prompt_text):
    persona_choice = st.session_state.hcp_persona
    tone_choice = st.session_state.tone
    header=f"<div class='step-title'>Acknowledged</div><div>Generating enriched product-specific sales call for {escape(persona_choice)} ({escape(tone_choice)} tone)...</div>"
    flow_html = generate_sales_flow(prompt_text,persona_choice,tone_choice)
    confirm="<div class='step-title'>Next step</div><div>Reply 'Yes' to draft 30s call script and 1-page leave-behind.</div>"
    ai_html="\n".join([header,flow_html,confirm])
    st.session_state.chat_history.append({"role":"assistant","content":ai_html,"citation":""})

# -------------------------
# Chat renderers
# -------------------------
def render_ai_message(message_html):
    st.markdown(f"""<div class="ai-message"><img src="{HOLO_AVATAR}" class="ai-avatar" /><div class="ai-bubble">{message_html}</div></div>""",unsafe_allow_html=True)
def render_user_message(msg):
    st.markdown(f'<div class="user-bubble">{escape(msg)}</div>',unsafe_allow_html=True)

# -------------------------
# Load references & build RAG corpus
# -------------------------
bconf=brand_data[st.session_state.selected_brand]
refs_folder = bconf.get("references_path","")
sales_folder = bconf.get("sales_path","")
corpus_folders=[refs_folder,sales_folder]
chunks,chunk_meta = build_corpus_for_folders(corpus_folders,chunk_size_sentences=3)
st.session_state.chunks = chunks
st.session_state.chunk_meta = chunk_meta
