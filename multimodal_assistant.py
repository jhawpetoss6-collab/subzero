import os
import sys
import json
from pathlib import Path

# Multi-Modal Learning Assistant
# Processes images, videos, audio, PDFs

print("""\nâ•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘   SUBZERO MULTI-MODAL LEARNING ASSISTANT           â•‘
â•‘   Learn from Images, Videos, Audio, PDFs           â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•\n""")

def check_dependencies():
    """Check what tools are available"""
    tools = {}
    
    # Check for Whisper (audio)
    try:
        import whisper
        tools["whisper"] = True
        print("âœ“ Whisper (audio transcription) - INSTALLED")
    except:
        tools["whisper"] = False
        print("âœ— Whisper - NOT INSTALLED (pip install openai-whisper)")
    
    # Check for OpenCV (video)
    try:
        import cv2
        tools["opencv"] = True
        print("âœ“ OpenCV (video processing) - INSTALLED")
    except:
        tools["opencv"] = False
        print("âœ— OpenCV - NOT INSTALLED (pip install opencv-python)")
    
    # Check for Tesseract (OCR)
    try:
        import pytesseract
        tools["tesseract"] = True
        print("âœ“ Tesseract OCR (image text) - INSTALLED")
    except:
        tools["tesseract"] = False
        print("âœ— Tesseract - NOT INSTALLED (pip install pytesseract)")
    
    # Check for PDF
    try:
        import PyPDF2
        tools["pdf"] = True
        print("âœ“ PyPDF2 (PDF extraction) - INSTALLED")
    except:
        tools["pdf"] = False
        print("âœ— PyPDF2 - NOT INSTALLED (pip install PyPDF2)")
    
    # Check for yt-dlp
    try:
        import yt_dlp
        tools["ytdlp"] = True
        print("âœ“ yt-dlp (video download) - INSTALLED")
    except:
        tools["ytdlp"] = False
        print("âœ— yt-dlp - NOT INSTALLED (pip install yt-dlp)")
    
    print()
    return tools

def process_image(file_path, tools):
    """Extract text and understanding from image"""
    print(f"\n[IMAGE] Processing: {file_path}")
    
    if not tools["tesseract"]:
        print("  âš  Tesseract not available. Install: pip install pytesseract")
        return None
    
    try:
        import pytesseract
        from PIL import Image
        
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img)
        
        if text.strip():
            print(f"\n  ðŸ“ Extracted text ({len(text)} chars):")
            print("  " + "-" * 50)
            print("  " + text[:500].replace("\n", "\n  "))
            if len(text) > 500:
                print("  ... (truncated)")
            print("  " + "-" * 50)
            return {"type": "image", "text": text}
        else:
            print("  â„¹ No text found (might be a photo/diagram)")
            return {"type": "image", "text": "[Image with no readable text]"}
    except Exception as e:
        print(f"  âœ— Error: {e}")
        return None

def process_audio(file_path, tools):
    """Transcribe audio file"""
    print(f"\n[AUDIO] Processing: {file_path}")
    
    if not tools["whisper"]:
        print("  âš  Whisper not available. Install: pip install openai-whisper")
        return None
    
    try:
        import whisper
        
        print("  ðŸŽ§ Loading Whisper model...")
        model = whisper.load_model("base")
        
        print("  ðŸŽ¤ Transcribing (this may take a moment)...")
        result = model.transcribe(file_path)
        
        transcript = result["text"]
        print(f"\n  ðŸ“ Transcript ({len(transcript)} chars):")
        print("  " + "-" * 50)
        print("  " + transcript[:500])
        if len(transcript) > 500:
            print("  ... (truncated)")
        print("  " + "-" * 50)
        
        return {"type": "audio", "text": transcript}
    except Exception as e:
        print(f"  âœ— Error: {e}")
        return None

def process_video(file_path, tools):
    """Extract frames and audio from video"""
    print(f"\n[VIDEO] Processing: {file_path}")
    
    if not tools["opencv"]:
        print("  âš  OpenCV not available. Install: pip install opencv-python")
        return None
    
    try:
        import cv2
        import tempfile
        
        video = cv2.VideoCapture(file_path)
        fps = video.get(cv2.CAP_PROP_FPS)
        total_frames = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        print(f"  ðŸ“¹ Video info: {duration:.1f}s, {fps:.1f} FPS, {total_frames} frames")
        
        # Extract key frames (1 per second)
        frames_extracted = 0
        all_text = []
        
        print("  ðŸŽ¬ Extracting key frames...")
        frame_interval = int(fps) if fps > 0 else 30
        
        while True:
            ret, frame = video.read()
            if not ret:
                break
            
            frame_num = int(video.get(cv2.CAP_PROP_POS_FRAMES))
            if frame_num % frame_interval == 0:
                frames_extracted += 1
                
                # Try OCR on frame
                if tools["tesseract"]:
                    import pytesseract
                    from PIL import Image
                    import numpy as np
                    
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(frame_rgb)
                    text = pytesseract.image_to_string(pil_img)
                    
                    if text.strip():
                        all_text.append(f"[Frame {frame_num}] {text.strip()}")
        
        video.release()
        
        print(f"  âœ“ Extracted {frames_extracted} frames")
        
        if all_text:
            combined_text = "\n\n".join(all_text)
            print(f"\n  ðŸ“ Found text in {len(all_text)} frames:")
            print("  " + "-" * 50)
            print("  " + combined_text[:500].replace("\n", "\n  "))
            if len(combined_text) > 500:
                print("  ... (truncated)")
            print("  " + "-" * 50)
            return {"type": "video", "text": combined_text}
        else:
            print("  â„¹ No text found in video frames")
            return {"type": "video", "text": "[Video with no readable text]"}
    
    except Exception as e:
        print(f"  âœ— Error: {e}")
        return None

def process_pdf(file_path, tools):
    """Extract text from PDF"""
    print(f"\n[PDF] Processing: {file_path}")
    
    if not tools["pdf"]:
        print("  âš  PyPDF2 not available. Install: pip install PyPDF2")
        return None
    
    try:
        import PyPDF2
        
        with open(file_path, "rb") as f:
            pdf = PyPDF2.PdfReader(f)
            num_pages = len(pdf.pages)
            
            print(f"  ðŸ“„ PDF has {num_pages} pages")
            
            all_text = []
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text.strip():
                    all_text.append(f"[Page {i+1}] {text.strip()}")
            
            combined_text = "\n\n".join(all_text)
            print(f"\n  ðŸ“ Extracted text ({len(combined_text)} chars):")
            print("  " + "-" * 50)
            print("  " + combined_text[:500].replace("\n", "\n  "))
            if len(combined_text) > 500:
                print("  ... (truncated)")
            print("  " + "-" * 50)
            
            return {"type": "pdf", "text": combined_text}
    
    except Exception as e:
        print(f"  âœ— Error: {e}")
        return None

def send_to_ollama(content):
    """Send extracted content to Ollama for analysis"""
    print("\n[OLLAMA] Analyzing content with Qwen...")
    
    try:
        import subprocess
        
        prompt = f"""Analyze this content extracted from a {content['type']} file:

{content['text'][:2000]}

Provide:
1. Brief summary (2-3 sentences)
2. Key points or topics
3. Main takeaways
"""
        
        result = subprocess.run(
            ["ollama", "run", "qwen2.5:1.5b", prompt],
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        
        if result.returncode == 0:
            print("\n" + "=" * 60)
            print("AI ANALYSIS:")
            print("=" * 60)
            print(result.stdout)
            print("=" * 60)
        else:
            print(f"  âœ— Error running Ollama: {result.stderr}")
    
    except Exception as e:
        print(f"  âœ— Error: {e}")

def main():
    tools = check_dependencies()
    
    print("\nDrag and drop a file, or enter file path:")
    print("Supported: Images (.jpg, .png), Videos (.mp4, .avi), Audio (.mp3, .wav), PDFs (.pdf)")
    print("Or type 'install' for installation instructions\n")
    
    while True:
        user_input = input("File path (or 'quit'): ").strip().strip('"')  
        
        if user_input.lower() in ["quit", "exit", "q"]:
            break
        
        if user_input.lower() == "install":
            print("\nINSTALLATION INSTRUCTIONS:")
            print("=" * 60)
            print("pip install openai-whisper  # Audio transcription")
            print("pip install opencv-python   # Video processing")
            print("pip install pytesseract     # OCR for images/videos")
            print("pip install PyPDF2          # PDF extraction")
            print("pip install yt-dlp          # Download videos")
            print("pip install pillow          # Image processing")
            print("=" * 60)
            continue
        
        if not os.path.exists(user_input):
            print(f"âœ— File not found: {user_input}")
            continue
        
        file_path = Path(user_input)
        ext = file_path.suffix.lower()
        
        content = None
        
        # Detect file type and process
        if ext in [".jpg", ".jpeg", ".png", ".bmp", ".gif"]:
            content = process_image(file_path, tools)
        elif ext in [".mp3", ".wav", ".m4a", ".ogg"]:
            content = process_audio(file_path, tools)
        elif ext in [".mp4", ".avi", ".mov", ".mkv"]:
            content = process_video(file_path, tools)
        elif ext == ".pdf":
            content = process_pdf(file_path, tools)
        else:
            print(f"âœ— Unsupported file type: {ext}")
            continue
        
        # Send to Ollama for analysis
        if content:
            send_to_ollama(content)
        
        print("\n" + "=" * 60 + "\n")

if __name__ == "__main__":
    main()
