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
import edge_tts
import html

# Groq client
try:
    import groq
    from groq import Groq
except Exception:
    Groq = None

# Optional docx export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

# ---------------------------- Page config ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ---------------------------- GROQ API Key ----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")  # ⚡ Insert your GROQ API Key here
client = Groq(api_key=GROQ_API_KEY) if (GROQ_API_KEY and Groq is not None) else None
if client is None:
    st.warning("⚠️ GROQ API client not configured. Please add your GROQ API key.")

# ---------------------------- Session state ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "extracted_medical_ref" not in st.session_state:
    st.session_state.extracted_medical_ref = ""
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "language" not in st.session_state:
    st.session_state.language = "English"
if "voice_pref" not in st.session_state:
    st.session_state.voice_pref = "English Neural"

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = "https://www.shutterstock.com/image-photo/excited-girl-white-shirt-using-260nw-708132598.jpg"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"

def get_brightness(url: str) -> int:
    try:
        r = requests.get(url, timeout=6)
        img = Image.open(BytesIO(r.content)).convert("L")
        stat = ImageStat.Stat(img)
        return int(stat.mean[0])
    except:
        return 255

brightness = get_brightness(BACKGROUND_URL)
text_color = "black" if brightness > 130 else "white"

# ---------------------------- Styling ----------------------------
CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-size: cover;
}}
.title-box {{
  background: rgba(245,245,245,0.6);
  padding: 22px;
  border-radius: 14px;
  text-align: center;
  max-width: 80%;
  margin: 12px auto;
}}
.title-box h1 {{ margin:0; font-size:34px; font-weight:800; color:{text_color}; }}
.title-box p {{ margin:6px 0 0 0; font-size:16px; color:{text_color}; }}
.chat-container {{
  height: 50vh;
  overflow:auto;
  padding:12px;
  border-radius:10px;
  background: rgba(255,255,255,0.76);
}}
.chat-bubble-user {{ background: #DCF8C6; border-radius:20px; padding:12px; margin:6px; max-width:70%; float:right; clear:both; }}
.chat-bubble-ai {{ background: #fdfdf5; border-radius:20px; padding:12px; margin:6px; max-width:70%; float:left; clear:both; font-size:15px; }}
.pdf-summary-inline {{
  background: #f9f9f9;
  padding:10px;
  border-radius:8px;
  border:1px solid #ddd;
  margin-top:6px;
}}
.highlight-step {{ font-weight:700; color:#000; }}
.highlight-figure {{ font-weight:700; color:#d35400; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- Data Lists ----------------------------
gsk_brands = {
    "Shingrix": "https://www.shingrix.com/",
    "Trelegy": "https://www.trelegy.com/",
    "Zejula": "https://www.zejula.com/"
}
gsk_brands_images = {
    "Shingrix":"https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Trelegy":"https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
    "Zejula":"https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png"
}
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = ["HCP does not consider HZ a risk","No time for discussion","Cost concerns",
                   "Not convinced of efficacy","Accessibility/Logistics","Patient reluctance","Other clinical doubts"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
sales_call_flow = ["Prepare the call","Engage","Create opportunities","Impact GSO (Good sell outcome)","Influence","Analyze and post call"]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist","Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"]

# ---------------------------- Sidebar Filters ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Select Brand", list(gsk_brands.keys()))
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try:
            resp = requests.get(img_path, timeout=6)
            st.image(Image.open(BytesIO(resp.content)), width=160)
        except:
            st.image("https://via.placeholder.com/160x90.png?text=No+Image", width=160)
    segment = st.selectbox("Select RACE Segment", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty", options=specialties)
    persona = st.selectbox("Select HCP Persona", options=personas)
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"])
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"])
    st.session_state.language = st.radio("Language", ["English","Arabic"], index=0, horizontal=True)
    st.session_state.voice_pref = st.selectbox("Voice preference", ["English Neural","Arabic Neural","Default"])

# ---------------------------- PDF Upload ----------------------------
st.markdown("### 📄 Upload PDF")
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:2000] + "..." if len(full_text) > 2000 else full_text
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"

        # PDF summary (mock or simple)
        st.session_state.pdf_summary = "- Key insight 1\n- Key insight 2\n- Key insight 3"

        # Display summary
        with st.expander("📑 PDF Summary", expanded=False):
            st.markdown(f"<div class='pdf-summary-inline'>{st.session_state.pdf_summary.replace(chr(10),'<br>')}</div>", unsafe_allow_html=True)

        # Collapsible extracted references
        with st.expander("📚 Extracted References", expanded=False):
            st.info(st.session_state.extracted_medical_ref)
    except Exception as e:
        st.error(f"PDF error: {e}")

# ---------------------------- Title & Logo ----------------------------
st.markdown(f'<div style="text-align:center;"><img src="{GSK_LOGO_URL}" width="140"></div>', unsafe_allow_html=True)
st.markdown('<div class="title-box"><h1>💡 AI Sales Call Assistant</h1><p>Powered by AI to equip sales reps for smarter HCP conversations</p></div>', unsafe_allow_html=True)

# ---------------------------- Helper Functions ----------------------------
def highlight_content(text):
    for step in sales_call_flow + APACT_STEPS:
        text = re.sub(rf"\b{re.escape(step)}\b", f"<span class='highlight-step'>{step}</span>", text)
    for fig in re.findall(r"\d+\.?\d*%", text):
        text = text.replace(fig, f"<span class='highlight-figure'>{fig}</span>")
    return text

def build_prompt(user_input):
    pdf_summary = st.session_state.pdf_summary or ""
    refs = st.session_state.extracted_medical_ref or "None"
    prompt = f"""
Language: {st.session_state.language}
User input: {user_input}
Brand: {brand}
RACE Segment: {segment}
Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Response tone: {response_tone}. Desired length: {response_length}.

Instructions:
- Use the uploaded PDF summary and extracted medical references.
- Apply sales call flow: {', '.join(sales_call_flow)}
- Apply APACT for objections: {', '.join(APACT_STEPS)}
- Bold steps, APACT titles, and numeric figures.

PDF Summary:
{pdf_summary}

Extracted references:
{refs}
"""
    return prompt

def call_groq(prompt):
    if client is None:
        return "⚠️ GROQ API not configured."
    try:
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"system","content":"You are a helpful GSK sales assistant."},
                      {"role":"user","content":prompt}],
            temperature=0.65
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI Error: {e}"

async def _edge_save_async(ssml_text, voice, outpath):
    comm = edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts(text, voice_pref):
    if not text: return None
    text = re.sub(r'(\d+)%', r'\1 percent', text)
    ssml = "<speak>" + text + "</speak>"
    voice = {"English Neural":"en-US-AriaNeural","Arabic Neural":"ar-EG-SalmaNeural"}.get(voice_pref,"en-US-AriaNeural")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_name = tmp.name
    tmp.close()
    try:
        asyncio.run(_edge_save_async(ssml, voice, tmp_name))
        with open(tmp_name,"rb") as f:
            return base64.b64encode(f.read()).decode()
    except: return None
    finally:
        try: os.remove(tmp_name)
        except: pass

def render_chat():
    html_out = ""
    for msg in st.session_state.chat_history:
        content = html.escape(msg["content"])
        if msg["role"]=="user":
            html_out += f"<div class='chat-bubble-user'>{content}</div>"
        else:
            content = highlight_content(msg["content"])
            audio_html = f"<br><audio controls style='margin-top:8px;'><source src='data:audio/mp3;base64,{msg.get('audio','')}' type='audio/mp3'></audio>" if msg.get('audio') else ""
            html_out += f"<div class='chat-bubble-ai'>{content}{audio_html}</div>"
    st.markdown(html_out, unsafe_allow_html=True)

# ---------------------------- Chat Interface ----------------------------
st.markdown("<h3>💬 Chat</h3>", unsafe_allow_html=True)
render_chat()

with st.form("chat_form", clear_on_submit=True):
    user_text = st.text_input("Type your message...")
    submitted = st.form_submit_button("Send")

if submitted and user_text.strip():
    st.session_state.chat_history.append({"role":"user","content":user_text.strip(),"time":datetime.now().strftime("%H:%M")})
    prompt = build_prompt(user_text.strip())
    ai_resp = call_groq(prompt)
    audio_b64 = synthesize_tts(ai_resp, st.session_state.voice_pref)
    st.session_state.chat_history.append({"role":"ai","content":ai_resp,"time":datetime.now().strftime("%H:%M"),"audio":audio_b64})
    render_chat()

# ---------------------------- Export to Word ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("📥 Export Chat to Word"):
        doc = Document()
        doc.add_heading("AI Sales Call Assistant Chat History",0)
        for msg in st.session_state.chat_history:
            role = "User" if msg["role"]=="user" else "AI"
            doc.add_paragraph(f"{role} [{msg.get('time','')}]")
            doc.add_paragraph(re.sub(r'<.*?>','',msg["content"]))
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp.name)
        tmp.close()
        with open(tmp.name,"rb") as f:
            st.download_button("⬇️ Download Chat (.docx)", f.read(), file_name="chat_history.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

# ---------------------------- Clear Chat ----------------------------
if st.button("🗑️ Clear Chat"):
    st.session_state.chat_history = []
    st.session_state.uploaded_pdf_text = ""
    st.session_state.extracted_medical_ref = ""
    st.session_state.pdf_summary = ""
    st.experimental_rerun()

# ---------------------------- Show Sales Call Flow ----------------------------
if st.button("Show GSK Sales Call Flow"):
    flow_lines = [f"**{s}**: Provide 1–2 lines guidance." for s in sales_call_flow]
    flow_text = "\n\n".join(flow_lines)
    st.session_state.chat_history.append({"role":"ai","content":flow_text})
    render_chat()
