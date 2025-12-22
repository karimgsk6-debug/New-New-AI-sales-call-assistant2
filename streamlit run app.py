# =========================================================
# AI Sales Call Assistant
# Repo: New-New-AI-sales-call-assistant2
# =========================================================

import streamlit as st
import os
from pathlib import Path

# -------------------------
# PAGE CONFIG
# -------------------------
st.set_page_config(
    page_title="AI Sales Call Assistant",
    layout="wide",
    initial_sidebar_state="expanded"
)

# -------------------------
# API
# -------------------------
GROQ_API_KEY = "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"
try:
    from groq import Groq
except:
    Groq = None

# -------------------------
# ASSETS
# -------------------------
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"

SALES_REP_AVATAR = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/Visuals/sales%20rep.gif"
HCP_AVATAR = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/Visuals/HCP.gif"
AI_AVATAR = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"

# -------------------------
# PATHS
# -------------------------
BASE_PATH = ".devcontainer"
SALES_MODULE_PATH = os.path.join(BASE_PATH, "SalesModule")
REFERENCE_PATH = os.path.join(BASE_PATH, "references")

# -------------------------
# BRAND DATA
# -------------------------
BRANDS = {
    "shingrix": {
        "display": "Shingrix",
        "specialties": ["GP", "Internal Medicine", "Immunology", "Rheumatology"],
        "personas": ["Uncommitted Vaccinator", "Time-Pressed GP", "Safety-Focused"],
        "call_flow": ["Prepare", "Engage", "Risk Awareness", "Value", "Close"],
        "sales_path": f"{SALES_MODULE_PATH}/shingrix",
        "ref_path": f"{REFERENCE_PATH}/shingrix",
    },
    "jemperli": {
        "display": "Jemperli",
        "specialties": ["Medical Oncologist", "Gynecologic Oncologist"],
        "personas": ["Evidence-Driven", "Skeptical Specialist", "Early Adopter"],
        "call_flow": ["Identify", "Position", "Data", "Access", "Commit"],
        "sales_path": f"{SALES_MODULE_PATH}/jemperli",
        "ref_path": f"{REFERENCE_PATH}/jemperli",
    },
    "trelegy": {
        "display": "Trelegy",
        "specialties": ["Pulmonologist", "GP", "Respiratory Specialist"],
        "personas": ["Guideline-Driven", "Adherence-Focused", "Cost-Concerned"],
        "call_flow": ["Diagnose", "Differentiate", "Demonstrate", "Access", "Close"],
        "sales_path": f"{SALES_MODULE_PATH}/trelegy",
        "ref_path": f"{REFERENCE_PATH}/trelegy",
    },
}

# -------------------------
# SESSION DEFAULTS
# -------------------------
st.session_state.setdefault("brand", "shingrix")
st.session_state.setdefault("history", [])

# -------------------------
# CSS
# -------------------------
st.markdown(
    """
    <style>
    .chat-container { margin-bottom:120px; }
    .bubble { padding:12px 16px; border-radius:14px; max-width:85%; }
    .user { background:#eef2f6; color:#000; }
    .ai { background:#0e1a25; color:#e6f7ff; border:1px solid #1ecad3; }
    .row { display:flex; gap:12px; margin:10px 0; }
    .fixed-input {
        position:fixed; bottom:0; left:0; right:0;
        background:#fff; padding:12px; border-top:1px solid #ddd;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -------------------------
# HELPERS
# -------------------------
def load_text(folder):
    text = ""
    if not os.path.exists(folder):
        return ""
    for f in Path(folder).glob("**/*"):
        if f.suffix.lower() in [".txt", ".md"]:
            text += f"\n\n{f.read_text(errors='ignore')}"
    return text[:15000]

def groq_client():
    if not Groq or "ADD_" in GROQ_API_KEY:
        return None
    return Groq(api_key=GROQ_API_KEY)

def is_medical(q):
    return any(k in q.lower() for k in [
        "indication","dose","safety","efficacy","approved","label","contra"
    ])

def generate_response(query, brand_key):
    client = groq_client()
    if not client:
        return "⚠️ GROQ API not configured."

    brand = BRANDS[brand_key]
    refs = load_text(brand["ref_path"])
    sales = load_text(brand["sales_path"])

    if is_medical(query):
        system = f"""
You are a pharma AI assistant.
Answer ONLY using approved references.
References:
{refs}
"""
    else:
        system = f"""
Simulate a FULL sales call.
Use ONLY the selling modules below.
Brand: {brand['display']}
Call flow: {', '.join(brand['call_flow'])}

Selling modules:
{sales}

Format EXACTLY:

HCP says:
...

AI Sales Assistant says:
...
"""

    r = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role":"system","content":system},
            {"role":"user","content":query}
        ],
        temperature=0.3
    )
    return r.choices[0].message.content

# -------------------------
# SIDEBAR
# -------------------------
with st.sidebar:
    st.header("⚙️ Call Setup")

    st.session_state.brand = st.selectbox(
        "Brand",
        options=list(BRANDS.keys()),
        format_func=lambda x: BRANDS[x]["display"]
    )

    st.selectbox(
        "Specialty",
        BRANDS[st.session_state.brand]["specialties"]
    )

    st.selectbox(
        "HCP Persona",
        BRANDS[st.session_state.brand]["personas"]
    )

    if st.button("🆕 New Call"):
        st.session_state.history = []

# -------------------------
# TITLE
# -------------------------
st.markdown(
    f"## 💡 AI Sales Call Assistant — {BRANDS[st.session_state.brand]['display']}"
)

# -------------------------
# CHAT
# -------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

for role, text in st.session_state.history:
    if role == "user":
        st.markdown(
            f"""
            <div class="row">
                <img src="{SALES_REP_AVATAR}" width="44">
                <div class="bubble user">{text}</div>
            </div>
            """, unsafe_allow_html=True
        )
    else:
        if "HCP says:" in text:
            hcp, rep = text.split("AI Sales Assistant says:")
            st.markdown(
                f"""
                <div class="row">
                    <img src="{HCP_AVATAR}" width="44">
                    <div class="bubble ai">{hcp.replace("HCP says:","")}</div>
                </div>
                <div class="row">
                    <img src="{AI_AVATAR}" width="44">
                    <div class="bubble ai">{rep}</div>
                </div>
                """, unsafe_allow_html=True
            )
        else:
            st.markdown(
                f"""
                <div class="row">
                    <img src="{AI_AVATAR}" width="44">
                    <div class="bubble ai">{text}</div>
                </div>
                """, unsafe_allow_html=True
            )

st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# FIXED INPUT
# -------------------------
st.markdown('<div class="fixed-input">', unsafe_allow_html=True)

query = st.text_area(
    "Sales Rep query",
    placeholder="Generate sales call, ask indication, objection handling...",
    label_visibility="collapsed",
    height=70,
    key="input_box"
)

if st.button("SEND"):
    if query.strip():
        st.session_state.history.append(("user", query))
        answer = generate_response(query, st.session_state.brand)
        st.session_state.history.append(("ai", answer))

st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# FOOTER
# -------------------------
st.caption("For internal training use only. Approved sources required for external use.")
