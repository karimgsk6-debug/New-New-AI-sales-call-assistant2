import streamlit as st
from PIL import Image
import requests
from io import BytesIO
import base64
from docx import Document
import tempfile
import asyncio
import os
import re
from groq import Groq

# ---------------------- CONFIG ----------------------
st.set_page_config(page_title="GSK Sales Call Assistant", layout="wide")

# ---------------------- GROQ API ----------------------
GROQ_API_KEY = "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"
groq_client = Groq(api_key=GROQ_API_KEY)

# ---------------------- ASSETS ----------------------
BACKGROUND_URL = "https://www.shutterstock.com/image-photo/excited-girl-white-shirt-using-260nw-708132598.jpg"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"

# ---------------------- SESSION STATE ----------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = []
if "extracted_refs" not in st.session_state:
    st.session_state.extracted_refs = ""
if "pdf_search" not in st.session_state:
    st.session_state.pdf_search = ""

# ---------------------- STYLING ----------------------
st.markdown(f"""
<style>
.stApp {{
    background: url("{BACKGROUND_URL}") no-repeat right top fixed;
    background-size: auto 150%;
}}

.title-box {{
    position: sticky;
    top: 0;
    z-index: 9999;
    border: 3px solid #ff8c00;
    background: rgba(245,245,245,0.9);
    padding: 25px;
    border-radius: 20px;
    text-align: center;
    max-width: 80%;
    margin: 12px auto;
}}

.title-box h1 {{ margin:0; font-size:34px; font-weight:800; color:#000; }}
.title-box p {{ margin:6px 0 0 0; font-size:16px; color:#333; }}

.chat-container {{
    height: 60vh;
    overflow-y: auto;
    padding: 12px;
    border-radius: 10px;
    background: rgba(220,220,220,0.4);
}}

.chat-bubble-user {{
    background-color: #DCF8C6;
    border-radius: 20px;
    padding: 12px;
    margin: 6px;
    max-width: 70%;
    float: right;
    clear: both;
}}

.chat-bubble-ai {{
    background-color: #fdfdf5;
    border-radius: 20px;
    padding: 12px;
    margin: 6px;
    max-width: 70%;
    float: left;
    clear: both;
    font-size: 15px;
}}

.bottom-bar {{
    position: sticky;
    bottom: 0;
    z-index: 9999;
    background: rgba(255,255,255,0.95);
    padding: 10px;
    display: flex;
    gap: 10px;
    align-items: center;
}}

.bottom-bar input {{
    flex: 1;
    padding: 10px;
    border-radius: 8px;
    border: 1px solid #ddd;
}}

.bottom-bar button {{
    padding: 10px 20px;
    border-radius: 8px;
    background: #ff8c00;
    color: white;
    font-weight: bold;
    border: none;
    cursor: pointer;
}}

.pdf-summary-inline {{
    margin-top:8px;
    background: #fdfdf5;
    padding:10px;
    border-radius:8px;
    border:1px solid #ccc;
}}

.pdf-summary-item {{
    margin-bottom: 6px;
}}

</style>
""", unsafe_allow_html=True)

# ---------------------- TITLE ----------------------
st.markdown(f'<div style="position:auto; top:0; left:18px; z-index:1200;"><img src="{GSK_LOGO_URL}" width="140" /></div>', unsafe_allow_html=True)
st.markdown('<div class="title-box"><h1>💡 GSK AI Sales Call Assistant</h1><p>Equip reps for smarter HCP conversations</p></div>', unsafe_allow_html=True)

# ---------------------- SIDEBAR FILTERS ----------------------
st.sidebar.header("Filters & Options")
brands = ["Shingrix", "Trelegy", "Zejula"]
brand = st.sidebar.selectbox("Select Brand", brands)
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
segment = st.sidebar.selectbox("RACE Segment", race_segments)
doctor_barriers = [
    "HCP does not consider HZ a risk","No time for discussion","Cost concerns",
    "Not convinced of efficacy","Accessibility/Logistics","Patient reluctance","Other clinical doubts"
]
barrier = st.sidebar.multiselect("Doctor Barrier", doctor_barriers, default=[])
objectives = ["Awareness","Adoption","Retention"]
objective = st.sidebar.selectbox("Objective", objectives)
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist","Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"]
specialty = st.sidebar.selectbox("Doctor Specialty", specialties)
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
persona = st.sidebar.selectbox("HCP Persona", personas)
response_tone = st.sidebar.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"])
response_length = st.sidebar.selectbox("Response Length", ["Short","Medium","Long"])

# ---------------------- PDF UPLOAD ----------------------
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
if uploaded_file:
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(uploaded_file)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        # Summarize PDF into bullet points
        summary_prompt = f"Summarize the following PDF medical content into concise, informative bullet points for a sales rep:\n{full_text[:10000]}"
        resp = groq_client.chat.completions.create(
            messages=[{"role":"system","content":"You are a medical summarizer."},{"role":"user","content":summary_prompt}],
            model="llama-3.3-70b-versatile"
        )
        # Keep each bullet point separate line
        st.session_state.pdf_summary = [line.strip() for line in resp.choices[0].message.content.splitlines() if line.strip()]
        # Extract references
        matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_refs = ", ".join(matches) if matches else "None"
    except Exception as e:
        st.error(f"PDF processing error: {e}")

# ---------------------- PDF SUMMARY DISPLAY ----------------------
if st.session_state.pdf_summary:
    st.markdown("### 📑 PDF Summary")
    search_term = st.text_input("🔍 Search PDF Summary", key="pdf_search")
    with st.expander("View PDF Summary", expanded=False):
        for item in st.session_state.pdf_summary:
            if search_term.lower() in item.lower() or search_term=="":
                st.markdown(f"<div class='pdf-summary-item'>- {item}</div>", unsafe_allow_html=True)
if st.session_state.extracted_refs:
    with st.expander("📚 Extracted References", expanded=False):
        st.markdown(st.session_state.extracted_refs)

# ---------------------- SALES CALL FLOW ----------------------
sales_call_flow = [
    "Prepare the call","Engage","Create opportunities",
    "Impact GSO","Influence","Analyze and post call analysis"
]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]

# ---------------------- CHAT HISTORY ----------------------
def render_chat_history():
    st.markdown('<div class="chat-container" id="chat-container">', unsafe_allow_html=True)
    for chat in st.session_state.chat_history:
        content = chat["content"]
        for step in sales_call_flow + APACT_STEPS:
            content = re.sub(rf"\b{re.escape(step)}\b", f"<b>{step}</b>", content)
        if chat["role"]=="user":
            st.markdown(f"<div class='chat-bubble-user'>{content}</div>", unsafe_allow_html=True)
        else:
            bubble_html = content
            if chat.get("audio"):
                bubble_html += f"<br><audio controls style='margin-top:5px;'><source src='data:audio/mp3;base64,{chat['audio']}' type='audio/mp3'></audio>"
            st.markdown(f"<div class='chat-bubble-ai'>{bubble_html}</div>", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    # auto-scroll
    st.markdown("""
        <script>
        var chat = document.getElementById('chat-container');
        chat.scrollTop = chat.scrollHeight;
        </script>
    """, unsafe_allow_html=True)

# ---------------------- TTS ----------------------
async def _edge_save_async(text, voice, outpath):
    import edge_tts
    comm = edge_tts.Communicate(text, voice=voice)
    await comm.save(outpath)

def generate_tts(text: str, voice="en-US-GuyNeural"):
    if not text: return None
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp.close()
    try:
        asyncio.run(_edge_save_async(text, voice, tmp.name))
        with open(tmp.name, "rb") as f:
            return base64.b64encode(f.read()).decode()
    finally:
        os.remove(tmp.name)

# ---------------------- AI RESPONSE ----------------------
def generate_ai_response(user_input):
    filters = f"""
Brand: {brand}
RACE Segment: {segment}
Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Response Tone: {response_tone}
Response Length: {response_length}
"""
    context = f"""
You are a GSK medical sales assistant. Follow Sales Call Flow:
{', '.join(sales_call_flow)}
Handle objections using APACT steps: {', '.join(APACT_STEPS)}
Use PDF Summary and References. Provide structured, actionable responses.
Filters: {filters}
"""
    prompt = f"{context}\nUser question: {user_input}\nPDF Summary:\n{' '.join(st.session_state.pdf_summary)}"
    try:
        response = groq_client.chat.completions.create(
            messages=[{"role":"system","content":context},{"role":"user","content":prompt}],
            model="llama-3.3-70b-versatile"
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI Error: {e}"

# ---------------------- CHAT INPUT ----------------------
st.markdown('<div class="bottom-bar">', unsafe_allow_html=True)
user_input = st.text_input("Type your message...", key="chat_input")
send_btn = st.button("Send")
if send_btn and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input})
    ai_text = generate_ai_response(user_input)
    audio_b64 = generate_tts(ai_text)
    st.session_state.chat_history.append({"role":"ai","content":ai_text,"audio":audio_b64})
render_chat_history()
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------- EXPORT ----------------------
if st.session_state.chat_history:
    doc = Document()
    for msg in st.session_state.chat_history:
        role = "User" if msg["role"]=="user" else "AI"
        doc.add_paragraph(f"{role}: {msg['content']}")
    doc_path = "AI_Response.docx"
    doc.save(doc_path)
    with open(doc_path,"rb") as f:
        st.download_button("⬇️ Download Chat History (.docx)", f, "AI_Response.docx")
