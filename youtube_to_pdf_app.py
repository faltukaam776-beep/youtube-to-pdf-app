import streamlit as st
import os
import cv2
import yt_dlp
import re
from PIL import Image
from youtube_transcript_api import YouTubeTranscriptApi
from fpdf import FPDF
import tempfile
import zipfile
from io import BytesIO

# --- Page Config ---
st.set_page_config(page_title="YouTube to PDF Pro", page_icon="🎥")
st.title("🎥 YouTube to PDF Converter (Pro)")

# --- Sidebar / Settings ---
st.sidebar.header("Processing Settings")
interval = st.sidebar.number_input("Screenshot Interval (sec)", min_value=5, value=40)
quality = st.sidebar.selectbox("Video Quality", ["worst", "720p", "1080p"])

# --- Helper Functions ---
def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", str(name)).strip()

def get_video_id(url):
    match = re.search(r"(?:v=|youtu\.be\/|embed\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None

# --- Core Logic ---
def process_video(url, do_transcript, do_screenshot):
    video_id = get_video_id(url)
    if not video_id:
        return None, "Invalid URL"
    
    results = {}
    
    # 1. Transcript Logic
    if do_transcript:
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            data = transcript_list.find_transcript(['en', 'ta', 'hi']).fetch() # Common languages
            text = " ".join([item['text'] for item in data]).replace('\n', ' ')
            
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            safe_text = text.encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 10, txt=safe_text)
            
            pdf_output = BytesIO()
            pdf.output(dest='S').encode('latin-1') # Stream to memory
            results['transcript'] = pdf.output(dest='S').encode('latin-1')
        except Exception as e:
            st.error(f"Transcript Error: {e}")

    # 2. Screenshot Logic
    if do_screenshot:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            ydl_opts = {'format': 'worstvideo[ext=mp4]', 'outtmpl': tmp.name, 'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            cap = cv2.VideoCapture(tmp.name)
            fps = cap.get(cv2.CAP_PROP_FPS) or 30
            frame_interval = int(fps * interval)
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
            os.remove(tmp.name)
            
            if frames:
                pdf_bytes = BytesIO()
                frames[0].save(pdf_bytes, format="PDF", save_all=True, append_images=frames[1:])
                results['screenshots'] = pdf_bytes.getvalue()

    return results, None

# --- Main UI ---
urls_input = st.text_area("Enter YouTube URLs (one per line):", placeholder="https://www.youtube.com/watch?v=...")
col1, col2 = st.columns(2)
do_trans = col1.checkbox("Extract Transcript", value=True)
do_screen = col2.checkbox("Extract Screenshots", value=True)

if st.button("Start Processing"):
    urls = [u.strip() for u in urls_input.split('\n') if u.strip()]
    if not urls:
        st.warning("Please enter at least one URL.")
    else:
        for url in urls:
            with st.spinner(f"Processing: {url}"):
                data, err = process_video(url, do_trans, do_screen)
                if err:
                    st.error(err)
                else:
                    if 'transcript' in data:
                        st.download_button("Download Transcript PDF", data['transcript'], file_name="transcript.pdf")
                    if 'screenshots' in data:
                        st.download_button("Download Screenshots PDF", data['screenshots'], file_name="screenshots.pdf")
        st.success("All videos processed!")
