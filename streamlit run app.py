import streamlit as st
import os
from groq import Groq, NotFoundError, RateLimitError
from PyPDF2 import PdfReader

# ---------------------------- APP CONFIG ----------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide")

# ---------------------------- SESSION STATE INIT ----------------------------
if "messages" not in st.session_state:
    st.session_state["messages"] = []
if "pdf_summary" not in st.session_state:
    st.session_state["pdf_summary"] = ""
if "last_model_used" not in st.session_state:
    st.session_state["last_model_used"] = "None"

# ---------------------------- CONSTANTS ----------------------------
APACT_STEPS = ["Ask", "Probe", "Acknowledge", "Convince", "Transition"]
sales_call_flow = ["Opening", "Exploring Needs", "Detailing", "Handling Objections", "Close"]

# ---------------------------- GROQ CLIENT ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", os.getenv("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"))
client = Groq(api_key=GROQ_API_KEY)

# Define model priority order
MODEL_PRIORITY = [
    "llama-3.3-70b-versatile",
    "mistral-7b-chat",
    "llama-3.1-8b-instant"
]

# ---------------------------- PDF HANDLING ----------------------------
def extract_pdf_text(uploaded_file):
    text = ""
    reader = PdfReader(uploaded_file)
    for page in reader.pages:
        text += page.extract_text() or ""
    return text

# ---------------------------- LIST MODELS ----------------------------
def list_available_models():
    try:
        models = client.models.list()
        st.sidebar.write("✅ Available Groq Models:")
        for m in models.data:
            st.sidebar.write("-", m.id)
    except Exception as e:
        st.sidebar.error(f"Error fetching models: {e}")

with st.sidebar.expander("Groq Models"):
    if st.button("🔍 List Models"):
        list_available_models()
    if "last_model_used" in st.session_state:
        st.sidebar.info(f"🤖 Model in use: `{st.session_state['last_model_used']}`")

# ---------------------------- AI RESPONSE WITH FALLBACK ----------------------------
def generate_ai_response(prompt, brand, segment, objective, barrier, persona, specialty):
    context = f"""
User: {prompt}
Brand: {brand}
RACE Segment: {segment}
Objective: {objective}
Doctor Barrier: {barrier}
Persona: {persona}
Specialty: {specialty}

PDF Summary:
{st.session_state.pdf_summary}

Sales Call Flow: {', '.join(sales_call_flow)}
APACT Steps: {', '.join(APACT_STEPS)}
"""
    for model_name in MODEL_PRIORITY:
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful GSK sales assistant."},
                    {"role": "user", "content": context}
                ],
                temperature=0.65,
            )
            st.session_state["last_model_used"] = model_name
            return response.choices[0].message.content

        except NotFoundError:
            continue
        except RateLimitError:
            continue
        except Exception as e:
            st.error(f"Unexpected error with `{model_name}`: {e}")
            continue

    st.session_state["last_model_used"] = "❌ None (all failed)"
    return "❌ No valid Groq models available at the moment. Please try again later."

# ---------------------------- UI ----------------------------
st.title("💊 AI Sales Call Assistant")

uploaded_file = st.file_uploader("📂 Upload PDF (optional)", type=["pdf"])
if uploaded_file is not None:
    with st.spinner("Extracting text from PDF..."):
        pdf_text = extract_pdf_text(uploaded_file)
        st.session_state.pdf_summary = pdf_text[:3000]  # limit size
    st.success("✅ PDF uploaded and summarized.")

brand = st.text_input("🏷️ Brand")
segment = st.text_input("📊 RACE Segment")
objective = st.text_input("🎯 Objective")
barrier = st.text_input("🚧 Doctor Barrier")
persona = st.text_input("🧑 Persona")
specialty = st.text_input("🩺 Specialty")

# Chat input
user_input = st.chat_input("💬 Ask me something...")
if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})

    with st.spinner("🤖 Generating AI response..."):
        ai_resp = generate_ai_response(user_input, brand, segment, objective, barrier, persona, specialty)
    st.session_state.messages.append({"role": "ai", "content": ai_resp})

# Display chat history
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f"🧑 **You:** {msg['content']}")
    else:
        st.markdown(f"🤖 **AI:** {msg['content']}")
