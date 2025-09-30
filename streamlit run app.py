import streamlit as st
from PIL import Image
import requests
from io import BytesIO
import base64
import re
import tempfile
import asyncio
from datetime import datetime
from docx import Document
from groq import Groq
import edge_tts
import PyPDF2
import html

# ---------------------- PAGE CONFIG ----------------------
st.set_page_config(page_title="GSK Sales Call Assistant", layout="wide")

# ---------------------- GROQ API ----------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
groq_client = Groq(api_key=GROQ_API_KEY)

# ---------------------- SESSION STATE ----------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "uploaded_pdf_text" not in st.session_state:
    st.session_state.uploaded_pdf_text = ""
if "extracted_medical_ref" not in st.session_state:
    st.session_state.extracted_medical_ref = ""
if "voice_pref" not in st.session_state:
    st.session_state.voice_pref = "Male Neural"
if "language" not in st.session_state:
    st.session_state.language = "English"

# ---------------------- ASSETS ----------------------
BACKGROUND_URL = "https://www.shutterstock.com/image-photo/excited-girl-white-shirt-using-260nw-708132598.jpg"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"

# ---------------------- STYLING ----------------------
st.markdown(f"""
<style>
/* Background & title */
body {{
    background: url("{BACKGROUND_URL}") no-repeat right top fixed;
    background-size: auto 150%;
}}
.title-box {{
    background: rgba(255,255,255,0.9);
    padding: 20px;
    border-radius: 15px;
    text-align: center;
    max-width: 90%;
    margin:auto;
}}
.title-box h1 {{ margin:0; font-size:34px; font-weight:800; color:#000; }}
.title-box p {{ margin:6px 0 0 0; font-size:16px; color:#333; }}

/* Chat bubbles */
.chat-container {{
    height: 55vh;
    overflow:auto;
    padding:12px;
    border-radius:10px;
    background: rgba(255,255,255,0.76);
}}
.chat-bubble-user {{ background: #DCF8C6; border-radius:20px; padding:12px; margin:6px; max-width:70%; float:right; clear:both; }}
.chat-bubble-ai {{ background: #E6F0FF; border-radius:20px; padding:12px; margin:6px; max-width:70%; float:left; clear:both; font-size:15px; }}
.pdf-summary-box {{ background: #E6F0FF; border-radius:12px; padding:10px; margin:6px; border:1px solid #ccc; max-height:200px; overflow:auto; }}
.collapsible {{
  background-color: #f1f1f1;
  color: #444;
  cursor: pointer;
  padding: 10px;
  width: 100%;
  border: none;
  text-align: left;
  outline: none;
  font-size: 15px;
}}
.active, .collapsible:hover {{ background-color: #ddd; }}
.content {{
  padding: 0 18px;
  display: none;
  overflow: hidden;
  background-color: #f9f9f9;
}}

/* Fixed bottom input */
.bottom-bar {{
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 1200;
  background: rgba(255,255,255,0.98);
  padding:10px;
  border-top:1px solid #ccc;
  display:flex;
  gap:10px;
}}
.bottom-bar input[type="text"] {{
    flex:1;
    padding:10px 12px;
    border-radius:8px;
    border:1px solid #ddd;
    outline:none;
}}
.bottom-bar button {{
    min-width:100px;
    padding:8px 12px;
    border-radius:8px;
    background:#4CAF50;
    color:white;
    border:none;
    font-weight:600;
    cursor:pointer;
}}
</style>
""", unsafe_allow_html=True)

# ---------------------- TITLE ----------------------
st.markdown(f"""
<div class="title-box">
<img src="{GSK_LOGO_URL}" width="140"><br>
<h1>💡 GSK Sales Call Assistant</h1>
<p>AI-powered assistant to prepare, engage & impact HCP calls</p>
</div>
""", unsafe_allow_html=True)

# ---------------------- PDF UPLOAD ----------------------
st.markdown("### 📄 Upload PDF for Summary & References")
uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
if uploaded_pdf:
    reader = PyPDF2.PdfReader(uploaded_pdf)
    full_text = "".join([p.extract_text() or "" for p in reader.pages])
    st.session_state.uploaded_pdf_text = full_text[:3000] + ("..." if len(full_text) > 3000 else "")
    refs = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
    st.session_state.extracted_medical_ref = ", ".join(refs) if refs else "None"
    
    # Summarize PDF
    prompt = f"Summarize the following medical PDF into concise bullet points:\n\n{full_text[:5000]}"
    summary_resp = groq_client.chat.completions.create(
        messages=[{"role":"system","content":"You are a concise medical summarizer for sales reps."},
                  {"role":"user","content":prompt}],
        model="llama-3.3-70b-versatile"
    )
    st.session_state.pdf_summary = summary_resp.choices[0].message.content if summary_resp.choices else ""
    
    st.markdown(f'<div class="pdf-summary-box">{"<br>".join(["- "+line.strip() for line in st.session_state.pdf_summary.splitlines() if line.strip()])}</div>', unsafe_allow_html=True)
    
    st.markdown(f"""
    <button class="collapsible">📚 Extracted References</button>
    <div class="content">{st.session_state.extracted_medical_ref}</div>
    <script>
    var coll = document.getElementsByClassName("collapsible");
    for (var i = 0; i < coll.length; i++) {{
      coll[i].addEventListener("click", function() {{
        this.classList.toggle("active");
        var content = this.nextElementSibling;
        if (content.style.display === "block") {{ content.style.display = "none"; }}
        else {{ content.style.display = "block"; }}
      }});
    }}
    </script>
    """, unsafe_allow_html=True)

# ---------------------- UPDATED FILTER/SELECTION SECTION ----------------------
st.sidebar.markdown("### Filters & Options")
gsk_brands = ["Shingrix","Trelegy","Zejula"]
segment_list = ["Reach","Acquisition","Conversion","Engagement"]
barriers = ["No risk perceived","No time","Cost","Efficacy doubts","Accessibility","Patient reluctance","Other"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist"]
personas = ["Uncommitted","Reluctant","Patient influenced","Committed"]
response_tones = ["Formal","Casual","Friendly","Persuasive"]

brand = st.sidebar.selectbox("Brand", gsk_brands)
segment = st.sidebar.selectbox("RACE Segment", segment_list)
barrier = st.sidebar.multiselect("Doctor Barrier", barriers)
objective = st.sidebar.selectbox("Objective", objectives)
specialty = st.sidebar.selectbox("Specialty", specialties)
persona = st.sidebar.selectbox("HCP Persona", personas)
response_tone = st.sidebar.selectbox("Response Tone", response_tones)
response_length = st.sidebar.selectbox("Response Length", ["Short","Medium","Long"])
st.session_state.language = st.sidebar.radio("Language", ["English","العربية"])
st.session_state.voice_pref = st.sidebar.selectbox("Voice Preference", ["Male Neural","Female Neural","Default"])

# ---------------------- SALES CALL STEPS ----------------------
sales_call_flow = ["Prepare the call","Engage","Create opportunities","Impact GSO","Influence","Post Call Analysis"]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]

# ---------------------- CHAT HISTORY ----------------------
st.markdown('<div class="chat-container" id="chat-container">', unsafe_allow_html=True)
for chat in st.session_state.chat_history:
    role = chat["role"]
    content = chat["content"]
    if role=="user":
        st.markdown(f'<div class="chat-bubble-user">{html.escape(content)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">{html.escape(content)}</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------- FUNCTIONS ----------------------
def generate_ai_response(prompt):
    context = f"""
    You are a GSK medical sales assistant. Use PDF summary if available.
    Follow sales call flow: {', '.join(sales_call_flow)}
    Handle objections with APACT: {', '.join(APACT_STEPS)}
    """
    resp = groq_client.chat.completions.create(
        messages=[{"role":"system","content":context},{"role":"user","content":prompt}],
        model="llama-3.3-70b-versatile"
    )
    return resp.choices[0].message.content if resp.choices else "⚠️ AI did not return a response."

async def _edge_save_async(ssml_text, voice, outpath):
    comm = edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts(text):
    if not text: return None
    text_clean = re.sub(r'[.;,]', '', text)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.close()
    asyncio.run(_edge_save_async(text_clean, voice="en-US-GuyNeural", outpath=tmp.name))
    with open(tmp.name,"rb") as f: audio_data = f.read()
    return base64.b64encode(audio_data).decode("utf-8")

# ---------------------- BOTTOM CHAT INPUT ----------------------
st.markdown("""
<div class="bottom-bar">
<form id="chat-form" style="display:flex; width:100%;">
<input type="text" id="chat_input" placeholder="Type your message..." style="flex:1; padding:10px; border-radius:8px; border:1px solid #ddd;">
<button type="button" onclick="sendMessage()" style="min-width:100px; padding:8px; border-radius:8px; background:#4CAF50; color:white;">Send</button>
</form>
</div>

<script>
function sendMessage(){{
    let val = document.getElementById("chat_input").value;
    if(val){{
        window.parent.postMessage({{func:"chatInput", value:val}}, "*");
        document.getElementById("chat_input").value = "";
    }}
}}
</script>
""", unsafe_allow_html=True)

# ---------------------- EXPORT CHAT ----------------------
if st.button("📥 Download Chat as Word"):
    doc = Document()
    doc.add_heading("GSK AI Sales Call Assistant Chat History",0)
    for msg in st.session_state.chat_history:
        role = "User" if msg["role"]=="user" else "AI"
        doc.add_paragraph(f"{role}: {msg['content']}")
    tmp = tempfile.NamedTemporaryFile(delete=False,suffix=".docx")
    doc.save(tmp.name)
    with open(tmp.name,"rb") as f: data=f.read()
    st.download_button("⬇️ Download Word", data=data, file_name="chat_history.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
