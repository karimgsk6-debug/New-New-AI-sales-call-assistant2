# app.py - MR Mentor — Full AI Sales Call Assistant (FINAL, Advanced Dashboard)
# Features:
# - Product filter (shingrix, jemperli, trelegy)
# - RAG per-product (references + sales module)
# - Collapsible summaries
# - Prompt suggestions above the chat (click to insert)
# - Send button with safe callback
# - Feedback buttons (useful / not useful)
# - Advanced sidebar dashboard w/ matplotlib charts
# - Temperature slider
# - Background image + white AI bubbles
# - Fixed footer disclaimer
# - No NLTK required

import streamlit as st
import os, glob, base64, io, numpy as np
from html import escape
from sklearn.feature_extraction.text import TfidfVectorizer
from datetime import datetime
import matplotlib.pyplot as plt

# --------------------------
# Optional GROQ import
# --------------------------
try:
    from groq import Groq
except Exception:
    Groq = None

# --------------------------
# GROQ API placeholder
# --------------------------
GROQ_API_KEY = "Add_GROQ_API_Here"
client = None
if Groq and GROQ_API_KEY and GROQ_API_KEY != "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":
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except Exception:
        client = None

# --------------------------
# Brand definitions (paths)
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
# Small helpers: file load, chunk split, vector DB
# --------------------------
def load_all_files(base_path):
    results = []
    if not os.path.exists(base_path):
        return results
    pattern = os.path.join(base_path, "**", "*.*")
    for file in glob.glob(pattern, recursive=True):
        try:
            with open(file, "r", encoding="utf-8", errors="ignore") as fh:
                txt = fh.read()
                results.append((os.path.basename(file), txt))
        except Exception:
            pass
    return results

def split_into_chunks(text, max_words=160):
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i+max_words])
        chunks.append(chunk)
    return chunks

def build_vector_db_for_paths(paths):
    docs = []
    metas = []
    for p in paths:
        for fname, txt in load_all_files(p):
            # split into chunks for better retrieval
            for chunk in split_into_chunks(txt):
                docs.append(chunk)
                metas.append({"filename": fname, "folder": p})
    if not docs:
        docs = ["No files found for selected path."]
        metas = [{"filename": "none", "folder": "none"}]
    try:
        vect = TfidfVectorizer(stop_words="english")
        vectors = vect.fit_transform(docs)
    except Exception:
        # fallback minimal vector (rare)
        vect = None
        vectors = None
    return docs, metas, vect, vectors

def search_docs_custom(query, docs, vectorizer, vectors, metas, top_k=5):
    if not query or not query.strip():
        return []
    if vectorizer is None or vectors is None:
        # naive substring fallback
        out = []
        q = query.lower()
        for i, d in enumerate(docs):
            if q in d.lower():
                out.append({"text": d, "meta": metas[i], "score": 1.0})
            if len(out) >= top_k:
                break
        return out
    try:
        qv = vectorizer.transform([query])
        scores = np.dot(vectors, qv.T).toarray().ravel()
        top_idx = np.argsort(scores)[::-1][:top_k]
        results = [{"text": docs[i], "meta": metas[i], "score": float(scores[i])} for i in top_idx]
        return results
    except Exception:
        return []

def summarize_docs_preview(docs, bullets=5):
    if not docs:
        return "No data available."
    lines = []
    for d in docs[:bullets]:
        s = d.replace("\n", " ").strip()
        lines.append("- " + (s[:200] + ("..." if len(s) > 200 else "")))
    return "\n".join(lines)

# --------------------------
# Streamlit page config + styles + background
# --------------------------
st.set_page_config(page_title="MR Mentor — AI Sales Call Assistant", layout="wide")

def add_background_image():
    image_path = ".devcontainer/Visuals/MR mentor final1.png"
    if os.path.exists(image_path):
        with open(image_path, "rb") as fh:
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

st.markdown("""
<style>
.user-bubble { background:#DCF2FF; padding:12px 18px; border-radius:18px; max-width:78%; margin:8px 0; font-size:14px; margin-left:auto; }
.ai-bubble { background:#FFFFFF; padding:14px 20px; border-radius:14px; max-width:78%; margin:10px 0; font-size:14px; border-left:4px solid #FF6A00; box-shadow:0 6px 18px rgba(20,20,40,0.06); }
.small-muted { font-size:12px; color:#666; margin-top:6px; }
.disclaimer-box { position: fixed; bottom: 0; left: 0; width: 100%; background: rgba(255,255,255,0.88); padding:10px 16px; font-size:12px; color:#444; text-align:center; border-top:1px solid #e6e6e6; backdrop-filter: blur(4px); z-index: 9998; }
.app-content-padding { padding-bottom: 140px; }
.prompt-suggestion { display:inline-block; margin:4px; padding:6px 10px; border-radius:8px; background:#f4f4f4; cursor:pointer; }
.sidebar-section { margin-bottom:12px; padding-bottom:6px; border-bottom:1px solid #eee; }
</style>
""", unsafe_allow_html=True)

st.title("💊 MR Mentor — AI Sales Call Assistant")

# --------------------------
# Sidebar: product, HCP filters, temperature, and advanced dashboard (with charts)
# --------------------------
st.sidebar.header("Product & HCP Filters")

selected_brand = st.sidebar.selectbox("Product", list(brand_data.keys()), format_func=lambda x: brand_data[x]["display"])

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

# Build RAG DB for selected brand (references + sales paths)
ref_path = brand_data[selected_brand]["references_path"]
sales_path = brand_data[selected_brand]["sales_path"]

docs_ref, metas_ref, vector_ref, vectors_ref = build_vector_db_for_paths([ref_path])
docs_sales, metas_sales, vector_sales, vectors_sales = build_vector_db_for_paths([sales_path])

# --------------------------
# Sidebar: Advanced Mini Dashboard with charts
# --------------------------
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Mini Dashboard (Advanced)")

# initialize analytics state
if "product_counts" not in st.session_state:
    st.session_state.product_counts = {k:0 for k in brand_data.keys()}
if "segment_counts" not in st.session_state:
    st.session_state.segment_counts = {}
if "engagement_values" not in st.session_state:
    st.session_state.engagement_values = []
if "question_count" not in st.session_state:
    st.session_state.question_count = 0
if "feedback" not in st.session_state:
    st.session_state.feedback = {}

# summary numbers
st.sidebar.metric("Total questions", st.session_state.question_count)

# Product usage pie chart
fig1, ax1 = plt.subplots(figsize=(3.2,3.2))
prod_counts = list(st.session_state.product_counts.values())
prod_labels = [brand_data[k]['display'] for k in st.session_state.product_counts.keys()]
# Avoid empty pie
if sum(prod_counts) == 0:
    prod_counts = [1 for _ in prod_counts]
ax1.pie(prod_counts, labels=prod_labels, autopct='%1.0f%%')
ax1.set_title("Product usage")
st.sidebar.pyplot(fig1)

# Segment bar chart
fig2, ax2 = plt.subplots(figsize=(3.2,2.2))
segments = list(st.session_state.segment_counts.keys())
counts = [st.session_state.segment_counts.get(s,0) for s in segments]
if not segments:
    segments = ["No data"]
    counts = [1]
ax2.bar(segments, counts)
ax2.set_xticklabels(segments, rotation=30, ha='right')
ax2.set_title("HCP Segment distribution")
st.sidebar.pyplot(fig2)

# Engagement trend line
fig3, ax3 = plt.subplots(figsize=(3.2,2.2))
eng_vals = st.session_state.engagement_values
if not eng_vals:
    eng_vals = [0]
ax3.plot(range(1, len(eng_vals)+1), eng_vals, marker='o')
ax3.set_title("Engagement trend")
ax3.set_xlabel("Interaction #")
ax3.set_ylabel("Engagement (1-5)")
st.sidebar.pyplot(fig3)

# Feedback distribution pie
fig4, ax4 = plt.subplots(figsize=(3.2,2.2))
useful = sum(1 for v in st.session_state.feedback.values() if v == "useful")
notuseful = sum(1 for v in st.session_state.feedback.values() if v == "not_useful")
if useful + notuseful == 0:
    ax4.pie([1], labels=["No feedback"])
else:
    ax4.pie([useful, notuseful], labels=["Useful","Not useful"], autopct='%1.0f%%')
ax4.set_title("Feedback")
st.sidebar.pyplot(fig4)

st.sidebar.markdown("---")
st.sidebar.markdown("**Files loaded (medical):**")
st.sidebar.write(", ".join(sorted({m['filename'] for m in metas_ref if m.get('filename')} )[:30]) or "None")
st.sidebar.markdown("**Files loaded (sales):**")
st.sidebar.write(", ".join(sorted({m['filename'] for m in metas_sales if m.get('filename')} )[:30]) or "None")

# --------------------------
# Main area: Prompt suggestions (collapsible) above chat
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
            # safe set before input widget is created / updated
            st.session_state.user_input = s

# --------------------------
# Chat area: input, send button (with safe callback)
# --------------------------
if "history" not in st.session_state:
    st.session_state.history = []  # list of dicts: {"role": "user"/"ai", "text":..., "time":..., "retrieved_ref":..., "retrieved_sales":..., "prompt":...}

if "user_input" not in st.session_state:
    st.session_state.user_input = ""

# Define processing callback
def submit_message():
    # read user input from session_state (safe inside callback)
    ui = st.session_state.get("user_input", "").strip()
    if not ui:
        return
    # build context
    context = (
        f"Product: {brand_data[selected_brand]['display']} | "
        f"Segment: {hcp_segment} | Specialty: {hcp_specialty} | "
        f"Barriers: {', '.join(hcp_barriers) if hcp_barriers else 'None'} | "
        f"Persona: {persona} | Behavior: {behavior_type} | Objection: {objection_type} | "
        f"Visit: {visit_type} | Engagement: {engagement}"
    )
    # retrieve
    retrieved_ref = search_docs_custom(ui, docs_ref, vector_ref, vectors_ref, metas_ref, top_k=5)
    retrieved_sales = search_docs_custom(ui, docs_sales, vector_sales, vectors_sales, metas_sales, top_k=5)
    # build prompt for RAG hybrid C
    med_block = "\n".join([f"[{i+1}] ({r['meta']['filename']})\n{r['text']}" for i, r in enumerate(retrieved_ref)]) or "(no medical snippets)"
    sales_block = "\n".join([f"[{i+1}] ({r['meta']['filename']})\n{r['text']}" for i, r in enumerate(retrieved_sales)]) or "(no sales snippets)"
    instruction = (
        "You are MR Mentor, an AI Sales Call Assistant. Follow these rules:\n"
        "1) Medical factual claims MUST be supported by MEDICAL_SNIPPETS and include a short quote (<=40 words) and filename.\n"
        "2) Sales guidance may use model reasoning but label it 'Sales Guidance'.\n"
        "3) If no medical support exists, say so and do not hallucinate.\n"
        "4) Use bullets and end with a 1-2 sentence suggested script.\n\n"
    )
    prompt = (
        instruction
        + f"HCP & Context:\n{context}\n\nUSER QUERY:\n{ui}\n\nMEDICAL_SNIPPETS:\n{med_block}\n\nSALES_SNIPPETS:\n{sales_block}\n\nProduce: 1) summary, 2) medical evidence (quote+file), 3) sales guidance, 4) script."
    )

    # call LLM via client or fallback
    ai_text = None
    if client:
        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt}],
                temperature=st.session_state.temperature,
                max_tokens=1000
            )
            ai_text = resp.choices[0].message.content
        except Exception:
            ai_text = None
    if ai_text is None:
        # fallback: show retrieved snippets and context (no hallucination)
        lines = ["⚠️ (No LLM available) - offline fallback. See retrieved snippets below for grounding.", ""]
        lines.append("MEDICAL SNIPPETS:")
        for r in retrieved_ref:
            lines.append(f"- {r['meta'].get('filename','')} — {r['text'][:300].replace('\\n',' ')}")
        lines.append("")
        lines.append("SALES SNIPPETS:")
        for r in retrieved_sales:
            lines.append(f"- {r['meta'].get('filename','')} — {r['text'][:300].replace('\\n',' ')}")
        ai_text = "\n".join(lines)

    ts = datetime.utcnow().isoformat()
    # append to history
    st.session_state.history.append({
        "role": "user",
        "text": ui,
        "time": ts
    })
    st.session_state.history.append({
        "role": "ai",
        "text": ai_text,
        "time": ts,
        "retrieved_ref": retrieved_ref,
        "retrieved_sales": retrieved_sales,
        "prompt": prompt
    })

    # analytics updates
    st.session_state.product_counts[selected_brand] = st.session_state.product_counts.get(selected_brand, 0) + 1
    st.session_state.segment_counts[hcp_segment] = st.session_state.segment_counts.get(hcp_segment, 0) + 1
    eng_map = {"Very Low":1,"Low":2,"Medium":3,"High":4,"Very High":5}
    st.session_state.engagement_values.append(eng_map.get(engagement, 3))
    st.session_state.question_count += 1

    # clear input safely (this is inside callback)
    st.session_state.user_input = ""

# Input widgets: text_area and Send button (callback on_click)
st.text_area("Your message", key="user_input", height=120, placeholder="Type a question or scenario and press Send")
st.button("Send", on_click=submit_message)

# --------------------------
# Display chat history
# --------------------------
st.markdown("### Conversation")
st.markdown('<div class="app-content-padding">', unsafe_allow_html=True)

for i, msg in enumerate(st.session_state.history):
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
        if c1.button("👍 Useful", key=f"useful_{i}"):
            st.session_state.feedback[text] = "useful"
        if c2.button("👎 Not useful", key=f"notuseful_{i}"):
            st.session_state.feedback[text] = "not_useful"
        if c3.button("Show prompt & sources", key=f"showprompt_{i}"):
            # show prompt stored on the AI message (if available)
            prompt_text = msg.get("prompt", "(prompt not available)")
            st.code(prompt_text[:4000])
        # show retrieved snippets with Insert buttons
        if msg.get("retrieved_ref"):
            with st.expander("View medical snippets used for this reply"):
                for j, r in enumerate(msg["retrieved_ref"]):
                    snippet = r["text"][:300].replace("\n"," ")
                    fname = r["meta"].get("filename","")
                    colL, colR = st.columns([5,1])
                    colL.markdown(f"**{fname}** — {escape(snippet)}...")
                    if colR.button("Insert", key=f"insert_ref_{i}_{j}"):
                        # set input for follow-up using snippet
                        st.session_state.user_input = f"Using the snippet from {fname}: {snippet}\n\nFollow-up question: "
        if msg.get("retrieved_sales"):
            with st.expander("View sales snippets used for this reply"):
                for j, r in enumerate(msg["retrieved_sales"]):
                    snippet = r["text"][:300].replace("\n"," ")
                    fname = r["meta"].get("filename","")
                    colL, colR = st.columns([5,1])
                    colL.markdown(f"**{fname}** — {escape(snippet)}...")
                    if colR.button("Insert", key=f"insert_sales_{i}_{j}"):
                        st.session_state.user_input = f"Using the sales snippet from {fname}: {snippet}\n\nFollow-up question: "

st.markdown('</div>', unsafe_allow_html=True)

# --------------------------
# Collapsible RAG summaries (per selected brand)
# --------------------------
with st.expander("📚 Medical References Summary", expanded=False):
    st.text(summarize_docs_preview(docs_ref, bullets=6))
    st.markdown("**Top files (medical):**")
    st.write(", ".join(sorted({m['filename'] for m in metas_ref if m.get('filename')})[:50]) or "None")

with st.expander("💼 Sales Module Summary", expanded=False):
    st.text(summarize_docs_preview(docs_sales, bullets=6))
    st.markdown("**Top files (sales):**")
    st.write(", ".join(sorted({m['filename'] for m in metas_sales if m.get('filename')})[:50]) or "None")

# --------------------------
# Footer disclaimer
# --------------------------
st.markdown("""
<div class="disclaimer-box">
This AI assistant provides general medical and product-related information for educational and sales-training purposes only. It does not provide medical advice, diagnosis, or treatment recommendations. Healthcare Professionals should rely on official product information and clinical judgment. Always refer to the approved prescribing information and your local compliance regulations.
</div>
""", unsafe_allow_html=True)
