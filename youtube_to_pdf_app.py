import streamlit as st
import os
import cv2
import yt_dlp
import re
from PIL import Image
from youtube_transcript_api import YouTubeTranscriptApi
from fpdf import FPDF
import tempfile
from io import BytesIO

st.set_page_config(page_title="YouTube to PDF Pro", page_icon="🎥")
st.title("🎥 YouTube to PDF Converter (Pro)")

# Initialize session state for files
if 'pdf_files' not in st.session_state:
    st.session_state.pdf_files = []

# --- Sidebar ---
st.sidebar.header("Processing Settings")
interval = st.sidebar.number_input("Screenshot Interval (sec)", min_value=5, value=40)

# --- Functions ---
def get_video_id(url):
    match = re.search(r"(?:v=|youtu\.be\/|embed\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None

def create_transcript_pdf(video_id):
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        # Try to find any manual or generated transcript
        transcript = transcript_list.find_transcript(['en', 'ta', 'hi', 'es', 'fr'])
        data = transcript.fetch()
        text = " ".join([item['text'] for item in data]).replace('\n', ' ')
        
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        safe_text = text.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 10, txt=safe_text)
        return pdf.output(dest='S').encode('latin-1')
    except:
        return None

def capture_screenshots(url, interval_sec):
    temp_mp4 = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    try:
        ydl_opts = {'format': 'worstvideo[ext=mp4]', 'outtmpl': temp_mp4, 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        cap = cv2.VideoCapture(temp_mp4)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        frame_interval = int(fps * interval_sec)
        frames = []
        count = 0
        
        while True:
            success, image = cap.read()
            if not success: break
            if count % frame_interval == 0:
                img = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).convert("RGB")
                frames.append(img)
            count += 1
        cap.release()
        
        if frames:
            pdf_bytes = BytesIO()
            frames[0].save(pdf_bytes, format="PDF", save_all=True, append_images=frames[1:])
            return pdf_bytes.getvalue()
    finally:
        if os.path.exists(temp_mp4):
            os.remove(temp_mp4)
    return None

# --- UI ---
urls_input = st.text_area("Enter YouTube URLs (one per line):")
c1, c2 = st.columns(2)
do_trans = c1.checkbox("Extract Transcript", value=True)
do_screen = c2.checkbox("Extract Screenshots", value=True)

if st.button("Start Processing"):
    st.session_state.pdf_files = [] # Reset for new batch
    urls = [u.strip() for u in urls_input.split('\n') if u.strip()]
    
    for url in urls:
        v_id = get_video_id(url)
        if not v_id:
            st.error(f"Invalid URL: {url}")
            continue
            
        with st.spinner(f"Processing {url}..."):
            if do_trans:
                t_pdf = create_transcript_pdf(v_id)
                if t_pdf:
                    st.session_state.pdf_files.append({"name": f"Transcript_{v_id}.pdf", "data": t_pdf})
            
            if do_screen:
                s_pdf = capture_screenshots(url, interval)
                if s_pdf:
                    st.session_state.pdf_files.append({"name": f"Screenshots_{v_id}.pdf", "data": s_pdf})

# --- Persistent Download Section ---
if st.session_state.pdf_files:
    st.write("---")
    st.subheader("📥 Download Your Files")
    for file in st.session_state.pdf_files:
        st.download_button(label=f"Click to Download {file['name']}", 
                           data=file['data'], 
                           file_name=file['name'],
                           mime="application/pdf")
