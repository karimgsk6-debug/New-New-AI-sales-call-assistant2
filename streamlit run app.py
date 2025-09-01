import streamlit as st
from PIL import Image
from io import BytesIO
from datetime import datetime
import requests
from groq import Groq
import matplotlib.pyplot as plt

# --- API Key (set directly here) ---
# ⚠️ Replace with your actual key
GROQ_API_KEY = "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"

if not GROQ_API_KEY:
    st.error("❌ Groq API key not set. Please add it in the script.")
else:
    client = Groq(api_key=GROQ_API_KEY)

# --- References to be shown in collapsible section ---
REFERENCES = """
1. Clinical Overview about Shingles. CDC. Available at: https://www.cdc.gov/shingles/hcp/clinical-overview.html (Accessed: 04 February 2024).  
2. Harpaz R, et al. MMWR Recomm Rep 2008;57:1-30.  
3. Kawai K, Gebremeskel BG, Acosta CJ. Systematic review of incidence and complications of herpes zoster: BMJ Open. 2014;4(6):e004833.  
4. Pinchinat S, et al. Similar herpes zoster incidence across Europe: BMC Infect Dis. 2013;13:170.  
5. Li Y, et al. Disease Burden Due to Herpes Zoster in China: PLoS One. 2016;11(4):e0152660.  
6. SHINGRIX Egyptian Drug Authority Approved leaflet. Approval date: 11/09/2023.  
"""

# --- Streamlit page setup ---
st.set_page_config(page_title="AI Sales Call Assistant", page_icon="💊", layout="wide")
st.title("💊 AI Sales Call Assistant")

# --- Chat history ---
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# --- Chat bubble styling ---
chat_css = """
<style>
.user-bubble {
    background-color: #dcf8c6;
    color: black;
    padding: 10px;
    border-radius: 15px;
    margin: 5px;
    max-width: 70%;
    float: right;
    clear: both;
}
.ai-bubble {
    background-color: #f1f0f0;
    color: black;
    padding: 10px;
    border-radius: 15px;
    margin: 5px;
    max-width: 70%;
    float: left;
    clear: both;
}
</style>
"""
st.markdown(chat_css, unsafe_allow_html=True)

# --- Display chat history ---
for msg in st.session_state["messages"]:
    if msg["role"] == "user":
        st.markdown(f'<div class="user-bubble">👤 {msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="ai-bubble">🤖 {msg["content"]}</div>', unsafe_allow_html=True)

        # --- Show visuals when AI responds ---
        with st.container():
            # Example: Shingles rash image from CDC
            st.image(
                "https://www.cdc.gov/shingles/images/shingles-rash.jpg",
                caption="Shingles rash (CDC)",
                use_column_width=True
            )

            # Example: Incidence chart from literature
            fig, ax = plt.subplots()
            ages = ["50-59", "60-69", "70-79", "80+"]
            incidence = [6, 8, 10, 12]  # per 1,000 person-years (illustrative)
            ax.bar(ages, incidence)
            ax.set_title("Herpes Zoster Incidence by Age Group")
            ax.set_ylabel("Incidence (per 1,000 person-years)")
            st.pyplot(fig)

            # Collapsible references
            with st.expander("📚 References"):
                st.markdown(REFERENCES)

# --- Chat input with send + clear ---
with st.container():
    cols = st.columns([10, 1, 1])
    user_input = cols[0].text_input(
        "Type your message...",
        key="chat_input",
        label_visibility="collapsed",
        on_change=lambda: st.session_state.update(send_triggered=True)
    )
    send_clicked = cols[1].button("⏩")  # Send button
    clear_clicked = cols[2].button("🗑️ Clear Chat")  # Clear chat button

# --- Clear chat functionality ---
if clear_clicked:
    st.session_state["messages"] = []
    st.experimental_rerun()

# --- Process new input ---
if (user_input and (send_clicked or st.session_state.get("send_triggered", False))):
    st.session_state["messages"].append({"role": "user", "content": user_input})
    st.session_state["send_triggered"] = False

    try:
        response = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role": "system", "content": "You are an AI assistant for pharma sales discussions."}] +
                     [{"role": m["role"], "content": m["content"]} for m in st.session_state["messages"]],
            temperature=0.7,
            max_tokens=500,
        )

        ai_reply = response.choices[0].message.content.strip()
        st.session_state["messages"].append({"role": "assistant", "content": ai_reply})
        st.experimental_rerun()

    except Exception as e:
        st.error(f"⚠️ Error generating response: {e}")
