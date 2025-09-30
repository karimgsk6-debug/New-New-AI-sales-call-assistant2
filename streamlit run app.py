# app.py
import os, re, asyncio
from io import BytesIO
from datetime import datetime
import streamlit as st
from PIL import Image, ImageStat
import requests, PyPDF2, edge_tts
try:
    import groq
    from groq import Groq
    GROQ_API_KEY = "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"
    client = Groq(api_key=GROQ_API_KEY)
except:
    client = None

# Optional docx export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", page_icon="💡", layout="wide")

# ----------------------------
# Session state defaults
# ----------------------------
for key in ["chat_history","uploaded_pdf_text","pdf_summary","language","tts_file"]:
    if key not in st.session_state: st.session_state[key] = "" if "text" in key or "pdf" in key else []

# ----------------------------
# Assets & styling
# ----------------------------
BACKGROUND_URL = "https://drive.google.com/uc?id=1WlvNx4MqufxuGUw9ilLxGJLsuozbX17b"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"

def get_brightness(url): 
    try: 
        r = requests.get(url, timeout=6)
        img = Image.open(BytesIO(r.content)).convert("L")
        return int(ImageStat.Stat(img).mean[0])
    except: return 255
text_color = "black" if get_brightness(BACKGROUND_URL)>130 else "white"

CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat;
  background-position: right top;
  background-attachment: fixed;
  background-size: auto 150%;
}}
.title-box {{ background: rgba(240,240,240,0.6); padding:20px; border-radius:14px; text-align:center; max-width:75%; margin:12px auto; }}
.title-box h1 {{ margin:0; font-size:36px; font-weight:800; color:#000; }}
.title-box p {{ margin:6px 0 0 0; font-size:20px; color:#000; }}
.chat-container {{ height:56vh; overflow:auto; padding:12px; border-radius:10px; background: rgba(255,255,255,0.8); }}
.chat-bubble-user {{ background:#eef9e6; margin-left:auto; border:1px solid #c2e0b0; padding:12px; border-radius:14px; max-width:40%; word-wrap: break-word; }}
.chat-bubble-ai {{ background:#f5f7fa; margin-right:auto; border:1px solid #a0c4ff; padding:12px; border-radius:14px; max-width:75%; word-wrap: break-word; }}
.sales-step {{ background:#fff3e0; border-left:4px solid #ff8c00; padding:10px; margin:6px 0; border-radius:6px; }}
.apact-step {{ font-weight:700; color:#2980b9; }}
.bottom-bar {{ position: fixed; bottom:12px; left:16px; right:16px; background:rgba(255,255,255,0.98); padding:10px; border-radius:20px; display:flex; gap:12px; align-items:center; }}
.bottom-bar input[type="text"] {{ flex:1; padding:10px 12px; border-radius:20px; border:1px solid #ddd; }}
.bottom-bar button {{ min-width:80px; padding:8px 12px; border-radius:20px; background:#ff8c00; color:white; border:none; font-weight:600; cursor:pointer; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
SCROLL_JS = """<script>function scrollChat(){const el=document.querySelector('.chat-container');if(el) el.scrollTop=el.scrollHeight;}setTimeout(scrollChat,200);</script>"""
st.markdown(f'<div style="position:auto; right:30px; top:80px; z-index:1200;"><img src="{GSK_LOGO_URL}" width="140"/></div>', unsafe_allow_html=True)
st.markdown('<div class="title-box"><h1>💡 AI Sales Call Assistant</h1><p>Powered by AI to equip reps for smarter HCP conversations</p></div>', unsafe_allow_html=True)

# ----------------------------
# Filters & selections
# ----------------------------
gsk_brands = {"Shingrix":"https://www.shingrix.com/","Trelegy":"https://www.trelegy.com/","Zejula":"https://www.zejula.com/"}
race_segments = ["R – Reach","A – Acquisition","C – Conversion","E – Engagement"]
doctor_barriers = ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy",
                   "Accessibility/Logistics","Patient reluctance","Other clinical doubts"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist",
               "Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"]
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Select Brand", list(gsk_brands.keys()))
    segment = st.selectbox("Select RACE Segment", race_segments)
    barrier = st.multiselect("Select Doctor Barrier", doctor_barriers, default=[])
    objective = st.selectbox("Select Objective", objectives)
    specialty = st.selectbox("Select Doctor Specialty", specialties)
    persona = st.selectbox("Select HCP Persona", personas)
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"])
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"])
    tts_lang = st.radio("Voice", ["English","العربية"], index=0)

# ----------------------------
# Sales & APACT steps
# ----------------------------
sales_call_steps = ["1-Prepare","2-Engage","3-Create opportunities","4-Impact GSO_good sell out come","5-Influence","6-Poast call analysis"]
APACT_STEPS = ["Acknowledge","Probing","Confirm","Action","Transition to next step"]

# ----------------------------
# PDF upload & summary
# ----------------------------
st.markdown("### 📄 Upload Medical Reference PDF (Optional)")
uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text
    except: pass

# ----------------------------
# TTS helper
# ----------------------------
async def generate_tts(text, lang="en"):
    clean_text = re.sub(r"[^a-zA-Z0-9 .,؟!?]", "", text)
    if not clean_text.strip(): return None
    file_name = f"tts_{datetime.now().strftime('%H%M%S')}.mp3"
    comm = edge_tts.Communicate(clean_text, voice="en-US-AriaNeural" if lang=="en" else "ar-EG-SalmaNeural")
    await comm.save(file_name)
    return file_name

# ----------------------------
# Render chat
# ----------------------------
def render_chat_history():
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for entry in st.session_state.chat_history:
        role = entry.get("role","user")
        content = entry.get("content","")
        if role=="user":
            st.markdown(f'<div class="chat-bubble-user">{content}</div>', unsafe_allow_html=True)
        else:
            # Split AI response into sales call steps blocks
            for step in sales_call_steps:
                step_content = ""
                pattern = re.compile(f"{re.escape(step)}(.*?)(?=" + "|".join([re.escape(s) for s in sales_call_steps if s!=step]) + "|$)", re.DOTALL)
                match = pattern.search(content)
                if match: step_content = match.group(1).strip()
                if step_content:
                    # highlight APACT
                    for apact in APACT_STEPS:
                        step_content = step_content.replace(apact,f'<span class="apact-step">{apact}</span>')
                    st.markdown(f'<div class="chat-bubble-ai"><div class="sales-step"><b>{step}</b><br>{step_content.replace(chr(10),"<br>")}</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown(SCROLL_JS, unsafe_allow_html=True)

render_chat_history()

# ----------------------------
# Bottom input + send
# ----------------------------
st.markdown('<div class="bottom-bar">', unsafe_allow_html=True)
col1, col2 = st.columns([6,1])
with col1:
    user_input = st.text_input("Type your question...", key="bottom_input")
with col2:
    if st.button("Send") and user_input.strip():
        st.session_state.chat_history.append({"role":"user","content":user_input})
        prompt = f"""
        Answer specifically for product {brand} for HCPs.
        Include medical references from PDF if uploaded, else general evidence.
        Structure according to GSK sales call steps: {', '.join(sales_call_steps)}.
        Inject APACT: {', '.join(APACT_STEPS)} to address HCP concerns.
        Tone: {response_tone}, Length: {response_length}.
        Question: {user_input}
        Reference: {st.session_state.uploaded_pdf_text[:3000]}
        """
        if client:
            resp = client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=[{"role":"system","content":"You are a pharma sales AI expert, product-specific, using medical references."},
                          {"role":"user","content":prompt}],
                temperature=0.2
            )
            ai_resp = resp.choices[0].message.content.strip()
        else:
            ai_resp = "Set GROQ_API_KEY to generate AI responses."

        st.session_state.chat_history.append({"role":"ai","content":ai_resp})
        # Generate TTS
        tts_file = asyncio.run(generate_tts(ai_resp, lang="en" if tts_lang=="English" else "ar"))
        st.session_state.tts_file = tts_file
        render_chat_history()
st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------
# Clear chat & download
# ----------------------------
col1, col2 = st.columns([1,1])
with col1:
    if st.button("Clear Chat"):
        st.session_state.chat_history = []
        render_chat_history()
with col2:
    if DOCX_AVAILABLE and st.session_state.chat_history:
        last_ai = next((c["content"] for c in reversed(st.session_state.chat_history) if c["role"]=="ai"), None)
        if last_ai:
            doc = Document()
            doc.add_paragraph(last_ai)
            doc_name = f"AI_Response_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
            doc.save(doc_name)
            with open(doc_name,"rb") as f:
                st.download_button("Download AI Response as Word", f.read(), file_name=doc_name)
# ----------------------------
# Play TTS button
# ----------------------------
if st.session_state.tts_file:
    st.audio(st.session_state.tts_file, format="audio/mp3")
