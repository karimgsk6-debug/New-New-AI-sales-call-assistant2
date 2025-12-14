# app_final_ready.py — AI Sales Call Assistant (RAG-Enhanced, Product-Specific)

import streamlit as st
import os, re, base64
from html import escape

# -------------------------
# Optional imports
# -------------------------
try:
    from groq import Groq
except Exception:
    Groq = None

try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

# -------------------------
# Page config
# -------------------------
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------
# Session init
# -------------------------
def init_session():
    defaults = {
        "chat_history": [],
        "main_input": "",
        "selected_brand": "shingrix",
        "tone": "executive",
        "hcp_persona": "Friendly",
        "hcp_personality": "Friendly",
        "medical_summary": "",
        "sales_summary": "",
        "temperature": 0.85
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

init_session()

# -------------------------
# Assets
# -------------------------
AI_AVATAR = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

# -------------------------
# CSS
# -------------------------
st.markdown("""
<style>
.ai-message{display:flex;gap:12px;margin:10px 0}
.ai-avatar{width:52px;height:52px;border-radius:50%;box-shadow:0 0 16px rgba(0,255,255,.7)}
.ai-bubble{background:rgba(255,255,255,.07);border:1px solid rgba(0,255,255,.25);
color:#E6FBFF;padding:14px;border-radius:14px;max-width:90%}
.user-bubble{background:rgba(0,0,0,.06);padding:10px 14px;border-radius:12px;margin:8px 0}
.step-title{font-weight:700;color:#BFF;margin-top:12px}
.story{font-style:italic;color:#DFF;margin:6px 0}
.objection{background:rgba(255,240,220,.06);padding:8px;border-radius:8px;margin:6px 0}
</style>
""", unsafe_allow_html=True)

# -------------------------
# Background
# -------------------------
def set_background(path):
    if not os.path.exists(path):
        return
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()
    st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        background:url("data:image/png;base64,{encoded}");
        background-size:cover;
    }}
    </style>
    """, unsafe_allow_html=True)

set_background(BACKGROUND_PATH)

# -------------------------
# Groq client
# -------------------------
def get_client():
    key = os.getenv("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY", "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")
    if not key or Groq is None:
        return None
    return Groq(api_key=key)

# -------------------------
# Brand configuration
# -------------------------
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "call_flow": [
            "Prepare",
            "Engage",
            "Create Opportunities",
            "Influence",
            "Impact GSO",
            "Analyze"
        ],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/",
        "objections": {
            "safety": "reactogenicity concerns",
            "urgency": "HZ perceived as low priority",
            "cost": "budget and reimbursement"
        }
    }
}

# -------------------------
# File helpers
# -------------------------
def read_text(path):
    if not os.path.exists(path):
        return ""
    if path.lower().endswith(".pdf") and PdfReader:
        reader = PdfReader(path)
        return " ".join(p.extract_text() or "" for p in reader.pages)
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()

def load_rag_context(brand):
    conf = brand_data[brand]
    context = ""

    for folder in [conf["references_path"], conf["sales_path"]]:
        if not os.path.exists(folder):
            continue
        for file in os.listdir(folder):
            if file.lower().endswith((".pdf", ".txt")):
                context += read_text(os.path.join(folder, file)) + "\n"

    return context[:12000]

# -------------------------
# SMART PROMPT BUILDER
# -------------------------
def build_sales_prompt(user_query, brand):
    conf = brand_data[brand]
    rag_context = load_rag_context(brand)

    return f"""
You are an expert pharmaceutical sales coach.

TASK:
Generate a FULL, REALISTIC SALES CALL SCENARIO for {conf['display']}.

RULES:
- Use the selling steps ONLY as a STRUCTURE, not definitions
- Be conversational, confident, and action-oriented
- Use storytelling and examples
- Adapt to:
  • HCP persona: {st.session_state.hcp_persona}
  • HCP personality: {st.session_state.hcp_personality}
  • Tone: {st.session_state.tone}

SELLING FRAME:
{", ".join(conf["call_flow"])}

CONTENT REQUIREMENTS PER STEP:
- What the rep says
- Likely HCP reaction
- How the rep adapts
- Practical phrases the rep can use
- Soft call-to-action where appropriate

OBJECTIONS TO HANDLE:
{conf["objections"]}

REFERENCE CONTEXT (do NOT quote directly, use for grounding):
{rag_context}

USER REQUEST:
{user_query}
"""

# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    brand = st.selectbox("Brand", list(brand_data.keys()))
    st.session_state.selected_brand = brand
    st.session_state.hcp_persona = st.selectbox(
        "HCP Persona",
        ["Friendly", "Evidence-led", "Time-pressured", "Skeptical", "Early-adopter"]
    )
    st.session_state.hcp_personality = st.selectbox(
        "HCP Personality",
        ["Assertive", "Masked", "Detail-oriented", "Skeptic", "Relationship-driven"]
    )
    st.session_state.tone = st.selectbox(
        "Tone",
        ["executive", "coaching", "persuasive", "clinical"]
    )

# -------------------------
# Main UI
# -------------------------
st.markdown(f"## 💡 AI Sales Call Assistant — {brand_data[brand]['display']}")

user_input = st.text_area("Ask for a sales call, objection handling, or scenario")

if st.button("Send") and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    client = get_client()
    ai_text = "AI generation failed."

    if client:
        prompt = build_sales_prompt(user_input, brand)
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role": "system", "content": "You are a high-performing pharma sales strategist."},
                {"role": "user", "content": prompt}
            ],
            temperature=st.session_state.temperature
        )
        ai_text = response.choices[0].message.content

    st.session_state.chat_history.append({"role": "ai", "content": ai_text})
    st.session_state.main_input = ""

# -------------------------
# Chat rendering
# -------------------------
for msg in st.session_state.chat_history:
    if msg["role"] == "user":
        st.markdown(f"<div class='user-bubble'>{escape(msg['content'])}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="ai-message">
            <img src="{AI_AVATAR}" class="ai-avatar"/>
            <div class="ai-bubble">{msg['content']}</div>
        </div>
        """, unsafe_allow_html=True)

# -------------------------
# Footer
# -------------------------
st.markdown(
    "<div style='font-size:12px;color:#aac'>Internal use only — not promotional</div>",
    unsafe_allow_html=True
)
