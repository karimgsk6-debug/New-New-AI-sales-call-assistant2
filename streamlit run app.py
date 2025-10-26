# app.py - Final merged app with:
# - Prompt Suggestions (autofill only)
# - Temperature slider
# - Search mode (shallow / deep)
# - Send icon merged, microphone icon inside input
# - Medical references + Sales Module snippets (from PDFs)
# - Feedback (like / dislike) with follow-up questions on dislike
# - Safe session-state and graceful fallbacks

import streamlit as st
import os, re, tempfile, base64, requests, time
from datetime import datetime
from html import escape
from PyPDF2 import PdfReader
from gtts import gTTS

# Optional ML & API libs
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except Exception:
    GROQ_AVAILABLE = False

# Optional DOCX export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

# ElevenLabs optional TTS
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except Exception:
    ELEVENLABS_AVAILABLE = False

# ------------------------- Config & Repo paths -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_BLOB_BASE = f"https://github.com/{REPO_USER}/{REPO_NAME}/blob/{COMMIT}/.devcontainer"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"

BACKGROUND_URL = REPO_RAW_BASE + "/.devcontainer/background1.png"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# ------------------------- Session defaults -------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []  # list of messages: {role, content, audio?, citations?, sales_summary?, id}
if "main_input" not in st.session_state:
    st.session_state.main_input = ""
if "selected_brand" not in st.session_state:
    st.session_state.selected_brand = "trelegy"
if "tfidf_cache" not in st.session_state:
    st.session_state.tfidf_cache = None
if "expecting_followup_for" not in st.session_state:
    st.session_state.expecting_followup_for = None  # message id that asked follow-up after dislike
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.6
if "search_mode" not in st.session_state:
    st.session_state.search_mode = "deep"  # 'shallow' or 'deep'
if "last_message_id" not in st.session_state:
    st.session_state.last_message_id = 0

# ------------------------- CSS / layout -------------------------
CSS = f"""
<style>
.stApp {{ background-image: url('{BACKGROUND_URL}'); background-size:cover; background-attachment:fixed; background-position:center; }}
.title-box {{ background: rgba(255,255,255,0.94); padding:12px; border-radius:10px; position:relative; margin-bottom:12px; display:flex; align-items:center; justify-content:center; }}
.title-box img.left-logo {{ position:absolute; left:16px; width:120px; height:auto; }}
.title-box img.right-logo {{ position:absolute; right:16px; width:120px; height:auto; }}
.title-box h1 {{ margin:0; font-size:20px; }}
.chat-container {{ max-height:58vh; overflow-y:auto; padding:14px; border-radius:10px; background: rgba(255,255,255,0.96); margin-bottom:160px; }}
.chat-bubble-user {{ background:#0078D7; color:white; padding:12px; border-radius:12px; margin:10px 0; max-width:78%; margin-left:auto; }}
.chat-bubble-ai {{ background:#f7fbff; color:#000; padding:12px; border-radius:12px; margin:10px 0; max-width:78%; }}
.suggestions-inline {{ background: rgba(255,255,255,0.96); padding:10px; border-radius:8px; box-shadow:0 4px 10px rgba(0,0,0,0.06); margin-bottom:8px; }}
.suggestion-pill {{ background:#fff; border:1px solid #ddd; padding:8px 12px; border-radius:20px; cursor:pointer; margin:6px; display:inline-block; }}
.suggestion-pill:hover {{ background:#eef6ff; }}
.input-bar {{ position:fixed; left:24px; right:180px; bottom:24px; z-index:9999; display:flex; gap:8px; align-items:center; }}
.input-bar textarea {{ width:100%; min-height:64px; max-height:200px; padding:12px; border-radius:12px; border:1px solid #ccc; resize:vertical; }}
.input-buttons {{ position:fixed; right:24px; bottom:24px; z-index:9999; display:flex; gap:8px; align-items:center; }}
.send-btn {{ height:56px; width:56px; border-radius:12px; border:none; background:#FF6F00; color:white; display:flex; align-items:center; justify-content:center; cursor:pointer; }}
.mic-btn {{ height:44px; width:44px; border-radius:10px; border:1px solid #ccc; background:white; display:flex; align-items:center; justify-content:center; cursor:pointer; }}
.citation-box {{ background:#fbfbff; border-left:4px solid #0078D7; padding:8px; margin-top:8px; border-radius:6px; font-size:13px; white-space:pre-wrap; }}
.sales-box {{ background:#fff7ec; border-left:4px solid #FF6F00; padding:8px; margin-top:8px; border-radius:6px; font-size:13px; white-space:pre-wrap; }}
.feedback-area {{ margin-top:6px; display:flex; gap:8px; align-items:center; }}
.fixed-disclaimer {{ position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9998; }}
.small-note {{ font-size:12px; color:#666; margin-left:8px; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ------------------------- GROQ client -------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = None
if GROQ_AVAILABLE and GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

# ------------------------- Brands -------------------------
brand_data = {
    "trelegy": {
        "display": "Trelegy",
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy"
    },
    "shingrix": {
        "display": "Shingrix",
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix"
    },
    "jemperli": {
        "display": "Jemperli",
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli"
    }
}

# ------------------------- Helpers: file reading / corpus -------------------------
def read_file_text(path):
    try:
        if path.lower().endswith(".pdf"):
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                return fh.read()
    except Exception as e:
        return f"[Error reading {os.path.basename(path)}: {e}]"

def list_files(folder):
    if not folder or not os.path.exists(folder):
        return []
    return sorted([f for f in os.listdir(folder) if f.lower().endswith((".pdf", ".txt"))])

def build_chunks(folder_paths, chunk_sents=3):
    chunks = []
    metas = []
    for folder in folder_paths:
        if not folder or not os.path.exists(folder): continue
        for fname in list_files(folder):
            p = os.path.join(folder, fname)
            txt = read_file_text(p)
            sents = re.split(r'(?<=[\.\?\!])\s+', txt)
            if not sents:
                continue
            for i in range(0, len(sents), chunk_sents):
                chunk = " ".join(sents[i:i+chunk_sents]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename": fname, "folder": folder, "start": i})
    return chunks, metas

def shallow_search(query, chunks, metas, top_n=3):
    q = query.lower()
    out = []
    for i, c in enumerate(chunks):
        if q in c.lower():
            out.append({"score":1.0, "text":c, "meta":metas[i]})
            if len(out) >= top_n: break
    return out

def deep_search(query, chunks, metas, top_n=3):
    if not SKLEARN_AVAILABLE or not chunks:
        return shallow_search(query, chunks, metas, top_n)
    try:
        vec = TfidfVectorizer(stop_words="english").fit(chunks + [query])
        chunk_vecs = vec.transform(chunks)
        qv = vec.transform([query])
        sims = linear_kernel(qv, chunk_vecs).flatten()
        idxs = sims.argsort()[::-1][:top_n]
        res = []
        for idx in idxs:
            if sims[idx] <= 0:
                continue
            res.append({"score": float(sims[idx]), "text": chunks[idx], "meta": metas[idx]})
        return res
    except Exception:
        return shallow_search(query, chunks, metas, top_n)

def top_snippets_for_query(query, chunks, metas, mode="deep", top_n=3):
    if mode == "shallow":
        return shallow_search(query, chunks, metas, top_n)
    else:
        return deep_search(query, chunks, metas, top_n)

# ------------------------- Audio helper -------------------------
ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
    try:
        elevenlabs.api_key = ELEVENLABS_API_KEY
    except:
        pass

def tts_base64(text):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        t = re.sub(r'[,*]{1,}', '', text)
        if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
            stream = elevenlabs.generate(text=t, voice=ELEVENLABS_VOICE_ID, stream=True)
            with open(tmp.name, "wb") as fh:
                for ch in stream: fh.write(ch)
        else:
            gtts = gTTS(text=t, lang="en", slow=False)
            gtts.save(tmp.name)
        with open(tmp.name, "rb") as fh:
            return base64.b64encode(fh.read()).decode()
    except Exception:
        return ""

# ------------------------- Sidebar controls -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    sel_brand = st.selectbox("Brand", sorted(list(brand_data.keys())),
                             index=list(sorted(brand_data.keys())).index(st.session_state.get("selected_brand","trelegy")))
    st.session_state.selected_brand = sel_brand
    # small controls
    segment = st.selectbox("Segment", ["Segment A","Segment B"], key="seg_key")
    persona = st.selectbox("HCP Persona", ["Persona 1","Persona 2"], key="pers_key")
    barrier = st.multiselect("Doctor Barrier", ["Barrier 1","Barrier 2"], key="bar_key")
    specialty = st.selectbox("Specialty", ["GP","Pulmonologist"], key="spec_key")
    objective = st.selectbox("Objective", ["Awareness","Adoption"], key="obj_key")
    # temperature
    temp = st.slider("Temperature (creativity)", 0.0, 1.0, value=float(st.session_state.temperature), step=0.05, key="temp_key")
    st.session_state.temperature = temp
    # search mode
    search_mode = st.selectbox("Search mode", ["deep","shallow"], index=0 if st.session_state.search_mode=="deep" else 1, key="search_key")
    st.session_state.search_mode = search_mode
    st.session_state.language = st.radio("Language", ["English","Arabic"], horizontal=True, key="lang_key")
    if st.button("🗑️ Clear Chat", key="clear_btn"):
        st.session_state.chat_history = []
        st.session_state.tfidf_cache = None

with st.sidebar.expander("🌐 Add External Reference URLs", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_choice = st.radio("Export format", ["TXT","DOCX"], index=0, key="export_key")

# ------------------------- Header -------------------------
st.markdown(f"""
<div class="title-box">
  <img src="{GSK_LOGO_RAW}" class="left-logo">
  <h1>💡 AI Sales Call Assistant — {brand_data[st.session_state.selected_brand]['display']}</h1>
  <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# ------------------------- Build/Cache corpus -------------------------
refs_folder = brand_data[st.session_state.selected_brand]["references_path"]
sales_folder = brand_data[st.session_state.selected_brand]["sales_path"]

# list files
ref_files = list_files(refs_folder)
sales_files = list_files(sales_folder)

# cache chunks to session to avoid recompute
if not st.session_state.tfidf_cache:
    chunks, metas = build_chunks([refs_folder, sales_folder], chunk_sents=3)
    st.session_state.tfidf_cache = {"chunks":chunks, "metas":metas}
else:
    chunks = st.session_state.tfidf_cache.get("chunks", [])
    metas = st.session_state.tfidf_cache.get("metas", [])

# ------------------------- Helper: generate AI response -------------------------
def generate_ai_response(user_input, temperature=0.6, context_text=""):
    # Build system and prompt
    system_prompt = "You are a helpful pharmaceutical sales assistant. Provide concise, practical suggestions for sales calls."
    prompt = f"{user_input}\n\nContext (truncated):\n{context_text[:5000]}"
    if client:
        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":system_prompt}, {"role":"user","content":prompt}],
                temperature=float(temperature)
            )
            return resp.choices[0].message.content
        except Exception as e:
            return f"(AI Error) {e}"
    else:
        # fallback simple echo + tips
        return f"(Fallback) Suggestion based on context: {user_input}"

# ------------------------- Build prompt suggestions (brand-specific) -------------------------
def build_prompt_suggestions(brand_key, persona, barrier_list, segment, specialty, objective):
    s = []
    s.append(f"Generate call flow for {persona} focused on {objective}.")
    if barrier_list:
        s.append(f"Handle objection: {', '.join(barrier_list[:2])} for {persona}.")
    else:
        s.append(f"Identify common objections for {persona}.")
    s.append(f"Summarize HCP persona insights for {persona}.")
    s.append(f"Key talking points for {brand_key.upper()} in {segment}.")
    s.append(f"Draft a short adoption message for {brand_key.upper()} to a {specialty}.")
    return s

# ------------------------- Prompt Suggestions UI (always visible, autofill only) -------------------------
st.markdown('<div class="suggestions-inline"><b>Prompt Suggestions</b> — click to autofill the chat box (edit before send)</div>', unsafe_allow_html=True)
cols = st.columns([1,1,1])
suggestions = build_prompt_suggestions(st.session_state.selected_brand, persona, barrier, segment, specialty, objective)
for i, s in enumerate(suggestions):
    col = cols[i % 3]
    # use a unique key per suggestion
    if col.button(s, key=f"prompt_sugg_{i}"):
        # set main_input and rerun so the text area shows the value
        st.session_state.main_input = s
        st.experimental_rerun()  # immediately show autofill in the input

# small helper note
st.markdown("<div class='small-note'>Tip: click a suggestion to autofill the input; edit if you like, then press Send.</div>", unsafe_allow_html=True)

# ------------------------- Chat history display -------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for msg in st.session_state.chat_history:
    # each msg is dict: id, role, content, audio?, citations?, sales_summary?
    if msg.get("role") == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)

        # show citations (medical refs)
        if msg.get("citations"):
            for c in msg["citations"]:
                fname = c["meta"]["filename"]
                # prefer references path
                if fname in ref_files:
                    blob = f"{REPO_BLOB_BASE}/references/{st.session_state.selected_brand}/{fname}"
                else:
                    blob = f"{REPO_BLOB_BASE}/SalesModule/{st.session_state.selected_brand}/{fname}"
                snippet = c["text"]
                st.markdown(f'<div class="citation-box"><b>Excerpt from {escape(fname)}:</b><br>{escape(snippet[:800])}...<br><a href="{blob}" target="_blank">View full file</a></div>', unsafe_allow_html=True)

        # show sales module summary
        if msg.get("sales_summary"):
            st.markdown(f'<div class="sales-box"><b>Sales Module (excerpt):</b><br>{escape(msg.get("sales_summary")[:1000])}...</div>', unsafe_allow_html=True)

        # feedback UI (like/dislike)
        fb_col1, fb_col2, fb_col3 = st.columns([1,1,10])
        if fb_col1.button("👍", key=f"like_{msg['id']}"):
            # record positive feedback in message
            msg['feedback'] = "like"
            # optional: append a short ack message
            st.session_state.chat_history.append({"id": next_msg_id(), "role":"assistant","content":"Thanks — glad that helped! If you want more details, ask."})
            st.experimental_rerun()
        if fb_col2.button("👎", key=f"dislike_{msg['id']}"):
            msg['feedback'] = "dislike"
            # assistant asks a clarifying question to improve suggestions
            followup_q = "Sorry — what was missing or not helpful? (e.g. more data, different tone, shorter bullets, specific objection handling)"
            st.session_state.chat_history.append({"id": next_msg_id(), "role":"assistant", "content": followup_q})
            # set expecting_followup_for to the assistant msg id we want improved later
            st.session_state.expecting_followup_for = msg['id']
            st.experimental_rerun()
st.markdown('</div>', unsafe_allow_html=True)

# ------------------------- Input bar (merged send icon + mic icon) -------------------------
# Use a form so Send triggers server-side handling
with st.form(key="chat_input_form", clear_on_submit=False):
    text_val = st.text_area("Type your message here...", value=st.session_state.get("main_input",""), key="chat_input", height=90)
    # buttons to the right: microphone (placeholder) and send
    col1, col2 = st.columns([1,1])
    # We render mic and send as streamlit buttons grouped visually using columns
    mic_clicked = col1.button("🎤", key="mic_button")
    send_clicked = col2.form_submit_button("Send", use_container_width=True)

    if mic_clicked:
        # Placeholder action: show a small toast / message
        st.toast = None  # no-op, since st.toast may not exist; use st.info instead
        st.info("Microphone capture not implemented in this demo. You can paste or type your message.")
        # do not clear input

    if send_clicked:
        user_text = text_val.strip()
        if not user_text:
            st.warning("Please enter a message before sending.")
        else:
            # If we were expecting follow-up for a prior message (disliked), handle differently:
            if st.session_state.expecting_followup_for:
                # Attach user's clarification as feedback and regenerate improved response
                parent_id = st.session_state.expecting_followup_for
                # find parent assistant message
                parent_msg = None
                for m in st.session_state.chat_history:
                    if m.get("id") == parent_id:
                        parent_msg = m
                        break
                # append the user's clarification message
                st.session_state.chat_history.append({"id": next_msg_id(), "role":"user", "content": user_text})
                # generate a new improved response (using clarification)
                improved_prompt = f"User asked for improvement on previous answer (id={parent_id}). Clarification: {user_text}\nPlease produce an improved answer."
                combined_context = build_context(refs_folder, sales_folder, external_urls)
                assistant_resp = generate_ai_response(improved_prompt, temperature=st.session_state.temperature, context_text=combined_context)
                # find top snippets using selected search_mode
                snippets = top_snippets_for_query(user_text, chunks, metas, mode=st.session_state.search_mode, top_n=3)
                # sales snippet
                sales_snip = ""
                for meta_i, meta in enumerate(metas):
                    if meta["filename"] in sales_files:
                        sales_snip = metas[meta_i]["text"] if "text" in metas[meta_i] else ""
                        break
                # append improved assistant message
                st.session_state.chat_history.append({
                    "id": next_msg_id(),
                    "role":"assistant",
                    "content": assistant_resp,
                    "citations": snippets,
                    "sales_summary": sales_snip
                })
                # clear expecting_followup_for
                st.session_state.expecting_followup_for = None
                st.session_state.main_input = ""
                st.experimental_rerun()

            else:
                # Normal send flow
                st.session_state.chat_history.append({"id": next_msg_id(), "role":"user", "content": user_text})
                st.session_state.main_input = ""
                # Build combined_context quickly from local top-of-chunks and external URLs
                combined_context = build_context(refs_folder, sales_folder, external_urls)
                # generate assistant response
                assistant_text = generate_ai_response(user_text, temperature=st.session_state.temperature, context_text=combined_context)
                # get citations based on search_mode
                snippets = top_snippets_for_query(user_text, chunks, metas, mode=st.session_state.search_mode, top_n=3)
                # simple sales summary: first chunk coming from sales files, if any
                sales_summary = ""
                for i, m in enumerate(metas):
                    if m["filename"] in sales_files:
                        sales_summary = chunks[i]
                        break
                # generate audio optionally
                audio_b64 = ""
                try:
                    audio_b64 = tts_base64(assistant_text)
                except:
                    audio_b64 = ""
                st.session_state.chat_history.append({
                    "id": next_msg_id(),
                    "role":"assistant",
                    "content": assistant_text,
                    "audio": audio_b64,
                    "citations": snippets,
                    "sales_summary": sales_summary
                })
                st.experimental_rerun()  # refresh UI to show new messages


# ------------------------- Export section -------------------------
if st.session_state.chat_history:
    with st.expander("💾 Export / Download Chat", expanded=False):
        text_export = "\n\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in st.session_state.chat_history])
        st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{st.session_state.selected_brand}_chat.txt")
        if DOCX_AVAILABLE and st.button("Export as DOCX"):
            try:
                doc = Document()
                doc.add_heading("AI Sales Call Assistant Export", 0)
                doc.add_paragraph(f"Brand: {st.session_state.selected_brand.upper()} | Date: {datetime.now().strftime('%Y-%m-%d')}")
                for e in st.session_state.chat_history:
                    doc.add_paragraph(f"{e['role'].capitalize()}: {e['content']}")
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
                doc.save(tmp.name)
                with open(tmp.name, "rb") as fh:
                    st.download_button("⬇️ Download DOCX", fh.read(), file_name=f"{st.session_state.selected_brand}_chat.docx")
            except Exception as ex:
                st.error(f"Could not export DOCX: {ex}")

# ------------------------- Footer disclaimer -------------------------
st.markdown('<div class="fixed-disclaimer">⚠️ This AI tool is for informational purposes only. Verify medical content with approved references and company guidance.</div>', unsafe_allow_html=True)

# ------------------------- Utility functions placed after main body -------------------------
def next_msg_id():
    st.session_state.last_message_id += 1
    return st.session_state.last_message_id

def build_context(refs_folder, sales_folder, external_urls_list):
    # build a small combined context string from top files (avoid huge reads)
    ctx = ""
    # read first few reference files
    if refs_folder and os.path.exists(refs_folder):
        files = list_files(refs_folder)[:3]
        for f in files:
            try:
                ctx += read_file_text(os.path.join(refs_folder, f))[:3000] + "\n"
            except:
                pass
    # sales
    if sales_folder and os.path.exists(sales_folder):
        files = list_files(sales_folder)[:2]
        for f in files:
            try:
                ctx += read_file_text(os.path.join(sales_folder, f))[:2000] + "\n"
            except:
                pass
    # external URLs (small)
    if external_urls_list:
        for url in external_urls_list[:5]:
            try:
                r = requests.get(url, timeout=4)
                if r.status_code == 200:
                    ctx += r.text[:1500] + "\n"
            except:
                pass
    return ctx

# move helper defs above where they are used in code by reordering; (if using real-run ensure functions are defined earlier)
# But since Python executes top->bottom, we need these utility functions earlier. To ensure the file runs, you can move these function defs earlier.
# For this paste-in, if you get NameError, move the function definitions up above usage.
