import easyocr
import pyperclip
import numpy as np
import time
import hashlib
import psutil
import os
from PIL import ImageGrab, Image

# 1. Initialize Reader
print("Loading OCR models (Simplified Chinese + English)...")
startup_start = time.time()
reader = easyocr.Reader(['ch_sim', 'en'], gpu=False) # Forced False for your CPU setup
startup_time = time.time() - startup_start
print(f"⏱️  Startup Time: {startup_time:.2f} seconds\n")

def get_image_hash(img):
    """Creates a unique fingerprint for an image to detect changes."""
    return hashlib.md5(img.tobytes()).hexdigest()

def run_ocr_with_benchmarks(img):
    """Processes image and prints timing data."""
    img_np = np.array(img.convert('RGB'))
    
    process = psutil.Process(os.getpid())
    cpu_percent_start = process.cpu_percent(interval=0.1)
    
    start_time = time.time()
    
    # Run OCR
    # detail=0 returns just strings. 
    # paragraph=True can speed up CPU by grouping text blocks
    results = reader.readtext(img_np, detail=0, paragraph=True)
    
    end_time = time.time()
    duration = end_time - start_time
    cpu_percent_end = process.cpu_percent(interval=0.1)
    
    if results:
        text_out = "\n".join(results)
        pyperclip.copy(text_out)
        print(f"\n[{time.strftime('%H:%M:%S')}] OCR SUCCESS")
        print(f"⏱️  Time Taken: {duration:.2f} seconds")
        print(f"💾 CPU Usage: {(cpu_percent_start + cpu_percent_end) / 2:.1f}%")
        print(f"📄 Result:\n{text_out}")
        print("-" * 30)
    else:
        print(f"[{time.strftime('%H:%M:%S')}] No text detected ({duration:.2f}s)")

def monitor_clipboard():
    last_img_hash = None
    print("\n🚀 Monitoring started! Take a screenshot (Win+Shift+S) to begin.")
    
    try:
        while True:
            img = ImageGrab.grabclipboard()
            
            if isinstance(img, Image.Image):
                current_hash = get_image_hash(img)
                
                # Only process if it's a NEW image
                if current_hash != last_img_hash:
                    last_img_hash = current_hash
                    run_ocr_with_benchmarks(img)
            
            # Polling interval (0.5s is responsive but low CPU usage)
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        print("\nStopping monitor...")

if __name__ == "__main__":
    monitor_clipboard()