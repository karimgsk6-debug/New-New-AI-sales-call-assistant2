# app_full_with_prompts.py - AI Sales Call Assistant with Prompt Suggestions
import streamlit as st
import os, re, base64
from datetime import datetime
from html import escape

# Optional imports
try:
    from groq import Groq
except:
    Groq = None

try:
    from PyPDF2 import PdfReader
except:
    PdfReader = None

# -------------------------
# Page config
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# -------------------------
# Session defaults
# -------------------------
def _init_session():
    defaults = {
        "chat_history": [],
        "main_input": "",
        "selected_brand": "shingrix",
        "temperature": 0.95,
        "search_mode": "deep",
        "medical_summary": "",
        "sales_summary": "",
        "prompt_suggestions": [
            "Summarize the latest clinical data",
            "Explain key sales objections",
            "List product differentiators",
            "Provide HCP engagement tips",
            "Generate Q&A for sales call"
        ]
    }
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

_init_session()

# -------------------------
# CSS for avatars & chat
# -------------------------
st.markdown("""
<style>
.chat-bubble-user{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }
.ai-message { display:flex; align-items:flex-start; gap:12px; margin:10px 0; }
.ai-avatar { width:52px; height:52px; border-radius:50%; box-shadow: 0 0 12px rgba(0,255,255,0.6); flex-shrink:0; animation:holoPulse 2.5s infinite ease-in-out; }
@keyframes holoPulse { 0% { box-shadow:0 0 8px rgba(0,255,255,0.35);} 50% { box-shadow:0 0 22px rgba(0,255,255,0.9);} 100% { box-shadow:0 0 8px rgba(0,255,255,0.35);} }
.ai-bubble { background: rgba(255,255,255,0.06); border:1px solid rgba(0,255,255,0.18); color:#E6FBFF; padding:14px; border-radius:14px; max-width:90%; white-space:pre-wrap; }
.user-bubble{ background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; }
.prompt-button{ margin:2px; }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Groq client
# -------------------------
def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY", "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") or (st.secrets.get("GROQ_API_KEY") if "GROQ_API_KEY" in st.secrets else "")
    if not api_key or Groq is None:
        return None
    try:
        return Groq(api_key=api_key)
    except:
        return None

# -------------------------
# Summarization helper
# -------------------------
def summarize_text(text, bullets=6):
    sents = re.split(r'(?<=[.!?])\s+', text)
    return "\n".join(["- "+s for s in sents[:bullets]])

# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    st.header("Options & Filters")
    brands = ["shingrix","jemperli","trelegy"]
    st.session_state.selected_brand = st.selectbox("Brand", brands, index=brands.index(st.session_state.selected_brand), key="brand_sel")
    st.session_state.temperature = st.slider("Temperature", 0.0, 1.0, st.session_state.temperature, 0.05, key="temp_sel")
    if st.button("🗑️ Clear Chat", key="clear_chat"):
        st.session_state.chat_history = []
        st.experimental_rerun()

# -------------------------
# Title
# -------------------------
st.markdown(f"""
<div style="background: rgba(255,255,255,0.85); padding:12px; border-radius:10px; text-align:center; margin-bottom:12px;">
<h2>💡 AI Sales Call Assistant — {st.session_state.selected_brand.title()}</h2>
</div>
""", unsafe_allow_html=True)

# -------------------------
# Prompt Suggestions (Collapsible)
# -------------------------
with st.expander("💡 Prompt Suggestions", expanded=True):
    for i, s in enumerate(st.session_state.prompt_suggestions):
        if st.button(s, key=f"prompt_{i}"):
            st.session_state.main_input = s

# -------------------------
# Chat input & AI response
# -------------------------
user_input = st.text_area("Ask the AI assistant...", value=st.session_state.main_input, key="main_input", height=80)

if st.button("Send", key="send_button") and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input})
    # AI response
    client = get_groq_client()
    ai_text = ""
    if client:
        try:
            resp = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[
                    {"role":"system","content":"You are a helpful assistant."},
                    {"role":"user","content":user_input[:12000]}
                ],
                temperature=st.session_state.temperature
            )
            ai_text = getattr(getattr(resp.choices[0],"message",{}),"content","") or getattr(resp.choices[0],"text","")
        except:
            ai_text = "Failed to generate AI response. Try again."
    else:
        ai_text = "Groq API not configured."

    st.session_state.chat_history.append({"role":"ai","content":ai_text})
    st.session_state.main_input = ""

# -------------------------
# Render chat
# -------------------------
for msg in st.session_state.chat_history:
    if msg["role"]=="user":
        st.markdown(f'<div class="user-bubble">{escape(msg["content"])}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="ai-message">
            <img src="https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/Visuals/futuristic_hologram_ai.gif" class="ai-avatar">
            <div class="ai-bubble">{escape(msg["content"])}</div>
        </div>
        """, unsafe_allow_html=True)
