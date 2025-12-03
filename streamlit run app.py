# app.py - MR Mentor — Full AI Sales Call Assistant (FINAL)
# Features: Product filter, RAG, summaries, prompt suggestions, feedback, temperature, floating dashboard

import streamlit as st
import os, glob, base64, io, numpy as np
from html import escape
from sklearn.feature_extraction.text import TfidfVectorizer
from datetime import datetime

# --------------------------
# GROQ (optional)
# --------------------------
try:
    from groq import Groq
except:
    Groq = None

GROQ_API_KEY = "Add_GROQ_API_Here"
client = None
if Groq and GROQ_API_KEY and GROQ_API_KEY != "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":
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except:
        client = None

# --------------------------
# Brand definitions
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
# Utilities (no NLTK)
# --------------------------
def load_all_files(base_path):
    data = []
    if not os.path.exists(base_path):
        return data
    for file in glob.glob(base_path + "/**/*.*", recursive=True):
        try:
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
                data.append((os.path.basename(file), text))
        except:
            pass
    return data

def split_into_chunks(text, max_words=160):
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunks.append(" ".join(words[i:i+max_words]))
    return chunks

def build_vector_db_for_paths(paths):
    all_docs = []
    metas = []
    for p in paths:
        for fname, text in load_all_files(p):
            for chunk in split_into_chunks(text):
                all_docs.append(chunk)
                metas.append({"filename": fname, "folder": p})
    if not all_docs:
        all_docs.append("No files found for selected brand.")
        metas.append({"filename": "none", "folder": "none"})
    vectorizer = TfidfVectorizer(stop_words="english")
    vectors = vectorizer.fit_transform(all_docs)
    return all_docs, metas, vectorizer, vectors

def search_docs_custom(query, docs, vectorizer, vectors, metas, top_k=5):
    if not query.strip():
        return []
    try:
        q_vec = vectorizer.transform([query])
        scores = np.dot(vectors, q_vec.T).toarray().ravel()
        top_ids = np.argsort(scores)[::-1][:top_k]
        results = [{"text": docs[i], "meta": metas[i], "score": float(scores[i])} for i in top_ids]
        return results
    except Exception:
        # fallback: naive substring
        out=[]
        q = query.lower()
        for i,d in enumerate(docs[:top_k*10]):
            if q in d.lower():
                out.append({"text":d,"meta":metas[i],"score":1.0})
            if len(out)>=top_k:
                break
        return out

def summarize_docs_preview(docs_list, bullets=5):
    if not docs_list:
        return "No data available."
    lines=[]
    for i,d in enumerate(docs_list[:bullets]):
        snippet = d[:200].replace("\n"," ")
        lines.append(f"- {snippet}{'...' if len(d)>200 else ''}")
    return "\n".join(lines)

# --------------------------
# Streamlit setup & CSS
# --------------------------
st.set_page_config(page_title="MR Mentor — AI Sales Call Assistant", layout="wide")
# background image
def add_bg():
    image_path = ".devcontainer/Visuals/MR mentor final1.png"
    if os.path.exists(image_path):
        with open(image_path,"rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        st.markdown(
            f"""
            <style>
            .stApp {{
                background-image: url('data:image/png;base64,{encoded}');
                background-size: cover;
                background-position: right;
                background-repeat: no-repeat;
            }}
            </style>
            """, unsafe_allow_html=True
        )
add_bg()

st.markdown("""
    <style>
    /* Chat bubbles */
    .user-bubble { background: #DCF2FF; padding: 12px 18px; border-radius: 18px; max-width:78%; margin:8px 0; font-size:14px; margin-left:auto; }
    .ai-bubble { background: #fff; padding: 14px 20px; border-radius: 14px; max-width:78%; margin:10px 0; font-size:14px; border-left:4px solid #FF6A00; box-shadow:0 6px 18px rgba(20,20,40,0.06); }
    .small-muted { font-size:12px; color:#666; margin-top:6px; }
    /* Floating dashboard on right */
    .floating-dashboard {
        position: fixed;
        right: 18px;
        top: 110px;
        width: 300px;
        background: rgba(255,255,255,0.95);
        border-radius: 10px;
        padding: 12px;
        box-shadow: 0 8px 24px rgba(0,0,0,0.12);
        z-index: 9999;
        font-size:13px;
        border:1px solid #eee;
    }
    .prompt-button { background:#f4f4f4; border-radius:8px; padding:8px 10px; margin:4px; display:inline-block; cursor:pointer; }
    .disclaimer-box { position: fixed; bottom: 0; left: 0; width: 100%; background: rgba(255,255,255,0.88); padding:10px 16px; font-size:12px; color:#444; text-align:center; border-top:1px solid #e6e6e6; backdrop-filter: blur(4px); z-index: 9998; }
    .app-content-padding { padding-bottom: 120px; }
    </style>
""", unsafe_allow_html=True)

st.title("💊 MR Mentor — AI Sales Call Assistant")

# --------------------------
# Sidebar: product, HCP filters, temperature, suggestions
# --------------------------
st.sidebar.header("Product & HCP Filters")

selected_brand = st.sidebar.selectbox("Product", list(brand_data.keys()), format_func=lambda x: brand_data[x]["display"])

# HCP fields
hcp_segment = st.sidebar.selectbox("HCP Segment", ["High Value","Medium Value","Low Value","New to Brand"])
hcp_specialty = st.sidebar.selectbox("Specialty", ["GP","Dermatology","Oncology","Immunology","Pulmonology","Other"])
hcp_barriers = st.sidebar.multiselect("HCP Barriers", ["Lack of Awareness","Safety Concerns","Efficacy Doubts","Too Busy","Cost Concerns","Prefers Competitor","No Time for Reps"])
persona = st.sidebar.selectbox("Persona", ["Analytical","Skeptical","Supportive","Passive","Time-Pressed"])
behavior_type = st.sidebar.selectbox("Behavior Type", ["Early Adopter","Follower","Skeptic","Unengaged"])
objection_type = st.sidebar.selectbox("Objection Type", ["Clinical","Safety","Cost","Access","Time","Other"])
visit_type = st.sidebar.selectbox("Visit Type", ["Detailing Visit","Follow-Up Visit","Objection Handling","Awareness Visit"])
engagement = st.sidebar.select_slider("Engagement Level", ["Very Low","Low","Medium","High","Very High"])

st.sidebar.markdown("---")
st.sidebar.subheader("LM Settings")
if "temperature" not in st.session_state:
    st.session_state.temperature = 0.2
st.session_state.temperature = st.sidebar.slider("Temperature", 0.0, 1.5, st.session_state.temperature, 0.05)

st.sidebar.markdown("---")
st.sidebar.subheader("Prompt Suggestions")
# example prompt suggestions
prompt_suggestions = [
    f"Create a short call script for a GP to encourage adoption of {brand_data[selected_brand]['display']}.",
    f"Address the top 2 medical objections for {brand_data[selected_brand]['display']}.",
    f"Summarize eligibility criteria for {brand_data[selected_brand]['display']} (use references only).",
    f"Suggest 3 talking points for a skeptical specialist about {brand_data[selected_brand]['display']}."
]
for i, s in enumerate(prompt_suggestions):
    if st.sidebar.button(s, key=f"ps_{i}"):
        st.session_state.user_input = s  # programmatically set text area content

# --------------------------
# Build RAG DB for selected brand
# --------------------------
ref_path = brand_data[selected_brand]["references_path"]
sales_path = brand_data[selected_brand]["sales_path"]

docs_ref, metas_ref, vector_ref, vectors_ref = build_vector_db_for_paths([ref_path])
docs_sales, metas_sales, vector_sales, vectors_sales = build_vector_db_for_paths([sales_path])

# --------------------------
# Session state initialization
# --------------------------
if "history" not in st.session_state:
    st.session_state.history = []  # list of tuples ("user"/"ai", text, timestamp)
if "feedback" not in st.session_state:
    st.session_state.feedback = {}  # map ai_text -> "useful"/"not_useful"
if "product_counts" not in st.session_state:
    st.session_state.product_counts = {k:0 for k in brand_data.keys()}
if "segment_counts" not in st.session_state:
    st.session_state.segment_counts = {}
if "engagement_values" not in st.session_state:
    st.session_state.engagement_values = []
if "question_count" not in st.session_state:
    st.session_state.question_count = 0

# --------------------------
# Helper: build RAG prompt (Hybrid C)
# --------------------------
def build_rag_prompt(user_question, retrieved_ref, retrieved_sales, context_info):
    instruction = (
        "You are MR Mentor, an AI Sales Call Assistant. Follow these rules:\n"
        "1) Medical factual claims (efficacy, dosing, safety, eligibility) MUST be grounded in MEDICAL_SNIPPETS. "
        "When using them, quote a short excerpt (<=40 words) and include filename in parentheses.\n"
        "2) Sales guidance may use model reasoning but label it as 'Sales Guidance'.\n"
        "3) If no medical support is available, say so and avoid hallucination.\n"
        "4) Use bullets and provide a 1-2 sentence verbatim script at the end.\n\n"
    )
    med_block = "\n".join([f"---\n[{i+1}] ({r['meta']['filename']})\n{r['text']}" for i,r in enumerate(retrieved_ref)]) or "(no medical snippets)"
    sales_block = "\n".join([f"---\n[{i+1}] ({r['meta']['filename']})\n{r['text']}" for i,r in enumerate(retrieved_sales)]) or "(no sales snippets)"
    prompt = (
        instruction
        + "\nHCP & CONTEXT:\n" + context_info + "\n\n"
        + "USER QUESTION:\n" + user_question + "\n\n"
        + "MEDICAL_SNIPPETS:\n" + med_block + "\n\n"
        + "SALES_SNIPPETS:\n" + sales_block + "\n\n"
        + "Produce: 1) Brief summary, 2) Medical evidence (quote+file) if applicable, 3) Sales Guidance, 4) 1-2 sentence script.\n"
    )
    return prompt

# --------------------------
# Call LLM (GROQ) or fallback
# --------------------------
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
        except Exception as e:
            # fall through to offline fallback
            pass
    # fallback: show retrieved snippets and context instead of hallucination
    return "⚠️ (No LLM available) - offline fallback. See retrieved snippets below for grounding."

# --------------------------
# Generate response using RAG
# --------------------------
def generate_ai_response(user_input, selected_brand, context_info):
    # retrieve separately for medical and sales
    retrieved_ref = search_docs_custom(user_input, docs_ref, vector_ref, vectors_ref, metas_ref, top_k=5)
    retrieved_sales = search_docs_custom(user_input, docs_sales, vector_sales, vectors_sales, metas_sales, top_k=5)
    prompt = build_rag_prompt(user_input, retrieved_ref, retrieved_sales, context_info)
    ai_text = call_model(prompt, temperature=st.session_state.temperature)
    # return results and metadata for UI
    return ai_text, retrieved_ref, retrieved_sales, prompt

# --------------------------
# Input area and suggestions
# --------------------------
st.markdown("### Conversation")
st.markdown('<div class="app-content-padding">', unsafe_allow_html=True)

# Use a text area with key 'user_input' so that prompt buttons can set it
if "user_input" not in st.session_state:
    st.session_state.user_input = ""

with st.form("input_form", clear_on_submit=False):
    user_input = st.text_area("Ask MR Mentor something...", value=st.session_state.user_input, key="user_input", height=120)
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        # prepare context
        context = (
            f"Product: {brand_data[selected_brand]['display']}\n"
            f"Segment: {hcp_segment}\nSpecialty: {hcp_specialty}\nBarriers: {', '.join(hcp_barriers) if hcp_barriers else 'None'}\n"
            f"Persona: {persona}\nBehavior: {behavior_type}\nObjection: {objection_type}\nVisit Type: {visit_type}\nEngagement: {engagement}"
        )
        ai_text, retrieved_ref, retrieved_sales, prompt_used = generate_ai_response(user_input, selected_brand, context)
        timestamp = datetime.utcnow().isoformat()
        st.session_state.history.append(("user", user_input, timestamp))
        st.session_state.history.append(("ai", ai_text, timestamp))
        # update analytics
        st.session_state.product_counts[selected_brand] = st.session_state.product_counts.get(selected_brand,0) + 1
        st.session_state.segment_counts[hcp_segment] = st.session_state.segment_counts.get(hcp_segment,0) + 1
        # map engagement to numeric
        eng_map = {"Very Low":1,"Low":2,"Medium":3,"High":4,"Very High":5}
        st.session_state.engagement_values.append(eng_map.get(engagement,3))
        st.session_state.question_count += 1
        # store last retrieval for UI insertion
        st.session_state._last_retrieved_ref = retrieved_ref
        st.session_state._last_retrieved_sales = retrieved_sales
        st.session_state._last_prompt = prompt_used
        # reset local user_input (keep in session state if desired)
        st.session_state.user_input = ""

# --------------------------
# Display chat history with feedback buttons and snippet insertion
# --------------------------
for idx, item in enumerate(st.session_state.history):
    role, text, ts = item
    if role == "user":
        st.markdown(f"<div class='user-bubble'>{escape(text)}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='ai-bubble'>{escape(text)}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='small-muted'>Generated: {ts}</div>", unsafe_allow_html=True)
        # feedback buttons
        fb_col1, fb_col2, fb_col3 = st.columns([1,1,4])
        if fb_col1.button("👍 Useful", key=f"useful_{idx}"):
            st.session_state.feedback[text] = "useful"
        if fb_col2.button("👎 Not Useful", key=f"notuseful_{idx}"):
            st.session_state.feedback[text] = "not_useful"
        # show "Show raw prompt" toggle
        if fb_col3.button("Show Prompt Used", key=f"showprompt_{idx}"):
            prompt_text = st.session_state._last_prompt if "_last_prompt" in st.session_state else "(prompt not available)"
            st.code(prompt_text[:4000])

        # show retrieved snippets for that answer if available (last retrieval)
        if "_last_retrieved_ref" in st.session_state:
            with st.expander("View last retrieved Medical snippets"):
                for i, r in enumerate(st.session_state._last_retrieved_ref):
                    snippet = r["text"][:320].replace("\n"," ")
                    filemeta = r["meta"].get("filename","")
                    score = r.get("score",0)
                    cols = st.columns([5,1])
                    cols[0].write(f"**{filemeta}** — {snippet}...")
                    if cols[1].button("Insert", key=f"ins_ref_{idx}_{i}"):
                        # Insert snippet into the input area for follow-up
                        st.session_state.user_input = f"Using this snippet: {snippet}\n\nFollow-up question: "
        if "_last_retrieved_sales" in st.session_state:
            with st.expander("View last retrieved Sales snippets"):
                for i, r in enumerate(st.session_state._last_retrieved_sales):
                    snippet = r["text"][:320].replace("\n"," ")
                    filemeta = r["meta"].get("filename","")
                    cols = st.columns([5,1])
                    cols[0].write(f"**{filemeta}** — {snippet}...")
                    if cols[1].button("Insert", key=f"ins_sales_{idx}_{i}"):
                        st.session_state.user_input = f"Using this sales snippet: {snippet}\n\nFollow-up question: "

# --------------------------
# RAG Summaries (per selected brand)
# --------------------------
with st.expander("📚 Medical References Summary", expanded=False):
    st.text(summarize_docs_preview(docs_ref, bullets=6))
    # show top 5 files loaded
    files_loaded = sorted({m['filename'] for m in metas_ref if m.get('filename')})
    if files_loaded:
        st.markdown("**Files loaded (medical):**")
        st.write(", ".join(files_loaded[:20]))

with st.expander("💼 Sales Module Summary", expanded=False):
    st.text(summarize_docs_preview(docs_sales, bullets=6))
    files_loaded_sales = sorted({m['filename'] for m in metas_sales if m.get('filename')})
    if files_loaded_sales:
        st.markdown("**Files loaded (sales):**")
        st.write(", ".join(files_loaded_sales[:20]))

st.markdown('</div>', unsafe_allow_html=True)

# --------------------------
# Floating Mini Dashboard (Right side)
# --------------------------
# compute analytics
most_selected_product = max(st.session_state.product_counts.items(), key=lambda x: x[1])[0] if any(v>0 for v in st.session_state.product_counts.values()) else None
most_selected_product_display = brand_data[most_selected_product]['display'] if most_selected_product else "—"

segment_distribution = st.session_state.segment_counts
questions = st.session_state.question_count
useful_count = sum(1 for v in st.session_state.feedback.values() if v=="useful")
notuseful_count = sum(1 for v in st.session_state.feedback.values() if v=="not_useful")
avg_engagement = (sum(st.session_state.engagement_values)/len(st.session_state.engagement_values)) if st.session_state.engagement_values else 0

dashboard_html = f"""
<div class="floating-dashboard">
  <h4 style="margin:6px 0 8px 0;">📊 Mini Dashboard</h4>
  <div><strong>Questions:</strong> {questions}</div>
  <div><strong>Top Product:</strong> {escape(most_selected_product_display)}</div>
  <div><strong>Useful / Not Useful:</strong> {useful_count} / {notuseful_count}</div>
  <div><strong>Avg Engagement:</strong> {avg_engagement:.2f} / 5</div>
  <div style="margin-top:8px;"><strong>HCP segments:</strong></div>
"""
for seg, cnt in segment_distribution.items():
    dashboard_html += f"<div style='font-size:13px; color:#333;'>{escape(seg)}: {cnt}</div>"
dashboard_html += """
  <div style="margin-top:10px;">
    <small class="small-muted">Tip: click Prompt Suggestions in the sidebar to quickly insert example prompts.</small>
  </div>
</div>
"""
st.markdown(dashboard_html, unsafe_allow_html=True)

# --------------------------
# DISCLAIMER (footer)
# --------------------------
st.markdown("""
<div class="disclaimer-box">
This AI assistant provides general medical and product-related information for educational and sales-training purposes only. It does not provide medical advice, diagnosis, or treatment recommendations. Healthcare Professionals should rely on official product information and clinical judgment. Always refer to the approved prescribing information and your local compliance regulations.
</div>
""", unsafe_allow_html=True)
