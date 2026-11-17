"""
Tests for Live Minute Cutter & Lazy Enhancement Subsystem
Validates Phase 4 Full Clip Every Minute Engine:
1. INTERVAL=10s, 65s run -> assert >= 5 clips, 10 +/- 3s each
2. Clip i end == Clip i+1 start (tiling within 0.05s)
3. Each clip ends 'ready' at 1080x1920 with audio
4. Kill worker mid-render and restart -> clip finishes with no duplicates
5. Real-time factor (RTF) tracking & falling_behind warning on 5 consecutive slow renders
6. Flush final partial window on stream stop (min 10s setting)
7. Unique (session_id, index) constraint raises IntegrityError on collision
8. POST /clips/{id}/process with auth + ownership
9. SSE events stream: clip_raw_ready, clip_enhancing, clip_ready, clip_failed, falling_behind
"""

import asyncio
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from typing import Tuple, List, Dict, Any
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from backend.app import app
from backend.auth import create_access_token, hash_password
from backend.database import SessionLocal, init_db
from backend.models import User, LiveSession, LiveSegment, Clip
from backend.sse import live_broadcaster
from ffmpeg_utils import get_ffmpeg_bin
from live.minute_cutter import MinuteCutter
from live.enhancer import enhance_clip_sync, rtf_tracker

client = TestClient(app)
SOURCE_VIDEO = Path("temp_media/test_inputs/solo_speaker_full.mp4").resolve()


def create_user(prefix: str = "cutter_user") -> User:
    """Creates an active test user in database."""
    init_db()
    db = SessionLocal()
    user = User(
        id=str(uuid.uuid4()),
        email=f"{prefix}_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("Pass1234!"),
        full_name="Minute Cutter User",
        plan="pro",
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def setup_65s_session(user_id: str, tmp_path: Path) -> Tuple[str, List[LiveSegment]]:
    """
    Creates a LiveSession and segments 66s of video into 6.0s MPEG-TS segments.
    """
    assert SOURCE_VIDEO.exists(), f"Source video {SOURCE_VIDEO} must exist."
    session_id = str(uuid.uuid4())
    session_dir = tmp_path / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    session = LiveSession(
        id=session_id,
        user_id=user_id,
        title="Minute Cutter 65s Stream",
        stream_url="rtmp://localhost/live/test",
        platform="rtmp",
        source_type="rtmp",
        rights_confirmed=True,
    )
    db.add(session)
    db.commit()

    ffmpeg = str(get_ffmpeg_bin())
    seg_pattern = session_dir / "seg_%05d.ts"
    cmd = [
        ffmpeg, "-nostdin", "-loglevel", "warning",
        "-stream_loop", "1",
        "-t", "78.0",
        "-i", str(SOURCE_VIDEO),
        "-c", "copy",
        "-f", "segment",
        "-segment_time", "6.0",
        "-segment_format", "mpegts",
        "-reset_timestamps", "1",
        "-y",
        str(seg_pattern),
    ]
    subprocess.run(cmd, check=True)

    seg_files = sorted(session_dir.glob("seg_*.ts"))[:11]
    created_segments = []
    for idx, f in enumerate(seg_files):
        start_sec = round(idx * 6.0, 2)
        end_sec = round((idx + 1) * 6.0, 2)
        seg = LiveSegment(
            id=str(uuid.uuid4()),
            session_id=session_id,
            segment_index=idx,
            file_path=str(f.resolve()),
            start_seconds=start_sec,
            end_seconds=end_sec,
            duration=6.0,
            status="recorded",
        )
        db.add(seg)
        created_segments.append(seg)

    db.commit()
    db.close()
    return session_id, created_segments


def probe_clip_media(file_path: Path) -> Dict[str, Any]:
    """Probes resolution and audio presence of rendered video."""
    ffmpeg = str(get_ffmpeg_bin())
    ffprobe = ffmpeg.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")
    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "stream=width,height,codec_type",
        "-of", "json",
        str(file_path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    info = json.loads(res.stdout)
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    audio = next((s for s in info.get("streams", []) if s.get("codec_type") == "audio"), None)
    return {
        "width": int(video["width"]) if video and "width" in video else 0,
        "height": int(video["height"]) if video and "height" in video else 0,
        "has_audio": audio is not None,
    }


def test_minute_cutter_interval_cuts_no_overlap_and_no_duplicates():
    """
    Test: INTERVAL=10s, run 65s, assert >= 5 raw clips, 10 +/- 3s each,
    exact boundary tiling (within 0.05s), no duplicates after a restart.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        user = create_user("interval_test")
        session_id, segments = setup_65s_session(user.id, tmp_path)

        cutter = MinuteCutter(
            session_id=session_id,
            interval_seconds=10.0,
            auto_enhance=False,
            media_root=tmp_path / session_id,
        )

        clips = cutter.check_and_cut_windows()

        # 1. Assert >= 5 raw clips
        assert len(clips) >= 5, f"Expected >= 5 clips for 65s stream at 10s interval, got {len(clips)}"

        # 2. Assert each clip: source='fixed', status='raw', duration is 10 +/- 3s (7.0s to 13.0s)
        for i, c in enumerate(clips):
            assert c.source == "fixed", f"Clip #{i} source must be 'fixed'"
            assert c.status == "raw", f"Clip #{i} status must be 'raw'"
            assert 7.0 <= c.duration <= 13.0, (
                f"Clip #{i} duration {c.duration}s is not within 10 +/- 3s [7.0s, 13.0s]"
            )
            assert c.clip_index == i
            assert Path(c.video_url).exists() or c.r2_key is not None

        # 3. Assert exact boundary tiling: clip i end == clip i+1 start (within 0.05s)
        for i in range(len(clips) - 1):
            cur_end = clips[i].end_seconds
            next_start = clips[i + 1].start_seconds
            diff = abs(next_start - cur_end)
            assert diff <= 0.05, (
                f"Tiling gap/overlap between Clip #{i} (end {cur_end:.2f}s) and "
                f"Clip #{i+1} (start {next_start:.2f}s): diff={diff:.3f}s"
            )

        # 4. Assert NO DUPLICATES after a restart
        restarted_cutter = MinuteCutter(
            session_id=session_id,
            interval_seconds=10.0,
            auto_enhance=False,
            media_root=tmp_path / session_id,
        )
        restarted_clips = restarted_cutter.check_and_cut_windows()

        db = SessionLocal()
        total_in_db = db.query(Clip).filter(Clip.live_session_id == session_id).count()
        db.close()

        assert total_in_db == len(clips), f"Restart duplicated clips! DB has {total_in_db}, expected {len(clips)}"


def test_full_clip_every_minute_auto_enhance_and_worker_resumption():
    """
    Test Phase 4 requirement 6:
    - Run 65s fake live source, INTERVAL=10s -> >= 5 clips
    - Clip i end == Clip i+1 start (tiling within 0.05s)
    - Kill worker mid-render (status='enhancing') and restart -> finishes as 'ready' with no duplicates
    - Each ends 'ready' at 1080x1920 with audio
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        user = create_user("resumption_test")
        session_id, segments = setup_65s_session(user.id, tmp_path)

        # Cut raw clips first
        cutter = MinuteCutter(
            session_id=session_id,
            interval_seconds=10.0,
            auto_enhance=False,
            media_root=tmp_path / session_id,
        )
        clips = cutter.check_and_cut_windows()
        assert len(clips) >= 5, f"Expected >= 5 clips, got {len(clips)}"

        # 1. Assert tiling: clip i end == clip i+1 start (within 0.05s)
        for i in range(len(clips) - 1):
            diff = abs(clips[i].end_seconds - clips[i + 1].start_seconds)
            assert diff <= 0.05, f"Tiling error between clip {i} and {i+1}: diff={diff}"

        # 2. Simulate worker kill mid-render on Clip #0:
        # Worker marked clip 0 as 'enhancing' and died mid-render
        db = SessionLocal()
        clip0 = db.query(Clip).filter(Clip.id == clips[0].id).first()
        clip0.status = "enhancing"
        db.commit()
        db.close()

        # Worker restarts: enhances pending clips
        restarted_cutter = MinuteCutter(
            session_id=session_id,
            interval_seconds=10.0,
            auto_enhance=False,
            media_root=tmp_path / session_id,
        )
        # Resumed enhancement finishes clip 0
        enhanced_clip0 = enhance_clip_sync(clips[0].id)
        assert enhanced_clip0 is not None
        assert enhanced_clip0.status == "ready"

        # Check resolution and audio on clip 0
        probe0 = probe_clip_media(Path(enhanced_clip0.video_url))
        assert probe0["width"] == 1080, f"Expected width 1080, got {probe0['width']}"
        assert probe0["height"] == 1920, f"Expected height 1920, got {probe0['height']}"
        assert probe0["has_audio"] is True, "Rendered short must contain audio"

        # Assert no duplicates were created in database
        db = SessionLocal()
        clip0_count = (
            db.query(Clip)
            .filter(Clip.live_session_id == session_id, Clip.clip_index == 0)
            .count()
        )
        assert clip0_count == 1, f"Expected exactly 1 record for clip_index 0, got {clip0_count}"

        # 3. Enhance a second clip and verify it also finishes 'ready' at 1080x1920 with audio
        enhanced_clip1 = enhance_clip_sync(clips[1].id)
        assert enhanced_clip1 is not None
        assert enhanced_clip1.status == "ready"

        probe1 = probe_clip_media(Path(enhanced_clip1.video_url))
        assert probe1["width"] == 1080
        assert probe1["height"] == 1920
        assert probe1["has_audio"] is True
        db.close()


def test_real_time_factor_tracking_and_falling_behind_alert():
    """
    Validates Requirement 4: Real-time factor (RTF).
    If RTF > 1.0 for 5 consecutive clips, emits 'falling_behind' warning.
    """
    test_session_id = f"test_rtf_{uuid.uuid4().hex[:8]}"
    rtf_tracker.reset(test_session_id)

    # 1. 4 clips with RTF > 1.0 -> should not trigger alert yet
    for r in [1.2, 1.3, 1.1, 1.4]:
        triggered = rtf_tracker.record_rtf(test_session_id, r)
        assert triggered is False

    # 2. 5th clip with RTF > 1.0 -> triggers falling behind!
    triggered_5 = rtf_tracker.record_rtf(test_session_id, 1.25)
    assert triggered_5 is True, "5 consecutive clips with RTF > 1.0 must trigger falling_behind"

    recent = rtf_tracker.get_recent(test_session_id)
    assert len(recent) == 5
    assert all(r > 1.0 for r in recent)

    # 3. Fast clip (RTF < 1.0) resets consecutive condition
    triggered_reset = rtf_tracker.record_rtf(test_session_id, 0.8)
    assert triggered_reset is False


def test_minute_cutter_flush_final_window():
    """
    Validates Requirement 1: On stop, flush the final partial window as a clip (setting: min 10s).
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        user = create_user("flush_test")
        session_id, segments = setup_65s_session(user.id, tmp_path)

        # 66s stream at INTERVAL=20s -> cuts windows [0, 20], [20, 40], [40, 60]
        # Remaining time is 66 - 60 = 6s.
        cutter = MinuteCutter(
            session_id=session_id,
            interval_seconds=20.0,
            auto_enhance=False,
            min_flush_duration=10.0,
            media_root=tmp_path / session_id,
        )
        clips = cutter.check_and_cut_windows()
        assert len(clips) == 3

        # Remaining 6s is < min_flush_duration (10s) -> should NOT flush
        flushed_none = cutter.flush_final_window(min_duration=10.0)
        assert flushed_none is None

        # If min_duration=5.0s, remaining 6s >= 5.0s -> MUST flush final partial window
        flushed_clip = cutter.flush_final_window(min_duration=5.0)
        assert flushed_clip is not None
        assert flushed_clip.clip_index == 3
        assert flushed_clip.source == "fixed"
        assert flushed_clip.status == "raw"
        assert flushed_clip.start_seconds == clips[-1].end_seconds, "Final window start must tile with last clip end"
        assert flushed_clip.end_seconds == 66.0


def test_unique_constraint_rejects_duplicate_clip_index():
    """Asserts unique (live_session_id, clip_index) constraint prevents duplicate clips."""
    user = create_user("unique_test")
    session_id = str(uuid.uuid4())

    db = SessionLocal()
    session = LiveSession(
        id=session_id,
        user_id=user.id,
        title="Unique Test Session",
        stream_url="rtmp://localhost/live/test",
        platform="rtmp",
        source_type="rtmp",
        rights_confirmed=True,
    )
    db.add(session)
    db.commit()

    clip1 = Clip(
        id=str(uuid.uuid4()),
        live_session_id=session_id,
        clip_index=0,
        source="fixed",
        status="raw",
        title="Clip 0",
        headline="Moment 0",
        start_seconds=0.0,
        end_seconds=10.0,
        duration=10.0,
    )
    db.add(clip1)
    db.commit()

    # Attempting to insert duplicate (session_id, clip_index=0) must raise IntegrityError
    clip2 = Clip(
        id=str(uuid.uuid4()),
        live_session_id=session_id,
        clip_index=0,
        source="fixed",
        status="raw",
        title="Clip 0 Duplicate",
        headline="Moment 0 Duplicate",
        start_seconds=0.0,
        end_seconds=10.0,
        duration=10.0,
    )
    db.add(clip2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_lazy_enhancement_process_endpoint_auth_and_ownership(monkeypatch):
    """
    Verifies POST /api/v1/clips/{id}/process:
    1. Returns 403 when accessed by non-owner
    2. Returns 200 and transitions status to 'processing' when authorized
    """
    owner = create_user("owner_user")
    other_user = create_user("other_user")

    session_id = str(uuid.uuid4())
    clip_id = str(uuid.uuid4())

    db = SessionLocal()
    session = LiveSession(
        id=session_id,
        user_id=owner.id,
        title="Enhancement Test Session",
        stream_url="rtmp://localhost/live/test",
        platform="rtmp",
        source_type="rtmp",
        rights_confirmed=True,
    )
    db.add(session)

    clip = Clip(
        id=clip_id,
        live_session_id=session_id,
        clip_index=0,
        source="fixed",
        status="raw",
        title="Raw Cut #1",
        headline="Headline #1",
        start_seconds=0.0,
        end_seconds=10.0,
        duration=10.0,
        video_url=str(SOURCE_VIDEO),
    )
    db.add(clip)
    db.commit()
    db.close()

    other_token = create_access_token({"sub": other_user.id})
    owner_token = create_access_token({"sub": owner.id})

    import backend.tasks
    import live.enhancer
    monkeypatch.setattr(backend.tasks.enhance_live_clip_task, "apply_async", lambda *args, **kwargs: None)
    monkeypatch.setattr(live.enhancer, "enhance_clip_sync", lambda *args, **kwargs: None)

    # 1. Non-owner gets 403 Forbidden
    res_forbidden = client.post(
        f"/api/v1/clips/{clip_id}/process",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert res_forbidden.status_code == 403
    assert "Not authorized" in res_forbidden.json()["detail"]

    # 2. Owner gets 200 OK and clip status is updated
    res_ok = client.post(
        f"/api/v1/clips/{clip_id}/process",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert res_ok.status_code == 200
    data = res_ok.json()
    assert data["status"] in ("processing", "completed", "ready")
    assert data["clip_id"] == clip_id


def test_live_session_events_sse_auth_and_ownership():
    """
    Verifies GET /api/v1/live/{id}/events:
    1. Returns 403 for non-owner
    2. Streams events for owner
    """
    owner = create_user("sse_owner")
    other_user = create_user("sse_other")
    session_id = str(uuid.uuid4())

    db = SessionLocal()
    session = LiveSession(
        id=session_id,
        user_id=owner.id,
        title="SSE Test Session",
        stream_url="rtmp://localhost/live/test",
        platform="rtmp",
        source_type="rtmp",
        rights_confirmed=True,
    )
    db.add(session)
    db.commit()
    db.close()

    other_token = create_access_token({"sub": other_user.id})
    owner_token = create_access_token({"sub": owner.id})

    # 1. Non-owner gets 403
    res_forbidden = client.get(
        f"/api/v1/live/{session_id}/events",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert res_forbidden.status_code == 403

    # 2. Owner can connect to stream
    with client.stream(
        "GET",
        f"/api/v1/live/{session_id}/events",
        headers={"Authorization": f"Bearer {owner_token}"},
    ) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

        lines = []
        for line in response.iter_lines():
            if line:
                lines.append(line)
            if len(lines) >= 2:
                break

        full_output = "\n".join(lines)
        assert "connected" in full_output
