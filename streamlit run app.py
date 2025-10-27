# app.py - AI Sales Call Assistant (final merged version)
import streamlit as st
from PIL import Image
import os, re, tempfile, base64, math
from io import BytesIO
from datetime import datetime
from html import escape

# attempt imports that may not exist in every environment
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

# TF-IDF tools (optional - fallback implemented)
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

# Optional DOCX export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

# Optional ElevenLabs TTS
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except Exception:
    ELEVENLABS_AVAILABLE = False

# ---------------- Page config ----------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ---------------- Repo / Assets ----------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
BACKGROUND_URL = REPO_RAW_BASE + "/.devcontainer/background1.png"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# ---------------- Safe Session State Initialization ----------------
defaults = {
    "chat_history": [],
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "main_input": "",
    "selected_brand": "trelegy",
    "temperature": 0.6,
    "search_mode": "deep",
    "sales_summary": "",
    "medical_summary": "",
    "followup_state": None,  # dict: {"msg_idx":int, "type":"dislike"|"needmore"}
}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)

# ---------------- CSS (ensure Streamlit container background) ----------------
st.markdown(
    f"""
<style>
/* apply background to main app container (data-testid) */
[data-testid="stAppViewContainer"] {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}}
.title-box {{
  background: rgba(255,255,255,0.92);
  padding: 12px;
  border-radius: 10px;
  margin-bottom: 14px;
  position: relative;
  display:flex;
  align-items:center;
  justify-content:center;
}}
.title-box img.left-logo {{ position:absolute; left:16px; width:120px; height:auto; }}
.title-box img.right-logo {{ position:absolute; right:16px; width:120px; height:auto; }}
.chat-container {{
  max-height: 58vh;
  overflow-y:auto;
  padding: 14px;
  border-radius: 10px;
  background: rgba(255,255,255,0.95);
  margin-bottom: 140px;
}}
.chat-bubble-user {{ background:#0078D7; color:white; padding:12px; border-radius:10px; margin:8px 0; max-width:78%; margin-left:auto; }}
.chat-bubble-ai {{ background:#d9f0ff; color:#000; padding:12px; border-radius:10px; margin:8px 0; max-width:78%; }}
.suggestions-inline {{ background: rgba(255,255,255,0.96); padding:10px; border-radius:8px; box-shadow:0 4px 10px rgba(0,0,0,0.06); }}
.suggestion-pill {{ background:#fff; border:1px solid #ddd; padding:8px 12px; border-radius:20px; cursor:pointer; margin:6px; display:inline-block; }}
.suggestion-pill:hover {{ background:#eef6ff; }}
.input-area {{
  position: fixed;
  left:24px;
  right:24px;
  bottom:18px;
  z-index:9999;
  display:flex;
  gap:8px;
  align-items:flex-end;
}}
.input-area textarea {{
  width:100%;
  min-height:72px;
  max-height:180px;
  padding:10px;
  border-radius:8px;
  border:1px solid #ccc;
  resize:vertical;
}}
.send-button {{
  height:44px;
  padding:0 14px;
  border-radius:8px;
  border:none;
  background:#FF6F00;
  color:white;
  cursor:pointer;
  display:flex;
  align-items:center;
  gap:8px;
  font-weight:600;
}}
.citation-box {{
  background:#fbfbff;
  border-left:4px solid #0078D7;
  padding:8px;
  margin-top:8px;
  border-radius:6px;
  font-size:13px;
  white-space:pre-wrap;
}}
.fixed-disclaimer {{ position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }}
</style>
""",
    unsafe_allow_html=True,
)

# ---------------- GROQ Client (if available) ----------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = None
if Groq is not None and GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

# ---------------- Brand config (paths) ----------------
brand_data = {
    "trelegy": {
        "display": "Trelegy",
        "references_path": "./references/trelegy/",
        "sales_path": "./Salesmodule/trelegy",
    },
    "shingrix": {
        "display": "Shingrix",
        "references_path": "./references/shingrix/",
        "sales_path": "./Salesmodule/shingrix",
    },
    "jemperli": {
        "display": "Jemperli",
        "references_path": "./references/jemperli/",
        "sales_path": "./Salesmodule/jemperli",
    },
}

# ---------------- Helper functions ----------------
def read_pdf_or_text(path):
    """Return text for PDF or txt; robust to missing PyPDF2."""
    try:
        if path.lower().endswith(".pdf") and PdfReader is not None:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()
    except Exception as e:
        return f"[Error reading {os.path.basename(path)}: {e}]"

def build_corpus_for_brand(brand_key, chunk_size_sentences=3):
    """Return chunks and metadata for both references and sales module for a brand."""
    chunks = []
    metas = []
    for folder in (brand_data[brand_key]["references_path"], brand_data[brand_key]["sales_path"]):
        if not folder or not os.path.exists(folder):
            continue
        files = [f for f in os.listdir(folder) if f.lower().endswith((".pdf", ".txt"))]
        for fname in files:
            p = os.path.join(folder, fname)
            text = read_pdf_or_text(p)
            # naive sentence split
            sents = re.split(r'(?<=[\.\?\!])\s+', text)
            for i in range(0, max(1, len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename": fname, "folder": folder, "start": i})
    return chunks, metas

def find_top_n_snippets_local(query, chunks, metas, top_n=3):
    if not chunks:
        return []
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks + [query])
            chunk_vecs = vectorizer.transform(chunks)
            q_vec = vectorizer.transform([query])
            sims = linear_kernel(q_vec, chunk_vecs).flatten()
            idxs = sims.argsort()[::-1][:top_n]
            return [{"score": float(sims[i]), "text": chunks[i], "meta": metas[i]} for i in idxs if sims[i] > 0]
        except Exception:
            pass
    # fallback substring match
    q = query.lower()
    out = []
    for i, c in enumerate(chunks):
        if q in c.lower():
            out.append({"score": 1.0, "text": c, "meta": metas[i]})
            if len(out) >= top_n:
                break
    return out

def safe_generate_audio(text):
    if not text:
        return ""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        tts_text = re.sub(r'[,*]{1,}', '', text)
        if ELEVENLABS_AVAILABLE and "ELEVENLABS_API_KEY" in st.secrets:
            # note: elevenlabs usage may differ; keep as fallback
            try:
                elevenlabs.api_key = st.secrets.get("ELEVENLABS_API_KEY")
                audio_stream = elevenlabs.generate(text=tts_text, voice=st.secrets.get("ELEVENLABS_VOICE_ID", None), stream=True)
                with open(tmp.name, "wb") as f:
                    for ch in audio_stream:
                        f.write(ch)
            except Exception:
                pass
        if gTTS is not None:
            tts = gTTS(text=tts_text, lang="en", slow=False)
            tts.save(tmp.name)
        with open(tmp.name, "rb") as fh:
            return base64.b64encode(fh.read()).decode()
    except Exception:
        return ""

def generate_summary_simple(text, max_sentences=6):
    # Very simple heuristic summary: take first N sentences of text
    if not text:
        return ""
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    return "\n".join(sents[:max_sentences])

def generate_summary_via_model(text, bullets=6):
    if not client:
        return generate_summary_simple(text, bullets)
    try:
        prompt = f"Summarize the following document into {bullets} concise bullet points:\n\n{text[:12000]}"
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return resp.choices[0].message.content
    except Exception:
        return generate_summary_simple(text, bullets)

# ---------------- Sidebar: filters, summaries, options ----------------
with st.sidebar:
    st.header("Filters & Options")
    brand_choice = st.selectbox("Brand", list(brand_data.keys()), index=list(brand_data.keys()).index(st.session_state.selected_brand))
    st.session_state.selected_brand = brand_choice
    segment = st.selectbox("Segment (call flow)", ["Default"], key="seg_select")
    persona = st.selectbox("HCP Persona", ["Default Persona"], key="persona_select")
    barrier = st.multiselect("Barriers", ["Barrier A", "Barrier B"], key="barrier_select")
    st.session_state.temperature = st.slider("AI Temperature", 0.0, 1.0, st.session_state.temperature, 0.05)
    st.session_state.search_mode = st.selectbox("Search mode", ["deep", "shallow"], index=0 if st.session_state.search_mode == "deep" else 1)
    st.write("---")

    # Summaries area for medical references & sales module
    st.subheader("Auto / Manual Summaries")
    # Show existing summaries if present; allow user to edit
    med_summary_input = st.text_area("Medical References Summary (edit or leave empty to auto-generate)", value=st.session_state.medical_summary, height=160)
    sales_summary_input = st.text_area("Sales Module Summary (edit or leave empty to auto-generate)", value=st.session_state.sales_summary, height=160)

    # If user edited, update session state
    st.session_state.medical_summary = med_summary_input.strip()
    st.session_state.sales_summary = sales_summary_input.strip()

    st.write("---")
    st.write("Add external URLs to include as context (one per line):")
    external_urls_text = st.text_area("", value="", height=80)
    st.write("---")
    if st.button("🗑️ Clear chat"):
        st.session_state.chat_history = []
    st.write("---")
    st.write("Export:")
    export_fmt = st.radio("Format", ["TXT", "DOCX"], index=0)
    st.write("---")
    st.caption("Summaries will be auto-generated if left empty using loaded PDFs (model or heuristic).")

# ---------------- Build or load corpora for selected brand ----------------
chunks, chunk_meta = build_corpus_for_brand(st.session_state.selected_brand)

# If summaries empty => auto-generate using the brand files
if not st.session_state.medical_summary:
    # Build medical combined text by reading references folder
    refs_folder = brand_data[st.session_state.selected_brand]["references_path"]
    combined_refs_text = ""
    if os.path.exists(refs_folder):
        for f in os.listdir(refs_folder):
            if f.lower().endswith((".pdf", ".txt")):
                combined_refs_text += read_pdf_or_text(os.path.join(refs_folder, f)) + "\n"
    if combined_refs_text.strip():
        st.session_state.medical_summary = generate_summary_via_model(combined_refs_text, bullets=6)
if not st.session_state.sales_summary:
    sales_folder = brand_data[st.session_state.selected_brand]["sales_path"]
    combined_sales_text = ""
    if os.path.exists(sales_folder):
        for f in os.listdir(sales_folder):
            if f.lower().endswith((".pdf", ".txt")):
                combined_sales_text += read_pdf_or_text(os.path.join(sales_folder, f)) + "\n"
    if combined_sales_text.strip():
        st.session_state.sales_summary = generate_summary_via_model(combined_sales_text, bullets=6)

# ---------------- Title box with logos ----------------
st.markdown(
    f"""
<div class="title-box">
  <img src="{GSK_LOGO_RAW}" class="left-logo">
  <h1>💡 AI Sales Call Assistant — {brand_data[st.session_state.selected_brand]['display']}</h1>
  <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""",
    unsafe_allow_html=True,
)

# ---------------- Prompt suggestions (above chat input) ----------------
suggestions = build_suggestions_for_brand = lambda bk, p, b, s, sp, o: [
    f"Generate call flow for {p} focused on {o}.",
    f"Handle objection: {', '.join(b[:2])} for {p}." if b else f"Identify common objections for {p}.",
    f"Summarize HCP persona insights for {p}.",
    f"Key talking points for {brand_data[bk]['display']}.",
    f"Draft a short adoption message for {brand_data[bk]['display']} to a {sp}."
]

st.markdown("<div style='margin-bottom:6px'><strong>Prompt Suggestions</strong> — click to autofill the input</div>", unsafe_allow_html=True)
cols = st.columns([1, 1, 1])
sugs = build_suggestions_for_brand(st.session_state.selected_brand, persona, barrier, segment, "Specialist", "Awareness")
for i, s in enumerate(sugs):
    c = cols[i % 3]
    if c.button(s, key=f"sugg_{i}"):
        # Autofill only (user must press Send)
        st.session_state["main_input"] = s

# ---------------- Chat container display ----------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for idx, msg in enumerate(st.session_state.chat_history):
    role = msg.get("role", "assistant" if msg.get("content") else "user")
    if role == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)

        # inline citations if present
        if msg.get("citations"):
            for c in msg["citations"]:
                fname = c["meta"]["filename"]
                # Build blob link to repo (best-effort)
                repo_blob = f"https://github.com/{REPO_USER}/{REPO_NAME}/blob/{COMMIT}/.devcontainer"
                if os.path.exists(os.path.join(brand_data[st.session_state.selected_brand]["references_path"], fname)):
                    blob_url = f"{repo_blob}/references/{st.session_state.selected_brand}/{fname}"
                else:
                    blob_url = f"{repo_blob}/Salesmodule/{st.session_state.selected_brand}/{fname}"
                st.markdown(
                    f'<div class="citation-box"><b>Excerpt from {escape(fname)}:</b><br>{escape(c["text"][:800])}...<br><a href="{blob_url}" target="_blank">View full file</a></div>',
                    unsafe_allow_html=True,
                )
        # audio player
        if msg.get("audio"):
            try:
                st.audio(base64.b64decode(msg["audio"]), format="audio/mp3")
            except Exception:
                pass

        # feedback buttons (interactive)
        fb_cols = st.columns([1, 1, 1, 1])
        if fb_cols[0].button("👍 Like", key=f"like_{idx}"):
            st.success("Thanks for the feedback — noted 👍")
        if fb_cols[1].button("👎 Dislike", key=f"dislike_{idx}"):
            # mark followup state and render a clarifying input below (persisted)
            st.session_state.followup_state = {"msg_idx": idx, "type": "dislike"}
        if fb_cols[2].button("😐 Neutral", key=f"neutral_{idx}"):
            st.info("Thanks — noted as neutral")
        if fb_cols[3].button("🔄 Need more", key=f"needmore_{idx}"):
            st.session_state.followup_state = {"msg_idx": idx, "type": "needmore"}

    # If followup for this message is active, show clarifying input
    if st.session_state.get("followup_state") and st.session_state["followup_state"]["msg_idx"] == idx:
        follow_type = st.session_state["followup_state"]["type"]
        prompt_label = "What exactly is missing or how should we improve it?" if follow_type == "dislike" else "What area should we expand on?"
        # use simple input widget outside any form
        clar = st.text_input(prompt_label, key=f"clarify_{idx}")
        if st.button("Submit clarification", key=f"clarify_submit_{idx}"):
            clar_text = st.session_state.get(f"clarify_{idx}", "").strip()
            if clar_text:
                # regenerate based on clarification
                # Original user prompt generally precedes assistant message; find it
                # best-effort: look for previous user message
                orig_user_text = ""
                # search backwards for last user message before this assistant msg
                for j in range(idx - 1, -1, -1):
                    if st.session_state.chat_history[j].get("role") == "user":
                        orig_user_text = st.session_state.chat_history[j].get("content", "")
                        break
                # build combined context including summaries and uploaded pdf
                combined_context = "\n\n".join(
                    [
                        "Medical summary:\n" + (st.session_state.medical_summary or ""),
                        "Sales summary:\n" + (st.session_state.sales_summary or ""),
                        "Uploaded PDF (truncated):\n" + (st.session_state.uploaded_pdf_text[:4000] if st.session_state.uploaded_pdf_text else ""),
                    ]
                )
                regeneration_prompt = f"{orig_user_text}\n\nClarification from user: {clar_text}\n\nContext:\n{combined_context[:8000]}"
                # call model if present
                new_resp = "(AI unavailable)"
                if client:
                    try:
                        resp = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=[{"role": "system", "content": "You are a helpful pharmaceutical sales assistant."},
                                      {"role": "user", "content": regeneration_prompt}],
                            temperature=st.session_state.temperature,
                        )
                        new_resp = resp.choices[0].message.content
                    except Exception as e:
                        new_resp = f"(AI error regenerating: {e})"
                else:
                    new_resp = "(Fallback) Regenerated response based on clarification: " + clar_text
                # replace old assistant content with improved response (keeps citations empty initially)
                st.session_state.chat_history[idx]["content"] = new_resp
                # update citations by running local TF-IDF search on clarification + original prompt
                local_query = clar_text if clar_text else orig_user_text
                new_cits = find_top_n_snippets_local(local_query, chunks, chunk_meta, top_n=3 if st.session_state.search_mode == "deep" else 1)
                st.session_state.chat_history[idx]["citations"] = new_cits
                st.session_state.chat_history[idx]["audio"] = safe_generate_audio(new_resp)
                # clear followup state
                st.session_state.followup_state = None
                # clear clar input value
                st.session_state[f"clarify_{idx}"] = ""
                st.experimental_rerun()
st.markdown("</div>", unsafe_allow_html=True)

# ---------------- Chat Input Form ----------------
with st.form(key="main_chat_form", clear_on_submit=False):
    temp_msg = st.text_area("Ask or continue your sales dialogue...", value=st.session_state.get("main_input", ""), key="main_chat_area", height=120)
    submit = st.form_submit_button("Send")
    if submit and temp_msg.strip():
        user_text = temp_msg.strip()
        # add user message
        st.session_state.chat_history.append({"role": "user", "content": user_text})
        # prepare context for the model, injecting summaries
        combined_context = "\n\n".join(
            [
                "Medical summary:\n" + (st.session_state.medical_summary or ""),
                "Sales summary:\n" + (st.session_state.sales_summary or ""),
                "Uploaded PDF (truncated):\n" + (st.session_state.uploaded_pdf_text[:4000] if st.session_state.uploaded_pdf_text else ""),
            ]
        )
        system_prompt = "You are a helpful pharmaceutical sales assistant. Use provided medical and sales summaries to ground your answers."
        user_prompt = f"{user_text}\n\nContext:\n{combined_context[:8000]}"
        ai_text = "(AI not available)"
        if client:
            try:
                resp = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    temperature=st.session_state.temperature,
                )
                ai_text = resp.choices[0].message.content
            except Exception as e:
                ai_text = f"(AI Error: {e})"
        else:
            ai_text = "(Fallback) " + user_text

        # citations from local TF-IDF search
        top_snips = find_top_n_snippets_local(user_text, chunks, chunk_meta, top_n=3 if st.session_state.search_mode == "deep" else 1)
        audio_b64 = safe_generate_audio(ai_text)
        st.session_state.chat_history.append({"role": "assistant", "content": ai_text, "citations": top_snips, "audio": audio_b64})
        # clear main input safely
        st.session_state["main_input"] = ""

# ---------------- Export area ----------------
if st.session_state.chat_history:
    with st.expander("💾 Export / Download Chat", expanded=False):
        txt = "\n\n".join([f"{('You' if m['role']=='user' else 'AI')}: {m['content']}" for m in st.session_state.chat_history])
        st.download_button("⬇️ Download TXT", txt.encode("utf-8"), file_name=f"{st.session_state.selected_brand}_chat_{datetime.now().strftime('%Y%m%d')}.txt")
        if DOCX_AVAILABLE and st.button("Export as DOCX"):
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
                st.error(f"Could not create DOCX: {e}")

# ---------------- Footer disclaimer ----------------
st.markdown(
    '<div class="fixed-disclaimer">⚠️ This AI Sales Call Assistant is for informational purposes only. Verify all medical content with approved references and company guidance before use.</div>',
    unsafe_allow_html=True,
)
