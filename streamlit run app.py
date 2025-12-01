# app.py - Full AI Sales Call Assistant (with Product Filter + RAG Summaries)

import streamlit as st
import os, glob, base64, io, numpy as np
from html import escape
from sklearn.feature_extraction.text import TfidfVectorizer

# --------------------------
# IMPORT GROQ
# --------------------------
try:
    from groq import Groq
except:
    Groq = None

# --------------------------
# 1. SETUP GROQ API
# --------------------------
GROQ_API_KEY = "Add_GROQ_API_Here"
client = None
if Groq and GROQ_API_KEY and GROQ_API_KEY != "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":
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except:
        client = None

# ========================================================================
# 2. PRODUCTS & PATHS
# ========================================================================
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
    }
}

# ========================================================================
# 3. RAG UTILITIES (NO NLTK)
# ========================================================================

def load_all_files(base_path):
    data = []
    for file in glob.glob(base_path + "/**/*.*", recursive=True):
        try:
            with open(file, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
                data.append((os.path.basename(file), text))
        except:
            pass
    return data

def split_into_chunks(text, max_words=180):
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunks.append(" ".join(words[i:i+max_words]))
    return chunks

def build_vector_db_for_paths(paths):
    all_docs = []
    for p in paths:
        for fname, text in load_all_files(p):
            for chunk in split_into_chunks(text):
                all_docs.append(chunk)
    if not all_docs:
        all_docs.append("No files found for selected brand.")
    vectorizer = TfidfVectorizer(stop_words="english")
    vectors = vectorizer.fit_transform(all_docs)
    return all_docs, vectorizer, vectors

# ========================================================================
# 4. STREAMLIT UI — BACKGROUND + STYLES
# ========================================================================

def add_bg():
    image_path = ".devcontainer/Visuals/MR mentor final1.png"
    if os.path.exists(image_path):
        with open(image_path, "rb") as f:
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
    .user-bubble {
        background: #DCF2FF;
        padding: 12px 18px;
        border-radius: 18px;
        max-width: 78%;
        margin: 8px 0;
        font-size: 16px;
    }
    .ai-bubble {
        background: #FFFFFF;
        padding: 14px 20px;
        border-radius: 18px;
        max-width: 78%;
        margin: 10px 0;
        font-size: 17px;
        border-left: 4px solid #FF6A00;
        box-shadow: 0 0 6px rgba(0,0,0,0.08);
    }
    .disclaimer-box {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background: rgba(255,255,255,0.88);
        padding: 10px 16px;
        font-size: 12px;
        color: #444;
        text-align: center;
        border-top: 1px solid #e6e6e6;
        backdrop-filter: blur(4px);
        z-index: 9999;
    }
    .app-content-padding { padding-bottom: 120px; }
    </style>
""", unsafe_allow_html=True)

st.title("💊 MR Mentor — AI Sales Call Assistant")

# ========================================================================
# 5. SIDEBAR — PRODUCT + HCP INFO
# ========================================================================

st.sidebar.title("Select Product & HCP Profile")

# 1. Product filter
selected_brand = st.sidebar.selectbox(
    "Product:",
    list(brand_data.keys()),
    format_func=lambda x: brand_data[x]["display"]
)

# 2. HCP Profile
hcp_segment = st.sidebar.selectbox("HCP Segment:", ["High Value","Medium Value","Low Value","New to Brand"])
hcp_specialty = st.sidebar.selectbox("Specialty:", ["GP","Dermatology","Oncology","Immunology","Pulmonology","Other"])
hcp_barriers = st.sidebar.multiselect("HCP Barriers:", ["Lack of Awareness","Safety Concerns","Efficacy Douts","Too Busy","Cost Concerns","Prefers Competitor","No Time for Reps"])
persona = st.sidebar.selectbox("Persona:", ["Analytical","Skeptical","Supportive","Passive","Time-Pressed"])
behavior_type = st.sidebar.selectbox("Behavior Type:", ["Early Adopter","Follower","Skeptic","Unengaged"])
objection_type = st.sidebar.selectbox("Objection Type:", ["Clinical","Safety","Cost","Access","Time","Other"])
visit_type = st.sidebar.selectbox("Visit Type:", ["Detailing Visit","Follow-Up Visit","Objection Handling","Awareness Visit"])
engagement = st.sidebar.select_slider("Engagement Level:", ["Very Low","Low","Medium","High","Very High"])

# ========================================================================
# 6. BUILD RAG VECTOR DB FOR SELECTED BRAND
# ========================================================================

ref_path = brand_data[selected_brand]["references_path"]
sales_path = brand_data[selected_brand]["sales_path"]

docs_ref, vector_ref, vectors_ref = build_vector_db_for_paths([ref_path])
docs_sales, vector_sales, vectors_sales = build_vector_db_for_paths([sales_path])

def search_docs_custom(query, docs, vectorizer, vectors, top_k=5):
    if not query.strip(): return []
    q_vec = vectorizer.transform([query])
    scores = np.dot(vectors, q_vec.T).toarray().ravel()
    top_ids = np.argsort(scores)[::-1][:top_k]
    return [docs[i] for i in top_ids]

# Summarize function
def summarize_docs(docs_list, bullets=5):
    if not docs_list: return "No data available."
    summary = []
    for doc in docs_list[:bullets]:
        summary.append(f"- {doc[:200]}{'...' if len(doc)>200 else ''}")
    return "\n".join(summary)

# ========================================================================
# 7. AI RESPONSE
# ========================================================================

def generate_ai_response(user_input, context_info):
    retrieved_ref = search_docs_custom(user_input, docs_ref, vector_ref, vectors_ref, top_k=5)
    retrieved_sales = search_docs_custom(user_input, docs_sales, vector_sales, vectors_sales, top_k=5)

    rag_text = "\n\n--- Retrieved Relevant Medical & Sales Insights ---\n"
    rag_text += "\n\n[Medical References]\n" + "\n".join([f"[{i+1}] {txt}" for i,txt in enumerate(retrieved_ref)])
    rag_text += "\n\n[Sales Module]\n" + "\n".join([f"[{i+1}] {txt}" for i,txt in enumerate(retrieved_sales)])

    prompt = f"""
You are MR Mentor, an AI Sales Coach for pharmaceutical representatives.

Follow **Hybrid RAG Mode**:
- Medical accuracy must come ONLY from retrieved RAG data.
- Sales coaching can include your own reasoning.
- Conversation style can be natural.
- Never invent medical facts not found in retrieved documents.

HCP & Visit Context:
{context_info}

User Question:
{user_input}

{rag_text}

Now produce:
1. A crisp, structured, high-value answer.
2. Medical claims ONLY from retrieved RAG evidence.
3. Tailored sales guidance based on HCP segment, barriers & specialty.
"""

    if client:
        try:
            res = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt}]
            )
            return res.choices[0].message["content"]
        except:
            pass
    return "⚠️ Running in offline/fallback mode — No GROQ response available."

# ========================================================================
# 8. MAIN CHAT INTERFACE
# ========================================================================

if "history" not in st.session_state:
    st.session_state.history = []

user_msg = st.text_input("Ask MR Mentor something...")

if user_msg:
    context = f"""
Segment: {hcp_segment}
Specialty: {hcp_specialty}
Barriers: {', '.join(hcp_barriers) if hcp_barriers else 'None'}
Persona: {persona}
Behavior: {behavior_type}
Objection: {objection_type}
Visit Type: {visit_type}
Engagement: {engagement}
Product: {brand_data[selected_brand]['display']}
"""
    ai_answer = generate_ai_response(user_msg, context)
    st.session_state.history.append(("user", user_msg))
    st.session_state.history.append(("ai", ai_answer))

# Display chat
st.markdown("### Conversation")
st.markdown('<div class="app-content-padding">', unsafe_allow_html=True)
for role, msg in st.session_state.history:
    if role == "user":
        st.markdown(f"<div class='user-bubble'>{escape(msg)}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='ai-bubble'>{msg}</div>", unsafe_allow_html=True)

# RAG summaries collapsible
with st.expander("📚 Medical References Summary"):
    st.text(summarize_docs(docs_ref))

with st.expander("💼 Sales Module Summary"):
    st.text(summarize_docs(docs_sales))

st.markdown('</div>', unsafe_allow_html=True)

# ========================================================================
# 9. DISCLAIMER
# ========================================================================
st.markdown("""
<div class="disclaimer-box">
This AI assistant provides general medical and product-related information for educational and sales-training purposes only. It does not provide medical advice, diagnosis, or treatment recommendations. Healthcare Professionals should rely on official product information and clinical judgment. Always refer to the approved prescribing information and your local compliance regulations.
</div>
""", unsafe_allow_html=True)
