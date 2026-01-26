import streamlit as st  
from PIL import Image
import requests
from io import BytesIO
import groq
from groq import Groq

# --- Initialize Groq client ---
client = Groq(api_key="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")

# --- Initialize session state ---
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- Language selector ---
language = st.radio("Select Language / اختر اللغة", options=["English", "العربية"])

# --- GSK logo (robust loading) ---
logo_local_path = "images/gsk_logo.png"  # Local file path
logo_fallback_url = "https://www.tungsten-network.com/wp-content/uploads/2020/05/GSK_Logo_Full_Colour_RGB.png"

col1, col2 = st.columns([1, 5])
with col1:
    try:
        logo_img = Image.open(logo_local_path)
        st.image(logo_img, width=120)
    except Exception:
        st.image(logo_fallback_url, width=120)
with col2:
    st.title("🧠 AI Sales Call Assistant")

# --- GSK brand mappings ---
gsk_brands = {
    "Augmentin": "https://example.com/augmentin-leaflet",
    "Shingrix": "https://example.com/shingrix-leaflet",
    "Seretide": "https://example.com/seretide-leaflet",
}

# --- Brand logos (mix of local and URL) ---
gsk_brands_images = {
    "Augmentin": "https://www.bloompharmacy.com/cdn/shop/products/augmentin-1-gm-14-tablets-145727_600x600_crop_center.jpg?v=1687635056",
    "Shingrix": "https://www.oma-apteekki.fi/WebRoot/NA/Shops/na/67D6/48DA/D0B0/D959/ECAF/0A3C/0E02/D573/3ad67c4e-e1fb-4476-a8a0-873423d8db42_3Dimage.png",
    "Seretide": "https://cdn.salla.sa/QeZox/eyy7B0bg8D7a0Wwcov6UshWFc04R6H8qIgbfFq8u.png",
}

# --- RACE Segmentation ---
race_segments = [
    "R – Reach: Did not start to prescribe yet and Don't believe that vaccination is his responsibility.",
    "A – Acquisition: Prescribe to patient who initiate discussion about the vaccine but Convinced about Shingrix data.",
    "C – Conversion: Proactively initiate discussion with specific patient profile but For other patient profiles he is not prescribing yet.",
    "E – Engagement: Proactively prescribe to different patient profiles"
]

# --- Doctor Barriers ---
doctor_barriers = [
    "1 - HCP does not consider HZ as risk for the selected patient profile",
    "2 - HCP thinks there is no time to discuss preventive measures with the patients",
    "3 - HCP thinks about cost considerations",
    "4 - HCP is not convinced that HZ Vx is effective in reducing the burden",
    "5 - Accessibility (POVs)"
]

# --- Other filters ---
objectives = ["Awareness", "Adoption", "Retention"]
specialties = ["General Practitioner", "Cardiologist", "Dermatologist", "Endocrinologist", "Pulmonologist"]

# --- New HCP Persona filter (Shingrix & Adult Vaccines) ---
personas = [
    "Uncommitted Vaccinator – Not engaged, poor knowledge, least likely to prescribe vaccines (26%)",
    "Reluctant Efficiency – Do not see vaccinating 50+ as part of role, least likely to believe in impact (12%)",
    "Patient Influenced – Aware of benefits but prescribes only if patient requests (26%)",
    "Committed Vaccinator – Very positive, motivated, prioritizes vaccination & sets example (36%)"
]

# --- Approved sales approaches ---
gsk_approaches = [
    "Use data-driven evidence",
    "Focus on patient outcomes",
    "Leverage storytelling techniques",
]

# --- Brand selection ---
brand = st.selectbox("Select Brand / اختر العلامة التجارية", options=list(gsk_brands.keys()))

# --- Load brand image safely ---
image_path = gsk_brands_images.get(brand)
try:
    if image_path.startswith("http"):
        response = requests.get(image_path)
        img = Image.open(BytesIO(response.content))
    else:
        img = Image.open(image_path)
    st.image(img, width=200)
except Exception:
    st.warning(f"⚠️ Could not load image for {brand}. Using placeholder.")
    st.image("https://via.placeholder.com/200x100.png?text=No+Image", width=200)

# --- Inputs ---
segment = st.selectbox("Select RACE Segment / اختر شريحة RACE", race_segments)
barrier = st.selectbox("Select Doctor Barrier / اختر حاجز الطبيب", doctor_barriers)
objective = st.selectbox("Select Objective / اختر الهدف", objectives)
specialty = st.selectbox("Select Doctor Specialty / اختر تخصص الطبيب", specialties)
persona = st.selectbox("Select HCP Persona / اختر شخصية الطبيب", personas)  # <-- New

# --- AI Response Customization ---
response_length_options = ["Short", "Medium", "Long"]
response_tone_options = ["Formal", "Casual", "Friendly", "Persuasive"]

response_length = st.selectbox("Select Response Length / اختر طول الرد", response_length_options)
response_tone = st.selectbox("Select Response Tone / اختر نبرة الرد", response_tone_options)

# --- Clear chat button ---
if st.button("🗑️ Clear Chat / مسح المحادثة"):
    st.session_state.chat_history = []

# --- Chat container ---
chat_container = st.container()

# --- User message input ---
placeholder_text = "Type your message..." if language == "English" else "اكتب رسالتك..."
user_input = st.text_area(placeholder_text, key="user_input", height=80)

if st.button("🚀 Send / أرسل") and user_input.strip():
    with st.spinner("Generating AI response... / جارٍ إنشاء الرد"):
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # Prepare dynamic GSK approaches context
        approaches_str = "\n".join(gsk_approaches)

        # Build AI prompt with Persona, Doctor Barrier, Tone, and Length
        prompt = f"""
Language: {language}
You are an expert GSK sales assistant. 
User input: {user_input}
RACE Segment: {segment}
Doctor Barrier: {barrier}
Objective: {objective}
Brand: {brand}
Doctor Specialty: {specialty}
HCP Persona: {persona}
Approved GSK Sales Approaches:
{approaches_str}
Response Length: {response_length}
Response Tone: {response_tone}
Provide actionable suggestions tailored to this persona, following the selected length and tone, in a friendly and professional manner.
"""

        # Call Groq API
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": f"You are a helpful sales assistant chatbot that responds in {language}."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )

        ai_output = response.choices[0].message.content
        st.session_state.chat_history.append({"role": "ai", "content": ai_output})

# --- Display chat history ---
with chat_container:
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(
                f"""
<div style="
    text-align:right;
    margin:10px 0;
    padding:10px;
    background-color:#d1e7dd;
    border-radius:12px;
    display:inline-block;
    max-width:80%;
    font-family:sans-serif;
    white-space:pre-wrap;
">
<strong>You:</strong><br>{msg['content']}
</div>
""",
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"""
<div style="
    text-align:left;
    margin:10px 0;
    padding:15px;
    background-color:#f0f2f6;
    border-radius:12px;
    display:inline-block;
    max-width:80%;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    font-family:sans-serif;
    white-space:pre-wrap;
">
<strong>AI:</strong><br>{msg['content']}
</div>
""",
                unsafe_allow_html=True
            )

# --- Leaflet link below chat ---
st.markdown(f"[Brand Leaflet - {brand}]({gsk_brands[brand]})")
