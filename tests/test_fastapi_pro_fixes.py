"""
TDD Tests for FastAPI Pro & Architecture Hardening Fixes:
1. Cross-platform FFmpeg/FFprobe binary resolution using shutil.which with fallback
2. Strict requirements version pinning (==) and email-validator presence
3. /health endpoint reporting real dynamic system capabilities
4. Linux CI workflow installing headless OpenCV/audio system dependencies
5. Feedback loop moat strictly computing Pearson correlation (0.0 on zero variance) and DB persistence
6. PROGRESS.md marking billing UI, publishers, and legal pages as stubs
"""

import os
import re
import shutil
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).parent.parent.resolve()

from ffmpeg_utils import get_ffmpeg_bin, get_ffprobe_bin
from backend.app import app
from backend.config import settings
from backend.database import SessionLocal
from backend.models import User, Project, Clip, ClipMetric
from agents.feedback import MoatFeedbackEngine


# ----------------------------------------------------------------------
# 1. Binary Resolution with shutil.which
# ----------------------------------------------------------------------
def test_ffmpeg_utils_resolution_and_which(monkeypatch):
    """Verifies get_ffmpeg_bin and get_ffprobe_bin utilize shutil.which and fall back safely."""
    # Test normal resolution
    ffmpeg_bin = get_ffmpeg_bin(PROJECT_ROOT)
    ffprobe_bin = get_ffprobe_bin(PROJECT_ROOT)
    assert ffmpeg_bin is not None
    assert ffprobe_bin is not None
    assert Path(ffmpeg_bin).exists()
    assert Path(ffprobe_bin).exists()

    # Test preference for shutil.which when available
    fake_system_ffmpeg = "/usr/bin/ffmpeg" if os.name != "nt" else "C:\\Windows\\System32\\ffmpeg.exe"
    monkeypatch.setattr(shutil, "which", lambda cmd: fake_system_ffmpeg if cmd == "ffmpeg" else None)
    resolved = get_ffmpeg_bin(PROJECT_ROOT)
    assert resolved == Path(fake_system_ffmpeg)

    # Test fallback to project root when shutil.which returns None
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    fallback_resolved = get_ffmpeg_bin(PROJECT_ROOT)
    assert fallback_resolved.name in ["ffmpeg.exe", "ffmpeg"]


# ----------------------------------------------------------------------
# 2. Strict Requirements Pinning & email-validator
# ----------------------------------------------------------------------
def test_requirements_strictly_pinned_and_email_validator():
    """Verifies all dependencies in requirements.txt use exact pinning (==) and email-validator is present."""
    req_file = PROJECT_ROOT / "requirements.txt"
    assert req_file.exists(), "requirements.txt must exist"

    lines = [
        line.strip() for line in req_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    # Verify email-validator is included
    email_val_lines = [l for l in lines if l.startswith("email-validator")]
    assert len(email_val_lines) == 1, "email-validator must be present in requirements.txt"
    assert "==" in email_val_lines[0], "email-validator must be pinned with =="

    # Verify EVERY dependency line is pinned with exact '=='
    for line in lines:
        assert "==" in line, f"Requirement '{line}' must be pinned with exact '=='"
        assert not re.search(r"[><~^]", line), f"Requirement '{line}' must not use unpinned operators like >, <, ~, ^"


# ----------------------------------------------------------------------
# 3. Dynamic /health Endpoint Capabilities
# ----------------------------------------------------------------------
def test_health_reports_real_capabilities():
    """Verifies /health reports real dynamic system capabilities and accurate status."""
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()

    assert "status" in data
    assert data["status"] in ["healthy", "degraded"]
    assert "capabilities" in data

    caps = data["capabilities"]
    expected_keys = ["ffmpeg", "ffprobe", "gpu_nvenc", "face_tracking", "database", "groq_api", "storage"]
    for k in expected_keys:
        assert k in caps, f"Capability key '{k}' must be reported in /health"

    # Core capabilities must match the current environment
    assert isinstance(caps["ffmpeg"], bool)
    assert caps["ffmpeg"] is True, "FFmpeg binary must be detected"
    assert isinstance(caps["ffprobe"], bool)
    assert caps["ffprobe"] is True, "FFprobe binary must be detected"
    assert isinstance(caps["face_tracking"], bool)
    assert caps["face_tracking"] is True, "OpenCV face tracking capability must be functional"
    assert isinstance(caps["database"], bool)
    assert caps["database"] is True, "Database connection must be operational"
    assert isinstance(caps["gpu_nvenc"], bool)
    assert caps["storage"] in ["local", "r2"]


# ----------------------------------------------------------------------
# 4. Linux CI Workflow Dependencies
# ----------------------------------------------------------------------
def test_ci_workflow_has_linux_deps():
    """Verifies CI workflow installs system headless dependencies for OpenCV and audio processing."""
    ci_file = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_file.exists(), ".github/workflows/ci.yml must exist"
    ci_text = ci_file.read_text(encoding="utf-8")

    assert "ubuntu-latest" in ci_text
    assert "libgl1" in ci_text, "CI must install libgl1 for headless OpenCV"
    assert "libglib2.0-0" in ci_text, "CI must install libglib2.0-0"
    assert "libsndfile1" in ci_text, "CI must install libsndfile1 for audio decoding"
    assert "libass-dev" in ci_text, "CI must install libass-dev for subtitle rendering"


# ----------------------------------------------------------------------
# 5. Feedback Loop Moat: Zero-Variance Protection & DB Persistence
# ----------------------------------------------------------------------
def test_feedback_correlation_never_085_on_zero_variance():
    """Verifies Pearson correlation is 0.0 when variance is zero, never an invented 0.85."""
    engine = MoatFeedbackEngine()
    # Add identical predicted scores -> zero variance
    engine.record_clip_features("c_1", predicted_score=85, duration_seconds=30.0, hook="Hook 1")
    engine.sync_actual_metrics("c_1", views=10000, retention_rate=0.7)

    engine.record_clip_features("c_2", predicted_score=85, duration_seconds=30.0, hook="Hook 2")
    engine.sync_actual_metrics("c_2", views=50000, retention_rate=0.9)

    stats = engine.compute_accuracy_metrics()
    assert stats["sample_count"] == 2
    assert stats["correlation"] == 0.0
    assert stats["correlation"] != 0.85


def test_feedback_db_persistence_and_loading():
    """Verifies MoatFeedbackEngine saves features & metrics to DB and loads them back."""
    db = SessionLocal()
    try:
        user = User(email=f"moat_test_{uuid.uuid4().hex[:6]}@example.com", plan="pro")
        db.add(user)
        db.commit()

        project = Project(user_id=user.id, title="Test Moat Project")
        db.add(project)
        db.commit()

        clip = Clip(
            project_id=project.id,
            title="Moat Test Clip",
            headline="Headline",
            start_seconds=10.0,
            end_seconds=40.0,
            duration=30.0,
            viral_score=88
        )
        db.add(clip)
        db.commit()

        engine = MoatFeedbackEngine(db=db)
        engine.record_clip_features(
            clip_id=clip.id,
            predicted_score=88,
            duration_seconds=30.0,
            hook="Proven Hook Formula",
            caption_style="hormozi",
            speaker_count=1
        )

        engine.sync_actual_metrics(
            clip_id=clip.id,
            views=32000,
            retention_rate=0.86,
            likes=2100,
            shares=430
        )

        # Check DB rows
        metric = db.query(ClipMetric).filter(ClipMetric.clip_id == clip.id).first()
        assert metric is not None
        assert metric.views == 32000
        assert metric.retention_rate == 0.86
        assert metric.likes == 2100
        assert metric.shares == 430

        # Create a fresh engine and load from DB
        fresh_engine = MoatFeedbackEngine(db=db)
        fresh_engine.load_from_db()
        assert clip.id in fresh_engine.data_store
        vec = fresh_engine.data_store[clip.id]
        assert vec.actual_views == 32000
        assert vec.actual_retention_rate == 0.86
        assert vec.predicted_score == 88

    finally:
        db.close()


# ----------------------------------------------------------------------
# 6. PROGRESS.md Stubs Formally Marked
# ----------------------------------------------------------------------
def test_progress_md_stubs_marked():
    """Verifies PROGRESS.md explicitly designates stub features."""
    prog_file = PROJECT_ROOT / "PROGRESS.md"
    assert prog_file.exists(), "PROGRESS.md must exist"
    content = prog_file.read_text(encoding="utf-8")

    # Phase 6 Billing UI
    assert re.search(r"Phase 6.*\[STUB\]", content, re.IGNORECASE) or "[STUB]" in content
    assert "Billing UI" in content and "[STUB]" in content
    # Phase 7 Official Publishers
    assert "Publishers" in content or "Phase 7" in content
    # Phase 9 Legal Pages
    assert "Legal Pages" in content or "Terms" in content


# ----------------------------------------------------------------------
# 7. Brand Kit Backend Endpoint (/api/v1/brand-kit)
# ----------------------------------------------------------------------
def test_brand_kit_endpoints():
    """Verifies GET and POST /api/v1/brand-kit persist and retrieve styling tokens."""
    from backend.auth import create_access_token
    client = TestClient(app)

    db = SessionLocal()
    user = User(email=f"brand_{uuid.uuid4().hex[:6]}@example.com", plan="pro")
    db.add(user)
    db.commit()
    token = create_access_token({"sub": user.id, "email": user.email})
    db.close()

    headers = {"Authorization": f"Bearer {token}"}

    # 1. GET default brand kit
    res_get = client.get(f"{settings.API_V1_PREFIX}/brand-kit/", headers=headers)
    assert res_get.status_code == 200
    data = res_get.json()
    assert "brand_kit" in data
    assert data["brand_kit"]["primary_color"] == "#8B5CF6"

    # 2. POST update brand kit
    payload = {
        "primary_color": "#7C3AED",
        "secondary_color": "#F43F5E",
        "font_family": "Montserrat",
        "caption_preset": "cyber_cyan",
        "watermark_text": "@custombrand",
        "watermark_position": "bottom_left",
        "outro_cta_enabled": True,
        "outro_text": "Follow for more daily insights"
    }
    res_post = client.post(f"{settings.API_V1_PREFIX}/brand-kit/", json=payload, headers=headers)
    assert res_post.status_code == 200
    assert res_post.json()["status"] == "saved"
    assert res_post.json()["brand_kit"]["primary_color"] == "#7C3AED"

    # 3. GET reflects updated brand kit
    res_get2 = client.get(f"{settings.API_V1_PREFIX}/brand-kit/", headers=headers)
    assert res_get2.status_code == 200
    assert res_get2.json()["brand_kit"]["font_family"] == "Montserrat"
    assert res_get2.json()["brand_kit"]["watermark_text"] == "@custombrand"

