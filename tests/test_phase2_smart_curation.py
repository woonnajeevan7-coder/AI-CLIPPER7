"""
Phase 2 Verification Tests: Smart Curation
Tests boundary snapping, multimodal audio signals, two-pass judge evaluation, and Pydantic validation.
"""

from pathlib import Path
import pytest
from schema import WordTimestamp, CandidateClip, RubricScore, HeadlineVariants, ClipMetadata, AudioSignals
from agents.boundary import BoundarySnapper
from agents.judge import JudgeAgent
from agents.curator import ViralCuratorAgent
from audio_signals import AudioSignalAnalyzer


def test_boundary_snapping_sentence_and_pause():
    words = [
        WordTimestamp(word="Hey", start=0.0, end=0.4),
        WordTimestamp(word="everyone.", start=0.4, end=0.8),
        # 0.6s pause
        WordTimestamp(word="Here", start=1.4, end=1.8),
        WordTimestamp(word="is", start=1.8, end=2.0),
        WordTimestamp(word="the", start=2.0, end=2.2),
        WordTimestamp(word="biggest", start=2.2, end=2.6),
        WordTimestamp(word="secret", start=2.6, end=3.0),
        WordTimestamp(word="to", start=3.0, end=3.2),
        WordTimestamp(word="coding.", start=3.2, end=3.8),
        # pause
        WordTimestamp(word="You", start=4.5, end=4.8),
        WordTimestamp(word="must", start=4.8, end=5.2),
        WordTimestamp(word="test.", start=5.2, end=25.5),
    ]

    # Raw start at 1.0 (in the pause before "Here") -> should snap to 1.4 ("Here")
    # Raw end at 24.0 -> should snap to 25.5 ("test.")
    snapped_start, snapped_end = BoundarySnapper.snap_boundaries(
        words=words,
        raw_start=1.0,
        raw_end=24.0,
        min_duration=10.0,
        max_duration=30.0
    )
    assert snapped_start == 1.4
    assert snapped_end == 25.5
    assert (snapped_end - snapped_start) >= 10.0


def test_audio_signals_analysis():
    words = [
        WordTimestamp(word=f"word{i}", start=i * 0.4, end=i * 0.4 + 0.3)
        for i in range(20)
    ]
    signals = AudioSignalAnalyzer.analyze_audio(words=words)
    assert isinstance(signals, AudioSignals)
    assert signals.avg_speech_rate_wps > 0.0
    assert "Speech" in signals.summary_text


def test_judge_rubric_and_headline_variants():
    candidates = [
        CandidateClip(
            candidate_id=1,
            title="Mindset Shift",
            start_seconds=10.0,
            end_seconds=42.0,
            duration=32.0,
            initial_score=85,
            hook="If you want to win, stop waiting for permission.",
            reason="High hook energy"
        ),
        CandidateClip(
            candidate_id=2,
            title="Routine",
            start_seconds=50.0,
            end_seconds=80.0,
            duration=30.0,
            initial_score=80,
            hook="My daily routine is simple.",
            reason="Moderate engagement"
        )
    ]

    judge = JudgeAgent(api_key=None, provider="offline")
    evaluated = judge.evaluate_and_rank(candidates=candidates, transcript_context="", top_n=2)

    assert len(evaluated) == 2
    # Verify Pydantic structure
    for clip in evaluated:
        assert isinstance(clip, ClipMetadata)
        assert clip.rubric is not None
        assert isinstance(clip.rubric, RubricScore)
        assert 0 <= clip.rubric.total_score <= 100
        assert clip.headline_variants is not None
        assert isinstance(clip.headline_variants, HeadlineVariants)
        assert len(clip.headline_variants.curiosity) > 0
        assert len(clip.headline_variants.value) > 0
        assert len(clip.headline_variants.bold_claim) > 0
        assert clip.headline == clip.headline_variants.chosen


def test_two_pass_curation_end_to_end():
    words = [
        WordTimestamp(word="Start", start=0.0, end=0.5),
        WordTimestamp(word="talking.", start=0.5, end=1.0),
        WordTimestamp(word="This", start=1.5, end=1.8),
        WordTimestamp(word="is", start=1.8, end=2.0),
        WordTimestamp(word="viral.", start=2.0, end=30.0),
    ]
    transcript_text = "[00:01] Start talking. This is viral."

    curator = ViralCuratorAgent(api_key=None, provider="offline")
    clips = curator.curate_clips(
        transcript_text=transcript_text,
        words=words,
        num_clips=2,
        min_duration=20,
        max_duration=40
    )

    assert len(clips) > 0
    first_clip = clips[0]
    assert "viral_score" in first_clip
    assert "headline" in first_clip
    assert "rubric" in first_clip
    assert "headline_variants" in first_clip


def test_judge_score_gating():
    candidates = [
        CandidateClip(
            candidate_id=1,
            title="High Virality Clip",
            start_seconds=10.0,
            end_seconds=42.0,
            duration=32.0,
            initial_score=90,
            hook="This is the biggest breakthrough of the decade.",
            reason="High hook energy"
        ),
        CandidateClip(
            candidate_id=2,
            title="Low Virality Clip",
            start_seconds=50.0,
            end_seconds=60.0,
            duration=10.0,
            initial_score=60,
            hook="Short hook",
            reason="Low engagement"
        )
    ]
    judge = JudgeAgent(api_key=None, provider="offline", min_score_threshold=75)
    evaluated = judge.evaluate_and_rank(candidates=candidates, transcript_context="", top_n=5)
    assert len(evaluated) > 0
    for clip in evaluated:
        assert clip.viral_score >= 75

    strictly_gated = judge.evaluate_and_rank(candidates=candidates, transcript_context="", top_n=5, min_score=95)
    assert len(strictly_gated) == 0
