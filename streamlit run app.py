import os
import re
import time
import base64
import tempfile
import asyncio
from datetime import datetime
from io import BytesIO

import streamlit as st
from PIL import Image, ImageStat
import requests
import PyPDF2
import html
try:
    import edge_tts
except:
    edge_tts = None

# Groq AI client
try:
    import groq
    from groq import Groq
except:
    Groq = None

# Optional docx
try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False

# ---------------- CONFIG ----------------
st.set_page_config(page_title="💡 AI Sales Call Assistant", layout="wide")

# ---------------- GROQ API ----------------
GROQ_API_KEY = "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"
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY and Groq is not None else None
if client is None:
    st.info("⚠️ GROQ AI client not configured. AI features disabled.")

# ---------------- SESSION ----------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history=[]
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary=""
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text=""
if "extracted_medical_ref" not in st.session_state:
    st.session_state.extracted_medical_ref=""
if "language" not in st.session_state:
    st.session_state.language="English"
if "voice_pref" not in st.session_state:
    st.session_state.voice_pref="English Neural"

# ---------------- ASSETS ----------------
BACKGROUND_URL="https://www.shutterstock.com/image-photo/excited-girl-white-shirt-using-260nw-708132598.jpg"
GSK_LOGO_URL="https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"

# ---------------- DATA ----------------
gsk_brands = {"Shingrix":"https://www.shingrix.com/","Trelegy":"https://www.trelegy.com/","Zejula":"https://www.zejula.com/"}
gsk_brands_images = {
    "Shingrix":"https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Trelegy":"https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
    "Zejula":"https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png"
}
race_segments=["R – Reach","A – Acquisition","C – Conversion","E – Engagement"]
doctor_barriers=["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy","Accessibility/Logistics","Patient reluctance","Other clinical doubts"]
personas=["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
sales_call_flow=["Prepare the call","Engage","Create opportunities","Impact GSO (Good sell outcome)","Influence","Analyze and post call analysis"]
APACT_STEPS=["Acknowledge","Probing","Action","Confirm","Transition"]
objectives=["Awareness","Adoption","Retention"]
specialties=["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist","Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"]

# ---------------- STYLING ----------------
CSS = f"""
<style>
.chat-container {{height:50vh; overflow:auto; padding:10px; border-radius:10px; background:rgba(255,255,255,0.85);}}
.chat-bubble-user {{background:#DCF8C6; border-radius:20px; padding:12px; margin:6px; float:right; clear:both; max-width:70%;}}
.chat-bubble-ai {{background:#E6F0FF; border-radius:20px; padding:12px; margin:6px; float:left; clear:both; max-width:70%;}}
.highlight-step {{font-weight:700;color:#000;}}
.highlight-figure {{font-weight:700;color:#d35400;}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------- SIDEBAR ----------------
with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown("<b>Filters & Options</b>", unsafe_allow_html=True)
    brand = st.selectbox("Brand", list(gsk_brands.keys()))
    segment = st.selectbox("RACE Segment", race_segments)
    barrier = st.multiselect("Doctor Barrier", doctor_barriers)
    objective = st.selectbox("Objective", objectives)
    specialty = st.selectbox("Doctor Specialty", specialties)
    persona = st.selectbox("HCP Persona", personas)
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"])
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"])
    st.session_state.language = st.radio("Language", ["English","العربية"], horizontal=True)
    st.session_state.voice_pref = st.selectbox("Voice preference", ["English Neural","Arabic Neural","Default"])

# ---------------- PDF UPLOAD ----------------
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
if uploaded_pdf:
    reader=PyPDF2.PdfReader(uploaded_pdf)
    full_text="".join([p.extract_text() or "" for p in reader.pages])
    st.session_state.uploaded_pdf_text=full_text
    matches=re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
    st.session_state.extracted_medical_ref=", ".join(matches) if matches else "None"
    st.session_state.pdf_summary="- Key insight 1\n- Key insight 2\n- Key insight 3"

# ---------------- HELPER FUNCTIONS ----------------
def highlight_content_for_display(content:str)->str:
    for s in sales_call_flow:
        content=re.sub(rf"\b{re.escape(s)}\b", f"<span class='highlight-step'>{s}</span>", content)
    for a in APACT_STEPS:
        content=re.sub(rf"\b{re.escape(a)}\b", f"<span class='highlight-step'>{a}</span>", content)
    for f in re.findall(r"\d+\.?\d*%", content):
        content=content.replace(f,f"<span class='highlight-figure'>{f}</span>")
    return content

def build_ai_bubble_content(ai_text:str)->str:
    text=(ai_text or "").replace("\n","<br>")
    text=highlight_content_for_display(text)
    pdf_html=""
    if st.session_state.pdf_summary:
        lines=[ln.strip() for ln in st.session_state.pdf_summary.splitlines() if ln.strip()][:6]
        pdf_html=f"""
        <details style='background-color:#fdfcf5; padding:8px; border-radius:8px; max-height:150px; overflow:auto; margin-bottom:4px;'>
            <summary>📑 PDF Summary</summary>
            {"<br>".join(lines)}
        </details>
        """
    return pdf_html+text

def render_extracted_refs():
    refs=st.session_state.extracted_medical_ref
    if refs and refs!="None":
        st.markdown(f"""
        <details style='background-color:#f2f2f2; padding:8px; border-radius:8px; margin-top:6px;'>
            <summary>📚 Extracted References</summary>
            {refs}
        </details>
        """, unsafe_allow_html=True)

def render_chat_history():
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for msg in st.session_state.chat_history:
        if msg.get("content","").strip()=="":
            continue
        if msg["role"]=="user":
            st.markdown(f'<div class="chat-bubble-user">{html.escape(msg["content"])}</div>', unsafe_allow_html=True)
        else:
            content_html=build_ai_bubble_content(msg["content"])
            st.markdown(f'<div class="chat-bubble-ai">{content_html}</div>', unsafe_allow_html=True)
            if msg.get("audio"):
                st.audio(base64.b64decode(msg["audio"]))
    st.markdown('</div>', unsafe_allow_html=True)

async def _edge_save_async(ssml_text:str, voice:str, outpath:str):
    comm=edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts_humanized(text:str, lang:str, voice_pref:str)->str:
    if not text: return None
    text=re.sub(r'(\d+)\s*%','\\1 percent',text)
    text=re.sub(r'[;:{}\[\]\*\^<>@#\$%&\|~_/\\+]','',text)
    sentences=re.split(r'(?<=[.?!])\s+', text)
    ssml="<speak>"+"".join([f"<prosody rate='medium'>{s}<break time='0.45s'/></prosody>" for s in sentences if s.strip()])+"</speak>"
    voice="en-US-AriaNeural" if voice_pref!="Arabic Neural" else "ar-EG-SalmaNeural"
    tmp=tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name=tmp.name
    tmp.close()
    try:
        asyncio.run(_edge_save_async(ssml, voice, tmp_name))
        with open(tmp_name,"rb") as f:
            data=f.read()
        return base64.b64encode(data).decode("utf-8")
    except:
        return None
    finally:
        try: os.remove(tmp_name)
        except: pass

def build_prompt(user_input:str, language:str)->str:
    pdf_summary=st.session_state.pdf_summary or ""
    refs=st.session_state.extracted_medical_ref or "None"
    instructions=[
        "- Use PDF summary & references as source.",
        "- Provide short sample script.",
        "- Match requested tone & length.",
        "- Bold sales call steps, APACT, and figures."
    ]
    return "\n".join([
        f"Language: {language}",
        f"User input: {user_input}",
        f"Brand: {brand}",
        f"RACE Segment: {segment}",
        f"Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}",
        f"Objective: {objective}",
        f"Doctor Specialty: {specialty}",
        f"HCP Persona: {persona}",
        "Instructions:"] + instructions + ["PDF Summary:", pdf_summary, "Extracted References:", refs, f"Response Tone: {response_tone} | Length: {response_length}"]
    )

def call_groq_with_retry(prompt:str, language:str)->str:
    if client is None: return "⚠️ GROQ AI not configured."
    try:
        resp=client.chat.completions.create(
            model="llama-3.1-70b-versatile",
            messages=[{"role":"system","content":"You are a helpful sales assistant."},{"role":"user","content":prompt}]
        )
        return resp.choices[0].message["content"]
    except Exception as e:
        return f"⚠️ AI error: {e}"

# ---------------- CHAT INTERFACE ----------------
st.markdown("### 💬 Chat")
with st.form("bottom_chat_form", clear_on_submit=True):
    user_text=st.text_input("Type message...", label_visibility="collapsed")
    submitted=st.form_submit_button("Send")

if submitted and user_text.strip():
    st.session_state.chat_history.append({"role":"user","content":user_text.strip(),"time":datetime.now().strftime("%H:%M")})
    prompt=build_prompt(user_text.strip(), st.session_state.language)
    ai_output=call_groq_with_retry(prompt, st.session_state.language)
    audio_b64=synthesize_tts_humanized(ai_output, st.session_state.language, st.session_state.voice_pref)
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M"),"audio":audio_b64})
    render_chat_history()
    render_extracted_refs()

# ---------------- EXPORT / CLEAR ----------------
cols=st.columns([1,1])
with cols[0]:
    if st.button("🗑️ Clear Chat"):
        st.session_state.chat_history=[]
        st.session_state.uploaded_pdf_text=""
        st.session_state.extracted_medical_ref=""
        st.session_state.pdf_summary=""
        st.experimental_rerun()
with cols[1]:
    if DOCX_AVAILABLE and st.session_state.chat_history:
        if st.button("📥 Export Chat (.docx)"):
            doc=Document()
            doc.add_heading("AI Sales Call Assistant Chat",0)
            for msg in st.session_state.chat_history:
                role="User" if msg.get("role")=="user" else "AI"
                doc.add_paragraph(f"{role} [{msg.get('time','')}]")
                doc.add_paragraph(re.sub(r'<.*?>','',msg.get("content","")))
            tmp=tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
            doc.save(tmp.name)
            tmp.close()
            with open(tmp.name,"rb") as f:
                data=f.read()
            st.download_button("⬇️ Download Chat History (.docx)", data=data, file_name="chat_history.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
