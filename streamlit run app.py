
---

### 4️⃣ Updated `app.py`
I condensed it for clarity while keeping **Shingrix CDC URL fetching + images + Groq integration**:

```python
import streamlit as st
from PIL import Image
import requests
from io import BytesIO, BytesIO as io_bytes
from datetime import datetime
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import groq
from groq import Groq

# Optional Word export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    st.warning("⚠️ python-docx not installed. Word download unavailable.")

# Groq API
GROQ_API_KEY = os.getenv("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")
if not GROQ_API_KEY:
    st.error("❌ Groq API key not found. Add it to .env or environment variables.")
else:
    client = Groq(api_key=GROQ_API_KEY)

# Session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Language selection
language = st.radio("Select Language / اختر اللغة", ["English", "العربية"])

# Logo
logo_local_path = "images/gsk_logo.png"
logo_fallback_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"
col1, col2 = st.columns([1,5])
with col1:
    try:
        st.image(Image.open(logo_local_path), width=120)
    except:
        st.image(logo_fallback_url, width=120)
with col2:
    st.title("🧠 AI Sales Call Assistant")

# Brand data
gsk_brands = {
    "Shingrix": "https://www.cdc.gov/shingles/hcp/clinical-overview",
    "Trelegy": "https://example.com/trelegy-leaflet",
    "Zejula": "https://example.com/zejula-leaflet",
}
gsk_brands_images = {
    "Trelegy": "https://www.example.com/trelegy.png",
    "Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Zejula": "https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png",
}

# Filters
race_segments = ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"]
doctor_barriers = ["HCP does not consider HZ as risk", "No time to discuss preventive measures", "Cost considerations", "Not convinced HZ Vx effective", "Accessibility issues"]
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]
personas = ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"]
gsk_approaches = ["Use data-driven evidence", "Focus on patient outcomes", "Leverage storytelling techniques"]
sales_call_flow = ["Prepare", "Engage", "Create Opportunities", "Influence", "Drive Impact", "Post Call Analysis"]

# Sidebar
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand", list(gsk_brands.keys()))
segment = st.sidebar.selectbox("Select RACE Segment", race_segments)
barrier = st.sidebar.multiselect("Select Doctor Barrier", doctor_barriers, default=[])
objective = st.sidebar.selectbox("Select Objective", objectives)
specialty = st.sidebar.selectbox("Select Doctor Specialty", specialties)
persona = st.sidebar.selectbox("Select HCP Persona", personas)
response_length = st.sidebar.selectbox("Response Length", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])

# Brand image
image_path = gsk_brands_images.get(brand)
try:
    if image_path.startswith("http"):
        img = Image.open(BytesIO(requests.get(image_path).content))
    else:
        img = Image.open(image_path)
    st.image(img, width=200)
except:
    st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)

# Clear chat
if st.button("🗑️ Clear Chat"):
    st.session_state.chat_history = []

# Chat display
chat_placeholder = st.empty()
def display_chat():
    html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time","")
        content = msg["content"].replace("\n","<br>")
        if msg["role"]=="user":
            html += f"<div style='text-align:right;background:#dcf8c6;padding:10px;border-radius:15px;margin:5px;max-width:80%'>{content}<br><small>{time}</small></div>"
        else:
            html += f"<div style='text-align:left;background:#f0f2f6;padding:10px;border-radius:15px;margin:5px;max-width:80%'>{content}<br><small>{time}</small></div>"
    chat_placeholder.markdown(html, unsafe_allow_html=True)
display_chat()

# Fetch CDC URL content & images
def fetch_url_content_and_images(url):
    text_summary = ""
    images = []
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        paragraphs = [p.get_text() for p in soup.find_all("p")]
        text_summary = "\n".join(paragraphs[:10])
        for img_tag in soup.find_all("img"):
            img_url = img_tag.get("src")
            if img_url:
                if not img_url.startswith("http"):
                    img_url = urljoin(url,img_url)
                images.append(img_url)
    except Exception as e:
        text_summary = f"Could not fetch content: {e}"
    return text_summary, images

url_summary = ""
url_images = []
if brand=="Shingrix":
    url_summary, url_images = fetch_url_content_and_images(gsk_brands[brand])
    st.subheader("📝 Shingrix CDC Summary")
    st.text_area("CDC Content", url_summary, height=200)
    st.subheader("📊 Shingrix Figures")
    for i, img_url in enumerate(url_images[:10]):
        try:
            img = Image.open(BytesIO(requests.get(img_url).content))
            st.image(img, caption=f"Figure {i+1}")
        except:
            continue

# Chat input
with st.form("chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...")
    submitted = st.form_submit_button("➤")

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})
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
Reference URL content (if Shingrix):
{text_summary}
Number of extracted figures: {len(url_images)}
Use APACT technique.
Response Length: {response_length}
Response Tone: {response_tone}
Provide actionable suggestions tailored to this persona.
"""
    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[{"role":"system","content":f"You are a helpful sales assistant chatbot that responds in {language}."},{"role":"user","content":prompt}],
        temperature=0.7
    )
    ai_output = response.choices[0].message.content
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M")})
    display_chat()
