"""
AI Clipper Agent Core Engine
Automated Long-Form to Viral 9:16 Vertical Shorts Generator
Multi-Agent Architecture (TranscriberAgent, ViralCuratorAgent, VideoEditorAgent, ClipperOrchestratorAgent)
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).parent.resolve()
FFMPEG_BIN = PROJECT_ROOT / "ffmpeg.exe"
FFPROBE_BIN = PROJECT_ROOT / "ffprobe.exe"
FONTS_DIR = PROJECT_ROOT / "fonts"
OUTPUT_DIR = PROJECT_ROOT / "output_clips"
TEMP_DIR = PROJECT_ROOT / "temp_media"

OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)

# Import specialized agents
from agents import (
    TranscriberAgent,
    ViralCuratorAgent,
    VideoEditorAgent,
    ClipperOrchestratorAgent
)
from agents.transcriber import YouTubeTranscriptApi, yt_dlp

# Shared agent instances
_transcriber = TranscriberAgent(FFMPEG_BIN, TEMP_DIR)
_editor = VideoEditorAgent(FFMPEG_BIN, FONTS_DIR)


# Compatibility functions
def get_ffmpeg_path() -> str:
    return str(FFMPEG_BIN) if FFMPEG_BIN.exists() else "ffmpeg"


def get_ffprobe_path() -> str:
    return str(FFPROBE_BIN) if FFPROBE_BIN.exists() else "ffprobe"


def extract_youtube_id(url: str) -> Optional[str]:
    return TranscriberAgent.extract_youtube_id(url)


def get_youtube_transcript(video_id: str) -> List[Dict[str, Any]]:
    return _transcriber.fetch_youtube_transcript(video_id)


def download_youtube_video(url: str, output_path: Path) -> Path:
    return _transcriber.download_youtube_video(url, output_path)


def extract_audio_from_video(video_path: Path, output_audio_path: Path) -> bool:
    return _transcriber.extract_audio(video_path, output_audio_path)


def transcribe_with_groq_whisper(audio_path: Path, api_key: str) -> List[Dict[str, Any]]:
    return _transcriber.transcribe_with_groq_whisper(audio_path, api_key)


def format_transcript_for_prompt(transcript: List[Dict[str, Any]], max_entries: int = 500) -> str:
    return TranscriberAgent.format_transcript_for_prompt(transcript, max_entries)


def analyze_viral_clips(
    transcript_text: str,
    api_key: Optional[str] = None,
    provider: str = "groq",
    num_clips: int = 3,
    min_duration: int = 25,
    max_duration: int = 60
) -> List[Dict[str, Any]]:
    curator = ViralCuratorAgent(api_key=api_key, provider=provider)
    return curator.curate_clips(
        transcript_text=transcript_text,
        num_clips=num_clips,
        min_duration=min_duration,
        max_duration=max_duration
    )


def render_916_vertical_clip(
    source_video_path: Path,
    start_seconds: float,
    end_seconds: float,
    headline: str,
    output_path: Path
) -> bool:
    return _editor.render_short(source_video_path, start_seconds, end_seconds, headline, output_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AI Clipper Agent CLI")
    parser.add_argument("url", nargs="?", help="YouTube video URL or path to MP4")
    parser.add_argument("--clips", type=int, default=3, help="Number of clips to generate")
    parser.add_argument("--key", type=str, default=os.getenv("GROQ_API_KEY"), help="Groq, Gemini, or OpenAI API key")
    parser.add_argument("--provider", type=str, default="groq", choices=["groq", "gemini", "openai", "heuristic"])
    args = parser.parse_args()

    if not args.url:
        print("Usage: python ai_clipper.py <youtube_url_or_file> [--clips 3] [--key API_KEY]")
        print("Or launch the web studio: double-click run_clipit.bat or run 'python -m streamlit run app.py'")
        sys.exit(0)

    orchestrator = ClipperOrchestratorAgent(PROJECT_ROOT, api_key=args.key, provider=args.provider)
    print(f"\n🎬 [OrchestratorAgent] Starting multi-agent pipeline for: {args.url}\n")
    
    for event in orchestrator.run_pipeline(args.url, is_url=True, num_clips=args.clips):
        agent_tag = f"[{event.get('agent')}]"
        print(f"{agent_tag:<24} Step {event.get('step')}: {event.get('status')} ({event.get('progress')}%)")

    print("\n✅ All AI clips rendered successfully in: output_clips/\n")
