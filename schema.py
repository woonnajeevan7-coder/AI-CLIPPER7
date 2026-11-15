"""
AI Clipper Core Typed Schemas
Decoupled typed communication contracts across all agents.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class WordTimestamp(BaseModel):
    """Word-level timing contract."""
    word: str
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


class CaptionSegment(BaseModel):
    """Group of words displayed together in a caption line."""
    words: List[WordTimestamp]
    start: float
    end: float
    text: str


class ClipMetadata(BaseModel):
    """Structured clip candidate contract."""
    title: str
    headline: str
    start_seconds: float
    end_seconds: float
    duration: float
    viral_score: int = Field(ge=0, le=100)
    hook: str
    reason: str
    words: Optional[List[WordTimestamp]] = Field(default_factory=list)


class PipelineEvent(BaseModel):
    """Event schema for streaming agent progress."""
    step: int
    agent: str
    status: str
    progress: int = Field(ge=0, le=100)
    error: Optional[str] = None
    result: Optional[Any] = None
