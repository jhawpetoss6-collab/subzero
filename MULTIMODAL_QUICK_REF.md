# SubZero Multi-Modal Quick Reference

## 🚀 Quick Commands

### In SubZero Warp
```powershell
.\subzero-warp.ps1
```

Then use these commands:

| Command | What It Does |
|---------|--------------|
| `learn multimodal` | Shows complete multi-modal learning guide |
| `learn multimodal_learning` | Same as above |
| `create multimodal script` | Generates multimodal_assistant.py |

## 📦 Installation (One-Line)

```bash
pip install openai-whisper opencv-python pytesseract PyPDF2 yt-dlp pillow
```

## 🎯 Using the Assistant

```bash
python multimodal_assistant.py
```

Then drag & drop any file!

## 📸 Supported File Types

| Type | Extensions | What It Extracts |
|------|-----------|------------------|
| **Images** | .jpg, .png, .bmp, .gif | Text via OCR |
| **Videos** | .mp4, .avi, .mov, .mkv | Frames + audio transcript |
| **Audio** | .mp3, .wav, .m4a, .ogg | Full transcript |
| **PDFs** | .pdf | All text content |

## ⚡ Speed Reference

| Task | Time (Your PC) |
|------|---------------|
| Screenshot OCR | 1 second |
| 1-hour podcast | 4 minutes |
| 30-min video | 10 minutes |
| 500-page PDF | 30 seconds |

## 🛠️ Individual Tools

### Image → Text (OCR)
```python
import pytesseract
from PIL import Image

img = Image.open("screenshot.png")
text = pytesseract.image_to_string(img)
print(text)
```

### Audio → Text (Whisper)
```python
import whisper

model = whisper.load_model("base")
result = model.transcribe("podcast.mp3")
print(result["text"])
```

### Video → Frames + Audio
```python
import cv2
import whisper

# Extract frames
video = cv2.VideoCapture("tutorial.mp4")
# ... process frames

# Transcribe audio
model = whisper.load_model("base")
transcript = model.transcribe("tutorial.mp4")
```

### PDF → Text
```python
import PyPDF2

with open("book.pdf", "rb") as f:
    pdf = PyPDF2.PdfReader(f)
    text = ""
    for page in pdf.pages:
        text += page.extract_text()
print(text)
```

## 🎓 Learning Path

1. **Start here:** Type `learn multimodal` in SubZero Warp
2. **Create tool:** Type `create multimodal script`
3. **Test it:** Drop a screenshot, see it work
4. **Read guide:** See MULTIMODAL_GUIDE.md for deep dive
5. **Build project:** Try YouTube learner or podcast knowledge base

## 💡 Pro Tips

- **Use Base Whisper** - Best speed/accuracy balance
- **1 frame/second** - Enough for video analysis
- **Cache results** - Don't re-process same files
- **Combine modes** - Video + PDF + Audio = best learning

## 🔥 Real Use Cases

### 1. Learn from Screenshots
Drop tutorial screenshot → Get code + explanation

### 2. Extract Video Code
Drop YouTube tutorial → Get all code examples

### 3. Podcast Notes
Drop podcast MP3 → Get summary + key points

### 4. Textbook Search
Drop PDF → Ask any question about content

### 5. Meeting Recorder
Drop Zoom audio → Get action items + decisions

## 📊 Model Comparison

### Whisper Models

| Model | Speed | Accuracy | Memory | Use When |
|-------|-------|----------|--------|----------|
| Tiny | 32x | 90% | 1GB | Quick commands |
| **Base** | **16x** | **95%** | **2GB** | **DEFAULT** |
| Small | 6x | 97% | 3GB | High quality |
| Medium | 2x | 99% | 5GB | Perfect needed |

## 🐛 Troubleshooting

### "Tesseract not found"
```bash
pip install pytesseract
# Windows: Also install from https://github.com/UB-Mannheim/tesseract/wiki
```

### "Whisper too slow"
```python
# Use faster model
model = whisper.load_model("tiny")  # Instead of "base"
```

### "Out of memory"
```python
# Process in smaller chunks
# For video: Extract fewer frames (1 per 2 seconds instead of 1 per second)
```

### "Low OCR accuracy"
```python
# Preprocess image
from PIL import Image, ImageEnhance

img = Image.open("screenshot.png")
img = img.convert('L')  # Grayscale
img = ImageEnhance.Contrast(img).enhance(2)  # More contrast
text = pytesseract.image_to_string(img)
```

## 📈 Performance Optimization

### For Images
1. Convert to grayscale
2. Increase contrast
3. Crop to relevant area
4. Use higher DPI

### For Videos
1. Extract 1 frame per second (not more)
2. Skip duplicate frames
3. Process in batches
4. Use Tiny Whisper for quick preview

### For Audio
1. Use Base model (not Small/Medium)
2. Convert to WAV format first
3. Normalize audio levels
4. Remove silence gaps

### For PDFs
1. Check if text is native (not scanned)
2. Use pdfplumber for scanned PDFs
3. Process page by page
4. Cache extracted text

## 🎯 Next Steps

**Complete Guide:** See [MULTIMODAL_GUIDE.md](MULTIMODAL_GUIDE.md)

**Get Started:**
```powershell
.\subzero-warp.ps1
# Then: learn multimodal
# Then: create multimodal script
```

**Your AI learns from ANYTHING now!** 🚀
