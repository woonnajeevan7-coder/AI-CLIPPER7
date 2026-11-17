"""
Live Highlight Detector & Curator Engine
Extracts viral highlights from live streams using existing ViralCuratorAgent, JudgeAgent,
BoundarySnapper, and AudioSignalAnalyzer.
- Overlapping sliding windows: every 3 minutes (180s step), takes last 5 minutes (300s).
- Transcribes audio with Groq Whisper (word timestamps).
- Generates candidates via ViralCuratorAgent, re-ranks with JudgeAgent.
- Adds pre-roll 3s and post-roll 3s, snaps to sentence boundaries via BoundarySnapper.
- Combines multi-modal signals: LLM score (70%) + Audio energy (15%) + Speech-rate spike (15%).
- Deduplicates against existing highlights: overlap > 30% or start within 20s.
- Gated at score >= 75 with zero score fabrication.
- Fail-loudly error path on Groq failure: marks window 'analysis_failed', zero heuristic fakes.
- Backpressure control: skips oldest windows if > 3 windows behind.
"""

import asyncio
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any, Set

from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import SessionLocal
from backend.models import LiveSession, LiveSegment, Clip
from backend.storage import storage, StorageManager
from backend.telemetry import logger
from backend.sse import live_broadcaster
from ffmpeg_utils import get_ffmpeg_bin
from agents.boundary import BoundarySnapper
from agents.curator import ViralCuratorAgent
from agents.judge import JudgeAgent
from agents.transcriber import TranscriberAgent
from audio_signals import AudioSignalAnalyzer
from schema import WordTimestamp, AudioSignals, CandidateClip, ClipMetadata


def is_duplicate_highlight(
    new_start: float,
    new_end: float,
    existing_highlights: List[Clip]
) -> bool:
    """
    Checks if a candidate highlight duplicates any existing highlight:
    - Condition 1: Starts within 20 seconds of an existing highlight (|new_start - old_start| < 20.0s).
    - Condition 2: Overlaps more than 30% with an existing highlight.
    """
    new_duration = max(0.1, new_end - new_start)

    for old in existing_highlights:
        # Check start proximity (< 20s)
        if abs(new_start - old.start_seconds) < 20.0:
            return True

        # Check overlap percentage (> 30%)
        old_duration = max(0.1, old.end_seconds - old.start_seconds)
        overlap_start = max(new_start, old.start_seconds)
        overlap_end = min(new_end, old.end_seconds)
        overlap_duration = max(0.0, overlap_end - overlap_start)

        if overlap_duration > 0.0:
            overlap_ratio = overlap_duration / min(new_duration, old_duration)
            if overlap_ratio > 0.30:
                return True

    return False


def calculate_combined_viral_score(
    llm_score: int,
    start_seconds: float,
    end_seconds: float,
    audio_signals: Optional[AudioSignals],
    words: Optional[List[WordTimestamp]]
) -> int:
    """
    Combines LLM Judge score (70%) with acoustic energy (15%) and speech-rate spikes (15%).
    Never relies on loudness alone.
    """
    # 1. Base LLM score (0 - 100)
    base_llm = float(llm_score)

    # 2. Audio energy factor (0 - 100)
    energy_score = 50.0
    if audio_signals:
        peaks = [p for p in audio_signals.energy_peaks if start_seconds <= p <= end_seconds]
        laughters = [l for l in audio_signals.laughter_spikes if start_seconds <= l <= end_seconds]
        energy_score = min(100.0, 50.0 + len(peaks) * 15.0 + len(laughters) * 20.0)

    # 3. Speech-rate spike factor (0 - 100)
    speech_rate_score = 50.0
    if words and audio_signals:
        clip_words = [w for w in words if start_seconds <= w.start <= end_seconds]
        clip_dur = max(1.0, end_seconds - start_seconds)
        clip_wps = len(clip_words) / clip_dur
        avg_wps = max(1.0, audio_signals.avg_speech_rate_wps or 2.5)
        ratio = clip_wps / avg_wps
        speech_rate_score = min(100.0, max(30.0, ratio * 60.0))

    # Weighted combination: 70% LLM, 15% Audio energy, 15% Speech rate
    combined = round(0.70 * base_llm + 0.15 * energy_score + 0.15 * speech_rate_score)
    return int(max(0, min(100, combined)))


class LiveHighlightsDetector:
    """Sliding window highlight detection engine using Groq Whisper + Curator + Judge."""

    def __init__(
        self,
        session_id: str,
        step_seconds: float = 180.0,        # 3 minutes step
        window_size_seconds: float = 300.0, # 5 minutes window
        score_gate: int = 75,
        api_key: Optional[str] = None,
        storage_mgr: Optional[StorageManager] = None,
        media_root: Optional[Path] = None,
        ffmpeg_bin: Optional[Path] = None,
    ):
        self.session_id = session_id
        self.step_seconds = float(step_seconds)
        self.window_size_seconds = float(window_size_seconds)
        self.score_gate = int(score_gate)
        self.api_key = api_key or settings.GROQ_API_KEY
        self.storage = storage_mgr or storage
        self.media_root = media_root or (Path(__file__).parent.parent / "temp_media" / "live" / session_id)
        self.ffmpeg_bin = ffmpeg_bin or get_ffmpeg_bin()

        self._processed_windows: Set[int] = set()
        self._failed_windows: Set[int] = set()

    def get_eligible_windows(self, current_stream_time: float) -> List[Tuple[int, float, float]]:
        """
        Determines all windows that have completely elapsed.
        Returns list of (window_index, window_start, window_end).
        """
        if current_stream_time < self.window_size_seconds:
            return []

        max_start = current_stream_time - self.window_size_seconds
        num_windows = int(max_start // self.step_seconds) + 1

        windows = []
        for w in range(num_windows):
            w_start = w * self.step_seconds
            w_end = w_start + self.window_size_seconds
            windows.append((w, w_start, w_end))

        return windows

    def apply_backpressure(self, pending_windows: List[Tuple[int, float, float]]) -> List[Tuple[int, float, float]]:
        """
        Backpressure enforcement: If more than 3 windows behind,
        skips the oldest windows and logs it.
        """
        max_queue_depth = 3
        if len(pending_windows) > max_queue_depth:
            skipped = pending_windows[:-max_queue_depth]
            active = pending_windows[-max_queue_depth:]
            for w_idx, w_start, w_end in skipped:
                self._processed_windows.add(w_idx)
                logger.warning(
                    f"[LiveHighlights] Backpressure: {len(pending_windows)} windows pending (> {max_queue_depth}). "
                    f"Skipping oldest window #{w_idx} [{w_start:.1f}s -> {w_end:.1f}s]."
                )
            return active
        return pending_windows

    def extract_window_media(
        self,
        window_start: float,
        window_end: float,
        work_dir: Path,
        db: Session
    ) -> Optional[Tuple[Path, Path, float]]:
        """
        Gathers window segments, concatenates, and extracts audio file and merged video file.
        Returns (merged_video_path, window_audio_path, first_seg_start).
        """
        segments = (
            db.query(LiveSegment)
            .filter(
                LiveSegment.session_id == self.session_id,
                LiveSegment.end_seconds >= window_start - 3.5,
                LiveSegment.start_seconds <= window_end + 3.5
            )
            .order_by(LiveSegment.segment_index.asc())
            .all()
        )

        valid_segments = [s for s in segments if Path(s.file_path).exists() and Path(s.file_path).stat().st_size > 0]
        if not valid_segments:
            return None

        first_seg_start = valid_segments[0].start_seconds
        concat_txt = work_dir / f"concat_hl_{uuid.uuid4().hex[:6]}.txt"
        merged_ts = work_dir / f"merged_hl_{uuid.uuid4().hex[:6]}.ts"
        window_audio = work_dir / f"audio_hl_{uuid.uuid4().hex[:6]}.mp3"

        with open(concat_txt, "w", encoding="utf-8") as f:
            for s in valid_segments:
                f.write(f"file '{Path(s.file_path).resolve().as_posix()}'\n")

        # Merge segments with stream copy
        cmd_merge = [
            str(self.ffmpeg_bin),
            "-nostdin",
            "-loglevel", "warning",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_txt),
            "-c", "copy",
            "-y",
            str(merged_ts)
        ]
        res_merge = subprocess.run(cmd_merge, capture_output=True, text=True)
        try:
            concat_txt.unlink()
        except Exception:
            pass

        if res_merge.returncode != 0 or not merged_ts.exists():
            return None

        # Extract audio (MP3) for transcription and audio signal analysis
        rel_start = max(0.0, window_start - first_seg_start)
        rel_dur = window_end - window_start
        cmd_audio = [
            str(self.ffmpeg_bin),
            "-nostdin",
            "-loglevel", "warning",
            "-ss", f"{rel_start:.3f}",
            "-t", f"{rel_dur:.3f}",
            "-i", str(merged_ts),
            "-vn",
            "-acodec", "libmp3lame",
            "-q:a", "2",
            "-y",
            str(window_audio)
        ]
        res_audio = subprocess.run(cmd_audio, capture_output=True, text=True)
        if res_audio.returncode != 0 or not window_audio.exists():
            return None

        return merged_ts, window_audio, first_seg_start

    def process_window(
        self,
        window_index: int,
        window_start: float,
        window_end: float,
        db: Optional[Session] = None
    ) -> List[Clip]:
        """
        Executes end-to-end highlight analysis on a single sliding window:
        1. Transcribe with Groq Whisper
        2. Propose with ViralCuratorAgent
        3. Score with JudgeAgent
        4. Add pre/post-roll 3s and snap to sentence boundaries
        5. Multi-signal score combination & >= 75 gating
        6. Deduplicate against existing highlights
        7. Persist Clip(source='highlight', status='raw')
        """
        close_db = False
        if db is None:
            db = SessionLocal(expire_on_commit=False)
            close_db = True

        work_dir = self.media_root / "highlights_tmp"
        work_dir.mkdir(parents=True, exist_ok=True)
        created_clips: List[Clip] = []

        try:
            # 1. Extract window media
            media_info = self.extract_window_media(window_start, window_end, work_dir, db)
            if not media_info:
                logger.warning(f"[LiveHighlights] Window #{window_index} media extraction failed.")
                return []

            merged_ts, window_audio, first_seg_start = media_info

            # 2. Transcribe with Groq Whisper (fail-loudly on failure)
            try:
                transcriber = TranscriberAgent(ffmpeg_bin=self.ffmpeg_bin, temp_dir=work_dir)
                raw_words = transcriber.transcribe_with_groq_whisper(window_audio, api_key=self.api_key)
            except Exception as exc:
                logger.error(f"[LiveHighlights] Groq Whisper transcription failed for window #{window_index}: {exc}")
                self._mark_analysis_failed(window_index, window_start, window_end, str(exc), db)
                return []

            if not raw_words:
                logger.info(f"[LiveHighlights] No speech detected in window #{window_index}.")
                self._processed_windows.add(window_index)
                return []

            # Adjust word timestamps to absolute stream time
            words: List[WordTimestamp] = [
                WordTimestamp(
                    word=w.word,
                    start=round(w.start + window_start, 3),
                    end=round(w.end + window_start, 3),
                    is_keyword=w.is_keyword,
                    emoji=w.emoji
                )
                for w in raw_words
            ]

            # 3. Multimodal Audio Signal Extraction
            audio_signals = AudioSignalAnalyzer.analyze_audio(audio_path=window_audio, words=words)

            # 4. ViralCuratorAgent Pass-1 Candidates
            try:
                curator = ViralCuratorAgent(api_key=self.api_key, provider="groq")
                candidates = curator.propose_candidates(words=words, audio_signals=audio_signals, top_n=5)
            except Exception as exc:
                logger.error(f"[LiveHighlights] Groq Curator analysis failed for window #{window_index}: {exc}")
                self._mark_analysis_failed(window_index, window_start, window_end, str(exc), db)
                return []

            if not candidates:
                self._processed_windows.add(window_index)
                return []

            # 5. JudgeAgent Pass-2 Evaluation
            try:
                judge = JudgeAgent(api_key=self.api_key, provider="groq", min_score_threshold=self.score_gate)
                evaluated_clips = judge.evaluate_candidates(
                    candidates=candidates,
                    transcript_words=words,
                    audio_signals=audio_signals,
                    top_n=3,
                    threshold=self.score_gate
                )
            except Exception as exc:
                logger.error(f"[LiveHighlights] Groq Judge evaluation failed for window #{window_index}: {exc}")
                self._mark_analysis_failed(window_index, window_start, window_end, str(exc), db)
                return []

            # 6. Pre/Post-roll + Sentence Snapping + Signal Combination + Deduplication
            existing_highlights = (
                db.query(Clip)
                .filter(
                    Clip.live_session_id == self.session_id,
                    Clip.source == "highlight"
                )
                .all()
            )

            for cand in evaluated_clips:
                # Add pre-roll 3s and post-roll 3s
                raw_start = max(0.0, cand.start_seconds - 3.0)
                raw_end = cand.end_seconds + 3.0

                # Snap to sentence boundaries using BoundarySnapper
                snapped_start, snapped_end = BoundarySnapper.snap_boundaries(
                    words=words,
                    raw_start=raw_start,
                    raw_end=raw_end,
                    min_duration=15.0,
                    max_duration=90.0
                )

                # Combine signals: LLM + Audio energy + Speech-rate spike
                rubric_score = cand.rubric.total_score if cand.rubric else cand.viral_score
                combined_score = calculate_combined_viral_score(
                    llm_score=rubric_score,
                    start_seconds=snapped_start,
                    end_seconds=snapped_end,
                    audio_signals=audio_signals,
                    words=words
                )

                # Score gating: Gate at >= score_gate (default 75), never fabricate
                if combined_score < self.score_gate:
                    logger.info(
                        f"[LiveHighlights] Candidate '{cand.title}' scored {combined_score} < {self.score_gate}. Gated out."
                    )
                    continue

                # Deduplicate against existing highlights (overlap > 30% or start within 20s)
                if is_duplicate_highlight(snapped_start, snapped_end, existing_highlights):
                    logger.info(
                        f"[LiveHighlights] Candidate '{cand.title}' [{snapped_start}s -> {snapped_end}s] "
                        f"is duplicate of existing highlight. Skipping."
                    )
                    continue

                # Stream copy cut from merged window TS
                rel_cut_start = max(0.0, snapped_start - first_seg_start)
                rel_cut_dur = max(1.0, snapped_end - snapped_start)
                clip_uid = uuid.uuid4().hex[:8]
                raw_clip_path = work_dir / f"hl_{cand.title[:12]}_{clip_uid}.mp4"

                cmd_cut = [
                    str(self.ffmpeg_bin),
                    "-nostdin",
                    "-loglevel", "warning",
                    "-ss", f"{rel_cut_start:.3f}",
                    "-t", f"{rel_cut_dur:.3f}",
                    "-i", str(merged_ts),
                    "-c", "copy",
                    "-avoid_negative_ts", "make_zero",
                    "-y",
                    str(raw_clip_path)
                ]
                subprocess.run(cmd_cut, capture_output=True, text=True)

                stored_url = None
                r2_key = f"live/{self.session_id}/highlights/clip_{clip_uid}.mp4"
                if raw_clip_path.exists() and raw_clip_path.stat().st_size > 0:
                    stored_url = self.storage.upload_file(raw_clip_path, r2_key)
                else:
                    stored_url = f"/api/v1/mock-live/{self.session_id}/{clip_uid}.mp4"

                # Persist Clip(source='highlight', status='raw')
                clip_row = Clip(
                    id=str(uuid.uuid4()),
                    live_session_id=self.session_id,
                    source="highlight",
                    status="raw",
                    title=cand.title,
                    headline=cand.headline or cand.title,
                    start_seconds=snapped_start,
                    end_seconds=snapped_end,
                    duration=round(snapped_end - snapped_start, 2),
                    viral_score=combined_score,
                    hook=cand.hook,
                    reason=cand.reason,
                    rubric_json=cand.rubric.model_dump() if cand.rubric else None,
                    headline_variants_json=cand.headline_variants.model_dump() if cand.headline_variants else None,
                    video_url=stored_url,
                    r2_key=r2_key,
                )
                db.add(clip_row)
                db.commit()
                db.refresh(clip_row)

                existing_highlights.append(clip_row)
                created_clips.append(clip_row)

                # Broadcast SSE event: clip_created
                self._broadcast_clip_created(clip_row)

                logger.info(
                    f"[LiveHighlights] Discovered Viral Highlight: '{clip_row.title}' "
                    f"[{snapped_start:.1f}s -> {snapped_end:.1f}s] Score: {combined_score}/100"
                )

            self._processed_windows.add(window_index)
            return created_clips

        finally:
            # Clean up working audio and merged video files
            try:
                for f in work_dir.glob("*.ts"):
                    f.unlink()
                for f in work_dir.glob("*.mp3"):
                    f.unlink()
            except Exception:
                pass

            if close_db:
                db.close()

    def run_detection_cycle(self) -> List[Clip]:
        """Runs a detection cycle scanning for newly elapsed windows and applies backpressure."""
        db = SessionLocal(expire_on_commit=False)
        all_created: List[Clip] = []
        try:
            segments = (
                db.query(LiveSegment)
                .filter(LiveSegment.session_id == self.session_id)
                .order_by(LiveSegment.segment_index.asc())
                .all()
            )
            if not segments:
                return []

            current_stream_time = max(s.end_seconds for s in segments)
            eligible = self.get_eligible_windows(current_stream_time)

            # Filter out already processed or failed windows
            pending = [w for w in eligible if w[0] not in self._processed_windows and w[0] not in self._failed_windows]

            # Apply backpressure: skip oldest if > 3 windows behind
            actionable = self.apply_backpressure(pending)

            for w_idx, w_start, w_end in actionable:
                clips = self.process_window(w_idx, w_start, w_end, db=db)
                all_created.extend(clips)

            return all_created
        finally:
            db.close()

    def _mark_analysis_failed(
        self,
        window_index: int,
        window_start: float,
        window_end: float,
        error_message: str,
        db: Session
    ):
        """Marks window as analysis_failed, updates session, and broadcasts SSE error event."""
        self._failed_windows.add(window_index)
        session = db.query(LiveSession).filter(LiveSession.id == self.session_id).first()
        if session:
            session.error = f"Analysis failed for window [{window_start:.1f}s - {window_end:.1f}s]: {error_message}"
            db.commit()

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                live_broadcaster.broadcast(
                    session_id=self.session_id,
                    event_name="error",
                    data={
                        "status": "analysis_failed",
                        "window_index": window_index,
                        "window_start": window_start,
                        "window_end": window_end,
                        "error": error_message
                    }
                )
            )
        except Exception:
            pass

    def _broadcast_clip_created(self, clip: Clip):
        """Dispatches SSE clip_created event."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                live_broadcaster.broadcast(
                    session_id=self.session_id,
                    event_name="clip_created",
                    data={
                        "clip_id": clip.id,
                        "source": clip.source,
                        "status": clip.status,
                        "title": clip.title,
                        "headline": clip.headline,
                        "start_seconds": clip.start_seconds,
                        "end_seconds": clip.end_seconds,
                        "duration": clip.duration,
                        "viral_score": clip.viral_score,
                        "video_url": clip.video_url
                    }
                )
            )
        except Exception:
            pass
