# app.py
import os
import re
import time
import base64
import tempfile
import asyncio
from typing import Optional
from datetime import datetime
from io import BytesIO, BytesIO as io_bytes

import streamlit as st
from PIL import Image, ImageStat
import requests
import PyPDF2
import edge_tts

# Groq client
try:
    import groq
    from groq import Groq
except Exception as e:
    st.error("groq package not found. Install groq to enable AI. Error: " + str(e))
    raise

# Optional docx export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", page_icon="💡", layout="wide")

# ----------------------------
# Load GROQ API key
# ----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
if not GROQ_API_KEY:
    st.warning("GROQ_API_KEY not found in environment. Set GROQ_API_KEY in env or Streamlit Secrets.")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ----------------------------
# Session state defaults
# ----------------------------
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

# ----------------------------
# Assets & styling variables
# ----------------------------
BACKGROUND_URL = "https://sdmntprcentralus.oaiusercontent.com/files/00000000-b734-61f5-a93b-9ba88dbca3ee/raw?se=2025-09-29T12%3A57%3A58Z&sp=r&sv=2024-08-04&sr=b&scid=824d4bff-2b7f-5840-ab88-6b299849a7f3&skoid=add8ee7d-5fc7-451e-b06e-a82b2276cf62&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-29T06%3A35%3A36Z&ske=2025-09-30T06%3A35%3A36Z&sks=b&skv=2024-08-04&sig=INZ//zwicD0PpLeRFxvyL6kj3i6KdFnF3ZYZudrjqKw%3D"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"

def get_brightness(url: str) -> int:
    try:
        r = requests.get(url, timeout=8)
        img = Image.open(BytesIO(r.content)).convert("L")
        stat = ImageStat.Stat(img)
        return int(stat.mean[0])
    except Exception:
        return 255

brightness = get_brightness(BACKGROUND_URL)
text_color = "black" if brightness > 130 else "white"

# ----------------------------
# CSS: responsive background and chat
# ----------------------------
CSS = f"""
<style>
.stApp {{
  background: url('{BACKGROUND_URL}') no-repeat top right;
  background-size: calc(100% - 260px) auto;
  transition: background-size 0.3s ease;
}}
[data-testid="stSidebar"][aria-expanded="true"] ~ .stApp {{
  background-size: calc(100% - 360px) auto;
}}
[data-testid="stSidebar"][aria-expanded="false"] ~ .stApp {{
  background-size: 100% auto;
}}
.stSidebar {{
  background-color: #dddd;
  padding: 14px;
}}
.stSidebar .stSelectbox, .stSidebar .stMultiselect, .stSidebar .stRadio, .stSidebar .stCheckbox, .stSidebar .stFileUploader {{
  border: 1px solid #fff;
  border-radius: 10px;
  padding: 8px;
  margin-bottom: 12px;
  background-color: #dddd;
}}
.gsk-logo {{
  position: flix;
  top: 60px;
  left: 16px;
  z-index: 1200;
}}
.title-box {{
  background: rgba(255,255,255,0.6);
  padding: 28px;
  border-radius: 14px;
  text-align: center;
  max-width: 85%;
  margin: 12px auto;
}}
.title-box h1 {{ margin:0; font-size:38px; font-weight:800; }}
.title-box p {{ margin:8px 0 0 0; font-size:18px; font-weight:500; }}
.pdf-summary-box {{
  background: rgba(255,255,255,0.6);
  padding:16px;
  border-radius:12px;
  margin-bottom:12px;
}}
.chat-bubble-user, .chat-bubble-ai {{
  padding:12px;
  border-radius:12px;
  margin:8px 0;
  display:block;
  max-width:95%;
  word-wrap: break-word;
  color:black;
}}
.chat-bubble-user {{ background:#f1f8e9; margin-left:auto; }}
.chat-bubble-ai {{ background:#f5f7fa; margin-right:auto; }}
.pdf-summary-inline {{
  margin-top:8px;
  background: rgba(255,255,255,0.6);
  padding:10px;
  border-radius:10px;
}}
.bottom-input {{
  position: fixed;
  bottom: 12px;
  left: 16px;
  right: 16px;
  z-index: 2000;
  display:flex;
  gap:12px;
  align-items:center;
  background: rgba(255,255,255,0.6);
  padding:10px;
  border-radius:12px;
  box-shadow: 0 6px 18px rgba(0,0,0,0.08);
}}
.bottom-input input[type="text"] {{
  width:100%;
  padding:10px 14px;
  border-radius:12px;
  border:1px solid #ddd;
  outline:none;
}}
.bottom-input button {{
  min-width:120px;
  padding:8px 14px;
  border-radius:8px;
  border:none;
  background:#ff8c00;
  color:white;
  font-weight:600;
}}
@media (max-width:430px) {{
  .title-box h1 {{ font-size:26px; }}
  .gsk-logo img {{ width:90px; }}
  .bottom-input {{ left:8px; right:8px; bottom:8px; padding:8px; }}
}}
.highlight-step {{ font-weight:700; color:#000; }}
.highlight-figure {{ font-weight:700; color:#d35400; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(f'<div class="gsk-logo"><img src="{GSK_LOGO_URL}" width="140"></div>', unsafe_allow_html=True)
st.markdown("""
<div class="title-box">
  <h1>💡 AI Sales Call Assistant</h1>
  <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
</div>
""", unsafe_allow_html=True)
st.markdown('<p style="text-align:center;font-weight:600;">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Filters & Data
# ----------------------------
gsk_brands = {"Shingrix":"https://www.shingrix.com/","Trelegy":"https://www.trelegy.com/","Zejula":"https://www.zejula.com/"}
gsk_brands_images = {"Shingrix":"https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
"Trelegy":"https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
"Zejula":"https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png"}

race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy",
"Accessibility/Logistics","Patient reluctance","Other clinical doubts"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
gsk_approaches = ["Use data-driven evidence","Focus on patient outcomes & quality of life","Leverage brief storytelling and peer endorsement","Address practical barriers"]
sales_call_flow = ["Prepare the call", "Engage", "Create opportunities", "Impact GSO (Good sell outcome)", "Influence", "Analyze and post call analysis"]
APACT_STEPS = ["Acknowledge", "Probing", "Action", "Confirm", "Transition"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist","Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"]

# ----------------------------
# Sidebar Filters
# ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Select Brand", options=list(gsk_brands.keys()))
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try:
            resp = requests.get(img_path, timeout=6)
            st.image(Image.open(BytesIO(resp.content)), width=180)
        except:
            st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=180)
    segment = st.selectbox("Select RACE Segment", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty", options=specialties)
    persona = st.selectbox("Select HCP Persona", options=personas)
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"])
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"])
    interface_mode = st.radio("Interface Mode", ["Chatbot","Card Dashboard","Flow Visualization"])

# ----------------------------
# PDF Upload
# ----------------------------
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:2000]+"..." if len(full_text)>2000 else full_text
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(matches) if matches else "None"
        st.success("✅ PDF processed")
    except Exception as e:
        st.error("PDF error: "+str(e))

# ----------------------------
# Chat area
# ----------------------------
st.markdown("<h3>💬 Chat</h3>", unsafe_allow_html=True)
st.markdown('<div id="chat-area" style="height:56vh; overflow:auto; padding:12px; border-radius:8px; background: rgba(255,255,255,0.6);">', unsafe_allow_html=True)

# helper: render chat
def build_ai_bubble_content(ai_text:str)->str:
    content = ai_text.replace("\n","<br>")
    for step in sales_call_flow:
        content = re.sub(rf"\b{re.escape(step)}\b", f"<span class='highlight-step'>{step}</span>", content)
    for ap in APACT_STEPS:
        content = re.sub(rf"\b{re.escape(ap)}\b", f"<span class='highlight-step'>{ap}</span>", content)
    for figure in re.findall(r"\d+\.?\d*%", content):
        content = content.replace(figure,f"<span class='highlight-figure'>{figure}</span>")
    return f"<div class='chat-bubble-ai'>{content}</div>"

def render_chat_history():
    html=""
    for msg in st.session_state.chat_history:
        if msg["role"]=="user":
            html+=f"<div class='chat-bubble-user'>{msg['content']}</div>"
        else:
            html+=build_ai_bubble_content(msg["content"])
            if msg.get("audio"):
                html+=f"<br><audio controls style='margin-top:8px;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
    st.markdown(html, unsafe_allow_html=True)
    st.markdown("<script>const el=document.getElementById('chat-area'); if(el) el.scrollTop=el.scrollHeight;</script>", unsafe_allow_html=True)

render_chat_history()
st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# Humanized TTS (punctuation removed)
# ----------------------------
async def _edge_save_async(ssml_text:str, voice:str, outpath:str):
    comm = edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts_humanized(text:str, lang:str)->Optional[str]:
    if not text or not text.strip(): return None
    # Remove punctuation
    text = re.sub(r'[^\w\s]','', text)
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'(?<=[.?!])\s+', text)
    ssml_parts=[]
    for s in sentences:
        s=s.strip()
        if not s: continue
        ssml_parts.append(f"<prosody rate='medium'>{s}<break time='0.35s'/></prosody>")
    ssml_text = "<speak>" + " ".join(ssml_parts) + "</speak>"
    voice = "ar-EG-SalmaNeural" if lang=="العربية" else "en-US-AriaNeural"
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name=tmp.name
    tmp.close()
    try:
        asyncio.run(_edge_save_async(ssml_text, voice, tmp_name))
        with open(tmp_name,"rb") as f: b=f.read()
        return base64.b64encode(b).decode("utf-8")
    except: return None
    finally:
        if os.path.exists(tmp_name): os.remove(tmp_name)

# ----------------------------
# Build prompt
# ----------------------------
def build_prompt(user_input:str, language:str)->str:
    pdf_summary = st.session_state.pdf_summary or ""
    refs = st.session_state.extracted_medical_ref or "None"
    instructions = [
        "- Use uploaded PDF summary and references as primary sources.",
        "- Cite references when applicable.",
        "- Provide actionable sales suggestions and short 3–6 line sample script.",
        "- Output in clear, professional language matching tone and length."
    ]
    if re.search(r"\b(sales call flow|call flow|sales flow|sales steps)\b", user_input, flags=re.I):
        instructions.append("Return call steps as bold bullet points with 1-2 sentences actionable guidance: " + ", ".join([f"**{s}**" for s in sales_call_flow]))
    if re.search(r"\b(objection|concern|barrier|hesitat|not convinced|resist)\b", user_input, flags=re.I):
        instructions.append("Use APACT structure: **Acknowledge**, **Probing**, **Action**, **Confirm**, **Transition**.")
    instructions.append("Bold call steps, APACT titles, and notable figures (e.g. 45%).")
    prompt_lines = [
        f"Language: {language}",
        f"User input: {user_input}",
        f"Brand: {brand}",
        f"RACE Segment: {segment}",
        f"Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}",
        f"Objective: {objective}",
        f"Doctor Specialty: {specialty}",
        f"HCP Persona: {persona}",
        "",
        "Instructions for the assistant:",
        *instructions,
        "",
        "PDF Summary (if any):", pdf_summary or "None",
        "Extracted References:", refs,
        f"Response Tone: {response_tone}, Length: {response_length}"
    ]
    return "\n".join(prompt_lines)

# ----------------------------
# Call Groq AI with retry
# ----------------------------
def call_groq_with_retry(prompt:str, language:str, max_retries:int=3, base_delay:int=2):
    if client is None: return "⚠️ AI service not configured."
    models = ["meta-llama/llama-4-scout-17b-16e-instruct","meta-llama/llama-4-scout-13b-instruct"]
    last_err = None
    for model in models:
        for attempt in range(1,max_retries+1):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role":"system","content":f"You are a helpful sales assistant that responds in {language}."},
                        {"role":"user","content":prompt}
                    ],
                    temperature=0.7
                )
                return resp.choices[0].message.content
            except Exception as e:
                last_err=e
                err_msg=str(e).lower()
                if "over capacity" in err_msg or "503" in err_msg or "internal_server_error" in err_msg:
                    wait = base_delay*(2**(attempt-1))
                    st.warning(f"Model {model} busy. Retrying in {wait}s (attempt {attempt}/{max_retries})...")
                    time.sleep(wait)
                    continue
                if "authentication" in err_msg or "unauthorized" in err_msg:
                    return "⚠️ AI Authentication failed. Check GROQ_API_KEY."
                break
    return f"⚠️ AI call failed after retries. Last error: {last_err}"

# ----------------------------
# Bottom input bar
# ----------------------------
with st.container():
    user_text = st.text_input("Type your query here…", key="user_input", placeholder="Ask about sales call steps, objections handling, sample scripts…")
    send_button = st.button("Send")
    if send_button and user_text.strip():
        # Append user message
        st.session_state.chat_history.append({
            "role": "user",
            "content": user_text,
            "time": datetime.now().strftime("%H:%M")
        })
        # Build prompt
        prompt = build_prompt(user_text, st.session_state.language)
        # Call Groq
        ai_output = call_groq_with_retry(prompt, st.session_state.language)
        if not ai_output: ai_output = "⚠️ AI call failed after retries."
        # Generate TTS
        audio_b64 = synthesize_tts_humanized(ai_output, st.session_state.language)
        # Append AI
        st.session_state.chat_history.append({
            "role": "ai",
            "content": ai_output,
            "time": datetime.now().strftime("%H:%M"),
            "audio": audio_b64
        })
        render_chat_history()

# ----------------------------
# Clear chat button
# ----------------------------
if st.button("Clear Chat History"):
    st.session_state.chat_history = []
    st.experimental_rerun()
# ----------------------------
# Export Chat History to Word
# ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    if st.button("📄 Export Chat History to Word"):
        doc = Document()
        doc.add_heading("AI Sales Call Assistant Chat History", 0)
        for msg in st.session_state.chat_history:
            role = "User" if msg["role"]=="user" else "AI"
            doc.add_paragraph(f"{role} [{msg['time']}] : ", style='Intense Quote')
            content = msg['content']
            # Replace HTML tags with plain text for Word
            content = re.sub(r'<.*?>', '', content)
            doc.add_paragraph(content)
            # Add audio info
            if msg.get("audio"):
                doc.add_paragraph("[Audio available]")
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp_file.name)
        tmp_file.close()
        with open(tmp_file.name, "rb") as f:
            bytes_data = f.read()
            b64 = base64.b64encode(bytes_data).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="chat_history.docx">⬇️ Download Chat History</a>'
            st.markdown(href, unsafe_allow_html=True)
