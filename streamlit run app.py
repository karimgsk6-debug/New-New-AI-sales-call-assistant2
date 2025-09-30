import streamlit as st
from PyPDF2 import PdfReader
import requests
import re

# ----------------------------
# Settings
# ----------------------------
BACKGROUND_URL = "https://drive.google.com/file/d/1WlvNx4MqufxuGUw9ilLxGJLsuozbX17b/view"

sales_call_steps = [
    "Greet",
    "Opening",
    "Probing",
    "Features & Benefits",
    "Handling Objections",
    "Close",
    "Follow-up"
]

APACT_STEPS = ["Acknowledge", "Probe", "Answer", "Check", "Transition"]

# ----------------------------
# Session State
# ----------------------------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ----------------------------
# CSS + JS
# ----------------------------
st.markdown(
    f"""
    <style>
    body {{
        background: url('{BACKGROUND_URL}') no-repeat center center fixed;
        background-size: cover;
    }}
    .chat-container {{
        display: flex;
        flex-direction: column;
        gap: 12px;
        max-height: 70vh;
        overflow-y: auto;
        padding: 12px;
    }}
    .chat-bubble-user {{
        align-self: flex-end;
        background: #ffb347;
        color: black;
        padding: 10px 14px;
        border-radius: 16px;
        max-width: 70%;
        word-wrap: break-word;
        font-size: 15px;
    }}
    .chat-bubble-ai {{
        align-self: flex-start;
        background: #f1f1f1;
        padding: 10px 14px;
        border-radius: 16px;
        max-width: 75%;
        word-wrap: break-word;
        font-size: 15px;
    }}
    .apact-step {{
        background: #ffe0b2;
        padding: 2px 6px;
        border-radius: 6px;
        font-weight: 600;
    }}
    .sales-step {{
        margin: 6px 0;
        padding: 6px 8px;
        background: #fff;
        border-radius: 8px;
        border-left: 3px solid #ff9800;
        font-size: 14px;
    }}
    .chat-input-container {{
        display: flex;
        align-items: center;
        gap: 8px;
        background: #fff;
        border-radius: 20px;
        padding: 6px 12px;
        border: 1px solid #ddd;
    }}
    </style>
    <script>
    function scrollToBottom() {{
        var chat = window.parent.document.querySelector('.chat-container');
        if(chat) chat.scrollTop = chat.scrollHeight;
    }}
    setInterval(scrollToBottom, 500);
    </script>
    """,
    unsafe_allow_html=True
)

# ----------------------------
# Helper: Extract PDF text
# ----------------------------
def extract_pdf_text(uploaded_file):
    reader = PdfReader(uploaded_file)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

# ----------------------------
# Chat Renderer
# ----------------------------
def render_chat_history():
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for entry in st.session_state.chat_history:
        role = entry.get("role","user")
        content = entry.get("content","")
        if role == "user":
            st.markdown(f'<div class="chat-bubble-user">{content}</div>', unsafe_allow_html=True)
        else:
            # One AI bubble with collapsible steps
            with st.container():
                with st.expander("📋 AI Sales Call Response", expanded=True):
                    for step in sales_call_steps:
                        step_content = ""
                        pattern = re.compile(f"{re.escape(step)}(.*?)(?=" + "|".join([re.escape(s) for s in sales_call_steps if s!=step]) + "|$)", re.DOTALL)
                        match = pattern.search(content)
                        if match:
                            step_content = match.group(1).strip()
                        if step_content:
                            for apact in APACT_STEPS:
                                step_content = step_content.replace(apact, f'<span class="apact-step">{apact}</span>')
                            with st.expander(f"➡️ {step}", expanded=False):
                                st.markdown(step_content.replace("\n", "<br>"), unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ----------------------------
# Filters & File Upload
# ----------------------------
with st.sidebar:
    st.header("⚙️ Filters & Upload")
    uploaded_file = st.file_uploader("Upload PDF (optional)", type=["pdf"])
    selected_filter = st.selectbox("Select Customer Segment", ["All", "High Potential", "Medium Potential", "Low Potential"])

# ----------------------------
# Chat Input
# ----------------------------
col_input = st.container()
with col_input:
    c1, c2 = st.columns([8,1])
    with c1:
        user_input = st.text_input("Type your message...", key="chat_input", label_visibility="collapsed")
    with c2:
        if st.button("➤", key="send_btn", help="Send", use_container_width=True):
            if user_input.strip():
                st.session_state.chat_history.append({"role":"user","content":user_input})

                # Simulated AI Response (replace with model integration)
                simulated_ai = "Greet Hello Doctor!\nOpening Today we discuss shingles vaccine.\nProbing How often do you see cases?\nFeatures & Benefits Vaccine reduces risk significantly.\nHandling Objections Acknowledge your concern about side effects.\nClose Can we start scheduling vaccinations?\nFollow-up I'll provide more data via email."

                st.session_state.chat_history.append({"role":"assistant","content":simulated_ai})

# ----------------------------
# Display Chat
# ----------------------------
render_chat_history()
