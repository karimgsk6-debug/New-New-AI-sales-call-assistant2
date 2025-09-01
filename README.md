# --- Modern Collapsible README / Top Panel ---
st.markdown("""
<div style='max-width:800px; margin:auto; border-radius:12px; box-shadow:0 4px 12px rgba(0,0,0,0.1); overflow:hidden; transition:all 0.3s; background:white;'>
    <div style='display:flex; align-items:center; gap:15px; padding:10px; background:#FF8C00; cursor:pointer;' onclick="document.getElementById('readme_content').style.display = document.getElementById('readme_content').style.display === 'none' ? 'block' : 'none'; this.querySelector('span').innerText = this.querySelector('span').innerText === 'Show Info' ? 'Hide Info' : 'Show Info';">
        <img src='https://www.gsk.com/media/1234/gsk-logo.png' width='100' style='border-radius:5px'>
        <h3 style='margin:0; color:white;'>💊 AI Sales Call Assistant <span style='font-weight:normal; font-size:0.8em; margin-left:10px;'>Show Info</span></h3>
    </div>
    <div id='readme_content' style='display:none; padding:15px; background:#fff3e0; color:#333;'>
        <p style='margin:5px 0;'>Smart assistant to help GSK reps prepare for HCP interactions efficiently.</p>
        <p style='margin:5px 0; font-size:0.9em; color:red;'>⚠️ Always refer to approved GSK references and local guidelines when discussing with HCPs.</p>
    </div>
</div>

<style>
/* Card hover effect */
div[style*="box-shadow"] {
    transition: all 0.3s ease;
}
div[style*="box-shadow"]:hover {
    box-shadow:0 8px 20px rgba(0,0,0,0.15);
}
</style>
""", unsafe_allow_html=True)
