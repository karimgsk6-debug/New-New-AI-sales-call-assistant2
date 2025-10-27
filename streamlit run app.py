# app.py - Full AI Sales Call Assistant (Enhanced, APACT, interactive feedback, humanized voice, examples)
import streamlit as st
import os, re, tempfile, base64, io
from datetime import datetime
from html import escape

# Optional libs (best-effort)
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

try:
    from docx import Document
    DOCX_AVAILABLE = True
except:
    DOCX_AVAILABLE = False

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import linear_kernel
    SKLEARN_AVAILABLE = True
except:
    SKLEARN_AVAILABLE = False

try:
    import elevenlabs
    ELEVENLABS_AVAILABLE = True
except:
    ELEVENLABS_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except:
    PYTTSX3_AVAILABLE = False

# -------------------------
# Page config & background
# -------------------------
st.set_page_config(page_title="AI Sales Call Assistant", layout="wide", initial_sidebar_state="expanded")

REPO_USER = "karimgsk6-debug"
REPO_NAME = "New-New-AI-sales-call-assistant2"
COMMIT = "845b8f1ae98e46440e840c0a906f3610dd343c9a"
REPO_BLOB_BASE = f"https://github.com/{REPO_USER}/{REPO_NAME}/blob/{COMMIT}/.devcontainer"
REPO_RAW_BASE = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/{COMMIT}/.devcontainer"
BACKGROUND_URL = REPO_RAW_BASE + "/background1.png"
GSK_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/GSK1-logo.png"
AI_LOGO_RAW = f"https://raw.githubusercontent.com/{REPO_USER}/{REPO_NAME}/main/.devcontainer/AURA1.png"

# -------------------------
# Session defaults
# -------------------------
defaults = {
    "chat_history": [],
    "main_input": "",
    "selected_brand": "shingrix",
    "temperature": 0.62,
    "search_mode": "deep",
    "medical_summary": "",
    "sales_summary": "",
    "uploaded_pdf_text": "",
    "pdf_summary": "",
    "feedback": {},
    "language": "English",
    # user preference stored for the session
    "reply_style": "balanced",  # options: balanced, short_script, data, conversational
    "awaiting_style_pref": False,
}
for k,v in defaults.items():
    st.session_state.setdefault(k,v)

# -------------------------
# CSS & background
# -------------------------
CSS = f"""
<style>
[data-testid="stAppViewContainer"] {{
  background-image: url('{BACKGROUND_URL}');
  background-size: cover;
  background-position: center;
  background-attachment: fixed;
}}
.title-box {{
  background: rgba(255,255,255,0.95);
  padding: 12px;
  border-radius: 10px;
  margin-bottom: 12px;
  position: relative;
  display:flex;
  align-items:center;
  justify-content:center;
}}
.title-box img.left-logo {{ position:absolute; left:12px; height:64px; }}
.title-box img.right-logo {{ position:absolute; right:12px; height:64px; }}
.chat-container {{ max-height: 60vh; overflow-y:auto; padding:12px; background: rgba(255,255,255,0.95); border-radius:8px; margin-bottom:160px; }}
.chat-bubble-user {{ background:#0078D7; color:white; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; margin-left:auto; }}
.chat-bubble-ai {{ background:#eef9ff; color:#000; padding:10px; border-radius:12px; margin:8px 0; max-width:78%; }}
.suggestion-pill {{ background:#fff; border:1px solid #ddd; padding:8px 12px; border-radius:20px; margin:6px; cursor:pointer; display:inline-block; }}
.suggestion-pill:hover {{ background:#f0f8ff; }}
.citation-box {{ background:#fbfbff; border-left:4px solid #0078D7; padding:8px; margin-top:8px; border-radius:6px; font-size:13px; white-space:pre-wrap; }}
.input-area {{ position: fixed; left:20px; right:20px; bottom:18px; z-index:9999; display:flex; gap:8px; align-items:flex-end; }}
.input-area textarea {{ width:100%; min-height:72px; max-height:250px; padding:10px; border-radius:8px; border:1px solid #ccc; resize:vertical; }}
.send-button {{ height:44px; padding:0 14px; border-radius:8px; border:none; background:#FF6F00; color:white; cursor:pointer; font-weight:600; }}
.feedback-buttons button {{ margin-right:6px; }}
.fixed-disclaimer {{ position:fixed; left:0; right:0; bottom:0; background:rgba(255,255,255,0.95); padding:8px; border-top:2px solid #FF6F00; text-align:center; font-size:12px; z-index:9997; }}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# -------------------------
# Initialize GROQ client
# -------------------------
GROQ_API_KEY = "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"
client = None
if Groq and GROQ_API_KEY:
    try:
        client = Groq(api_key=GROQ_API_KEY)
    except:
        client = None

# -------------------------
# Brand info
# -------------------------
brand_data = {
    "shingrix": {
        "display":"Shingrix",
        "segments":["R – Reach","A – Acquisition","C – Conversion","E – Engagement"],
        "personas":["Uncommitted Vaccinator","Reluctant Efficiency","Patient Influenced","Committed Vaccinator"],
        "barriers":["HCP does not consider HZ a risk","No time for discussion","Cost concerns","Not convinced of efficacy"],
        "specialties":["GP","Dermatologist","Geriatrician"],
        "references_path":".devcontainer/references/shingrix/",
        "sales_path":".devcontainer/SalesModule/shingrix/",
        "call_flow":["Prepare","Engage","Create Opportunities","Influence","Impact GSO","Post-call Analysis"]
    },
    "jemperli": {
        "display":"Jemperli",
        "segments":["Target Identification","Trial Adoption","Routine Use","Advocacy"],
        "personas":["Data-Driven Oncologist","Skeptical Specialist","Innovator Prescriber","Late Adopter"],
        "barriers":["Unfamiliar with immunotherapy","Safety concerns","Limited eligibility","Access/reimbursement issues"],
        "specialties":["Oncologist","Medical Oncologist"],
        "references_path":".devcontainer/references/jemperli/",
        "sales_path":".devcontainer/SalesModule/jemperli/",
        "call_flow":["COCO","Anchor","Engage","Close"]
    },
    "trelegy": {
        "display":"Trelegy",
        "segments":["Awareness","Diagnosis","Adoption","Adherence"],
        "personas":["Primary Care COPD Prescriber","Pulmonologist","Respiratory Nurse"],
        "barriers":["Formulary access","Inhaler technique","Side effect concerns","Cost/coverage"],
        "specialties":["GP","Pulmonologist","Respiratory Specialist"],
        "references_path":".devcontainer/references/trelegy/",
        "sales_path":".devcontainer/SalesModule/trelegy/",
        "call_flow":["Prepare","Engage","Demonstrate","Address Access","Close"]
    }
}

# -------------------------
# Helper functions
# -------------------------
def read_file_text(path):
    if not os.path.exists(path): return ""
    try:
        if path.lower().endswith(".pdf") and PdfReader:
            reader = PdfReader(path)
            return "".join([p.extract_text() or "" for p in reader.pages])
        else:
            with open(path,"r",encoding="utf-8",errors="ignore") as fh:
                return fh.read()
    except:
        return ""


def build_corpus_for_folders(folders, chunk_size_sentences=3):
    chunks, metas = [], []
    for folder in folders:
        if not folder or not os.path.exists(folder): continue
        files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".pdf",".txt"))]
        for fname in files:
            p = os.path.join(folder,fname)
            text = read_file_text(p)
            if not text: continue
            sents = re.split(r'(?<=[\.!\?])\s+',text)
            for i in range(0,max(1,len(sents)),chunk_size_sentences):
                chunk = " ".join(sents[i:i+chunk_size_sentences]).strip()
                if chunk:
                    chunks.append(chunk)
                    metas.append({"filename":fname,"folder":folder,"start":i})
    return chunks, metas


def local_search_snippets(query,chunks,metas,top_n=5):
    if not chunks: return []
    if SKLEARN_AVAILABLE:
        try:
            vectorizer = TfidfVectorizer(stop_words="english").fit(chunks+[query])
            chunk_vecs = vectorizer.transform(chunks)
            q_vec = vectorizer.transform([query])
            sims = linear_kernel(q_vec,chunk_vecs).flatten()
            top_idxs = sims.argsort()[::-1][:top_n]
            results = []
            for idx in top_idxs:
                if sims[idx]<=0: continue
                results.append({"score":float(sims[idx]),"text":chunks[idx],"meta":metas[idx]})
            return results
        except:
            pass
    out = []
    q=query.lower()
    for i,c in enumerate(chunks):
        if q in c.lower():
            out.append({"score":1.0,"text":c,"meta":metas[i]})
            if len(out)>=top_n: break
    return out


def simple_summary(text, bullets=6):
    if not text: return ""
    sents = re.split(r'(?<=[\.!\?])\s+',text)
    selected = [s.strip() for s in sents if s.strip()][:bullets]
    return "\n".join(["- "+s for s in selected])


def model_summarize(text, bullets=6):
    if not text: return ""
    if client:
        try:
            prompt=f"Summarize into {bullets} concise bullet points:\n\n{text[:12000]}"
            resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
                messages=[{"role":"user","content":prompt}],
                temperature=0.2)
            return resp.choices[0].message.content
        except:
            return simple_summary(text, bullets)
    else:
        return simple_summary(text, bullets)

# smarter TTS generator that returns base64 mp3; inserts gentle pauses between APACT stages
def generate_audio_base64(text):
    if not text:
        return ""
    # Preprocess text to add spoken pauses - insert short ellipses line breaks between sections
    tts_text = re.sub(r'\n\s*\n', ' ... ', text)
    tts_text = tts_text.replace("\n", " ")
    # Prefer ElevenLabs if available (best quality), otherwise gTTS fallback
    if ELEVENLABS_AVAILABLE:
        try:
            elevenlabs.api_key = st.secrets.get("ELEVENLABS_API_KEY", None) or os.environ.get("ELEVENLABS_API_KEY")
            audio_iter = elevenlabs.generate(text=tts_text, voice="alloy", model="eleven_multilingual_v1", stream=True)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            with open(tmp.name, "wb") as f:
                for chunk in audio_iter:
                    f.write(chunk)
            with open(tmp.name, "rb") as fh:
                return base64.b64encode(fh.read()).decode()
        except Exception:
            pass
    # gTTS fallback
    if gTTS:
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            gTTS(text=tts_text, lang="en", slow=False).save(tmp.name)
            with open(tmp.name, "rb") as fh:
                return base64.b64encode(fh.read()).decode()
        except Exception:
            pass
    return ""

# -------------------------
# Sidebar filters
# -------------------------
with st.sidebar.expander("Filters & Options", expanded=True):
    brand_options = list(brand_data.keys())
    sel_brand = st.selectbox("Brand", brand_options, index=brand_options.index(st.session_state.selected_brand))
    st.session_state.selected_brand = sel_brand
    bconf = brand_data[sel_brand]
    segment = st.selectbox("Segment", bconf["segments"])
    persona = st.selectbox("HCP Persona", bconf["personas"])
    barrier = st.multiselect("Doctor Barrier", bconf["barriers"])
    specialty = st.selectbox("Specialty", bconf["specialties"])
    objective = st.selectbox("Objective", ["Awareness","Adoption","Retention"])
    st.session_state.temperature = st.slider("Temperature",0.0,1.0,st.session_state.temperature,0.05)
    st.session_state.search_mode = st.selectbox("Search mode", ["deep","shallow"])
    st.session_state.language = st.radio("Language", ["English","Arabic"])
    if st.button("🗑️ Clear Chat"): st.session_state.chat_history=[]

with st.sidebar.expander("🌐 Add External Reference URLs (one per line)", expanded=False):
    external_urls = st.text_area("Enter URLs (one per line)").splitlines()

with st.sidebar.expander("📄 Export Options", expanded=False):
    export_format = st.radio("Choose Export Format", ["TXT","DOCX"], horizontal=True)

# -------------------------
# Title box
# -------------------------
st.markdown(f"""
<div class="title-box">
<img src="{GSK_LOGO_RAW}" class="left-logo">
<h2>💡 AI Sales Call Assistant — {brand_data[sel_brand]['display']}</h2>
<img src="{AI_LOGO_RAW}" class="right-logo">
</div>
""", unsafe_allow_html=True)

# -------------------------
# Load references and sales summaries
# -------------------------
refs_folder = bconf["references_path"]
sales_folder = bconf["sales_path"]
combined_refs = ""
if os.path.exists(refs_folder):
    for f in sorted(os.listdir(refs_folder)):
        if f.lower().endswith((".pdf",".txt")):
            combined_refs += read_file_text(os.path.join(refs_folder,f)) + "\n"
combined_sales = ""
if os.path.exists(sales_folder):
    for f in sorted(os.listdir(sales_folder)):
        if f.lower().endswith((".pdf",".txt")):
            combined_sales += read_file_text(os.path.join(sales_folder,f)) + "\n"
if not st.session_state.medical_summary and combined_refs.strip():
    st.session_state.medical_summary = model_summarize(combined_refs, bullets=6)
if not st.session_state.sales_summary and combined_sales.strip():
    st.session_state.sales_summary = model_summarize(combined_sales, bullets=6)

with st.expander("📚 Medical References Summary", expanded=False):
    st.markdown(st.session_state.medical_summary or "No medical summary available.")
with st.expander("💼 Sales Module Summary", expanded=False):
    st.markdown(st.session_state.sales_summary or "No sales summary available.")

# -------------------------
# PDF Upload and summarize
# -------------------------
uploaded_file = st.file_uploader("Upload PDF for summary", type=["pdf"])
if uploaded_file and PdfReader:
    reader = PdfReader(uploaded_file)
    pdf_text = "".join([p.extract_text() or "" for p in reader.pages])
    st.session_state.uploaded_pdf_text = pdf_text
    st.session_state.pdf_summary = model_summarize(pdf_text, bullets=6)
    st.success("PDF summarized successfully!")
if st.session_state.pdf_summary:
    with st.expander("📄 Uploaded PDF Summary", expanded=False):
        st.markdown(st.session_state.pdf_summary)

# -------------------------
# Build corpus
# -------------------------
corpus_folders = [refs_folder, sales_folder]
chunks, chunk_meta = build_corpus_for_folders(corpus_folders, chunk_size_sentences=3)

# -------------------------
# Prompt suggestions (collapsible)
# -------------------------
def make_suggestions(brand_key, persona_val, barriers_list, segment_val, specialty_val, objective_val):
    s=[]
    s.append(f"Generate call flow for {persona_val} focused on {objective_val}.")
    if barriers_list: s.append(f"Handle objection: {', '.join(barriers_list[:2])} for {persona_val}.")
    else: s.append(f"Identify common objections for {persona_val}.")
    s.append(f"Summarize HCP persona insights for {persona_val}.")
    s.append(f"Key talking points for {brand_data[brand_key]['display']} in {segment_val}.")
    s.append(f"Draft a short adoption message for {brand_data[brand_key]['display']} to a {specialty_val}.")
    return s

# helper to clean noisy filename citations (remove IMPACT Full KIT lines)
def build_clean_citation(snippets):
    noisy_pattern = "impact full kit 2023 - shingrix selling model -  short version.pdf"
    parts = []
    for s in snippets:
        fname = s['meta'].get('filename','')
        fname_l = fname.lower()
        if noisy_pattern in fname_l:
            continue
        parts.append(f"{fname} ({s['score']:.2f})")
    # Deduplicate & join
    parts = list(dict.fromkeys(parts))
    return "\n".join(parts)

# -------------------------
# APACT response builder + interactive feedback + voice generation
# -------------------------
def add_ai_response(prompt, follow_up=False, context_previous=None):
    """
    prompt: user prompt or internal instruction
    follow_up: when True, produce a follow-up clarifying question (for 'dislike' or 'need more')
    context_previous: the previous assistant content to base follow_up on (string)
    """
    snippets = local_search_snippets(prompt, chunks, chunk_meta, top_n=6)
    citation = build_clean_citation(snippets)

    # Build a clean, organized APACT response with examples and multiple probes
    out_lines = []
    # Humanized opener variations
    opener = "Thanks — I hear you. Let's tackle this together." if not follow_up else "Thanks for the feedback — I want to make this more useful."
    out_lines.append(f"*{opener}*\n")

    # Expanded opening examples
    out_lines.append("**Opening lines you can use:**")
    out_lines.append("- 'I appreciate you bringing this up — it's an important point that often affects patient decisions.'")
    out_lines.append("- 'That's a fair question. Let me walk you through what we've seen in practice.'")
    out_lines.append("")

    if not follow_up:
        # Acknowledge
        out_lines.append("**🟢 Acknowledge**")
        out_lines.append("I understand the concern you've raised and why it matters for patient care and clinic workflow. Example: 'I know time is tight — here's a 60-second way to explain benefit.'\n")

        # Probe (offer both open and closed questions with examples)
        out_lines.append("**🔵 Probe — sample questions (use as-is or adapt)**")
        out_lines.append("- Open: 'Can you tell me more about which patients you're most worried about?' — (Example: 'Patients over 80 or immunocompromised?')")
        out_lines.append("- Closed: 'Is your main worry safety, efficacy, or reimbursement? (Reply with safety/efficacy/reimbursement)'")
        out_lines.append("- Diagnostic: 'How often do you see eligible patients per week?' — (Helps prioritize the call strategy)")
        out_lines.append("")

        # Actions - merge best snippets per call flow with concise humanized bullets and short examples
        out_lines.append("**🟣 Actions — practical steps to use in the next HCP call (with example phrasing)**")
        reply_style = st.session_state.get('reply_style','balanced')

        for step in bconf.get("call_flow", []):
            # find snippets that mention the step or are relevant
            relevant = []
            for s in snippets:
                text = s.get("text","")
                if step.lower() in text.lower() or any(word.lower() in text.lower() for word in [persona.lower(), specialty.lower(), objective.lower()]):
                    relevant.append((s["score"], text))
            relevant.sort(key=lambda x: x[0], reverse=True)

            if relevant:
                out_lines.append(f"**{step}:**")
                for rscore, rtext in relevant[:2]:
                    # create short bullet + example phrasing depending on reply_style
                    short = re.split(r'(?<=[\.!\?])\s+', rtext.strip())[0][:220]
                    if reply_style == 'short_script':
                        out_lines.append(f"- Quick line: '{short}.' (Use within 15s)")
                    elif reply_style == 'data':
                        out_lines.append(f"- Data point: {short} — follow with 'In X study, Y% saw...' (add local stat if available)")
                    elif reply_style == 'conversational':
                        out_lines.append(f"- Example dialogue: I: \"{short}.\" HCP: \"[response]\" — then add patient story or anecdote.")
            else:  # balanced
                        out_lines.append(f"- {short} — Example: In practice, you can say: \"{short}...\"")

            else:
                out_lines.append(f"**{step}:** - Refer to the sales module for step-specific lines and examples.")
        out_lines.append("")

        # Confirm
        out_lines.append("**🟠 Confirm**")
        out_lines.append("- Does this direction address the HCP's main barrier in your next visit? (Yes / No)")

        # Transition
        out_lines.append("**🟡 Transition**")
        out_lines.append("- If yes, I can prepare a short script and patient profiling checklist for that next step. If no, tell me which part to deepen.\n")

        out_lines.append("*Reference note: suggestions were generated from internal sales kits and uploaded documents (auto-summarized).*)")
    else:
        # follow_up True: richer clarifying open and closed questions + examples
        out_lines.append("**Follow-up — tell me more so I can improve the answer**")
        if context_previous:
            prev_short = re.split(r'(?<=[\.!\?])\s+', context_previous.strip())
            prev_snippet = prev_short[0] if prev_short else context_previous.strip()
            out_lines.append(f"- About the previous suggestion: \"{prev_snippet[:140]}...\" — which part felt off? (unclear / not practical / too technical / other)")
        out_lines.append("- Quick choices: (A) unclear, (B) not enough practical steps, (C) too technical, (D) other")
        out_lines.append("- Preferred output: (1) Short script, (2) Data-backed bullets, (3) Conversational examples")
        out_lines.append("- Example: Reply '2' if you want me to add study numbers, '3' for role-play examples.")

    ai_text = "\n".join(out_lines)

    # Add assistant entry with audio placeholder; audio generated and stored in entry for playback
    audio_b64 = generate_audio_base64(ai_text)
    entry = {"role":"assistant","content":ai_text, "citation": citation, "audio_b64": audio_b64}
    st.session_state.chat_history.append(entry)

# -------------------------
# Chat container and input
# -------------------------
chat_container = st.container()

with st.expander("💡 Prompt Suggestions (Click to Expand)", expanded=False):
    suggs = make_suggestions(sel_brand, persona, barrier, segment, specialty, objective)
    sugg_cols = st.columns(3)
    for i, s in enumerate(suggs):
        col = sugg_cols[i % 3]
        if col.button(s, key=f"sugg_{i}"):
            st.session_state.main_input = s

with st.form("main_input_form", clear_on_submit=True):
    user_input = st.text_area("Ask something:", st.session_state.main_input, height=96)
    submitted = st.form_submit_button("Send")
    if submitted and user_input.strip():
        st.session_state.chat_history.append({"role":"user","content":user_input.strip()})
        # if the user replies with a preference code while awaiting preference, capture it
        if st.session_state.get('awaiting_style_pref'):
            # map common replies
            pref = user_input.strip().lower()
            if '1' in pref or 'script' in pref or 'short' in pref:
                st.session_state.reply_style = 'short_script'
                st.session_state.awaiting_style_pref = False
                st.session_state.chat_history.append({"role":"assistant","content":"Got it — I'll favor short scripts going forward.", "citation":"", "audio_b64": generate_audio_base64("Got it — I'll favor short scripts going forward.")})
            elif '2' in pref or 'data' in pref:
                st.session_state.reply_style = 'data'
                st.session_state.awaiting_style_pref = False
                st.session_state.chat_history.append({"role":"assistant","content":"Got it — I'll prioritize data-backed bullets going forward.", "citation":"", "audio_b64": generate_audio_base64("Got it — I'll prioritize data-backed bullets going forward.")})
            elif '3' in pref or 'convers' in pref:
                st.session_state.reply_style = 'conversational'
                st.session_state.awaiting_style_pref = False
                st.session_state.chat_history.append({"role":"assistant","content":"Great — I'll include more conversational examples and role-plays.", "citation":"", "audio_b64": generate_audio_base64("Great — I'll include more conversational examples and role-plays.")})
            else:
                # treat as normal query
                add_ai_response(user_input.strip(), follow_up=False)
        else:
            add_ai_response(user_input.strip(), follow_up=False)
        st.session_state.main_input = ""

# render preference buttons if awaiting
if st.session_state.get('awaiting_style_pref'):
    st.markdown("**Quick preference — choose a reply style that I should favor going forward:**")
    p1, p2, p3 = st.columns(3)
    if p1.button("Short scripts (1)"):
        st.session_state.reply_style = 'short_script'
        st.session_state.awaiting_style_pref = False
        st.session_state.chat_history.append({"role":"assistant","content":"Got it — I'll favor short scripts going forward.", "citation":"", "audio_b64": generate_audio_base64("Got it — I'll favor short scripts going forward.")})
    if p2.button("Data bullets (2)"):
        st.session_state.reply_style = 'data'
        st.session_state.awaiting_style_pref = False
        st.session_state.chat_history.append({"role":"assistant","content":"Got it — I'll prioritize data-backed bullets going forward.", "citation":"", "audio_b64": generate_audio_base64("Got it — I'll prioritize data-backed bullets going forward.")})
    if p3.button("Conversational (3)"):
        st.session_state.reply_style = 'conversational'
        st.session_state.awaiting_style_pref = False
        st.session_state.chat_history.append({"role":"assistant","content":"Great — I'll include more conversational examples and role-plays.", "citation":"", "audio_b64": generate_audio_base64("Great — I'll include more conversational examples and role-plays.")})

# -------------------------
# Display chat with audio and interactive feedback
# -------------------------
with chat_container:
    for idx,entry in enumerate(st.session_state.chat_history):
        if entry["role"]=="user":
            st.markdown(f'<div class="chat-bubble-user">{escape(entry["content"])}</div>',unsafe_allow_html=True)
        else:
            # show assistant text (render markdown-like content safely)
            st.markdown(f'<div class="chat-bubble-ai">{escape(entry["content"]).replace("\\n","<br>")}</div>',unsafe_allow_html=True)
            if entry.get("citation"):
                # short, humanized reference note (not raw filenames)
                ref_note = "References checked from internal sales kit and uploaded documents."
                st.markdown(f'<div class="citation-box">{escape(ref_note)}</div>',unsafe_allow_html=True)
            # Play audio if available
            audio_b64 = entry.get("audio_b64","")
            if audio_b64:
                try:
                    st.audio(io.BytesIO(base64.b64decode(audio_b64)), format="audio/mp3")
                except Exception:
                    pass

            # Interactive feedback buttons
            fb_cols = st.columns(3)
            entry_key = f"fb_{idx}"
            if entry_key not in st.session_state.feedback:
                if fb_cols[0].button("👍 Like", key=f"like_{idx}"):
                    st.session_state.feedback[entry_key] = "like"
                    # ask quick preference for future replies
                    st.session_state.awaiting_style_pref = True
                    st.session_state.chat_history.append({"role":"assistant","content":"Great — glad that helped! Quick preference: do you prefer (1) short scripts, (2) data bullets, or (3) conversational examples? Reply with 1/2/3 or click the button below.", "citation":"", "audio_b64": generate_audio_base64("Great — glad that helped! Quick preference: do you prefer short scripts, data bullets, or conversational examples? Reply with 1, 2, or 3.")})
                if fb_cols[1].button("👎 Dislike", key=f"dislike_{idx}"):
                    st.session_state.feedback[entry_key] = "dislike"
                    prev_assistant_text = entry.get("content","")
                    add_ai_response("User indicated dislike — follow up", follow_up=True, context_previous=prev_assistant_text)
                if fb_cols[2].button("ℹ️ Need More", key=f"needmore_{idx}"):
                    st.session_state.feedback[entry_key] = "need_more"
                    prev_assistant_text = entry.get("content","")
                    add_ai_response("User requested more detail — expand previous answer", follow_up=True, context_previous=prev_assistant_text)

# -------------------------
# Footer disclaimer
# -------------------------
st.markdown("""
<div class="fixed-disclaimer">
💡 This tool is for internal sales support purposes only. All medical info should be verified from official sources. 
</div>
""",unsafe_allow_html=True)
