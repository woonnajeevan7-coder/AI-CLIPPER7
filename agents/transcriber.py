"""
Transcriber Agent
Handles Video Ingestion, Audio Extraction & Speech-to-Text via YouTube API & Groq Whisper
Propagates word-level timestamps through the full pipeline.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

from schema import WordTimestamp


class TranscriberAgent:
    """Agent responsible for media ingestion, audio isolation, and word-level transcription."""

    def __init__(self, ffmpeg_bin: Path, temp_dir: Path):
        self.ffmpeg_bin = ffmpeg_bin
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(exist_ok=True)

    @staticmethod
    def extract_youtube_id(url: str) -> Optional[str]:
        patterns = [
            r"(?:v=|\/|youtu\.be\/|embed\/)([0-9A-Za-z_-]{11})",
            r"^([0-9A-Za-z_-]{11})$"
        ]
        for p in patterns:
            match = re.search(p, url)
            if match:
                return match.group(1)
        return None

    def fetch_youtube_transcript(self, video_id: str) -> List[WordTimestamp]:
        """Fetch YouTube captions and interpolate to word-level timestamps."""
        if not YouTubeTranscriptApi:
            raise ImportError("youtube-transcript-api is not installed.")
        
        raw_items = []
        try:
            raw_items = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US', 'en-GB'])
        except Exception:
            try:
                transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                for transcript in transcript_list:
                    raw_items = transcript.fetch()
                    break
            except Exception as e:
                raise RuntimeError(f"Could not retrieve YouTube captions: {e}")

        # Interpolate phrases to word-level timestamps
        words: List[WordTimestamp] = []
        for item in raw_items:
            text = item.get('text', '').replace('\n', ' ').strip()
            item_start = float(item.get('start', 0.0))
            item_duration = float(item.get('duration', 0.0))
            item_end = item_start + item_duration

            tokens = [t for t in re.split(r'\s+', text) if t]
            if not tokens:
                continue

            word_dur = item_duration / len(tokens)
            for idx, token in enumerate(tokens):
                w_start = item_start + (idx * word_dur)
                w_end = w_start + word_dur
                words.append(WordTimestamp(word=token, start=round(w_start, 3), end=round(w_end, 3)))

        return words

    def download_youtube_video(self, url: str, output_path: Path) -> Path:
        if not yt_dlp:
            raise ImportError("yt-dlp is not installed.")
        
        ydl_opts = {
            'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
            'outtmpl': str(output_path.with_suffix('')) + '.%(ext)s',
            'merge_output_format': 'mp4',
            'ffmpeg_location': str(self.ffmpeg_bin.parent),
            'quiet': True,
            'no_warnings': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            final_filename = ydl.prepare_filename(info)
            final_path = Path(final_filename)
            if not final_path.exists():
                final_path = output_path.with_suffix('.mp4')
            return final_path

    def extract_audio(self, video_path: Path, output_audio_path: Path) -> bool:
        cmd = [
            str(self.ffmpeg_bin),
            "-i", str(video_path),
            "-vn",
            "-acodec", "mp3",
            "-ar", "16000",
            "-ac", "1",
            "-y",
            str(output_audio_path)
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except Exception as e:
            print(f"[TranscriberAgent] Error extracting audio: {e}")
            return False

    def transcribe_with_groq_whisper(self, audio_path: Path, api_key: str) -> List[WordTimestamp]:
        """
        Ultra-fast speech-to-text using Groq Whisper Large v3 Turbo with word-level timestamps.
        If extracted audio exceeds 25MB, splits into 10-minute segments using FFmpeg,
        transcribes each chunk with Groq Whisper, and accumulates time offsets (t_offset = chunk_idx * 600.0s).
        """
        from groq import Groq
        client = Groq(api_key=api_key)

        file_size = audio_path.stat().st_size if audio_path.exists() else 0
        max_payload_size = 25 * 1024 * 1024  # 25MB Groq API limit

        if file_size > max_payload_size:
            print(f"[TranscriberAgent] Audio file ({file_size / (1024*1024):.2f}MB) exceeds 25MB limit. Splitting into 10-minute chunks...")
            chunk_pattern = self.temp_dir / f"{audio_path.stem}_chunk_%03d.mp3"
            cmd = [
                str(self.ffmpeg_bin),
                "-i", str(audio_path),
                "-f", "segment",
                "-segment_time", "600",
                "-c", "copy",
                "-y",
                str(chunk_pattern)
            ]
            try:
                subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                chunk_files = sorted(self.temp_dir.glob(f"{audio_path.stem}_chunk_*.mp3"))
                all_words: List[WordTimestamp] = []
                for chunk_idx, chunk_file in enumerate(chunk_files):
                    t_offset = chunk_idx * 600.0
                    chunk_words = self._transcribe_single_audio_file(chunk_file, api_key, client)
                    for w in chunk_words:
                        all_words.append(WordTimestamp(
                            word=w.word,
                            start=round(w.start + t_offset, 3),
                            end=round(w.end + t_offset, 3),
                            is_keyword=w.is_keyword,
                            emoji=w.emoji
                        ))
                    try:
                        chunk_file.unlink()
                    except Exception:
                        pass
                return all_words
            except Exception as e:
                print(f"[TranscriberAgent] Error during chunked transcription: {e}, falling back to single file...")

        return self._transcribe_single_audio_file(audio_path, api_key, client)

    def _transcribe_single_audio_file(self, audio_path: Path, api_key: str, client: Any = None) -> List[WordTimestamp]:
        if client is None:
            from groq import Groq
            client = Groq(api_key=api_key)

        with open(audio_path, "rb") as f:
            response = client.audio.transcriptions.create(
                file=(audio_path.name, f.read()),
                model="whisper-large-v3-turbo",
                response_format="verbose_json",
                timestamp_granularities=["word"]
            )
        
        words: List[WordTimestamp] = []
        raw_words = getattr(response, "words", [])
        if raw_words:
            for w in raw_words:
                words.append(WordTimestamp(
                    word=str(w.get("word", "")).strip(),
                    start=float(w.get("start", 0.0)),
                    end=float(w.get("end", 0.0))
                ))
        else:
            # Fallback to segments
            segments = getattr(response, "segments", [])
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

    @staticmethod
    def words_to_transcript_text(words: List[WordTimestamp], max_entries: int = 500) -> str:
        """Convert word stream into timestamped lines for LLM analysis."""
        if not words:
            return ""
        lines = []
        chunk_words = []
        chunk_start = words[0].start

        for w in words:
            chunk_words.append(w.word)
            if len(chunk_words) >= 12 or (w.end - chunk_start) >= 5.0:
                mins = int(chunk_start // 60)
                secs = int(chunk_start % 60)
                lines.append(f"[{mins:02d}:{secs:02d}] {' '.join(chunk_words)}")
                chunk_words = []
                chunk_start = w.end

        if chunk_words:
            mins = int(chunk_start // 60)
            secs = int(chunk_start % 60)
            lines.append(f"[{mins:02d}:{secs:02d}] {' '.join(chunk_words)}")

        return "\n".join(lines[:max_entries])

    @classmethod
    def format_transcript_for_prompt(cls, words_or_items: Any) -> str:
        """Alias for backward compatibility accepting WordTimestamp list or raw dicts."""
        if not words_or_items:
            return ""
        if isinstance(words_or_items, list) and words_or_items and isinstance(words_or_items[0], WordTimestamp):
            return cls.words_to_transcript_text(words_or_items)
        if isinstance(words_or_items, list) and words_or_items and isinstance(words_or_items[0], dict):
            words = [
                WordTimestamp(
                    word=d.get("word", d.get("text", "")),
                    start=float(d.get("start", 0.0)),
                    end=float(d.get("end", float(d.get("start", 0.0)) + float(d.get("duration", 1.0))))
                )
                for d in words_or_items
            ]
            return cls.words_to_transcript_text(words)
        return str(words_or_items)

    @staticmethod
    def filter_words_for_range(words: List[WordTimestamp], start_seconds: float, end_seconds: float) -> List[WordTimestamp]:
        """Extract only words falling inside a clip's [start, end] window."""
        return [w for w in words if w.start >= start_seconds - 0.2 and w.end <= end_seconds + 0.5]
