# app.py - AI Sales Call Assistant (Full merged version with GROQ API, feedback, PDF, refs, sales modules)

import streamlit as st
from PIL import Image
import re, os, tempfile, base64
from io import BytesIO
from datetime import datetime
from groq import Groq
from PyPDF2 import PdfReader
from html import escape
from gtts import gTTS
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

# Optional DOCX export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False

# ElevenLabs fallback
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except:
    ELEVENLABS_AVAILABLE = False

# ---------------------------- Page config ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ---------------------------- Session defaults ----------------------------
for key, default in {
    "chat_history": [], "uploaded_pdf_text": "", "pdf_summary": "",
    "voice_pref": "Old Male", "pdf_summary_size": "Normal",
    "main_input": "", "selected_brand": "trelegy",
    "followup_active": False, "followup_prompt": "", "temperature": 0.62,
    "search_mode": "deep"
}.items():
    st.session_state.setdefault(key, default)

# ---------------------------- Repo info ----------------------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_BLOB_BASE = f"https://github.com/{REPO_USER}/{REPO_NAME}/blob/{COMMIT}/.devcontainer"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = REPO_RAW_BASE + "/.devcontainer/background1.png"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# ---------------------------- GROQ client ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = None
if GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except:
        client = None

# ---------------------------- Brands ----------------------------
brand_data = {
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Concerns about side effects", "Cost/coverage"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy"
    },
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix"
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited patient eligibility", "Access/reimbursement issues"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli"
    }
}
specialties = ["GP", "Pulmonologist", "Internal medicine", "Oncologist"]
objectives = ["Awareness", "Adoption", "Retention"]

# ---------------------------- Helper functions ----------------------------
def read_file_text(path):
    try:
        if path.lower().endswith(".pdf"):
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except Exception as e:
        return f"[Error reading {os.path.basename(path)}: {e}]"

def build_corpus_for_paths(folder_paths, chunk_size_sentences=3):
    chunks, metadatas = [], []
    for folder in folder_paths:
        if not folder or not os.path.exists(folder): continue
        files = [f for f in os.listdir(folder) if f.lower().endswith((".pdf", ".txt"))]
        for fname in files:
            p = os.path.join(folder, fname)
            text = read_file_text(p)
            sents = re.split(r'(?<=[\.\?\!])\s+', text)
            for i in range(0, max(1, len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metadatas.append({"filename": fname, "folder": folder, "start": i})
    return chunks, metadatas

def find_top_n_snippets(query, chunks, metadatas, top_n=3):
    if not chunks: return []
    try:
        vectorizer = TfidfVectorizer(stop_words="english").fit(chunks + [query])
        chunk_vecs = vectorizer.transform(chunks)
        q_vec = vectorizer.transform([query])
        sims = linear_kernel(q_vec, chunk_vecs).flatten()
        top_idxs = sims.argsort()[::-1][:top_n]
        results = []
        for idx in top_idxs:
            if sims[idx] <= 0: continue
            results.append({"score": float(sims[idx]), "text": chunks[idx], "meta": metadatas[idx]})
        return results
    except:
        out = []
        q = query.lower()
        for i, c in enumerate(chunks):
            if q in c.lower():
                out.append({"score": 1.0, "text": c, "meta": metadatas[i]})
                if len(out) >= top_n: break
        return out

# ---------------------------- Audio ----------------------------
ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY:
    elevenlabs.api_key = ELEVENLABS_API_KEY

def generate_audio(text):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        tts_text = re.sub(r'[,*]{1,}', '', text)
        if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
            audio_stream = elevenlabs.generate(text=tts_text, voice=ELEVENLABS_VOICE_ID, stream=True)
            with open(tmp.name, "wb") as f:
                for ch in audio_stream: f.write(ch)
        else:
            tts = gTTS(text=tts_text, lang="en", slow=False)
            tts.save(tmp.name)
        with open(tmp.name, "rb") as fh:
            return base64.b64encode(fh.read()).decode()
    except: return ""

# ---------------------------- Sidebar ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    sel_brand_key = st.selectbox("Brand", sorted(list(brand_data.keys())),
                                 index=list(sorted(brand_data.keys())).index(st.session_state.get("selected_brand","trelegy")))
    st.session_state.selected_brand = sel_brand_key
    sel_brand = brand_data[sel_brand_key]
    segment = st.selectbox("Segment", sel_brand["segments"], key="sidebar_segment")
    persona = st.selectbox("HCP Persona", sel_brand["personas"], key="sidebar_persona")
    barrier = st.multiselect("Doctor Barrier", sel_brand["barriers"], key="sidebar_barrier")
    specialty = st.selectbox("Specialty", specialties, key="sidebar_specialty")
    objective = st.selectbox("Objective", objectives, key="sidebar_objective")
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"], key="sidebar_tone")
    st.session_state.temperature = st.slider("Temperature", 0.1, 1.0, st.session_state.temperature, 0.05)
    st.session_state.search_mode = st.selectbox("Search Mode", ["deep","shallow"], index=0 if st.session_state.search_mode=="deep" else 1)
    selected_language = st.radio("Language", ["English", "Arabic"], horizontal=True, key="sidebar_language")
    if st.button("🗑️ Clear Chat", key="sidebar_clear"): st.session_state.chat_history = []

with st.sidebar.expander("🌐 Add External Reference URLs", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT", "DOCX"], horizontal=True)

# ---------------------------- Title ----------------------------
st.markdown(f"""
<div class="title-box">
  <img src="{GSK_LOGO_RAW}" class="left-logo">
  <h1>💡 AI Sales Call Assistant — {brand_data[st.session_state.selected_brand]['display']}</h1>
  <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# ---------------------------- Load local files ----------------------------
refs_folder = sel_brand["references_path"]
sales_folder = sel_brand["sales_path"]
local_refs_text, local_ref_files = "", []
sales_text, sales_files = "", []

for folder, txt_var, files_var in [(refs_folder, local_refs_text, local_ref_files),
                                  (sales_folder, sales_text, sales_files)]:
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.lower().endswith((".pdf", ".txt")):
                files_var.append(f)
                try:
                    txt_var += read_file_text(os.path.join(folder, f)) + "\n"
                except: pass

# Build TF-IDF chunks
corpus_folders = [f for f in [refs_folder, sales_folder] if f]
chunks, chunk_meta = build_corpus_for_paths(corpus_folders, chunk_size_sentences=3)

# ---------------------------- PDF Upload ----------------------------
with st.expander("📄 Upload Custom PDF for AI Context", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
    st.session_state.pdf_summary_size = st.radio("PDF Summary Size", ["Consisted", "Normal", "Detailed"],
                                                horizontal=True, key="pdf_size_widget")
    if uploaded_pdf:
        try:
            reader = PdfReader(uploaded_pdf)
            full_text = "".join([p.extract_text() or "" for p in reader.pages])
            st.session_state.uploaded_pdf_text = full_text
            st.success(f"Loaded {len(full_text)} characters from uploaded PDF.")
            bullets_count = {"Consisted":5,"Normal":10,"Detailed":20}.get(st.session_state.pdf_summary_size,10)
            if client:
                try:
                    summ_prompt = f"Summarize into {bullets_count} bullet points:\n{full_text[:12000]}"
                    summ = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                                         messages=[{"role":"user","content":summ_prompt}], temperature=0.4)
                    st.session_state.pdf_summary = summ.choices[0].message.content
                except:
                    sts = re.findall(r'([A-Z][^.]{20,200})', full_text)
                    st.session_state.pdf_summary = "\n".join(sts[:bullets_count])
            else:
                sts = re.findall(r'([A-Z][^.]{20,200})', full_text)
                st.session_state.pdf_summary = "\n".join(sts[:bullets_count])
        except Exception as e: st.error(f"Error reading uploaded PDF: {e}")
    if st.session_state.pdf_summary:
        st.markdown(f"<div style='background:#E6F0FF;padding:12px;border-radius:8px;white-space:pre-line'>{escape(st.session_state.pdf_summary)}</div>", unsafe_allow_html=True)

# ---------------------------- Chat Display ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for i, msg in enumerate(st.session_state.chat_history):
    if msg.get("role") == "user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)
        if msg.get("citations"):
            for c in msg["citations"]:
                fname = c["meta"]["filename"]
                blob_url = f"{REPO_BLOB_BASE}/references/{st.session_state.selected_brand}/{fname}" if fname in local_ref_files else f"{REPO_BLOB_BASE}/SalesModule/{st.session_state.selected_brand}/{fname}"
                st.markdown(f'<div class="citation-box"><b>Excerpt from {escape(fname)}:</b><br>{escape(c["text"][:800])}...<br><a href="{blob_url}" target="_blank">View full file</a></div>', unsafe_allow_html=True)
        if msg.get("audio"):
            try: st.audio(base64.b64decode(msg["audio"]), format="audio/mp3")
            except: pass
        # ---------------------------- Satisfaction ----------------------------
        col1, col2, col3, col4 = st.columns(4)
        if col1.button("👍", key=f"like_{i}"): st.success("Thanks for your feedback!")
        if col2.button("👎", key=f"dislike_{i}"):
            st.session_state.followup_active = True
            st.session_state.followup_prompt = "What exactly is missing or needs improvement?"
        if col3.button("😐", key=f"neutral_{i}"): st.info("Thanks for your feedback!")
        if col4.button("❗ Need more", key=f"needmore_{i}"):
            st.session_state.followup_active = True
            st.session_state.followup_prompt = "Which part should I focus on to improve the response?"
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Prompt Suggestions ----------------------------
def build_suggestions_for_brand(brand_key, persona, barrier_list, segment, specialty, objective):
    s = []
    s.append(f"Generate call flow for {persona} focused on {objective}.")
    if barrier_list:
        s.append(f"Handle objection: {', '.join(barrier_list[:2])} for {persona}.")
    else:
        s.append(f"Identify common objections for {persona}.")
    s.append(f"Summarize HCP persona insights for {persona}.")
    s.append(f"Key talking points for {brand_data[brand_key]['display']} in {segment}.")
    s.append(f"Draft a short adoption message for {brand_data[brand_key]['display']} to a {specialty}.")
    return s

with st.expander("Prompt Suggestions (click to autofill)", expanded=False):
    suggs = build_suggestions_for_brand(st.session_state.selected_brand, persona, barrier, segment, specialty, objective)
    cols = st.columns([1,1,1])
    for i, s in enumerate(suggs):
        col = cols[i % 3]
        if col.button(s, key=f"sugg_{i}"): st.session_state.main_input = s

# ---------------------------- Chat Input Form ----------------------------
with st.form(key="chat_form", clear_on_submit=False):
    temp_input = st.text_area("Type your message here", value=st.session_state.main_input, key="chat_input_area", height=110)
    send = st.form_submit_button("Send")
    if send:
        user_text = temp_input.strip()
        if user_text:
            # If follow-up active, prepend prompt
            if st.session_state.followup_active:
                user_text = f"{st.session_state.followup_prompt}\nUser answer: {user_text}"
                st.session_state.followup_active = False
                st.session_state.followup_prompt = ""
            st.session_state.chat_history.append({"role":"user","content":user_text})
            # Generate AI response
            resp_content, citations, audio_b64 = "", [], ""
            prompt_parts = [user_text]
            if st.session_state.uploaded_pdf_text:
                prompt_parts.append(st.session_state.uploaded_pdf_text[:8000])
            if chunks:
                if st.session_state.search_mode=="deep":
                    top_snippets = find_top_n_snippets(user_text, chunks, chunk_meta, top_n=3)
                    citations = top_snippets
                    for t in top_snippets: prompt_parts.append(t["text"])
                else:
                    top_snippets = find_top_n_snippets(user_text, chunks, chunk_meta, top_n=1)
                    citations = top_snippets
                    for t in top_snippets: prompt_parts.append(t["text"])
            full_prompt = "\n".join(prompt_parts)
            if client:
                try:
                    ai_resp = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role":"user","content":full_prompt}],
                        temperature=st.session_state.temperature
                    )
                    resp_content = ai_resp.choices[0].message.content
                except:
                    resp_content = "AI service unavailable. Please try later."
            else:
                resp_content = "AI client not configured."
            audio_b64 = generate_audio(resp_content)
            st.session_state.chat_history.append({"role":"ai","content":resp_content,"citations":citations,"audio":audio_b64})
            st.session_state["main_input"] = ""  # safe clear

# ---------------------------- Disclaimer ----------------------------
st.markdown("""
<div style="background:#f5f5f5;padding:10px;border-radius:8px;color:#555;font-size:13px;margin-top:15px">
⚠️ Disclaimer: This AI-generated content is for informational purposes only. Verify all references and medical content before use.
</div>
""", unsafe_allow_html=True)

# ---------------------------- Custom CSS ----------------------------
st.markdown("""
<style>
body {background-image: url('""" + BACKGROUND_URL + """'); background-size: cover;}
.chat-container {margin-top: 10px;}
.chat-bubble-user {background:#DCF8C6;padding:10px;border-radius:10px;margin:5px; text-align:right;}
.chat-bubble-ai {background:#F1F0F0;padding:10px;border-radius:10px;margin:5px; text-align:left;}
.citation-box {background:#FFF8DC;padding:8px;margin:5px;border-left:3px solid #FFA500;}
.left-logo {height:60px; float:left;}
.right-logo {height:60px; float:right;}
.title-box {display:flex; align-items:center; justify-content:center; margin-bottom:20px;}
</style>
""", unsafe_allow_html=True)
