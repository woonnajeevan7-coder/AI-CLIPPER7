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


def test_moat_never_invents_085_correlation_on_zero_variance():
    moat = MoatFeedbackEngine()
    # Add samples with zero variance in predicted_score (all 90)
    moat.record_clip_features("c_zero_1", 90, 30.0, "Hook A")
    moat.sync_actual_metrics("c_zero_1", views=50000, retention_rate=0.85)

    moat.record_clip_features("c_zero_2", 90, 30.0, "Hook B")
    moat.sync_actual_metrics("c_zero_2", views=60000, retention_rate=0.90)

    stats = moat.compute_accuracy_metrics()
    assert stats["sample_count"] == 2
    # Must mathematically report 0.0, never an invented 0.85
    assert stats["correlation"] == 0.0
    assert stats["correlation"] != 0.85


def test_moat_persists_to_database():
    from backend.database import SessionLocal
    from backend.models import User, Project, Clip, ClipMetric
    import uuid

    db = SessionLocal()
    try:
        # Create user, project, clip in DB
        u = User(email=f"moat_test_{uuid.uuid4().hex[:6]}@example.com", plan="pro")
        db.add(u)
        db.commit()

        p = Project(user_id=u.id, title="Moat Project")
        db.add(p)
        db.commit()

        c = Clip(
            project_id=p.id,
            title="Moat Test Clip",
            headline="TEST HEADLINE",
            start_seconds=10.0,
            end_seconds=40.0,
            duration=30.0,
            viral_score=92,
            hook="Hook for persistence test"
        )
        db.add(c)
        db.commit()

        # Instantiate moat with db session
        moat = MoatFeedbackEngine(db=db)
        moat.record_clip_features(
            clip_id=str(c.id),
            predicted_score=95,
            duration_seconds=30.0,
            hook="Updated hook"
        )

        # Sync real metrics and persist to DB
        moat.sync_actual_metrics(
            clip_id=str(c.id),
            views=100000,
            retention_rate=0.89,
            likes=7500,
            shares=1200
        )

        # Query database directly to confirm persistence
        metric_row = db.query(ClipMetric).filter(ClipMetric.clip_id == str(c.id)).first()
        assert metric_row is not None
        assert metric_row.views == 100000
        assert metric_row.retention_rate == 0.89
        assert metric_row.likes == 7500
        assert metric_row.shares == 1200

        # Also verify load_from_db reconstructs data_store
        moat_new = MoatFeedbackEngine(db=db)
        loaded_count = moat_new.load_from_db()
        assert loaded_count >= 1
        assert str(c.id) in moat_new.data_store
        assert moat_new.data_store[str(c.id)].actual_views == 100000

    finally:
        db.close()
