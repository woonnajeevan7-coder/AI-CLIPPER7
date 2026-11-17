"""
Live Stream Supervisor (Asyncio)
Coordinates long-lived stream recorders outside Celery.
Enforces:
1. Kill switch: LIVE_ENABLED
2. Disk guard: minimum free disk space check (>= 5 GB)
3. Concurrency limits per subscription plan
4. Mandatory rights_confirmed verification on external streams
5. Auto-reconnect with exponential backoff & gap logging
6. 15-minute rolling buffer cleanup to prevent disk bloat
7. Safe shutdown with zero orphan FFmpeg processes
"""

import asyncio
import os
import secrets
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any, List

from backend.config import settings
from backend.database import SessionLocal
from backend.models import User, LiveSession, LiveSegment
from backend.telemetry import logger
from .recorder import StreamRecorder


class LiveDisabledError(RuntimeError):
    """Raised when live streaming is disabled via system kill switch (LIVE_ENABLED=false)."""
    pass


class LowDiskSpaceError(RuntimeError):
    """Raised when available disk space is below safety threshold (< 5 GB)."""
    pass


class PlanLimitExceededError(PermissionError):
    """Raised when active sessions exceed user's subscription tier quota."""
    pass


class RightsNotConfirmedError(PermissionError):
    """Raised when attempting to capture an external stream without explicit rights confirmation."""
    pass


class LiveSupervisor:
    """Asyncio process supervisor managing active StreamRecorder instances."""

    def __init__(self, media_root: Optional[Path] = None):
        self.media_root = media_root or (Path(__file__).parent.parent / "temp_media" / "live")
        self.media_root.mkdir(parents=True, exist_ok=True)
        # In-memory registry: session_id -> { "recorder": StreamRecorder, "task": asyncio.Task, "stop_event": asyncio.Event }
        self._active_sessions: Dict[str, Dict[str, Any]] = {}

    def is_session_active(self, session_id: str) -> bool:
        return session_id in self._active_sessions

    def check_system_guards(self, user_id: str, is_external: bool, rights_confirmed: bool):
        """Validates kill switch, disk space, plan limits, and broadcast rights."""
        # 1. Kill switch
        if not settings.LIVE_ENABLED:
            raise LiveDisabledError("Live stream recording is currently disabled by system administrator (LIVE_ENABLED=false).")

        # 2. Disk guard
        free_bytes = shutil.disk_usage(self.media_root).free
        free_gb = free_bytes / (1024 ** 3)
        if free_gb < settings.MIN_DISK_FREE_GB:
            raise LowDiskSpaceError(
                f"Refusing to start recording: free disk space ({free_gb:.2f} GB) is below minimum required {settings.MIN_DISK_FREE_GB} GB."
            )

        # 3. Plan concurrency limits
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            user_plan = user.plan if user else "free"
            plan_cfg = settings.PLAN_LIMITS.get(user_plan, settings.PLAN_LIMITS["free"])
            max_concurrent = plan_cfg.get("max_concurrent_jobs", 1)

            active_count = db.query(LiveSession).filter(
                LiveSession.user_id == user_id,
                LiveSession.status.in_(["starting", "live", "reconnecting"])
            ).count()

            if active_count >= max_concurrent:
                raise PlanLimitExceededError(
                    f"User plan '{user_plan}' allows a maximum of {max_concurrent} concurrent live sessions (currently active: {active_count})."
                )
        finally:
            db.close()

        # 4. Rights confirmation on external feeds
        if is_external and not rights_confirmed:
            raise RightsNotConfirmedError(
                "Authorized streams only: external stream capture requires explicit broadcast rights confirmation (rights_confirmed=true)."
            )

    def resolve_stream_source(self, session: LiveSession) -> str:
        """
        Resolves stream input:
        - Source A (default, own streams): RTMP ingest from MediaMTX (rtmp://host/live/<stream_key>)
        - Source B (external feeds): streamlink resolution of HLS manifest
        """
        if session.source_type == "streamlink" or session.platform in ("twitch", "youtube_live"):
            # Resolve HLS via streamlink if available
            try:
                cmd = ["streamlink", "--stream-url", session.stream_url, "best"]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
                if res.returncode == 0 and res.stdout.strip().startswith("http"):
                    return res.stdout.strip()
            except Exception as e:
                logger.warning(f"[LiveSupervisor] streamlink resolution notice: {e}. Falling back to direct URL.")
            return session.stream_url

        # Source A: RTMP ingest with per-session random stream key
        if not session.stream_key:
            session.stream_key = secrets.token_urlsafe(24)
        rtmp_base = settings.RTMP_BASE_URL.rstrip("/")
        return f"{rtmp_base}/{session.stream_key}"

    async def start_session(
        self,
        session_id: str,
        custom_input_source: Optional[str] = None,
        max_reconnect_attempts: int = 10,
        reconnect_delay_base: float = 1.0,
        input_args: Optional[List[str]] = None,
        segment_duration: Optional[float] = None,
    ) -> LiveSession:
        """Starts the supervised live recording session loop."""
        db = SessionLocal()
        try:
            session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
            if not session:
                raise ValueError(f"LiveSession '{session_id}' not found.")

            is_external = (session.platform != "rtmp" and session.source_type != "rtmp")
            self.check_system_guards(
                user_id=session.user_id,
                is_external=is_external,
                rights_confirmed=session.rights_confirmed
            )

            # Resolve input source
            input_source = custom_input_source or self.resolve_stream_source(session)
            session.stream_url = input_source
            session.status = "live"
            session.started_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(session)
        finally:
            db.close()

        session_dir = self.media_root / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        stop_event = asyncio.Event()
        supervisor_task = asyncio.create_task(
            self._supervised_recording_loop(
                session_id=session_id,
                input_source=input_source,
                output_dir=session_dir,
                stop_event=stop_event,
                max_reconnect_attempts=max_reconnect_attempts,
                reconnect_delay_base=reconnect_delay_base,
                input_args=input_args,
                segment_duration=segment_duration,
            )
        )

        self._active_sessions[session_id] = {
            "task": supervisor_task,
            "stop_event": stop_event,
            "session_dir": session_dir,
            "recorder": None,
        }

        return session

    async def _on_segment_ready(self, session_id: str, segment_index: int, segment_path: Path):
        """Persists LiveSegment row with stream-time offset and performs rolling buffer pruning."""
        db = SessionLocal()
        try:
            duration = settings.LIVE_SEGMENT_DURATION_SECONDS
            start_sec = round(segment_index * duration, 3)
            end_sec = round((segment_index + 1) * duration, 3)

            seg = LiveSegment(
                session_id=session_id,
                segment_index=segment_index,
                file_path=str(segment_path.resolve()),
                start_seconds=start_sec,
                end_seconds=end_sec,
                duration=duration,
                status="recorded"
            )
            db.add(seg)

            session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
            if session:
                session.total_segments_recorded = (session.total_segments_recorded or 0) + 1
                buffer_minutes = session.rolling_buffer_minutes or settings.LIVE_ROLLING_BUFFER_MINUTES
            else:
                buffer_minutes = settings.LIVE_ROLLING_BUFFER_MINUTES

            db.commit()

            # Rolling buffer maintenance: Prune old .ts segments on disk exceeding buffer window
            retention_segments = int((buffer_minutes * 60) / duration)
            cutoff_index = segment_index - retention_segments
            if cutoff_index > 0:
                old_file = segment_path.parent / f"seg_{cutoff_index:05d}.ts"
                if old_file.exists():
                    try:
                        old_file.unlink()
                        logger.info(f"[LiveSupervisor] Pruned expired rolling segment: {old_file.name}")
                    except Exception as e:
                        logger.warning(f"[LiveSupervisor] Could not prune {old_file.name}: {e}")

        except Exception as exc:
            db.rollback()
            logger.error(f"[LiveSupervisor] Error persisting segment {segment_index}: {exc}")
        finally:
            db.close()

    async def _supervised_recording_loop(
        self,
        session_id: str,
        input_source: str,
        output_dir: Path,
        stop_event: asyncio.Event,
        max_reconnect_attempts: int = 10,
        reconnect_delay_base: float = 1.0,
        input_args: Optional[List[str]] = None,
        segment_duration: Optional[float] = None,
    ):
        """Auto-reconnecting supervisor loop with gap logging and exponential backoff."""
        reconnect_attempts = 0
        last_healthy_time = time.time()
        seg_dur = segment_duration or settings.LIVE_SEGMENT_DURATION_SECONDS

        while not stop_event.is_set():
            recorder = StreamRecorder(
                session_id=session_id,
                input_source=input_source,
                output_dir=output_dir,
                segment_duration=seg_dur,
                input_args=input_args,
                on_segment_completed=lambda idx, p: self._on_segment_ready(session_id, idx, p),
            )
            if session_id in self._active_sessions:
                self._active_sessions[session_id]["recorder"] = recorder

            try:
                await recorder.start()
                returncode = await recorder.wait()
            except Exception as exc:
                logger.error(f"[LiveSupervisor] Recorder crash for session {session_id}: {exc}")
                returncode = -1

            if stop_event.is_set():
                break

            # Process exited unexpectedly -> Stream gap detected
            now = time.time()
            gap_duration = now - last_healthy_time
            reconnect_attempts += 1

            logger.warning(
                f"[LiveSupervisor] Gap detected on session {session_id}! Stream down for {gap_duration:.1f}s. "
                f"Reconnect attempt {reconnect_attempts}/{max_reconnect_attempts}."
            )

            # Update session status to reconnecting in DB
            db = SessionLocal()
            try:
                s = db.query(LiveSession).filter(LiveSession.id == session_id).first()
                if s:
                    s.status = "reconnecting"
                    db.commit()
            finally:
                db.close()

            if reconnect_attempts > max_reconnect_attempts:
                logger.error(f"[LiveSupervisor] Exceeded max reconnect attempts for {session_id}. Halting.")
                db = SessionLocal()
                try:
                    s = db.query(LiveSession).filter(LiveSession.id == session_id).first()
                    if s:
                        s.status = "failed"
                        s.error = f"Stream failed after {max_reconnect_attempts} reconnect attempts."
                        db.commit()
                finally:
                    db.close()
                break

            # Exponential backoff: min(30s, base * 2^attempt)
            delay = min(30.0, reconnect_delay_base * (2 ** (reconnect_attempts - 1)))
            logger.info(f"[LiveSupervisor] Sleeping {delay:.1f}s before reconnecting...")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
                break
            except asyncio.TimeoutError:
                pass

        logger.info(f"[LiveSupervisor] Supervised loop ended for session {session_id}.")

    async def stop_session(self, session_id: str):
        """Stops the active supervisor and terminates FFmpeg with zero orphan processes."""
        session_info = self._active_sessions.pop(session_id, None)
        if not session_info:
            return

        session_info["stop_event"].set()
        recorder: Optional[StreamRecorder] = session_info.get("recorder")
        if recorder:
            await recorder.stop(timeout_seconds=5.0)

        task: Optional[asyncio.Task] = session_info.get("task")
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Flush final partial window if >= min_flush_duration (default 10s)
        try:
            from .minute_cutter import MinuteCutter
            cutter = MinuteCutter(session_id=session_id)
            cutter.flush_final_window(min_duration=10.0)
        except Exception as e:
            logger.warning(f"[LiveSupervisor] Notice flushing final window on stop: {e}")

        # Update database status to stopped
        db = SessionLocal()
        try:
            session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
            if session:
                session.status = "stopped"
                session.stopped_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.close()

        logger.info(f"[LiveSupervisor] LiveSession {session_id} cleanly stopped with zero orphan processes.")


supervisor = LiveSupervisor()
