# ============================================================
# app.py — AI Medical Rep Sales Call Assistant (FULL MERGED)
# ============================================================

import streamlit as st
import os, base64, tempfile

# ============================================================
# 🔐 GROQ API KEY
# ============================================================
GROQ_API_KEY = "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"

try:
    from groq import Groq
except:
    Groq = None

try:
    from PyPDF2 import PdfReader
except:
    PdfReader = None

try:
    from gtts import gTTS
except:
    gTTS = None

# ============================================================
# REPO ASSETS & PATHS
# ============================================================
REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"

GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"
AI_AVATAR = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/Visuals/futuristic_hologram_ai.gif"
BACKGROUND_PATH = ".devcontainer/Visuals/MR mentor final1.png"

BASE_PATH = ".devcontainer"
SALES_MODULE_PATH = os.path.join(BASE_PATH, "SalesModule")
REFERENCE_PATH = os.path.join(BASE_PATH, "references")
HCP_AVATAR = ".devcontainer/Visuals/HCP.gif"
REP_AVATAR = ".devcontainer/Visuals/sales rep.gif"

# ============================================================
# Page config
# ============================================================
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

# ============================================================
# CSS for chat bubbles, avatars, title
# ============================================================
st.markdown("""
<style>
.title-box {background: rgba(255,255,255,0.85); padding:12px; border-radius:10px; display:flex; align-items:center; justify-content:center; position:relative; margin-bottom:12px;}
.title-box img.left-logo { position:absolute; left:12px; height:36px; }
.title-box img.right-logo { position:absolute; right:12px; height:36px; }

.chat-bubble-user {background: rgba(0,0,0,0.06); color:#111; padding:10px 14px; border-radius:12px; margin:8px 0; max-width:80%; display:flex; align-items:center; gap:8px;}
.ai-message { display:flex; align-items:flex-start; gap:12px; margin:10px 0;}
.ai-avatar { width:52px; height:52px; border-radius:50%; box-shadow:0 0 12px rgba(0,255,255,0.6); flex-shrink:0; animation:holoPulse 2.5s infinite ease-in-out; }
@keyframes holoPulse {0% { box-shadow:0 0 8px rgba(0,255,255,0.35);}50% {box-shadow:0 0 22px rgba(0,255,255,0.9);}100% {box-shadow:0 0 8px rgba(0,255,255,0.35);}}
.ai-bubble {background: rgba(255,255,255,0.06); border:1px solid rgba(0,255,255,0.18); color:#E6FBFF; padding:14px; border-radius:14px; backdrop-filter: blur(6px); max-width:90%; white-space:pre-wrap;}
.user-bubble img {border-radius:50%; width:48px; height:48px;}
.hcp-bubble img {border-radius:50%; width:48px; height:48px;}
.fixed-disclaimer { font-size:12px; color:#aac; margin-top:16px; opacity:0.9; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# Dynamic background
# ============================================================
def set_dynamic_background(image_path):
    if not os.path.exists(image_path): return
    try:
        with open(image_path,"rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        st.markdown(f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background: linear-gradient(90deg, rgba(255,140,0,0.06), rgba(255,165,0,0.02)),
                        url("data:image/png;base64,{encoded}");
            background-repeat:no-repeat;
            background-position:right top;
            background-size:cover;
        }}
        </style>
        """, unsafe_allow_html=True)
    except: pass
set_dynamic_background(BACKGROUND_PATH)

# ============================================================
# Brands config
# ============================================================
BRANDS = {
    "shingrix": {
        "display": "Shingrix",
        "segments": ["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas": ["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers": ["HZ risk not perceived","No time","Cost concerns","Efficacy doubts"],
        "specialties": ["GP","Dermatology","Cardiology","Immunology","Internal Medicine"],
        "references_path": os.path.join(REFERENCE_PATH,"shingrix"),
        "sales_path": os.path.join(SALES_MODULE_PATH,"shingrix"),
        "call_flow": ["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Analyze"],
        "objections": {"efficacy":"Focus on durable protection.","safety":"Acknowledge common AEs.","cost":"Frame cost as prevention of complications."}
    },
    "jemperli": {
        "display":"Jemperli",
        "segments":["Target ID","Trial","Routine","Advocacy"],
        "personas":["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber"],
        "barriers":["Eligibility","Safety","Access"],
        "specialties":["Oncologist","Medical Oncologist"],
        "references_path": os.path.join(REFERENCE_PATH,"jemperli"),
        "sales_path": os.path.join(SALES_MODULE_PATH,"jemperli"),
        "call_flow":["COCO","Anchor","Engage","Close"],
        "objections":{"efficacy":"Discuss durable responses.","safety":"Share safety profile.","access":"Offer starter kits."}
    },
    "trelegy": {
        "display":"Trelegy",
        "segments":["Awareness","Diagnosis","Adoption","Adherence"],
        "personas":["PCP Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers":["Inhaler","Access","Coverage"],
        "specialties":["GP","Pulmonologist"],
        "references_path": os.path.join(REFERENCE_PATH,"trelegy"),
        "sales_path": os.path.join(SALES_MODULE_PATH,"trelegy"),
        "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"],
        "objections":{"device":"Offer practical coaching.","coverage":"Explain access options.","effectiveness":"Share outcomes."}
    },
}

# ============================================================
# Session defaults
# ============================================================
if "brand" not in st.session_state: st.session_state.brand = "shingrix"
if "chat_history" not in st.session_state: st.session_state.chat_history = []

# ============================================================
# GROQ client helper
# ============================================================
def get_client():
    if not GROQ_API_KEY or GROQ_API_KEY.startswith("Add_"): return None
    if not Groq: return None
    return Groq(api_key=GROQ_API_KEY)

# ============================================================
# Load folder helper
# ============================================================
def read_file(path):
    if path.endswith(".pdf") and PdfReader:
        reader = PdfReader(path)
        return "".join([p.extract_text() or "" for p in reader.pages])
    with open(path,"r",encoding="utf-8",errors="ignore") as f:
        return f.read()

def load_folder(folder):
    if not os.path.exists(folder): return ""
    content=[]
    for f in os.listdir(folder):
        if f.endswith((".txt",".pdf")):
            content.append(read_file(os.path.join(folder,f)))
    return "\n".join(content)

# ============================================================
# Objection response helper
# ============================================================
def persona_profile(persona):
    profiles = {
        "Uncommitted Vaccinator": {"quick_win":"1-step vaccination script."},
        "Reluctant Efficiency":{"quick_win":"Concise adoption checklist."},
        "Patient Influenced":{"quick_win":"Patient-facing summary."},
        "Committed Vaccinator":{"quick_win":"Highlight long-term impact data."},
        "Data-Driven Oncologist":{"quick_win":"Share key trial metrics."},
        "Skeptical Specialist":{"quick_win":"Provide monitoring protocols."},
        "Innovator Prescriber":{"quick_win":"Show new workflow pilots."},
        "PCP Prescriber":{"quick_win":"Demonstrate simple inhaler use."},
        "Pulmonologist":{"quick_win":"Share comparative outcomes."},
        "Respiratory Nurse":{"quick_win":"Provide patient coaching sheets."},
    }
    return profiles.get(persona, {"quick_win":"Offer actionable next step."})

def objection_response(product_key, objection_key, persona):
    product = BRANDS.get(product_key,{})
    reply = product.get("objections",{}).get(objection_key,"Acknowledge and offer concise evidence.")
    prof = persona_profile(persona)
    return f"{reply} (Tailored: {prof['quick_win']})"

# ============================================================
# Generate sales call / RAG answer
# ============================================================
def generate_sales_call(user_input):
    brand_conf = BRANDS.get(st.session_state.brand, BRANDS["shingrix"])
    sales_module = load_folder(brand_conf["sales_path"])
    references = load_folder(brand_conf["references_path"])

    if not sales_module and not references:
        return f"❌ Missing materials for {brand_conf['display']}"

    client = get_client()
    if not client:
        return f"⚠️ GROQ API unavailable. Showing placeholder output.\n\n{sales_module[:500]}"

    # System + User prompt
    system_prompt = f"""
You are a pharma sales assistant. Use ONLY provided SalesModule & References.
Brand: {brand_conf['display']}, Persona: {st.session_state.get('persona','')}, Tone: executive
Call flow: {brand_conf['call_flow']}
"""
    user_prompt = f"Scenario: {user_input}\nSales Module:\n{sales_module}\nReferences:\n{references}"

    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],
        temperature=0.5,
    )
    return resp.choices[0].message.content

# ============================================================
# Text → Voice
# ============================================================
def text_to_voice(text):
    if not gTTS: return None
    tmp = tempfile.NamedTemporaryFile(delete=False,suffix=".mp3")
    gTTS(text=text[:1200],lang="en").save(tmp.name)
    return open(tmp.name,"rb").read()

# ============================================================
# Sidebar
# ============================================================
with st.sidebar:
    st.header("Call Configuration")
    brand_key = st.selectbox(
        "Brand",
        options=list(BRANDS.keys()),
        format_func=lambda k: BRANDS[k]["display"],
        key="brand_selector"
    )
    st.session_state.brand = brand_key
    brand_conf = BRANDS[brand_key]

    st.selectbox("Specialty", brand_conf["specialties"], key="specialty")
    st.selectbox("HCP Persona", brand_conf["personas"], key="persona")
    st.selectbox("Segment", brand_conf["segments"], key="segment")
    st.selectbox("Tone", ["executive","clinical","coaching"], key="tone")
    st.slider("Creativity",0.0,1.0,0.3,key="temperature")

# ============================================================
# Title box
# ============================================================
st.markdown(f"""
<div class="title-box">
    <img src="{GSK_LOGO_RAW}" class="left-logo">
    <h2>💡 AI Sales Call Assistant — {brand_conf['display']}</h2>
    <img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""",unsafe_allow_html=True)

# ============================================================
# User input + clickable suggestions
# ============================================================
user_input = st.text_area("Your query (sales rep)", height=120)
suggestions = ["Generate full sales call", "Ask medical question", "Ask approved indication", "Handle cost objection"]
cols = st.columns(len(suggestions))
for i,s in enumerate(suggestions):
    if cols[i].button(s):
        user_input = s
        st.session_state.main_input = user_input

# ============================================================
# Generate / Display response
# ============================================================
if st.button("SEND"):
    if user_input:
        reply_text = generate_sales_call(user_input)
        st.session_state.chat_history.append(("rep",user_input))
        st.session_state.chat_history.append(("hcp",reply_text))

# ============================================================
# Show chat history
# ============================================================
for role,text in st.session_state.chat_history:
    if role=="rep":
        st.markdown(f"""
        <div class="chat-bubble-user">
        <img src="{REP_AVATAR}"> {text}
        </div>
        """,unsafe_allow_html=True)
    elif role=="hcp":
        st.markdown(f"""
        <div class="ai-message">
        <img src="{HCP_AVATAR}" class="ai-avatar">
        <div class="ai-bubble">{text}</div>
        </div>
        """,unsafe_allow_html=True)
        audio_bytes = text_to_voice(text)
        if audio_bytes: st.audio(audio_bytes, format="audio/mp3")

# ============================================================
# Footer disclaimer
# ============================================================
st.markdown('<div class="fixed-disclaimer">Internal use only. Generated content limited to approved materials.</div>', unsafe_allow_html=True)
