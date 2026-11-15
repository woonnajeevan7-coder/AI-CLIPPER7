"""
AI Clipper Specialized Agents
Decoupled multi-agent architecture for autonomous video repurposing.
"""

from .transcriber import TranscriberAgent
from .curator import ViralCuratorAgent
from .editor import VideoEditorAgent
from .orchestrator import ClipperOrchestratorAgent
from .judge import JudgeAgent
from .boundary import BoundarySnapper
from .framing import SmartFramingAgent
from .polish import KeywordEmojiTagger, PunchInPlanner, AudioPolisher

__all__ = [
    "TranscriberAgent",
    "ViralCuratorAgent",
    "VideoEditorAgent",
    "ClipperOrchestratorAgent",
    "JudgeAgent",
    "BoundarySnapper",
    "SmartFramingAgent",
    "KeywordEmojiTagger",
    "PunchInPlanner",
    "AudioPolisher",
]
