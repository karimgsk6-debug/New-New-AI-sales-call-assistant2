# app.py - Full merged with exports and inline summaries

import streamlit as st
from PIL import Image
import re, os, tempfile, base64
from PyPDF2 import PdfReader
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

from groq import Groq
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ---------------------------- Session Defaults ----------------------------
for key, val in {
    "chat_history": [],
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "voice_pref": "Old Male",
    "pdf_summary_size": "Normal",
    "main_input": "",
    "selected_brand": "trelegy",
    "temperature": 0.6,
    "search_mode": "Shallow"
}.items():
    if key not in st.session_state:
        st.session_state[key] = val

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

def find_top_n_snippets(query, chunks, metadatas, top_n=3, search_mode="Shallow"):
    if not chunks: return []
    if search_mode=="Deep":
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks + [query])
            sims = linear_kernel(vectorizer.transform([query]), vectorizer.transform(chunks)).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            return [{"score": float(sims[i]), "text": chunks[i], "meta": metadatas[i]} for i in top_idxs if sims[i]>0]
        except:
            search_mode="Shallow"
    # Shallow mode: simple substring match
    out = []
    q = query.lower()
    for i, c in enumerate(chunks):
        if q in c.lower(): out.append({"score":1.0,"text":c,"meta":metadatas[i]})
        if len(out)>=top_n: break
    return out

def generate_audio(text):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        if ELEVENLABS_AVAILABLE:
            import elevenlabs
            elevenlabs.api_key = st.secrets.get("ELEVENLABS_API_KEY", "")
            voice_id = st.secrets.get("ELEVENLABS_VOICE_ID", "")
            audio_stream = elevenlabs.generate(text=text, voice=voice_id, stream=True)
            with open(tmp.name, "wb") as f:
                for ch in audio_stream: f.write(ch)
        else:
            tts = gTTS(text=text, lang="en", slow=False)
            tts.save(tmp.name)
        with open(tmp.name,"rb") as fh: return base64.b64encode(fh.read()).decode()
    except:
        return ""

# ---------------------------- Sidebar ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    st.session_state.selected_brand = st.selectbox("Brand", sorted(list(brand_data.keys())),
                                index=list(sorted(brand_data.keys())).index(st.session_state.get("selected_brand","trelegy")))
    sel_brand = brand_data[st.session_state.selected_brand]
    st.session_state.segment = st.selectbox("Segment", sel_brand["segments"])
    st.session_state.persona = st.selectbox("HCP Persona", sel_brand["personas"])
    st.session_state.barrier = st.multiselect("Doctor Barrier", sel_brand["barriers"])
    st.session_state.specialty = st.selectbox("Specialty", specialties)
    st.session_state.objective = st.selectbox("Objective", objectives)
    st.session_state.temperature = st.slider("Temperature", 0.1, 1.0, st.session_state.temperature, 0.05)
    st.session_state.search_mode = st.radio("Search Mode", ["Shallow","Deep"], horizontal=True)
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history = []

with st.sidebar.expander("📄 Upload PDF", expanded=False):
    uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
    st.session_state.pdf_summary_size = st.radio("Summary Size", ["Consisted","Normal","Detailed"], horizontal=True)

# ---------------------------- Load References & Sales ----------------------------
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

chunks, chunk_meta = build_corpus_for_paths([refs_folder,sales_folder], chunk_size_sentences=3)

# ---------------------------- PDF Processing ----------------------------
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
        st.error(f"Error reading PDF: {e}")

if st.session_state.pdf_summary:
    st.markdown(f"### PDF Summary\n```\n{st.session_state.pdf_summary}\n```")

# ---------------------------- Prompt Suggestions (auto-send) ----------------------------
def build_suggestions_for_brand():
    s = []
    s.append(f"Generate call flow for {st.session_state.persona} focused on {st.session_state.objective}.")
    if st.session_state.barrier: s.append(f"Handle objection: {', '.join(st.session_state.barrier[:2])}.")
    s.append(f"Summarize latest PDF and integrate into call script.")
    s.append(f"Highlight 3 sales points for segment {st.session_state.segment}.")
    return s

st.markdown("### Prompt Suggestions (Click to auto-send)")
suggestions = build_suggestions_for_brand()
for s in suggestions:
    if st.button(s, key=f"sugg_{s}"):
        # Auto-send the suggestion like a normal user message
        user_text = s
        st.session_state.chat_history.append({"role":"user","content":user_text})
        
        # Combine context
        combined_context = "\n".join([local_refs_text, sales_text, st.session_state.uploaded_pdf_text or ""])[:15000]
        system_prompt = "You are a pharmaceutical AI assistant. Tailor responses using references, sales modules, uploaded PDFs, and brand call flow."
        final_prompt = f"{user_text}\nBrand: {st.session_state.selected_brand}\nPersona: {st.session_state.persona}\nSegment: {st.session_state.segment}\nBarriers: {', '.join(st.session_state.barrier) if st.session_state.barrier else 'None'}\nContext (truncated):\n{combined_context[:5000]}"

        # Call AI
        assistant_text = "(AI not available)"
        try:
            if client:
                resp = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role":"system","content":system_prompt},
                              {"role":"user","content":final_prompt}],
                    temperature=st.session_state.temperature
                )
                assistant_text = resp.choices[0].message.content
        except Exception as e:
            assistant_text = f"(AI Error) {e}"

        top_snips = find_top_n_snippets(user_text, chunks, chunk_meta, top_n=3, search_mode=st.session_state.search_mode)
        audio_b64 = generate_audio(assistant_text)

        st.session_state.chat_history.append({
            "role":"assistant",
            "content":assistant_text,
            "audio": audio_b64,
            "citations": top_snips,
            "feedback_done": False
        })

# ---------------------------- Chat Input & Send ----------------------------
st.markdown("### Enter Message")
user_text = st.text_area("", value=st.session_state.main_input, key="chat_input_area", height=100)
if st.button("Send"):
    if user_text.strip():
        st.session_state.chat_history.append({"role":"user","content":user_text})
        st.session_state.main_input = ""
        
        # Combine context
        combined_context = "\n".join([local_refs_text, sales_text, st.session_state.uploaded_pdf_text or ""])[:15000]
        system_prompt = "You are a pharmaceutical AI assistant. Tailor responses using references, sales modules, uploaded PDFs, and brand call flow."
        final_prompt = f"{user_text}\nBrand: {st.session_state.selected_brand}\nPersona: {st.session_state.persona}\nSegment: {st.session_state.segment}\nBarriers: {', '.join(st.session_state.barrier) if st.session_state.barrier else 'None'}\nContext (truncated):\n{combined_context[:5000]}"

        assistant_text = "(AI not available)"
        try:
            if client:
                resp = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role":"system","content":system_prompt},
                              {"role":"user","content":final_prompt}],
                    temperature=st.session_state.temperature
                )
                assistant_text = resp.choices[0].message.content
        except Exception as e:
            assistant_text = f"(AI Error) {e}"

        top_snips = find_top_n_snippets(user_text, chunks, chunk_meta, top_n=3, search_mode=st.session_state.search_mode)
        audio_b64 = generate_audio(assistant_text)

        st.session_state.chat_history.append({
            "role":"assistant",
            "content":assistant_text,
            "audio": audio_b64,
            "citations": top_snips,
            "feedback_done": False
        })

# ---------------------------- Chat Display ----------------------------
st.markdown("---")
for idx, msg in enumerate(st.session_state.chat_history):
    if msg["role"]=="user":
        st.markdown(f"**You:** {msg['content']}")
    else:
        st.markdown(f"**AI:** {msg['content']}")
        # Inline citations
        for c in msg.get("citations", []):
            st.markdown(f"- Reference snippet from **{c['meta']['filename']}**: {c['text'][:200]}...")
        if msg.get("audio"):
            st.audio(base64.b64decode(msg["audio"]), format="audio/mp3")
        # Satisfaction feedback
        col1, col2 = st.columns([1,1])
        if col1.button("👍", key=f"like_{idx}"):
            st.session_state.chat_history[idx]["feedback_done"] = True
        if col2.button("👎", key=f"dislike_{idx}"):
            st.session_state.chat_history[idx]["feedback_done"] = True

# ---------------------------- Export Chat ----------------------------
if st.session_state.chat_history:
    st.markdown("---")
    st.markdown("### Export Chat")
    # Export as TXT
    chat_txt = ""
    for m in st.session_state.chat_history:
        role = "You" if m["role"]=="user" else "AI"
        chat_txt += f"{role}: {m['content']}\n"
        for c in m.get("citations", []):
            chat_txt += f"  - Ref: {c['text'][:200]}...\n"
    st.download_button("Download TXT", chat_txt, file_name="chat_export.txt")

    # Export as DOCX
    if DOCX_AVAILABLE:
        doc = Document()
        for m in st.session_state.chat_history:
            role = "You" if m["role"]=="user" else "AI"
            doc.add_paragraph(f"{role}: {m['content']}")
            for c in m.get("citations", []):
                doc.add_paragraph(f"  - Reference snippet from {c['meta']['filename']}: {c['text'][:200]}...", style="IntenseQuote")
        tmp_doc = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp_doc.name)
        st.download_button("Download DOCX", tmp_doc.name, file_name="chat_export.docx")
