# app.py - Final merged AI Sales Call Assistant
# Features:
# - Brand-specific HCP fields
# - Collapsible prompt suggestions (click to autofill)
# - Medical & SalesModule summaries (auto or manual)
# - Summaries automatically injected into AI prompts
# - TF-IDF inline citation snippets
# - Dislike -> clarifying Q -> regenerate
# - Improved (heuristic) TTS preprocessing for more humanized audio
# - Export TXT/DOCX
# - Uses .devcontainer/references and .devcontainer/SalesModule folders

import streamlit as st
from html import escape
import os, re, tempfile, base64, time
from datetime import datetime

# Optional libraries
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

# TF-IDF tools (optional)
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

# ---------------- Page config ----------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# ---------------- repo asset paths (raw) ----------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
BACKGROUND_URL = REPO_RAW_BASE + "/.devcontainer/background1.png"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# ---------------- safe session state defaults ----------------
for key, val in {
    "chat_history": [],
    "main_input": "",
    "selected_brand": "trelegy",
    "temperature": 0.62,
    "search_mode": "deep",  # deep | shallow
    "medical_summary": "",
    "sales_summary": "",
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "followup_state": None  # {"msg_idx": int, "type":"dislike"|"needmore"}
}.items():
    st.session_state.setdefault(key, val)

# ---------------- CSS / background ----------------
st.markdown(
    f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}}
.title-box {{
  background: rgba(255,255,255,0.94);
  padding: 10px;
  border-radius: 10px;
  margin-bottom: 12px;
  position: relative;
  display:flex;
  align-items:center;
  justify-content:center;
}}
.title-box img.left-logo {{ position:absolute; left:12px; height:64px; }}
.title-box img.right-logo {{ position:absolute; right:12px; height:64px; }}
.chat-container {{
  max-height: 62vh;
  overflow-y: auto;
  padding: 12px;
  background: rgba(255,255,255,0.95);
  border-radius: 8px;
  margin-bottom: 120px;
}}
.chat-bubble-user {{ background:#0078D7; color:white; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto; }}
.chat-bubble-ai {{ background:#eef9ff; color:#000; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }}
.suggestions-expander .streamlit-expanderHeader {{ font-weight:700; }}
.suggestion-pill {{ background:#fff; border:1px solid #ddd; padding:8px 12px; border-radius:20px; cursor:pointer; display:inline-block; margin:6px; }}
.suggestion-pill:hover {{ background:#f0f8ff; }}
.citation-box {{ background:#fbfbff; border-left:4px solid #0078D7; padding:8px; margin-top:8px; border-radius:6px; font-size:13px; white-space:pre-wrap; }}
.input-area {{ position: fixed; left:20px; right:20px; bottom:18px; z-index:9999; display:flex; gap:8px; align-items:flex-end; }}
.input-area textarea {{ width:100%; min-height:72px; max-height:200px; padding:10px; border-radius:8px; border:1px solid #ccc; resize:vertical; }}
.send-button {{ height:44px; padding:0 14px; border-radius:8px; border:none; background:#FF6F00; color:white; cursor:pointer; font-weight:600; }}
.fixed-disclaimer {{ position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------- GROQ client init (if available) ----------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = None
if Groq is not None and GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

# ---------------- Brand configuration (HCP segments, personas, barriers, specialties) ----------------
brand_data = {
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Concerns about side effects", "Cost/coverage"],
        "specialties": ["GP", "Pulmonologist", "Respiratory Specialist"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy/"
    },
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "specialties": ["GP", "Dermatologist", "Geriatrician"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/"
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited patient eligibility", "Access/reimbursement issues"],
        "specialties": ["Oncologist", "Medical Oncologist"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli/"
    }
}

# ---------------- Helpers: read text (pdf/txt) ----------------
def read_file_text(path):
    if not os.path.exists(path):
        return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader is not None:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()
    except Exception as e:
        return f"[Error reading {os.path.basename(path)}: {e}]"

# ---------------- Build corpus for brand (references + sales) ----------------
def build_corpus_for_brand(brand_key, chunk_size_sentences=3):
    base_paths = [
        brand_data[brand_key]["references_path"],
        brand_data[brand_key]["sales_path"]
    ]
    chunks = []
    metas = []
    for folder in base_paths:
        if not folder or not os.path.exists(folder):
            continue
        for fname in sorted(os.listdir(folder)):
            if not fname.lower().endswith((".pdf", ".txt")):
                continue
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

def local_tf_idf_snippets(query, chunks, metas, top_n=3):
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
    # fallback substring search
    out = []
    q = query.lower()
    for i, c in enumerate(chunks):
        if q in c.lower():
            out.append({"score": 1.0, "text": c, "meta": metas[i]})
            if len(out) >= top_n:
                break
    return out

# ---------------- Summarization helpers ----------------
def simple_summary(text, bullets=6):
    if not text:
        return ""
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    selected = sents[:max(1, bullets)]
    return "\n".join([s.strip() for s in selected if s.strip()])

def model_summary(text, bullets=6):
    # Use Groq if available otherwise simple heuristic
    if client is None or not text:
        return simple_summary(text, bullets)
    try:
        prompt = f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return resp.choices[0].message.content
    except Exception:
        return simple_summary(text, bullets)

# ---------------- TTS preprocessing to avoid "reading punctuation" and add pauses ----------------
def tts_preprocess(text):
    if not text:
        return ""
    # Replace common markup that should not be read literally
    # Remove sequences of punctuation and keep sentence breaks.
    # Strategy: split into sentences, strip punctuation tokens (but keep sentence ends), then join with short "..." pause.
    sents = re.split(r'(?<=[\.\?\!])\s+', text.strip())
    clean_sents = []
    for s in sents:
        s = s.strip()
        if not s:
            continue
        # remove extraneous punctuation that TTS might read oddly (preserve internal numbers/letters)
        s = re.sub(r'[\[\]\(\)\{\}<>\"*_:;=\\/]', '', s)
        # remove commas and excessive dashes to prevent robotic reading
        s = re.sub(r'[,—–\-]', '', s)
        # ensure sentence ends with a period for pacing
        if not re.search(r'[\.!?]$', s):
            s = s + '.'
        clean_sents.append(s)
    # join with soft pause markers (TTS will read them as small pauses)
    joined = " ... ".join(clean_sents)
    # reduce repeated dots
    joined = re.sub(r'\.{3,}', ' ... ', joined)
    return joined

def generate_audio(text):
    if not text or gTTS is None:
        return ""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        tts_text = tts_preprocess(text)
        tts = gTTS(text=tts_text, lang="en", slow=False)
        tts.save(tmp.name)
        with open(tmp.name, "rb") as fh:
            return base64.b64encode(fh.read()).decode()
    except Exception:
        return ""

# ---------------- Sidebar: brand selection, HCP fields, summaries ----------------
with st.sidebar:
    st.header("Filters & Brand Context")
    brand_keys = list(brand_data.keys())
    sel_idx = brand_keys.index(st.session_state.selected_brand) if st.session_state.selected_brand in brand_keys else 0
    selected_brand = st.selectbox("Brand", brand_keys, index=sel_idx)
    st.session_state.selected_brand = selected_brand
    bconf = brand_data[selected_brand]

    # brand HCP details
    segment = st.selectbox("Segment", bconf["segments"], key="seg")
    persona = st.selectbox("HCP Persona", bconf["personas"], key="persona")
    barrier = st.multiselect("Barriers", bconf["barriers"], key="barriers")
    specialty = st.selectbox("Specialty", bconf["specialties"], key="specialty")
    objective = st.selectbox("Objective", ["Awareness", "Adoption", "Retention"], key="objective")

    st.write("---")
    st.subheader("Summaries (auto if empty)")
    med_in = st.text_area("Medical References Summary (edit or leave empty)", value=st.session_state.medical_summary, height=160)
    sales_in = st.text_area("Sales Module Summary (edit or leave empty)", value=st.session_state.sales_summary, height=160)
    st.session_state.medical_summary = med_in.strip()
    st.session_state.sales_summary = sales_in.strip()

    st.write("---")
    st.subheader("Options")
    st.session_state.temperature = st.slider("Temperature", 0.0, 1.0, st.session_state.temperature, 0.05)
    st.session_state.search_mode = st.selectbox("Search mode", ["deep", "shallow"], index=0 if st.session_state.search_mode == "deep" else 1)
    add_urls = st.text_area("External reference URLs (one per line, optional)", value="", height=80)
    st.write("---")
    if st.button("🗑️ Clear chat"):
        st.session_state.chat_history = []
    st.write("---")
    st.caption("Summaries will be auto-generated from brand files in .devcontainer if left empty.")

# ---------------- Build brand corpora and auto-generate summaries if empty ----------------
# Build corpus for brand (references + sales)
chunks, chunk_meta = build_corpus_for_brand(st.session_state.selected_brand)

# Auto-generate medical summary if empty
if not st.session_state.medical_summary:
    refs_path = brand_data[st.session_state.selected_brand]["references_path"]
    combined = ""
    if os.path.exists(refs_path):
        for fname in sorted(os.listdir(refs_path)):
            if fname.lower().endswith((".pdf", ".txt")):
                combined += read_file_text(os.path.join(refs_path, fname)) + "\n"
    if combined.strip():
        st.session_state.medical_summary = model_summary(combined, bullets=6)

# Auto-generate sales summary if empty
if not st.session_state.sales_summary:
    sales_path = brand_data[st.session_state.selected_brand]["sales_path"]
    combined = ""
    if os.path.exists(sales_path):
        for fname in sorted(os.listdir(sales_path)):
            if fname.lower().endswith((".pdf", ".txt")):
                combined += read_file_text(os.path.join(sales_path, fname)) + "\n"
    if combined.strip():
        st.session_state.sales_summary = model_summary(combined, bullets=6)

# ---------------- Title box with logos ----------------
st.markdown(
    f"""
<div class="title-box">
  <img src="{GSK_LOGO_RAW}" class="left-logo">
  <h2>💡 AI Sales Call Assistant — {brand_data[st.session_state.selected_brand]['display']}</h2>
  <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""",
    unsafe_allow_html=True,
)

# ---------------- Prompt suggestions (collapsible expander) ----------------
def build_brand_suggestions(bk, persona, barrier_list, segment, specialty, objective):
    s = []
    s.append(f"Generate call flow for {persona} focused on {objective}.")
    if barrier_list:
        s.append(f"Handle objection: {', '.join(barrier_list[:2])} for {persona}.")
    else:
        s.append(f"Identify common objections for {persona}.")
    s.append(f"Summarize HCP persona insights for {persona}.")
    s.append(f"Key talking points for {brand_data[bk]['display']} in {segment}.")
    s.append(f"Draft a short adoption message for {brand_data[bk]['display']} to a {specialty}.")
    return s

with st.expander("Prompt Suggestions (click to autofill)", expanded=False):
    suggs = build_brand_suggestions(st.session_state.selected_brand, persona, barrier, segment, specialty, objective)
    cols = st.columns([1,1,1])
    for i, s in enumerate(suggs):
        col = cols[i % 3]
        if col.button(s, key=f"sugg_{i}"):
            # autofill only — user must press Send
            st.session_state.main_input = s

# ---------------- Chat container ----------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for idx, msg in enumerate(st.session_state.chat_history):
    role = msg.get("role", "assistant" if msg.get("content") else "user")
    if role == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)

        # display citations if available
        if msg.get("citations"):
            for c in msg["citations"]:
                fname = c["meta"]["filename"]
                # best-effort link to repo blob
                blob_url = f"https://github.com/{REPO_USER}/{REPO_NAME}/blob/{COMMIT}/.devcontainer"
                if os.path.exists(os.path.join(brand_data[st.session_state.selected_brand]["references_path"], fname)):
                    blob_url += f"/references/{st.session_state.selected_brand}/{fname}"
                else:
                    blob_url += f"/SalesModule/{st.session_state.selected_brand}/{fname}"
                st.markdown(f'<div class="citation-box"><b>Excerpt from {escape(fname)}:</b><br>{escape(c["text"][:800])}...<br><a href="{blob_url}" target="_blank">View full file</a></div>', unsafe_allow_html=True)

        # audio
        if msg.get("audio"):
            try:
                st.audio(base64.b64decode(msg["audio"]), format="audio/mp3")
            except Exception:
                pass

        # feedback buttons
        col1, col2, col3, col4 = st.columns(4)
        if col1.button("👍 Like", key=f"like_{idx}"):
            st.success("Thanks — noted 👍")
        if col2.button("👎 Dislike", key=f"dislike_{idx}"):
            st.session_state.followup_state = {"msg_idx": idx, "type": "dislike"}
        if col3.button("😐 Neutral", key=f"neutral_{idx}"):
            st.info("Marked as neutral")
        if col4.button("🔄 Need more", key=f"needmore_{idx}"):
            st.session_state.followup_state = {"msg_idx": idx, "type": "needmore"}

    # If follow-up active for this message, show clarifying input below it
    if st.session_state.get("followup_state") and st.session_state["followup_state"]["msg_idx"] == idx:
        ftype = st.session_state["followup_state"]["type"]
        prompt_q = "What exactly is missing or how should we improve it?" if ftype == "dislike" else "Which area should we expand on?"
        clar = st.text_input(prompt_q, key=f"clarify_{idx}")
        if st.button("Submit clarification", key=f"clarify_submit_{idx}"):
            clar_text = st.session_state.get(f"clarify_{idx}", "").strip()
            if clar_text:
                # find previous user message to base regeneration on
                orig_user = ""
                for j in range(idx - 1, -1, -1):
                    if st.session_state.chat_history[j].get("role") == "user":
                        orig_user = st.session_state.chat_history[j].get("content", "")
                        break
                # build prompt with summaries + uploaded pdf
                combined_ctx = "\n\n".join([
                    "Medical summary:\n" + (st.session_state.medical_summary or ""),
                    "Sales summary:\n" + (st.session_state.sales_summary or ""),
                    "Uploaded PDF (truncated):\n" + (st.session_state.uploaded_pdf_text[:4000] if st.session_state.uploaded_pdf_text else "")
                ])
                regen_prompt = f"{orig_user}\n\nUser clarification: {clar_text}\n\nContext:\n{combined_ctx[:8000]}"
                new_response = "(AI unavailable)"
                if client:
                    try:
                        resp = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[{"role": "system", "content": "You are a helpful pharmaceutical sales assistant."},
                                      {"role": "user", "content": regen_prompt}],
                            temperature=st.session_state.temperature
                        )
                        new_response = resp.choices[0].message.content
                    except Exception as e:
                        new_response = f"(AI error regenerating: {e})"
                else:
                    new_response = "(Fallback) " + clar_text
                # update existing assistant message
                st.session_state.chat_history[idx]["content"] = new_response
                # update citations locally
                new_cits = local_tf_idf_snippets(clar_text or orig_user, chunks, chunk_meta, top_n=3 if st.session_state.search_mode == "deep" else 1)
                st.session_state.chat_history[idx]["citations"] = new_cits
                st.session_state.chat_history[idx]["audio"] = generate_audio(new_response)
                # clear followup
                st.session_state.followup_state = None
                st.session_state[f"clarify_{idx}"] = ""
                st.experimental_rerun()

st.markdown('</div>', unsafe_allow_html=True)

# ---------------- Chat input area (form) ----------------
with st.form(key="chat_form", clear_on_submit=False):
    txt = st.text_area("Ask or continue your sales dialogue...", value=st.session_state.get("main_input", ""), key="main_chat_area", height=120)
    submitted = st.form_submit_button("Send")
    if submitted and txt.strip():
        user_text = txt.strip()
        # add user message
        st.session_state.chat_history.append({"role": "user", "content": user_text})
        # build combined context to inject into model prompt
        combined_ctx = "\n\n".join([
            "Medical summary:\n" + (st.session_state.medical_summary or ""),
            "Sales summary:\n" + (st.session_state.sales_summary or ""),
            "Uploaded PDF:\n" + (st.session_state.uploaded_pdf_text[:4000] if st.session_state.uploaded_pdf_text else "")
        ])
        system_prompt = "You are a helpful pharmaceutical sales assistant. Use the provided medical and sales summaries to ground your replies and reference the content where appropriate."
        prompt = f"{user_text}\n\nBrand: {brand_data[st.session_state.selected_brand]['display']}\nPersona: {persona}\nSegment: {segment}\nSpecialty: {specialty}\nObjective: {objective}\nBarriers: {', '.join(barrier) if barrier else 'None'}\n\n{combined_ctx[:8000]}"
        ai_content = "(AI not available)"
        if client:
            try:
                resp = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
                    temperature=st.session_state.temperature
                )
                ai_content = resp.choices[0].message.content
            except Exception as e:
                ai_content = f"(AI Error: {e})"
        else:
            ai_content = f"(Fallback) {user_text}"

        # local citations
        snips = local_tf_idf_snippets(user_text, chunks, chunk_meta, top_n=3 if st.session_state.search_mode == "deep" else 1)
        audio_b64 = generate_audio(ai_content)
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": ai_content,
            "citations": snips,
            "audio": audio_b64
        })
        # clear main input
        st.session_state["main_input"] = ""

# ---------------- PDF upload and summary (separate expander) ----------------
with st.expander("📄 Upload Custom PDF for AI Context", expanded=False):
    up = st.file_uploader("Upload PDF (will be added to context)", type=["pdf"])
    pdf_summary_mode = st.selectbox("PDF Summary Size", ["Consisted", "Normal", "Detailed"], index=1)
    if up is not None:
        # read pdf
        try:
            if PdfReader is not None:
                reader = PdfReader(up)
                pages_text = "".join([p.extract_text() or "" for p in reader.pages])
            else:
                # fallback: read as bytes -> blank
                pages_text = ""
            st.session_state.uploaded_pdf_text = pages_text
            st.success(f"Loaded {len(pages_text)} characters from uploaded PDF.")
            bullets = {"Consisted":5, "Normal":10, "Detailed":20}.get(pdf_summary_mode, 10)
            # summarize via model if available
            if client and pages_text.strip():
                try:
                    summ_prompt = f"Summarize into {bullets} bullet points:\n\n{pages_text[:12000]}"
                    summ = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                                         messages=[{"role":"user","content":summ_prompt}],
                                                         temperature=0.2)
                    st.session_state.pdf_summary = summ.choices[0].message.content
                except Exception:
                    st.session_state.pdf_summary = simple_summary(pages_text, bullets)
            else:
                st.session_state.pdf_summary = simple_summary(pages_text, bullets)
        except Exception as e:
            st.error(f"Could not read uploaded PDF: {e}")
    if st.session_state.pdf_summary:
        st.markdown(f"<div style='background:#E8F4FF;padding:10px;border-radius:8px;white-space:pre-line'>{escape(st.session_state.pdf_summary)}</div>", unsafe_allow_html=True)

# ---------------- Export area ----------------
if st.session_state.chat_history:
    with st.expander("💾 Export / Download Chat", expanded=False):
        export_txt = "\n\n".join([f"{('You' if m['role']=='user' else 'AI')}: {m['content']}" for m in st.session_state.chat_history])
        st.download_button("⬇️ Download TXT", export_txt.encode("utf-8"), file_name=f"{st.session_state.selected_brand}_chat_{datetime.now().strftime('%Y%m%d')}.txt")
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

# ---------------- Footer disclaimer ----------------
st.markdown('<div class="fixed-disclaimer">⚠️ This AI Sales Call Assistant is for informational and educational purposes only. Verify all medical content with approved references and company guidance before use.</div>', unsafe_allow_html=True)
