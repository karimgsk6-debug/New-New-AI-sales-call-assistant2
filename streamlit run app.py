# ============================================================
# AI SALES CALL ASSISTANT — FULLY MERGED VERSION
# ============================================================

import streamlit as st
import os, re
from html import escape

# =========================
# OPTIONAL DEPENDENCIES
# =========================
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
    SKLEARN = True
except:
    SKLEARN = False

# =========================
# PAGE CONFIG & STYLING
# =========================
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide"
)

st.markdown(
    """
    <style>
        .stApp {
            background-image: url('https://images.unsplash.com/photo-1588776814546-8c80b1cd3b19?auto=format&fit=crop&w=1350&q=80');
            background-size: cover;
            background-position: center;
        }
        .chat-bubble-user {background-color:#cce5ff; padding:10px; border-radius:10px; margin:5px 0;}
        .chat-bubble-ai {background-color:#e2e3e5; padding:10px; border-radius:10px; margin:5px 0;}
    </style>
    """,
    unsafe_allow_html=True
)

# =========================
# SESSION STATE
# =========================
def init_state():
    defaults = {
        "chat": [],
        "roleplay_history": [],
        "simulation": False,
        "product": "Shingrix",
        "indication": "Herpes Zoster",
        "persona": "Evidence-led",
        "hcp_segment": "Consultant",
        "barrier": "Time constraints",
        "objective": "Initiate discussion"
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_state()

# =========================
# PRODUCT REGISTRY
# =========================
PRODUCTS = {
    "Shingrix": {
        "indications": ["Herpes Zoster"],
        "refs": "data/shingrix/references/",
        "sales": "data/shingrix/sales/"
    },
    "Jemperli": {
        "indications": ["Endometrial Cancer"],
        "refs": "data/jemperli/references/",
        "sales": "data/jemperli/sales/"
    },
    "Trelegy": {
        "indications": ["COPD", "Asthma"],
        "refs": "data/trelegy/references/",
        "sales": "data/trelegy/sales/"
    }
}

# =========================
# GROQ CLIENT
# =========================
def get_llm():
    # Replace with your real Groq API key
    api_key = "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"
    if not api_key or not Groq:
        return None
    return Groq(api_key=api_key)

LLM = get_llm()

# =========================
# FILE & CORPUS LOADING
# =========================
def read_file(path):
    if not os.path.exists(path):
        return ""
    if path.endswith(".pdf") and PdfReader:
        reader = PdfReader(path)
        return " ".join(p.extract_text() or "" for p in reader.pages)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def build_corpus(folders):
    chunks, meta = [], []
    for folder in folders:
        if not os.path.exists(folder):
            continue
        for f in os.listdir(folder):
            if f.endswith((".pdf", ".txt")):
                text = read_file(os.path.join(folder, f))
                for s in re.split(r'(?<=[.!?])\s+', text):
                    if len(s) > 40:
                        chunks.append(s)
                        meta.append(f)
    return chunks, meta

# =========================
# RETRIEVAL
# =========================
def retrieve(query, chunks, meta, k=6):
    if not SKLEARN or not chunks:
        return []
    vec = TfidfVectorizer(stop_words="english")
    X = vec.fit_transform(chunks + [query])
    sims = linear_kernel(X[-1], X[:-1]).flatten()
    idxs = sims.argsort()[::-1][:k]
    return [{"text": chunks[i], "src": meta[i]} for i in idxs if sims[i] > 0]

# =========================
# CITATION ENGINE
# =========================
def cite(text, refs):
    out = []
    for sent in re.split(r'(?<=[.!?])\s+', text):
        src = refs[0]["src"] if refs else "N/A"
        out.append(f"{sent}<br><span style='font-size:11px;color:#9aa'>(Source: {src})</span>")
    return "<br>".join(out)

# =========================
# GUARDED GENERATION
# =========================
def guarded_llm(user_prompt, role="assistant"):
    if not LLM:
        return "⚠️ LLM not configured. Please add GROQ_API_key."

    product = PRODUCTS[st.session_state.product]
    chunks, meta = build_corpus([product["refs"], product["sales"]])
    retrieved = retrieve(user_prompt, chunks, meta)

    if not retrieved:
        return "⚠️ This question is not covered by approved materials."

    context = "\n".join(f"[{r['src']}] {r['text']}" for r in retrieved)

    prompt = f"""
ROLE: {role}
PRODUCT: {st.session_state.product}
INDICATION: {st.session_state.indication}
HCP SEGMENT: {st.session_state.hcp_segment}
OBJECTIVE: {st.session_state.objective}
BARRIER: {st.session_state.barrier}

STRICT RULES:
- Use ONLY the context
- No external knowledge
- Cite implicitly

CONTEXT:
{context}

TASK:
{user_prompt}
"""

    resp = LLM.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )

    return cite(resp.choices[0].message.content, retrieved)

# =========================
# ROLE PLAY
# =========================
def roleplay(rep_input):
    history = "\n".join(st.session_state.roleplay_history[-6:])
    prompt = f"""
You are an HCP persona: {st.session_state.persona}

Conversation:
{history}

Rep says:
{rep_input}

Respond ONLY as HCP.
"""
    reply = guarded_llm(prompt, role="HCP")
    st.session_state.roleplay_history += [f"REP: {rep_input}", f"HCP: {reply}"]
    return reply

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.header("⚙️ Call Setup")

    st.selectbox("Product", PRODUCTS.keys(), key="product")
    st.selectbox("Indication", PRODUCTS[st.session_state.product]["indications"], key="indication")

    st.selectbox("HCP Segment", ["Consultant", "GP", "Specialist", "Pharmacist"], key="hcp_segment")
    st.selectbox("Persona", ["Evidence-led", "Skeptical", "Time-pressured", "Early adopter"], key="persona")
    st.selectbox("Barrier", ["Time constraints", "Budget limits", "Efficacy concerns", "Safety concerns"], key="barrier")

    st.selectbox("Call Objective", [
        "Initiate discussion",
        "Handle objection",
        "Drive adoption",
        "Close next step"
    ], key="objective")

    st.toggle("🎭 Simulation Mode", key="simulation")

    if st.button("🔄 Reset Session"):
        st.session_state.chat = []
        st.session_state.roleplay_history = []

# =========================
# MAIN UI
# =========================
st.title("🧠 AI Sales Call Assistant")
mode = "🎭 Simulation" if st.session_state.simulation else "💬 Q&A"
st.markdown(f"**Mode:** {mode}")

user_input = st.text_area("Your input")

if st.button("Send") and user_input.strip():
    if st.session_state.simulation:
        reply = roleplay(user_input)
    else:
        reply = guarded_llm(user_input)

    st.session_state.chat.append(("user", user_input))
    st.session_state.chat.append(("ai", reply))

# =========================
# CHAT DISPLAY
# =========================
for r, m in st.session_state.chat:
    if r == "user":
        st.markdown(f"<div class='chat-bubble-user'>🧑‍💼 {escape(m)}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='chat-bubble-ai'>🤖 {m}</div>", unsafe_allow_html=True)

# =========================
# COLLAPSIBLE SUMMARIES
# =========================
product_data = PRODUCTS[st.session_state.product]

with st.expander("📄 Medical References Summary"):
    medical_text = "\n".join([read_file(os.path.join(product_data["refs"], f)) for f in os.listdir(product_data["refs"])])
    st.write(medical_text[:2000] + "...")  # first 2000 chars

with st.expander("💼 Sales Module Summary"):
    sales_text = "\n".join([read_file(os.path.join(product_data["sales"], f)) for f in os.listdir(product_data["sales"])])
    st.write(sales_text[:2000] + "...")  # first 2000 chars

# =========================
# FOOTER
# =========================
st.markdown(
    "<hr><small>Internal use only — responses limited to approved materials.</small>",
    unsafe_allow_html=True
)
