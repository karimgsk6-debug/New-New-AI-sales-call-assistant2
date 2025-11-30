# app.py - Rewritten AI Sales Call Assistant
# - Smarter bullet summaries for medical & sales modules
# - White "bubble" UI for AI summaries and generated responses
# - GROQ usage: when available, retrieves & conditions on files inside each brand's
#   .devcontainer/references/<brand> and .devcontainer/SalesModule/<brand> folders

import streamlit as st
import os, re, tempfile, base64, io
from datetime import datetime
from html import escape

# Optional libs
try:
    from groq import Groq
except Exception:
    Groq = None

try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except Exception:
    SKLEARN_AVAILABLE = False

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# ---- Repo / visual assets (placeholders) ----
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"
GSK_LOGO_RAW = f"{REPO_RAW_BASE}/GSK1-logo.png"
AI_LOGO_RAW = f"{REPO_RAW_BASE}/AURA1.png"

# -------------------------
# Session defaults
# -------------------------
defaults = {
    "chat_history": [],
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.2,
    "search_mode": "deep",
    "medical_summary": "",
    "sales_summary": "",
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "feedback": {},
    "dislike_state": None,
    "language": "English",
}
for k,v in defaults.items():
    st.session_state.setdefault(k,v)

# -------------------------
# Small helper: dynamic background (keeps previous behaviour)
# -------------------------
def set_dynamic_background(image_path: str):
    """
    Injects CSS to set the background image + keeps gradient behind it.
    """
    if os.path.exists(image_path):
        encoded_bg = base64.b64encode(open(image_path, "rb").read()).decode()

        css = f"""
        <style>
        .stApp {{
            background: linear-gradient(135deg, #ff7e33 0%, #ffbb66 100%);
            background-size: cover;
            background-attachment: fixed;
        }}

        .background-image-overlay {{
            position: fixed;
            top: 0;
            right: 0;
            width: 40%;
            height: 100%;
            background-image: url('data:image/png;base64,{encoded_bg}');
            background-size: contain;
            background-repeat: no-repeat;
            background-position: right center;
            pointer-events: none;
            z-index: 0;
        }}

        .chat-bubble {{
            background: #ffffff;
            padding: 14px 18px;
            border-radius: 14px;
            margin-top: 15px;
            box-shadow: 0px 2px 4px rgba(0,0,0,0.1);
        }}

        .summary-bubble {{
            background: #ffffff;
            padding: 12px 16px;
            border-radius: 12px;
            margin-top: 10px;
            box-shadow: 0px 1px 3px rgba(0,0,0,0.1);
        }}

        .citation-box {{
            font-size: 12px;
            color: #374151;
            margin-top: 6px;
        }}
        </style>

        <div class="background-image-overlay"></div>
        """

        st.markdown(css, unsafe_allow_html=True)(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background: linear-gradient(90deg, rgba(255,140,0,0.05), rgba(255,165,0,0.02)),
                        url("data:image/png;base64,{encoded}");
            background-repeat: no-repeat;
            background-position: right top;
            background-size: cover;
        }}
        .title-box {{ background: rgba(255,255,255,0.85); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; }}
        .title-box img.left-logo {{ position:absolute; left:12px; height:48px; }}
        .title-box img.right-logo {{ position:absolute; right:12px; height:48px; }}

        /* White bubble styles for AI outputs and summaries */
        .chat-bubble-ai, .summary-bubble {{
            background: #ffffff;
            color: #111827;
            padding: 14px;
            border-radius: 12px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.06);
            margin: 8px 0;
        }}
        .chat-bubble-user {{
            background: rgba(15,23,42,0.07);
            color: #0f172a;
            padding:10px 14px;
            border-radius:12px;
            margin:8px 0;
        }}
        .citation-box { font-size:12px; color:#374151; margin-top:6px; }
        .fixed-disclaimer { font-size:12px; color:#374151; margin-top:18px; }
        </style>
        """, unsafe_allow_html=True
    )

set_dynamic_background(BACKGROUND_PATH)

# -------------------------
# Initialize GROQ client (if available)
# -------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "GROQ_API_KEY_PLACEHOLDER") if hasattr(st, "secrets") else os.environ.get("GROQ_API_KEY", "")
client = None
if Groq and GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

# -------------------------
# Brand info and paths (as requested)
# -------------------------
brand_data = {
    "shingrix": {
        "display":"Shingrix",
        "references_path":".devcontainer/references/shingrix",
        "sales_path":".devcontainer/SalesModule/shingrix",
        "call_flow":["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Post-call Analysis"]
    },
    "jemperli": {
        "display":"Jemperli",
        "references_path":".devcontainer/references/jemperli",
        "sales_path":".devcontainer/SalesModule/jemperli",
        "call_flow":["COCO","Anchor","Engage","Close"]
    },
    "trelegy": {
        "display":"Trelegy",
        "references_path":".devcontainer/references/trelegy",
        "sales_path":".devcontainer/SalesModule/trelegy",
        "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"]
    }
}

# -------------------------
# File reading helpers
# -------------------------

def read_file_text(path):
    if not os.path.exists(path):
        return ""
    try:
        if path.lower().endswith('.pdf') and PdfReader:
            reader = PdfReader(path)
            return "\n".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path, 'r', encoding='utf-8', errors='ignore') as fh:
                return fh.read()
    except Exception:
        return ""


def gather_text_from_folder(folder):
    """Concatenate text from .txt and .pdf files under a folder (non-recursive)."""
    out = []
    if not folder or not os.path.exists(folder):
        return ""
    for fname in sorted(os.listdir(folder)):
        if fname.lower().endswith(('.txt', '.pdf')):
            out.append(read_file_text(os.path.join(folder, fname)))
    return "\n\n".join([t for t in out if t.strip()])

# -------------------------
# Build brand-specific combined texts
# -------------------------
sel_brand = st.sidebar.selectbox("Brand", list(brand_data.keys()), index=list(brand_data.keys()).index(st.session_state.selected_brand))
st.session_state.selected_brand = sel_brand
bconf = brand_data[sel_brand]
refs_text = gather_text_from_folder(bconf['references_path'])
sales_text = gather_text_from_folder(bconf['sales_path'])

# -------------------------
# Local corpus building for quick retrieval (simple chunking)
# -------------------------

def build_chunks_from_text(text, chunk_size_sentences=4):
    if not text: return [], []
    sents = re.split(r'(?<=[\.!?])\s+', text)
    chunks = []
    metas = []
    for i in range(0, len(sents), chunk_size_sentences):
        chunk = ' '.join(sents[i:i+chunk_size_sentences]).strip()
        if chunk:
            chunks.append(chunk)
            metas.append({'start_sent': i})
    return chunks, metas

corpus_text = refs_text + "\n\n" + sales_text
chunks, metas = build_chunks_from_text(corpus_text, chunk_size_sentences=4)

# -------------------------
# Local search helper (TF-IDF fallback)
# -------------------------

def local_search(query, chunks, metas, top_n=4):
    if not chunks: return []
    q = query.lower()
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words='english').fit(chunks + [query])
            chunk_vecs = vectorizer.transform(chunks)
            q_vec = vectorizer.transform([query])
            sims = linear_kernel(q_vec, chunk_vecs).flatten()
            idxs = sims.argsort()[::-1][:top_n]
            out = []
            for i in idxs:
                if sims[i] <= 0: continue
                out.append({'score': float(sims[i]), 'text': chunks[i], 'meta': metas[i]})
            return out
        except Exception:
            pass
    # simple substring fallback
    out = []
    for i,c in enumerate(chunks):
        if q in c.lower():
            out.append({'score':1.0,'text':c,'meta':metas[i]})
            if len(out) >= top_n: break
    return out

# -------------------------
# Improved summarization routines
# -------------------------

def simple_bullets_from_text(text, max_bullets=6):
    if not text: return ""
    sents = [s.strip() for s in re.split(r'(?<=[\.!?])\s+', text) if s.strip()]
    bullets = sents[:max_bullets]
    return '\n'.join([f'- {b}' for b in bullets])


def smart_summary_with_model(text, label="Summary", max_bullets=6, context_snippets=None):
    """If Groq client is available, ask it to produce a smart, clinically-oriented bullet summary.
       We include short context snippets (from local files) to ground the reply. Falls back to simple bullets."""
    if not text:
        return "No content available for summarization."

    # Build a compact grounding context from local snippets (if provided)
    grounding = ''
    if context_snippets:
        grounding = '\n\n'.join([s['text'] for s in context_snippets[:4]])

    if client:
        try:
            # Compose a clear instruction for the model
            instruction = (
                f"You are an expert medical communications assistant. Create a {max_bullets}-bullet "
                f"{label} aimed at a pharmaceutical field sales rep. Each bullet should be concise, "
                f"actionable, and include a one-line practical implication for a sales call. Use the "
                f"grounding material below when relevant. If information is not present, say 'Not stated in provided documents'.\n\n"
            )
            prompt = instruction + "\n\nGROUNDING:\n" + grounding + "\n\nSOURCE TEXT:\n" + text[:12000]
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt}],
                temperature=0.15,
            )
            answer = resp.choices[0].message.content.strip()
            # Ensure bullet formatting - if model returns paragraphs, try to transform
            if not answer.startswith("-") and '\n' in answer:
                lines = [l.strip() for l in answer.splitlines() if l.strip()]
                if len(lines) <= max_bullets:
                    answer = '\n'.join([f'- {l}' if not l.startswith('-') else l for l in lines[:max_bullets]])
            return answer
        except Exception:
            pass
    # Fallback: use simple extraction and add a sales-focused implication line
    bullets = []
    sents = [s.strip() for s in re.split(r'(?<=[\.!?])\s+', text) if s.strip()]
    for i, sent in enumerate(sents[:max_bullets]):
        implication = ''
        if 'efficacy' in sent.lower():
            implication = ' (Sales tip: emphasise comparative efficacy data to address efficacy concerns.)'
        elif 'safety' in sent.lower() or 'adverse' in sent.lower():
            implication = ' (Sales tip: prepare concise safety takeaway and quick references.)'
        bullets.append(f'- {sent}{implication}')
    return '\n'.join(bullets)

# -------------------------
# Prepare or refresh brand summaries (medical & sales) and show in white bubbles
# -------------------------
if not st.session_state.medical_summary:
    ref_snippets = local_search('key facts', chunks, metas, top_n=6) if chunks else []
    st.session_state.medical_summary = smart_summary_with_model(refs_text, label='Medical References Summary', max_bullets=6, context_snippets=ref_snippets)

if not st.session_state.sales_summary:
    sales_snips = local_search('sales', chunks, metas, top_n=6) if chunks else []
    st.session_state.sales_summary = smart_summary_with_model(sales_text, label='Sales Module Summary', max_bullets=6, context_snippets=sales_snips)

# Render title box
st.markdown(f"""
<div class="title-box">
    <img src="{GSK_LOGO_RAW}" class="left-logo">
    <h2>💡 AI Sales Call Assistant — {bconf['display']}</h2>
    <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# Show summaries inside white bubbles (styled via CSS)
with st.expander("📚 Medical References Summary", expanded=False):
    st.markdown(f"<div class=\"summary-bubble\">{escape(st.session_state.medical_summary).replace('\n','<br>')}</div>", unsafe_allow_html=True)
with st.expander("💼 Sales Module Summary", expanded=False):
    st.markdown(f"<div class=\"summary-bubble\">{escape(st.session_state.sales_summary).replace('\n','<br>')}</div>", unsafe_allow_html=True)

# -------------------------
# PDF Upload and summarize with the same smart routine
# -------------------------
uploaded_file = st.file_uploader("Upload PDF for summary", type=["pdf"] )
if uploaded_file and PdfReader:
    try:
        reader = PdfReader(uploaded_file)
        pdf_text = '\n'.join([p.extract_text() or '' for p in reader.pages])
        st.session_state.uploaded_pdf_text = pdf_text
        st.session_state.pdf_summary = smart_summary_with_model(pdf_text, label='Uploaded PDF Summary', max_bullets=6)
        st.success("PDF summarized successfully!")
    except Exception:
        st.error("Failed to parse the uploaded PDF.")

if st.session_state.pdf_summary:
    with st.expander("📄 Uploaded PDF Summary", expanded=False):
        st.markdown(f"<div class=\"summary-bubble\">{escape(st.session_state.pdf_summary).replace('\n','<br>')}</div>", unsafe_allow_html=True)

# -------------------------
# Prompt suggestions for quick inputs
# -------------------------

def make_suggestions_display():
    seg = st.selectbox("Segment", ["Awareness","Adoption","Retention"])  # simple UI to choose segment
    persona = st.text_input("HCP Persona", "Committed Vaccinator")
    obj = st.selectbox("Objective", ["Awareness","Adoption","Retention"], index=0)
    s = []
    s.append(f"Generate call flow for {persona} focused on {obj}.")
    s.append(f"Key talking points for {bconf['display']} in {seg}.")
    s.append(f"Handle objection: cost or efficacy for {persona}.")
    cols = st.columns(3)
    for i,txt in enumerate(s):
        if cols[i%3].button(txt, key=f'sugg_{i}'):
            st.session_state.main_input = txt

with st.expander("💡 Prompt Suggestions (Click to expand)", expanded=False):
    make_suggestions_display()

# -------------------------
# Core: produce a more intelligent AI answer using GROQ (when available)
# -------------------------

def compose_grounded_prompt(user_query, brand_key, snippets):
    """Compose a prompt that provides grounding from local files and instructs the model to be concise, helpful and sales-focused."""
    instruction = (
        "You are a concise, practical sales enablement assistant. Produce an answer tailored for a field sales representative. "
        "Use the provided local document snippets as grounding. Return output as bullet points where appropriate, include explicit 'Sales Tips' lines and a one-line suggested call-opening. "
    )
    grounding_text = ''
    if snippets:
        grounding_text = '\n\n'.join([f"SNIPPET (score={s.get('score',0):.2f}): {s['text'][:1000]}" for s in snippets[:6]])
    # Include small instructions about which folders were used
    folders_info = f"References folder: {brand_data[brand_key]['references_path']}\nSales module folder: {brand_data[brand_key]['sales_path']}"
    prompt = instruction + "\n\n" + folders_info + "\n\nGROUNDING_SNIPPETS:\n" + grounding_text + "\n\nUSER_QUERY:\n" + user_query
    return prompt


def generate_model_response(user_query, brand_key, temperature=0.15):
    # Find local snippets to ground the model
    snippets = local_search(user_query, chunks, metas, top_n=6)
    prompt = compose_grounded_prompt(user_query, brand_key, snippets)

    if client:
        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt}],
                temperature=temperature,
            )
            return resp.choices[0].message.content.strip(), snippets
        except Exception:
            pass
    # Fallback: build a heuristic answer using snippets
    lines = ["- Acknowledge: Thanks for the question. Here are focused points:"]
    for s in snippets[:5]:
        short = (s['text'][:280] + '...') if len(s['text']) > 300 else s['text']
        lines.append(f"- {short} (source snippet)")
    lines.append("\nSales Tip: Summarise efficacy in one sentence and offer to send the key reference PDF.")
    lines.append("Call Opening Suggestion: 'Hi Dr X, I wanted to quickly share the most relevant evidence on...'")
    return '\n'.join(lines), snippets

# Function that drives AI reply and stores chat history

def add_ai_response(user_prompt):
    # Produce a grounded model answer
    ai_text, snippets = generate_model_response(user_prompt, st.session_state.selected_brand, temperature=st.session_state.temperature)
    # Build citation list for UI (files found in local snippets)
    citation_files = []
    for s in snippets:
        # We don't have exact filenames in this simple chunking approach; attempt to find filename by searching folders
        # (If more precise meta is needed, build chunker that stores filename earlier.)
        citation_files.append(f"local_snippet (score={s.get('score',0):.2f})")
    citation = ', '.join(list(dict.fromkeys(citation_files)))
    st.session_state.chat_history.append({
        'role':'assistant',
        'content':ai_text,
        'citation': citation,
        'timestamp': datetime.utcnow().isoformat()
    })

# -------------------------
# Chat input form and sending
# -------------------------
with st.form('main_input_form', clear_on_submit=True):
    user_input = st.text_area('Ask something:', value=st.session_state.main_input, height=90)
    submitted = st.form_submit_button('Send')
    if submitted and user_input.strip():
        st.session_state.chat_history.append({'role':'user','content':user_input.strip(),'timestamp':datetime.utcnow().isoformat()})
        add_ai_response(user_input.strip())
        st.session_state.main_input = ''

# -------------------------
# Display chat history (white bubble for AI)
# -------------------------
chat_container = st.container()
with chat_container:
    for idx,entry in enumerate(st.session_state.chat_history):
        if entry['role'] == 'user':
            st.markdown(f"<div class=\"chat-bubble-user\">{escape(entry['content'])}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class=\"chat-bubble-ai\">{escape(entry['content']).replace('\n','<br>')}</div>", unsafe_allow_html=True)
            if entry.get('citation'):
                st.markdown(f"<div class=\"citation-box\">Sources: {escape(entry['citation'])}</div>", unsafe_allow_html=True)

            # Feedback buttons
            fb_cols = st.columns(3)
            if entry['content'] not in st.session_state.feedback:
                if fb_cols[0].button('👍 Like', key=f'like_{idx}'):
                    st.session_state.feedback[entry['content']] = 'like'
                if fb_cols[1].button('👎 Dislike', key=f'dislike_{idx}'):
                    st.session_state.feedback[entry['content']] = 'dislike'
                    # on dislike we add a clarifying follow-up answer (shorter / clearer)
                    followup_prompt = 'Refine and shorten previous assistant reply focusing on clarity.'
                    add_ai_response(followup_prompt)
                if fb_cols[2].button('ℹ️ Need More', key=f'needmore_{idx}'):
                    st.session_state.feedback[entry['content']] = 'need_more'
                    add_ai_response('Expand the previous answer with more actionable bullets and exact references.')

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown("""
<div class="fixed-disclaimer">
💡 This tool is for internal sales support purposes only. All medical info should be verified from official sources.
</div>
""", unsafe_allow_html=True)
