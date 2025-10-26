# app.py - Full AI Sales Call Assistant with GROQ API, clickable suggestions, feedback, PDF upload, references, export, and background

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

try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False

try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except:
    ELEVENLABS_AVAILABLE = False

st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/background1.png"
GSK_LOGO_RAW = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/AURA1.png"

# ---------------------------- Session defaults ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "main_input" not in st.session_state:
    st.session_state.main_input = ""
if "selected_brand" not in st.session_state:
    st.session_state.selected_brand = "trelegy"
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.6
if "search_mode" not in st.session_state:
    st.session_state.search_mode = "deep"

# ---------------------------- CSS ----------------------------
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
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ---------------------------- Brands ----------------------------
brand_data = {
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Concerns about side effects", "Cost/coverage"],
        "references_path": "./references/trelegy/",
        "sales_path": "./Salesmodule/trelegy"
    },
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "references_path": "./references/shingrix/",
        "sales_path": "./Salesmodule/shingrix"
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited patient eligibility", "Access/reimbursement issues"],
        "references_path": "./references/jemperli/",
        "sales_path": "./Salesmodule/jemperli"
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
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except:
        return ""

def build_corpus_for_paths(folder_paths, chunk_size_sentences=3):
    chunks, metadatas = [], []
    for folder in folder_paths:
        if not os.path.exists(folder): continue
        files = [f for f in os.listdir(folder) if f.lower().endswith((".pdf",".txt"))]
        for fname in files:
            text = read_file_text(os.path.join(folder,fname))
            sents = re.split(r'(?<=[\.\?\!])\s+', text)
            for i in range(0, max(1,len(sents)), chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metadatas.append({"filename":fname,"folder":folder,"start":i})
    return chunks, metadatas

def find_top_n_snippets(query, chunks, metadatas, top_n=3):
    if not chunks: return []
    try:
        vectorizer = TfidfVectorizer(stop_words="english").fit(chunks+[query])
        chunk_vecs = vectorizer.transform(chunks)
        q_vec = vectorizer.transform([query])
        sims = linear_kernel(q_vec, chunk_vecs).flatten()
        top_idxs = sims.argsort()[::-1][:top_n]
        return [{"score":float(sims[i]),"text":chunks[i],"meta":metadatas[i]} for i in top_idxs if sims[i]>0]
    except:
        out=[]
        q=query.lower()
        for i,c in enumerate(chunks):
            if q in c.lower(): out.append({"score":1.0,"text":c,"meta":metadatas[i]})
            if len(out)>=top_n: break
        return out

def generate_audio(text):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        tts_text = re.sub(r'[,*]{1,}','',text)
        tts = gTTS(text=tts_text, lang="en", slow=False)
        tts.save(tmp.name)
        with open(tmp.name,"rb") as fh: return base64.b64encode(fh.read()).decode()
    except: return ""

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
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"], key="sidebar_tone")
    st.session_state.temperature = st.slider("Temperature", 0.0,1.0,st.session_state.temperature,0.05)
    st.session_state.search_mode = st.selectbox("Search Mode",["deep","shallow"],index=0 if st.session_state.search_mode=="deep" else 1)
    selected_language = st.radio("Language", ["English","Arabic"], horizontal=True, key="sidebar_language")
    if st.button("🗑️ Clear Chat"): st.session_state.chat_history=[]

with st.sidebar.expander("Add External Reference URLs", expanded=False):
    external_text = "\n".join(st.text_area("Enter URLs (one per line)").splitlines())

with st.sidebar.expander("Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT","DOCX"], horizontal=True)
# ---------------------------- Title / Header ----------------------------
st.markdown(f"""
<div class="title-box">
  <img src="{GSK_LOGO_RAW}" class="left-logo">
  <h1>💡 AI Sales Call Assistant — {brand_data[st.session_state.selected_brand]['display']}</h1>
  <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# ---------------------------- Load local references and sales module ----------------------------
refs_folder = sel_brand["references_path"]
sales_folder = sel_brand["sales_path"]
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

corpus_folders = [refs_folder, sales_folder]
chunks, chunk_meta = build_corpus_for_paths(corpus_folders)

# ---------------------------- PDF Upload ----------------------------
with st.expander("📄 Upload Custom PDF for AI Context", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
    pdf_size_option = st.radio("PDF Summary Size", ["Consisted","Normal","Detailed"], horizontal=True)
    if uploaded_pdf:
        reader = PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text
        bullets_count = {"Consisted":5,"Normal":10,"Detailed":20}.get(pdf_size_option,10)
        if client:
            try:
                summ_prompt = f"Summarize into {bullets_count} bullet points:\n{full_text[:12000]}"
                summ = client.chat.completions.create(model="llama-3.3-70b-versatile",
                                                     messages=[{"role":"user","content":summ_prompt}],
                                                     temperature=0.4)
                st.session_state.pdf_summary = summ.choices[0].message.content
            except:
                sts = re.findall(r'([A-Z][^.]{20,200})', full_text)
                st.session_state.pdf_summary = "\n".join(sts[:bullets_count])
        else:
            sts = re.findall(r'([A-Z][^.]{20,200})', full_text)
            st.session_state.pdf_summary = "\n".join(sts[:bullets_count])
    if st.session_state.pdf_summary:
        st.markdown(f"<div style='background:#E6F0FF;padding:12px;border-radius:8px;white-space:pre-line'>{escape(st.session_state.pdf_summary)}</div>", unsafe_allow_html=True)

# ---------------------------- Chat Display ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for idx,msg in enumerate(st.session_state.chat_history):
    role = msg.get("role")
    st.markdown(f'<div class="chat-bubble-{"user" if role=="user" else "ai"}">{("🧑 You" if role=="user" else "🤖 AI")}: {escape(msg.get("content",""))}</div>', unsafe_allow_html=True)
    
    if role=="assistant":
        # Citations
        if msg.get("citations"):
            for c in msg["citations"]:
                fname = c["meta"]["filename"]
                blob_url = f"{refs_folder}/{fname}" if fname in local_ref_files else f"{sales_folder}/{fname}"
                st.markdown(f'<div class="citation-box"><b>Excerpt from {escape(fname)}:</b><br>{escape(c["text"][:800])}...<br><a href="{blob_url}" target="_blank">View full file</a></div>', unsafe_allow_html=True)
        # Audio
        if msg.get("audio"):
            st.audio(base64.b64decode(msg["audio"]), format="audio/mp3")
        # Satisfaction feedback
        cols = st.columns(4)
        feedback_options = ["👍 Like","👎 Dislike","😐 Neutral","🔄 Need More"]
        for i,opt in enumerate(feedback_options):
            if cols[i].button(opt, key=f"feedback_{idx}_{i}"):
                st.session_state.chat_history[idx]["feedback"] = opt
                # Dislike interactive follow-up
                if opt=="👎 Dislike":
                    followup = st.text_area("What is missing or which part to focus on?", key=f"followup_{idx}")
                    if followup:
                        # regenerate AI based on followup
                        user_text = st.session_state.chat_history[idx-1]["content"] if idx>0 else ""
                        combined_context = "\n".join([local_refs_text, sales_text, st.session_state.uploaded_pdf_text])[:15000]
                        prompt = f"{user_text}\nFollow-up feedback: {followup}\nContext (truncated):\n{combined_context[:5000]}"
                        if client:
                            try:
                                resp = client.chat.completions.create(
                                    model="llama-3.3-70b-versatile",
                                    messages=[{"role":"user","content":prompt}],
                                    temperature=st.session_state.temperature
                                )
                                regenerated = resp.choices[0].message.content
                                st.session_state.chat_history[idx]["content"] = regenerated
                                st.experimental_rerun()
                            except:
                                pass
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Prompt Suggestions ----------------------------
with st.expander("Prompt Suggestions (click to autofill)", expanded=False):
    suggs = build_suggestions_for_brand(st.session_state.selected_brand, persona, barrier, segment, specialty, objective)
    st.markdown('<div class="suggestions-inline">', unsafe_allow_html=True)
    cols = st.columns([1,1,1])
    for i,s in enumerate(suggs):
        col = cols[i%3]
        if col.button(s, key=f"sugg_{i}"):
            st.session_state.main_input = s
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Chat Input ----------------------------
with st.form(key="chat_form", clear_on_submit=False):
    message = st.text_area("Message (editable)", value=st.session_state.get("main_input",""), key="chat_input_area", height=110)
    send = st.form_submit_button("Send")
    if send and message.strip():
        user_text = message.strip()
        st.session_state.chat_history.append({"role":"user","content":user_text})
        st.session_state.main_input = ""
        # Build combined context
        combined_context = "\n".join([local_refs_text, sales_text, st.session_state.uploaded_pdf_text])[:15000]
        system_prompt = "You are a pharmaceutical AI assistant. Tailor responses using references, sales modules, uploaded PDFs."
        final_prompt = f"{user_text}\nContext:\n{combined_context[:5000]}"
        assistant_text = ""
        if client:
            try:
                resp = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role":"system","content":system_prompt},{"role":"user","content":final_prompt}],
                    temperature=st.session_state.temperature
                )
                assistant_text = resp.choices[0].message.content
            except:
                assistant_text = "(AI Error)"
        else:
            assistant_text = f"(Fallback) {user_text}"
        # Inline citation
        top_snips = find_top_n_snippets(user_text, chunks, chunk_meta)
        audio_b64 = generate_audio(assistant_text)
        st.session_state.chat_history.append({
            "role":"assistant",
            "content":assistant_text,
            "audio": audio_b64,
            "citations": top_snips
        })

# ---------------------------- Export / Download ----------------------------
if st.session_state.chat_history:
    with st.expander("💾 Export / Download Chat", expanded=False):
        text_export = "\n\n".join([f"{e['role'].capitalize()}: {e['content']}" for e in st.session_state.chat_history])
        st.download_button("⬇️ Download TXT", text_export.encode(), file_name=f"{st.session_state.selected_brand}_chat.txt")
        if DOCX_AVAILABLE:
            if st.button("Export as DOCX"):
                doc = Document()
                doc.add_heading("AI Sales Call Assistant Export",0)
                doc.add_paragraph(f"Brand: {st.session_state.selected_brand.upper()} | Date: {datetime.now().strftime('%Y-%m-%d')}")
                for e in st.session_state.chat_history:
                    doc.add_paragraph(f"{e['role'].capitalize()}: {e['content']}")
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
                doc.save(tmp.name)
                with open(tmp.name,"rb") as fh:
                    st.download_button("⬇️ Download DOCX", fh.read(), file_name=f"{st.session_state.selected_brand}_chat.docx")

# ---------------------------- Disclaimer ----------------------------
st.markdown('<div class="fixed-disclaimer">⚠️ This AI tool is for informational purposes only. Verify all medical content with approved references before use.</div>', unsafe_allow_html=True)
