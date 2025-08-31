
---

### **5️⃣ `app.py`** (updated version)

```python
import streamlit as st
from PIL import Image
import requests
from io import BytesIO, BytesIO as io_bytes
from datetime import datetime
import os
from dotenv import load_dotenv

# PDF handling
from PyPDF2 import PdfReader
from pdf2image import convert_from_path

# Groq
import groq
from groq import Groq

# Word export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# Load Groq API key from .env
load_dotenv()
GROQ_API_KEY = os.getenv("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")
client = Groq(api_key=GROQ_API_KEY)

# Session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Language selection
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])

# GSK Logo
logo_local_path = "images/gsk_logo.png"
logo_fallback_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
col1, col2 = st.columns([1,5])
with col1:
    try:
        logo_img = Image.open(logo_local_path)
        st.image(logo_img, width=120)
    except:
        st.image(logo_fallback_url, width=120)
with col2:
    st.title("🧠 AI Sales Call Assistant")

# Brands & Images
gsk_brands = {"Shingrix": "Shingrix.pdf"}
gsk_brands_images = {"Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png"}

# Sidebar filters
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))

# Display brand image
image_path = gsk_brands_images.get(brand)
try:
    if image_path.startswith("http"):
        response = requests.get(image_path)
        img = Image.open(BytesIO(response.content))
    else:
        img = Image.open(image_path)
    st.image(img, width=200)
except:
    st.warning(f"⚠️ Could not load image for {brand}. Using placeholder.")
    st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)

# --- PDF extraction ---
pdf_path = gsk_brands[brand]
st.subheader(f"📄 {brand} PDF Content & Visuals")
try:
    reader = PdfReader(pdf_path)
    text_content = ""
    for page in reader.pages[:3]:  # Extract first 3 pages text
        text_content += page.extract_text() + "\n"
    st.text_area("PDF Text Preview", text_content, height=200)
    
    # Extract figures as images
    pages = convert_from_path(pdf_path, dpi=150)
    st.subheader("Medical Figures / Charts from PDF")
    for i, page_img in enumerate(pages[:3]):  # Show first 3 figures/pages
        st.image(page_img, caption=f"Page {i+1}", use_column_width=True)
except Exception as e:
    st.error(f"⚠️ Failed to extract PDF content: {e}")

# --- Chatbot Section ---
st.subheader("💬 Chatbot Interface")
chat_placeholder = st.empty()

def display_chat():
    chat_html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time", "")
        content = msg["content"].replace('\n', '<br>')
        if msg["role"] == "user":
            chat_html += f"<div style='text-align:right; background:#dcf8c6; padding:10px; border-radius:15px 15px 0px 15px; margin:5px; display:inline-block; max-width:80%;'>{content}<br><small>{time}</small></div>"
        else:
            chat_html += f"<div style='text-align:left; background:#f0f2f6; padding:10px; border-radius:15px 15px 15px 0px; margin:5px; display:inline-block; max-width:80%;'>{content}<br><small>{time}</small></div>"
    chat_placeholder.markdown(chat_html, unsafe_allow_html=True)

display_chat()

# Chat input
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="user_input_box")
    submitted = st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "user", "content": user_input, "time": datetime.now().strftime("%H:%M")})
    
    # Call Groq API
    prompt = f"Language: {language}\nUser input: {user_input}\nBrand: {brand}\nPDF summary: {text_content[:500]}..."  # include first 500 chars
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role": "system", "content": f"You are a helpful sales assistant chatbot."},
                  {"role": "user", "content": prompt}],
        temperature=0.7
    )
    ai_output = response.choices[0].message.content
    st.session_state.chat_history.append({"role": "ai", "content": ai_output, "time": datetime.now().strftime("%H:%M")})
    display_chat()

# Word download
if DOCX_AVAILABLE and st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"] == "ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1])
        word_buffer = io_bytes()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")
