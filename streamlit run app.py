import streamlit as st
from PIL import Image
import requests
from io import BytesIO
import base64
import tempfile
import asyncio
import re
from datetime import datetime
import PyPDF2
from docx import Document

# ---------------------------- GROQ Setup ----------------------------
from groq import Groq
# Replace with your key
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY)

# ---------------------------- Page config ----------------------------
st.set_page_config(page_title="GSK Sales Call Assistant", layout="wide")

# ---------------------------- Session State ----------------------------
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state: st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state: st.session_state.pdf_summary = ""
if "extracted_medical_ref" not in st.session_state: st.session_state.extracted_medical_ref = ""
if "language" not in st.session_state: st.session_state.language = "English"
if "voice_pref" not in st.session_state: st.session_state.voice_pref = "English Neural"

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = "https://www.shutterstock.com/image-photo/excited-girl-white-shirt-using-260nw-708132598.jpg"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png"

# ---------------------------- Styling ----------------------------
CSS = f"""
<style>
.stApp {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-attachment: fixed;
  background-size: auto 150%;
}}
.chat-bubble-user {{ background-color: #DCF8C6; border-radius:20px; padding:12px; margin:6px; max-width:70%; float:right; clear:both; }}
.chat-bubble-ai {{ background-color: #E6F0FF; border-radius:20px; padding:12px; margin:6px; max-width:70%; float:left; clear:both; }}
.pdf-summary-inline {{ background-color: #FAFAFA; padding:10px; border-radius:8px; border:1px solid #DDD; margin-top:6px; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- Title Box ----------------------------
st.markdown(f'<div style="display:flex;align-items:center;gap:12px;"><img src="{GSK_LOGO_URL}" width="140"><h1>💡 AI Sales Call Assistant</h1></div>', unsafe_allow_html=True)
st.markdown('<p style="font-weight:600;">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ---------------------------- PDF Upload ----------------------------
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text

        # Extract references
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"

        # PDF summary bullet points
        lines = [f"- {line.strip()}" for line in full_text.splitlines() if line.strip()]
        st.session_state.pdf_summary = "\n".join(lines[:10])

        with st.expander("📑 PDF Summary", expanded=True):
            st.markdown(f"<div class='pdf-summary-inline'>{st.session_state.pdf_summary.replace(chr(10),'<br>')}</div>", unsafe_allow_html=True)

        with st.expander("📚 Extracted References", expanded=False):
            st.info(st.session_state.extracted_medical_ref)

    except Exception as e:
        st.error(f"PDF error: {e}")

# ---------------------------- Filters / Sidebar ----------------------------
st.sidebar.markdown("### Filters & Options")
brands = ["Shingrix","Trelegy","Zejula"]
segment_list = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
barriers_list = ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy","Accessibility/Logistics","Patient reluctance","Other clinical doubts"]
personas_list = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
objectives_list = ["Awareness","Adoption","Retention"]
specialties_list = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist","Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"]

brand = st.sidebar.selectbox("Brand", brands)
segment = st.sidebar.selectbox("RACE Segment", segment_list)
barrier = st.sidebar.multiselect("Doctor Barrier(s)", barriers_list)
objective = st.sidebar.selectbox("Objective", objectives_list)
specialty = st.sidebar.selectbox("Doctor Specialty", specialties_list)
persona = st.sidebar.selectbox("HCP Persona", personas_list)
response_length = st.sidebar.selectbox("Response Length", ["Short","Medium","Long"])
response_tone = st.sidebar.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"])
st.session_state.language = st.sidebar.radio("Language", ["English","العربية"])
st.session_state.voice_pref = st.sidebar.selectbox("Voice preference", ["English Neural","Arabic Neural","Default"])

# ---------------------------- Helper: TTS ----------------------------
async def _edge_save_async(ssml_text: str, voice: str, outpath: str):
    import edge_tts
    comm = edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts(text, voice_pref):
    if not text: return None
    text_clean = re.sub(r'[.,/!?;:*]', '', text)
    ssml = "<speak>" + text_clean + "</speak>"
    voice = {"English Neural":"en-US-GuyNeural","Arabic Neural":"ar-EG-AdamNeural"}.get(voice_pref,"en-US-GuyNeural")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_name = tmp.name
    tmp.close()
    try:
        asyncio.run(_edge_save_async(ssml, voice, tmp_name))
        with open(tmp_name,"rb") as f:
            return base64.b64encode(f.read()).decode()
    finally:
        try: os.remove(tmp_name)
        except: pass

# ---------------------------- Helper: Chat ----------------------------
def render_chat():
    html_out = ""
    for msg in st.session_state.chat_history:
        content = msg["content"]
        if msg["role"]=="user":
            html_out += f"<div class='chat-bubble-user'>{content}</div>"
        else:
            audio_html = f"<br><audio controls style='margin-top:8px;'><source src='data:audio/mp3;base64,{msg.get('audio','')}' type='audio/mp3'></audio>" if msg.get('audio') else ""
            html_out += f"<div class='chat-bubble-ai'>{content}{audio_html}</div>"
    st.markdown(html_out, unsafe_allow_html=True)

def build_prompt(user_input):
    pdf_text = st.session_state.pdf_summary or ""
    refs = st.session_state.extracted_medical_ref or "None"
    return f"""You are a GSK sales assistant AI.
Language: {st.session_state.language}
Brand: {brand}
RACE Segment: {segment}
HCP Persona: {persona}
Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Specialty: {specialty}
Tone: {response_tone}, Length: {response_length}

Instructions:
- Use PDF summary and references when possible.
- Handle objections using APACT steps: Acknowledge, Probing, Action, Confirm, Transition.
- Bold steps and numeric figures.
PDF Summary:
{pdf_text}
References:
{refs}
User Query:
{user_input}
"""

def call_groq(prompt):
    try:
        resp = client.chat.completions.create(
            messages=[{"role":"system","content":"You are a helpful sales assistant."},
                      {"role":"user","content":prompt}],
            model="meta-llama/llama-4-scout-13b-instruct"
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI Error: {e}"

# ---------------------------- Chat Input ----------------------------
st.markdown("### 💬 Chat")
user_text = st.text_input("Type your message...")
if st.button("Send") and user_text.strip():
    st.session_state.chat_history.append({"role":"user","content":user_text})
    prompt = build_prompt(user_text)
    ai_resp = call_groq(prompt)
    audio_b64 = synthesize_tts(ai_resp, st.session_state.voice_pref)
    st.session_state.chat_history.append({"role":"ai","content":ai_resp,"audio":audio_b64})
    render_chat()

# ---------------------------- Export to Word ----------------------------
if st.button("📥 Export Chat + PDF Summary (.docx)"):
    doc = Document()
    doc.add_heading("AI Sales Call Assistant Chat History", 0)
    if st.session_state.pdf_summary:
        doc.add_heading("PDF Summary",1)
        doc.add_paragraph(st.session_state.pdf_summary)
    for msg in st.session_state.chat_history:
        role = "User" if msg["role"]=="user" else "AI"
        doc.add_paragraph(f"{role}: {msg['content']}")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
    doc.save(tmp.name)
    tmp.close()
    with open(tmp.name,"rb") as f:
        st.download_button("⬇️ Download Word File", f, file_name="chat_export.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
