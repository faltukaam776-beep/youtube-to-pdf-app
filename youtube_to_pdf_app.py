import customtkinter as ctk
import threading
import os
import cv2
import yt_dlp
import re
from PIL import Image
from youtube_transcript_api import YouTubeTranscriptApi
from fpdf import FPDF
from tkinter import filedialog
import traceback

# --- App Configuration ---
ctk.set_appearance_mode("Dark")  
ctk.set_default_color_theme("blue") 

class YouTubePDFApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("YouTube to PDF Pro v2.2")
        self.geometry("650x700")
        self.resizable(False, False)

        self.output_dir = ctk.StringVar(value=os.getcwd())
        self.is_processing = False

        # --- UI Elements ---
        self.title_label = ctk.CTkLabel(self, text="YouTube to PDF Converter (Pro)", font=ctk.CTkFont(size=22, weight="bold"))
        self.title_label.pack(pady=(20, 10))

        self.input_label = ctk.CTkLabel(self, text="Enter YouTube URLs (One per line) OR a Playlist URL:")
        self.input_label.pack(anchor="w", padx=30)
        
        self.url_textbox = ctk.CTkTextbox(self, width=590, height=100)
        self.url_textbox.pack(pady=(5, 10), padx=30)

        self.playlist_var = ctk.BooleanVar(value=False)
        self.playlist_checkbox = ctk.CTkCheckBox(self, text="Link is a Playlist (Extract all videos)", variable=self.playlist_var)
        self.playlist_checkbox.pack(anchor="w", padx=30, pady=5)

        self.options_frame = ctk.CTkFrame(self)
        self.options_frame.pack(pady=10, padx=30, fill="x")

        self.transcript_var = ctk.BooleanVar(value=True)
        self.transcript_checkbox = ctk.CTkCheckBox(self.options_frame, text="Extract Transcript", variable=self.transcript_var)
        self.transcript_checkbox.grid(row=0, column=0, padx=20, pady=15, sticky="w")

        self.screenshot_var = ctk.BooleanVar(value=True)
        self.screenshot_checkbox = ctk.CTkCheckBox(self.options_frame, text="Extract Screenshots", variable=self.screenshot_var)
        self.screenshot_checkbox.grid(row=0, column=1, padx=20, pady=15, sticky="w")

        self.interval_label = ctk.CTkLabel(self.options_frame, text="Interval (sec):")
        self.interval_label.grid(row=1, column=0, padx=(20, 5), pady=10, sticky="e")

        self.interval_entry = ctk.CTkEntry(self.options_frame, width=60)
        self.interval_entry.insert(0, "40")
        self.interval_entry.grid(row=1, column=1, padx=(0, 20), pady=10, sticky="w")

        self.quality_label = ctk.CTkLabel(self.options_frame, text="Video Quality:")
        self.quality_label.grid(row=2, column=0, padx=(20, 5), pady=10, sticky="e")

        self.quality_menu = ctk.CTkOptionMenu(self.options_frame, values=["Lowest (Fast)", "Medium (720p)", "High (1080p)"])
        self.quality_menu.grid(row=2, column=1, padx=(0, 20), pady=10, sticky="w")

        self.dir_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.dir_frame.pack(pady=10, padx=30, fill="x")
        
        self.dir_button = ctk.CTkButton(self.dir_frame, text="Select Output Folder", command=self.select_directory, width=150)
        self.dir_button.pack(side="left", padx=(0, 10))
        
        self.dir_label = ctk.CTkLabel(self.dir_frame, textvariable=self.output_dir, text_color="gray", width=400, anchor="w")
        self.dir_label.pack(side="left")

        self.progress_bar = ctk.CTkProgressBar(self, width=590)
        self.progress_bar.pack(pady=(20, 5), padx=30)
        self.progress_bar.set(0)

        self.process_button = ctk.CTkButton(self, text="Start Processing", command=self.start_processing, height=40, font=ctk.CTkFont(weight="bold"))
        self.process_button.pack(pady=10)

        self.status_label = ctk.CTkLabel(self, text="Ready", text_color="gray")
        self.status_label.pack(pady=5)

    # --- Utility Functions ---
    def select_directory(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.output_dir.set(folder_selected)

    def safe_update_ui(self, status, color="white", progress=None):
        self.status_label.configure(text=status, text_color=color)
        if progress is not None:
            self.progress_bar.set(progress)

    def sanitize_filename(self, name):
        return re.sub(r'[\\/*?:"<>|]', "", str(name)).strip()

    def get_video_info(self, url):
        # Fallback Regex ID Extraction if yt-dlp metadata fails
        match = re.search(r"(?:v=|youtu\.be\/|embed\/)([0-9A-Za-z_-]{11})", url)
        fallback_id = match.group(1) if match else None

        ydl_opts = {'quiet': True, 'extract_flat': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info:
                    vid_id = info.get('id', fallback_id)
                    title = self.sanitize_filename(info.get('title', f"Video_{vid_id}"))
                    return vid_id, title
        except Exception:
            pass
            
        if fallback_id:
            return fallback_id, f"YouTube_Video_{fallback_id}"
        return None, "Unknown_Video"

    def get_playlist_urls(self, url):
        ydl_opts = {'extract_flat': True, 'quiet': True}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if 'entries' in info:
                    return [entry['url'] for entry in info['entries'] if entry.get('url')]
        except Exception:
            return []

    # --- Core Processing Functions ---
    def get_transcript_text(self, video_id):
        # Primary method
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            for transcript in transcript_list:
                try:
                    data = transcript.fetch()
                    full_text = " ".join([item['text'] for item in data])
                    return full_text.replace('\n', ' ')
                except Exception:
                    continue
        except Exception:
            pass

        # Fallback method
        try:
            data = YouTubeTranscriptApi.get_transcript(video_id)
            full_text = " ".join([item['text'] for item in data])
            return full_text.replace('\n', ' ')
        except Exception as e:
            return f"ERROR: {str(e)}"

    def create_text_pdf(self, text, output_path):
        try:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            safe_text = text.encode('latin-1', 'replace').decode('latin-1')
            pdf.multi_cell(0, 10, txt=safe_text)
            pdf.output(output_path)
            return True, "Success"
        except Exception as e:
            return False, f"PDF Gen Failed: {str(e)[:40]}"

    def process_screenshots(self, youtube_url, interval_seconds, output_path, quality_choice):
        quality_map = {
            "Lowest (Fast)": "worstvideo[ext=mp4]",
            "Medium (720p)": "bestvideo[height<=720][ext=mp4]",
            "High (1080p)": "bestvideo[ext=mp4]"
        }
        format_selector = quality_map.get(quality_choice, "worstvideo[ext=mp4]")
        temp_file = os.path.join(self.output_dir.get(), "temp_download.mp4")

        try:
            ydl_opts = {'format': format_selector, 'outtmpl': temp_file, 'quiet': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([youtube_url])
            
            if not os.path.exists(temp_file):
                return False, "Download blocked by YouTube."

            cap = cv2.VideoCapture(temp_file)
            fps = cap.get(cv2.CAP_PROP_FPS)
            if fps == 0 or fps != fps: 
                fps = 30.0 
                
            frame_interval = int(fps * interval_seconds)
            if frame_interval <= 0: frame_interval = 30 
            
            frames = []
            count = 0
            success, image = cap.read()
            
            while success:
                if count % frame_interval == 0:
                    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                    # Forcing conversion to explicit RGB fixes the 'JPEG' encoder crash
                    pil_img = Image.fromarray(image_rgb).convert("RGB")
                    frames.append(pil_img)
                success, image = cap.read()
                count += 1
                
            cap.release()
            
            if frames:
                # Forcing output format to PDF bypasses Pillow extension guessing errors
                frames[0].save(output_path, format="PDF", save_all=True, append_images=frames[1:])
                return True, "Success"
            return False, "Video valid, but no frames extracted."
            
        except Exception as e:
            err_str = str(e).replace("\n", " ")
            return False, err_str[:50]
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

    # --- Main Execution Thread ---
    def run_processing(self, urls, do_transcript, do_screenshot, interval, quality, is_playlist):
        target_urls = []
        
        self.safe_update_ui("Analyzing URLs...", "yellow", 0.05)
        for url in urls:
            if is_playlist:
                self.safe_update_ui(f"Extracting playlist: {url}...", "yellow")
                playlist_urls = self.get_playlist_urls(url)
                target_urls.extend(playlist_urls)
            else:
                target_urls.append(url)

        if not target_urls:
            self.safe_update_ui("Error: No valid URLs found to process.", "red", 0)
            self.process_button.configure(state="normal")
            self.is_processing = False
            return

        total_videos = len(target_urls)
        out_dir = self.output_dir.get()
        files_created = 0
        error_msgs = []

        for idx, url in enumerate(target_urls):
            base_progress = (idx / total_videos)
            self.safe_update_ui(f"Video {idx+1}/{total_videos}: Fetching info...", "yellow", base_progress)
            
            video_id, title = self.get_video_info(url)
            if not video_id:
                self.safe_update_ui(f"Video {idx+1}: Could not fetch video ID.", "red")
                error_msgs.append("Invalid YouTube ID")
                continue

            if do_transcript:
                self.safe_update_ui(f"Video {idx+1}/{total_videos}: Generating Transcript...", "yellow")
                transcript_text = self.get_transcript_text(video_id)
                
                if transcript_text and not transcript_text.startswith("ERROR:"):
                    pdf_path = os.path.join(out_dir, f"{title} - Transcript.pdf")
                    success, msg = self.create_text_pdf(transcript_text, pdf_path)
                    if success:
                        files_created += 1
                    else:
                        error_msgs.append(f"PDF Error: {msg}")
                        self.safe_update_ui(f"Transcript Error: {msg}", "red")
                else:
                    err = transcript_text.replace("ERROR: ", "")
                    error_msgs.append(f"Subtitles: {err[:30]}")
                    self.safe_update_ui(f"Transcript Error: {err[:50]}", "red")

            if do_screenshot:
                self.safe_update_ui(f"Video {idx+1}/{total_videos}: Downloading frames...", "yellow")
                pdf_path = os.path.join(out_dir, f"{title} - Screenshots.pdf")
                success, msg = self.process_screenshots(url, interval, pdf_path, quality)
                if success:
                    files_created += 1
                else:
                    error_msgs.append(f"Video Error: {msg}")
                    self.safe_update_ui(f"Screenshot Error: {msg}", "red")

        if files_created > 0:
            if error_msgs:
                self.safe_update_ui(f"Partial Success! {files_created} file(s) saved. Some errors occurred.", "orange", 1.0)
            else:
                self.safe_update_ui(f"Success! {files_created} file(s) saved to selected folder.", "green", 1.0)
        else:
            final_err = " | ".join(set(error_msgs))
            self.safe_update_ui(f"Failed. Errors: {final_err[:80]}", "red", 1.0)

        self.process_button.configure(state="normal")
        self.is_processing = False

    def start_processing(self):
        if self.is_processing: return

        raw_urls = self.url_textbox.get("1.0", "end-1c").strip().split('\n')
        urls = [u.strip() for u in raw_urls if u.strip()]
        
        if not urls:
            self.safe_update_ui("Error: Please enter at least one URL.", "red")
            return
            
        do_transcript = self.transcript_var.get()
        do_screenshot = self.screenshot_var.get()
        if not do_transcript and not do_screenshot:
            self.safe_update_ui("Error: Select at least one output option.", "red")
            return

        try:
            interval = int(self.interval_entry.get().strip())
        except ValueError:
            self.safe_update_ui("Error: Interval must be an integer.", "red")
            return

        quality = self.quality_menu.get()
        is_playlist = self.playlist_var.get()

        self.is_processing = True
        self.process_button.configure(state="disabled")
        self.progress_bar.set(0)
        
        thread = threading.Thread(
            target=self.run_processing, 
            args=(urls, do_transcript, do_screenshot, interval, quality, is_playlist)
        )
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    app = YouTubePDFApp()
    app.mainloop()
