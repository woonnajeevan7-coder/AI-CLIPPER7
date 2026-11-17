"""
Live Stream Recorder Engine
Runs low-level FFmpeg subprocesses to ingest RTMP / HLS live video streams,
slices them into 6-second MPEG-TS segments with -c copy, and prevents orphan processes.
"""

import asyncio
import os
import re
import signal
from pathlib import Path
from typing import Optional, Callable, Awaitable, List

from ffmpeg_utils import get_ffmpeg_bin
from backend.telemetry import logger


class StreamRecorder:
    """Manages an individual FFmpeg segmentation recording subprocess."""

    def __init__(
        self,
        session_id: str,
        input_source: str,
        output_dir: Path,
        segment_duration: float = 6.0,
        on_segment_completed: Optional[Callable[[int, Path], Awaitable[None]]] = None,
        ffmpeg_bin: Optional[Path] = None,
        input_args: Optional[List[str]] = None,
    ):
        self.session_id = session_id
        self.input_source = input_source
        self.output_dir = output_dir
        self.segment_duration = segment_duration
        self.on_segment_completed = on_segment_completed
        self.ffmpeg_bin = ffmpeg_bin or get_ffmpeg_bin()
        self.input_args = input_args or []
        self.output_pattern = self.output_dir / "seg_%05d.ts"

        self._process: Optional[asyncio.subprocess.Process] = None
        self._monitor_task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        self._completed_segments: set[int] = set()

    @property
    def is_running(self) -> bool:
        return self._is_running and self._process is not None and self._process.returncode is None

    @property
    def pid(self) -> Optional[int]:
        return self._process.pid if self._process else None

    async def start(self):
        """Starts the FFmpeg segmenter subprocess and directory watcher."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(self.ffmpeg_bin),
            "-nostdin",
            "-loglevel", "warning",
            "-re",
        ]
        if self.input_args:
            cmd.extend(self.input_args)
        cmd.extend([
            "-i", str(self.input_source),
            "-c", "copy",
            "-f", "segment",
            "-segment_time", str(self.segment_duration),
            "-segment_format", "mpegts",
            "-reset_timestamps", "1",
            "-strftime", "0",
            "-y",
            str(self.output_pattern),
        ])

        logger.info(f"[StreamRecorder] Launching FFmpeg for session {self.session_id}: {' '.join(cmd)}")
        self._process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        self._is_running = True
        self._monitor_task = asyncio.create_task(self._monitor_segments())

    async def _monitor_segments(self):
        """Polls directory for finalized .ts files and invokes completion callback."""
        seg_regex = re.compile(r"^seg_(\d{5})\.ts$")

        try:
            while self._is_running:
                await asyncio.sleep(0.5)
                # Find all current segment files
                try:
                    files = sorted(self.output_dir.glob("seg_*.ts"))
                except Exception:
                    continue

                if not files:
                    continue

                # In segment muxer, seg_N is fully written once seg_{N+1} exists
                # or when FFmpeg process terminates.
                for i in range(len(files) - 1):
                    f = files[i]
                    match = seg_regex.match(f.name)
                    if match:
                        idx = int(match.group(1))
                        if idx not in self._completed_segments and f.stat().st_size > 0:
                            self._completed_segments.add(idx)
                            if self.on_segment_completed:
                                try:
                                    await self.on_segment_completed(idx, f)
                                except Exception as exc:
                                    logger.error(f"[StreamRecorder] Error in segment callback: {exc}")

                # Check if process exited
                if self._process and self._process.returncode is not None:
                    # Final segment is now complete
                    if files:
                        last_file = files[-1]
                        match = seg_regex.match(last_file.name)
                        if match:
                            idx = int(match.group(1))
                            if idx not in self._completed_segments and last_file.stat().st_size > 0:
                                self._completed_segments.add(idx)
                                if self.on_segment_completed:
                                    try:
                                        await self.on_segment_completed(idx, last_file)
                                    except Exception as exc:
                                        logger.error(f"[StreamRecorder] Error in final segment callback: {exc}")
                    break
        except asyncio.CancelledError:
            pass

    async def wait(self) -> int:
        """Awaits FFmpeg process completion and returns returncode."""
        if not self._process:
            return 0
        return await self._process.wait()

    async def stop(self, timeout_seconds: float = 5.0):
        """
        Gracefully terminates the FFmpeg subprocess with zero orphan processes.
        Sends SIGTERM, waits up to timeout_seconds, and forces SIGKILL if necessary.
        """
        self._is_running = False

        if self._process and self._process.returncode is None:
            logger.info(f"[StreamRecorder] Terminating FFmpeg process (PID {self._process.pid})...")
            try:
                self._process.terminate()
            except ProcessLookupError:
                pass

            try:
                await asyncio.wait_for(self._process.wait(), timeout=timeout_seconds)
                logger.info(f"[StreamRecorder] FFmpeg (PID {self._process.pid}) terminated gracefully.")
            except asyncio.TimeoutError:
                logger.warning(f"[StreamRecorder] FFmpeg (PID {self._process.pid}) did not exit; sending SIGKILL.")
                try:
                    self._process.kill()
                    await self._process.wait()
                except ProcessLookupError:
                    pass

        # Allow monitor task a brief window to capture final segment before cancellation
        if self._monitor_task and not self._monitor_task.done():
            try:
                await asyncio.wait_for(self._monitor_task, timeout=1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._monitor_task.cancel()
