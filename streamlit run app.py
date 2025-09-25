import streamlit as st
from PIL import Image
import requests
from io import BytesIO
import base64
from datetime import datetime
from groq import Groq

# --- Optional dependency for Word download ---
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# --- Initialize Groq client ---
if "GROQ_API_KEY" not in st.secrets:
    st.error("⚠️ Please add your GROQ_API_KEY in Streamlit secrets.")
else:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# --- Background image ---
bg_url = "https://img.freepik.com/premium-photo/black-woman-smiling-using-phone-with-yellow-background_176841-18605.jpg"
st.markdown(
    f"""
    <style>
    .stApp {{
        background: url("{bg_url}") no-repeat center center fixed;
        background-size: cover;
        color: white;
    }}
    .title-box {{
        background: rgba(0, 0, 0, 0.5);
        padding: 15px;
        border-radius: 12px;
        margin-bottom: 15px;
    }}
    .disclaimer {{
        font-size: 12px;
        color: black;
        background: rgba(255,255,255,0.7);
        padding: 6px;
        border-radius: 6px;
    }}
    .chat-bubble-user {{
        text-align: right;
        background: rgba(220,248,198,0.85);
        padding: 10px;
        border-radius: 15px 15px 0px 15px;
        margin: 5px;
        display: inline-block;
        max-width: 80%;
        color: black;
    }}
    .chat-bubble-ai {{
        text-align: left;
        background: rgba(240,242,246,0.7);
        padding: 10px;
        border-radius: 15px 15px 15px 0px;
        margin: 5px;
        display: inline-block;
        max-width: 80%;
        color: black;
    }}
    .highlight {{
        font-weight: bold;
        background-color: yellow;
        color: black;
        padding: 2px 4px;
        border-radius: 4px;
    }}
    .send-btn {{
        background-color: #FF6600;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        padding: 8px 16px;
        border: none;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pdf_summary" not in st.session_state:
    st.session_state.pdf_summary = None

# --- Language ---
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])

# --- Header ---
logo_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
col1, col2 = st.columns([1, 5])
with col1:
    st.image(logo_url, width=120)
with col2:
    st.markdown(
        "<div class='title-box'><h2>💡 AI Sales Call Assistant</h2>"
        "<p>Powered by AI to equip sales reps for smarter HCP conversations</p></div>",
        unsafe_allow_html=True,
    )
    st.markdown("<p class='disclaimer'>⚠️ Disclaimer: For training and educational purposes only.</p>", unsafe_allow_html=True)

# --- Filters ---
race_segments = [
    "R – Reach: Did not start prescribing yet, doesn't see responsibility.",
    "A – Acquisition: Prescribes if patient asks, needs more conviction.",
    "C – Conversion: Initiates discussion with some patients.",
    "E – Engagement: Proactively prescribes across patient profiles."
]
doctor_barriers = [
    "HCP does not consider HZ as risk",
    "No time to discuss prevention",
    "Cost considerations",
    "Not convinced HZ Vx effective",
    "Accessibility issues"
]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]

st.sidebar.header("Filters & Options")
segment = st.sidebar.selectbox("Select RACE Segment", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barrier", doctor_barriers, default=[])
objective = st.sidebar.selectbox("Select Objective", objectives)
specialty = st.sidebar.selectbox("Select Doctor Specialty", specialties)
persona = st.sidebar.selectbox("Select HCP Persona", personas)
response_tone = st.sidebar.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])

# --- PDF Upload & Summarize (in main UI) ---
st.subheader("📄 Upload PDF for Summarization")
uploaded_file = st.file_uploader("Upload a PDF file", type="pdf")
if uploaded_file is not None:
    import pdfplumber
    with pdfplumber.open(uploaded_file) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)

    preview = text[:1500] + ("..." if len(text) > 1500 else "")
    with st.expander("📖 PDF Preview (click to expand)"):
        st.text(preview)

    # Generate summary
    if st.button("Summarize PDF"):
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You summarize PDFs for pharma sales training."},
                    {"role": "user", "content": f"Summarize this PDF:\n{text[:4000]}"}
                ]
            )
            st.session_state.pdf_summary = response.choices[0].message.content
            st.success("✅ PDF summary generated.")
        except Exception as e:
            st.error(f"Error summarizing PDF: {e}")

if st.session_state.pdf_summary:
    st.markdown("### 📌 PDF Summary")
    st.write(st.session_state.pdf_summary)

# --- Chat history ---
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()

def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time", "")
        content = msg["content"].replace("\n", "<br>")
        for step in ["Acknowledge", "Probing", "Action", "Confirm", "Transition"]:
            content = content.replace(step, f"<span class='highlight'>{step}</span>")
        if msg["role"] == "user":
            chat_html += f"<div class='chat-bubble-user'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>"
        else:
            chat_html += f"<div class='chat-bubble-ai'>{content}<br><span style='font-size:10px; color:gray;'>{time}</span></div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# --- Chat input ---
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    submitted = st.form_submit_button("➤", help="Send", use_container_width=True)

if submitted and user_input.strip():
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_input,
        "time": datetime.now().strftime("%H:%M")
    })

    pdf_context = f"\nRelevant PDF summary:\n{st.session_state.pdf_summary}" if st.session_state.pdf_summary else ""

    prompt = f"""
Language: {language}
User: {user_input}
Segment: {segment}
Barriers: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Specialty: {specialty}
Persona: {persona}
Use APACT steps (Acknowledge → Probing → Action → Confirm → Transition).
Tone: {response_tone}
{pdf_context}
"""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": f"You are a helpful AI sales assistant in {language}."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.6
        )
        ai_output = response.choices[0].message.content
    except Exception as e:
        ai_output = f"⚠️ Error from Groq API: {e}"

    st.session_state.chat_history.append({
        "role": "ai",
        "content": ai_output,
        "time": datetime.now().strftime("%H:%M")
    })
    display_chat()

# --- Download Word ---
if DOCX_AVAILABLE and st.session_state.chat_history:
    from io import BytesIO
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"] == "ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1])
        buf = BytesIO()
        doc.save(buf)
        st.download_button("📥 Download AI Response (.docx)", buf.getvalue(), "AI_Response.docx")
