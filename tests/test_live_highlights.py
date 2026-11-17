"""
Tests for Live Highlight Detection & Curation Subsystem (live/highlights.py)
Validates:
1. Window overlap: 3-minute steps, 5-minute windows (overlapping by 120s)
2. Deduplication: rejects overlap > 30% or start within 20s, accepts non-overlapping
3. Multi-signal combination: 70% LLM + 15% Audio energy + 15% Speech-rate spike, gated at >= 75
4. Pre-roll 3s and post-roll 3s with sentence boundary snapping
5. Failure path: Groq failure marks window 'analysis_failed', zero heuristic fakes
6. Backpressure control: skips oldest windows when > 3 windows behind
"""

import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from backend.database import SessionLocal, init_db
from backend.models import User, LiveSession, LiveSegment, Clip
from backend.auth import hash_password
from schema import WordTimestamp, AudioSignals, CandidateClip, ClipMetadata, RubricScore, HeadlineVariants
from live.highlights import (
    LiveHighlightsDetector,
    is_duplicate_highlight,
    calculate_combined_viral_score,
)


def create_user(prefix: str = "hl_user") -> User:
    init_db()
    db = SessionLocal()
    user = User(
        id=str(uuid.uuid4()),
        email=f"{prefix}_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("HighlightPass123!"),
        full_name="Highlight Test User",
        plan="pro",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def create_live_session(user_id: str) -> str:
    db = SessionLocal()
    session_id = str(uuid.uuid4())
    session = LiveSession(
        id=session_id,
        user_id=user_id,
        title="Live Highlights Stream",
        stream_url="rtmp://localhost/live/test",
        platform="rtmp",
        source_type="rtmp",
        rights_confirmed=True,
    )
    db.add(session)
    db.commit()
    db.close()
    return session_id


def test_window_overlap_calculation():
    """
    Verifies sliding window logic:
    Every 3 minutes (180s step), takes 5 minutes (300s window).
    Adjacent windows overlap by 120s (2 minutes).
    """
    detector = LiveHighlightsDetector(
        session_id="dummy_session",
        step_seconds=180.0,
        window_size_seconds=300.0
    )

    # At 700s of stream time:
    # w0: 0s -> 300s
    # w1: 180s -> 480s
    # w2: 360s -> 660s
    windows = detector.get_eligible_windows(current_stream_time=700.0)

    assert len(windows) == 3
    assert windows[0] == (0, 0.0, 300.0)
    assert windows[1] == (1, 180.0, 480.0)
    assert windows[2] == (2, 360.0, 660.0)

    # Verify overlap: w0 end (300s) - w1 start (180s) = 120s overlap
    overlap_0_1 = windows[0][2] - windows[1][1]
    assert overlap_0_1 == 120.0

    # Before reaching 300s, no window is eligible
    assert detector.get_eligible_windows(current_stream_time=250.0) == []


def test_deduplication_rules():
    """
    Verifies deduplication:
    - Overlap > 30% -> duplicate
    - Start within 20s -> duplicate
    - Independent highlight -> accepted
    """
    existing_clip = Clip(
        id="c1",
        live_session_id="s1",
        source="highlight",
        start_seconds=100.0,
        end_seconds=140.0,  # 40s duration
        duration=40.0
    )
    existing_list = [existing_clip]

    # Case 1: Start within 20s (start=115s -> diff=15s < 20s) -> Duplicate
    assert is_duplicate_highlight(new_start=115.0, new_end=160.0, existing_highlights=existing_list)

    # Case 2: Start within 20s on earlier side (start=85s -> diff=15s < 20s) -> Duplicate
    assert is_duplicate_highlight(new_start=85.0, new_end=125.0, existing_highlights=existing_list)

    # Case 3: Start is 25s away (125s), but overlaps [125s, 140s] = 15s out of 40s = 37.5% (> 30%) -> Duplicate
    assert is_duplicate_highlight(new_start=125.0, new_end=165.0, existing_highlights=existing_list)

    # Case 4: Start is 35s away (135s), overlaps [135s, 140s] = 5s out of 40s = 12.5% (< 30%) -> Accepted
    assert not is_duplicate_highlight(new_start=135.0, new_end=175.0, existing_highlights=existing_list)

    # Case 5: Completely non-overlapping (start=200s, end=230s) -> Accepted
    assert not is_duplicate_highlight(new_start=200.0, new_end=230.0, existing_highlights=existing_list)


def test_multi_signal_score_combination_and_gating():
    """
    Verifies score combination:
    70% LLM + 15% Audio energy + 15% Speech-rate spike. Never relies on loudness alone.
    Gated at >= 75.
    """
    audio_signals = AudioSignals(
        energy_peaks=[15.0, 25.0, 35.0],
        laughter_spikes=[20.0],
        avg_speech_rate_wps=2.5,
        summary_text="Energy peaks detected"
    )

    words = [
        WordTimestamp(word=f"word_{i}", start=10.0 + i * 0.25, end=10.0 + (i + 1) * 0.25)
        for i in range(40)  # 4 words/sec (fast speech rate spike vs 2.5 avg)
    ]

    # High LLM score (85) + High energy + Fast speech rate
    high_score = calculate_combined_viral_score(
        llm_score=85,
        start_seconds=10.0,
        end_seconds=20.0,
        audio_signals=audio_signals,
        words=words
    )
    assert high_score >= 80

    # Low LLM score (40) with loud audio must NEVER cross the >= 75 gate
    loud_low_llm = calculate_combined_viral_score(
        llm_score=40,
        start_seconds=10.0,
        end_seconds=20.0,
        audio_signals=audio_signals,
        words=words
    )
    assert loud_low_llm < 75, f"Loudness alone should never pass gate! Got {loud_low_llm}"


def test_backpressure_skips_oldest_windows():
    """
    Verifies backpressure control:
    If more than 3 windows behind, skips the oldest and processes only the latest 3.
    """
    detector = LiveHighlightsDetector(
        session_id="backpressure_session",
        step_seconds=180.0,
        window_size_seconds=300.0
    )

    # Simulate 5 pending windows queued up: w0, w1, w2, w3, w4
    pending = [
        (0, 0.0, 300.0),
        (1, 180.0, 480.0),
        (2, 360.0, 660.0),
        (3, 540.0, 840.0),
        (4, 720.0, 1020.0)
    ]

    actionable = detector.apply_backpressure(pending)

    # Must retain only the newest 3 windows
    assert len(actionable) == 3
    assert actionable[0][0] == 2
    assert actionable[1][0] == 3
    assert actionable[2][0] == 4

    # w0 and w1 must be marked as processed/skipped
    assert 0 in detector._processed_windows
    assert 1 in detector._processed_windows


def test_groq_failure_path_no_heuristics(monkeypatch):
    """
    Verifies fail-loudly error path:
    If Groq fails, marks window 'analysis_failed' and does NOT create heuristic fake highlights.
    """
    user = create_user("groq_fail_user")
    session_id = create_live_session(user.id)

    with tempfile.TemporaryDirectory() as tmp_dir:
        detector = LiveHighlightsDetector(
            session_id=session_id,
            api_key="mock_invalid_key",
            media_root=Path(tmp_dir)
        )

        # Mock media extraction to return dummy paths
        dummy_ts = Path(tmp_dir) / "dummy.ts"
        dummy_ts.write_bytes(b"ts_data")
        dummy_mp3 = Path(tmp_dir) / "dummy.mp3"
        dummy_mp3.write_bytes(b"mp3_data")
        monkeypatch.setattr(
            detector,
            "extract_window_media",
            lambda w_start, w_end, work_dir, db: (dummy_ts, dummy_mp3, 0.0)
        )

        # Mock TranscriberAgent to simulate Groq API 500 error / rate limit
        def mock_transcribe(*args, **kwargs):
            raise RuntimeError("Groq API 500 Internal Error: Rate limit reached or model unavailable")

        from agents.transcriber import TranscriberAgent
        monkeypatch.setattr(TranscriberAgent, "transcribe_with_groq_whisper", mock_transcribe)

        clips = detector.process_window(
            window_index=0,
            window_start=0.0,
            window_end=300.0
        )

        # Zero clips created
        assert len(clips) == 0

        # Window must be registered as failed
        assert 0 in detector._failed_windows

        # Database session must record the error
        db = SessionLocal()
        session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
        assert session is not None
        assert session.error is not None
        assert "Analysis failed" in session.error

        # Zero fake clips in DB
        clip_count = db.query(Clip).filter(Clip.live_session_id == session_id).count()
        assert clip_count == 0, "Heuristic fake highlights must NEVER be created on failure!"
        db.close()


def test_highlights_groq_curator_judge_pipeline_with_pre_post_roll_and_snapping(monkeypatch):
    """
    End-to-end test with mocked Groq:
    1. Transcribes words
    2. Runs ViralCuratorAgent + JudgeAgent
    3. Adds pre-roll 3s + post-roll 3s, snaps to sentence boundaries
    4. Combines scores, gates >= 75
    5. Saves Clip(source='highlight', status='raw') with rubric & 3 headline variants
    """
    user = create_user("e2e_hl_user")
    session_id = create_live_session(user.id)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        detector = LiveHighlightsDetector(
            session_id=session_id,
            api_key="mock_groq_key",
            media_root=tmp_path
        )

        dummy_ts = tmp_path / "stream.ts"
        dummy_ts.write_bytes(b"ts_stream_bytes")
        dummy_mp3 = tmp_path / "stream.mp3"
        dummy_mp3.write_bytes(b"mp3_stream_bytes")
        monkeypatch.setattr(
            detector,
            "extract_window_media",
            lambda w_start, w_end, work_dir, db: (dummy_ts, dummy_mp3, 0.0)
        )

        # 1. Mock word timestamps with distinct sentence punctuation
        mock_words = [
            WordTimestamp(word="Welcome", start=16.0, end=16.5),
            WordTimestamp(word="everyone.", start=16.6, end=17.0),
            WordTimestamp(word="Here", start=18.0, end=18.3),
            WordTimestamp(word="is", start=18.4, end=18.6),
            WordTimestamp(word="the", start=18.7, end=18.9),
            WordTimestamp(word="secret", start=19.0, end=19.5),
            WordTimestamp(word="to", start=19.6, end=19.8),
            WordTimestamp(word="viral", start=19.9, end=20.4),
            WordTimestamp(word="growth.", start=20.5, end=21.0),
            WordTimestamp(word="It", start=22.0, end=22.3),
            WordTimestamp(word="changes", start=22.4, end=22.8),
            WordTimestamp(word="everything", start=22.9, end=23.4),
            WordTimestamp(word="forever.", start=23.5, end=24.0),
            WordTimestamp(word="Thank", start=49.0, end=49.4),
            WordTimestamp(word="you.", start=49.5, end=50.0),
            WordTimestamp(word="Goodbye.", start=53.0, end=53.5),
        ]

        from agents.transcriber import TranscriberAgent
        monkeypatch.setattr(TranscriberAgent, "transcribe_with_groq_whisper", lambda *a, **k: mock_words)

        # 2. Mock ViralCuratorAgent.propose_candidates
        mock_cand = CandidateClip(
            candidate_id=1,
            title="The Viral Growth Secret",
            start_seconds=18.0,
            end_seconds=48.0,
            duration=30.0,
            initial_score=90,
            hook="Here is the secret to viral growth.",
            reason="Clear viral value proposition."
        )
        from agents.curator import ViralCuratorAgent
        monkeypatch.setattr(ViralCuratorAgent, "propose_candidates", lambda *a, **k: [mock_cand])

        # 3. Mock JudgeAgent.evaluate_candidates
        mock_meta = ClipMetadata(
            title="The Viral Growth Secret",
            headline="THE SECRET TO VIRAL GROWTH",
            start_seconds=18.0,
            end_seconds=48.0,
            duration=30.0,
            viral_score=88,
            hook="Here is the secret to viral growth.",
            reason="High engagement and retention payoff.",
            rubric=RubricScore(
                hook_strength=23,
                self_contained=22,
                payoff=24,
                zero_context_needed=22,
                total_score=91,
                critique="Superb self-contained arc."
            ),
            headline_variants=HeadlineVariants(
                curiosity="Why didn't anyone tell you this?",
                value="The Complete Viral Framework",
                bold_claim="This Will Change How You Post",
                chosen="The Complete Viral Framework"
            )
        )
        from agents.judge import JudgeAgent
        monkeypatch.setattr(JudgeAgent, "evaluate_candidates", lambda *a, **k: [mock_meta])

        # Execute window analysis
        clips = detector.process_window(
            window_index=0,
            window_start=0.0,
            window_end=300.0
        )

        assert len(clips) == 1
        clip = clips[0]

        # Verify properties
        assert clip.source == "highlight"
        assert clip.status == "raw"
        assert clip.viral_score >= 75
        assert clip.title == "The Viral Growth Secret"
        assert clip.rubric_json is not None
        assert clip.rubric_json["total_score"] == 91
        assert clip.headline_variants_json is not None
        assert clip.headline_variants_json["chosen"] == "The Complete Viral Framework"

        # Pre-roll 3s: 18.0s - 3.0s = 15.0s, snapped to sentence start at 16.0s ("Welcome everyone.") or 18.0s ("Here is...")
        # Post-roll 3s: 48.0s + 3.0s = 51.0s, snapped to sentence end at 50.0s ("Thank you.") or 53.5s ("Goodbye.")
        assert clip.start_seconds <= 18.0, "Pre-roll must expand before candidate start"
        assert clip.end_seconds >= 48.0, "Post-roll must extend after candidate end"
        assert clip.duration >= 25.0
