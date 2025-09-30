import os, re, time, base64, tempfile, asyncio
from datetime import datetime
from io import BytesIO
import streamlit as st
from PIL import Image, ImageStat
import requests, PyPDF2, edge_tts, html

try:
    import groq
    from groq import Groq
except Exception:
    Groq = None

try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False

# ----------------------------
# Page config
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ----------------------------
# GROQ API Key
GROQ_API_KEY = "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"  # <--- Insert your GROQ API key here
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY and Groq else None
if client is None:
    st.info("⚠️ GROQ AI client not configured. Responses will not be generated.")

# ----------------------------
# Session state defaults
if "chat_history" not in st.session_state: st.session_state.chat_history=[]
if "uploaded_pdf_text" not in st.session_state: st.session_state.uploaded_pdf_text=""
if "extracted_medical_ref" not in st.session_state: st.session_state.extracted_medical_ref=""
if "pdf_summary" not in st.session_state: st.session_state.pdf_summary=""
if "language" not in st.session_state: st.session_state.language="English"
if "voice_pref" not in st.session_state: st.session_state.voice_pref="English Neural"

# ----------------------------
# Assets & Variables
BACKGROUND_URL = "https://www.shutterstock.com/image-photo/excited-girl-white-shirt-using-260nw-708132598.jpg"
GSK_LOGO_URL = "https://i-cf65.gskstatic.com/content/dam/cf-pharma/gskusmedicalaffairs/en_US/logos/gsk-logo-white.png?auto=format"

def get_brightness(url: str) -> int:
    try:
        r = requests.get(url, timeout=6)
        img = Image.open(BytesIO(r.content)).convert("L")
        stat = ImageStat.Stat(img)
        return int(stat.mean[0])
    except Exception:
        return 255

brightness = get_brightness(BACKGROUND_URL)
text_color = "black" if brightness > 130 else "white"

# ----------------------------
# Styling CSS
st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url("{BACKGROUND_URL}");
  background-repeat: no-repeat; background-position: right top; background-attachment: fixed;
  background-size: auto 150%; transition: background-size 0.25s ease;
}}
.chat-container {{ height:56vh; overflow:auto; padding:12px; border-radius:10px; background: rgba(255,255,255,0.76); }}
.chat-bubble-user {{ display:inline-block; padding:12px; border-radius:12px; margin:8px 0; max-width:86%; word-wrap: break-word; background:#eef9e6; margin-left:auto; }}
.chat-bubble-ai {{ display:inline-block; padding:12px; border-radius:12px; margin:8px 0; max-width:86%; word-wrap: break-word; background:#f5f7fa; margin-right:auto; }}
.pdf-summary-inline {{ margin-top:8px; background: rgba(245,245,245,0.7); padding:10px; border-radius:8px; border:1px solid #1111; }}
.bottom-bar {{ position:fixed; bottom:12px; left:16px; right:16px; z-index:1200; background: rgba(255,255,255,0.98); padding:10px; border-radius:12px; display:flex; gap:12px; align-items:center; }}
.bottom-bar input[type="text"] {{ flex:1; padding:10px 12px; border-radius:8px; border:1px solid #ddd; outline:none; }}
.bottom-bar button {{ min-width:110px; padding:8px 12px; border-radius:8px; background:#ff8c00; color:white; border:none; font-weight:600; cursor:pointer; }}
.highlight-step {{ font-weight:700; color:#000; }}
.highlight-figure {{ font-weight:700; color:#d35400; }}
</style>
""", unsafe_allow_html=True)

# Auto-scroll chat
st.markdown("""
<script>
function scrollChat(){ const el=document.querySelector('.chat-container'); if(el) el.scrollTop = el.scrollHeight; }
setInterval(scrollChat, 500);
</script>
""", unsafe_allow_html=True)

# ----------------------------
# Brands & Filters
gsk_brands = {"Shingrix": "https://www.shingrix.com/", "Trelegy":"https://www.trelegy.com/", "Zejula":"https://www.zejula.com/"}
gsk_brands_images = {
    "Shingrix":"https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Trelegy":"https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
    "Zejula":"https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png"
}
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = ["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy","Accessibility/Logistics","Patient reluctance","Other clinical doubts"]
personas = ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"]
sales_call_flow = ["Prepare the call","Engage","Create opportunities","Impact GSO","Influence","Analyze & Post Call"]
APACT_STEPS = ["Acknowledge","Probing","Action","Confirm","Transition"]
objectives = ["Awareness","Adoption","Retention"]
specialties = ["GP","Cardiologist","Dermatologist","Endocrinologist","Pulmonologist","Rheumatologist","Internal Medicine","Diabetologist","Neurologist","Pneumologist"]

# ----------------------------
# Sidebar Filters
with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown('<div style="font-weight:800; margin-bottom:8px;">Filters & Options</div>', unsafe_allow_html=True)
    brand = st.selectbox("Brand", options=list(gsk_brands.keys()))
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try: st.image(Image.open(BytesIO(requests.get(img_path,timeout=6).content)), width=160)
        except: st.image("https://via.placeholder.com/160x90.png?text=No+Image", width=160)
    segment = st.selectbox("RACE Segment", options=race_segments)
    barrier = st.multiselect("Doctor Barrier", options=doctor_barriers, default=[])
    objective = st.selectbox("Objective", options=objectives)
    specialty = st.selectbox("Doctor Specialty", options=specialties)
    persona = st.selectbox("HCP Persona", options=personas)
    response_length = st.selectbox("Response Length", ["Short","Medium","Long"])
    response_tone = st.selectbox("Response Tone", ["Formal","Casual","Friendly","Persuasive"])
    st.session_state.language = st.radio("Language", ["English","العربية"], index=0, horizontal=True)
    st.session_state.voice_pref = st.selectbox("Voice preference", ["English Neural","Arabic Neural","Default"])

# ----------------------------
# PDF Upload
st.markdown("### 📄 Upload Medical Reference PDF")
uploaded_pdf = st.file_uploader("Upload PDF", type=["pdf"])
if uploaded_pdf:
    try:
        reader = PyPDF2.PdfReader(uploaded_pdf)
        full_text = "".join([p.extract_text() or "" for p in reader.pages])
        st.session_state.uploaded_pdf_text = full_text[:2000]+"..." if len(full_text)>2000 else full_text
        refs = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM|BMJ|JAMA)[^.\n]*", full_text, flags=re.I)
        st.session_state.extracted_medical_ref = ", ".join(refs) if refs else "None"

        # Chunk & summarize via Groq
        if client:
            chunk_size=5000; chunks=[full_text[i:i+chunk_size] for i in range(0,len(full_text),chunk_size)]; summaries=[]
            for chunk in chunks:
                summary_prompt=("You are a concise medical summarizer. Produce actionable bullet points.\n\n")+chunk[:6000]
                resp = client.chat.completions.create(model="meta-llama/llama-4-scout-17b-16e-instruct",
                    messages=[{"role":"system","content":"You are a concise medical summarizer."},{"role":"user","content":summary_prompt}],
                    temperature=0.2)
                summaries.append(resp.choices[0].message.content)
            st.session_state.pdf_summary="\n".join(summaries).strip()
        else: st.warning("GROQ not configured. Skipping PDF summarization.")
        if st.session_state.pdf_summary:
            with st.expander("📑 PDF Summary", expanded=False):
                lines=[ln.strip() for ln in st.session_state.pdf_summary.splitlines() if ln.strip()]
                st.markdown("\n".join([f"- {ln}" for ln in lines]))
        if st.session_state.extracted_medical_ref:
            st.info(f"📚 Extracted references: {st.session_state.extracted_medical_ref}")
    except Exception as e: st.error(f"PDF error: {e}")

# ----------------------------
# Highlighting helpers
def highlight_content_for_display(content: str) -> str:
    for step in sales_call_flow: content = re.sub(rf"\b{re.escape(step)}\b", f"<span class='highlight-step'>{step}</span>", content)
    for ap in APACT_STEPS: content = re.sub(rf"\b{re.escape(ap)}\b", f"<span class='highlight-step'>{ap}</span>", content)
    for fig in re.findall(r"\d+\.?\d*%", content): content = content.replace(fig,f"<span class='highlight-figure'>{fig}</span>")
    return content

def build_ai_bubble_content(ai_text: str, inject_pdf_lines: int = 6) -> str:
    text = (ai_text or "").replace("\n","<br>")
    text = highlight_content_for_display(text)
    pdf_html = ""
    if st.session_state.pdf_summary:
        pdf_lines=[ln.strip() for ln in st.session_state.pdf_summary.splitlines() if ln.strip()][:inject_pdf_lines]
        pdf_html="<div class='pdf-summary-inline'>"+("<br>".join(pdf_lines))+"</div>"
    return pdf_html+text

# ----------------------------
# Build AI prompt
def build_prompt(user_input, language):
    pdf_summary = st.session_state.pdf_summary or ""
    refs = st.session_state.extracted_medical_ref or "None"
    instructions = [
        "- Use PDF summary & extracted medical references for clinical claims.",
        "- Cite references when available (e.g., CDC, NEJM).",
        "- Provide a short 'Sample script' (3–6 lines) for the rep.",
        "- Match requested tone and length."
    ]
    if re.search(r"\b(sales call flow|call flow|sales steps)\b", user_input, flags=re.I):
        steps_text = ", ".join([f"**{s}**" for s in sales_call_flow])
        instructions.append(f"When asked for 'sales call flow', return steps as bold bullet points in order: {steps_text}. Provide 1–2 action lines per step.")
    if re.search(r"\b(objection|concern|barrier|hesitat|not convinced|resist)\b", user_input, flags=re.I):
        instructions.append("Structure objections using APACT: **Acknowledge**, **Probing**, **Action**, **Confirm**, **Transition**. Bold APACT titles.")
    instructions.append("Bold sales steps, APACT titles, and numeric figures (e.g., 45%).")
    prompt_parts = [
        f"Language: {language}",
        f"User input: {user_input}",
        f"Brand: {brand}",
        f"RACE Segment: {segment}",
        f"Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}",
        f"Objective: {objective}",
        f"Doctor Specialty: {specialty}",
        f"HCP Persona: {persona}",
        "",
        "Instructions:", *instructions, "",
        "PDF Summary:", pdf_summary or "None", "",
        "Extracted references:", refs, "",
        f"Response tone: {response_tone}. Desired length: {response_length}."
    ]
    return "\n".join(prompt_parts)

# ----------------------------
# Call Groq AI
def call_groq_with_retry(prompt, language, max_retries=3, base_delay=2):
    if client is None: return "⚠️ AI service not configured. Set GROQ_API_KEY."
    models = ["meta-llama/llama-4-scout-17b-16e-instruct", "meta-llama/llama-4-scout-13b-instruct"]
    last_err = None
    for model in models:
        for attempt in range(1, max_retries+1):
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role":"system","content":f"You are a helpful sales assistant in {language}."},
                              {"role":"user","content":prompt}],
                    temperature=0.65
                )
                return resp.choices[0].message.content
            except Exception as e:
                last_err = e; err_msg = str(e).lower()
                if "over capacity" in err_msg or "503" in err_msg or "internal_server_error" in err_msg:
                    wait = base_delay*(2**(attempt-1))
                    st.warning(f"Model {model} busy. Retrying in {wait}s (attempt {attempt}/{max_retries})...")
                    time.sleep(wait); continue
                if "authentication" in err_msg or "unauthorized" in err_msg: return "⚠️ Authentication error with Groq."
                return f"⚠️ Error generating response: {e}"
    return f"⚠️ AI call failed after retries. Last error: {last_err}"

# ----------------------------
# TTS
async def _edge_save_async(ssml_text, voice, outpath):
    comm = edge_tts.Communicate(ssml_text, voice=voice)
    await comm.save(outpath)

def synthesize_tts_humanized(text, lang, voice_pref):
    if not text: return None
    text = re.sub(r'(\d+)\s*%', r'\1 percent', text)
    text = re.sub(r'[;:{}\[\]\*\^<>@#\$%&\|~_/\\+]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    sentences = re.split(r'(?<=[.?!])\s+', text)
    ssml_parts = [f"<prosody rate='medium'>{s}<break time='0.45s'/></prosody>" for s in sentences if s.strip()]
    ssml = "<speak>" + " ".join(ssml_parts) + "</speak>"
    voice = "ar-EG-SalmaNeural" if voice_pref=="Arabic Neural" else "en-US-AriaNeural"
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name = tmp.name; tmp.close()
    try: asyncio.run(_edge_save_async(ssml, voice, tmp_name))
    except: return None
    with open(tmp_name,"rb") as f: data=f.read()
    os.remove(tmp_name)
    return base64.b64encode(data).decode("utf-8")

# ----------------------------
# Render chat
def render_chat_history():
    with st.container():
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)
        for msg in st.session_state.chat_history:
            if msg["role"]=="user":
                st.markdown(f'<div class="chat-bubble-user">{html.escape(msg["content"])}</div>', unsafe_allow_html=True)
            else:
                content_html = build_ai_bubble_content(msg["content"])
                st.markdown(f'<div class="chat-bubble-ai">{content_html}</div>', unsafe_allow_html=True)
                if msg.get("audio"):
                    st.audio(base64.b64decode(msg["audio"]))
        st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------
# Chat input
with st.form("chat_form", clear_on_submit=True):
    user_text = st.text_input("Type your message...", key="chat_input", label_visibility="collapsed")
    submitted = st.form_submit_button("Send")

if submitted and user_text.strip():
    st.session_state.chat_history.append({"role":"user","content":user_text.strip(),"time":datetime.now().strftime("%H:%M")})
    render_chat_history()
    prompt = build_prompt(user_text.strip(), st.session_state.language)
    ai_output = call_groq_with_retry(prompt, st.session_state.language)
    audio_b64 = synthesize_tts_humanized(ai_output, st.session_state.language, st.session_state.voice_pref)
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M"),"audio":audio_b64})
    render_chat_history()

    # Download AI response to Word
    if DOCX_AVAILABLE:
        doc = Document(); doc.add_heading("AI Sales Call Assistant Response",0); doc.add_paragraph(ai_output)
        tmp = tempfile.NamedTemporaryFile(delete=False,suffix=".docx"); doc.save(tmp.name); tmp.close()
        with open(tmp.name,"rb") as f: data=f.read()
        st.download_button("⬇️ Download AI Response (.docx)", data=data, file_name="AI_Response.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

# ----------------------------
# Bottom buttons: clear/export
cols = st.columns([1,1])
with cols[0]:
    if st.button("🗑️ Clear Chat / مسح المحادثة"):
        st.session_state.chat_history=[]
        st.session_state.uploaded_pdf_text=""
        st.session_state.extracted_medical_ref=""
        st.session_state.pdf_summary=""
        st.experimental_rerun()
with cols[1]:
    if DOCX_AVAILABLE and st.session_state.chat_history:
        if st.button("📥 Export Chat History (.docx)"):
            doc = Document(); doc.add_heading("AI Sales Call Assistant Chat History",0)
            for msg in st.session_state.chat_history:
                role="User" if msg.get("role")=="user" else "AI"
                doc.add_paragraph(f"{role} [{msg.get('time','')}]"); text_content=re.sub(r'<.*?>','',msg.get("content",""))
                doc.add_paragraph(text_content)
            tmp=tempfile.NamedTemporaryFile(delete=False,suffix=".docx"); doc.save(tmp.name); tmp.close()
            with open(tmp.name,"rb") as f: data=f.read()
            st.download_button("⬇️ Download Chat History (.docx)", data=data, file_name="chat_history.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
