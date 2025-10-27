# app.py - Full AI Sales Call Assistant with GROQ integration
import streamlit as st
import os, re, tempfile, base64
from datetime import datetime
from html import escape

# -------------------------
# Optional imports
# -------------------------
try:
    from groq import Groq
except:
    Groq = None

try:
    from PyPDF2 import PdfReader
except:
    PdfReader = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except:
    SKLEARN_AVAILABLE = False

try:
    from gtts import gTTS
except:
    gTTS = None

try:
    from docx import Document
    DOCX_AVAILABLE = False
except:
    DOCX_AVAILABLE = False

# -------------------------
# Groq setup
# -------------------------
GROQ_API_KEY = "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"
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY and Groq else None

# -------------------------
# Page setup
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# -------------------------
# Session defaults
# -------------------------
defaults = {
    "chat_history": [],
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.62,
    "search_mode": "deep",
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "followup_state": {},
}
for k,v in defaults.items():
    st.session_state.setdefault(k,v)

# -------------------------
# Brand information
# -------------------------
brand_data = {
    "shingrix": {
        "display":"Shingrix",
        "references_path":".devcontainer/references/shingrix/",
        "call_flow":["Pre-call planning","Prepare","Engage","Create Opportunities","Influence","Impact GSO","Post-call analysis"]
    },
    "jemperli":{
        "display":"Jemperli",
        "references_path":".devcontainer/references/jemperli/",
        "call_flow":["COCO","Anchor","Engage","Close"]
    },
    "trelegy":{
        "display":"Trelegy",
        "references_path":".devcontainer/references/trelegy/",
        "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"]
    }
}

# -------------------------
# Helpers
# -------------------------
def read_file_text(path):
    if not os.path.exists(path): return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path,"r",encoding="utf-8",errors="ignore") as f:
                return f.read()
    except:
        return ""

def build_corpus(folder):
    chunks = []
    if not os.path.exists(folder): return chunks
    files = [f for f in os.listdir(folder) if f.lower().endswith((".pdf",".txt"))]
    for f in files:
        text = read_file_text(os.path.join(folder,f))
        sents = re.split(r'(?<=[\.\?\!])\s+', text)
        for i in range(0,len(sents),3):
            chunk = " ".join(sents[i:i+3]).strip()
            if chunk: chunks.append(chunk)
    return chunks

def search_local(query, corpus, top_n=3):
    if not corpus or not SKLEARN_AVAILABLE: return []
    vec = TfidfVectorizer(stop_words="english").fit(corpus+[query])
    corpus_vec = vec.transform(corpus)
    q_vec = vec.transform([query])
    sims = linear_kernel(q_vec, corpus_vec).flatten()
    top_idxs = sims.argsort()[::-1][:top_n]
    return [{"text": corpus[i], "score": float(sims[i])} for i in top_idxs if sims[i]>0]

def summarize_text(text, bullets=6):
    sents = re.split(r'(?<=[\.\?\!])\s+', text)
    sents = [s.strip() for s in sents if s.strip()]
    return "\n".join(["- "+s for s in sents[:bullets]])

def generate_audio(text):
    if not text: return ""
    t = re.sub(r'[\[\]\(\)\{\}<>\"*_:;=\\/]', '', text)
    try:
        if gTTS:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            gTTS(text=t, lang="en").save(tmp.name)
            with open(tmp.name,"rb") as f:
                return base64.b64encode(f.read()).decode()
    except:
        pass
    return ""

def generate_ai_response(query, brand, mode="deep"):
    """Use GROQ API to generate AI response"""
    corpus = build_corpus(brand_data[brand]["references_path"])
    if st.session_state.uploaded_pdf_text:
        corpus.append(st.session_state.uploaded_pdf_text)
    
    snippets = search_local(query, corpus, top_n=3 if mode=="deep" else 1)
    context_text = "\n".join([s["text"] for s in snippets])
    
    if groq_client:
        prompt = f"""
You are an AI Sales Assistant. Generate a concise, actionable response based on the user's query and context below.
Context:
{context_text}

Query:
{query}

Include citations if possible. Format output clearly.
"""
        try:
            response = groq_client.complete(prompt=prompt, max_output_tokens=500, temperature=st.session_state.temperature)
            resp_text = response.completions[0].text.strip()
        except:
            resp_text = "(Groq API error. Using fallback response)\n" + query
    else:
        resp_text = "(GROQ not configured) " + query
    
    return resp_text, snippets

def generate_call_flow_summary(persona="HCP", objective="Awareness", brand="shingrix"):
    steps = brand_data[brand]["call_flow"]
    summary = f"**Call Flow for {persona} ({objective})**:\n"
    for i,s in enumerate(steps,1):
        summary += f"{i}. {s}\n"
    return summary

# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    st.session_state.selected_brand = st.selectbox(
        "Brand",
        list(brand_data.keys()),
        format_func=lambda x: brand_data[x]["display"],
        index=list(brand_data.keys()).index(st.session_state.selected_brand)
    )
    st.session_state.temperature = st.slider("Temperature",0.1,1.0,value=st.session_state.temperature)
    st.session_state.search_mode = st.selectbox("Search Mode",["shallow","deep"],index=0 if st.session_state.search_mode=="shallow" else 1)
    
    uploaded_pdf = st.file_uploader("Upload PDF/TXT", type=["pdf","txt"])
    if uploaded_pdf:
        tmp_file = tempfile.NamedTemporaryFile(delete=False)
        tmp_file.write(uploaded_pdf.read())
        tmp_file.close()
        st.session_state.uploaded_pdf_text = read_file_text(tmp_file.name)
        st.session_state.pdf_summary = summarize_text(st.session_state.uploaded_pdf_text, bullets=10)

# -------------------------
# Title
# -------------------------
st.markdown(f"## AI Sales Call Assistant - {brand_data[st.session_state.selected_brand]['display']}")

# -------------------------
# PDF Summary display
# -------------------------
if st.session_state.pdf_summary:
    st.markdown("**Uploaded PDF Summary:**")
    st.markdown(f"<div style='background:#f0f8ff;padding:10px;border-radius:8px;white-space:pre-line'>{escape(st.session_state.pdf_summary)}</div>", unsafe_allow_html=True)

# -------------------------
# Chat display with feedback buttons
# -------------------------
for idx,msg in enumerate(st.session_state.chat_history):
    role = msg["role"]
    if role=="user":
        st.markdown(f"**You:** {msg['content']}")
    else:
        st.markdown(f"**AI:** {msg['content']}")
        if msg.get("citations"):
            for c in msg["citations"]:
                st.markdown(f"<div style='font-size:13px;background:#eef9ff;padding:4px;margin:2px;border-left:3px solid #0078D7'>{c['text'][:200]}...</div>", unsafe_allow_html=True)
        if msg.get("audio"):
            st.audio(base64.b64decode(msg["audio"]), format="audio/mp3")
        
        # Feedback buttons
        col1, col2 = st.columns([1,1])
        with col1:
            if st.button(f"👍 Helpful ({idx})", key=f"helpful_{idx}"):
                st.session_state.followup_state[idx] = "helpful"
        with col2:
            if st.button(f"👎 Not Helpful ({idx})", key=f"nothelpful_{idx}"):
                st.session_state.followup_state[idx] = "not_helpful"
        if idx in st.session_state.followup_state:
            st.markdown(f"*Feedback: {st.session_state.followup_state[idx]}*")

# -------------------------
# Prompt suggestions
# -------------------------
prompts = [
    "Generate call flow for this HCP",
    "Summarize key clinical points",
    "Prepare objection handling",
    "Generate patient education points"
]
st.markdown("**Suggestions:**")
cols = st.columns(len(prompts))
for i,p in enumerate(prompts):
    if cols[i].button(p):
        st.session_state.main_input = p
        st.experimental_rerun()

# -------------------------
# Generate Call Flow Button
# -------------------------
persona_input = st.text_input("HCP Persona","General HCP")
objective_input = st.text_input("Objective","Awareness")
if st.button("Generate Call Flow & Summary"):
    call_flow_text = generate_call_flow_summary(persona_input, objective_input, st.session_state.selected_brand)
    st.session_state.chat_history.append({"role":"ai","content":call_flow_text})
    st.experimental_rerun()

# -------------------------
# Input area
# -------------------------
user_input = st.text_area("Your message", value=st.session_state.main_input, key="main_input_area")
if st.button("Send Message"):
    if user_input.strip():
        st.session_state.chat_history.append({"role":"user","content":user_input.strip()})
        ai_resp, citations = generate_ai_response(user_input.strip(), st.session_state.selected_brand, st.session_state.search_mode)
        audio_b64 = generate_audio(ai_resp)
        st.session_state.chat_history.append({"role":"ai","content":ai_resp,"citations":citations,"audio":audio_b64})
        st.session_state.main_input = ""
        st.experimental_rerun()

# -------------------------
# Export / download chat
# -------------------------
if st.session_state.chat_history:
    with st.expander("💾 Export / Download Chat", expanded=False):
        text_export = "\n\n".join([f"{('You' if m['role']=='user' else 'AI')}: {m['content']}" for m in st.session_state.chat_history])
        st.download_button("⬇️ Download TXT", text_export.encode("utf-8"), file_name=f"{st.session_state.selected_brand}_chat_{datetime.now().strftime('%Y%m%d')}.txt")
        if DOCX_AVAILABLE and st.button("Export as DOCX"):
            doc = Document()
            doc.add_heading(f"AI Sales Call Assistant - {st.session_state.selected_brand}",0)
            for m in st.session_state.chat_history:
                role = "You" if m["role"]=="user" else "AI"
                doc.add_paragraph(f"{role}: {m['content']}")
            tmp = tempfile.NamedTemporaryFile(delete=False,suffix=".docx")
            doc.save(tmp.name)
            with open(tmp.name,"rb") as f:
                st.download_button("⬇️ Download DOCX", f.read(), file_name=f"{st.session_state.selected_brand}_chat.docx")

# -------------------------
# Footer
# -------------------------
st.markdown("""
---
<small style="color:gray;">AI Sales Call Assistant © 2025 | Powered by GROQ AI | Always verify clinical references before use.</small>
""", unsafe_allow_html=True)
