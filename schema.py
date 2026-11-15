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


class HeadlineVariants(BaseModel):
    """3 high-converting headline variants generated for a clip."""
    curiosity: str = Field(..., description="Curiosity-inducing headline")
    value: str = Field(..., description="Clear takeaway / lesson-oriented headline")
    bold_claim: str = Field(..., description="High-impact bold assertion headline")
    chosen: str = Field(..., description="The highest-converting variant chosen for the banner")


class RubricScore(BaseModel):
    """JudgeAgent 4-factor scoring rubric out of 100."""
    hook_strength: int = Field(..., ge=0, le=25, description="First 3 seconds scroll-stopping power (0-25)")
    self_contained: int = Field(..., ge=0, le=25, description="Complete thought/story arch without missing context (0-25)")
    payoff: int = Field(..., ge=0, le=25, description="High emotional or informational climax/resolution (0-25)")
    zero_context_needed: int = Field(..., ge=0, le=25, description="Viewer doesn't need to know who speaker is (0-25)")
    total_score: int = Field(..., ge=0, le=100, description="Sum of rubric factors (0-100)")
    critique: str = Field(..., description="Reasoning justifying the rubric scores")


class CandidateClip(BaseModel):
    """Pass-1 Candidate clip proposed by Generator."""
    candidate_id: int
    title: str
    start_seconds: float
    end_seconds: float
    duration: float
    initial_score: int = Field(..., ge=0, le=100)
    hook: str
    reason: str


class CropPlan(BaseModel):
    """Smart framing crop layout produced by SmartFramingAgent."""
    layout: str = Field(..., description="'single_face', 'split_screen', or 'blur_fallback'")
    face_count: int = Field(default=0)
    scene_cuts: List[float] = Field(default_factory=list)
    crop_x: Optional[int] = None
    crop_y: Optional[int] = None
    crop_w: Optional[int] = None
    crop_h: Optional[int] = None
    split_top_x: Optional[int] = None
    split_bottom_x: Optional[int] = None
    filter_string: str = Field(..., description="FFmpeg video filter string for the layout")


class AudioSignals(BaseModel):
    """Multimodal audio signals extracted via librosa / scipy."""
    energy_peaks: List[float] = Field(default_factory=list, description="Timestamps of highest vocal energy / volume bursts")
    laughter_spikes: List[float] = Field(default_factory=list, description="Timestamps of detected laughter or crowd resonance")
    avg_speech_rate_wps: float = Field(default=2.5, description="Average words per second")
    summary_text: str = Field(default="", description="Summary formatted for LLM prompt ingestion")


class ClipMetadata(BaseModel):
    """Final Curated Clip contract passed to Editor."""
    title: str
    headline: str
    start_seconds: float
    end_seconds: float
    duration: float
    viral_score: int = Field(ge=0, le=100)
    hook: str
    reason: str
    headline_variants: Optional[HeadlineVariants] = None
    rubric: Optional[RubricScore] = None
    words: Optional[List[WordTimestamp]] = Field(default_factory=list)


class PipelineEvent(BaseModel):
    """Event schema for streaming agent progress."""
    step: int
    agent: str
    status: str
    progress: int = Field(ge=0, le=100)
    error: Optional[str] = None
    result: Optional[Any] = None
