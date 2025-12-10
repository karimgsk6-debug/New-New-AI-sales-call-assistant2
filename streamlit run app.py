# app_final_ready.py - Fully merged and fixed AI Sales Call Assistant
import streamlit as st
import os, re, tempfile, base64, io
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
# Initialize session_state safely
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
    if not os.path.exists(image_path):
        return
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
    except Exception:
        pass

set_dynamic_background(BACKGROUND_PATH)

# -------------------------
# GROQ client loader
# -------------------------
def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY", "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") or st.secrets.get("GROQ_API_KEY", "")
    if not api_key or Groq is None:
        return None
    try:
        return Groq(api_key=api_key)
    except:
        return None

# -------------------------
# Brand data (simplified here)
# -------------------------
brand_data = {
    "shingrix": {"display":"Shingrix", "segments":["R","A","C","E"], "personas":["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"], "barriers":["HCP does not consider HZ a risk","No time","Cost","Not convinced"], "specialties":["GP","Derm","Cardio"], "references_path":".devcontainer/references/shingrix/","sales_path":".devcontainer/SalesModule/shingrix/","call_flow":["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Analyze"],"objections":{"efficacy":"Durable protection","safety":"Acknowledge AEs","cost":"Prevent downstream complications"}}
}

# -------------------------
# Helpers: file reading, corpus, local search, summarization
# -------------------------
def read_file_text(path):
    if not os.path.exists(path):
        return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except:
        return ""

def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas = [], []
    for folder in folders:
        if not os.path.exists(folder):
            continue
        for fname in sorted(os.listdir(folder)):
            if fname.lower().endswith((".pdf",".txt")):
                text = read_file_text(os.path.join(folder,fname))
                sents = re.split(r'(?<=[\.\?\!])\s+', text)
                for i in range(0, len(sents), chunk_size_sentences):
                    chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                    if chunk:
                        chunks.append(chunk)
                        metas.append({"filename":fname,"folder":folder})
    return chunks, metas

def simple_summary(text, bullets=6):
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- "+s for s in selected])

def model_summarize(text, bullets=6):
    client = get_groq_client()
    if client:
        try:
            prompt = f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp = client.chat.completions.create(model="meta-llama/llama-4-scout-17b-16e-instruct",
                                                 messages=[{"role":"user","content":prompt}],
                                                 temperature=0.2)
            content = getattr(getattr(resp.choices[0],"message",{}),"content","") or getattr(resp.choices[0],"text","")
            return content
        except:
            return simple_summary(text, bullets)
    else:
        return simple_summary(text, bullets)

# -------------------------
# Sidebar - Brand selection and summaries
# -------------------------
with st.sidebar.expander("Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]

    segment = st.selectbox("Segment", bconf["segments"])
    persona_sel = st.selectbox("HCP Persona", bconf["personas"])
    st.session_state.hcp_persona = persona_sel
    st.session_state.tone = st.selectbox("Tone", ["executive","coaching","persuasive","clinical"], index=0)

# -------------------------
# Summarize references and sales
# -------------------------
refs_folder = bconf.get("references_path","")
sales_folder = bconf.get("sales_path","")

combined_refs = ""
if os.path.exists(refs_folder):
    for f in sorted(os.listdir(refs_folder)):
        if f.lower().endswith((".pdf",".txt")):
            combined_refs += read_file_text(os.path.join(refs_folder,f)) + "\n"

combined_sales = ""
if os.path.exists(sales_folder):
    for f in sorted(os.listdir(sales_folder)):
        if f.lower().endswith((".pdf",".txt")):
            combined_sales += read_file_text(os.path.join(sales_folder,f)) + "\n"

if not st.session_state.medical_summary and combined_refs.strip():
    st.session_state.medical_summary = model_summarize(combined_refs, bullets=6)
if not st.session_state.sales_summary and combined_sales.strip():
    st.session_state.sales_summary = model_summarize(combined_sales, bullets=6)

with st.sidebar.expander("📚 Medical References Summary"):
    st.markdown(st.session_state.medical_summary)
with st.sidebar.expander("💼 Sales Module Summary"):
    st.markdown(st.session_state.sales_summary)

# -------------------------
# Main Input & Chat Handling
# -------------------------
st.markdown(f'<h2>💡 AI Sales Call Assistant — {bconf["display"]}</h2>', unsafe_allow_html=True)
user_input = st.text_area("Ask the AI assistant...", value=st.session_state.main_input, key="main_input", height=80)

if st.button("Send", key="send_button") and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input})
    
    # AI response
    client = get_groq_client()
    ai_text = "Failed to generate AI response. Check API key."
    if client:
        try:
            resp = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role":"system","content":"You are a helpful AI assistant."},
                          {"role":"user","content":user_input[:12000]}],
                temperature=st.session_state.temperature
            )
            ai_text = getattr(getattr(resp.choices[0],"message",{}),"content","") or getattr(resp.choices[0],"text","")
        except:
            ai_text = "Failed to generate AI response. Try again."

    st.session_state.chat_history.append({"role":"ai","content":ai_text})
    st.session_state.main_input = ""

# -------------------------
# Display chat
# -------------------------
for entry in st.session_state.chat_history:
    if entry["role"]=="user":
        st.markdown(f'<div class="user-bubble">{escape(entry["content"])}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="ai-message">
            <img src="{AI_AVATAR}" class="ai-avatar" />
            <div class="ai-bubble">{entry['content']}</div>
        </div>
        """, unsafe_allow_html=True)

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown("""
<div class="fixed-disclaimer">
💡 This tool is for internal sales support purposes only. All medical info should be verified from official sources.
</div>
""", unsafe_allow_html=True)
