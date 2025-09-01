import os
import streamlit as st
from groq import Groq
from datetime import datetime
from PIL import Image
import fitz  # PyMuPDF for PDF extraction

# --- Configuration ---
PDF_PATH = "SHINGRIX - 2025 EGYPT eDetail-aid2.pdf"
VISUALS_FOLDER = "visuals-shingrix"

# --- Load Groq API Key securely ---
api_key = os.environ.get("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")
if not api_key:
    st.error("❌ GROQ_API_KEY not found. Please set it as an environment variable.")
    st.stop()
else:
    client = Groq(api_key=api_key)

# --- App Header ---
st.image("gsk_logo.png", width=200)
st.markdown(
    "<h2 style='color: orange; font-weight: bold;'>💊 AI Sales Call Assistant - SHINGRIX</h2>",
    unsafe_allow_html=True,
)
st.write("Helping reps tailor discussions with HCPs using approved references + visuals.")

# --- References Section ---
st.markdown("### 📚 References")
st.markdown(
"""
- SHINGRIX Egyptian Drug Authority Approved Prescribing Information Approval Date 11-9-2023. Version number: GDS07/IPI02.  
- CDC. Shingrix Recommendations. [CDC Link](https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html). Last Reviewed: July 19, 2024.  
- Strezova A, Diez-Domingo J, Shawafi Kamal, et al. *Long-term Protection Against Herpes Zoster (HZ) by the Adjuvanted Recombinant Zoster Vaccine (RZV)*. Open Forum Infect Dis. 2022.  
- CDC. Clinical Overview of Shingles (Herpes Zoster). [CDC Link](https://www.cdc.gov/shingles/hcp/clinical-overview/index.html). Last updated: June 2024.  
"""
)

# --- Extract Pages from PDF ---
def extract_pdf_images(pdf_path):
    images = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            pix = doc[page_num].get_pixmap(matrix=fitz.Matrix(2, 2))  # Higher resolution
            img_path = f"page_{page_num+1}.png"
            pix.save(img_path)
            images.append(img_path)
    except Exception as e:
        st.warning(f"⚠️ PDF extraction failed: {e}")
    return images

# --- Load Visuals from Folder ---
def load_visuals(folder_path):
    visuals = []
    if os.path.exists(folder_path):
        for file in sorted(os.listdir(folder_path)):
            if file.lower().endswith((".png", ".jpg", ".jpeg")):
                visuals.append(os.path.join(folder_path, file))
    return visuals

# --- Sidebar for Input ---
st.sidebar.header("📋 Sales Call Input")
hcp_segment = st.sidebar.selectbox("Select HCP Segment", ["High Potential", "Medium Potential", "Low Potential"])
barrier = st.sidebar.text_input("Main HCP Objection/Barrier")
custom_prompt = st.sidebar.text_area("Custom Question for AI")

if st.sidebar.button("Generate AI Response"):
    with st.spinner("🤖 Generating response..."):
        messages = [
            {"role": "system", "content": "You are a medical sales assistant. Always provide evidence-based, referenced responses."},
            {"role": "user", "content": f"HCP Segment: {hcp_segment}\nBarrier: {barrier}\nQuestion: {custom_prompt}"}
        ]
        try:
            response = client.chat.completions.create(
                model="llama3-70b-8192",
                messages=messages,
                max_tokens=600,
            )
            ai_output = response.choices[0].message.content
            st.markdown("### 🧾 Suggested Response")
            st.write(ai_output)
        except Exception as e:
            st.error(f"❌ AI generation failed: {e}")

    # --- Suggest Visuals ---
    st.markdown("### 🖼 Suggested Visuals for HCP Detailing")
    pdf_images = extract_pdf_images(PDF_PATH)
    folder_images = load_visuals(VISUALS_FOLDER)

    if not pdf_images and not folder_images:
        st.warning("⚠️ No visuals available. Please check PDF or visuals folder.")
    else:
        all_visuals = pdf_images + folder_images
        for img_path in all_visuals:
            st.image(Image.open(img_path), caption=os.path.basename(img_path), use_container_width=True)

# --- Disclaimer ---
st.markdown("---")
st.markdown(
    "<p style='font-size:12px; color:gray;'>⚠️ This AI tool supports reps in preparing discussions. "
    "Always refer to approved GSK references and PI before engaging with HCPs.</p>",
    unsafe_allow_html=True,
)
