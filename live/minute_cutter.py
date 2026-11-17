"""
Live Minute Cutter Subsystem
Full Clip Every Minute Engine:
- Cuts fixed-interval raw clips tiling the whole stream exactly (no gaps, no overlaps, nothing dropped).
- Optional snap_to_silence (default ON): moves boundary to nearest silence within +/-3s,
  and applies the SAME moved boundary to both clips that share it (clip i end == clip i+1 start).
- Saves RAW cut (stream copy, no re-encode) and inserts Clip(source='fixed', status='raw').
- Unique (live_session_id, clip_index) constraint prevents duplicate clips across restarts.
- Auto enhancement: queues Celery task enhance_fixed_clip_task per clip (auto_enhance=True by default).
- On stop: flushes final partial window as a clip (setting: min_flush_duration=10.0s).
- SSE events: clip_raw_ready, clip_created, error.
"""

import asyncio
import os
import re
import subprocess
import uuid
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import LiveSession, LiveSegment, Clip
from backend.storage import storage, StorageManager
from backend.telemetry import logger
from backend.sse import live_broadcaster
from ffmpeg_utils import get_ffmpeg_bin
from agents.boundary import BoundarySnapper


def detect_silences_in_file(
    media_file: Path,
    ffmpeg_bin: Optional[Path] = None,
    noise_threshold: str = "-30dB",
    min_silence_duration: float = 0.25,
) -> List[Tuple[float, float]]:
    """
    Detects silent pauses within a media file using FFmpeg silencedetect filter.
    Returns list of (start_seconds, end_seconds).
    """
    bin_path = ffmpeg_bin or get_ffmpeg_bin()
    cmd = [
        str(bin_path),
        "-nostdin",
        "-loglevel", "info",
        "-i", str(media_file),
        "-af", f"silencedetect=noise={noise_threshold}:d={min_silence_duration}",
        "-f", "null",
        "-",
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
        output = res.stderr
    except Exception as e:
        logger.warning(f"[MinuteCutter] Silence detect execution warning: {e}")
        return []

    intervals: List[Tuple[float, float]] = []
    cur_start: Optional[float] = None

    for line in output.splitlines():
        if "silence_start:" in line:
            m = re.search(r"silence_start:\s*([0-9.]+)", line)
            if m:
                cur_start = float(m.group(1))
        elif "silence_end:" in line and cur_start is not None:
            m = re.search(r"silence_end:\s*([0-9.]+)", line)
            if m:
                cur_end = float(m.group(1))
                intervals.append((cur_start, cur_end))
                cur_start = None

    return intervals


class MinuteCutter:
    """Monitors live session stream progress and cuts fixed-interval raw clips."""

    def __init__(
        self,
        session_id: str,
        interval_seconds: float = 60.0,
        snap_to_silence: bool = True,
        auto_enhance: bool = True,
        min_flush_duration: float = 10.0,
        storage_mgr: Optional[StorageManager] = None,
        media_root: Optional[Path] = None,
        ffmpeg_bin: Optional[Path] = None,
    ):
        self.session_id = session_id
        self.interval_seconds = float(interval_seconds)
        self.snap_to_silence = snap_to_silence
        self.auto_enhance = auto_enhance
        self.min_flush_duration = float(min_flush_duration)
        self.storage = storage_mgr or storage
        self.media_root = media_root or (Path(__file__).parent.parent / "temp_media" / "live" / session_id)
        self.ffmpeg_bin = ffmpeg_bin or get_ffmpeg_bin()
        self._last_clip_end_seconds: Optional[float] = None

    def _sync_last_clip_end(self, db: Session):
        """Finds the maximum end_seconds of existing clips to ensure zero overlap."""
        last_clip = (
            db.query(Clip)
            .filter(Clip.live_session_id == self.session_id)
            .order_by(Clip.clip_index.desc())
            .first()
        )
        if last_clip:
            self._last_clip_end_seconds = last_clip.end_seconds

    def enqueue_enhancement(self, clip_id: str):
        """Enqueues clip enhancement via Celery, falling back to local sync execution."""
        try:
            from backend.tasks import enhance_fixed_clip_task
            enhance_fixed_clip_task.apply_async(args=[clip_id], retry=False)
            logger.info(f"[MinuteCutter] Enqueued Celery task for clip {clip_id}.")
        except Exception as exc:
            logger.warning(f"[MinuteCutter] Celery enqueue notice ({exc}); attempting local fallback.")
            try:
                from live.enhancer import enhance_clip_sync
                enhance_clip_sync(clip_id)
            except Exception as e:
                logger.error(f"[MinuteCutter] Local enhancement fallback failed: {e}")

    def enhance_pending_clips(self, db: Optional[Session] = None) -> List[Clip]:
        """Finds all clips in this session with status 'raw' or 'enhancing' and executes enhancement."""
        close_db = False
        if db is None:
            db = SessionLocal(expire_on_commit=False)
            close_db = True
        try:
            clips = (
                db.query(Clip)
                .filter(
                    Clip.live_session_id == self.session_id,
                    Clip.status.in_(["raw", "enhancing"]),
                )
                .order_by(Clip.clip_index.asc())
                .all()
            )
            enhanced = []
            for c in clips:
                from live.enhancer import enhance_clip_sync
                res = enhance_clip_sync(c.id)
                if res:
                    enhanced.append(res)
            return enhanced
        finally:
            if close_db:
                db.close()

    def cut_window(
        self,
        clip_index: int,
        window_start: Optional[float] = None,
        window_end: Optional[float] = None,
        db: Optional[Session] = None,
    ) -> Optional[Clip]:
        """
        Cuts clip n covering [t_n, t_{n+1}].
        - Start boundary t_n is taken directly from the previous clip's end_seconds (0.0 for clip 0),
          guaranteeing exact tiling with clip_{n-1} (clip_{n-1}.end == clip_n.start).
        - End boundary t_{n+1} snaps to the nearest silence within +/-3s if snap_to_silence is True,
          and is clamped so that clip length stays within [interval - 3s, interval + 3s].
        - Slices raw cut with stream copy (no re-encode) and commits Clip(source='fixed', status='raw').
        - Broadcasts SSE event 'clip_raw_ready'.
        - If auto_enhance=True, enqueues enhancement.
        """
        close_db_on_exit = False
        if db is None:
            db = SessionLocal(expire_on_commit=False)
            close_db_on_exit = True

        try:
            # 1. Unique constraint check: Skip if already cut
            existing = (
                db.query(Clip)
                .filter(
                    Clip.live_session_id == self.session_id,
                    Clip.clip_index == clip_index,
                )
                .first()
            )
            if existing:
                if self._last_clip_end_seconds is None or existing.end_seconds > self._last_clip_end_seconds:
                    self._last_clip_end_seconds = existing.end_seconds
                return existing

            # 2. Determine start boundary: Shared with previous clip's end_seconds
            if clip_index == 0:
                snapped_start = 0.0
            else:
                prev_clip = (
                    db.query(Clip)
                    .filter(
                        Clip.live_session_id == self.session_id,
                        Clip.clip_index == clip_index - 1,
                    )
                    .first()
                )
                if prev_clip:
                    snapped_start = prev_clip.end_seconds
                elif self._last_clip_end_seconds is not None:
                    snapped_start = self._last_clip_end_seconds
                else:
                    snapped_start = window_start if window_start is not None else float(clip_index * self.interval_seconds)

            nominal_end = window_end if window_end is not None else float((clip_index + 1) * self.interval_seconds)

            # 3. Locate matching LiveSegments
            search_start = max(0.0, snapped_start - 0.5)
            search_end = nominal_end + 3.5

            segments = (
                db.query(LiveSegment)
                .filter(
                    LiveSegment.session_id == self.session_id,
                    LiveSegment.end_seconds >= search_start,
                    LiveSegment.start_seconds <= search_end,
                )
                .order_by(LiveSegment.segment_index.asc())
                .all()
            )

            valid_segments = [s for s in segments if Path(s.file_path).exists() and Path(s.file_path).stat().st_size > 0]
            if not valid_segments:
                logger.warning(
                    f"[MinuteCutter] No valid segment files on disk for session {self.session_id} window {clip_index}."
                )
                return None

            first_seg_start = valid_segments[0].start_seconds

            work_dir = self.media_root / "cutter_tmp"
            work_dir.mkdir(parents=True, exist_ok=True)

            # 4. Concatenate segments using FFmpeg concat demuxer (stream copy)
            concat_txt = work_dir / f"concat_win_{clip_index:04d}_{uuid.uuid4().hex[:6]}.txt"
            merged_ts = work_dir / f"merged_win_{clip_index:04d}_{uuid.uuid4().hex[:6]}.ts"

            with open(concat_txt, "w", encoding="utf-8") as f:
                for s in valid_segments:
                    safe_path = Path(s.file_path).resolve().as_posix()
                    f.write(f"file '{safe_path}'\n")

            concat_cmd = [
                str(self.ffmpeg_bin),
                "-nostdin",
                "-loglevel", "warning",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_txt),
                "-c", "copy",
                "-y",
                str(merged_ts),
            ]
            concat_res = subprocess.run(concat_cmd, capture_output=True, text=True)
            if concat_res.returncode != 0 or not merged_ts.exists() or merged_ts.stat().st_size == 0:
                logger.error(f"[MinuteCutter] Concat failed: {concat_res.stderr}")
                return None

            # 5. Snap end boundary to silence within +/-3s if enabled
            snapped_end = nominal_end
            if self.snap_to_silence:
                rel_silences = detect_silences_in_file(merged_ts, ffmpeg_bin=self.ffmpeg_bin)
                abs_silences = [
                    (round(s + first_seg_start, 2), round(e + first_seg_start, 2))
                    for (s, e) in rel_silences
                ]
                candidates = [
                    round((s + e) / 2.0, 2)
                    for (s, e) in abs_silences
                    if abs(((s + e) / 2.0) - nominal_end) <= 3.0
                ]
                if candidates:
                    best_cand = min(candidates, key=lambda c: abs(c - nominal_end))
                    snapped_end = best_cand

                # Clamp end so duration stays within interval +/- 3s
                min_end = round(snapped_start + max(1.0, self.interval_seconds - 3.0), 2)
                max_end = round(snapped_start + self.interval_seconds + 3.0, 2)
                snapped_end = max(min_end, min(max_end, snapped_end))

            snapped_start = round(snapped_start, 2)
            snapped_end = round(snapped_end, 2)
            clip_duration = round(snapped_end - snapped_start, 2)

            # 6. Stream copy cut into final MP4 (no re-encode)
            rel_start = max(0.0, snapped_start - first_seg_start)
            rel_duration = max(0.5, clip_duration)

            raw_clip_filename = f"raw_clip_{clip_index:05d}_{uuid.uuid4().hex[:6]}.mp4"
            raw_clip_path = work_dir / raw_clip_filename

            cut_cmd = [
                str(self.ffmpeg_bin),
                "-nostdin",
                "-loglevel", "warning",
                "-ss", f"{rel_start:.3f}",
                "-t", f"{rel_duration:.3f}",
                "-i", str(merged_ts),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                "-y",
                str(raw_clip_path),
            ]
            cut_res = subprocess.run(cut_cmd, capture_output=True, text=True)
            if cut_res.returncode != 0 or not raw_clip_path.exists() or raw_clip_path.stat().st_size == 0:
                logger.error(f"[MinuteCutter] Raw stream copy cut failed: {cut_res.stderr}")
                return None

            # 7. Save via storage.py
            r2_key = f"live/{self.session_id}/raw_clips/clip_{clip_index:05d}.mp4"
            stored_url = self.storage.upload_file(raw_clip_path, r2_key)

            # 8. Insert Clip(source="fixed", status="raw")
            clip = Clip(
                id=str(uuid.uuid4()),
                live_session_id=self.session_id,
                clip_index=clip_index,
                source="fixed",
                status="raw",
                title=f"Raw Stream Cut #{clip_index + 1}",
                headline=f"Live Moment #{clip_index + 1}",
                start_seconds=snapped_start,
                end_seconds=snapped_end,
                duration=clip_duration,
                video_url=stored_url,
                r2_key=r2_key,
                viral_score=85,
            )
            db.add(clip)
            db.commit()
            db.refresh(clip)

            self._last_clip_end_seconds = snapped_end

            # 9. Clean up temporary working files
            try:
                if concat_txt.exists():
                    concat_txt.unlink()
                if merged_ts.exists():
                    merged_ts.unlink()
                if raw_clip_path.exists():
                    raw_clip_path.unlink()
            except Exception:
                pass

            # 10. Broadcast SSE events
            self._broadcast_clip_raw_ready(clip)

            # 11. Auto-enhancement: Trigger Celery enhancement task
            if self.auto_enhance:
                self.enqueue_enhancement(clip.id)

            logger.info(
                f"[MinuteCutter] Created raw clip #{clip_index} for session {self.session_id}: "
                f"[{snapped_start:.2f}s -> {snapped_end:.2f}s] ({clip.duration:.2f}s)"
            )
            return clip

        except IntegrityError:
            db.rollback()
            logger.info(f"[MinuteCutter] Clip #{clip_index} already committed by another worker.")
            return (
                db.query(Clip)
                .filter(
                    Clip.live_session_id == self.session_id,
                    Clip.clip_index == clip_index,
                )
                .first()
            )
        except Exception as exc:
            db.rollback()
            logger.error(f"[MinuteCutter] Error cutting window {clip_index}: {exc}")
            self._broadcast_error(str(exc))
            return None
        finally:
            if close_db_on_exit:
                db.close()

    def flush_final_window(
        self,
        min_duration: Optional[float] = None,
        db: Optional[Session] = None,
    ) -> Optional[Clip]:
        """
        Flushes the final partial window as a clip when stream stops (setting: min 10s).
        Enforces continuous boundary tiling with the last cut clip.
        """
        min_dur = min_duration if min_duration is not None else self.min_flush_duration
        close_db_on_exit = False
        if db is None:
            db = SessionLocal(expire_on_commit=False)
            close_db_on_exit = True

        try:
            segments = (
                db.query(LiveSegment)
                .filter(LiveSegment.session_id == self.session_id)
                .order_by(LiveSegment.segment_index.asc())
                .all()
            )
            if not segments:
                return None

            stream_end = max(s.end_seconds for s in segments)

            last_clip = (
                db.query(Clip)
                .filter(Clip.live_session_id == self.session_id)
                .order_by(Clip.clip_index.desc())
                .first()
            )

            last_end = last_clip.end_seconds if last_clip else 0.0
            next_index = (last_clip.clip_index + 1) if last_clip else 0

            remaining_duration = round(stream_end - last_end, 2)
            if remaining_duration < min_dur:
                logger.info(
                    f"[MinuteCutter] Remaining stream time {remaining_duration:.2f}s < min {min_dur:.2f}s; "
                    "skipping final partial window flush."
                )
                return None

            logger.info(
                f"[MinuteCutter] Flushing final partial window #{next_index}: "
                f"[{last_end:.2f}s -> {stream_end:.2f}s] ({remaining_duration:.2f}s)"
            )

            # Cut without silence snapping to preserve full stream tail
            return self._cut_slice(
                clip_index=next_index,
                start_sec=last_end,
                end_sec=stream_end,
                db=db,
            )
        finally:
            if close_db_on_exit:
                db.close()

    def _cut_slice(
        self,
        clip_index: int,
        start_sec: float,
        end_sec: float,
        db: Session,
    ) -> Optional[Clip]:
        """Internal helper to slice and save a raw clip between exact stream-time boundaries."""
        try:
            existing = (
                db.query(Clip)
                .filter(
                    Clip.live_session_id == self.session_id,
                    Clip.clip_index == clip_index,
                )
                .first()
            )
            if existing:
                return existing

            segments = (
                db.query(LiveSegment)
                .filter(
                    LiveSegment.session_id == self.session_id,
                    LiveSegment.end_seconds >= start_sec - 0.5,
                    LiveSegment.start_seconds <= end_sec + 0.5,
                )
                .order_by(LiveSegment.segment_index.asc())
                .all()
            )

            valid_segments = [s for s in segments if Path(s.file_path).exists() and Path(s.file_path).stat().st_size > 0]
            if not valid_segments:
                return None

            first_seg_start = valid_segments[0].start_seconds
            work_dir = self.media_root / "cutter_tmp"
            work_dir.mkdir(parents=True, exist_ok=True)

            concat_txt = work_dir / f"concat_flush_{clip_index:04d}_{uuid.uuid4().hex[:6]}.txt"
            merged_ts = work_dir / f"merged_flush_{clip_index:04d}_{uuid.uuid4().hex[:6]}.ts"

            with open(concat_txt, "w", encoding="utf-8") as f:
                for s in valid_segments:
                    safe_path = Path(s.file_path).resolve().as_posix()
                    f.write(f"file '{safe_path}'\n")

            concat_cmd = [
                str(self.ffmpeg_bin),
                "-nostdin",
                "-loglevel", "warning",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_txt),
                "-c", "copy",
                "-y",
                str(merged_ts),
            ]
            concat_res = subprocess.run(concat_cmd, capture_output=True, text=True)
            if concat_res.returncode != 0 or not merged_ts.exists():
                return None

            rel_start = max(0.0, start_sec - first_seg_start)
            rel_duration = max(0.5, end_sec - start_sec)
            raw_clip_filename = f"raw_clip_{clip_index:05d}_{uuid.uuid4().hex[:6]}.mp4"
            raw_clip_path = work_dir / raw_clip_filename

            cut_cmd = [
                str(self.ffmpeg_bin),
                "-nostdin",
                "-loglevel", "warning",
                "-ss", f"{rel_start:.3f}",
                "-t", f"{rel_duration:.3f}",
                "-i", str(merged_ts),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                "-y",
                str(raw_clip_path),
            ]
            cut_res = subprocess.run(cut_cmd, capture_output=True, text=True)
            if cut_res.returncode != 0 or not raw_clip_path.exists() or raw_clip_path.stat().st_size == 0:
                return None

            r2_key = f"live/{self.session_id}/raw_clips/clip_{clip_index:05d}.mp4"
            stored_url = self.storage.upload_file(raw_clip_path, r2_key)

            clip = Clip(
                id=str(uuid.uuid4()),
                live_session_id=self.session_id,
                clip_index=clip_index,
                source="fixed",
                status="raw",
                title=f"Raw Stream Cut #{clip_index + 1}",
                headline=f"Live Moment #{clip_index + 1}",
                start_seconds=start_sec,
                end_seconds=end_sec,
                duration=round(end_sec - start_sec, 2),
                video_url=stored_url,
                r2_key=r2_key,
                viral_score=85,
            )
            db.add(clip)
            db.commit()
            db.refresh(clip)

            self._last_clip_end_seconds = end_sec

            try:
                if concat_txt.exists():
                    concat_txt.unlink()
                if merged_ts.exists():
                    merged_ts.unlink()
                if raw_clip_path.exists():
                    raw_clip_path.unlink()
            except Exception:
                pass

            self._broadcast_clip_raw_ready(clip)

            if self.auto_enhance:
                self.enqueue_enhancement(clip.id)

            return clip

        except IntegrityError:
            db.rollback()
            return (
                db.query(Clip)
                .filter(
                    Clip.live_session_id == self.session_id,
                    Clip.clip_index == clip_index,
                )
                .first()
            )
        except Exception as e:
            db.rollback()
            logger.error(f"[MinuteCutter] Error slicing clip {clip_index}: {e}")
            return None

    def check_and_cut_windows(self) -> List[Clip]:
        """
        Scans recorded segments, determines current stream time,
        and cuts all crossed multiples of INTERVAL.
        """
        db = SessionLocal(expire_on_commit=False)
        created_clips: List[Clip] = []
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
            num_windows = int(current_stream_time // self.interval_seconds)

            for k in range(num_windows):
                w_start = k * self.interval_seconds
                w_end = (k + 1) * self.interval_seconds
                clip = self.cut_window(clip_index=k, window_start=w_start, window_end=w_end, db=db)
                if clip:
                    created_clips.append(clip)

            return created_clips
        finally:
            db.close()

    def _broadcast_clip_raw_ready(self, clip: Clip):
        """Asynchronously dispatches SSE events 'clip_raw_ready' and 'clip_created'."""
        data = {
            "clip_id": clip.id,
            "clip_index": clip.clip_index,
            "source": clip.source,
            "status": clip.status,
            "start_seconds": clip.start_seconds,
            "end_seconds": clip.end_seconds,
            "duration": clip.duration,
            "video_url": clip.video_url,
        }
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(live_broadcaster.broadcast(session_id=self.session_id, event_name="clip_raw_ready", data=data))
            loop.create_task(live_broadcaster.broadcast(session_id=self.session_id, event_name="clip_created", data=data))
        except RuntimeError:
            try:
                asyncio.run(live_broadcaster.broadcast(session_id=self.session_id, event_name="clip_raw_ready", data=data))
                asyncio.run(live_broadcaster.broadcast(session_id=self.session_id, event_name="clip_created", data=data))
            except Exception:
                pass

    def _broadcast_error(self, message: str):
        """Asynchronously dispatches SSE event 'error'."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                live_broadcaster.broadcast(
                    session_id=self.session_id,
                    event_name="error",
                    data={"session_id": self.session_id, "error": message},
                )
            )
        except RuntimeError:
            try:
                asyncio.run(
                    live_broadcaster.broadcast(
                        session_id=self.session_id,
                        event_name="error",
                        data={"session_id": self.session_id, "error": message},
                    )
                )
            except Exception:
                pass
