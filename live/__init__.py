"""
Live Stream Capture Subsystem
Asyncio Stream Recorder and Supervisor for AI-CLIPPER7.
"""

from .recorder import StreamRecorder
from .minute_cutter import MinuteCutter, detect_silences_in_file
from .enhancer import enhance_clip_sync
from .highlights import (
    LiveHighlightsDetector,
    is_duplicate_highlight,
    calculate_combined_viral_score,
)
from .supervisor import (
    LiveSupervisor,
    supervisor,
    LiveDisabledError,
    LowDiskSpaceError,
    PlanLimitExceededError,
    RightsNotConfirmedError,
)

__all__ = [
    "StreamRecorder",
    "MinuteCutter",
    "detect_silences_in_file",
    "enhance_clip_sync",
    "LiveHighlightsDetector",
    "is_duplicate_highlight",
    "calculate_combined_viral_score",
    "LiveSupervisor",
    "supervisor",
    "LiveDisabledError",
    "LowDiskSpaceError",
    "PlanLimitExceededError",
    "RightsNotConfirmedError",
]
