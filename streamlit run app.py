import os
import streamlit as st
from PIL import Image
import requests
from io import BytesIO
from datetime import datetime

# Optional dependencies
try:
    import fitz  # PyMuPDF for PDF extraction
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from pptx import Presentation  # python-pptx
    PPT_AVAILABLE = True
except ImportError:
    PPT_AVAILABLE = False

# AI Client (Groq or any LLM provider)
from groq import Groq
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# --- App Header ---
st.set_page_config(page_title="GSK AI Detailing Assistant", layout="wide")
st.image("gsk_logo.png", width=120)
st.markdown(
    "<h2 style='color:orange; font-weight:bold;'>GSK AI Sales Call Assistant</h2>",
    unsafe_allow_html=True
)

st.info("⚠️ Disclaimer: This tool is intended to support GSK representatives. Always refer to the approved PI and references.")

# --- References ---
REFERENCES = [
    "SHINGRIX Egyptian Drug Authority Approved Prescribing Information Approval Date 11-9-2023. Version number: GDS07/IPI02.",
    "Centers for Disease Control and Prevention. Shingrix Recommendations. Available at: https://www.cdc.gov/shingles/hcp/vaccine-considerations/index.html. Last Reviewed: July 19, 2024.",
    "Strezova A, Diez-Domingo J, Shawafi Kamal, et al. Long-term Protection Against Herpes Zoster (HZ) by the Adjuvanted Recombinant Zoster Vaccine (RZV): Interim Efficacy, Immunogenicity, and Safety Results up to 10 Years. Open Forum Infect Dis. 2022; ofac485. https://doi.org/10.1093/ofid/ofac485.",
    "CDC. Clinical Overview of Shingles (Herpes Zoster). Available at: https://www.cdc.gov/shingles/hcp/clinical-overview/index.html. Last updated: June 2024."
]

# --- PDF/PPT Extraction ---
def extract_from_pdf(pdf_path):
    if not PDF_AVAILABLE:
        return "⚠️ PyMuPDF not installed. PDF extraction disabled."
    text = ""
    images = []
    doc = fitz.open(pdf_path)
    for page in doc:
        text += page.get_text("text")
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_img = doc.extract_image(xref)
            img_bytes = base_img["image"]
            images.append(Image.open(BytesIO(img_bytes)))
    return text, images

def extract_from_ppt(ppt_path):
    if not PPT_AVAILABLE:
        return "⚠️ python-pptx not installed. PPT extraction disabled."
    text = ""
    prs = Presentation(ppt_path)
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text += shape.text + "\n"
    return text

# --- AI Query ---
def ask_ai(question, context=""):
    prompt = f"""
    You are a medical assistant for GSK reps.
    Question: {question}
    Context: {context}
    Always cite references at the end.
    """
    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "system", "content": "Medical assistant"},
                      {"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"⚠️ AI Error: {e}"

# --- Main App ---
st.markdown("### ❓ Ask a Medical/Brand Question")
user_question = st.text_input("Enter your question for the AI:")

if user_question:
    with st.spinner("Generating response..."):
        # Extract from local PI (if available)
        pdf_path = "SHINGRIX - 2025 EGYPT eDetail-aid2.pdf"
        context = ""
        if os.path.exists(pdf_path):
            extracted = extract_from_pdf(pdf_path)
            if isinstance(extracted, tuple):
                context, pdf_images = extracted
        else:
            pdf_images = []

        ai_answer = ask_ai(user_question, context)
        st.markdown("### 💡 AI Response")
        st.write(ai_answer)

        # --- AI Suggested Visuals ---
        st.markdown("### 🎯 AI-Suggested Top 3 Visuals")

        visuals_dir = "visuals/shingrix"
        if os.path.exists(visuals_dir):
            image_files = [f for f in os.listdir(visuals_dir) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
            if image_files:
                ai_prompt = f"""
                The following visuals are available: {', '.join(image_files)}.
                Based on the query: "{user_question}", suggest the 3 most relevant visuals.
                """
                try:
                    ai_response = client.chat.completions.create(
                        model="llama3-70b-8192",
                        messages=[{"role": "system", "content": "You are a medical assistant helping sales reps."},
                                  {"role": "user", "content": ai_prompt}]
                    )
                    suggested_files = ai_response.choices[0].message.content.split(",")[:3]
                    suggested_files = [f.strip() for f in suggested_files if f.strip() in image_files]
                except Exception:
                    suggested_files = image_files[:3]

                if suggested_files:
                    cols = st.columns(len(suggested_files))
                    for idx, image_file in enumerate(suggested_files):
                        img_path = os.path.join(visuals_dir, image_file)
                        img = Image.open(img_path)
                        with cols[idx]:
                            st.image(img, caption=image_file.replace("_", " ").split(".")[0], use_container_width=True)
                else:
                    st.info("ℹ️ No AI suggestions available.")
            else:
                st.info("ℹ️ No visuals found in `visuals/shingrix/` folder.")
        else:
            st.warning("⚠️ The folder `visuals/shingrix/` does not exist.")

        # --- Full Visual Gallery ---
        st.markdown("### 📊 Full Visual Gallery")
        if os.path.exists(visuals_dir) and image_files:
            cols = st.columns(3)
            for idx, image_file in enumerate(image_files):
                img_path = os.path.join(visuals_dir, image_file)
                img = Image.open(img_path)
                with cols[idx % 3]:
                    st.image(img, caption=image_file.replace("_", " ").split(".")[0], use_container_width=True)

# --- References Section ---
st.markdown("### 📚 References")
for ref in REFERENCES:
    st.write(f"- {ref}")
