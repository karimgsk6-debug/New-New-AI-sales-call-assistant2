import streamlit as st
from datetime import datetime
import base64, os, io, tempfile
from PyPDF2 import PdfReader
import requests

# -----------------------------
# --- APP CONFIG ---
# -----------------------------
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# --- BACKGROUND STYLE ---
# -----------------------------
st.markdown(
    """
    <style>
        .stApp { background: linear-gradient(135deg, #ff8c00, #ffcc70); }
        .white-card { background-color: white; border-radius:12px; padding:16px; box-shadow:0px 4px 8px rgba(0,0,0,0.1); margin-bottom:12px; }
        .footer-disclaimer { font-size:0.75rem; color:gray; position: fixed; bottom:0; right:0; padding:8px; background-color:white; border-radius:8px 0 0 0; box-shadow:0px -2px 8px rgba(0,0,0,0.1); z-index:99; }
        .chat-input-container { position: fixed; bottom:40px; width:100%; max-width:720px; left:50%; transform:translateX(-50%); z-index:100; }
    </style>
    """, unsafe_allow_html=True
)

# -----------------------------
# --- SESSION STATE ---
# -----------------------------
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []

if 'pdf_text' not in st.session_state:
    st.session_state['pdf_text'] = None

# -----------------------------
# --- SIDEBAR MINI DASHBOARD ---
# -----------------------------
with st.sidebar:
    st.header("Mini Dashboard")
    st.write("Uploaded PDF status:", "Yes" if st.session_state['pdf_text'] else "No")
    st.write("Total interactions:", len(st.session_state['chat_history']))

# -----------------------------
# --- PDF UPLOAD ---
# -----------------------------
st.markdown("### Upload Medical References or Sales Module PDFs")
uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
if uploaded_pdf:
    pdf_reader = PdfReader(uploaded_pdf)
    text = ""
    for page in pdf_reader.pages:
        text += page.extract_text() + "\n"
    st.session_state['pdf_text'] = text

if st.session_state['pdf_text']:
    with st.expander("📄 Uploaded PDF Summary", expanded=False):
        st.markdown(f"<div class='white-card'>{st.session_state['pdf_text'][:1500]}...</div>", unsafe_allow_html=True)

# -----------------------------
# --- PROMPT SUGGESTIONS & CHAT INPUT ---
# -----------------------------
with st.container():
    st.markdown("<div class='chat-input-container'>", unsafe_allow_html=True)
    user_input = st.text_input("Ask your AI Sales Assistant:", key="user_input")
    st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------
# --- BRAND-SPECIFIC FRAMEWORKS ---
# -----------------------------
frameworks = {
    "Shingrix": {
        "name": "EMOTIVE Selling Framework",
        "steps": [
            "Prepare: Link to last call, create interest, co-identify patient profile",
            "Engage: Rapport, co-identify patient, tell patient story, highlight feelings, create urgency",
            "Create Opportunity: Insightful questions, unmet needs, patient risks",
            "Influence: Customize messages, handle objections, agree next steps",
            "Impact GSO: Close call with agreed outcomes",
            "Analyse: Evaluate call success and plan next steps"
        ]
    },
    "Jemperli": {
        "name": "IMPACT Competitive Selling Framework",
        "steps": [
            "COCO: Pre-call planning, identify persona and call objective",
            "Anchor: Open conversation with patient-focused narrative",
            "Engage: Two-way dialogue, connect clinical data and product messages",
            "Close: Gain agreement, define next steps",
            "Post-Call Analysis: Record insights and update CRM"
        ]
    },
    "Trelegy": {
        "name": "Default Competitive Selling Module",
        "steps": [
            "Prepare to sell",
            "Open the sales call",
            "Uncover opportunities",
            "Align on brand and address objections",
            "Close with commitments",
            "Analyse sales call and plan next steps"
        ]
    }
}

# -----------------------------
# --- GROQ AI API FUNCTION ---
# -----------------------------
def query_groq(prompt: str):
    """Query the GROQ API with a prompt and return the response."""
    api_key = "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"  # <--- Your GROQ API Key
    url = "https://api.groq.ai/v1/llm"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "groq-llm",
        "prompt": prompt,
        "max_output_tokens": 1200
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get("output", "No response from GROQ API.")
    except Exception as e:
        return f"Error querying GROQ API: {e}"

# -----------------------------
# --- GENERATE AI RESPONSE ---
# -----------------------------
def generate_ai_response(user_input, brand="Trelegy"):
    framework = frameworks.get(brand, frameworks["Trelegy"])
    framework_name = framework["name"]
    steps = framework["steps"]

    # Construct a strong GROQ prompt
    prompt = f"""
You are an expert pharmaceutical sales assistant. 
Brand: {brand}
Framework: {framework_name}
Framework Steps: {steps}

Instructions:
1. Generate a detailed sales call for the brand following each step of the framework.
2. Provide concrete examples and actionable guidance for the user at each step.
3. If PDF content is available, summarize key medical insights and integrate into the sales call.
4. Output should be rich, informative, with bullet points and examples.
5. Start each step clearly with 'Step X: <Step Name>'.
"""

    if st.session_state['pdf_text']:
        prompt += f"\nMedical References:\n{st.session_state['pdf_text'][:2000]}"

    # Query GROQ API
    ai_output = query_groq(prompt)
    return ai_output

# -----------------------------
# --- HANDLE USER INPUT ---
# -----------------------------
if user_input:
    # determine brand dynamically
    brand = "Trelegy"
    if "shingrix" in user_input.lower():
        brand = "Shingrix"
    elif "jemperli" in user_input.lower():
        brand = "Jemperli"

    ai_response = generate_ai_response(user_input, brand=brand)
    st.session_state['chat_history'].append((user_input, ai_response))

# -----------------------------
# --- DISPLAY CHAT HISTORY ---
# -----------------------------
for user_msg, ai_msg in st.session_state['chat_history']:
    st.markdown(f"<div class='white-card'><b>You:</b> {user_msg}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='white-card'><b>Assistant:</b><br>{ai_msg}</div>", unsafe_allow_html=True)

# -----------------------------
# --- FOOTER DISCLAIMER ---
# -----------------------------
st.markdown(
    "<div class='footer-disclaimer'>Please refer to Write Right Principles course: BUS-LGL-WRJA-001</div>",
    unsafe_allow_html=True
)
