import streamlit as st
from PIL import Image
from io import BytesIO, BytesIO as io_bytes
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import requests
from groq import Groq

# --- API Key (set it directly here) ---
# ⚠️ Replace with your actual key
GROQ_API_KEY = "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"

if not GROQ_API_KEY:
    st.error("❌ Groq API key not set. Please add it in the script.")
else:
    client = Groq(api_key=GROQ_API_KEY)

# Optional Word export
try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

# Session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Language selection
language = st.radio("Select Language / اختر اللغة", ["English", "العربية"])

# Sidebar filters
st.sidebar.header("Filters & Options")
brand = st.sidebar.selectbox("Select Brand", ["Shingrix", "Trelegy", "Zejula"])
segment = st.sidebar.selectbox("Select RACE Segment", [
    "R – Reach: Did not start to prescribe yet",
    "A – Acquisition: Prescribe to patients who initiate discussion",
    "C – Conversion: Proactively initiate discussion with specific patients",
    "E – Engagement: Proactively prescribe to different patient profiles"
])
barrier = st.sidebar.multiselect("Select Doctor Barrier", [
    "HCP does not consider HZ as risk",
    "No time to discuss preventive measures",
    "Cost considerations",
    "Not convinced HZ Vx effective",
    "Accessibility issues"
])
objective = st.sidebar.selectbox("Select Objective", ["Awareness", "Adoption", "Retention"])
specialty = st.sidebar.selectbox("Select Doctor Specialty", ["GP", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"])
persona = st.sidebar.selectbox("Select HCP Persona", [
    "Uncommitted Vaccinator",
    "Reluctant Efficiency",
    "Patient Influenced",
    "Committed Vaccinator"
])
response_length = st.sidebar.selectbox("Response Length", ["Short", "Medium", "Long"])
response_tone = st.sidebar.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])

# Brand images
gsk_brands_images = {
    "Trelegy": "https://www.example.com/trelegy.png",
    "Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Zejula": "https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png",
}

image_path = gsk_brands_images.get(brand)
try:
    if image_path.startswith("http"):
        img = Image.open(BytesIO(requests.get(image_path).content))
    else:
        img = Image.open(image_path)
    st.image(img, width=200)
except:
    st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)

# References list
references = """
<b>References:</b><br>
1. Clinical Overview about Shingles. Available at: <a href='https://www.cdc.gov/shingles/hcp/clinical-overview.html' target='_blank'>CDC Website</a> (Accessed: 04 February 2024).<br>
2. Harpaz R, et al. MMWR Recomm Rep 2008;57:1-30.<br>
3. Kawai K, Gebremeskel BG, Acosta CJ. BMJ Open. 2014;4(6):e004833.<br>
4. Pinchinat S, et al. BMC Infect Dis. 2013;13:170.<br>
5. Li Y, et al. PLoS One. 2016;11(4):e0152660.<br>
6. SHINGRIX Egyptian Drug Authority Approved leaflet, approval date 11/09/2023.<br>
"""

# Chat display
st.subheader("💬 AI Sales Response")

def display_chat():
    html = ""
    for msg in st.session_state.chat_history:
        time = msg.get("time","")
        content = msg["content"].replace("\n","<br>")
        if msg["role"]=="user":
            html += f"<div style='text-align:right;background:#dcf8c6;padding:10px;border-radius:15px;margin:5px;max-width:80%'>{content}<br><small>{time}</small></div>"
        else:
            # Append references for AI messages
            content_with_refs = content + "<br><br>" + references
            html += f"<div style='text-align:left;background:#f0f2f6;padding:10px;border-radius:15px;margin:5px;max-width:80%'>{content_with_refs}<br><small>{time}</small></div>"
    st.markdown(html, unsafe_allow_html=True)

display_chat()

# Chat input with inline send button (Telegram/Teams style)
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_input("Type your message...", key="chat_input")
    send_pressed = st.form_submit_button("📨 Send")

# Fetch CDC Shingrix content
def fetch_shingrix_content():
    url = "https://www.cdc.gov/shingles/hcp/clinical-overview"
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

cdc_text, cdc_images = ("", [])
if brand=="Shingrix":
    cdc_text, cdc_images = fetch_shingrix_content()

# Prepare and send AI prompt
if send_pressed and user_input.strip() and GROQ_API_KEY:
    st.session_state.chat_history.append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})

    prompt = f"""
Language: {language}
User input: {user_input}
RACE Segment: {segment}
Doctor Barrier: {', '.join(barrier) if barrier else 'None'}
Objective: {objective}
Brand: {brand}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Reference content from Shingrix CDC: {cdc_text}
Number of extracted figures: {len(cdc_images)}
Use APACT technique.
Response Length: {response_length}
Response Tone: {response_tone}
Provide actionable suggestions and include insights from CDC content and figures in your response.

Always align your response with the following references:
{references}
"""

    response = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role":"system","content":f"You are a helpful sales assistant chatbot that responds in {language}."},
            {"role":"user","content":prompt}
        ],
        temperature=0.7
    )

    ai_output = response.choices[0].message.content
    st.session_state.chat_history.append({"role":"ai","content":ai_output,"time":datetime.now().strftime("%H:%M")})

    display_chat()

# Word download
if DOCX_AVAILABLE and st.session_state.chat_history:
    latest_ai = [msg["content"] for msg in st.session_state.chat_history if msg["role"]=="ai"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1] + "\n\nReferences:\n" + references.replace("<br>","\n").replace("<b>","").replace("</b>",""))
        word_buffer = io_bytes()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")
