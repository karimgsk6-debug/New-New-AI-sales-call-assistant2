# app.py - Full merged AI Sales Call Assistant
import streamlit as st
import os
import re
import tempfile
import base64
from datetime import datetime
from html import escape

# -------------------------
# Optional libs (best-effort)
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
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

# TF-IDF optional
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

# ElevenLabs optional
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except Exception:
    ELEVENLABS_AVAILABLE = False

# pyttsx3 optional for local TTS fallback
try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except Exception:
    PYTTSX3_AVAILABLE = False

# -------------------------
# Page config & repo info
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_BLOB_BASE = f"https://github.com/{REPO_USER}/{REPO_NAME}/blob/{COMMIT}/.devcontainer"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"

BACKGROUND_URL = REPO_RAW_BASE + "/.devcontainer/background1.png"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# -------------------------
# Session defaults (safe)
# -------------------------
defaults = {
    "chat_history": [],                # list of messages: dict {role:user|assistant, content, citations?, audio?}
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.62,
    "search_mode": "deep",
    "medical_summary": "",
    "sales_summary": "",
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "followup_state": None,            # {"msg_idx": int, "type": str, "questions":[..], "answers":[..]}
    "language": "English",
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# -------------------------
# CSS & background
# -------------------------
CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}}
.title-box {{
  background: rgba(255,255,255,0.95);
  padding: 12px;
  border-radius: 10px;
  margin-bottom: 12px;
  position: relative;
  display:flex;
  align-items:center;
  justify-content:center;
}}
.title-box img.left-logo {{ position:absolute; left:12px; height:64px; }}
.title-box img.right-logo {{ position:absolute; right:12px; height:64px; }}
.chat-container {{ max-height: 62vh; overflow-y:auto; padding:12px; background: rgba(255,255,255,0.95); border-radius:8px; margin-bottom:140px; }}
.chat-bubble-user {{ background:#0078D7; color:white; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto; }}
.chat-bubble-ai {{ background:#eef9ff; color:#000; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }}
.suggestion-pill {{ background:#fff; border:1px solid #ddd; padding:8px 12px; border-radius:20px; margin:6px; cursor:pointer; display:inline-block; }}
.suggestion-pill:hover {{ background:#f0f8ff; }}
.citation-box {{ background:#fbfbff; border-left:4px solid #0078D7; padding:8px; margin-top:8px; border-radius:6px; font-size:13px; white-space:pre-wrap; }}
.input-area {{ position: fixed; left:20px; right:20px; bottom:18px; z-index:9999; display:flex; gap:8px; align-items:flex-end; }}
.input-area textarea {{ width:100%; min-height:72px; max-height:250px; padding:10px; border-radius:8px; border:1px solid #ccc; resize:vertical; }}
.send-button {{ height:44px; padding:0 14px; border-radius:8px; border:none; background:#FF6F00; color:white; cursor:pointer; font-weight:600; }}
.fixed-disclaimer {{ position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# -------------------------
# Initialize GROQ client safely if available
# -------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = None
if Groq and GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

# -------------------------
# Brand data
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
        "call_flow": ["Pre-call planning", "Prepare", "Engage", "Create Opportunities", "Influence", "Impact GSO", "Post-call analysis"]
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited eligibility", "Access/reimbursement issues"],
        "specialties": ["Oncologist", "Medical Oncologist"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli/",
        "call_flow": ["COCO", "Anchor", "Engage", "Close"]
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Side effect concerns", "Cost/coverage"],
        "specialties": ["GP", "Pulmonologist", "Respiratory Specialist"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy/",
        "call_flow": ["Prepare", "Engage", "Demonstrate", "Address Access", "Close"]
    }
}

# -------------------------
# Helpers: read files, build corpus, TF-IDF snippet search
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
    except Exception as e:
        return f"[Error reading {os.path.basename(path)}: {e}]"

def build_corpus_for_folders(folder_paths, chunk_size_sentences=3):
    chunks = []
    metas = []
    for folder in folder_paths:
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
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
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
    # fallback substring match
    out = []
    q = query.lower()
    for i, c in enumerate(chunks):
        if q in c.lower():
            out.append({"score": 1.0, "text": c, "meta": metas[i]})
            if len(out) >= top_n:
                break
    return out

# -------------------------
# Summarization helpers
# -------------------------
def simple_summary(text, bullets=6):
    if not text:
        return ""
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- " + s for s in selected])

def model_summarize(text, bullets=6):
    if not text:
        return ""
    if client:  # GROQ model summarize
        try:
            prompt = f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                                 messages=[{"role":"user","content":prompt}],
                                                 temperature=0.2)
            return resp.choices[0].message.content
        except Exception:
            return simple_summary(text, bullets)
    else:
        return simple_summary(text, bullets)

# -------------------------
# TTS helpers (humanized)
# -------------------------
def tts_preprocess(text):
    if not text:
        return ""
    sents = re.split(r'(?<=[\.\?\!])\s+', text.strip())
    clean = []
    for s in sents:
        s2 = re.sub(r'[\[\]\(\)\{\}<>\"*_:;=\\/]', '', s)
        s2 = re.sub(r'[,*]', '', s2)
        if not re.search(r'[\.!?]$', s2):
            s2 = s2 + '.'
        clean.append(s2.strip())
    return " ... ".join(clean)

def generate_audio(text):
    if not text:
        return ""
    t = tts_preprocess(text)
    # try ElevenLabs first
    if ELEVENLABS_AVAILABLE and st.secrets.get("ELEVENLABS_API_KEY") and st.secrets.get("ELEVENLABS_VOICE_ID"):
        try:
            elevenlabs.api_key = st.secrets.get("ELEVENLABS_API_KEY")
            audio_stream = elevenlabs.generate(text=t, voice=st.secrets.get("ELEVENLABS_VOICE_ID"), stream=True)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            with open(tmp.name, "wb") as f:
                for chunk in audio_stream:
                    f.write(chunk)
            with open(tmp.name, "rb") as fh:
                return base64.b64encode(fh.read()).decode()
        except Exception:
            pass
    # fallback to gTTS
    if gTTS:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            gTTS(text=t, lang="en", slow=False).save(tmp.name)
            with open(tmp.name, "rb") as fh:
                return base64.b64encode(fh.read()).decode()
        except Exception:
            pass
    # fallback to pyttsx3 (local)
    if PYTTSX3_AVAILABLE:
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 160)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            # pyttsx3 can write to speakers only in many envs; skip saving if not possible
            return ""
        except Exception:
            return ""
    return ""

# -------------------------
# Sidebar: filters & options
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = ["shingrix", "jemperli", "trelegy"]
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.get("selected_brand","shingrix")))
    st.session_state.selected_brand = sel_brand

    bconf = brand_data[st.session_state.selected_brand]
    segment = st.selectbox("Segment", bconf["segments"], key="sidebar_segment")
    persona = st.selectbox("HCP Persona", bconf["personas"], key="sidebar_persona")
    barrier = st.multiselect("Doctor Barrier", bconf["barriers"], key="sidebar_barrier")
    specialty = st.selectbox("Specialty", bconf["specialties"], key="sidebar_specialty")
    objective = st.selectbox("Objective", ["Awareness", "Adoption", "Retention"], key="sidebar_objective")

    st.write("---")
    st.session_state.temperature = st.slider("Temperature", min_value=0.0, max_value=1.0, value=st.session_state.temperature, step=0.05)
    st.session_state.search_mode = st.selectbox("Search mode", ["deep","shallow"], index=0 if st.session_state.search_mode=="deep" else 1)
    st.session_state.language = st.radio("Language", ["English","Arabic"], index=0 if st.session_state.language=="English" else 1)
    st.write("---")
    st.caption("Summaries below are auto-generated from .devcontainer files per selected brand.")
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []

with st.sidebar.expander("🌐 Add External Reference URLs (one per line)", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT", "DOCX"], horizontal=True)

# -------------------------
# Title box (header)
# -------------------------
st.markdown(f"""
<div class="title-box">
  <img src="{GSK_LOGO_RAW}" class="left-logo">
  <h2>💡 AI Sales Call Assistant — {brand_data[st.session_state.selected_brand]['display']}</h2>
  <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# -------------------------
# Load local files and auto-summarize (brand-specific)
# -------------------------
refs_folder = brand_data[st.session_state.selected_brand]["references_path"]
sales_folder = brand_data[st.session_state.selected_brand]["sales_path"]

combined_refs = ""
local_ref_files = []
if os.path.exists(refs_folder):
    for f in sorted(os.listdir(refs_folder)):
        if f.lower().endswith((".pdf", ".txt")):
            local_ref_files.append(f)
            combined_refs += read_file_text(os.path.join(refs_folder, f)) + "\n"

combined_sales = ""
sales_files = []
if os.path.exists(sales_folder):
    for f in sorted(os.listdir(sales_folder)):
        if f.lower().endswith((".pdf", ".txt")):
            sales_files.append(f)
            combined_sales += read_file_text(os.path.join(sales_folder, f)) + "\n"

# auto-fill summaries if empty
if not st.session_state.medical_summary and combined_refs.strip():
    st.session_state.medical_summary = model_summarize(combined_refs, bullets=6)
if not st.session_state.sales_summary and combined_sales.strip():
    st.session_state.sales_summary = model_summarize(combined_sales, bullets=6)

# -------------------------
# Show summaries in collapsed expanders (collapsed by default)
# -------------------------
with st.expander("📚 Medical References Summary", expanded=False):
    st.markdown(st.session_state.medical_summary or "No medical summary available for this brand.")

with st.expander("💼 Sales Module Summary", expanded=False):
    st.markdown(st.session_state.sales_summary or "No sales summary available for this brand.")

# -------------------------
# Build local corpus (chunks) once per run for TF-IDF
# -------------------------
corpus_folders = []
if refs_folder: corpus_folders.append(refs_folder)
if sales_folder: corpus_folders.append(sales_folder)
chunks, chunk_meta = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# Helper: create suggestions for brand/persona
# -------------------------
def make_suggestions(brand_key, persona_val, barriers_list, segment_val, specialty_val, objective_val):
    s=[]
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
# Chat container display
# -------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for idx, msg in enumerate(st.session_state.chat_history):
    role = msg.get("role","assistant" if msg.get("content") else "user")
    if role == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)
        # show citations if present
        if msg.get("citations"):
            for c in msg["citations"]:
                fname = c["meta"]["filename"]
                # link to blob path (try references first)
                if fname in local_ref_files:
                    blob = f"{REPO_BLOB_BASE}/references/{st.session_state.selected_brand}/{fname}"
                elif fname in sales_files:
                    blob = f"{REPO_BLOB_BASE}/SalesModule/{st.session_state.selected_brand}/{fname}"
                else:
                    blob = f"{REPO_BLOB_BASE}/{fname}"
                st.markdown(f'<div class="citation-box"><b>Excerpt from {escape(fname)}:</b><br>{escape(c["text"][:800])}...<br><a href="{blob}" target="_blank">View full file</a></div>', unsafe_allow_html=True)
        # audio
        if msg.get("audio"):
            try:
                st.audio(base64.b64decode(msg["audio"]), format="audio/mp3")
            except Exception:
                pass
        # feedback row
        c1, c2, c3, c4 = st.columns([1,1,1,1])
        if c1.button("👍 Like", key=f"like_{idx}"):
            st.success("Thanks — feedback recorded 👍")
        if c2.button("👎 Dislike", key=f"dislike_{idx}"):
            questions = ["Was the response lacking specific clinical data? (Yes/No)", "Was the tone or length not appropriate? (Yes/No)"]
            st.session_state.followup_state = {"msg_idx": idx, "type": "dislike", "questions": questions, "answers": []}
        if c3.button("😐 Neutral", key=f"neutral_{idx}"):
            questions = ["Was the response too generic? (Yes/No)", "Do you want more examples? (Yes/No)"]
            st.session_state.followup_state = {"msg_idx": idx, "type": "neutral", "questions": questions, "answers": []}
        if c4.button("🔄 Need more", key=f"needmore_{idx}"):
            questions = ["Do you want more detail? (Yes/No)", "Should I focus on practical steps? (Yes/No)"]
            st.session_state.followup_state = {"msg_idx": idx, "type": "needmore", "questions": questions, "answers": []}

    # followup flow if active for this msg
    fs = st.session_state.get("followup_state")
    if fs and fs.get("msg_idx") == idx:
        st.info(f"Feedback type: {fs['type']}. Please answer the following (Yes/No) to help improve the response.")
        answers = fs.get("answers", [])
        qcount = len(fs["questions"])
        for qi, qtext in enumerate(fs["questions"]):
            if qi < len(answers):
                st.markdown(f"**Q{qi+1}:** {qtext} — **Answer:** {answers[qi]}")
            else:
                coly, coln = st.columns([1,1])
                if coly.button("Yes", key=f"follow_yes_{idx}_{qi}"):
                    answers.append("Yes"); st.session_state.followup_state["answers"] = answers; st.experimental_rerun()
                if coln.button("No", key=f"follow_no_{idx}_{qi}"):
                    answers.append("No"); st.session_state.followup_state["answers"] = answers; st.experimental_rerun()
        # when all answered, enable regeneration
        if len(answers) == qcount and st.button("Submit feedback & regenerate", key=f"submit_feedback_{idx}"):
            # find original user message prior to this assistant msg
            orig_user = ""
            for j in range(idx-1, -1, -1):
                if st.session_state.chat_history[j].get("role") == "user":
                    orig_user = st.session_state.chat_history[j].get("content",""); break
            combined_ctx = "\n\n".join([
                "Medical summary:\n" + (st.session_state.medical_summary or ""),
                "Sales summary:\n" + (st.session_state.sales_summary or ""),
                "Uploaded PDF (truncated):\n" + (st.session_state.uploaded_pdf_text[:4000] if st.session_state.uploaded_pdf_text else "")
            ])
            feedback_note = "Feedback answers: " + "; ".join([f"{q} => {a}" for q,a in zip(fs["questions"], fs["answers"])])
            regen_prompt = f"{orig_user}\n\nUser feedback: {feedback_note}\n\nContext:\n{combined_ctx[:8000]}"
            new_resp = "(AI unavailable)"
            if client:
                try:
                    resp = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role":"system","content":"You are a helpful pharmaceutical sales assistant. Use the context and user feedback to produce an improved response."},
                                  {"role":"user","content":regen_prompt}],
                        temperature=st.session_state.temperature
                    )
                    new_resp = resp.choices[0].message.content
                except Exception as e:
                    new_resp = f"(AI error regenerating: {e})"
            else:
                new_resp = "(Fallback) Improved answer based on feedback: " + "; ".join(fs["answers"])
            # update assistant message + citations + audio
            new_cits = local_search_snippets(orig_user + " " + feedback_note, chunks, chunk_meta, top_n=3 if st.session_state.search_mode=="deep" else 1)
            st.session_state.chat_history[idx]["content"] = new_resp
            st.session_state.chat_history[idx]["citations"] = new_cits
            st.session_state.chat_history[idx]["audio"] = generate_audio(new_resp)
            st.session_state.followup_state = None
            st.experimental_rerun()

st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Prompt suggestions expander (click autofill)
# -------------------------
with st.expander("Prompt Suggestions (click to autofill)", expanded=False):
    suggs = make_suggestions(st.session_state.selected_brand, persona, barrier, segment, specialty, objective)
    cols = st.columns([1,1,1])
    for i, s in enumerate(suggs):
        col = cols[i%3]
        if col.button(s, key=f"sugg_fill_{i}"):
            st.session_state.main_input = s

# -------------------------
# Chat input area (merged + send button fixed bottom)
# -------------------------
st.markdown("""
<div class="input-area">
</div>
""", unsafe_allow_html=True)

# Render the input controls (not inside a form to avoid st.button-in-form conflicts)
user_text = st.text_area("", value=st.session_state.get("main_input",""), key="main_input_area", placeholder="Type your message here... (click a suggestion to autofill, then edit if needed)")

# Send button (next to textarea visually -- because streamlit layout ordering is linear, we place it after)
send_clicked = st.button("Send", key="send_main", help="Send message to AI")

if send_clicked and user_text and user_text.strip():
    # append user message
    st.session_state.chat_history.append({"role":"user","content": user_text.strip()})
    # prepare model prompt/context
    ask_for_callflow = bool(re.search(r'\b(call flow|sales call|call plan|pre-call|call)\b', user_text, re.IGNORECASE))
    call_flow_prompt = ""
    if ask_for_callflow:
        steps = brand_data[st.session_state.selected_brand].get("call_flow", [])
        if steps:
            call_flow_prompt = "\n\n--- Sales Call Flow ---\n" + "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
    combined_ctx = "\n\n".join([
        "Medical summary:\n" + (st.session_state.medical_summary or ""),
        "Sales summary:\n" + (st.session_state.sales_summary or ""),
        "Uploaded PDF (truncated):\n" + (st.session_state.uploaded_pdf_text[:4000] if st.session_state.uploaded_pdf_text else "")
    ])
    system_prompt = "You are a pharmaceutical AI assistant. Tailor responses using references, sales modules, uploaded PDFs, and follow the brand-specific call flow when asked."
    final_prompt = f"{user_text}\n\nBrand: {brand_data[st.session_state.selected_brand]['display']}\nPersona: {persona}\nSegment: {segment}\nSpecialty: {specialty}\nObjective: {objective}\nBarriers: {', '.join(barrier) if barrier else 'None'}\n\n{call_flow_prompt}\n\nContext:\n{combined_ctx[:8000]}"
    ai_resp = "(AI unavailable)"
    if client:
        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":system_prompt},{"role":"user","content":final_prompt}],
                temperature=st.session_state.temperature
            )
            ai_resp = resp.choices[0].message.content
        except Exception as e:
            ai_resp = f"(AI Error: {e})"
    else:
        # Fallback: produce a structured reply incorporating summaries and call flow
        fallback_parts = [f"(Fallback) Response for {st.session_state.selected_brand.upper()}:"]
        if call_flow_prompt:
            fallback_parts.append(call_flow_prompt)
        fallback_parts.append("\nSummary (medical):\n" + (st.session_state.medical_summary or "N/A")[:800])
        fallback_parts.append("\nSummary (sales):\n" + (st.session_state.sales_summary or "N/A")[:800])
        fallback_parts.append("\nSuggested reply:\n" + user_text)
        ai_resp = "\n\n".join(fallback_parts)

    # attach local citations
    snips = local_search_snippets(user_text, chunks, chunk_meta, top_n=3 if st.session_state.search_mode=="deep" else 1)
    audio_b64 = generate_audio(ai_resp)
    st.session_state.chat_history.append({"role":"assistant","content": ai_resp, "citations": snips, "audio": audio_b64})
    # clear main input safely
    st.session_state.main_input = ""
    # clear text area (update widget value)
    st.experimental_set_query_params()  # no-op trick to cause UI update
    # note: we don't call st.experimental_rerun() here to avoid mid-render exceptions

# -------------------------
# PDF upload expander (in main area)
# -------------------------
with st.expander("📄 Upload Custom PDF for AI Context (optional)", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
    pdf_size = st.selectbox("PDF Summary Size", ["Consisted","Normal","Detailed"], index=1)
    if uploaded_pdf:
        try:
            if PdfReader:
                reader = PdfReader(uploaded_pdf)
                txt = "".join([p.extract_text() or "" for p in reader.pages])
            else:
                txt = ""
            st.session_state.uploaded_pdf_text = txt
            st.success(f"Loaded {len(txt)} characters from uploaded PDF.")
            bullets = {"Consisted":5,"Normal":10,"Detailed":20}.get(pdf_size,10)
            if client and txt.strip():
                try:
                    summ_prompt = f"Summarize into {bullets} bullet points:\n\n{txt[:12000]}"
                    summ = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content":summ_prompt}], temperature=0.2)
                    st.session_state.pdf_summary = summ.choices[0].message.content
                except Exception:
                    st.session_state.pdf_summary = simple_summary(txt, bullets)
            else:
                st.session_state.pdf_summary = simple_summary(txt, bullets)
        except Exception as e:
            st.error(f"Could not read uploaded PDF: {e}")
    if st.session_state.get("pdf_summary"):
        st.markdown(f"<div style='background:#E8F4FF;padding:10px;border-radius:8px;white-space:pre-line'>{escape(st.session_state.pdf_summary)}</div>", unsafe_allow_html=True)

# -------------------------
# Export / Download Chat (main area)
# -------------------------
if st.session_state.chat_history:
    with st.expander("💾 Export / Download Chat", expanded=False):
        text_export = "\n\n".join([f"{('You' if m['role']=='user' else 'AI')}: {m['content']}" for m in st.session_state.chat_history])
        st.download_button("⬇️ Download TXT", text_export.encode("utf-8"), file_name=f"{st.session_state.selected_brand}_chat_{datetime.now().strftime('%Y%m%d')}.txt")
        if DOCX_AVAILABLE:
            if st.button("Export as DOCX"):
                try:
                    doc = Document()
                    doc.add_heading(f"AI Sales Call Assistant - {st.session_state.selected_brand}", 0)
                    for m in st.session_state.chat_history:
                        role = "You" if m["role"] == "user" else "AI"
                        doc.add_paragraph(f"{role}: {m['content']}")
                        if m.get("citations"):
                            for c in m["citations"]:
                                doc.add_paragraph(f"    - Snippet ({c['meta']['filename']}): {c['text'][:200]}...", style="IntenseQuote")
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
                    doc.save(tmp.name)
                    with open(tmp.name, "rb") as fh:
                        st.download_button("⬇️ Download DOCX", fh.read(), file_name=f"{st.session_state.selected_brand}_chat.docx")
                except Exception as e:
                    st.error(f"DOCX export failed: {e}")

# -------------------------
# Disclaimer footer
# -------------------------
st.markdown('<div class="fixed-disclaimer">⚠️ This AI Sales Call Assistant is for informational and educational purposes only. Verify all medical content with approved references and local compliance guidance.</div>', unsafe_allow_html=True)
