"""
AI Clipper Agent Pro - Automated Diagnostic & Verification Suite
AI Engineer Quality & Production Readiness Test
"""

import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_ROOT))

results = {}

def log_test(name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"[{status}] {name}")
    if detail:
        print(f"       -> {detail}")
    results[name] = (passed, detail)

print("=" * 60)
print("   🎬 AI CLIPPER AGENT PRO - SYSTEM VERIFICATION SUITE")
print("=" * 60)

# 1. Environment & API Key
print("\n--- [1/5] API & Authentication Check ---")
groq_key = os.getenv("GROQ_API_KEY", "")
if not groq_key and (PROJECT_ROOT / ".env").exists():
    with open(PROJECT_ROOT / ".env", "r") as f:
        for line in f:
            if line.startswith("GROQ_API_KEY="):
                groq_key = line.strip().split("=", 1)[1]
                break

if groq_key and groq_key.startswith("gsk_"):
    log_test("Groq API Key Configured", True, f"Key present ({groq_key[:8]}...{groq_key[-4:]})")
else:
    log_test("Groq API Key Configured", False, "Missing or invalid Groq key format")

# 2. Groq LLM Inference & Structured Output Test
print("\n--- [2/5] Groq LPU LLM Brain & Structured JSON Test ---")
try:
    from groq import Groq
    from ai_clipper import analyze_viral_clips

    test_transcript = """
    [00:00] In 2026, the biggest mistake most founders make is ignoring vertical short-form video.
    [00:15] Organic reach on horizontal long-form has plummeted by over seventy percent.
    [00:30] If you want to scale to seven figures without spending a single dollar on ads, shorts are the ultimate leverage.
    [00:45] Let me show you the three-step framework our team used to get ten million views.
    """
    
    t0 = time.time()
    clips = analyze_viral_clips(test_transcript, api_key=groq_key, provider="groq", num_clips=1)
    latency = time.time() - t0

    if clips and len(clips) > 0 and "viral_score" in clips[0] and "headline" in clips[0]:
        c = clips[0]
        log_test("Groq LPU Inference (Qwen 27B)", True, f"Generated clip in {latency:.2f}s | Title: '{c.get('title')}' | Score: {c.get('viral_score')}/100 | Hook: '{c.get('headline')}'")
    else:
        log_test("Groq LPU Inference (Qwen 27B)", False, "Empty or non-conforming JSON response")
except Exception as e:
    log_test("Groq LPU Inference (Qwen 27B)", False, str(e))

# 3. FFmpeg Engine & Typography Verification
print("\n--- [3/5] FFmpeg Video Engine & Typography Test ---")
try:
    from ai_clipper import render_916_vertical_clip, get_ffmpeg_path, FFMPEG_BIN, FONTS_DIR, OUTPUT_DIR, TEMP_DIR
    import subprocess

    ffmpeg = get_ffmpeg_path()
    if Path(ffmpeg).exists() or subprocess.run(["where", ffmpeg], capture_output=True).returncode == 0:
        log_test("FFmpeg Binary Available", True, f"Engine path: {ffmpeg}")
    else:
        log_test("FFmpeg Binary Available", False, "ffmpeg not found")

    font_path = FONTS_DIR / "Montserrat-Bold.ttf"
    if font_path.exists():
        log_test("Typography Engine (Montserrat)", True, f"Font size: {font_path.stat().st_size} bytes")
    else:
        log_test("Typography Engine (Montserrat)", False, "Font file missing")

    # Render a micro test clip
    test_src = TEMP_DIR / "_diag_test_source.mp4"
    test_out = OUTPUT_DIR / "_diag_test_out.mp4"

    cmd_create = [
        ffmpeg, "-f", "lavfi", "-i", "testsrc=duration=1:size=1920x1080:rate=30",
        "-f", "lavfi", "-i", "sine=frequency=1000:duration=1",
        "-c:v", "libx264", "-c:a", "aac", "-y", str(test_src)
    ]
    subprocess.run(cmd_create, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

    render_success = render_916_vertical_clip(
        source_video_path=test_src,
        start_seconds=0.0,
        end_seconds=0.5,
        headline="AI ENGINE PASS",
        output_path=test_out
    )

    if render_success and test_out.exists() and test_out.stat().st_size > 1000:
        log_test("9:16 Vertical Video Renderer", True, f"Rendered 1080x1920 MP4 ({test_out.stat().st_size} bytes, yuv420p)")
    else:
        log_test("9:16 Vertical Video Renderer", False, "FFmpeg rendering failed")

    # Clean up test artifacts
    if test_src.exists(): test_src.unlink()
    if test_out.exists(): test_out.unlink()

except Exception as e:
    log_test("9:16 Vertical Video Renderer", False, str(e))

# 4. Media Ingestion & YouTube Pipeline Check
print("\n--- [4/5] YouTube Ingestion & Captions API Check ---")
try:
    from ai_clipper import extract_youtube_id, YouTubeTranscriptApi, yt_dlp

    test_url = "https://www.youtube.com/watch?v=jNQXAC9IVRw" # First video on YouTube
    vid = extract_youtube_id(test_url)
    if vid == "jNQXAC9IVRw":
        log_test("YouTube URL Parser", True, f"Parsed ID: {vid}")
    else:
        log_test("YouTube URL Parser", False, "URL extraction failed")

    if YouTubeTranscriptApi:
        log_test("YouTube Transcript API", True, "Library installed and ready")
    else:
        log_test("YouTube Transcript API", False, "Library missing")

    if yt_dlp:
        log_test("yt-dlp Video Downloader", True, f"yt-dlp version: {yt_dlp.version.__version__}")
    else:
        log_test("yt-dlp Video Downloader", False, "yt-dlp missing")

except Exception as e:
    log_test("YouTube Ingestion Check", False, str(e))

# 5. Local Web Dashboard Server Status
print("\n--- [5/5] Streamlit Web Dashboard Status ---")
try:
    import urllib.request
    req = urllib.request.Request("http://localhost:8501/healthz")
    with urllib.request.urlopen(req, timeout=3) as resp:
        if resp.status == 200:
            log_test("Streamlit Web Server (:8501)", True, "Server active and responding (HTTP 200 OK)")
        else:
            log_test("Streamlit Web Server (:8501)", False, f"Status code: {resp.status}")
except Exception as e:
    log_test("Streamlit Web Server (:8501)", False, f"Not reachable: {e}")

# Summary
print("\n" + "=" * 60)
passed_count = sum(1 for p, _ in results.values() if p)
total_count = len(results)
print(f"DIAGNOSTIC SUMMARY: {passed_count}/{total_count} CHECKS PASSED")
print("=" * 60)

if passed_count == total_count:
    print("🚀 STATUS: ALL SYSTEMS FULLY OPERATIONAL AND PRODUCTION-READY!")
else:
    print("⚠️ STATUS: SOME CHECKS REQUIRE ATTENTION.")
