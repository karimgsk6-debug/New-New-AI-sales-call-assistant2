# ============================================================
# AI SALES CALL ASSISTANT — FINAL INTEGRATED VERSION
# ============================================================

import streamlit as st
import os, re

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="AI Sales Call Coach",
    layout="wide",
)

# ============================================================
# PATHS & VISUALS
# ============================================================
BASE_PATH = ".devcontainer"
VISUALS = os.path.join(BASE_PATH, "Visuals")

AI_AVATAR = f"{VISUALS}/futuristic_hologram_ai.gif"
HCP_AVATAR = f"{VISUALS}/HCP.gif"
REP_AVATAR = f"{VISUALS}/sales rep.gif"

# ============================================================
# BRAND DATA
# ============================================================
brand_data = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Vaccinator", "Reluctant Efficiency", "Patient Influenced", "Committed Vaccinator"],
        "barriers": ["HCP does not consider HZ a risk", "No time for discussion", "Cost concerns", "Not convinced of efficacy"],
        "specialties": ["GP", "Dermatologist", "Cardiology", "Endocrinology", "Immunology", "Internal Medicine", "Rheumatology"],
        "references_path": ".devcontainer/references/shingrix/",
        "sales_path": ".devcontainer/SalesModule/shingrix/",
        "call_flow": ["Prepare", "Engage", "Create Opportunities", "Influence", "Impact GSO", "Analyze"],
        "objections": {
            "efficacy": "Focus on durable protection and age-agnostic efficacy evidence.",
            "safety": "Acknowledge common AEs, then contrast with risk of complications from shingles.",
            "cost": "Frame cost as prevention of downstream complications and reduce clinic workload."
        }
    },
    "jemperli": {
        "display": "Jemperli",
        "segments": ["Target Identification", "Trial Adoption", "Routine Use", "Advocacy"],
        "personas": ["Data-Driven Oncologist", "Skeptical Specialist", "Innovator Prescriber", "Late Adopter"],
        "barriers": ["Unfamiliar with immunotherapy", "Safety concerns", "Limited eligibility", "Access/reimbursement issues"],
        "specialties": ["Oncologist", "Medical Oncologist"],
        "references_path": ".devcontainer/references/jemperli/",
        "sales_path": ".devcontainer/SalesModule/jemperli/",
        "call_flow": ["COCO", "Anchor", "Engage", "Close"],
        "objections": {
            "efficacy": "Discuss durable responses in dMMR/MSI-H and appropriate patient selection.",
            "safety": "Share safety profile and monitoring guidance to reduce perceived risk.",
            "access": "Offer starter kits or initiation support and reimbursement pathways."
        }
    },
    "trelegy": {
        "display": "Trelegy",
        "segments": ["Awareness", "Diagnosis", "Adoption", "Adherence"],
        "personas": ["Primary Care COPD Prescriber", "Pulmonologist", "Respiratory Nurse"],
        "barriers": ["Formulary access", "Inhaler technique", "Side effect concerns", "Cost/coverage"],
        "specialties": ["GP", "Pulmonologist", "Internal Medicine", "Respiratory Specialist"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy/",
        "call_flow": ["Prepare", "Engage", "Demonstrate", "Address Access", "Close"],
        "objections": {
            "device": "Offer quick practical coaching and demo materials.",
            "coverage": "Explain access options and patient support programs.",
            "effectiveness": "Share comparative outcomes framed for real-world practice."
        }
    }
}

# ============================================================
# SAFE GROQ IMPORT
# ============================================================
try:
    from groq import Groq
except:
    Groq = None

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")

def get_client():
    if not GROQ_API_KEY or not Groq:
        return None
    return Groq(api_key=GROQ_API_KEY)

# ============================================================
# SESSION STATE
# ============================================================
def init_state():
    st.session_state.setdefault("chat_history", [])
    st.session_state.setdefault("brand", "shingrix")
    st.session_state.setdefault("hcp_persona", "Uncommitted Vaccinator")
    st.session_state.setdefault("tone", "Professional")
    st.session_state.setdefault("main_input", "")

init_state()

bconf = brand_data[st.session_state.brand]

# ============================================================
# STYLES
# ============================================================
st.markdown("""
<style>
.chat-container {max-width: 920px; margin:auto;}
.msg {display:flex; margin-bottom:16px;}
.avatar {width:46px; margin-right:10px;}
.bubble {
  padding:14px;
  border-radius:16px;
  max-width:720px;
  background:#1f2937;
  color:white;
}
.rep {background:#0b3c49;}
.hcp {background:#3a2c1f;}
.fixed-input {
  position:fixed;
  bottom:48px;
  left:0;
  right:0;
  background:#0e1117;
  padding:12px;
  border-top:1px solid #333;
}
.footer {
  position:fixed;
  bottom:6px;
  width:100%;
  text-align:center;
  font-size:12px;
  color:#999;
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# DIALOG PARSER
# ============================================================
def parse_dialogue(text):
    blocks = []
    role = "rep"
    buff = ""

    for line in text.split("\n"):
        if re.search(r"\bhcp\b", line, re.I):
            if buff:
                blocks.append((role, buff.strip()))
            role = "hcp"
            buff = re.sub(r"\bhcp[:\-]*", "", line, flags=re.I)
        elif re.search(r"\brep\b|\byou say\b", line, re.I):
            if buff:
                blocks.append((role, buff.strip()))
            role = "rep"
            buff = re.sub(r"\brep[:\-]*|\byou say[:\-]*", "", line, flags=re.I)
        else:
            buff += " " + line

    if buff.strip():
        blocks.append((role, buff.strip()))
    return blocks

# ============================================================
# AI RESPONSE
# ============================================================
def add_ai_response(user_input):
    client = get_client()
    if not client:
        st.session_state.chat_history.append(
            {"role": "rep", "content": "⚠️ GROQ API key is not configured."}
        )
        return

    system_prompt = f"""
You are a senior pharmaceutical sales coach.
Brand: {bconf['display']}
Persona: {st.session_state.hcp_persona}
Tone: {st.session_state.tone}

Generate a realistic back-and-forth conversation.
Use natural spoken language.
No bullets, no headings, no symbols.
Clearly alternate between HCP and Sales Rep.
"""

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        temperature=0.4,
    )

    parsed = parse_dialogue(resp.choices[0].message.content)
    for r, c in parsed:
        st.session_state.chat_history.append({"role": r, "content": c})

# ============================================================
# PROMPT SUGGESTIONS
# ============================================================
with st.expander("💡 Prompt Suggestions (Click to Expand)", expanded=False):
    suggs = [
        f"Generate a {bconf['display']} sales call for {st.session_state.hcp_persona} in {st.session_state.tone} tone",
        f"How to handle an efficacy objection for {bconf['display']}?",
        "Short 30-second script for my next call",
        "Pilot offer for 10 patients — example script"
    ]
    cols = st.columns(2)
    for i, s in enumerate(suggs):
        if cols[i % 2].button(s, key=f"sugg_{i}"):
            st.session_state.main_input = s

# ============================================================
# CHAT HISTORY
# ============================================================
st.markdown("<div class='chat-container'>", unsafe_allow_html=True)

for msg in st.session_state.chat_history:
    avatar = REP_AVATAR if msg["role"] == "rep" else HCP_AVATAR
    css = "rep" if msg["role"] == "rep" else "hcp"
    st.markdown(f"""
    <div class="msg">
        <img src="{avatar}" class="avatar">
        <div class="bubble {css}">{msg["content"]}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# ============================================================
# FIXED INPUT
# ============================================================
st.markdown(f"""
<div class="fixed-input">
  <div style="display:flex;align-items:center;max-width:920px;margin:auto;">
    <img src="{AI_AVATAR}" width="46" style="margin-right:10px;">
""", unsafe_allow_html=True)

with st.form("main_input_form", clear_on_submit=True):
    user_input = st.text_area(
        "",
        st.session_state.main_input,
        height=80,
        label_visibility="collapsed",
        key="chat_input",
    )
    submitted = st.form_submit_button("SEND")

st.markdown("</div></div>", unsafe_allow_html=True)

if submitted and user_input.strip():
    st.session_state.chat_history.append({"role": "hcp", "content": user_input.strip()})
    add_ai_response(user_input.strip())
    st.session_state.main_input = ""
    st.experimental_rerun()

# ============================================================
# FOOTER
# ============================================================
st.markdown("""
<div class="footer">
Internal use only. Content generated strictly from approved materials.
</div>
""", unsafe_allow_html=True)
