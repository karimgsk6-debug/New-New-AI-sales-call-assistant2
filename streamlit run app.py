# ============================================================
# app.py — AI Medical Rep Sales Call Assistant (LIVE ROLE-PLAY)
# Brand-governed | SalesModule + Medical RAG | Hologram UI
# ============================================================

import streamlit as st
import os, tempfile
from groq import Groq
from gtts import gTTS

# ============================================================
# CONFIG
# ============================================================
GROQ_API_KEY = "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"

BASE_PATH = ".devcontainer"
SALES_MODULE_PATH = os.path.join(BASE_PATH, "SalesModule")
REFERENCE_PATH = os.path.join(BASE_PATH, "references")

AI_AVATAR = ".devcontainer/Visuals/futuristic_hologram_ai.gif"
HCP_AVATAR = ".devcontainer/Visuals/HCP.gif"
REP_AVATAR = ".devcontainer/Visuals/sales rep.gif"

# ============================================================
# PAGE
# ============================================================
st.set_page_config("AI Sales Call Assistant", layout="wide")

# ============================================================
# SESSION STATE
# ============================================================
st.session_state.setdefault("chat", [])
st.session_state.setdefault("brand", "shingrix")
st.session_state.setdefault("persona", "")
st.session_state.setdefault("pending_hcp", [])
st.session_state.setdefault("rep_input", "")

# ============================================================
# BRAND DATA (SINGLE SOURCE OF TRUTH)
# ============================================================
BRANDS = {
    "shingrix": {
        "display": "Shingrix",
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "sales": os.path.join(SALES_MODULE_PATH, "shingrix"),
        "refs": os.path.join(REFERENCE_PATH, "shingrix"),
    },
    "jemperli": {
        "display": "Jemperli",
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber"],
        "sales": os.path.join(SALES_MODULE_PATH, "jemperli"),
        "refs": os.path.join(REFERENCE_PATH, "jemperli"),
    },
    "trelegy": {
        "display": "Trelegy",
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "sales": os.path.join(SALES_MODULE_PATH, "trelegy"),
        "refs": os.path.join(REFERENCE_PATH, "trelegy"),
    },
}

# ============================================================
# HELPERS
# ============================================================
def load_folder(path):
    if not os.path.exists(path):
        return ""
    out = []
    for f in os.listdir(path):
        if f.endswith(".txt"):
            with open(os.path.join(path, f), "r", encoding="utf-8", errors="ignore") as file:
                out.append(file.read())
    return "\n".join(out)

def tts(text):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    gTTS(text=text[:1800], lang="en").save(tmp.name)
    return tmp.name

# ============================================================
# LLM CORE
# ============================================================
def generate(rep_input, hcp_reply=None):
    b = BRANDS[st.session_state.brand]
    sales = load_folder(b["sales"])
    refs = load_folder(b["refs"])

    client = Groq(api_key=GROQ_API_KEY)

    system = f"""
You are a pharmaceutical sales excellence AI.

RULES (STRICT):
- Use ONLY the provided Sales Module and References
- No external knowledge
- No markdown symbols
- Human conversational tone
- Simulate dialogue clearly

Brand: {b['display']}
Persona: {st.session_state.persona}
"""

    user = f"""
SALES MODULE:
{sales}

REFERENCES:
{refs}

Sales Rep input:
{rep_input}

Previous HCP reply (if any):
{hcp_reply or "None"}

TASK:
If this is a sales call request:
- Simulate a realistic dialogue
- Prefix lines with:
HCP:
AI SALES ASSISTANT:

Also provide:
HCP POSSIBLE NEXT REPLIES (3 short options)

If this is a medical/product question:
- Answer strictly from references
"""

    res = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.3,
    ).choices[0].message.content

    hcp_opts = []
    if "HCP POSSIBLE NEXT REPLIES" in res:
        parts = res.split("HCP POSSIBLE NEXT REPLIES")
        res = parts[0].strip()
        hcp_opts = [l.strip("- ").strip() for l in parts[1].split("\n") if l.strip()]

    return res, hcp_opts

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.selectbox("Brand", BRANDS.keys(), key="brand")
    st.selectbox("HCP Persona", BRANDS[st.session_state.brand]["personas"], key="persona")

# ============================================================
# PROMPT SUGGESTIONS
# ============================================================
with st.expander("💡 Suggested Sales Rep Prompts"):
    for p in [
        "Generate a full sales call",
        "Address an HCP safety concern",
        "Ask about approved indication",
        "Handle cost objection",
        "Discuss clinical evidence"
    ]:
        if st.button(p):
            st.session_state.rep_input = p

# ============================================================
# INPUT (SALES REP)
# ============================================================
st.markdown("### Sales Rep")
rep = st.text_input("Type what you want to say", key="rep_input")

if st.button("SEND"):
    if rep.strip():
        out, hcp = generate(rep)
        st.session_state.chat.append(("rep", rep))
        st.session_state.chat.append(("ai", out))
        st.session_state.pending_hcp = hcp
        st.session_state.rep_input = ""

# ============================================================
# CHAT DISPLAY
# ============================================================
for role, text in st.session_state.chat:
    if role == "rep":
        st.markdown(f"<img src='{REP_AVATAR}' width='40'> **Sales Rep:** {text}", unsafe_allow_html=True)
    else:
        lines = text.split("\n")
        for l in lines:
            if l.startswith("HCP:"):
                st.markdown(f"<img src='{HCP_AVATAR}' width='40'> {l.replace('HCP:', '')}", unsafe_allow_html=True)
            elif l.startswith("AI SALES ASSISTANT:"):
                clean = l.replace("AI SALES ASSISTANT:", "")
                st.markdown(f"<img src='{AI_AVATAR}' width='40'> {clean}", unsafe_allow_html=True)
                st.audio(tts(clean))

# ============================================================
# HCP NEXT REPLIES
# ============================================================
if st.session_state.pending_hcp:
    st.markdown("### What the HCP may say next:")
    for opt in st.session_state.pending_hcp:
        if st.button(opt):
            out, hcp = generate("Continue the discussion", hcp_reply=opt)
            st.session_state.chat.append(("ai", out))
            st.session_state.pending_hcp = hcp

# ============================================================
# DISCLAIMER
# ============================================================
st.caption("Internal use only. Generated content strictly limited to approved materials.")
