# app.py
import streamlit as st
from PIL import Image, ImageStat
import requests
from io import BytesIO, BytesIO as io_bytes
import groq
from groq import Groq
from datetime import datetime
import PyPDF2
import asyncio
import edge_tts
import base64
import re
import os
import tempfile

# ----------------------------
# Page config
# ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", page_icon="💡", layout="wide")

# ----------------------------
# Optional Word download (docx)
# ----------------------------
try:
    from docx import Document
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# ----------------------------
# GROQ client (replace with your key)
# ----------------------------
GROQ_API_KEY = "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"  # <- REPLACE with your key
client = Groq(api_key=GROQ_API_KEY)

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

# ----------------------------
# Assets & styling variables
# ----------------------------
BACKGROUND_URL = ("https://sdmntpreastus.oaiusercontent.com/files/00000000-d8fc-61f9-a032-8b22cd0506d4/raw?se=2025-09-27T15%3A26%3A11Z&sp=r&sv=2024-08-04&sr=b&scid=94806956-ceed-5d91-8345-e5c58fe80700&skoid=6658dbdd-f305-4d30-8f6b-d62218202cb9&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-26T17%3A00%3A28Z&ske=2025-09-27T17%3A00%3A28Z&sks=b&skv=2024-08-04&sig=H0sSlc9j5wxHuYfQPjkJwkd417JLlDNhIgpE9eK4xp4%3D")

GSK_LOGO_URL = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"

# compute brightness to pick text color
def get_brightness(url):
    try:
        r = requests.get(url, timeout=8)
        img = Image.open(BytesIO(r.content)).convert("L")
        stat = ImageStat.Stat(img)
        return stat.mean[0]
    except Exception:
        return 255

brightness = get_brightness(BACKGROUND_URL)
text_color = "black" if brightness > 130 else "white"
button_bg = "#FFA500" if brightness > 130 else "#FF8C00"

# ----------------------------
# CSS (background, logo, layout)
# ----------------------------
CSS = f"""
<style>
.stApp {{
    background: url('{BACKGROUND_URL}') no-repeat right top;
    background-size: contain;
    background-attachment: fixed;
}}
.gsk-logo {{
    position: fixed;
    top: 60px;   /* ~3 cm below the top bar */
    right: 16px;
    z-index: 1000;
}}
.title-box {{
    background: rgba(245,245,245,0.55);
    padding: 35px;
    border-radius: 18px;
    text-align: center;
    max-width: 80%;
    margin: 12px auto;
}}
.title-box h1 {{
    margin: 0;
    font-size: 42px;
    font-weight: 800;
}}
.title-box p {{
    margin: 8px 0 0 0;
    font-size: 20px;
    font-weight: 500;
}}
.disclaimer {{
    text-align: center;
    padding: 12px;
    font-size: 15px;
    font-weight: 500;
    margin-bottom: 10px;
}}
.chat-bubble-user {{
    text-align: right;
    background: rgba(220,248,198,0.95);
    padding: 12px;
    border-radius: 15px 15px 0px 15px;
    margin: 6px;
    display: inline-block;
    max-width: 80%;
    color: {text_color};
}}
.chat-bubble-ai {{
    text-align: left;
    background: rgba(240,242,246,0.95);
    padding: 12px;
    border-radius: 15px 15px 15px 0px;
    margin: 6px;
    display: inline-block;
    max-width: 80%;
    color: {text_color};
}}
.highlight {{
    font-weight: bold;
    background-color: yellow;
    color: black;
    padding: 2px 4px;
    border-radius: 4px;
}}
.chat-input-container {{
    display:flex;
    margin-top:10px;
}}
.chat-input-container input {{
    flex:1;
    padding:12px;
    border-radius:20px;
    border:none;
    outline:none;
    backdrop-filter: blur(8px);
    background-color: rgba(255,255,255,0.4);
    color: {text_color};
}}
.chat-input-container button {{
    margin-left:5px;
    border:none;
    border-radius:50%;
    width:45px;
    height:45px;
    cursor:pointer;
    font-weight:bold;
    background-color: {button_bg};
    color: white;
}}
.clear-chat {{
    position: fixed;
    bottom: 20px;
    left: 20px;
    z-index: 1000;
}}
.sidebar-bold {{
    background: rgba(255,255,255,0.85);
    padding: 10px;
    border-radius: 8px;
    font-weight:700;
    margin-bottom:8px;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ----------------------------
# Top-right GSK logo + centered title + disclaimer
# ----------------------------
st.markdown(f"""<div class="gsk-logo"><img src="{GSK_LOGO_URL}" width="140"></div>""", unsafe_allow_html=True)
st.markdown("""
<div class="title-box">
  <h1>💡 AI Sales Call Assistant</h1>
  <p>Powered by AI to equip sales reps for smarter HCP conversations</p>
</div>
""", unsafe_allow_html=True)
st.markdown('<p class="disclaimer">⚠️ Disclaimer: For training and educational purposes only.</p>', unsafe_allow_html=True)

# ----------------------------
# Top-left language selector
# ----------------------------
st.markdown("""
<div style="position:fixed; top:72px; left:18px; z-index:1000; background: rgba(255,255,255,0.9); padding:8px 12px; border-radius:8px;">
""", unsafe_allow_html=True)
language = st.radio("", options=["English", "العربية"], horizontal=True, label_visibility="collapsed")
st.markdown("</div>", unsafe_allow_html=True)

# ----------------------------
# Data definitions (brands, segments etc.)
# ----------------------------
gsk_brands = {
    "Shingrix": "https://www.shingrix.com/",
    "Trelegy": "https://www.trelegy.com/",
    "Zejula": "https://www.zejula.com/"
}
gsk_brands_images = {
    "Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Trelegy": "https://www.1uphealth.com/wp-content/uploads/2020/11/trelegy.png",
    "Zejula": "https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png"
}

race_segments = [
    "R – Reach: Not prescribing yet; doesn't see vaccination responsibility.",
    "A – Acquisition: Prescribes when patient asks; convinced by data.",
    "C – Conversion: Initiates for specific profiles; not across all profiles.",
    "E – Engagement: Proactively prescribes across multiple patient profiles."
]

doctor_barriers = [
    "HCP does not consider HZ a risk",
    "No time for discussion",
    "Cost concerns",
    "Not convinced of efficacy",
    "Accessibility/Logistics",
    "Patient reluctance",
    "Other clinical doubts"
]

personas = [
    "Uncommitted Vaccinator",
    "Reluctant Efficiency",
    "Patient Influenced",
    "Committed Vaccinator"
]

gsk_approaches = [
    "Use data-driven evidence (local + global studies)",
    "Focus on patient outcomes & quality of life",
    "Leverage brief storytelling and peer endorsement",
    "Address practical barriers (access, scheduling, cost solutions)"
]

sales_call_flow = [
    "Prepare: Data & patient profiles",
    "Engage: Opening question & rapport",
    "Create Opportunities: Identify eligible patients",
    "Influence: Present tailored evidence & handle objections",
    "Drive Impact: Secure next steps (prescription/scheduling)",
    "Post Call Analysis: Document & follow up"
]

APACT_STEPS = ["Acknowledge", "Probing", "Action", "Confirm", "Transition"]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]

# ----------------------------
# Sidebar filters (brand image placed right under brand selector)
# ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    st.markdown('<div class="sidebar-bold">Filters & Options</div>', unsafe_allow_html=True)
    brand = st.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))
    # brand image under brand selector
    img_path = gsk_brands_images.get(brand)
    if img_path:
        try:
            resp = requests.get(img_path, timeout=8)
            img = Image.open(BytesIO(resp.content))
            st.image(img, width=200)
        except Exception:
            st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)

    segment = st.selectbox("Select RACE Segment / اختر شريحة RACE", options=race_segments)
    barrier = st.multiselect("Select Doctor Barrier / اختر حاجز الطبيب", options=doctor_barriers, default=[])
    objective = st.selectbox("Select Objective / اختر الهدف", options=objectives)
    specialty = st.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", options=specialties)
    persona = st.selectbox("Select HCP Persona / اختر شخصية الطبيب", options=personas)
    response_length = st.selectbox("Response Length / اختر طول الرد", ["Short", "Medium", "Long"])
    response_tone = st.selectbox("Response Tone / اختر نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])
    interface_mode = st.radio("Interface Mode / اختر واجهة", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# ----------------------------
# PDF upload & summarization (sidebar)
# ----------------------------
with st.sidebar:
    st.markdown("---")
    st.subheader("📄 Upload Medical Reference PDF")
    uploaded_pdf = st.file_uploader("Upload PDF for AI reference", type=["pdf"])
    show_more_toggle = st.checkbox("Show full PDF text", value=False)
    if uploaded_pdf:
        try:
            reader = PyPDF2.PdfReader(uploaded_pdf)
            full_text = ""
            for p in reader.pages:
                full_text += (p.extract_text() or "") + "\n"
            st.session_state.uploaded_pdf_text = full_text if show_more_toggle else full_text[:1000] + "..."
            # extract refs heuristically
            matches = re.findall(r"(?:CDC|FDA|Guideline|Study|Journal|20\d{2}|Lancet|NEJM)[^.\n]*", full_text, flags=re.I)
            st.session_state.extracted_medical_ref = ", ".join(matches) if matches else ""
            st.success("✅ PDF processed")
            if st.button("Summarize PDF"):
                # keep summary prompt size reasonable
                text_for_summary = full_text[:6000]
                summary_prompt = (
                    f"Summarize this medical document for sales reps for {brand}. Focus on actionable findings, "
                    f"key results, practical recommendations and anything the rep can use during a call. Language: {language}.\n\n"
                    + text_for_summary
                )
                try:
                    summary_resp = client.chat.completions.create(
                        model="meta-llama/llama-4-scout-17b-16e-instruct",
                        messages=[
                            {"role": "system", "content": "You are a concise medical summarizer for sales teams."},
                            {"role": "user", "content": summary_prompt}
                        ],
                        temperature=0.3
                    )
                    st.session_state.pdf_summary = summary_resp.choices[0].message.content
                except Exception as e:
                    st.session_state.pdf_summary = f"⚠️ Error summarizing PDF: {e}"
                st.markdown("### 📑 PDF Summary")
                st.write(st.session_state.pdf_summary)
                if st.session_state.extracted_medical_ref:
                    st.info(f"📚 Extracted references: {st.session_state.extracted_medical_ref}")
        except Exception as e:
            st.error(f"PDF error: {e}")

# ----------------------------
# Chat display area
# ----------------------------
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()

def display_chat():
    html = ""
    for msg in st.session_state.chat_history:
        content = msg["content"].replace("\n", "<br>")
        # highlight APACT steps
        for step in APACT_STEPS:
            content = content.replace(step, f"<span class='highlight'>{step}</span>")
        ts = msg.get("time", "")
        audio_html = ""
        if msg.get("audio"):
            audio_html = f"<br><audio controls style='margin-top:8px;'><source src='data:audio/mp3;base64,{msg['audio']}' type='audio/mp3'></audio>"
        if msg["role"] == "user":
            html += f"<div class='chat-bubble-user'>{content}<br><span style='font-size:10px;color:gray'>{ts}</span></div>"
        else:
            html += f"<div class='chat-bubble-ai'>{content}<br><span style='font-size:10px;color:gray'>{ts}</span>{audio_html}</div>"
    chat_placeholder.markdown(html, unsafe_allow_html=True)

display_chat()

# ----------------------------
# Chat input form (bottom of chat area)
# ----------------------------
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message... / اكتب رسالتك هنا", key="user_input_box")
    submitted = st.form_submit_button("➤")

# ----------------------------
# TTS: create mp3 with edge_tts and return base64 string
# ----------------------------
def synthesize_tts_base64(text, lang):
    if not text or not text.strip():
        return None
    # choose voice
    voice = "ar-EG-SalmaNeural" if lang == "العربية" else "en-US-JennyNeural"
    # save to a temporary file
    tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tmp_name = tmp.name
    tmp.close()
    try:
        async def _save():
            comm = edge_tts.Communicate(text, voice=voice)
            await comm.save(tmp_name)
        asyncio.run(_save())
        with open(tmp_name, "rb") as f:
            audio_bytes = f.read()
        return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        st.warning(f"⚠️ TTS failed: {e}")
        return None
    finally:
        try:
            if os.path.exists(tmp_name):
                os.remove(tmp_name)
        except Exception:
            pass

# ----------------------------
# Handle submitted input (prepare prompt, call Groq, TTS, append chat)
# ----------------------------
if submitted and user_input.strip():
    # append user message
    st.session_state.chat_history.append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})
    display_chat()

    # Build the prompt - include PDF summary / refs if available
    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)
    medical_ref_str = st.session_state.extracted_medical_ref or "None"
    pdf_summary_text = st.session_state.pdf_summary or "None"
    pdf_preview = st.session_state.uploaded_pdf_text or "No PDF uploaded."

    prompt_lines = [
        f"Language: {language}",
        f"User input: {user_input}",
        f"Brand: {brand}",
        f"RACE Segment: {segment}",
        f"Doctor Barrier(s): {', '.join(barrier) if barrier else 'None'}",
        f"Objective: {objective}",
        f"Doctor Specialty: {specialty}",
        f"HCP Persona: {persona}",
        f"Medical Reference(s): {medical_ref_str}",
        "",
        "Uploaded PDF (preview):",
        pdf_preview,
        "",
        "PDF AI Summary (if available):",
        pdf_summary_text,
        "",
        "Approved Sales Approaches:",
        approaches_str,
        "",
        "Sales Call Flow Steps:",
        flow_str,
        "",
        "Use APACT (Acknowledge → Probing → Action → Confirm → Transition) technique for handling objections.",
        f"Response Length: {response_length}",
        f"Response Tone: {response_tone}",
        "Provide actionable sales-call suggestions, a concise summary of the PDF content (if present), and a short 3–6 line script the rep can say. Clearly label APACT steps in the script."
    ]
    prompt = "\n".join(prompt_lines)

    # Call Groq
    try:
        resp = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role":"system","content":f"You are a helpful sales assistant that responds in {language}."},
                {"role":"user","content":prompt}
            ],
            temperature=0.7
        )
        ai_output = resp.choices[0].message.content
    except Exception as e:
        ai_output = f"⚠️ Error generating response: {e}"

    # Synthesize TTS and embed audio
    audio_b64 = synthesize_tts_base64(ai_output, language)
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M"), "audio": audio_b64})

    display_chat()

# ----------------------------
# Clear Chat (fixed bottom-left)
# ----------------------------
clear_clicked = st.button("🗑️ Clear Chat / مسح المحادثة", key="clear_chat", help="Clear conversation history")
if clear_clicked:
    st.session_state.chat_history = []
    st.session_state.uploaded_pdf_text = ""
    st.session_state.extracted_medical_ref = ""
    st.session_state.pdf_summary = ""
    st.experimental_rerun()

# ----------------------------
# Word download (latest AI reply)
# ----------------------------
if DOCX_AVAILABLE and st.session_state.chat_history:
    latest_ai = [m["content"] for m in st.session_state.chat_history if m["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io_bytes()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")

# ----------------------------
# Brand leaflet link
# ----------------------------
st.markdown(f"[📄 Brand Leaflet - {brand}]({gsk_brands[brand]})")
