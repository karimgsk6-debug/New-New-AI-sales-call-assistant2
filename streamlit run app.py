# app_fixed.py - Fixed AI Sales Call Assistant (Streamlit)
import streamlit as st
import os
import re
import tempfile
import base64
import io
from datetime import datetime
from html import escape

# Optional libs (soft imports)
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
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

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

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except Exception:
    PYTTSX3_AVAILABLE = False

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# Resource paths (adjust for your repo)
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
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
# Small CSS tweaks (white AI bubble)
# -------------------------
st.markdown(
    """
    <style>
    .title-box{ background: rgba(255,255,255,0.8); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; position:relative; }
    .title-box img.left-logo{ position:absolute; left:12px; height:48px; }
    .title-box img.right-logo{ position:absolute; right:12px; height:48px; }

    .chat-bubble-user{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }

    /* White bubble for AI responses */
    .chat-bubble-ai{ background: #ffffff; color:#000; padding:12px 16px; border-radius:12px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); margin:8px 0; max-width:90%; }

    .citation-box{ font-size:12px; color:#666; margin-left:6px; margin-bottom:6px; }

    .fixed-disclaimer{ font-size:12px; color:#444; margin-top:16px; opacity:0.9; }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# Dynamic background helper (optional)
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
                background: linear-gradient(90deg, rgba(255,140,0,0.18), rgba(255,165,0,0.08)),
                            url("data:image/png;base64,{encoded}");
                background-repeat: no-repeat;
                background-position: right top;
                background-size: cover;
            }}
            """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass

set_dynamic_background(BACKGROUND_PATH)

# -------------------------
# Initialize GROQ client (if available) using secrets
# -------------------------
client = None
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else None
if Groq and GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

# -------------------------
# Brand info
# -------------------------
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "specialties": ["GP", "Dermatologist", "Geriatrician"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/",
        "call_flow": ["Prepare", "Engage", "Create Opportunities", "Influence", "Impact GSO", "Post-call Analysis"],
    },
    # other brands omitted for brevity (keep original structure in your app)
}

# Ensure selected brand exists
brand_keys = list(brand_data.keys())
if st.session_state.selected_brand not in brand_keys:
    st.session_state.selected_brand = brand_keys[0]

# -------------------------
# Helper functions
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
    if client:
        try:
            prompt = f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            # NOTE: Groq SDK usage may differ; this is a best-effort placeholder.
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                                 messages=[{"role": "user", "content": prompt}],
                                                 temperature=0.2)
            # Fallbacks if structure differs
            content = getattr(resp.choices[0].message, "content", None) or getattr(resp.choices[0], "text", "")
            return content
        except Exception:
            return simple_summary(text, bullets)
    else:
        return simple_summary(text, bullets)


def generate_audio(text):
    if not text:
        return ""
    # Try ElevenLabs -> gTTS -> pyttsx3
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
# Sidebar filters
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]
    segment = st.selectbox("Segment", bconf["segments"])
    persona = st.selectbox("HCP Persona", bconf["personas"])
    barrier = st.multiselect("Doctor Barrier", bconf["barriers"])
    specialty = st.selectbox("Specialty", bconf["specialties"])
    objective = st.selectbox("Objective", ["Awareness", "Adoption", "Retention"])
    st.session_state.temperature = st.slider("Temperature", 0.0, 1.0, st.session_state.temperature, 0.05)
    st.session_state.search_mode = st.selectbox("Search mode", ["deep", "shallow"])
    st.session_state.language = st.radio("Language", ["English", "Arabic"])
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
st.markdown(f"""
<div class="title-box">
    <img src="{GSK_LOGO_RAW}" class="left-logo">
    <h2>💡 AI Sales Call Assistant — {bconf['display']}</h2>
    <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# -------------------------
# Load references and sales summaries (if folders exist)
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
# PDF Upload and summarize
# -------------------------
uploaded_file = st.file_uploader("Upload PDF for summary", type=["pdf"])
if uploaded_file is not None and PdfReader:
    try:
        # PyPDF2 PdfReader can accept a file-like object
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
# Build corpus
# -------------------------
corpus_folders = [refs_folder, sales_folder]
chunks, chunk_meta = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# Prompt suggestions
# -------------------------

def make_suggestions(brand_key, persona_val, barriers_list, segment_val, specialty_val, objective_val):
    s = []
    s.append(f"Generate call flow for {persona_val} focused on {objective_val}.")
    if barriers_list:
        s.append(f"Handle objection: {', '.join(barriers_list[:2])} for {persona_val}.")
    else:
        s.append(f"Identify common objections for {persona_val}.")
    s.append(f"Summarize HCP persona insights for {persona_val}.")
    s.append(f"Key talking points for {brand_data[brand_key]['display']} in {segment_val}.")
    s.append(f"Draft a short adoption message for {brand_data[brand_key]['display']} to a {specialty_val}.")
    return s

# -------------------------
# AI Response (APACT + multi-turn feedback)
# -------------------------

def add_ai_response(prompt, follow_up=False, dislike_choice=None):
    snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=5)
    citation = "\n".join([f"{s['meta']['filename']} ({s['score']:.2f})" for s in snippets])
    response_lines = []

    bconf_local = brand_data.get(st.session_state.selected_brand, {})

    if not follow_up:
        # --- APACT ---
        response_lines.append("Acknowledge: Thank you for raising this concern. I understand your perspective.")
        response_lines.append("Probing: Could you clarify if your main concern is about efficacy, safety, or patient eligibility?")
        response_lines.append("Actions: Based on your input, here are recommended steps:")
        for step in bconf_local.get("call_flow", []):
            step_snippets = [s["text"] for s in snippets if step.lower() in s["text"].lower()]
            if step_snippets:
                response_lines.append(f"{step}:")
                for sn in step_snippets:
                    response_lines.append(f"- {sn}")
            else:
                response_lines.append(f"{step}: - Refer to the sales module and uploaded references for guidance.")
        response_lines.append("Confirm: Does this approach address your concern sufficiently?")
        response_lines.append("Transition: If yes, we can move on to the next discussion point or objective.")
        response_lines.append("\nNote: Tailored using sales module and uploaded references.")
        st.session_state.dislike_state = None
    else:
        # Multi-turn dislike feedback
        if st.session_state.dislike_state is None:
            response_lines.append("I noticed you disliked the previous answer. Could you tell me why?")
            st.session_state.dislike_state = "waiting_reason"
        elif st.session_state.dislike_state == "waiting_reason" and dislike_choice:
            if dislike_choice == "Unclear":
                response_lines.append("Thanks! Let's clarify the points. Here is a refined answer focusing on clarity...")
            elif dislike_choice == "Too long":
                response_lines.append("Thanks! I'll shorten the response for easier reading...")
            elif dislike_choice == "Not relevant":
                response_lines.append("Thanks! Let's focus on the points most relevant to your needs...")
            st.session_state.dislike_state = None

    ai_text = "\n".join(response_lines)
    st.session_state.chat_history.append({"role": "assistant", "content": ai_text, "citation": citation})

# -------------------------
# Chat container and input
# -------------------------
chat_container = st.container()

with st.expander("💡 Prompt Suggestions (Click to Expand)", expanded=False):
    suggs = make_suggestions(st.session_state.selected_brand, persona, barrier, segment, specialty, objective)
    sugg_cols = st.columns(3)
    for i, s in enumerate(suggs):
        col = sugg_cols[i % 3]
        if col.button(s, key=f"sugg_{i}"):
            st.session_state.main_input = s

with st.form("main_input_form", clear_on_submit=True):
    user_input = st.text_area("Ask something:", st.session_state.main_input, height=72)
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role": "user", "content": user_input.strip()})
        add_ai_response(user_input.strip())
        st.session_state.main_input = ""

# -------------------------
# Display chat with audio and interactive feedback
# -------------------------
with chat_container:
    for idx, entry in enumerate(st.session_state.chat_history):
        if entry.get("role") == "user":
            st.markdown(f'<div class="chat-bubble-user">{escape(entry.get("content",""))}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-ai">{escape(entry.get("content",""))}</div>', unsafe_allow_html=True)
            if entry.get("citation"):
                st.markdown(f'<div class="citation-box">{escape(entry.get("citation"))}</div>', unsafe_allow_html=True)
            audio_b64 = generate_audio(entry.get("content",""))
            if audio_b64:
                st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")

            # Feedback buttons
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
                    add_ai_response("The user requested more information; expand the previous answer.", follow_up=True)

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
