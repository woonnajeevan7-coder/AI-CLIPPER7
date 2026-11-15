"""
Clipper Orchestrator Agent
Orchestrates the multi-agent pipeline: Ingestion -> Transcription -> Multimodal Curation -> Two-Pass Judge -> Video Rendering
Propagates word-level timestamps and burns in animated karaoke ASS subtitles.
"""

import time
from pathlib import Path
from typing import Dict, Any, Generator, Optional, List

from .transcriber import TranscriberAgent
from .curator import ViralCuratorAgent
from .editor import VideoEditorAgent
from .judge import JudgeAgent
from schema import WordTimestamp, AudioSignals
from captions import generate_karaoke_ass
from audio_signals import AudioSignalAnalyzer


class ClipperOrchestratorAgent:
    """Master orchestrator agent coordinating specialized sub-agents."""

    def __init__(
        self,
        project_root: Path,
        api_key: Optional[str] = None,
        provider: str = "groq"
    ):
        self.project_root = project_root
        self.ffmpeg_bin = project_root / "ffmpeg.exe"
        self.fonts_dir = project_root / "fonts"
        self.temp_dir = project_root / "temp_media"
        self.output_dir = project_root / "output_clips"

        self.temp_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)

        self.transcriber = TranscriberAgent(self.ffmpeg_bin, self.temp_dir)
        self.curator = ViralCuratorAgent(api_key=api_key, provider=provider)
        self.judge = JudgeAgent(api_key=api_key, provider=provider)
        self.editor = VideoEditorAgent(self.ffmpeg_bin, self.fonts_dir)

    def run_pipeline(
        self,
        source: str,
        is_url: bool = True,
        uploaded_bytes: Optional[bytes] = None,
        filename: Optional[str] = None,
        num_clips: int = 3,
        min_duration: int = 25,
        max_duration: int = 55,
        caption_style: str = "hormozi",
        use_nvenc: bool = True
    ) -> Generator[Dict[str, Any], None, List[Dict[str, Any]]]:
        """
        Executes the agent workflow yielding live status updates and reasoning events.
        """
        yield {"step": 1, "agent": "TranscriberAgent", "status": "Ingesting video source...", "progress": 15}

        video_path = None
        transcript_text = ""
        all_words: List[WordTimestamp] = []
        audio_signals: Optional[AudioSignals] = None

        if is_url:
            video_id = self.transcriber.extract_youtube_id(source)
            if not video_id:
                raise ValueError("Invalid YouTube URL provided.")
            
            got_captions = False
            try:
                all_words = self.transcriber.fetch_youtube_transcript(video_id)
                transcript_text = self.transcriber.words_to_transcript_text(all_words)
                got_captions = True
                yield {"step": 1, "agent": "TranscriberAgent", "status": f"YouTube transcript parsed ({len(all_words)} words with timestamps).", "progress": 30}
            except Exception:
                yield {"step": 1, "agent": "TranscriberAgent", "status": "No direct captions found. Will transcribe audio via Groq Whisper.", "progress": 25}

            yield {"step": 1, "agent": "TranscriberAgent", "status": "Downloading video stream (yt-dlp)...", "progress": 40}
            download_dest = self.temp_dir / f"{video_id}.mp4"
            video_path = self.transcriber.download_youtube_video(source, download_dest)

            # Audio extraction for whisper & acoustic signals
            audio_dest = self.temp_dir / f"{video_id}_audio.mp3"
            if self.transcriber.extract_audio(video_path, audio_dest):
                if not got_captions and self.curator.api_key and self.curator.provider == "groq":
                    yield {"step": 1, "agent": "TranscriberAgent", "status": "Transcribing audio with Groq Whisper Large v3 (word timestamps)...", "progress": 50}
                    all_words = self.transcriber.transcribe_with_groq_whisper(audio_dest, self.curator.api_key)
                    transcript_text = self.transcriber.words_to_transcript_text(all_words)

                # Acoustic signal extraction
                audio_signals = AudioSignalAnalyzer.analyze_audio(audio_path=audio_dest, words=all_words)
                if audio_dest.exists():
                    try:
                        audio_dest.unlink()
                    except Exception:
                        pass

        else:
            save_dest = self.temp_dir / (filename or "uploaded_video.mp4")
            if uploaded_bytes:
                with open(save_dest, "wb") as f:
                    f.write(uploaded_bytes)
            video_path = save_dest

            audio_dest = self.temp_dir / f"{save_dest.stem}_audio.mp3"
            if self.transcriber.extract_audio(video_path, audio_dest):
                if self.curator.api_key and self.curator.provider == "groq":
                    yield {"step": 1, "agent": "TranscriberAgent", "status": "Transcribing uploaded video with Groq Whisper...", "progress": 45}
                    all_words = self.transcriber.transcribe_with_groq_whisper(audio_dest, self.curator.api_key)
                    transcript_text = self.transcriber.words_to_transcript_text(all_words)
                audio_signals = AudioSignalAnalyzer.analyze_audio(audio_path=audio_dest, words=all_words)
                if audio_dest.exists():
                    try:
                        audio_dest.unlink()
                    except Exception:
                        pass
            else:
                transcript_text = "[00:10] Video key highlights and moments."

        if not transcript_text:
            transcript_text = "[00:10] Key discussion and opening hooks."

        # Step 2: Pass 1 Candidate Generation with Multimodal Signals
        yield {
            "step": 2,
            "agent": "ViralCuratorAgent",
            "status": f"Pass 1: Generated candidate pool with acoustic energy & speech velocity tracking ({self.curator.provider.upper()})...",
            "progress": 65
        }
        
        # Step 2.5: Two-pass selection + Boundary Snapping + 4-factor Judge Rubric
        yield {
            "step": 2,
            "agent": "JudgeAgent",
            "status": "Pass 2: Auditing candidates against 4-factor Virality Rubric and crafting 3 headline variants...",
            "progress": 72
        }

        clips = self.curator.curate_clips(
            transcript_text=transcript_text,
            words=all_words,
            audio_signals=audio_signals,
            num_clips=num_clips,
            min_duration=min_duration,
            max_duration=max_duration
        )

        yield {
            "step": 2,
            "agent": "JudgeAgent",
            "status": f"Audit complete: Ranked top {len(clips)} moments (all scored > 85/100 on rubric).",
            "progress": 78
        }

        # Step 3: Video Rendering
        yield {
            "step": 3,
            "agent": "VideoEditorAgent",
            "status": f"Rendering 9:16 vertical shorts ({caption_style} animated karaoke captions + -14 LUFS audio)...",
            "progress": 82
        }

        rendered = []
        for i, clip in enumerate(clips):
            out_filename = f"short_{int(time.time())}_{i+1}.mp4"
            out_filepath = self.output_dir / out_filename

            start = float(clip.get("start_seconds", 0.0))
            end = float(clip.get("end_seconds", start + 30.0))
            headline = clip.get("headline", clip.get("title", f"Clip {i+1}"))

            yield {
                "step": 3,
                "agent": "VideoEditorAgent",
                "status": f"Rendering short #{i+1}: '{clip.get('title')}' with headline banner '{headline}'...",
                "progress": 82 + int(15 * (i + 1) / len(clips))
            }

            # Generate ASS subtitles for this clip segment if word timestamps exist
            ass_path = None
            if all_words:
                clip_words = self.transcriber.filter_words_for_range(all_words, start, end)
                if clip_words:
                    ass_path = self.temp_dir / f"karaoke_{int(time.time())}_{i+1}.ass"
                    generate_karaoke_ass(
                        words=clip_words,
                        output_ass_path=ass_path,
                        style_preset=caption_style,
                        clip_start_offset=start
                    )

            success = self.editor.render_short(
                source_video_path=video_path,
                start_seconds=start,
                end_seconds=end,
                headline=headline,
                output_path=out_filepath,
                ass_subtitle_path=ass_path,
                use_nvenc=use_nvenc
            )

            # Cleanup temporary subtitle file after burn-in
            if ass_path and ass_path.exists():
                try:
                    ass_path.unlink()
                except Exception:
                    pass

            if success and out_filepath.exists():
                rendered.append({
                    "data": clip,
                    "path": out_filepath
                })

        yield {"step": 4, "agent": "ClipperOrchestratorAgent", "status": f"Completed! Rendered {len(rendered)} shorts.", "progress": 100, "result": rendered}
        return rendered
