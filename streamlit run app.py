# app.py - AI Sales Call Assistant (RAG Hybrid - Option C)
import os, re, io, base64, tempfile
from datetime import datetime
from html import escape
import streamlit as st

# Optional imports - gracefully degraded
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

# -------------------------
# Page config & assets
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant (RAG Hybrid)", layout="wide")
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# -------------------------
# Styling: white assistant bubbles + user bubbles + layout
# -------------------------
def inject_styles():
    st.markdown(
        f"""
        <style>
        /* background */
        [data-testid="stAppViewContainer"] {{
            background: linear-gradient(90deg, rgba(255,140,0,0.06), rgba(255,165,0,0.02));
            background-repeat: no-repeat;
            background-position: right top;
            background-size: cover;
        }}

        .title-box {{
            background: rgba(255,255,255,0.85);
            padding: 10px 16px;
            border-radius: 10px;
            display:flex;
            align-items:center;
            justify-content:center;
            gap:12px;
        }}
        .title-box img.left-logo {{ height:40px; }}
        .title-box img.right-logo {{ height:40px; }}

        /* Chat containers */
        .chat-wrap {{ max-width:900px; margin:12px auto; padding:6px; }}
        .chat-bubble-user {{
            background: transparent;
            color: #111;
            border: 1px solid rgba(0,0,0,0.06);
            padding:10px 12px;
            margin:8px 0;
            border-radius:12px;
            max-width:70%;
            margin-left:auto;
            font-size:14px;
            white-space:pre-wrap;
        }}
        .chat-bubble-ai {{
            background: #ffffff;
            color: #111;
            padding:14px 16px;
            margin:8px 0;
            border-radius:14px;
            box-shadow: 0 6px 18px rgba(20,20,40,0.06);
            max-width:80%;
            font-size:14px;
            white-space:pre-wrap;
        }}
        .chat-meta {{
            font-size:12px;
            color:#666;
            margin-top:6px;
        }}
        .citation-box {{
            font-size:12px;
            color:#333;
            background: #f7f7f7;
            padding:8px;
            border-radius:8px;
            margin-top:6px;
        }}
        .fixed-disclaimer {{
            font-size:12px;
            color:#444;
            padding:8px;
            margin-top:18px;
            background: rgba(255,255,255,0.6);
            border-radius:8px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )

inject_styles()

# -------------------------
# Session defaults
# -------------------------
if "chat_history" not in st.session_state: st.session_state.chat_history = []
for key, val in {
    "selected_brand": "shingrix",
    "temperature": 0.2,
    "search_mode": "deep",
    "medical_summary": "",
    "sales_summary": "",
    "feedback": {},
    "dislike_state": None,
    "main_input": "",
    "pdf_summary": "",
}.items():
    st.session_state.setdefault(key, val)

# -------------------------
# Brand definitions (paths)
# -------------------------
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "references_path": ".devcontainer/references/shingrix",
        "sales_path": ".devcontainer/SalesModule/shingrix",
    },
    "jemperli": {
        "display": "Jemperli",
        "references_path": ".devcontainer/references/jemperli",
        "sales_path": ".devcontainer/SalesModule/jemperli",
    },
    "trelegy": {
        "display": "Trelegy",
        "references_path": ".devcontainer/references/trelegy",
        "sales_path": ".devcontainer/SalesModule/trelegy",
    },
}

# -------------------------
# Initialize GROQ client
# -------------------------
GROQ_API_KEY = "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"  # <--- safe placeholder
client = None
if Groq and GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except:
        client = None
# -------------------------
# File read helpers
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

def build_corpus_for_brand(brand_key, chunk_size_sentences=3):
    """Return chunks and metadata for references + sales folders for the selected brand."""
    bd = brand_data[brand_key]
    folders = [bd["references_path"], bd["sales_path"]]
    chunks, metas = [], []
    for folder in folders:
        if not os.path.exists(folder):
            continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf", ".txt"))]
        for fname in files:
            full = os.path.join(folder, fname)
            text = read_file_text(full)
            if not text:
                continue
            sents = re.split(r'(?<=[\.\?\!])\s+', text)
            # chunk by sentences
            for i in range(0, max(1, len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename": fname, "folder": folder, "start_sent": i})
    return chunks, metas

# -------------------------
# Local retrieval (TF-IDF or substring fallback)
# -------------------------
def local_search_snippets(query, chunks, metas, top_n=4):
    if not chunks:
        return []
    # prefer sklearn if available
    if SKLEARN_AVAILABLE and len(chunks) > 0:
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
    # fallback simple substring matching
    q = query.lower()
    out = []
    for i, c in enumerate(chunks):
        if q in c.lower():
            out.append({"score": 1.0, "text": c, "meta": metas[i]})
            if len(out) >= top_n:
                break
    # if nothing matched, return the top N chunks as default context (weak)
    if not out:
        for i in range(min(top_n, len(chunks))):
            out.append({"score": 0.01, "text": chunks[i], "meta": metas[i]})
    return out

# -------------------------
# Summarization helpers
# -------------------------
def simple_summary(text, bullets=6):
    if not text: return ""
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- " + s for s in selected])

def model_summarize(text, bullets=6):
    # Summarize locally unless groq is available
    if not text: return ""
    prompt = f"Summarize the following into {bullets} concise bullet points:\n\n{text[:12000]}"
    if groq_client:
        try:
            resp = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt}],
                temperature=0.1
            )
            return resp.choices[0].message.content
        except Exception:
            return simple_summary(text, bullets)
    else:
        return simple_summary(text, bullets)

# -------------------------
# Audio generation (optional)
# -------------------------
def generate_audio_base64(text):
    if not text:
        return ""
    # prefer elevenlabs if available via st.secrets (not implemented here)
    # fallback to gTTS
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
# Sidebar: brand & options
# -------------------------
with st.sidebar.expander("Settings", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    st.session_state.temperature = st.slider("Temperature (creativity)", 0.0, 1.0, st.session_state.temperature, 0.05)
    st.session_state.search_mode = st.selectbox("Search mode", ["deep", "shallow"])
    if st.button("Clear Chat"):
        st.session_state.chat_history = []
        st.session_state.feedback = {}
        st.session_state.pdf_summary = ""
        st.session_state.dislike_state = None

with st.sidebar.expander("Export / Upload", expanded=False):
    export_format = st.radio("Export format", ["TXT", "DOCX"], horizontal=True)
    uploaded_file = st.file_uploader("Upload PDF (optional)", type=["pdf"])
    if uploaded_file and PdfReader:
        try:
            reader = PdfReader(uploaded_file)
            pdf_text = "".join([p.extract_text() or "" for p in reader.pages])
            st.session_state.pdf_summary = model_summarize(pdf_text, bullets=6)
            st.success("PDF summarized.")
        except Exception:
            st.error("Failed to parse PDF.")

# -------------------------
# Title box
# -------------------------
st.markdown(
    f"""
    <div class="title-box">
      <img src="{GSK_LOGO_RAW}" class="left-logo" />
      <h3>💡 AI Sales Call Assistant — {brand_data[st.session_state.selected_brand]['display']}</h3>
      <img src="{AI_LOGO_RAW}" class="right-logo" />
    </div>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# Build brand corpus and precompute summaries
# -------------------------
chunks, metas = build_corpus_for_brand(st.session_state.selected_brand, chunk_size_sentences=3)
# Combine reference texts for quick summaries
combined_refs = []
for i, m in enumerate(metas):
    # prefer to attach only references folder content to medical summary
    if "references" in (m.get("folder","")):
        combined_refs.append(chunks[i])
combined_refs_text = "\n".join(combined_refs)

if not st.session_state.medical_summary and combined_refs_text.strip():
    st.session_state.medical_summary = model_summarize(combined_refs_text, bullets=6)

combined_sales = []
for i, m in enumerate(metas):
    if "SalesModule" in (m.get("folder","")):
        combined_sales.append(chunks[i])
combined_sales_text = "\n".join(combined_sales)
if not st.session_state.sales_summary and combined_sales_text.strip():
    st.session_state.sales_summary = model_summarize(combined_sales_text, bullets=6)

# Show quick summaries
with st.expander("📚 Medical References Summary (Grounded)", expanded=False):
    st.markdown(st.session_state.medical_summary or "No medical references found or summary empty.")
with st.expander("💼 Sales Module Summary (Guidance)", expanded=False):
    st.markdown(st.session_state.sales_summary or "No sales module content found.")

# -------------------------
# Prompt suggestions (quick)
# -------------------------
def make_suggestions(brand_key):
    b = brand_data[brand_key]["display"]
    return [
        f"Create a short call script for a GP to encourage adoption of {b}.",
        f"Address the top 2 medical objections for {b}.",
        f"Summarize eligibility criteria for {b} (use references only).",
        f"Suggest 3 talking points for a skeptical specialist about {b}.",
    ]

with st.expander("💡 Prompt Suggestions"):
    cols = st.columns(3)
    for i, s in enumerate(make_suggestions(st.session_state.selected_brand)):
        if cols[i % 3].button(s, key=f"sugg_{i}"):
            st.session_state.main_input = s

# -------------------------
# Core RAG prompt builder (Hybrid policy C)
# -------------------------
def build_rag_prompt(user_question, retrieved_snippets):
    """
    Hybrid RAG instruction:
     - Medical facts must be supported by the retrieved snippets (quote & cite).
     - Sales advice and conversational reasoning may use model reasoning, but if a medical claim is made, include the snippet reference.
    """
    instruction = (
        "You are an AI Sales Call Assistant. Follow these rules strictly:\n\n"
        "1) ANY direct medical factual claims (efficacy, dosing, safety, eligibility) MUST be grounded in the provided 'MEDICAL_SNIPPETS'. "
        "When you use a medical snippet, clearly quote a short excerpt (<= 40 words) and add the filename in parentheses.\n\n"
        "2) Sales guidance, call flow, objection handling, and conversational phrasing may use the model's reasoning, but label it as 'Sales Guidance'.\n\n"
        "3) If a medical question is asked and no supporting medical snippet is available, explicitly say: "
        "\"I could not find a supporting medical reference in the brand files — please verify with official sources.\" Do not hallucinate.\n\n"
        "4) Be concise, use bullets for steps, and use plain language suitable for an HCP sales call. Provide a short suggested verbatim script at the end.\n\n"
    )
    # Separate retrieved snippets into medical vs sales by folder name heuristics
    medical_snips = []
    sales_snips = []
    for s in retrieved_snippets:
        folder = s.get("meta", {}).get("folder", "")
        entry = {"text": s["text"], "filename": s["meta"].get("filename", "unknown")}
        if "references" in folder.lower():
            medical_snips.append(entry)
        else:
            sales_snips.append(entry)
    # Build snippet blocks
    med_block = ""
    for i, m in enumerate(medical_snips):
        med_block += f"---\n[{i+1}] ({m['filename']})\n{m['text']}\n"
    sales_block = ""
    for i, m in enumerate(sales_snips):
        sales_block += f"---\n[{i+1}] ({m['filename']})\n{m['text']}\n"
    # Compose final prompt for the model
    full_prompt = (
        instruction
        + "\nUSER QUESTION:\n" + user_question + "\n\n"
        + "MEDICAL_SNIPPETS (use these to ground medical claims):\n" + (med_block or "(no medical snippets found)") + "\n\n"
        + "SALES_SNIPPETS (use for sales context):\n" + (sales_block or "(no sales snippets found)") + "\n\n"
        + "Now produce a response that: (a) answers medically only with grounding from MEDICAL_SNIPPETS, quoting short excerpt and filename, "
        "and (b) provides Sales Guidance as a separate section. End with a 1-2 sentence suggested verbatim script.\n\n"
        "Start your answer with a one-line summary.\n"
    )
    return full_prompt

# -------------------------
# Model call function
# -------------------------
def call_model_with_rag(prompt, temperature=0.2):
    # Try GROQ if available
    if groq_client:
        try:
            resp = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=1000,
            )
            return resp.choices[0].message.content
        except Exception:
            # fallthrough to local fallback
            pass
    # Fallback: Short local echo / lightweight heuristic response (non-GROQ)
    # We do not hallucinate medical facts here — explain limitation and include snippets included in prompt.
    short = "⚠️ (No external LLM available) I cannot generate a fully synthesized answer because an LLM is not configured.\n\n"
    # Extract the MEDICAL_SNIPPETS portion to show as grounding
    med_match = re.search(r"MEDICAL_SNIPPETS.*?SALES_SNIPPETS", prompt, flags=re.S)
    med_block = med_match.group(0) if med_match else ""
    return short + "Provided medical snippets (use these for verification):\n\n" + med_block[:4000]

# -------------------------
# Generate AI response (adds to chat_history)
# -------------------------
def add_ai_response(user_question):
    # Step 1: retrieve relevant snippets from corpus
    retrieved = local_search_snippets(user_question, chunks, metas, top_n=5)
    # Step 2: build RAG prompt with hybrid policy
    rag_prompt = build_rag_prompt(user_question, retrieved)
    # Step 3: call model
    ai_answer = call_model_with_rag(rag_prompt, temperature=st.session_state.temperature)
    # Build citation summary (filenames)
    citation = ", ".join(sorted({s["meta"].get("filename","") for s in retrieved if s.get("meta")}))
    # Append to history with structured fields
    st.session_state.chat_history.append({
        "role": "assistant",
        "content": ai_answer,
        "raw_prompt": rag_prompt,
        "citation": citation,
        "retrieved": retrieved,
        "time": datetime.utcnow().isoformat()
    })

# -------------------------
# Interaction form
# -------------------------
with st.form("main_input_form", clear_on_submit=True):
    user_input = st.text_area("Ask something (answers will be grounded to brand files):", st.session_state.main_input, height=100)
    submit = st.form_submit_button("Send")
    if submit and user_input.strip():
        st.session_state.chat_history.append({"role": "user", "content": user_input.strip(), "time": datetime.utcnow().isoformat()})
        add_ai_response(user_input.strip())
        st.session_state.main_input = ""

# -------------------------
# Display chat area
# -------------------------
chat_holder = st.container()
with chat_holder:
    st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
    for idx, entry in enumerate(st.session_state.chat_history):
        if entry["role"] == "user":
            st.markdown(f'<div class="chat-bubble-user">{escape(entry["content"])}</div>', unsafe_allow_html=True)
        else:
            # assistant bubble
            content = entry.get("content", "")
            st.markdown(f'<div class="chat-bubble-ai">{escape(content)}</div>', unsafe_allow_html=True)
            # citations box (filenames of retrieved)
            if entry.get("citation"):
                st.markdown(f'<div class="citation-box">Sources used: {escape(entry["citation"])}</div>', unsafe_allow_html=True)
            # small meta
            st.markdown(f'<div class="chat-meta">Generated: {entry.get("time","-")}</div>', unsafe_allow_html=True)
            # audio (optional)
            audio_b64 = generate_audio_base64(content)
            if audio_b64:
                st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")
            # feedback UI
            fb_cols = st.columns([1,1,1])
            col_like, col_dislike, col_more = fb_cols
            key_like = f"like_{idx}"
            key_dislike = f"dislike_{idx}"
            key_more = f"more_{idx}"
            if st.session_state.feedback.get(content) is None:
                if col_like.button("👍 Like", key=key_like):
                    st.session_state.feedback[content] = "like"
                if col_dislike.button("👎 Dislike", key=key_dislike):
                    st.session_state.feedback[content] = "dislike"
                    # follow-up choices
                    reasons = ["Unclear", "Too long", "Not relevant"]
                    cols = st.columns(len(reasons))
                    for j, r in enumerate(reasons):
                        if cols[j].button(r, key=f"dislike_choice_{idx}_{j}"):
                            # simple refinement - re-run but ask for refinement
                            followup_q = f"Refine previous answer focusing on: {r}. Original question: {st.session_state.chat_history[idx-1]['content'] if idx>0 else 'N/A'}"
                            st.session_state.chat_history.append({"role": "user", "content": followup_q, "time": datetime.utcnow().isoformat()})
                            add_ai_response(followup_q)
                if col_more.button("ℹ️ Need More", key=key_more):
                    st.session_state.feedback[content] = "need_more"
                    followup_q = f"Please expand the previous answer with more details. Original: {entry.get('content','')[:300]}"
                    st.session_state.chat_history.append({"role": "user", "content": followup_q, "time": datetime.utcnow().isoformat()})
                    add_ai_response(followup_q)
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown("""
<div class="fixed-disclaimer">
💡 This tool is for internal sales support only. Medical facts should be verified from official sources. The assistant follows a hybrid RAG policy: medical claims are grounded to files in the brand folders.
</div>
""", unsafe_allow_html=True)
