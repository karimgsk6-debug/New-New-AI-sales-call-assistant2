# app.py - Final merged app with GROQ API, interactive feedback, inline citations, TTS, and exports

import streamlit as st
from PIL import Image
import re, os, tempfile, base64, math
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
except Exception:
    DOCX_AVAILABLE = False

# ElevenLabs fallback flag
try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except Exception:
    ELEVENLABS_AVAILABLE = False

# ---------------------------- Page config ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ---------------------------- Repo info for links ----------------------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_BLOB_BASE = f"https://github.com/{REPO_USER}/{REPO_NAME}/blob/{COMMIT}/.devcontainer"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = REPO_RAW_BASE + "/.devcontainer/background1.png"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# ---------------------------- Session defaults ----------------------------
for key, val in {
    "chat_history": [],
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "voice_pref": "Old Male",
    "pdf_summary_size": "Normal",
    "main_input": "",
    "selected_brand": "trelegy"
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ---------------------------- CSS / layout ----------------------------
CSS = f"""
<style>
.stApp {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-attachment: fixed;
  background-position: center;
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
.title-box img.left-logo {{ position:absolute; left:16px; width:130px; height:auto; }}
.title-box img.right-logo {{ position:absolute; right:16px; width:130px; height:auto; }}
.title-box h1 {{ margin:0; font-size:22px; }}
.chat-container {{
  max-height: 56vh;
  overflow-y:auto;
  padding: 14px;
  border-radius: 10px;
  background: rgba(255,255,255,0.94);
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
  max-height:200px;
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
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ API ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = None
if GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except:
        client = None

# ---------------------------- Brand Data ----------------------------
brand_data = {
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Concerns about side effects", "Cost/coverage"],
        "references_path": "references/trelegy/",
        "sales_path": "Salesmodule/trelegy"
    },
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "references_path": "references/shingrix/",
        "sales_path": "Salesmodule/shingrix"
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited patient eligibility", "Access/reimbursement issues"],
        "references_path": "references/jemperli/",
        "sales_path": "Salesmodule/jemperli"
    }
}
specialties = ["GP", "Pulmonologist", "Internal medicine", "Oncologist"]
objectives = ["Awareness", "Adoption", "Retention"]

# ---------------------------- Helper Functions ----------------------------
def read_file_text(path):
    try:
        if path.lower().endswith(".pdf"):
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except Exception as e:
        return f"[Error reading {os.path.basename(path)}: {e}]"

def build_corpus_for_paths(folder_paths, chunk_size_sentences=3):
    chunks, metadatas = [], []
    for folder in folder_paths:
        if not folder or not os.path.exists(folder): continue
        for fname in os.listdir(folder):
            if not fname.lower().endswith((".pdf", ".txt")): continue
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
        sims = linear_kernel(vectorizer.transform([query]), vectorizer.transform(chunks)).flatten()
        top_idxs = sims.argsort()[::-1][:top_n]
        return [{"score": float(sims[i]), "text": chunks[i], "meta": metadatas[i]} for i in top_idxs if sims[i]>0]
    except:
        out = []
        q = query.lower()
        for i, c in enumerate(chunks):
            if q in c.lower(): out.append({"score":1.0,"text":c,"meta":metadatas[i]})
            if len(out)>=top_n: break
        return out

# ---------------------------- Audio Generation ----------------------------
ELEVENLABS_API_KEY = st.secrets.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = st.secrets.get("ELEVENLABS_VOICE_ID", "")
if ELEVENLABS_AVAILABLE and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
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
        with open(tmp.name,"rb") as fh: return base64.b64encode(fh.read()).decode()
    except:
        return ""

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
    response_length = st.selectbox("Response Length", ["Short", "Medium", "Long"], key="sidebar_length")
    selected_language = st.radio("Language", ["English","Arabic"], horizontal=True, key="sidebar_language")
    if st.button("🗑️ Clear Chat", key="sidebar_clear"):
        st.session_state.chat_history = []

with st.sidebar.expander("🌐 Add External Reference URLs", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT", "DOCX"], horizontal=True)

# ---------------------------- Title Box ----------------------------
st.markdown(f"""
<div class="title-box">
  <img src="{GSK_LOGO_RAW}" class="left-logo">
  <h1>💡 AI Sales Call Assistant — {brand_data[st.session_state.selected_brand]['display']}</h1>
  <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# ---------------------------- Load Local References + Sales Modules ----------------------------
refs_folder = brand_data[st.session_state.selected_brand]["references_path"]
sales_folder = brand_data[st.session_state.selected_brand]["sales_path"]

local_refs_text, local_ref_files = "", []
sales_text, sales_files = "", []
if os.path.exists(refs_folder):
    for f in os.listdir(refs_folder):
        if f.lower().endswith((".pdf",".txt")):
            local_ref_files.append(f)
            local_refs_text += read_file_text(os.path.join(refs_folder,f)) + "\n"

if os.path.exists(sales_folder):
    for f in os.listdir(sales_folder):
        if f.lower().endswith((".pdf",".txt")):
            sales_files.append(f)
            sales_text += read_file_text(os.path.join(sales_folder,f)) + "\n"

chunks, chunk_meta = build_corpus_for_paths([refs_folder,sales_folder], chunk_size_sentences=3)

# ---------------------------- PDF Upload ----------------------------
with st.expander("📄 Upload Custom PDF for AI Context", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
    st.session_state.pdf_summary_size = st.radio("PDF Summary Size", ["Consisted","Normal","Detailed"], horizontal=True, key="pdf_size_widget")
    if uploaded_pdf:
        try:
            reader = PdfReader(uploaded_pdf)
            full_text = "".join([p.extract_text() or "" for p in reader.pages])
            st.session_state.uploaded_pdf_text = full_text
            bullets_count = {"Consisted":5,"Normal":10,"Detailed":20}.get(st.session_state.pdf_summary_size,10)
            if client:
                summ_prompt = f"Summarize into {bullets_count} bullet points:\n{full_text[:12000]}"
                summ = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                                     messages=[{"role":"user","content":summ_prompt}], temperature=0.4)
                st.session_state.pdf_summary = summ.choices[0].message.content
            else:
                sts = re.findall(r'([A-Z][^.]{20,200})', full_text)
                st.session_state.pdf_summary = "\n".join(sts[:bullets_count])
        except Exception as e:
            st.error(f"Error reading uploaded PDF: {e}")
    if st.session_state.pdf_summary:
        st.markdown(f"<div style='background:#E6F0FF;padding:12px;border-radius:8px;white-space:pre-line'>{escape(st.session_state.pdf_summary)}</div>", unsafe_allow_html=True)

# ---------------------------- Chat Display ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for msg in st.session_state.chat_history:
    if msg.get("role")=="user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)
        for c in msg.get("citations",[]):
            fname = c["meta"]["filename"]
            blob_url = f"{REPO_BLOB_BASE}/references/{st.session_state.selected_brand}/{fname}" if fname in local_ref_files else f"{REPO_BLOB_BASE}/SalesModule/{st.session_state.selected_brand}/{fname}"
            st.markdown(f'<div class="citation-box"><b>Excerpt from {escape(fname)}:</b><br>{escape(c["text"][:800])}...<br><a href="{blob_url}" target="_blank">View full file</a></div>', unsafe_allow_html=True)
        if msg.get("audio"):
            try: st.audio(base64.b64decode(msg["audio"]), format="audio/mp3")
            except: pass
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Prompt Suggestions ----------------------------
def build_suggestions_for_brand(brand_key, persona, barrier_list, segment, specialty, objective):
    s = []
    s.append(f"Generate call flow for {persona} focused on {objective}.")
    if barrier_list: s.append(f"Handle objection: {', '.join(barrier_list[:2])} for {persona}.")
    s.append(f"Summarize latest PDF and integrate into call script.")
    s.append(f"Highlight 3 sales points for segment {segment}.")
    return s
suggestions = build_suggestions_for_brand(st.session_state.selected_brand, persona, barrier, segment, specialty, objective)
st.markdown('<div class="suggestions-inline">', unsafe_allow_html=True)
for s in suggestions:
    st.markdown(f'<span class="suggestion-pill" onclick="navigator.clipboard.writeText(`{s}`)">{s}</span>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Chat Input + Send Logic ----------------------------
with st.form(key="chat_form", clear_on_submit=False):
    message = st.text_area("Message (editable)", value=st.session_state.get("main_input",""), key="chat_input_area", height=110)
    send = st.form_submit_button("Send")
    if send:
        user_text = message.strip()
        if user_text:
            st.session_state.chat_history.append({"role":"user","content":user_text})
            st.session_state.main_input = ""

            combined_context = "\n".join([
                local_refs_text or "",
                sales_text or "",
                "\n".join(external_urls) if external_urls else "",
                st.session_state.uploaded_pdf_text or ""
            ])[:15000]

            system_prompt = "You are a pharmaceutical AI assistant. Tailor responses using references, sales modules, uploaded PDFs, and follow brand call flow."
            final_prompt = f"{user_text}\nBrand: {st.session_state.selected_brand}\nPersona: {persona}\nSegment: {segment}\nSpecialty: {specialty}\nObjective: {objective}\nBarriers: {', '.join(barrier) if barrier else 'None'}\n\nContext (truncated):\n{combined_context[:5000]}"

            assistant_text = "(AI not available)"
            try:
                if client:
                    resp = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role":"system","content":system_prompt},
                                  {"role":"user","content":final_prompt}],
                        temperature=0.62
                    )
                    assistant_text = resp.choices[0].message.content
            except Exception as e:
                assistant_text = f"(AI Error) {e}"

            top_snips = find_top_n_snippets(user_text, chunks, chunk_meta, top_n=3)
            audio_b64 = generate_audio(assistant_text)

            st.session_state.chat_history.append({
                "role":"assistant",
                "content":assistant_text,
                "audio": audio_b64,
                "citations": top_snips,
                "feedback_done": False
            })

# ---------------------------- Interactive Feedback (👍👎) ----------------------------
for idx, msg in enumerate(st.session_state.chat_history):
    if msg.get("role")=="assistant" and not msg.get("feedback_done"):
        col1, col2 = st.columns([1,1])
        if col1.button("👍", key=f"like_{idx}"):
            st.session_state.chat_history[idx]["feedback_done"] = True
        if col2.button("👎", key=f"dislike_{idx}"):
            st.session_state.chat_history[idx]["feedback_done"] = True
            st.warning("You disliked the response. Please clarify to regenerate AI answer:")
            clar = st.text_input(f"Clarify your request for message {idx+1}", key=f"clar_input_{idx}")
            if clar:
                clar_prompt = f"Original user query: {user_text}\nClarification: {clar}\n\nRegenerate AI response using the same system prompt."
                try:
                    resp = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role":"system","content":system_prompt},
                                  {"role":"user","content":clar_prompt}],
                        temperature=0.62
                    )
                    new_text = resp.choices[0].message.content
                    new_audio = generate_audio(new_text)
                    st.session_state.chat_history.append({
                        "role":"assistant",
                        "content":new_text,
                        "audio":new_audio,
                        "citations": find_top_n_snippets(clar, chunks, chunk_meta, top_n=3),
                        "feedback_done": False
                    })
                    st.success("AI response regenerated with your clarification.")
                except Exception as e:
                    st.error(f"Failed to regenerate AI response: {e}")

# ---------------------------- Fixed Footer ----------------------------
st.markdown('<div class="fixed-disclaimer">💡 AI responses are suggestions and should be cross-checked with official brand guidelines.</div>', unsafe_allow_html=True)
