"""
Cross-platform FFmpeg and FFprobe binary path resolver using shutil.which.
Ensures seamless operation on Windows, Linux, and macOS in local and CI environments.
"""

import shutil
from pathlib import Path
from typing import Optional


def get_ffmpeg_bin(project_root: Optional[Path] = None) -> Path:
    """Resolves the FFmpeg binary path via system PATH (shutil.which) with local fallbacks."""
    system_path = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if system_path:
        return Path(system_path).resolve()

    if project_root:
        for name in ("ffmpeg", "ffmpeg.exe"):
            candidate = project_root / name
            if candidate.exists():
                return candidate.resolve()

    for name in ("ffmpeg", "ffmpeg.exe"):
        local = Path(name)
        if local.exists():
            return local.resolve()

    return Path("ffmpeg")


def get_ffprobe_bin(project_root: Optional[Path] = None) -> Path:
    """Resolves the FFprobe binary path via system PATH (shutil.which) with local fallbacks."""
    system_path = shutil.which("ffprobe") or shutil.which("ffprobe.exe")
    if system_path:
        return Path(system_path).resolve()

    if project_root:
        for name in ("ffprobe", "ffprobe.exe"):
            candidate = project_root / name
            if candidate.exists():
                return candidate.resolve()

    for name in ("ffprobe", "ffprobe.exe"):
        local = Path(name)
        if local.exists():
            return local.resolve()

    return Path("ffprobe")
