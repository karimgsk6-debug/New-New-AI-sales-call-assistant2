import streamlit as st
from PIL import Image
import requests
from io import BytesIO
import groq
from groq import Groq
from datetime import datetime
import fitz  # PyMuPDF for PDF reading
import base64

# --- Optional dependency for Word download ---
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# --- Groq client ---
client = Groq(api_key="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")

# --- Background Image (external URL) ---
bg_url = "https://sdmntprnortheu.oaiusercontent.com/files/00000000-7268-61f4-9aa6-71a39056c20e/raw?se=2025-09-25T15%3A42%3A47Z&sp=r&sv=2024-08-04&sr=b&scid=dfa0d35f-01ac-5224-bec7-ff9f505758dd&skoid=b32d65cd-c8f1-46fb-90df-c208671889d4&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2025-09-25T09%3A41%3A15Z&ske=2025-09-26T09%3A41%3A15Z&sks=b&skv=2024-08-04&sig=ap%2BO7ty9YJurxH528T8cPoSQD5Kh6VHdsvf/nvdkbjs%3D"
st.markdown(
    f"""
    <style>
    .stApp {{
        background: url('{bg_url}') no-repeat right top;
        background-size: contain;
        background-attachment: fixed;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# --- GSK Logo fixed top-right (3cm below bar) ---
logo_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
st.markdown(f"""
<style>
.gsk-logo {{
    position: fixed;
    top: 100px;  /* ~3cm */
    right: 30px;
    z-index: 1000;
}}
</style>
<div class="gsk-logo">
    <img src="{logo_url}" width="140">
</div>
""", unsafe_allow_html=True)

# --- Title + Disclaimer ---
st.markdown("<h1 style='text-align: center; font-size:40px;'>🧠 AI Sales Call Assistant</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; font-size:18px;'><b>Disclaimer:</b> For training purposes only. Not medical advice.</p>", unsafe_allow_html=True)

# --- Language selector (moved to top-left interface) ---
language = st.radio("🌐 Select Language / اختر اللغة", ["English", "العربية"], horizontal=True)

# --- Brand & product data ---
gsk_brands = {
    "Shingrix": "https://example.com/shingrix-leaflet",
    "Trelegy": "https://example.com/trelegy-leaflet",
    "Zejula": "https://example.com/zejula-leaflet",
}
gsk_brands_images = {
    "Trelegy": "https://www.example.com/trelegy.png",
    "Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/.../shingrix.png",
    "Zejula": "https://cdn.salla.sa/.../zejula.png",
}

# --- Segments, barriers, personas, approaches, call flow ---
race_segments = [
    "R – Reach: Not prescribing, doesn’t see vaccination as responsibility.",
    "A – Acquisition: Prescribes only if patient initiates.",
    "C – Conversion: Proactively prescribes for some patient profiles.",
    "E – Engagement: Actively prescribes across patient profiles."
]
doctor_barriers = [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ Vx effective",
    "Accessibility issues"
]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]
personas = [
    "Uncommitted Vaccinator",
    "Reluctant Efficiency",
    "Patient Influenced",
    "Committed Vaccinator"
]
gsk_approaches = [
    "Use data-driven evidence",
    "Focus on patient outcomes",
    "Leverage storytelling techniques"
]
sales_call_flow = ["Prepare", "Engage", "Create Opportunities", "Influence", "Drive Impact", "Post Call Analysis"]

# --- Sidebar filters ---
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))

# Brand image under brand name
image_path = gsk_brands_images.get(brand)
try:
    if image_path.startswith("http"):
        response = requests.get(image_path)
        img = Image.open(BytesIO(response.content))
    else:
        img = Image.open(image_path)
    st.sidebar.image(img, width=180)
except:
    st.sidebar.warning(f"⚠️ Could not load image for {brand}.")
    st.sidebar.image("https://via.placeholder.com/200x100.png?text=No+Image", width=180)

segment = st.sidebar.selectbox("RACE Segment / شريحة RACE", race_segments)
barrier = st.sidebar.multiselect("Doctor Barrier / حاجز الطبيب", options=doctor_barriers, default=[])
objective = st.sidebar.selectbox("Objective / الهدف", options=objectives)
specialty = st.sidebar.selectbox("Specialty / التخصص", options=specialties)
persona = st.sidebar.selectbox("HCP Persona / شخصية الطبيب", options=personas)
response_length = st.sidebar.selectbox("Response Length / طول الرد", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone / نبرة الرد", ["Formal", "Casual", "Friendly", "Persuasive"])
interface_mode = st.sidebar.radio("Interface Mode / واجهة", ["Chatbot", "Card Dashboard", "Flow Visualization"])

# --- PDF upload & summarization ---
st.subheader("📄 Upload Medical Reference PDF")
uploaded_file = st.file_uploader("Upload PDF", type=["pdf"])
pdf_summary = ""
if uploaded_file:
    pdf_doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text_content = ""
    for page in pdf_doc:
        text_content += page.get_text("text")
    st.success("✅ PDF Uploaded Successfully!")

    if st.button("Summarize PDF"):
        summary_prompt = f"Summarize the following medical reference for {brand} in {language}, focusing on actionable insights:\n\n{text_content[:3000]}"
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[{"role": "system", "content": f"You are a helpful medical summarizer."},
                      {"role": "user", "content": summary_prompt}],
            temperature=0.5
        )
        pdf_summary = response.choices[0].message.content
        st.markdown("### 📑 PDF Summary")
        st.write(pdf_summary)

# --- Chat history ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()

def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time", "")
        content = msg["content"].replace('\n', '<br>')
        apact_steps = ["Acknowledge", "Probing", "Answer", "Confirm", "Transition"]
        for step in apact_steps:
            content = content.replace(step, f"<b>{step}</b><br>")

        if msg["role"] == "user":
            chat_html += f"<div style='text-align:right;background:#dcf8c6;padding:10px;border-radius:15px;margin:5px;max-width:80%;'>{content}<span style='font-size:10px;color:gray;'><br>{time}</span></div>"
        else:
            chat_html += f"<div style='text-align:left;background:#f0f2f6;padding:10px;border-radius:15px;margin:5px;max-width:80%;'>{content}<span style='font-size:10px;color:gray;'><br>{time}</span></div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# --- Chat input ---
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    submitted = st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})

    approaches_str = "\n".join(gsk_approaches)
    flow_str = " → ".join(sales_call_flow)
    prompt = f"""
Language: {language}
User input: {user_input}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Brand: {brand}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Approved Sales Approaches:
{approaches_str}
Sales Call Flow Steps:
{flow_str}
APACT (Acknowledge → Probing → Answer → Confirm → Transition).
Response Length: {response_length}
Response Tone: {response_tone}
PDF Summary (if available): {pdf_summary}
"""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role": "system", "content": f"You are a helpful sales assistant chatbot that responds in {language}."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    ai_output = response.choices[0].message.content
    st.session_state.chat_history.append({"role": "ai", "content": ai_output, "time": datetime.now().strftime("%H:%M")})
    display_chat()

# --- Clear chat button (bottom-left of chat screen) ---
st.markdown("""
<style>
.clear-btn {
    position: fixed;
    bottom: 20px;
    left: 20px;
    z-index: 1000;
}
</style>
""", unsafe_allow_html=True)
if st.button("🗑️ Clear Chat", key="clear_chat", help="Clear conversation history"):
    st.session_state.chat_history = []
    st.experimental_rerun()

# --- Word download ---
if DOCX_AVAILABLE and st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"] == "ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1])
        buf = BytesIO()
        doc.save(buf)
        st.download_button("📥 Download as Word (.docx)", buf.getvalue(), file_name="AI_Response.docx")

# --- Brand leaflet ---
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
