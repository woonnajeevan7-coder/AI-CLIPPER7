"""
Growth Features Agent
Multi-language transcription (Hindi, Telugu, Tamil), YouTube channel watcher,
official OAuth auto-publishing (Shorts, TikTok, Instagram Reels), and batch processing.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import re

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

from schema import WordTimestamp


SUPPORTED_LANGUAGES = {
    "en": {"name": "English", "font": "Montserrat-Bold"},
    "hi": {"name": "Hindi (हिन्दी)", "font": "Nirmala.ttf"},
    "te": {"name": "Telugu (తెలుగు)", "font": "Nirmala.ttf"},
    "ta": {"name": "Tamil (தமிழ்)", "font": "Nirmala.ttf"},
    "es": {"name": "Spanish (Español)", "font": "Montserrat-Bold"},
    "pt": {"name": "Portuguese (Português)", "font": "Montserrat-Bold"},
}


class MultiLanguageEngine:
    """Manages multilingual transcription and translation for regional Indian and global languages."""

    @staticmethod
    def transcribe_multilingual(
        audio_path: Path,
        api_key: str,
        language: str = "hi",
        translate_to_english: bool = False
    ) -> List[WordTimestamp]:
        """
        Transcribes audio in Hindi, Telugu, Tamil, etc., or translates directly to English.
        """
        from groq import Groq
        client = Groq(api_key=api_key)

        with open(audio_path, "rb") as f:
            if translate_to_english:
                # Groq / Whisper translation endpoint
                resp = client.audio.translations.create(
                    file=(audio_path.name, f.read()),
                    model="whisper-large-v3",
                    response_format="verbose_json"
                )
            else:
                # Direct multilingual transcription
                resp = client.audio.transcriptions.create(
                    file=(audio_path.name, f.read()),
                    model="whisper-large-v3-turbo",
                    language=language,
                    response_format="verbose_json"
                )

        words: List[WordTimestamp] = []
        segments = getattr(resp, "segments", [])
        for seg in segments:
            text = seg.get("text", "").strip()
            s_start = float(seg.get("start", 0.0))
            s_end = float(seg.get("end", s_start + 1.0))
            tokens = [t for t in text.split() if t]
            if tokens:
                dur = (s_end - s_start) / len(tokens)
                for i, t in enumerate(tokens):
                    w_start = s_start + i * dur
                    words.append(WordTimestamp(word=t, start=round(w_start, 3), end=round(w_start + dur, 3)))

        return words


class ChannelWatcherAgent:
    """Monitors a YouTube channel and detects new uploads for autonomous clipping."""

    @staticmethod
    def check_new_channel_uploads(channel_url: str, limit: int = 5) -> List[Dict[str, str]]:
        """
        Fetches the latest videos uploaded to a channel using yt-dlp flat extraction.
        """
        if not yt_dlp:
            return []

        ydl_opts = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            "playlist_items": f"1:{limit}"
        }

        videos = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(channel_url, download=False)
                entries = info.get("entries", [])
                for entry in entries:
                    if entry and entry.get("id"):
                        videos.append({
                            "video_id": entry["id"],
                            "title": entry.get("title", "Upload"),
                            "url": f"https://www.youtube.com/watch?v={entry['id']}",
                            "duration": entry.get("duration", 0)
                        })
        except Exception as e:
            print(f"[ChannelWatcherAgent] Error checking channel uploads: {e}")

        return videos


class OfficialPublisherAgent:
    """
    Manages automated publishing and scheduling to official social platform APIs:
    - YouTube Data API v3 (Shorts)
    - TikTok Content Posting API
    - Meta Graph API (Instagram Reels)
    """

    @staticmethod
    def create_youtube_shorts_payload(
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        scheduled_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Builds official YouTube Data API v3 videos.insert payload."""
        snippet = {
            "title": f"{title} #Shorts",
            "description": f"{description}\n\n#Shorts #Viral #Podcast",
            "categoryId": "22",
            "tags": tags or ["shorts", "viral", "ai"]
        }
        status = {
            "privacyStatus": "private" if scheduled_at else "public",
            "selfDeclaredMadeForKids": False
        }
        if scheduled_at:
            status["publishAt"] = scheduled_at.isoformat() + "Z"

        return {
            "part": "snippet,status",
            "body": {
                "snippet": snippet,
                "status": status
            }
        }

    @staticmethod
    def create_tiktok_payload(
        caption: str,
        privacy_level: str = "PUBLIC_TO_EVERYONE",
        disable_comment: bool = False
    ) -> Dict[str, Any]:
        """Builds official TikTok Content Posting API request structure."""
        return {
            "post_info": {
                "title": f"{caption} #fyp #viral",
                "privacy_level": privacy_level,
                "disable_duet": False,
                "disable_stitch": False,
                "disable_comment": disable_comment,
                "video_cover_timestamp_ms": 1000
            },
            "source_info": {
                "source": "PULL_FROM_URL"
            }
        }

    @staticmethod
    def create_instagram_reels_payload(
        caption: str,
        video_url: str,
        share_to_feed: bool = True
    ) -> Dict[str, Any]:
        """Builds official Instagram Graph API Reels container payload."""
        return {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": f"{caption} #reels #explore",
            "share_to_feed": share_to_feed
        }
