import streamlit as st 
from PIL import Image
from io import BytesIO, BytesIO as io_bytes
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import requests
from groq import Groq
import os

# --- API Key ---
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

# --- README file display ---
if os.path.exists("README.md"):
    with open("README.md", "r", encoding="utf-8") as f:
        readme_text = f.read()
    st.markdown(f"<div style='background:#fff3e0;padding:15px;border-radius:10px'>{readme_text}</div>", unsafe_allow_html=True)

# --- References ---
REFERENCES = """
1. Clinical Overview about Shingles. CDC. https://www.cdc.gov/shingles/hcp/clinical-overview.html (Accessed: 04 Feb 2024).  
2. Harpaz R, et al. MMWR Recomm Rep 2008;57:1-30.  
3. Kawai K, et al. BMJ Open. 2014;4(6):e004833.  
4. Pinchinat S, et al. BMC Infect Dis. 2013;13:170.  
5. Li Y, et al. PLoS One. 2016;11(4):e0152660.  
6. SHINGRIX Egyptian Drug Authority Approved leaflet, approval date 11/09/2023.  
"""

# --- CSS styling ---
st.markdown("""
<style>
.user-bubble {background:#dcf8c6;padding:10px;border-radius:15px;margin:5px;max-width:70%;float:right;clear:both;}
.ai-bubble {background:#f1f0f0;padding:10px;border-radius:15px;margin:5px;max-width:70%;float:left;clear:both;}
h1,h2,h3,h4,h5,h6 {color:orange !important;font-weight:bold;}
</style>
""", unsafe_allow_html=True)

st.markdown("💊 **AI Sales Call Assistant**", unsafe_allow_html=True)

# --- Session state ---
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

# --- Sidebar filters ---
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

# --- Brand images ---
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

# --- Fetch CDC Shingrix content ---
def fetch_shingrix_content():
    url = "https://www.cdc.gov/shingles/hcp/clinical-overview"
    text_summary, images = "", []
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.content, "html.parser")
        text_summary = "\n".join([p.get_text() for p in soup.find_all("p")][:10])
        for img_tag in soup.find_all("img"):
            img_url = img_tag.get("src")
            if img_url:
                img_url = urljoin(url, img_url)  # make full URL
                images.append(img_url)
    except Exception as e:
        text_summary = f"Could not fetch content: {e}"
    return text_summary, images

cdc_text, cdc_images = ("", [])
if brand=="Shingrix":
    cdc_text, cdc_images = fetch_shingrix_content()

# --- Display chat ---
st.subheader("💬 AI Sales Response")
for msg in st.session_state["chat_history"]:
    if msg["role"] == "user":
        st.markdown(f'<div class="user-bubble">👤 {msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="ai-bubble">🤖 {msg["content"]}</div>', unsafe_allow_html=True)

        # --- Dynamically show all CDC images for Shingrix ---
        if brand == "Shingrix" and cdc_images:
            with st.container():
                st.markdown("### 📊 Visuals from CDC")
                for idx, img_url in enumerate(cdc_images):
                    try:
                        st.image(img_url, caption=f"Figure {idx+1}", use_container_width=True)
                    except:
                        st.warning(f"Could not load image: {img_url}")

        with st.expander("📚 References"):
            st.markdown(REFERENCES)

# --- Chat input ---
cols = st.columns([10,1,1])
user_input = cols[0].text_input("Type your message...", key="chat_input", label_visibility="collapsed")
send_clicked = cols[1].button("⏩")
clear_clicked = cols[2].button("🗑️ Clear Chat")

# --- Clear chat ---
if clear_clicked:
    st.session_state["chat_history"] = []
    st.experimental_rerun = None
    st.experimental_rerun = False

# --- Send AI message ---
if send_clicked and user_input.strip():
    st.session_state["chat_history"].append({"role":"user","content":user_input,"time":datetime.now().strftime("%H:%M")})

    prompt = f"""
Language: English
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
Always align your response with the following references:
{REFERENCES}
"""

    try:
        response = client.chat.completions.create(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            messages=[
                {"role":"system","content":"You are a helpful sales assistant chatbot."},
                {"role":"user","content":prompt}
            ],
            temperature=0.7
        )
        ai_output = response.choices[0].message.content.strip()
        st.session_state["chat_history"].append({"role":"assistant","content":ai_output,"time":datetime.now().strftime("%H:%M")})
    except Exception as e:
        st.error(f"⚠️ Error generating response: {e}")

# --- Word download ---
if DOCX_AVAILABLE and st.session_state["chat_history"]:
    latest_ai = [msg["content"] for msg in st.session_state["chat_history"] if msg["role"]=="assistant"]
    if latest_ai:
        doc = Document()
        doc.add_heading("AI Sales Call Response", 0)
        doc.add_paragraph(latest_ai[-1] + "\n\nReferences:\n" + REFERENCES.replace("\n","\n"))
        word_buffer = io_bytes()
        doc.save(word_buffer)
        st.download_button("📥 Download as Word (.docx)", word_buffer.getvalue(), file_name="AI_Response.docx")
