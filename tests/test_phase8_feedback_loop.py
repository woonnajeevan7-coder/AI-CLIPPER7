"""
Phase 8 Verification Tests: Feedback Loop & Moat
Tests real metrics syncing, predicted vs actual correlation, and curator prompt optimization.
"""

import pytest
from agents.feedback import MoatFeedbackEngine, ClipFeatureVector


def test_record_clip_features_and_sync_metrics():
    moat = MoatFeedbackEngine()
    vec = moat.record_clip_features(
        clip_id="clip_001",
        predicted_score=92,
        duration_seconds=31.5,
        hook="Why most founders fail in month three",
        caption_style="hormozi",
        speaker_count=1
    )

    assert isinstance(vec, ClipFeatureVector)
    assert vec.clip_id == "clip_001"
    assert vec.predicted_score == 92
    assert vec.hook_word_count == 7
    assert vec.actual_views == 0

    # Sync real performance from official API
    updated = moat.sync_actual_metrics(
        clip_id="clip_001",
        views=45200,
        retention_rate=0.88,
        likes=3400,
        shares=620
    )

    assert updated is not None
    assert updated.actual_views == 45200
    assert updated.actual_retention_rate == 0.88
    assert updated.actual_likes == 3400


def test_moat_accuracy_and_prompt_optimization():
    moat = MoatFeedbackEngine()
    # Add multiple calibrated data points
    moat.record_clip_features("c1", 90, 28.0, "Hook one", "hormozi")
    moat.sync_actual_metrics("c1", views=80000, retention_rate=0.91)

    moat.record_clip_features("c2", 84, 32.0, "Hook two", "hormozi")
    moat.sync_actual_metrics("c2", views=40000, retention_rate=0.82)

    moat.record_clip_features("c3", 75, 58.0, "Long hook three", "cyber_cyan")
    moat.sync_actual_metrics("c3", views=12000, retention_rate=0.55)

    stats = moat.compute_accuracy_metrics()
    assert stats["sample_count"] == 3
    assert stats["status"] == "Calibrated"
    assert "correlation" in stats
    assert "mean_absolute_error" in stats

    # Prompt optimization rule generation
    optimization_rule = moat.generate_prompt_optimizations()
    assert "REAL AUDIENCE FEEDBACK RULE" in optimization_rule
    assert "hormozi" in optimization_rule
