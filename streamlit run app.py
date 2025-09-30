import streamlit as st
from PIL import Image
import requests
from io import BytesIO
import html
import base64
from datetime import datetime
from docx import Document
from groq import Groq
import re
import asyncio
import tempfile
import edge_tts

# ---------------------------- CONFIG ----------------------------
st.set_page_config(page_title="💡 GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- GROQ API ----------------------------
# Highlight the place to add your GROQ API Key
groq_client = Groq(api_key="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")

# ---------------------------- SESSION STATE ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = ""
if "extracted_refs" not in st.session_state:
    st.session_state.extracted_refs = ""
if "voice_pref" not in st.session_state:
    st.session_state.voice_pref = "en-US-GuyNeural"

# ---------------------------- ASSETS ----------------------------
BACKGROUND_URL = "https://drive.google.com/uc?id=1WlvNx4MqufxuGUw9ilLxGJLsuozbX17b"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png"

# ---------------------------- FILTERS & DATA ----------------------------
gsk_brands = ["Shingrix", "Trelegy", "Zejula"]
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = [
    "HCP does not consider HZ a risk","No time for discussion","Cost concerns",
    "Not convinced of efficacy","Accessibility/Logistics","Patient reluctance","Other clinical doubts"
]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
sales_call_flow = [
    "Prepare the call",
    "Engage",
    "Create opportunities",
    "Impact GSO (Good sell outcome)",
    "Influence",
    "Analyze and post call"
]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist","Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"]

# ---------------------------- CSS ----------------------------
st.markdown(f"""
<style>
/* Background */
[data-testid="stAppViewContainer"] {{
    background: url("{BACKGROUND_URL}") no-repeat center top fixed;
    background-size: cover;
}}
.title-box {{
    background: rgba(255,255,255,0.85);
    padding: 18px;
    border-radius: 14px;
    text-align:center;
    margin-bottom:12px;
}}
.chat-container {{
    position: relative;
    bottom: 5cm;
    height: 55vh;
    overflow:auto;
    padding:12px;
    border-radius:10px;
    background: #E6F0FF;
}}
.chat-bubble-user {{ background:#DCF8C6; margin-left:auto; margin-bottom:6px; padding:12px; border-radius:12px; max-width:70%; clear:both; }}
.chat-bubble-ai {{ background:#E6F0FF; margin-right:auto; margin-bottom:6px; padding:12px; border-radius:12px; max-width:70%; clear:both; }}
.pdf-summary-box {{ background:#E6F0FF; padding:10px; border-radius:10px; margin-bottom:8px; max-height:180px; overflow:auto; }}
.bottom-bar {{
    position: fixed;
    bottom: 12px;
    left: 16px;
    right: 16px;
    z-index:1200;
    background: rgba(255,255,255,0.95);
    padding:10px;
    border-radius:12px;
    display:flex;
    gap:12px;
}}
.bottom-bar input[type=text] {{
    flex:1;
    padding:10px;
    border-radius:8px;
    border:1px solid #ddd;
}}
.bottom-bar button {{
    min-width:90px;
    border-radius:8px;
    background:#4CAF50;
    color:white;
    font-weight:600;
    cursor:pointer;
}}
</style>
""", unsafe_allow_html=True)

# ---------------------------- TITLE ----------------------------
st.markdown(f"""
<div class="title-box">
    <img src="{GSK_LOGO_URL}" width="140"><br>
    <h1>💡 GSK AI Sales Call Assistant</h1>
    <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------- PDF UPLOAD ----------------------------
st.markdown("### 📄 Upload PDF for Reference")
uploaded_pdf = st.file_uploader("Upload medical PDF", type=["pdf"])
if uploaded_pdf:
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(uploaded_pdf)
        text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.pdf_summary = "\n".join([f"- {line.strip()}" for line in text.splitlines() if line.strip()][:10])
        refs = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", text, flags=re.I)
        st.session_state.extracted_refs = ", ".join(refs) if refs else "None"
        # PDF summary box
        st.markdown(f'<div class="pdf-summary-box">{st.session_state.pdf_summary}</div>', unsafe_allow_html=True)
        # Collapsible references
        with st.expander("📚 Extracted References", expanded=False):
            st.write(st.session_state.extracted_refs)
    except Exception as e:
        st.error(f"PDF error: {e}")

# ---------------------------- FILTERS ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", gsk_brands)
    segment = st.selectbox("RACE Segment", race_segments)
    barrier = st.multiselect("Doctor Barrier", doctor_barriers)
    objective = st.selectbox("Objective", objectives)
    specialty = st.selectbox("Specialty", specialties)
    persona = st.selectbox("HCP Persona", personas)
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"])
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"])
    st.session_state.voice_pref = st.selectbox("Voice preference", ["en-US-GuyNeural","en-US-AriaNeural"])

# ---------------------------- HELPER FUNCTIONS ----------------------------
def add_user_message(msg):
    st.session_state.chat_history.append({"role":"user","content":msg})

def add_ai_message(msg):
    st.session_state.chat_history.append({"role":"ai","content":msg})

def build_ai_prompt(user_input):
    pdf_text = st.session_state.pdf_summary or ""
    refs = st.session_state.extracted_refs or "None"
    prompt = f"""
    You are a GSK medical sales assistant. Use PDF summary if available.
    Follow sales call flow: {', '.join(sales_call_flow)}
    Handle objections with APACT: {', '.join(APACT_STEPS)}
    PDF Summary:\n{pdf_text}
    References:\n{refs}
    Filter settings: Brand={brand}, Segment={segment}, Barrier={barrier}, Objective={objective}, Specialty={specialty}, Persona={persona}, Tone={response_tone}, Length={response_length}
    User question: {user_input}
    """
    return prompt

async def _edge_save_async(ssml_text: str, voice: str, outpath: str):
    comm = edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts(text):
    text = re.sub(r'[.;:/,]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    ssml = f"<speak>{text}</speak>"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_name = tmp.name
    tmp.close()
    try:
        asyncio.run(_edge_save_async(ssml, st.session_state.voice_pref, tmp_name))
        with open(tmp_name,"rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        st.warning(f"TTS failed: {e}")
        return None

def render_chat():
    for chat in st.session_state.chat_history:
        content = html.escape(chat["content"])
        if chat["role"]=="user":
            st.markdown(f'<div class="chat-bubble-user">{content}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-ai">{content}</div>', unsafe_allow_html=True)
    st.markdown("""
    <script>
    var chatDiv = window.parent.document.querySelectorAll('.chat-container')[0];
    if(chatDiv) chatDiv.scrollTop = chatDiv.scrollHeight;
    </script>
    """, unsafe_allow_html=True)

def call_groq_ai(prompt):
    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role":"system","content":"You are a helpful GSK sales assistant."},{"role":"user","content":prompt}]
        )
        return resp.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI Error: {str(e)}"

# ---------------------------- CHAT BOX ----------------------------
st.markdown('<div class="chat-container"></div>', unsafe_allow_html=True)
render_chat()

st.markdown(f"""
<div class="bottom-bar">
<input type="text" id="chat_input" placeholder="Type your message...">
<button onclick="document.getElementById('chat_send').click()">Send</button>
</div>
""", unsafe_allow_html=True)

user_input = st.text_input("💬 Type your message here", key="chat_input_box")
if st.button("Send", key="chat_send") and user_input:
    add_user_message(user_input)
    ai_resp = call_groq_ai(build_ai_prompt(user_input))
    add_ai_message(ai_resp)
    # Generate TTS
    audio_b64 = synthesize_tts(ai_resp)
    if audio_b64:
        st.markdown(f"<audio controls src='data:audio/mp3;base64,{audio_b64}'></audio>", unsafe_allow_html=True)
    st.experimental_rerun()

# ---------------------------- EXPORT CHAT ----------------------------
if st.session_state.chat_history:
    if st.button("📥 Export Chat to Word"):
        doc = Document()
        doc.add_heading("GSK AI Sales Call Assistant Chat",0)
        for msg in st.session_state.chat_history:
            role = "User" if msg["role"]=="user" else "AI"
            doc.add_paragraph(f"{role}: {msg['content']}")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        doc.save(tmp.name)
        with open(tmp.name,"rb") as f:
            st.download_button("⬇️ Download Chat (.docx)", f, file_name="GSK_AI_Chat.docx")
