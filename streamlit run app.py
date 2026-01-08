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
        "prompt_suggestions": ["Handle objection", "Summarize key points", "Prepare sales script", "Follow-up strategy"],
        "persona": "Doctor",
        "tone": "executive",
        "objection": "",
        "audio_enabled": False
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
.prompt-suggestion{ display:inline-block; background:#f0f0f0; padding:4px 8px; margin:2px; border-radius:6px; cursor:pointer; font-size:13px; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Background helper
# -------------------------
def set_dynamic_background(image_path):
    if not os.path.exists(image_path):
        return
    try:
        with open(image_path, "rb") as img_file:
            encoded = base64.b64encode(img_file.read()).decode()
        st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background: linear-gradient(90deg, rgba(255,140,0,0.08), rgba(255,165,0,0.03)),
                        url("data:image/png;base64,{encoded}");
            background-repeat: no-repeat;
            background-position: right top;
            background-size: cover;
        }}
        </style>
        """, unsafe_allow_html=True)
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
        "objections": {"efficacy":"Focus on durable protection and age-agnostic efficacy evidence.",
                       "safety":"Acknowledge common AEs, then contrast with risk of complications from shingles.",
                       "cost":"Frame cost as prevention of downstream complications and reduce clinic workload."}
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
        "objections": {"efficacy":"Discuss durable responses in dMMR/MSI-H and appropriate patient selection.",
                       "safety":"Share safety profile and monitoring guidance to reduce perceived risk.",
                       "access":"Offer starter kits or initiation support and reimbursement pathways."}
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
        "objections": {"device":"Offer quick practical coaching and demo materials.",
                       "coverage":"Explain access options and patient support programs.",
                       "effectiveness":"Share comparative outcomes framed for real-world practice."}
    }
}

EXTRA_PERSONAS = ["Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"]
def get_persona_options(brand_key):
    base = brand_data.get(brand_key, {}).get("personas", [])
    combined = base + [p for p in EXTRA_PERSONAS if p not in base]
    return combined

# -------------------------
# Helpers
# -------------------------
def clean_text(text):
    if not text: return ""
    text = ''.join(c if c.isprintable() else ' ' for c in text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

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
    except:
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
            if not text: continue
            sents = re.split(r'(?<=[\.\?\!])\s+', text)
            for i in range(0, max(1,len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename": fname, "folder": folder, "start": i})
    return chunks, metas

def local_search_snippets(query, chunks, metas, top_n=3):
    if not chunks: return []
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks + [query])
            chunk_vecs = vectorizer.transform(chunks)
            q_vec = vectorizer.transform([query])
            sims = linear_kernel(q_vec, chunk_vecs).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            results = []
            for idx in top_idxs:
                if sims[idx] <= 0: continue
                results.append({"score": float(sims[idx]), "text": chunks[idx], "meta": metas[idx]})
            return results
        except:
            pass
    out = []
    q = query.lower()
    for i, c in enumerate(chunks):
        if q in c.lower():
            out.append({"score":1.0, "text": c, "meta": metas[i]})
            if len(out)>=top_n: break
    return out

def simple_summary(text, bullets=6):
    if not text: return ""
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- "+s for s in selected])

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
            return clean_text(content)
        except:
            return simple_summary(text, bullets)
    else:
        return simple_summary(text, bullets)

def generate_audio(text):
    if not text: return ""
    if ELEVENLABS_AVAILABLE:
        try:
            elevenlabs.api_key = st.secrets.get("ELEVENLABS_API_KEY", "")
            audio_stream = elevenlabs.generate(text=text, voice="alloy", model="eleven_multilingual_v1", stream=True)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            with open(tmp.name, "wb") as f:
                for chunk in audio_stream: f.write(chunk)
            with open(tmp.name,"rb") as fh:
                return base64.b64encode(fh.read()).decode()
        except: pass
    if gTTS:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            gTTS(text=text, lang="en", slow=False).save(tmp.name)
            with open(tmp.name,"rb") as fh:
                return base64.b64encode(fh.read()).decode()
        except: pass
    return ""

# -------------------------
# Sidebar: Filters & Persona
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]

    segment = st.selectbox("Segment", bconf["segments"])
    persona_options = get_persona_options(sel_brand)
    persona = st.selectbox("HCP Persona", persona_options, key="persona")
    barrier = st.multiselect("Doctor Barrier", bconf["barriers"])
    specialty = st.selectbox("Specialty", bconf["specialties"])
    objective = st.selectbox("Objective", ["Awareness","Adoption","Retention"])
    st.session_state.temperature = st.slider("Temperature", 0.0,1.0, st.session_state.temperature, 0.05)
    st.session_state.search_mode = st.selectbox("Search mode", ["deep","shallow"])
    st.session_state.language = st.radio("Language", ["English","Arabic"])
    tone = st.selectbox("Tone", ["executive","coaching","persuasive","clinical"], index=0, key="tone")
    st.session_state.audio_enabled = st.checkbox("Enable Audio", value=st.session_state.audio_enabled)
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []
        st.experimental_rerun()

# -------------------------
# Title box
# -------------------------
st.markdown(f"""
<div class="title-box">
    <img src="{GSK_LOGO_RAW}" class="left-logo">
    <h2>💡 AI Sales Call Assistant — {bconf['display']}</h2>
    <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# -------------------------
# Prompt suggestions UI
# -------------------------
with st.expander("💡 Prompt Suggestions", expanded=False):
    for i, p in enumerate(st.session_state.prompt_suggestions):
        if st.button(p, key=f"sugg_{i}"):
            st.session_state.main_input = p

# -------------------------
# PDF upload & summary
# -------------------------
uploaded_file = st.file_uploader("Upload PDF/Text for reference", type=["pdf","txt"])
if uploaded_file:
    if uploaded_file.type=="application/pdf" and PdfReader:
        reader = PdfReader(uploaded_file)
        pdf_text = "".join([p.extract_text() or "" for p in reader.pages])
    else:
        pdf_text = clean_text(uploaded_file.getvalue().decode("utf-8",errors="ignore"))
    st.session_state.uploaded_pdf_text = pdf_text
    st.session_state.pdf_summary = model_summarize(pdf_text, bullets=6)
    st.success("PDF summarized successfully!")

if st.session_state.pdf_summary:
    with st.expander("📄 Uploaded PDF Summary", expanded=False):
        st.markdown(st.session_state.pdf_summary)

# -------------------------
# Build corpus for local search
# -------------------------
corpus_folders = [bconf.get("references_path",""), bconf.get("sales_path","")]
chunks, chunk_meta = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# AI response helper
# -------------------------
def generate_ai_response(prompt_text):
    snippets = local_search_snippets(prompt_text, chunks, chunk_meta, top_n=6)
    flow_html = []
    for i, step in enumerate(bconf.get("call_flow", ["Prepare","Engage","Create Opportunities","Influence","Close"])):
        sn = snippets[i]["text"] if i < len(snippets) else ""
        flow_html.append(f"<div class='step-title'>{escape(step)}</div><div>{escape(sn)}</div>")
    return "\n".join(flow_html)

# -------------------------
# Chat input form
# -------------------------
with st.form("main_input_form", clear_on_submit=True):
    user_input = st.text_area("Your Message:", st.session_state.main_input, height=80)
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role":"user","content":user_input.strip()})
        ai_resp = generate_ai_response(user_input.strip())
        st.session_state.chat_history.append({"role":"assistant","content":ai_resp})
        st.session_state.main_input = ""

# -------------------------
# Display chat
# -------------------------
for entry in st.session_state.chat_history:
    if entry.get("role")=="user":
        st.markdown(f'<div class="chat-bubble-user">{escape(entry.get("content",""))}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">{entry.get("content","")}</div>', unsafe_allow_html=True)
        if st.session_state.audio_enabled:
            plain = re.sub(r"<[^>]+>","",entry.get("content",""))[:1500]
            audio_b64 = generate_audio(plain)
            if audio_b64: st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown('<div class="fixed-disclaimer">💡 This tool is for internal sales support purposes only. Verify medical info from official sources.</div>', unsafe_allow_html=True)
