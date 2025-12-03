# app.py - MR Mentor — Final Full App (RAG cleaned for PDF/DOCX/TXT + All features)

import streamlit as st
import os, glob, base64, io, re, numpy as np
from html import escape
from sklearn.feature_extraction.text import TfidfVectorizer
from datetime import datetime
import altair as alt

# --------------------------
# Optional libs: GROQ, PDF, DOCX
# --------------------------
try:
    from groq import Groq
except Exception:
    Groq = None

try:
    from PyPDF2 import PdfReader
    PDF_AVAILABLE = True
except Exception:
    PdfReader = None
    PDF_AVAILABLE = False

try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except Exception:
    DocxDocument = None
    DOCX_AVAILABLE = False

# --------------------------
# GROQ API placeholder (safe)
# --------------------------
GROQ_API_KEY = "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"  # set your key in code or better in st.secrets / env
client = None
if Groq and GROQ_API_KEY and GROQ_API_KEY != "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":
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

# --------------------------
# Brand configuration (product filter)
# --------------------------
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

# --------------------------
# Utilities: robust text extraction + cleaning
# --------------------------

def clean_text_for_rag(text: str) -> str:
    """
    Clean raw extracted text to remove binary garbage, PDF artifacts, excessive punctuation,
    very long random tokens, and normalize whitespace.
    """
    if not text:
        return ""

    # Replace nulls and weird control characters
    text = text.replace("\x00", " ")
    # Keep printable chars and common whitespace
    text = "".join(c if 32 <= ord(c) <= 126 or c in "\n\t\r" else " " for c in text)

    # Remove PDF binary-like residual sequences (heuristic)
    # Convert multiple non-alphanumeric sequences to single spaces except common punctuation
    text = re.sub(r"[^A-Za-z0-9\.\,\;\:\%\-\(\)\/\s\'\"]+", " ", text)

    # Remove obviously garbled tokens (very long > 30 chars no space)
    text = re.sub(r"\b\w{30,}\b", " ", text)

    # Remove repeated punctuation sequences
    text = re.sub(r"[\-=_]{2,}", " ", text)
    text = re.sub(r"[<>]{2,}", " ", text)

    # Collapse multiple whitespace/newlines into single spaces but preserve paragraphs by double newline
    # First normalize newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Replace multiple newlines with double newline marker and then normalize internal whitespace
    text = re.sub(r"\n{2,}", "\n\n", text)
    text = re.sub(r"[ \t\f\v]+", " ", text)
    # Trim spaces on lines
    text = "\n".join(line.strip() for line in text.splitlines())
    # Normalize overall whitespace
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = text.strip()

    # Final safeguard: if the result is too short, return empty
    if len(text) < 20:
        return ""

    return text

def extract_text_from_pdf(path: str) -> str:
    """Attempt to read PDF text via PyPDF2 PdfReader; returns cleaned text or ''."""
    if not PDF_AVAILABLE:
        return ""
    try:
        reader = PdfReader(path)
        pages_text = []
        for p in reader.pages:
            try:
                txt = p.extract_text() or ""
                pages_text.append(txt)
            except Exception:
                # skip problematic page
                continue
        raw = "\n".join(pages_text)
        return clean_text_for_rag(raw)
    except Exception:
        return ""

def extract_text_from_docx(path: str) -> str:
    """Attempt to read DOCX using python-docx."""
    if not DOCX_AVAILABLE:
        return ""
    try:
        doc = DocxDocument(path)
        paras = []
        for p in doc.paragraphs:
            paras.append(p.text)
        raw = "\n".join(paras)
        return clean_text_for_rag(raw)
    except Exception:
        return ""

def extract_text_from_txt(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            raw = fh.read()
            return clean_text_for_rag(raw)
    except Exception:
        return ""

def load_all_files(base_path):
    """
    Load files from base_path (recursive). For each file, detect extension and extract text.
    Returns list of tuples: (filename, cleaned_text).
    """
    data = []
    if not os.path.exists(base_path):
        return data
    for file in glob.glob(os.path.join(base_path, "**", "*.*"), recursive=True):
        fname = os.path.basename(file)
        ext = os.path.splitext(fname)[1].lower()
        text = ""
        try:
            if ext == ".pdf":
                text = extract_text_from_pdf(file)
            elif ext in [".docx", ".doc"]:
                text = extract_text_from_docx(file)
            elif ext in [".txt", ".md", ".text"]:
                text = extract_text_from_txt(file)
            else:
                # Unknown extension - attempt plaintext read as fallback
                text = extract_text_from_txt(file)
        except Exception:
            text = ""
        if text and len(text) > 50:
            data.append((fname, text))
    return data

# --------------------------
# RAG: chunking, vector DB builder, search
# --------------------------
def split_into_chunks(text: str, max_words=160):
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i+max_words]).strip()
        if len(chunk) > 30:
            chunks.append(chunk)
    return chunks

def build_vector_db_for_paths(paths):
    docs = []
    metas = []
    for p in paths:
        files = load_all_files(p)
        for fname, text in files:
            # chunk and add cleaned chunks only
            for chunk in split_into_chunks(text, max_words=160):
                clean_chunk = clean_text_for_rag(chunk)
                if clean_chunk and len(clean_chunk) > 30:
                    docs.append(clean_chunk)
                    metas.append({"filename": fname, "folder": p})
    if not docs:
        docs = ["No files found or extracted for selected path."]
        metas = [{"filename": "none", "folder": "none"}]
    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        vectors = vectorizer.fit_transform(docs)
    except Exception:
        vectorizer = None
        vectors = None
    return docs, metas, vectorizer, vectors

def search_docs_custom(query, docs, vectorizer, vectors, metas, top_k=5):
    if not query or not query.strip():
        return []
    if vectorizer is None or vectors is None:
        # simple substring fallback
        q = query.lower()
        results = []
        for i, d in enumerate(docs):
            if q in d.lower():
                results.append({"text": d, "meta": metas[i], "score": 1.0})
            if len(results) >= top_k:
                break
        return results
    try:
        qv = vectorizer.transform([query])
        scores = np.dot(vectors, qv.T).toarray().ravel()
        top_idx = np.argsort(scores)[::-1][:top_k]
        results = [{"text": docs[i], "meta": metas[i], "score": float(scores[i])} for i in top_idx if scores[i] > 0]
        if not results:
            # return top few even if zero score to provide context
            results = [{"text": docs[i], "meta": metas[i], "score": float(scores[i])} for i in top_idx][:top_k]
        return results
    except Exception:
        return []

# --------------------------
# Streamlit UI & layout
# --------------------------
st.set_page_config(page_title="MR Mentor — AI Sales Call Assistant", layout="wide")

# background image (if available)
def add_background_image():
    img_path = ".devcontainer/Visuals/MR mentor final1.png"
    if os.path.exists(img_path):
        with open(img_path, "rb") as fh:
            enc = base64.b64encode(fh.read()).decode()
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url('data:image/png;base64,{enc}');
                background-size: cover;
                background-position: right;
                background-repeat: no-repeat;
            }}
            </style>
            """, unsafe_allow_html=True
        )

add_background_image()

# CSS for bubbles and layout
st.markdown("""
<style>
.user-bubble { background:#DCF2FF; padding:12px 18px; border-radius:18px; max-width:78%; margin:8px 0; font-size:14px; margin-left:auto; }
.ai-bubble { background:#FFFFFF; padding:14px 20px; border-radius:14px; max-width:78%; margin:10px 0; font-size:14px; border-left:4px solid #FF6A00; box-shadow:0 6px 18px rgba(20,20,40,0.06); }
.small-muted { font-size:12px; color:#666; margin-top:6px; }
.disclaimer-box { position: fixed; bottom: 0; left: 0; width: 100%; background: rgba(255,255,255,0.88); padding:10px 16px; font-size:12px; color:#444; text-align:center; border-top:1px solid #e6e6e6; backdrop-filter: blur(4px); z-index: 9998; }
.app-content-padding { padding-bottom: 160px; }
.prompt-suggestion { display:inline-block; margin:4px; padding:6px 10px; border-radius:8px; background:#f4f4f4; cursor:pointer; }
.sidebar-section { margin-bottom:12px; padding-bottom:6px; border-bottom:1px solid #eee; }
</style>
""", unsafe_allow_html=True)

st.title("💊 MR Mentor — AI Sales Call Assistant")

# --------------------------
# Sidebar: Product + HCP + Temperature + Dashboard (Altair charts)
# --------------------------
st.sidebar.header("Product & HCP Filters")

selected_brand = st.sidebar.selectbox("Product", list(brand_data.keys()), format_func=lambda k: brand_data[k]["display"])

# HCP selectors
hcp_segment = st.sidebar.selectbox("HCP Segment", ["High Value", "Medium Value", "Low Value", "New to Brand"])
hcp_specialty = st.sidebar.selectbox("Specialty", ["GP", "Dermatology", "Oncology", "Immunology", "Pulmonology", "Other"])
hcp_barriers = st.sidebar.multiselect("HCP Barriers", ["Lack of Awareness", "Safety Concerns", "Efficacy Doubts", "Too Busy", "Cost Concerns", "Prefers Competitor", "No Time for Reps"])
persona = st.sidebar.selectbox("Persona", ["Analytical", "Skeptical", "Supportive", "Passive", "Time-Pressed"])
behavior_type = st.sidebar.selectbox("Behavior Type", ["Early Adopter", "Follower", "Skeptic", "Unengaged"])
objection_type = st.sidebar.selectbox("Objection Type", ["Clinical", "Safety", "Cost", "Access", "Time", "Other"])
visit_type = st.sidebar.selectbox("Visit Type", ["Detailing Visit", "Follow-Up Visit", "Objection Handling", "Awareness Visit"])
engagement = st.sidebar.select_slider("Engagement Level", ["Very Low","Low","Medium","High","Very High"])

st.sidebar.markdown("---")
st.sidebar.subheader("LM Settings")
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.2
st.session_state.temperature = st.sidebar.slider("Temperature", 0.0, 1.5, st.session_state.temperature, 0.05)

# --------------------------
# Build brand-specific RAG DBs (references + sales)
# --------------------------
ref_path = brand_data[selected_brand]["references_path"]
sales_path = brand_data[selected_brand]["sales_path"]

docs_ref, metas_ref, vector_ref, vectors_ref = build_vector_db_for_paths([ref_path])
docs_sales, metas_sales, vector_sales, vectors_sales = build_vector_db_for_paths([sales_path])

# --------------------------
# Sidebar: Advanced dashboard using Altair
# --------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Mini Dashboard (Advanced)")

# initialize analytics in session state
st.session_state.setdefault("product_counts", {k:0 for k in brand_data.keys()})
st.session_state.setdefault("segment_counts", {})
st.session_state.setdefault("engagement_values", [])
st.session_state.setdefault("question_count", 0)
st.session_state.setdefault("feedback", {})  # mapping ai_text -> "useful"/"not_useful"

# show metrics
st.sidebar.metric("Total questions", st.session_state["question_count"])

# Product usage (pie-like using bar chart with percent labels)
prod_counts = [{"product": brand_data[k]["display"], "count": v} for k,v in st.session_state["product_counts"].items()]
if not any(d["count"]>0 for d in prod_counts):
    prod_counts = [{"product": brand_data[k]["display"], "count": 1} for k in st.session_state["product_counts"].keys()]

prod_df = alt.Chart(alt.Data(values=prod_counts)).mark_bar().encode(
    x=alt.X('count:Q', title='Count'),
    y=alt.Y('product:N', sort='-x', title=None),
    tooltip=['product','count']
).properties(height=120)
st.sidebar.altair_chart(prod_df, use_container_width=True)

# Segment distribution bar chart
seg_items = [{"segment": k, "count": v} for k,v in st.session_state["segment_counts"].items()]
if not seg_items:
    seg_items = [{"segment":"No data","count":1}]
seg_df = alt.Chart(alt.Data(values=seg_items)).mark_bar().encode(
    x='segment:N',
    y='count:Q',
    tooltip=['segment','count']
).properties(height=120)
st.sidebar.altair_chart(seg_df, use_container_width=True)

# Engagement trend line
eng_vals = st.session_state["engagement_values"]
eng_data = [{"i": i+1, "val": v} for i,v in enumerate(eng_vals)] if eng_vals else [{"i":1,"val":0}]
eng_df = alt.Chart(alt.Data(values=eng_data)).mark_line(point=True).encode(
    x='i:Q',
    y='val:Q',
    tooltip=['i','val']
).properties(height=120)
st.sidebar.altair_chart(eng_df, use_container_width=True)

# Feedback distribution pie via calculated values
useful = sum(1 for v in st.session_state["feedback"].values() if v=="useful")
notuseful = sum(1 for v in st.session_state["feedback"].values() if v=="not_useful")
fb_vals = [{"label":"Useful", "count": useful}, {"label":"Not useful", "count": notuseful}]
if useful+notuseful == 0:
    fb_vals = [{"label":"No feedback", "count": 1}]
fb_df = alt.Chart(alt.Data(values=fb_vals)).mark_bar().encode(
    x='count:Q',
    y='label:N',
    tooltip=['label','count']
).properties(height=80)
st.sidebar.altair_chart(fb_df, use_container_width=True)

st.sidebar.markdown("---")
st.sidebar.markdown("**Files loaded (medical):**")
st.sidebar.write(", ".join(sorted({m['filename'] for m in metas_ref if m.get('filename')})[:30]) or "None")
st.sidebar.markdown("**Files loaded (sales):**")
st.sidebar.write(", ".join(sorted({m['filename'] for m in metas_sales if m.get('filename')})[:30]) or "None")

# --------------------------
# Prompt suggestions (collapsible) above chat area
# --------------------------
with st.expander("💡 Prompt Suggestions (click to insert)", expanded=False):
    suggestions = [
        f"Create a short call script for a GP to encourage adoption of {brand_data[selected_brand]['display']}.",
        f"Address the top 2 medical objections for {brand_data[selected_brand]['display']}.",
        f"Summarize eligibility criteria for {brand_data[selected_brand]['display']} (use references only).",
        f"Suggest 3 talking points for a skeptical specialist about {brand_data[selected_brand]['display']}."
    ]
    cols = st.columns(2)
    for i, s in enumerate(suggestions):
        if cols[i % 2].button(s, key=f"sugg_{i}"):
            st.session_state["user_input"] = s

# --------------------------
# Prepare session state containers
# --------------------------
st.session_state.setdefault("history", [])  # list of dicts
st.session_state.setdefault("user_input", "")

# --------------------------
# RAG prompt builder and model call (Hybrid C)
# --------------------------
def build_rag_prompt(user_question, retrieved_ref, retrieved_sales, context_info):
    instruction = (
        "You are MR Mentor, an AI Sales Call Assistant. Strict rules:\n"
        "1) Medical factual claims MUST be supported by MEDICAL_SNIPPETS. Quote <=40 words and include filename.\n"
        "2) Sales guidance may use model reasoning but label as 'Sales Guidance'.\n"
        "3) If no medical support is found, say so explicitly and avoid hallucination.\n"
        "4) Use bullets and end with a 1-2 sentence verbatim script.\n\n"
    )
    med_block = "\n".join([f"---\n[{i+1}] ({r['meta']['filename']})\n{r['text']}" for i,r in enumerate(retrieved_ref)]) or "(no medical snippets)"
    sales_block = "\n".join([f"---\n[{i+1}] ({r['meta']['filename']})\n{r['text']}" for i,r in enumerate(retrieved_sales)]) or "(no sales snippets)"
    prompt = (
        instruction
        + "\nHCP CONTEXT:\n" + context_info + "\n\n"
        + "USER QUESTION:\n" + user_question + "\n\n"
        + "MEDICAL_SNIPPETS:\n" + med_block + "\n\n"
        + "SALES_SNIPPETS:\n" + sales_block + "\n\n"
        + "Produce: 1) Brief summary, 2) Medical evidence (quote+file) if applicable, 3) Sales Guidance, 4) 1-2 sentence script."
    )
    return prompt

def call_model(prompt, temperature=0.2):
    if client:
        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt}],
                temperature=temperature,
                max_tokens=1000
            )
            return resp.choices[0].message.content
        except Exception:
            # fall through
            pass
    # offline fallback
    return None

# --------------------------
# Submit callback safely clears input after use
# --------------------------
def submit_message_callback():
    ui = st.session_state.get("user_input", "").strip()
    if not ui:
        return
    context = (
        f"Product: {brand_data[selected_brand]['display']} | Segment: {hcp_segment} | Specialty: {hcp_specialty} | "
        f"Barriers: {', '.join(hcp_barriers) if hcp_barriers else 'None'} | Persona: {persona} | Behavior: {behavior_type} | "
        f"Objection: {objection_type} | Visit: {visit_type} | Engagement: {engagement}"
    )
    # retrieval
    retrieved_ref = search_docs_custom(ui, docs_ref, vector_ref, vectors_ref, metas_ref, top_k=5)
    retrieved_sales = search_docs_custom(ui, docs_sales, vector_sales, vectors_sales, metas_sales, top_k=5)
    # ensure retrieved texts are clean
    for r in retrieved_ref:
        r["text"] = clean_text_for_rag(r.get("text",""))
    for r in retrieved_sales:
        r["text"] = clean_text_for_rag(r.get("text",""))
    # build prompt
    prompt = build_rag_prompt(ui, retrieved_ref, retrieved_sales, context)
    # call model
    ai_response = call_model(prompt, temperature=st.session_state.temperature)
    if ai_response is None:
        # produce fallback message showing retrieved snippets only (no hallucination)
        lines = ["⚠️ (No LLM available) — offline fallback. Retrieved snippets shown below for reference.\n"]
        lines.append("=== MEDICAL SNIPPETS ===")
        for r in retrieved_ref:
            lines.append(f"{r['meta'].get('filename','')} — {r['text'][:400]}")
        lines.append("\n=== SALES SNIPPETS ===")
        for r in retrieved_sales:
            lines.append(f"{r['meta'].get('filename','')} — {r['text'][:400]}")
        ai_response = "\n".join(lines)

    ts = datetime.utcnow().isoformat()
    # append to history
    st.session_state.history.append({"role":"user","text":ui,"time":ts})
    st.session_state.history.append({
        "role":"ai","text":ai_response,"time":ts,
        "retrieved_ref": retrieved_ref, "retrieved_sales": retrieved_sales, "prompt": prompt
    })

    # update analytics
    st.session_state.product_counts[selected_brand] = st.session_state.product_counts.get(selected_brand,0) + 1
    st.session_state.segment_counts[hcp_segment] = st.session_state.segment_counts.get(hcp_segment,0) + 1
    eng_map = {"Very Low":1,"Low":2,"Medium":3,"High":4,"Very High":5}
    st.session_state.engagement_values.append(eng_map.get(engagement,3))
    st.session_state.question_count += 1

    # clear input safely
    st.session_state.user_input = ""

# --------------------------
# Input area & Send button
# --------------------------
st.text_area("Your message", key="user_input", height=120, placeholder="Type a question or scenario and press Send")
st.button("Send", on_click=submit_message_callback)

# --------------------------
# Show chat history with feedback & snippet insertion
# --------------------------
st.markdown("### Conversation")
st.markdown('<div class="app-content-padding">', unsafe_allow_html=True)

for idx, msg in enumerate(st.session_state.history):
    role = msg.get("role")
    text = msg.get("text","")
    ts = msg.get("time","")
    if role == "user":
        st.markdown(f"<div class='user-bubble'>{escape(text)}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='ai-bubble'>{escape(text)}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='small-muted'>Generated: {ts}</div>", unsafe_allow_html=True)

        # feedback buttons
        c1, c2, c3 = st.columns([1,1,4])
        if c1.button("👍 Useful", key=f"useful_{idx}"):
            st.session_state.feedback[text] = "useful"
        if c2.button("👎 Not useful", key=f"notuseful_{idx}"):
            st.session_state.feedback[text] = "not_useful"
        if c3.button("Show prompt & sources", key=f"showprompt_{idx}"):
            st.code(msg.get("prompt","(not available)")[:4000])

        # Expanders: show exact retrieved (cleaned) snippets and allow inserting into input for follow-up
        if msg.get("retrieved_ref"):
            with st.expander("View medical snippets used for this reply"):
                for j, r in enumerate(msg["retrieved_ref"]):
                    snippet = r["text"][:300].replace("\n"," ")
                    fname = r["meta"].get("filename","")
                    colL, colR = st.columns([5,1])
                    colL.markdown(f"**{fname}** — {escape(snippet)}...")
                    if colR.button("Insert", key=f"insert_ref_{idx}_{j}"):
                        st.session_state.user_input = f"Using snippet from {fname}: {snippet}\n\nFollow-up question: "

        if msg.get("retrieved_sales"):
            with st.expander("View sales snippets used for this reply"):
                for j, r in enumerate(msg["retrieved_sales"]):
                    snippet = r["text"][:300].replace("\n"," ")
                    fname = r["meta"].get("filename","")
                    colL, colR = st.columns([5,1])
                    colL.markdown(f"**{fname}** — {escape(snippet)}...")
                    if colR.button("Insert", key=f"insert_sales_{idx}_{j}"):
                        st.session_state.user_input = f"Using sales snippet from {fname}: {snippet}\n\nFollow-up question: "

st.markdown('</div>', unsafe_allow_html=True)

# --------------------------
# Collapsible RAG summaries (per product)
# --------------------------
with st.expander("📚 Medical References Summary", expanded=False):
    st.text(summarize_docs_preview(docs_ref, bullets=6))
    st.markdown("**Top medical files loaded:**")
    st.write(", ".join(sorted({m['filename'] for m in metas_ref if m.get('filename')})[:50]) or "None")

with st.expander("💼 Sales Module Summary", expanded=False):
    st.text(summarize_docs_preview(docs_sales, bullets=6))
    st.markdown("**Top sales files loaded:**")
    st.write(", ".join(sorted({m['filename'] for m in metas_sales if m.get('filename')})[:50]) or "None")

# --------------------------
# Footer: disclaimer
# --------------------------
st.markdown("""
<div class="disclaimer-box">
This AI assistant provides general medical and product-related information for educational and sales-training purposes only. It does not provide medical advice, diagnosis, or treatment recommendations. Healthcare Professionals should rely on official product information and clinical judgment. Always refer to the approved prescribing information and your local compliance regulations.
</div>
""", unsafe_allow_html=True)

# --------------------------
# Show warnings if necessary (PDF/DOCX/GROQ)
# --------------------------
warns = []
if not PDF_AVAILABLE:
    warns.append("PyPDF2 not available — PDF extraction disabled (install PyPDF2 for best results).")
if not DOCX_AVAILABLE:
    warns.append("python-docx not available — DOCX extraction disabled (install python-docx for best results).")
if client is None:
    warns.append("GROQ client not configured or not available — LLM calls will run in offline fallback mode.")

if warns:
    with st.expander("⚠️ System notices (click to view)", expanded=False):
        for w in warns:
            st.warning(w)
