import streamlit as st
import io
import os
import tempfile
import yt_dlp
import cv2
from PIL import Image
from fpdf import FPDF
from youtube_transcript_api import YouTubeTranscriptApi

# Initialize Session State
if 'text_pdf' not in st.session_state:
    st.session_state['text_pdf'] = None
if 'image_pdf' not in st.session_state:
    st.session_state['image_pdf'] = None

# --- Sidebar: Processing Settings ---
with st.sidebar:
    st.title("Processing Settings")
    screenshot_interval = st.number_input(
        "Screenshot Interval (sec)",
        min_value=1,
        value=40,
        step=1
    )
    
    # Updated Quality Options
    quality_map = {
        "360p": 360,
        "480p": 480,
        "720p": 720,
        "1080p": 1080,
        "4k": 2160
    }
    quality_option = st.selectbox(
        "Video Quality",
        options=list(quality_map.keys()),
        index=2  # Defaults to 720p
    )

# --- Main Content ---
st.title("🎥 YouTube to PDF Converter (Pro)")

urls_input = st.text_area(
    "Enter YouTube URLs (one per line):",
    value="https://www.youtube.com/watch?v=4ZwZwE8wwyM",
    height=100
)

col1, col2 = st.columns(2)
with col1:
    extract_transcript = st.checkbox("Extract Transcript", value=False)
with col2:
    extract_screenshots = st.checkbox("Extract Screenshots", value=True)

if st.button("Start Processing"):
    urls = [url.strip() for url in urls_input.split('\n') if url.strip()]
    
    if not urls:
        st.error("Please enter at least one valid YouTube URL.")
    elif not extract_transcript and not extract_screenshots:
        st.error("Please select at least one extraction method.")
    else:
        status_container = st.empty()
        
        for url in urls:
            status_container.info(f"Processing: {url}")
            try:
                video_id = url.split("v=")[-1].split("&")[0]
                
                # 1. Transcript Logic
                if extract_transcript:
                    status_container.info("Fetching subtitle tracks...")
                    transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                    text_content = " ".join([t['text'] for t in transcript_list])
                    
                    pdf = FPDF()
                    pdf.add_page()
                    pdf.set_font("Arial", size=12)
                    clean_text = text_content.encode('latin-1', 'replace').decode('latin-1')
                    pdf.multi_cell(0, 10, clean_text)
                    
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_text:
                        pdf.output(tmp_text.name)
                        with open(tmp_text.name, "rb") as f:
                            st.session_state['text_pdf'] = io.BytesIO(f.read())
                        os.remove(tmp_text.name)

                # 2. Screenshot Logic
                if extract_screenshots:
                    status_container.info(f"Downloading video at {quality_option}...")
                    height = quality_map[quality_option]
                    
                    with tempfile.TemporaryDirectory() as temp_dir:
                        temp_video = os.path.join(temp_dir, "video.mp4")
                        
                        # Added 403 Forbidden Workarounds (extractor_args & headers)
                        ydl_opts = {
                            'format': f'bestvideo[height<={height}][ext=mp4]/best[height<={height}]/best',
                            'outtmpl': temp_video,
                            'quiet': True,
                            'noplaylist': True,
                            'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
                            'http_headers': {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                            }
                        }
                        
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            ydl.download([url])
                        
                        status_container.info(f"Capturing frames every {screenshot_interval}s...")
                        cap = cv2.VideoCapture(temp_video)
                        fps = cap.get(cv2.CAP_PROP_FPS)
                        
                        if fps == 0:
                            raise ValueError("Could not determine video FPS. Download may have failed.")
                            
                        frame_interval_frames = int(fps * screenshot_interval)
                        
                        frames = []
                        count = 0
                        while cap.isOpened():
                            ret, frame = cap.read()
                            if not ret:
                                break
                            if count % frame_interval_frames == 0:
                                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                                frames.append(img)
                            count += 1
                        cap.release()
                        
                        if frames:
                            pdf_bytes_io = io.BytesIO()
                            frames[0].save(
                                pdf_bytes_io, 
                                format='PDF', 
                                save_all=True, 
                                append_images=frames[1:]
                            )
                            st.session_state['image_pdf'] = io.BytesIO(pdf_bytes_io.getvalue())
                        else:
                            st.warning("No frames extracted.")

                status_container.success("Processing complete! PDFs are ready for download.")
                
            except Exception as e:
                status_container.error(f"Error processing {url}: {str(e)}")

# --- Persistent Download Buttons ---
if st.session_state['text_pdf'] or st.session_state['image_pdf']:
    st.markdown("---")
    dl_col1, dl_col2 = st.columns(2)
    
    with dl_col1:
        if st.session_state['text_pdf']:
            st.download_button(
                label="📄 Download Transcript PDF",
                data=st.session_state['text_pdf'].getvalue(),
                file_name="transcript.pdf",
                mime="application/pdf"
            )
            
    with dl_col2:
        if st.session_state['image_pdf']:
            st.download_button(
                label="🖼️ Download Visual Summary PDF",
                data=st.session_state['image_pdf'].getvalue(),
                file_name="visual_summary.pdf",
                mime="application/pdf"
            )
