# app.py - MR Mentor AI Sales Call Assistant (Full Integrated Version)

import streamlit as st
import os, re, glob, base64
import numpy as np
from html import escape
from sklearn.feature_extraction.text import TfidfVectorizer

# --------------------------
# 1. GROQ Setup
# --------------------------
try:
    from groq import Groq
except:
    Groq = None

GROQ_API_KEY = "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"
client = None
if Groq and GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except:
        client = None

# --------------------------
# 2. Page config
# --------------------------
st.set_page_config(
    page_title="💊 MR Mentor — AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --------------------------
# 3. Load RAG documents
# --------------------------
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
    chunks, current = [], []
    for w in words:
        current.append(w)
        if len(current) >= max_words:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks

def build_vector_db():
    all_docs = []

    reference_paths = [
        ".devcontainer/references/jemperli",
        ".devcontainer/references/shingrix",
        ".devcontainer/references/trelegy"
    ]
    
    sales_paths = [
        ".devcontainer/SalesModule/jemperli",
        ".devcontainer/SalesModule/shingrix",
        ".devcontainer/SalesModule/trelegy"
    ]

    for p in reference_paths + sales_paths:
        for fname, text in load_all_files(p):
            for chunk in split_into_chunks(text):
                all_docs.append(chunk)

    if not all_docs:
        all_docs.append("Empty RAG dataset. No files found.")

    vectorizer = TfidfVectorizer(stop_words="english")
    vectors = vectorizer.fit_transform(all_docs)

    return all_docs, vectorizer, vectors

docs, vectorizer, vectors = build_vector_db()

def search_docs(query, top_k=5):
    if not query.strip():
        return []
    q_vec = vectorizer.transform([query])
    scores = np.dot(vectors, q_vec.T).toarray().ravel()
    top_ids = np.argsort(scores)[::-1][:top_k]
    return [docs[i] for i in top_ids]

# --------------------------
# 4. Generate AI response (Hybrid RAG)
# --------------------------
def generate_ai_response(user_input, context_info, temperature=0.7):
    retrieved = search_docs(user_input, top_k=5)
    rag_text = "\n\n--- Retrieved Relevant Medical & Sales Insights ---\n"
    for idx, chunk in enumerate(retrieved):
        rag_text += f"\n[{idx+1}] {chunk}\n"

    prompt = f"""
You are MR Mentor, an AI Sales Coach for pharmaceutical representatives.

Follow **Hybrid RAG Mode**:
- **Medical accuracy** must come ONLY from retrieved RAG data.
- **Sales coaching** can include your own reasoning.
- **Conversation style** can be natural.
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
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return res.choices[0].message["content"]
        except:
            pass
    return "⚠️ Running in offline/fallback mode — No GROQ response available."

# --------------------------
# 5. Background Image
# --------------------------
def add_bg():
    image_path = ".devcontainer/Visuals/MR mentor final1.png"
    if os.path.exists(image_path):
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: url('data:image/png;base64,{encoded}');
            background-size: cover;
            background-position: right;
            background-repeat: no-repeat;
        }}
        </style>
        """, unsafe_allow_html=True)

add_bg()

# --------------------------
# 6. CSS for chat bubbles
# --------------------------
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
.citation-box {
    font-size: 12px;
    color: gray;
    margin-left: 20px;
}
</style>
""", unsafe_allow_html=True)

# --------------------------
# 7. Sidebar: HCP + Product + Dashboard + Temperature
# --------------------------
st.sidebar.title("HCP & Session Settings")

hcp_segment = st.sidebar.selectbox("HCP Segment:", ["High Value","Medium Value","Low Value","New to Brand"])
hcp_specialty = st.sidebar.selectbox("Specialty:", ["GP","Dermatology","Oncology","Immunology","Pulmonology","Other"])
hcp_barriers = st.sidebar.multiselect("HCP Barriers:", ["Lack of Awareness","Safety Concerns","Efficacy Doubts","Too Busy","Cost Concerns","Prefers Competitor","No Time for Reps"])
persona = st.sidebar.selectbox("Persona:", ["Analytical","Skeptical","Supportive","Passive","Time-Pressed"])
behavior_type = st.sidebar.selectbox("Behavior Type:", ["Early Adopter","Follower","Skeptic","Unengaged"])
objection_type = st.sidebar.selectbox("Objection Type:", ["Clinical","Safety","Cost","Access","Time","Other"])
visit_type = st.sidebar.selectbox("Visit Type:", ["Detailing Visit","Follow-Up Visit","Objection Handling","Awareness Visit"])
engagement = st.sidebar.select_slider("Engagement Level:", ["Very Low","Low","Medium","High","Very High"])

selected_product = st.sidebar.selectbox("Product Filter:", ["Shingrix","Jemperli","Trelegy","All Products"])
temperature = st.sidebar.slider("Temperature:", 0.0, 1.0, 0.7, 0.05)

# Mini Dashboard
with st.sidebar.expander("📊 Mini Dashboard (Simple)", expanded=True):
    st.write(f"**Total Questions Asked:** {len(st.session_state.get('history', []))//2}")
    st.write(f"**Selected Product:** {selected_product}")
    st.write(f"**Segment Selected:** {hcp_segment}")
    st.write(f"**Engagement Level:** {engagement}")
    st.write(f"**Barriers Count:** {len(hcp_barriers)}")
    st.write(f"**Persona:** {persona}")

# --------------------------
# 8. Initialize chat history
# --------------------------
if "history" not in st.session_state:
    st.session_state.history = []

if "user_input" not in st.session_state:
    st.session_state.user_input = ""

# --------------------------
# 9. RAG summaries per product
# --------------------------
def get_rag_summary(path):
    combined_text = ""
    if os.path.exists(path):
        for f in sorted(os.listdir(path)):
            if f.lower().endswith((".txt",".pdf")):
                try:
                    with open(os.path.join(path,f),"r",encoding="utf-8", errors="ignore") as fh:
                        combined_text += fh.read() + "\n"
                except:
                    pass
    # Simple top-6 sentence summary
    sents = re.split(r'(?<=[.!?])\s+', combined_text)
    return "\n".join(["- "+s for s in sents[:6]]) if sents else "No content available."

# --------------------------
# 10. Prompt suggestions
# --------------------------
def make_suggestions():
    return [
        "Generate call flow for this HCP segment.",
        "Summarize objections and how to address them.",
        "Key talking points for selected product.",
        "Draft short adoption message for this specialty.",
        "Highlight patient eligibility criteria."
    ]

# --------------------------
# 11. Main Interface
# --------------------------
st.header("💡 Prompt Suggestions")
with st.expander("Click to view suggestions", expanded=False):
    cols = st.columns(3)
    for i,s in enumerate(make_suggestions()):
        col = cols[i%3]
        if col.button(s, key=f"sugg_{i}"):
            st.session_state.user_input = s

user_input = st.text_input("Ask MR Mentor something...", key="user_input")

def process_message(message):
    context_info = f"""
Segment: {hcp_segment}
Specialty: {hcp_specialty}
Barriers: {', '.join(hcp_barriers) if hcp_barriers else 'None'}
Persona: {persona}
Behavior: {behavior_type}
Objection: {objection_type}
Visit Type: {visit_type}
Engagement: {engagement}
Product: {selected_product}
"""
    ai_answer = generate_ai_response(message, context_info, temperature=temperature)
    st.session_state.history.append(("user", message))
    st.session_state.history.append(("ai", ai_answer))

if st.button("Send"):
    if st.session_state.user_input.strip():
        process_message(st.session_state.user_input.strip())
        st.session_state.user_input = ""  # safe clearing after processing

# --------------------------
# 12. RAG Summaries in interface
# --------------------------
st.header("📚 RAG Summaries")
product_paths = {
    "Shingrix": (".devcontainer/references/shingrix", ".devcontainer/SalesModule/shingrix"),
    "Jemperli": (".devcontainer/references/jemperli", ".devcontainer/SalesModule/jemperli"),
    "Trelegy": (".devcontainer/references/trelegy", ".devcontainer/SalesModule/trelegy")
}

for prod, (ref_path, sales_path) in product_paths.items():
    if selected_product != "All Products" and selected_product != prod:
        continue
    with st.expander(f"📖 {prod} — Medical Reference Summary", expanded=False):
        st.text(get_rag_summary(ref_path))
    with st.expander(f"💼 {prod} — Sales Module Summary", expanded=False):
        st.text(get_rag_summary(sales_path))

# --------------------------
# 13. Display chat
# --------------------------
st.header("💬 Conversation")
for role, msg in st.session_state.history:
    if role == "user":
        st.markdown(f"<div class='user-bubble'>{escape(msg)}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='ai-bubble'>{msg}</div>", unsafe_allow_html=True)

# --------------------------
# 14. Disclaimer
# --------------------------
st.markdown("""
<div style='font-size:12px;color:gray;margin-top:20px;'>
This AI assistant provides general medical and product-related information for educational and sales-training purposes only. 
It does not provide medical advice, diagnosis, or treatment recommendations. 
Healthcare Professionals should rely on official product information and clinical judgment. 
Always refer to the approved prescribing information and your local compliance regulations.
</div>
""", unsafe_allow_html=True)
