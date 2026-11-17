"""
Live Clip Enhancer Engine
Converts raw 60s stream cuts into full 9:16 vertical videos with animated karaoke captions,
cheap motion framing (10th frame sampling with EMA smoothing), viral headlines, and audio polish.
- Status flow: raw -> enhancing -> ready (or failed, with error & retry).
- Never drops clips; reports 'enhancing N clips behind'.
- Real-time factor (RTF) tracking: logs render sec / video sec. If RTF > 1.0 for 5 consecutive clips,
  emits 'falling_behind' warning with scaling advice.
- SSE events: clip_enhancing, clip_ready, clip_failed, falling_behind, error.
"""

import asyncio
import json
import os
import subprocess
import time
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

from backend.config import settings
from backend.database import SessionLocal
from backend.models import Clip, LiveSession, LiveSegment
from backend.storage import storage
from backend.telemetry import logger
from backend.sse import live_broadcaster
from ffmpeg_utils import get_ffmpeg_bin
from agents.framing import SmartFramingAgent
from agents.editor import VideoEditorAgent
from agents.transcriber import TranscriberAgent
from schema import WordTimestamp
from captions import generate_karaoke_ass


class RealTimeFactorTracker:
    """Tracks per-session render time / video duration real-time factors (RTF)."""

    def __init__(self):
        self._history: Dict[str, List[float]] = {}

    def record_rtf(self, session_id: str, rtf: float) -> bool:
        """
        Records RTF and returns True if the last 5 consecutive clips had RTF > 1.0.
        """
        if session_id not in self._history:
            self._history[session_id] = []
        self._history[session_id].append(rtf)
        recent_5 = self._history[session_id][-5:]
        return len(recent_5) == 5 and all(r > 1.0 for r in recent_5)

    def get_recent(self, session_id: str) -> List[float]:
        return self._history.get(session_id, [])

    def reset(self, session_id: str):
        self._history.pop(session_id, None)


rtf_tracker = RealTimeFactorTracker()


def _broadcast_event(session_id: Optional[str], event_name: str, data: dict):
    """Broadcasts SSE event across running event loops or standalone runner."""
    if not session_id:
        return
    try:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(live_broadcaster.broadcast(session_id=session_id, event_name=event_name, data=data))
        except RuntimeError:
            asyncio.run(live_broadcaster.broadcast(session_id=session_id, event_name=event_name, data=data))
    except Exception as e:
        logger.warning(f"[LiveEnhancer] Broadcast event {event_name} warning: {e}")


def _generate_headline(words: List[WordTimestamp], clip_index: int, default_headline: Optional[str] = None) -> str:
    """
    Generates a viral 3-6 word uppercase headline using a fast Groq LLM call,
    with automatic fallback to the first caption line.
    """
    if words and settings.GROQ_API_KEY:
        try:
            from groq import Groq
            client = Groq(api_key=settings.GROQ_API_KEY)
            snippet = " ".join(w.word for w in words[:35])
            comp = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an elite short-form video editor. Generate a punchy, viral "
                            "3 to 6 word headline in all uppercase letters for this video clip transcript. "
                            "Output ONLY the headline, no quotes, no markdown, no punctuation."
                        ),
                    },
                    {"role": "user", "content": f"Transcript: {snippet}"},
                ],
                max_tokens=25,
                temperature=0.7,
            )
            cand = comp.choices[0].message.content.strip().strip('"').strip("'")
            if 3 <= len(cand) <= 60 and not cand.startswith("{"):
                return cand.upper()
        except Exception as e:
            logger.info(f"[LiveEnhancer] Groq headline call notice: {e}; falling back to caption words.")

    if words:
        first_line = " ".join(w.word for w in words[:6]).strip()
        if first_line:
            return first_line.upper()

    return default_headline or f"VIRAL MOMENT #{clip_index + 1}"


def enhance_clip_sync(clip_id: str, framing_mode: Optional[str] = None) -> Optional[Clip]:
    """
    Synchronous enhancement execution designed for Celery worker or background task.
    Converts raw 60s stream cuts into full 9:16 vertical videos:
    1. Groq Whisper on the audio -> word-level timestamps
    2. Karaoke ASS subtitles with word highlighting & emojis
    3. Cheap framing mode for live: face detection every 10th frame with EMA smoothing
    4. Headline: fast LLM call with fallback to first caption line
    5. VideoEditorAgent rendering with NVENC / libx264 veryfast
    6. RTF logging & 5-in-a-row > 1.0 falling_behind alerting
    7. Storage upload and status transition to 'ready'
    """
    db = SessionLocal()
    session_id = None
    try:
        clip = db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            logger.error(f"[LiveEnhancer] Clip '{clip_id}' not found.")
            return None

        session_id = clip.live_session_id

        # Idempotency check: if clip is already ready and video file exists, return immediately
        if clip.status in ("ready", "completed") and clip.video_url:
            if Path(clip.video_url).exists() or clip.r2_key:
                logger.info(f"[LiveEnhancer] Clip {clip_id} already enhanced and ready.")
                return clip

        # Count pending clips behind this one
        clips_behind = 0
        if session_id:
            clips_behind = (
                db.query(Clip)
                .filter(
                    Clip.live_session_id == session_id,
                    Clip.status.in_(["raw", "enhancing"]),
                    Clip.id != clip.id,
                )
                .count()
            )

        # Transition status to 'enhancing'
        clip.status = "enhancing"
        db.commit()

        _broadcast_event(session_id, "clip_enhancing", {
            "clip_id": clip.id,
            "clip_index": clip.clip_index,
            "status": "enhancing",
            "clips_behind": clips_behind,
            "message": f"Enhancing clip #{clip.clip_index + 1} ({clips_behind} clips behind)"
            if clips_behind > 0
            else f"Enhancing clip #{clip.clip_index + 1}",
        })

        # Find raw input file
        raw_video_path = None
        if clip.video_url and Path(clip.video_url).exists():
            raw_video_path = Path(clip.video_url)
        elif clip.r2_key:
            candidate = storage.local_storage_dir / clip.r2_key
            if candidate.exists():
                raw_video_path = candidate

        if not raw_video_path or not raw_video_path.exists():
            if session_id:
                cutter_fallback = (
                    Path(__file__).parent.parent
                    / "temp_media"
                    / "live"
                    / session_id
                    / "cutter_tmp"
                    / f"raw_clip_{clip.clip_index or 0:05d}.mp4"
                )
                if cutter_fallback.exists():
                    raw_video_path = cutter_fallback

        if not raw_video_path or not raw_video_path.exists():
            clip.status = "failed"
            clip.error = f"Raw video file for clip {clip_id} could not be located on disk."
            db.commit()
            logger.error(f"[LiveEnhancer] Raw video file for clip {clip_id} could not be located on disk.")
            _broadcast_event(session_id, "clip_failed", {
                "clip_id": clip.id,
                "clip_index": clip.clip_index,
                "status": "failed",
                "error": clip.error,
                "can_retry": True,
            })
            _broadcast_event(session_id, "error", {
                "clip_id": clip.id,
                "status": "render_failed",
                "error": clip.error,
            })
            return None

        # Build output path
        output_dir = Path(__file__).parent.parent / "output_clips"
        output_dir.mkdir(parents=True, exist_ok=True)
        enhanced_filename = f"enhanced_live_{clip.id[:8]}_{uuid.uuid4().hex[:6]}.mp4"
        enhanced_path = output_dir / enhanced_filename

        # 1. Determine effective framing mode
        explicit_mode = framing_mode or clip.layout
        if explicit_mode in ("auto", "none", "", None) and clip.live_session and clip.live_session.target_framing:
            explicit_mode = clip.live_session.target_framing

        text_context = f"{clip.title} {clip.headline or ''} {clip.reason or ''}"
        effective_mode, _ = SmartFramingAgent.detect_genre_and_framing(
            text=text_context,
            explicit_framing_mode=explicit_mode,
        )

        ffmpeg_bin = get_ffmpeg_bin()

        # 2. Extract audio from raw video for Whisper transcription
        audio_tmp = output_dir / f"audio_{clip.id[:8]}_{uuid.uuid4().hex[:4]}.mp3"
        cmd_audio = [
            str(ffmpeg_bin),
            "-nostdin",
            "-loglevel", "warning",
            "-i", str(raw_video_path),
            "-vn",
            "-acodec", "libmp3lame",
            "-ar", "16000",
            "-ac", "1",
            "-y",
            str(audio_tmp),
        ]
        subprocess.run(cmd_audio, capture_output=True, text=True)

        # 3. Transcribe with Groq Whisper (word timestamps)
        words: List[WordTimestamp] = []
        if audio_tmp.exists() and audio_tmp.stat().st_size > 0 and settings.GROQ_API_KEY:
            try:
                transcriber = TranscriberAgent(ffmpeg_bin=ffmpeg_bin, temp_dir=output_dir)
                words = transcriber.transcribe_with_groq_whisper(audio_tmp, api_key=settings.GROQ_API_KEY)
            except Exception as e:
                logger.warning(f"[LiveEnhancer] Groq Whisper transcription notice for clip {clip_id}: {e}")

        # Fallback to segment words from database if Whisper yielded nothing
        if not words and session_id:
            segments = (
                db.query(LiveSegment)
                .filter(
                    LiveSegment.session_id == session_id,
                    LiveSegment.start_seconds <= clip.end_seconds,
                    LiveSegment.end_seconds >= clip.start_seconds,
                )
                .order_by(LiveSegment.segment_index)
                .all()
            )
            for seg in segments:
                if seg.words_json:
                    try:
                        w_list = json.loads(seg.words_json) if isinstance(seg.words_json, str) else seg.words_json
                        for w in w_list:
                            if clip.start_seconds - 0.2 <= w.get("start", 0.0) <= clip.end_seconds + 0.2:
                                words.append(
                                    WordTimestamp(
                                        word=w.get("word", ""),
                                        start=round(float(w.get("start", 0.0)), 3),
                                        end=round(float(w.get("end", 0.0)), 3),
                                        is_keyword=w.get("is_keyword", False),
                                        emoji=w.get("emoji"),
                                    )
                                )
                    except Exception:
                        pass

        # Cleanup audio tmp
        try:
            if audio_tmp.exists():
                audio_tmp.unlink()
        except Exception:
            pass

        # 4. Generate karaoke ASS subtitles
        ass_path = None
        if words:
            ass_path = output_dir / f"captions_{clip.id[:8]}_{uuid.uuid4().hex[:4]}.ass"
            style_preset = "sports_gaming" if effective_mode in ("gaming", "sports_gaming", "action_crop") else "hormozi"
            # If words came from LiveSegment with stream-time offsets, align to clip start;
            # if from raw cut audio, words start at 0.0 relative to clip
            offset = clip.start_seconds if (words[0].start >= clip.start_seconds - 0.5 and clip.start_seconds > 1.0) else 0.0
            generate_karaoke_ass(
                words=words,
                output_ass_path=ass_path,
                style_preset=style_preset,
                clip_start_offset=offset,
            )

        # 5. Framing: Cheap mode for live (every 10th frame with EMA smoothing)
        framing_agent = SmartFramingAgent(ema_alpha=0.15)
        crop_plan = framing_agent.analyze_framing(
            video_path=raw_video_path,
            start_seconds=0.0,
            end_seconds=clip.duration,
            mode=effective_mode,
            sample_stride=10,
        )

        # 6. Headline: Fast LLM call, fallback to first caption line
        headline_text = _generate_headline(
            words=words,
            clip_index=clip.clip_index or 0,
            default_headline=clip.headline or clip.title,
        )
        clip.headline = headline_text

        # 7. Rendering: VideoEditorAgent with hardware NVENC / software libx264 veryfast fallback
        fonts_dir = Path(__file__).parent.parent / "fonts"
        editor_agent = VideoEditorAgent(ffmpeg_bin=ffmpeg_bin, fonts_dir=fonts_dir)

        t_render_start = time.time()
        success = editor_agent.render_short(
            source_video_path=raw_video_path,
            start_seconds=0.0,
            end_seconds=clip.duration,
            headline=headline_text,
            output_path=enhanced_path,
            ass_subtitle_path=ass_path if (ass_path and ass_path.exists()) else None,
            crop_plan=crop_plan,
            use_nvenc=True,
        )
        render_seconds = time.time() - t_render_start
        video_seconds = max(0.1, clip.duration or (clip.end_seconds - clip.start_seconds))
        rtf = render_seconds / video_seconds
        logger.info(
            f"[LiveEnhancer] Clip {clip_id} rendered in {render_seconds:.2f}s for {video_seconds:.2f}s video (RTF: {rtf:.2f})"
        )

        # Real-time factor tracking: warn if 5 consecutive clips in a row have RTF > 1.0
        if session_id:
            falling_behind = rtf_tracker.record_rtf(session_id, rtf)
            if falling_behind:
                recent_5 = rtf_tracker.get_recent(session_id)[-5:]
                avg_rtf = sum(recent_5) / 5.0
                logger.warning(
                    f"[LiveEnhancer] Falling behind! Session {session_id} has RTF > 1.0 for 5 consecutive clips (avg RTF: {avg_rtf:.2f})"
                )
                _broadcast_event(session_id, "falling_behind", {
                    "session_id": session_id,
                    "consecutive_slow_clips": 5,
                    "recent_rtfs": [round(r, 2) for r in recent_5],
                    "average_rtf": round(avg_rtf, 2),
                    "advice": (
                        "Rendering is lagging behind live stream time (RTF > 1.0 for 5 consecutive clips). "
                        "Consider scaling Celery workers (concurrency 2-3), enabling GPU NVENC acceleration, "
                        "or switching to a faster libx264 preset."
                    ),
                })

        if not success or not enhanced_path.exists() or enhanced_path.stat().st_size == 0:
            clip.status = "failed"
            clip.error = f"Rendering failed for clip {clip_id}."
            db.commit()
            logger.error(f"[LiveEnhancer] Rendering failed for clip {clip_id}.")
            _broadcast_event(session_id, "clip_failed", {
                "clip_id": clip.id,
                "clip_index": clip.clip_index,
                "status": "failed",
                "error": clip.error,
                "can_retry": True,
            })
            _broadcast_event(session_id, "error", {
                "clip_id": clip.id,
                "status": "render_failed",
                "error": clip.error,
            })
            return None

        # 8. Upload to storage
        r2_key = f"clips/{session_id or 'live'}/{enhanced_filename}"
        access_url = storage.upload_file(enhanced_path, r2_key)

        clip.status = "ready"
        clip.layout = crop_plan.layout
        clip.video_url = access_url
        clip.r2_key = r2_key
        clip.error = None
        db.commit()
        db.refresh(clip)

        # 9. Broadcast SSE event: clip_ready
        _broadcast_event(session_id, "clip_ready", {
            "clip_id": clip.id,
            "clip_index": clip.clip_index,
            "status": "ready",
            "video_url": clip.video_url,
            "duration": clip.duration,
            "headline": clip.headline,
            "layout": clip.layout,
        })

        logger.info(f"[LiveEnhancer] Clip {clip_id} enhanced successfully -> {access_url}")
        return clip

    except Exception as exc:
        db.rollback()
        logger.error(f"[LiveEnhancer] Exception during clip enhancement: {exc}")
        try:
            c = db.query(Clip).filter(Clip.id == clip_id).first()
            if c:
                c.status = "failed"
                c.error = str(exc)
                db.commit()
                _broadcast_event(session_id, "clip_failed", {
                    "clip_id": clip_id,
                    "clip_index": c.clip_index,
                    "status": "failed",
                    "error": str(exc),
                    "can_retry": True,
                })
                _broadcast_event(session_id, "error", {
                    "clip_id": clip_id,
                    "status": "render_failed",
                    "error": str(exc),
                })
        except Exception:
            pass
        return None
    finally:
        db.close()


# Alias for compatibility with Celery tasks and external modules
enhance_fixed_clip_sync = enhance_clip_sync
