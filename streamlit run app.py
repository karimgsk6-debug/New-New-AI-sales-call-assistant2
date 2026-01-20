# app_ai_sales_roleplay_final.py

import streamlit as st
import random
import os
import re
from html import escape

# ======================
# CONFIG
# ======================
st.set_page_config(page_title="AI Sales Role-Play Trainer", layout="wide")

GROQ_API_KEY = "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"

# ======================
# STATE
# ======================
if "chat" not in st.session_state:
    st.session_state.chat = []

# ======================
# BRAND DATA
# ======================
brand_data = {
    "shingrix": {
        "display": "Shingrix (Herpes Zoster Vaccine)",
        "segments": ["GP", "Dermatologist", "Geriatrician"],
        "barriers": ["Efficacy doubts", "Safety concerns", "Low demand"],
        "references_path": "./references/shingrix"
    },
    "trelegy": {
        "display": "Trelegy Ellipta",
        "segments": ["Pulmonologist", "GP"],
        "barriers": ["Adherence", "Inhaler technique", "Cost"],
        "references_path": "./references/trelegy"
    }
}

# ======================
# RAG UTILITIES
# ======================
def chunk_text(text, size=300):
    sents = re.split(r'(?<=[.!?])\s+', text)
    chunks, buf = [], ""
    for s in sents:
        if len(buf) + len(s) < size:
            buf += " " + s
        else:
            chunks.append(buf.strip())
            buf = s
    if buf:
        chunks.append(buf.strip())
    return chunks

def similarity(a, b):
    a, b = set(a.lower().split()), set(b.lower().split())
    return len(a & b) / max(len(a), 1)

def load_corpus(brand):
    folder = brand_data[brand]["references_path"]
    text = ""
    if os.path.exists(folder):
        for f in os.listdir(folder):
            if f.endswith(".txt"):
                with open(os.path.join(folder, f), encoding="utf-8") as file:
                    text += file.read()
    return chunk_text(text)

def retrieve(query, chunks, k=2):
    ranked = sorted(chunks, key=lambda c: similarity(query, c), reverse=True)
    return ranked[:k]

# ======================
# ROLE-PLAY ENGINE
# ======================
def hcp_response(user_msg, persona, difficulty, corpus):
    difficulty_map = {
        "Easy": [
            "That sounds reasonable.",
            "I’m open to hearing more."
        ],
        "Medium": [
            "I’m not fully convinced.",
            "How is this different from alternatives?"
        ],
        "Brutal": [
            "I don’t see the clinical necessity.",
            "Show me guideline-level evidence or this goes nowhere."
        ]
    }

    persona_edge = {
        "Skeptical": "I’ve heard similar claims before.",
        "Time-pressured": "You have 30 seconds.",
        "Evidence-led": "What does the data actually show?"
    }

    base = random.choice(difficulty_map[difficulty])
    persona_add = persona_edge.get(persona, "")
    refs = retrieve(user_msg, corpus)

    response = f"""
👨‍⚕️ **HCP ({persona}, {difficulty})**

{base}  
{persona_add}

{"📚 Guideline insight:" if refs else ""}
{" ".join(refs)}
"""
    return response.strip()

# ======================
# VOICE (BROWSER TTS)
# ======================
def speak(text):
    st.markdown(
        f"""
        <script>
        var msg = new SpeechSynthesisUtterance({text!r});
        msg.rate = 0.95;
        msg.pitch = 1;
        window.speechSynthesis.speak(msg);
        </script>
        """,
        unsafe_allow_html=True
    )

# ======================
# SIDEBAR
# ======================
with st.sidebar:
    st.header("🎯 Role-Play Setup")

    brand = st.selectbox("Brand", brand_data.keys(),
                         format_func=lambda x: brand_data[x]["display"])
    segment = st.selectbox("Segment", brand_data[brand]["segments"])
    persona = st.selectbox("Persona", ["Friendly", "Skeptical", "Evidence-led", "Time-pressured"])
    difficulty = st.radio("Objection Difficulty", ["Easy", "Medium", "Brutal"])

    if st.button("🧹 Reset"):
        st.session_state.chat = []
        st.experimental_rerun()

# ======================
# TITLE
# ======================
st.title(f"🎙 AI HCP Role-Play — {brand_data[brand]['display']}")

# ======================
# LOAD CORPUS
# ======================
corpus = load_corpus(brand)

# ======================
# CHAT INPUT
# ======================
user_input = st.text_input("You (Sales Rep):")

if st.button("Send"):
    if user_input:
        st.session_state.chat.append(("user", user_input))
        reply = hcp_response(user_input, persona, difficulty, corpus)
        st.session_state.chat.append(("hcp", reply))
        speak(reply)

# ======================
# CHAT DISPLAY
# ======================
for role, msg in st.session_state.chat:
    if role == "user":
        st.markdown(f"<div style='background:#eee;padding:10px;border-radius:10px'>{escape(msg)}</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='background:#002b36;color:#0ff;padding:14px;border-radius:12px'>{msg}</div>", unsafe_allow_html=True)

# ======================
# FOOTER
# ======================
st.markdown(
    "<small>⚠️ Internal training simulation only. Not for promotional use.</small>",
    unsafe_allow_html=True
)
