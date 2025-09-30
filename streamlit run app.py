# app.py
import os
import re
import time
import base64
import tempfile
import asyncio
from datetime import datetime
from io import BytesIO

import streamlit as st
from PIL import Image
import requests
import PyPDF2
import edge_tts
from docx import Document

# ----------------------------
# GROQ API
# ----------------------------
try:
    import groq
    from groq import Groq
except Exception:
    Groq = None

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
client = Groq(api_key=GROQ_API_KEY) if (GROQ_API_KEY and Groq is not None) else None
if client is None:
    st.warning("⚠️ GROQ API not configured. Responses will not be generated.")

# ----------------------------
# Streamlit config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "extracted_medical_ref" not in st.session_state:
    st.session_state.extracted_medical_ref = ""

# ----------------------------
# Filters data
# ----------------------------
gsk_brands = ["Shingrix", "Trelegy", "Zejula"]
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = [
    "HCP does not consider HZ a risk","No time for discussion","Cost concerns",
    "Not convinced of efficacy","Accessibility/Logistics","Patient reluctance","Other clinical doubts"
]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist","Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"]
sales_call_flow = [
    "Prepare the call",
    "Engage",
    "Create opportunities",
    "Impact GSO (Good sell outcome)",
    "Influence",
    "Analyze and post call analysis"
]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]

# ----------------------------
# Sidebar filters
# ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Select Brand", options=gsk_brands)
    segment = st.selectbox("Select RACE Segment", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty", options=specialties)
    persona = st.selectbox("Select HCP Persona", options=personas)
    response_length = st.selectbox("Response Length", ["Short", "Medium", "Long"])
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])
    language = st.radio("Language", options=["English", "Arabic"], index=0)
    voice_pref = st.selectbox("Voice preference", ["English Neural", "Arabic Neural", "Default"])

# ----------------------------
# PDF upload
# ----------------------------
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
if uploaded_pdf:
    reader = PyPDF2.PdfReader(uploaded_pdf)
    full_text = "".join([p.extract_text() or "" for p in reader.pages])
    st.session_state.pdf_summary = "\n".join(full_text.splitlines()[:5])  # first 5 lines
    refs = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
    st.session_state.extracted_medical_ref = ", ".join(refs) if refs else "None"
    st.markdown(f"<div style='background:#fdfdfd;padding:10px;border-radius:8px;'>📑 PDF Summary:<br>{st.session_state.pdf_summary}</div>", unsafe_allow_html=True)
    with st.expander("📚 Extracted references", expanded=False):
        st.write(st.session_state.extracted_medical_ref)

# ----------------------------
# Helper: call Groq API
# ----------------------------
def call_groq(prompt: str):
    if client is None:
        return "⚠️ GROQ API not configured."
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"system","content":"You are a helpful GSK sales assistant."},
                      {"role":"user","content":prompt}],
            temperature=0.65
        )
        return resp.choices[0].message["content"]
    except Exception as e:
        return f"⚠️ AI Error: {e}"

# ----------------------------
# Helper: build prompt
# ----------------------------
def build_prompt(user_input: str):
    prompt = f"""
User input: {user_input}
Brand: {brand}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Doctor Specialty: {specialty}
HCP Persona: {persona}
PDF Summary: {st.session_state.pdf_summary}
Extracted references: {st.session_state.extracted_medical_ref}
Sales Call Steps: {', '.join(sales_call_flow)}
APACT Steps: {', '.join(APACT_STEPS)}
Response Tone: {response_tone}, Length: {response_length}
"""
    return prompt

# ----------------------------
# Helper: TTS
# ----------------------------
async def _edge_save_async(ssml_text: str, voice: str, outpath: str):
    comm = edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts(text: str, voice_pref: str):
    voice = "en-US-AriaNeural" if voice_pref == "English Neural" else "ar-EG-SalmaNeural"
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        asyncio.run(_edge_save_async(text, voice, tmp_name))
        with open(tmp_name, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return None

# ----------------------------
# Render chat history
# ----------------------------
def render_chat_history():
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f"<div style='background:#dcf8c6;padding:10px;border-radius:12px;margin:4px 0'>{msg['content']}</div>", unsafe_allow_html=True)
        else:
            ai_text = msg["content"]
            pdf_html = f"<div style='background:#fdfdfd;padding:8px;border-radius:8px;margin-top:4px'>{st.session_state.pdf_summary}</div>" if st.session_state.pdf_summary else ""
            audio_html = f"<br><audio controls src='data:audio/mp3;base64,{msg['audio']}'></audio>" if msg.get("audio") else ""
            st.markdown(f"<div style='background:#e6f0ff;padding:10px;border-radius:12px;margin:4px 0'>{ai_text}{pdf_html}{audio_html}</div>", unsafe_allow_html=True)

st.markdown("### 💬 Chat")
render_chat_history()

# ----------------------------
# Chat input
# ----------------------------
user_input = st.text_input("Type your message here")
if st.button("Send") and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input})
    prompt = build_prompt(user_input)
    ai_resp = call_groq(prompt)
    audio_b64 = synthesize_tts(ai_resp, voice_pref)
    st.session_state.chat_history.append({"role":"ai","content":ai_resp,"audio":audio_b64})
    render_chat_history()

# ----------------------------
# Download chat as Word
# ----------------------------
if st.session_state.chat_history:
    doc = Document()
    doc.add_heading("AI Sales Call Assistant Chat", 0)
    for msg in st.session_state.chat_history:
        role = "User" if msg["role"]=="user" else "AI"
        doc.add_paragraph(f"{role}: {msg['content']}")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        doc.save(tmp.name)
        with open(tmp.name, "rb") as f:
            st.download_button("⬇️ Download Chat (.docx)", f, file_name="chat_history.docx")

# ----------------------------
# Clear chat
# ----------------------------
if st.button("🧹 Clear Chat"):
    st.session_state.chat_history = []
    st.session_state.pdf_summary = ""
    st.session_state.extracted_medical_ref = ""
    st.experimental_rerun()
