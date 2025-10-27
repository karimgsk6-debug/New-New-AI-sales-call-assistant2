# app.py - AI Sales Call Assistant (updated with in-interface summaries, sales-call building, interactive feedback)
import streamlit as st
from html import escape
import os, re, tempfile, base64, json
from datetime import datetime

# Optional libs (best-effort)
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

# TF-IDF (optional)
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

# ---------------- Repo and assets ----------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
BACKGROUND_URL = REPO_RAW_BASE + "/.devcontainer/background1.png"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# ---------------- session defaults ----------------
defaults = {
    "chat_history": [],
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.62,
    "search_mode": "deep",
    "medical_summary": "",
    "sales_summary": "",
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "followup_state": None,          # {"msg_idx": int, "type": "dislike"|"neutral"|"needmore", "questions": [...], "answers": []}
    "language": "English",
}
for k,v in defaults.items():
    st.session_state.setdefault(k, v)

# ---------------- CSS / background ----------------
st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}}
.title-box {{
  background: rgba(255,255,255,0.95);
  padding: 10px;
  border-radius: 10px;
  margin-bottom: 10px;
  position: relative;
  display:flex;
  align-items:center;
  justify-content:center;
}}
.title-box img.left-logo {{ position:absolute; left:12px; height:64px; }}
.title-box img.right-logo {{ position:absolute; right:12px; height:64px; }}
.chat-container {{ max-height: 56vh; overflow-y:auto; padding:12px; background: rgba(255,255,255,0.95); border-radius:8px; margin-bottom:120px; }}
.chat-bubble-user {{ background:#0078D7; color:white; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto; }}
.chat-bubble-ai {{ background:#eef9ff; color:#000; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }}
.suggestion-pill {{ background:#fff; border:1px solid #ddd; padding:8px 12px; border-radius:20px; margin:6px; cursor:pointer; display:inline-block; }}
.suggestion-pill:hover {{ background:#f0f8ff; }}
.citation-box {{ background:#fbfbff; border-left:4px solid #0078D7; padding:8px; margin-top:8px; border-radius:6px; font-size:13px; white-space:pre-wrap; }}
.input-area {{ position: fixed; left:20px; right:20px; bottom:18px; z-index:9999; display:flex; gap:8px; align-items:flex-end; }}
.input-area textarea {{ width:100%; min-height:72px; max-height:180px; padding:10px; border-radius:8px; border:1px solid #ccc; resize:vertical; }}
.send-button {{ height:44px; padding:0 14px; border-radius:8px; border:none; background:#FF6F00; color:white; cursor:pointer; font-weight:600; }}
.fixed-disclaimer {{ position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }}
</style>
""", unsafe_allow_html=True)

# ---------------- GROQ client (if available) ----------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = None
if Groq and GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

# ---------------- Brand data (HCP, call flows) ----------------
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas": ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
        "specialties": ["GP","Dermatologist","Geriatrician"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/",
        "call_flow": ["Pre-call planning","Prepare","Engage","Create Opportunities","Influence","Impact GSO","Post-call analysis"]
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas": ["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties": ["Oncologist","Medical Oncologist"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli/",
        "call_flow": ["COCO","Anchor","Engage","Close"]
    },
    "trelegy": {  # ready to add
        "display": "Trelegy",
        "segments": ["Awareness","Diagnosis","Adoption","Adherence"],
        "personas": ["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers": ["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties": ["GP","Pulmonologist","Respiratory Specialist"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy/",
        "call_flow": ["Prepare","Engage","Demonstrate","Address Access","Close"]
    }
}

# ---------------- helpers: read files, corpus, TF-IDF search ----------------
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

def build_corpus_for_brand(brand_key, chunk_size_sentences=3):
    chunks = []
    metas = []
    for folder in (brand_data[brand_key]["references_path"], brand_data[brand_key]["sales_path"]):
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

def local_search_snippets(query, chunks, metas, top_n=3):
    if not chunks:
        return []
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks + [query])
            vecs = vectorizer.transform(chunks)
            qv = vectorizer.transform([query])
            sims = linear_kernel(qv, vecs).flatten()
            idxs = sims.argsort()[::-1][:top_n]
            results = []
            for i in idxs:
                if sims[i] <= 0:
                    continue
                results.append({"score": float(sims[i]), "text": chunks[i], "meta": metas[i]})
            return results
        except Exception:
            pass
    # fallback substring
    out=[]
    q = query.lower()
    for i,c in enumerate(chunks):
        if q in c.lower():
            out.append({"score":1.0,"text":c,"meta":metas[i]})
            if len(out) >= top_n: break
    return out

# ---------------- summarization helpers ----------------
def simple_summary(text, bullets=6):
    if not text:
        return ""
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    return "\n".join([s.strip() for s in sents[:max(1, bullets)] if s.strip()])

def model_summarize(text, bullets=6):
    if not client or not text:
        return simple_summary(text, bullets)
    try:
        prompt = f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
        resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                             messages=[{"role":"user","content":prompt}],
                                             temperature=0.2)
        return resp.choices[0].message.content
    except Exception:
        return simple_summary(text, bullets)

# ---------------- TTS preprocess ----------------
def tts_preprocess(text):
    if not text:
        return ""
    sents = re.split(r'(?<=[\.\?\!])\s+', text.strip())
    clean=[]
    for s in sents:
        if not s.strip(): continue
        s2 = re.sub(r'[\[\]\(\)\{\}<>\"*_:;=\\/]', '', s)
        s2 = re.sub(r'[,—–\-]', '', s2)
        if not re.search(r'[\.!?]$', s2):
            s2 = s2 + '.'
        clean.append(s2.strip())
    return " ... ".join(clean)

def generate_audio(text):
    if not text or not gTTS:
        return ""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        t = tts_preprocess(text)
        tts = gTTS(text=t, lang="en", slow=False)
        tts.save(tmp.name)
        with open(tmp.name, "rb") as fh:
            return base64.b64encode(fh.read()).decode()
    except Exception:
        return ""

# ---------------- Sidebar: controls ----------------
with st.sidebar:
    st.header("Filters & Options")
    brand_keys = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_keys, index=brand_keys.index(st.session_state.selected_brand) if st.session_state.selected_brand in brand_keys else 0)
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]

    segment = st.selectbox("Segment", bconf["segments"], key="seg")
    persona = st.selectbox("HCP Persona", bconf["personas"], key="persona")
    barrier = st.multiselect("Barriers", bconf["barriers"], key="bar")
    specialty = st.selectbox("Specialty", bconf["specialties"], key="spec")
    objective = st.selectbox("Objective", ["Awareness","Adoption","Retention"], key="obj")

    st.write("---")
    st.session_state.temperature = st.slider("Temperature", 0.0, 1.0, st.session_state.temperature, 0.05)
    st.session_state.search_mode = st.selectbox("Search mode", ["deep","shallow"], index=0 if st.session_state.search_mode=="deep" else 1)
    st.session_state.language = st.radio("Language", ["English","Arabic"], index=0 if st.session_state.language=="English" else 1)
    st.write("---")
    st.caption("Summaries below are auto-generated from .devcontainer files per brand, editable here in the interface.")
    if st.button("🗑️ Clear chat"):
        st.session_state.chat_history = []

# ---------------- Build corpus & auto-summaries ----------------
chunks, chunk_meta = build_corpus_for_brand(st.session_state.selected_brand)

# build medical combined text (from .devcontainer references)
refs_path = brand_data[st.session_state.selected_brand]["references_path"]
combined_refs=""
if os.path.exists(refs_path):
    for f in sorted(os.listdir(refs_path)):
        if f.lower().endswith((".pdf",".txt")):
            combined_refs += read_file_text(os.path.join(refs_path,f)) + "\n"

sales_path = brand_data[st.session_state.selected_brand]["sales_path"]
combined_sales=""
if os.path.exists(sales_path):
    for f in sorted(os.listdir(sales_path)):
        if f.lower().endswith((".pdf",".txt")):
            combined_sales += read_file_text(os.path.join(sales_path,f)) + "\n"

# Auto-generate summaries if empty
if not st.session_state.medical_summary and combined_refs.strip():
    st.session_state.medical_summary = model_summarize(combined_refs, bullets=6)
if not st.session_state.sales_summary and combined_sales.strip():
    st.session_state.sales_summary = model_summarize(combined_sales, bullets=6)

# ---------------- Title + Summaries under title ----------------
st.markdown(f"""
<div class="title-box">
  <img src="{GSK_LOGO_RAW}" class="left-logo">
  <h2>💡 AI Sales Call Assistant — {brand_data[st.session_state.selected_brand]['display']}</h2>
  <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# show summaries in interface, editable
st.markdown("### Medical References Summary")
med_summary_new = st.text_area("Edit Medical Summary (auto if left empty)", value=st.session_state.medical_summary or "", height=140, key="med_summary_area")
st.session_state.medical_summary = med_summary_new.strip()

st.markdown("### Sales Module Summary")
sales_summary_new = st.text_area("Edit Sales Module Summary (auto if left empty)", value=st.session_state.sales_summary or "", height=140, key="sales_summary_area")
st.session_state.sales_summary = sales_summary_new.strip()

# ---------------- Chat container ----------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for idx, msg in enumerate(st.session_state.chat_history):
    role = msg.get("role", "assistant" if msg.get("content") else "user")
    if role == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)
        # show citations
        if msg.get("citations"):
            for c in msg["citations"]:
                fname = c["meta"]["filename"]
                # link to repo blob best-effort
                blob_base = f"https://github.com/{REPO_USER}/{REPO_NAME}/blob/{COMMIT}/.devcontainer"
                if os.path.exists(os.path.join(brand_data[st.session_state.selected_brand]["references_path"], fname)):
                    blob = f"{blob_base}/references/{st.session_state.selected_brand}/{fname}"
                else:
                    blob = f"{blob_base}/SalesModule/{st.session_state.selected_brand}/{fname}"
                st.markdown(f'<div class="citation-box"><b>Excerpt from {escape(fname)}:</b><br>{escape(c["text"][:800])}...<br><a href="{blob}" target="_blank">View full file</a></div>', unsafe_allow_html=True)
        # audio
        if msg.get("audio"):
            try:
                st.audio(base64.b64decode(msg["audio"]), format="audio/mp3")
            except Exception:
                pass

        # feedback
        c1, c2, c3, c4 = st.columns([1,1,1,1])
        if c1.button("👍 Like", key=f"like_{idx}"):
            st.success("Thanks — feedback recorded 👍")
        if c2.button("👎 Dislike", key=f"dislike_{idx}"):
            # set followup state with generated Yes/No questions
            questions = [
                "Was the response lacking specific clinical data? (Yes/No)",
                "Was the tone or length not appropriate? (Yes/No)"
            ]
            st.session_state.followup_state = {"msg_idx": idx, "type": "dislike", "questions": questions, "answers": []}
        if c3.button("😐 Neutral", key=f"neutral_{idx}"):
            questions = ["Was the response too generic? (Yes/No)", "Do you want more examples? (Yes/No)"]
            st.session_state.followup_state = {"msg_idx": idx, "type": "neutral", "questions": questions, "answers": []}
        if c4.button("🔄 Need more", key=f"needmore_{idx}"):
            questions = ["Do you want more detail? (Yes/No)", "Should I focus on practical steps? (Yes/No)"]
            st.session_state.followup_state = {"msg_idx": idx, "type": "needmore", "questions": questions, "answers": []}

    # if followup active for this message, render yes/no questions
    if st.session_state.get("followup_state") and st.session_state["followup_state"]["msg_idx"] == idx:
        fs = st.session_state["followup_state"]
        st.info(f"Feedback type: {fs['type']}. Please answer the following (Yes/No) to help improve the response.")
        # render questions sequentially; store answers list
        answers = fs.get("answers", [])
        qcount = len(fs["questions"])
        for qi, qtext in enumerate(fs["questions"]):
            # if not answered yet, show Yes/No buttons
            if qi < len(answers):
                st.markdown(f"**Q{qi+1}:** {qtext} — **Answer:** {answers[qi]}")
            else:
                coly, coln = st.columns([1,1])
                if coly.button("Yes", key=f"follow_yes_{idx}_{qi}"):
                    answers.append("Yes")
                    st.session_state.followup_state["answers"] = answers
                    st.experimental_rerun()
                if coln.button("No", key=f"follow_no_{idx}_{qi}"):
                    answers.append("No")
                    st.session_state.followup_state["answers"] = answers
                    st.experimental_rerun()
        # when all answered, show Submit to regenerate
        if len(answers) == qcount:
            if st.button("Submit feedback & regenerate", key=f"submit_feedback_{idx}"):
                # collect original user prompt (best-effort: previous user message)
                orig_user = ""
                for j in range(idx-1, -1, -1):
                    if st.session_state.chat_history[j].get("role") == "user":
                        orig_user = st.session_state.chat_history[j].get("content","")
                        break
                # build combined context with summaries and uploaded pdf
                combined_ctx = "\n\n".join([
                    "Medical summary:\n" + (st.session_state.medical_summary or ""),
                    "Sales summary:\n" + (st.session_state.sales_summary or ""),
                    "Uploaded PDF (truncated):\n" + (st.session_state.uploaded_pdf_text[:4000] if st.session_state.uploaded_pdf_text else "")
                ])
                # fuse feedback answers into a short note
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
                # update assistant message at idx
                st.session_state.chat_history[idx]["content"] = new_resp
                # update citations for the regenerated response
                new_cits = local_search_snippets(orig_user + " " + feedback_note, chunks, chunk_meta, top_n=3 if st.session_state.search_mode=="deep" else 1)
                st.session_state.chat_history[idx]["citations"] = new_cits
                st.session_state.chat_history[idx]["audio"] = generate_audio(new_resp)
                # clear followup state
                st.session_state.followup_state = None
                st.experimental_rerun()

st.markdown('</div>', unsafe_allow_html=True)

# ---------------- Prompt suggestions (collapsible) ----------------
def build_brand_suggestions(bk, persona, barrier_list, segment, specialty, objective):
    s=[]
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
    for i,s in enumerate(suggs):
        col = cols[i%3]
        if col.button(s, key=f"sugg_fill_{i}"):
            st.session_state.main_input = s

# ---------------- Chat input (form) ----------------
with st.form(key="chat_form", clear_on_submit=False):
    user_message = st.text_area("Ask or continue your sales dialogue...", value=st.session_state.get("main_input",""), key="chat_input_area", height=120)
    send = st.form_submit_button("Send")
    if send and user_message.strip():
        user_text = user_message.strip()
        st.session_state.chat_history.append({"role":"user","content":user_text})
        st.session_state.main_input = ""
        # Determine if user asked explicitly for a sales call / call flow
        ask_for_callflow = bool(re.search(r'\b(call flow|sales call|call plan|pre-call|call)\b', user_text, re.IGNORECASE))
        # Build call_flow_prompt if needed
        call_flow_prompt = ""
        if ask_for_callflow:
            steps = brand_data[st.session_state.selected_brand].get("call_flow", [])
            if steps:
                call_flow_prompt = "\n\n--- Sales Call Flow ---\n" + "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
        # Build combined context
        combined_ctx = "\n\n".join([
            "Medical summary:\n" + (st.session_state.medical_summary or ""),
            "Sales summary:\n" + (st.session_state.sales_summary or ""),
            "Uploaded PDF (truncated):\n" + (st.session_state.uploaded_pdf_text[:4000] if st.session_state.uploaded_pdf_text else "")
        ])
        # system prompt
        system_prompt = "You are a pharmaceutical sales assistant. Use the provided medical & sales summaries and follow the brand call flow when asked."
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
            ai_resp = f"(Fallback) {user_text}"

        # local citations
        snips = local_search_snippets(user_text, chunks, chunk_meta, top_n=3 if st.session_state.search_mode=="deep" else 1)
        audio_b64 = generate_audio(ai_resp)
        st.session_state.chat_history.append({"role":"assistant","content":ai_resp,"citations":snips,"audio":audio_b64})

# ---------------- PDF upload expander ----------------
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
    if st.session_state.pdf_summary:
        st.markdown(f"<div style='background:#E8F4FF;padding:10px;border-radius:8px;white-space:pre-line'>{escape(st.session_state.pdf_summary)}</div>", unsafe_allow_html=True)

# ---------------- Export ----------------
if st.session_state.chat_history:
    with st.expander("💾 Export / Download Chat", expanded=False):
        txt = "\n\n".join([f"{('You' if m['role']=='user' else 'AI')}: {m['content']}" for m in st.session_state.chat_history])
        st.download_button("⬇️ Download TXT", txt.encode("utf-8"), file_name=f"{st.session_state.selected_brand}_chat_{datetime.now().strftime('%Y%m%d')}.txt")
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
st.markdown('<div class="fixed-disclaimer">⚠️ This AI Sales Call Assistant is for informational purposes only. Verify all medical content with approved references and company guidance.</div>', unsafe_allow_html=True)
