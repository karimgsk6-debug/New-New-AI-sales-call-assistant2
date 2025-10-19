import streamlit as st
from PIL import Image
from io import BytesIO
import re, os, tempfile, base64, requests
from datetime import datetime
from groq import Groq
from PyPDF2 import PdfReader
from html import escape
from gtts import gTTS

# ---------------------------- Page Config ----------------------------
st.set_page_config(page_title="GSK AI Sales Call Assistant", layout="wide")

# ---------------------------- Session Defaults ----------------------------
if "chat_history" not in st.session_state: st.session_state.chat_history = []
if "uploaded_pdf_text" not in st.session_state: st.session_state.uploaded_pdf_text = ""
if "pdf_summary" not in st.session_state: st.session_state.pdf_summary = ""
if "voice_pref" not in st.session_state: st.session_state.voice_pref = "Old Male"
if "language" not in st.session_state: st.session_state.language = "English"
if "pdf_summary_size" not in st.session_state: st.session_state.pdf_summary_size = "Normal"
if "main_input" not in st.session_state: st.session_state.main_input = ""

# ---------------------------- Assets ----------------------------
BACKGROUND_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/845b8f1ae98e46440e840c0a906f3610dd343c9a/.devcontainer/.devcontainer/background1.png"
GSK_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/gsk_logo.png"
AI_LOGO_URL = "https://raw.githubusercontent.com/karimgsk6-debug/New-New-AI-sales-call-assistant2/main/.devcontainer/ai_logo.png"

# ---------------------------- CSS ----------------------------
CSS = f"""
<style>
body {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-attachment: fixed;
}}
.title-box {{
  background: rgba(255,255,255,0.85);
  padding: 12px;
  border-radius: 10px;
  text-align: center;
  position: relative;
}}
.title-box img.ai-logo {{
   position: absolute;
   top: 10px;
   right: 15px;
   width: 120px;
}}
.title-box img.gsk-logo {{
   position: absolute;
   top: 10px;
   left: 15px;
   width: 120px;
}}
.chat-container {{
  max-height: 60vh;
  overflow-y: auto;
  padding: 12px;
  border-radius: 10px;
  background: rgba(240,240,240,0.7);
  margin-bottom: 80px;
}}
.chat-bubble-user {{ background: #0078D7; color:white; margin-left:auto; padding:10px; border-radius:10px; margin-bottom:6px; max-width:75%; }}
.chat-bubble-ai {{ background: #d9f0ff; color:#000; margin-right:auto; padding:10px; border-radius:10px; margin-bottom:6px; max-width:75%; }}
.fixed-chat-input {{
   position: fixed;
   bottom: 20px;
   left: 20px;
   right: 20px;
   z-index: 10002;
}}
.fixed-chat-input textarea {{
   width: 100%;
   min-height: 60px;
   max-height: 180px;
   resize: vertical;
}}
.send-button {{
   position: fixed;
   bottom: 30px;
   right: 30px;
   z-index: 10003;
   height: 40px;
   width: 110px;
}}
.prompt-suggestions {{
   position: absolute;
   bottom: 90px;
   left: 20px;
   z-index: 10005;
   background: rgba(255,255,255,0.95);
   padding: 8px;
   border-radius: 6px;
   max-width: 400px;
   box-shadow: 0px 0px 5px #888;
}}
.prompt-suggestion:hover {{
   background-color: #e0e0e0;
   cursor: pointer;
}}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------------------------- GROQ Client ----------------------------
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# ---------------------------- Brands & Modules ----------------------------
brand_data = {
    "TRELEGY": {
        "segments": ["R – Reach", "A – Acquisition", "C – Conversion", "E – Engagement"],
        "personas": ["Uncommitted Prescriber", "Reluctant Efficiency", "Patient Influenced", "Committed Prescriber"],
        "barriers": ["HCP unaware of guideline", "Time constraints", "Cost concerns", "Not convinced of efficacy"],
        "references_path": ".devcontainer/references/trelegy/",
        "sales_path": ".devcontainer/SalesModule/trelegy"
    }
}

specialties = ["GP", "Pulmonologist", "Respiratory Specialist"]
objectives = ["Awareness", "Adoption", "Retention"]

# ---------------------------- Sidebar ----------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand = st.selectbox("Brand", list(brand_data.keys()))
    selected_brand = brand_data[brand]
    segment = st.selectbox("Segment", selected_brand["segments"])
    persona = st.selectbox("HCP Persona", selected_brand["personas"])
    barrier = st.multiselect("Doctor Barrier", selected_brand["barriers"])
    specialty = st.selectbox("Specialty", specialties)
    objective = st.selectbox("Objective", objectives)
    response_tone = st.selectbox("Response Tone", ["Formal", "Casual", "Friendly", "Persuasive"])
    response_length = st.selectbox("Response Length", ["Short", "Medium", "Long"])

with st.sidebar.expander("🌐 Add External Reference URLs", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

# ---------------------------- Helper Functions ----------------------------
def load_local_text(folder_path):
    """Load PDFs and TXT files from local folder"""
    text_all = ""
    if not os.path.exists(folder_path): return ""
    files = [f for f in os.listdir(folder_path) if f.lower().endswith((".pdf",".txt"))]
    for file in files:
        path = os.path.join(folder_path, file)
        try:
            if file.endswith(".pdf"):
                reader = PdfReader(path)
                text_all += "".join([p.extract_text() or "" for p in reader.pages])
            elif file.endswith(".txt"):
                with open(path, "r", encoding="utf-8") as f:
                    text_all += f.read()
        except:
            pass
    return text_all

def load_external_refs(url_list):
    text = ""
    for url in url_list:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code==200: text+=r.text+"\n"
        except: pass
    return text

def generate_audio(text):
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    try:
        tts = gTTS(text=text, lang="en", slow=True)
        tts.save(tmp_file.name)
        audio_bytes = open(tmp_file.name,"rb").read()
        return base64.b64encode(audio_bytes).decode()
    except:
        return ""

def generate_ai_response(user_input):
    combined_context = "\n".join([
        load_local_text(selected_brand["references_path"]),
        load_local_text(selected_brand["sales_path"]),
        load_external_refs([u for u in external_urls if u.strip()])
    ])[:15000]

    prompt = f"""
Brand: {brand}
Persona: {persona}
Segment: {segment}
Specialty: {specialty}
Objective: {objective}
Barriers: {', '.join(barrier) if barrier else 'None'}
Context (truncated):\n{combined_context[:5000]}
User Input: {user_input}
"""
    if client:
        try:
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role":"system","content":"You are a helpful pharma AI assistant."},
                          {"role":"user","content":prompt}],
                temperature=0.65
            )
            return resp.choices[0].message.content
        except:
            return f"(Fallback) {user_input}"
    return f"(Fallback) {user_input}"

# ---------------------------- Title & Header ----------------------------
st.markdown(f"""
<div class="title-box">
   <img src="{GSK_LOGO_URL}" class="gsk-logo">
   <img src="{AI_LOGO_URL}" class="ai-logo">
   <h1>💡 AI Sales Call Assistant</h1>
   <p>Empowering reps for smarter <b style="color:#FF6F00;">{brand}</b> conversations</p>
</div>
""", unsafe_allow_html=True)

# ---------------------------- Chat Container ----------------------------
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for item in st.session_state.chat_history:
    if item["role"]=="user":
        st.markdown(f'<div class="chat-bubble-user">🧑 You: {escape(item["content"])}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-ai">🤖 AI: {escape(item["content"])}</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------- Copilot Prompt Suggestions ----------------------------
PROMPTS = [
    "Generate call flow",
    "Handle objection",
    "Summarize HCP persona"
]

if st.session_state.main_input.strip():
    suggestion_html = '<div class="prompt-suggestions">'
    for p in PROMPTS:
        suggestion_html += f'<div class="prompt-suggestion" onclick="document.getElementById(\'chat_input\').value = `{p}`">{p}</div>'
    suggestion_html += '</div>'
    st.markdown(suggestion_html, unsafe_allow_html=True)

# ---------------------------- Chat Input ----------------------------
st.markdown(f"""
<div class="fixed-chat-input">
<textarea id="chat_input" placeholder="Type your question or continue your sales dialogue...">{st.session_state.main_input}</textarea>
</div>
<button class="send-button" onclick="window.parent.postMessage({{'type':'SEND_CHAT'}}, '*')">Send</button>
<script>
const textarea = document.getElementById('chat_input');
window.addEventListener('message', (event)=>{
    if(event.data.type=='SEND_CHAT'){ 
        const val = textarea.value;
        fetch(window.location.href + '?chat_input=' + encodeURIComponent(val));
    }
});
</script>
""", unsafe_allow_html=True)

# ---------------------------- Disclaimer ----------------------------
st.markdown(f"""
<div style="position:fixed; bottom:0; left:0; right:0; background:rgba(255,255,255,0.95); 
padding:8px; border-top:2px solid #FF6F00; font-size:12px; z-index:9999;">
<b>Disclaimer:</b> ⚠️This AI Sales Call Assistant is for informational purposes only. Always verify with approved medical references and company guidance.
</div>
""", unsafe_allow_html=True)

# ---------------------------- Handle Chat Input ----------------------------
import urllib.parse
query_params = st.experimental_get_query_params()
if "chat_input" in query_params:
    user_text = query_params["chat_input"][0]
    st.session_state.chat_history.append({"role":"user","content":user_text})
    ai_resp = generate_ai_response(user_text)
    st.session_state.chat_history.append({"role":"assistant","content":ai_resp})
    st.experimental_rerun()
# ---------------------------- Copilot Prompt Suggestions ----------------------------
# Brand-specific prompts
BRAND_PROMPTS = {
    "TRELEGY": [
        "Generate call flow",
        "Handle objection",
        "Summarize HCP persona",
        "Suggest patient engagement strategy"
    ]
}

# JS + HTML for dynamic suggestions
st.markdown(f"""
<div id="prompt_suggestions" class="prompt-suggestions" style="display:none;"></div>

<script>
const inputEl = document.getElementById('chat_input');
const suggestionsDiv = document.getElementById('prompt_suggestions');
const prompts = {BRAND_PROMPTS[brand]};

inputEl.addEventListener('input', function() {{
    const val = inputEl.value.trim();
    if(val.length > 0){{
        suggestionsDiv.style.display = 'block';
        suggestionsDiv.innerHTML = '';
        prompts.forEach(p => {{
            const div = document.createElement('div');
            div.className = 'prompt-suggestion';
            div.innerText = p;
            div.onclick = function() {{
                inputEl.value = p;
                suggestionsDiv.style.display = 'none';
                inputEl.focus();
            }};
            suggestionsDiv.appendChild(div);
        }});
    }} else {{
        suggestionsDiv.style.display = 'none';
    }}
}});
</script>
""", unsafe_allow_html=True)
