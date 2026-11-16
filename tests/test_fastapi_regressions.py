"""
FastAPI Architecture & Security Regression Tests
Validates auth enforcement, ownership checks, token verification, settings, and quotas.
"""

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config import settings
from backend.database import SessionLocal
from backend.models import User, Project, Job, Clip, Usage
from backend.auth import create_access_token, create_refresh_token, hash_password

client = TestClient(app)


def create_test_user(email: str, password: str = "Password123!", plan: str = "free") -> User:
    db = SessionLocal()
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        hashed_password=hash_password(password),
        full_name="Regression Test User",
        plan=plan,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def test_clips_auth_and_ownership():
    # 1. Setup User 1 (Owner) and User 2 (Attacker)
    user1 = create_test_user(f"owner_{uuid.uuid4().hex[:8]}@example.com")
    user2 = create_test_user(f"attacker_{uuid.uuid4().hex[:8]}@example.com")
    token1 = create_access_token({"sub": user1.id, "email": user1.email})
    token2 = create_access_token({"sub": user2.id, "email": user2.email})

    db = SessionLocal()
    proj = Project(user_id=user1.id, title="Owner Project", status="completed")
    db.add(proj)
    db.commit()
    db.refresh(proj)

    clip = Clip(
        project_id=proj.id,
        title="Owner Clip",
        headline="Awesome Clip",
        start_seconds=0.0,
        end_seconds=15.0,
        duration=15.0,
        viral_score=92
    )
    db.add(clip)
    db.commit()
    db.refresh(clip)
    clip_id = clip.id
    db.close()

    # (a) Unauthenticated access rejected with 401
    resp_unauth = client.get(f"{settings.API_V1_PREFIX}/clips/{clip_id}")
    assert resp_unauth.status_code == 401

    # (b) User 2 (non-owner) rejected with 403
    resp_attacker = client.get(
        f"{settings.API_V1_PREFIX}/clips/{clip_id}",
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert resp_attacker.status_code == 403

    # (c) User 1 (owner) succeeds with 200
    resp_owner = client.get(
        f"{settings.API_V1_PREFIX}/clips/{clip_id}",
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert resp_owner.status_code == 200
    assert resp_owner.json()["id"] == clip_id

    # (d) Trim unauthenticated rejected with 401
    resp_trim_unauth = client.post(
        f"{settings.API_V1_PREFIX}/clips/{clip_id}/trim",
        json={"new_start_seconds": 1.0, "new_end_seconds": 10.0}
    )
    assert resp_trim_unauth.status_code == 401

    # (e) Trim by User 2 rejected with 403
    resp_trim_attacker = client.post(
        f"{settings.API_V1_PREFIX}/clips/{clip_id}/trim",
        json={"new_start_seconds": 1.0, "new_end_seconds": 10.0},
        headers={"Authorization": f"Bearer {token2}"}
    )
    assert resp_trim_attacker.status_code == 403

    # (f) Trim by User 1 succeeds with 200
    resp_trim_owner = client.post(
        f"{settings.API_V1_PREFIX}/clips/{clip_id}/trim",
        json={"new_start_seconds": 1.0, "new_end_seconds": 10.0},
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert resp_trim_owner.status_code == 200
    assert resp_trim_owner.json()["duration"] == 9.0


def test_jobs_auth_and_ownership():
    user1 = create_test_user(f"job_owner_{uuid.uuid4().hex[:8]}@example.com")
    user2 = create_test_user(f"job_attacker_{uuid.uuid4().hex[:8]}@example.com")
    token1 = create_access_token({"sub": user1.id, "email": user1.email})
    token2 = create_access_token({"sub": user2.id, "email": user2.email})

    db = SessionLocal()
    proj = Project(user_id=user1.id, title="Job Project", status="pending")
    db.add(proj)
    db.commit()
    db.refresh(proj)

    job = Job(project_id=proj.id, stage="queued", status="queued", progress=0)
    db.add(job)
    db.commit()
    db.refresh(job)
    job_id = job.id
    db.close()

    # Status check unauthenticated -> 401
    assert client.get(f"{settings.API_V1_PREFIX}/jobs/{job_id}").status_code == 401
    # Status check attacker -> 403
    assert client.get(
        f"{settings.API_V1_PREFIX}/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token2}"}
    ).status_code == 403
    # Status check owner -> 200
    resp_owner = client.get(
        f"{settings.API_V1_PREFIX}/jobs/{job_id}",
        headers={"Authorization": f"Bearer {token1}"}
    )
    assert resp_owner.status_code == 200
    assert resp_owner.json()["id"] == job_id

    # SSE Stream unauthenticated -> 401
    assert client.get(f"{settings.API_V1_PREFIX}/jobs/{job_id}/stream").status_code == 401
    # SSE Stream attacker -> 403
    assert client.get(
        f"{settings.API_V1_PREFIX}/jobs/{job_id}/stream",
        headers={"Authorization": f"Bearer {token2}"}
    ).status_code == 403
    # SSE Stream owner with header -> 200
    with client.stream(
        "GET",
        f"{settings.API_V1_PREFIX}/jobs/{job_id}/stream",
        headers={"Authorization": f"Bearer {token1}"}
    ) as stream_resp:
        assert stream_resp.status_code == 200

    # SSE Stream owner with query param -> 200
    with client.stream(
        "GET",
        f"{settings.API_V1_PREFIX}/jobs/{job_id}/stream?token={token1}"
    ) as stream_resp_param:
        assert stream_resp_param.status_code == 200


def test_reject_non_access_tokens_in_get_current_user():
    user = create_test_user(f"token_type_user_{uuid.uuid4().hex[:8]}@example.com")
    access_tok = create_access_token({"sub": user.id, "email": user.email})
    refresh_tok = create_refresh_token({"sub": user.id, "email": user.email})

    # Access token must succeed
    resp_access = client.get(
        f"{settings.API_V1_PREFIX}/auth/me",
        headers={"Authorization": f"Bearer {access_tok}"}
    )
    assert resp_access.status_code == 200
    assert resp_access.json()["id"] == user.id

    # Refresh token must be rejected with 401
    resp_refresh = client.get(
        f"{settings.API_V1_PREFIX}/auth/me",
        headers={"Authorization": f"Bearer {refresh_tok}"}
    )
    assert resp_refresh.status_code == 401
    assert "access token" in resp_refresh.json()["detail"].lower()

    # Token with missing or wrong type must be rejected with 401
    import jwt
    from datetime import datetime, timezone, timedelta
    custom_tok = jwt.encode(
        {"sub": user.id, "exp": datetime.now(timezone.utc) + timedelta(hours=1), "type": "id_token"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )
    resp_custom = client.get(
        f"{settings.API_V1_PREFIX}/auth/me",
        headers={"Authorization": f"Bearer {custom_tok}"}
    )
    assert resp_custom.status_code == 401
    assert "access token" in resp_custom.json()["detail"].lower()


def test_jwt_secret_key_unset_fails_startup(monkeypatch):
    from backend.config import Settings
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="JWT_SECRET_KEY environment variable is required"):
        Settings()

    # Verify docker-compose.yml does not contain hard-coded defaults
    with open("docker-compose.yml", "r", encoding="utf-8") as f:
        dc_text = f.read()
    assert "production-secure-jwt-key-change-me" not in dc_text
    assert "JWT_SECRET_KEY=${JWT_SECRET_KEY}" in dc_text


def test_tasks_uses_source_url_not_project_title(monkeypatch):
    from backend.tasks import process_pipeline_task
    from agents.orchestrator import ClipperOrchestratorAgent

    user = create_test_user(f"task_user_{uuid.uuid4().hex[:8]}@example.com")
    db = SessionLocal()
    proj = Project(
        user_id=user.id,
        title="My Epic Podcast Episode 42",
        source_type="upload",
        source_url="temp_media/actual_uploaded_video.mp4",
        status="pending"
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    proj_id = proj.id
    db.close()

    captured_args = {}

    def mock_run_pipeline(self, source, is_url=True, num_clips=3, **kwargs):
        captured_args["source"] = source
        captured_args["is_url"] = is_url
        yield {"agent": "mock", "status": "done", "progress": 100, "result": []}

    monkeypatch.setattr(ClipperOrchestratorAgent, "run_pipeline", mock_run_pipeline)

    # Run the pipeline task synchronously
    res = process_pipeline_task(proj_id)
    assert res["status"] == "success"
    # Ensure source was actual_uploaded_video.mp4 and NOT project.title
    assert captured_args["source"] == "temp_media/actual_uploaded_video.mp4"
    assert captured_args["source"] != "My Epic Podcast Episode 42"
    assert captured_args["is_url"] is False


def test_groq_api_key_passed_from_settings_to_orchestrator(monkeypatch):
    from backend.tasks import process_pipeline_task
    from agents.orchestrator import ClipperOrchestratorAgent

    user = create_test_user(f"groq_user_{uuid.uuid4().hex[:8]}@example.com")
    db = SessionLocal()
    proj = Project(
        user_id=user.id,
        title="Groq Key Pipeline Test",
        source_type="youtube",
        source_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        status="pending"
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    proj_id = proj.id
    db.close()

    mock_key = "gsk_test_pipeline_secret_key_99999"
    monkeypatch.setattr(settings, "GROQ_API_KEY", mock_key)

    captured_init = {}
    original_init = ClipperOrchestratorAgent.__init__

    def mock_init(self, project_root, api_key=None, provider="groq", **kwargs):
        captured_init["api_key"] = api_key
        captured_init["provider"] = provider
        original_init(self, project_root, api_key=api_key, provider=provider, **kwargs)

    def mock_run_pipeline(self, *args, **kwargs):
        yield {"agent": "mock", "status": "done", "progress": 100, "result": []}

    monkeypatch.setattr(ClipperOrchestratorAgent, "__init__", mock_init)
    monkeypatch.setattr(ClipperOrchestratorAgent, "run_pipeline", mock_run_pipeline)

    res = process_pipeline_task(proj_id)
    assert res["status"] == "success"
    assert captured_init["api_key"] == mock_key
    assert captured_init["provider"] == "groq"


def test_cors_restricted_to_known_origins():
    # 1. Known origin: http://localhost:3000
    resp_valid = client.get(
        "/health",
        headers={"Origin": "http://localhost:3000"}
    )
    assert resp_valid.status_code == 200
    assert resp_valid.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert resp_valid.headers.get("access-control-allow-credentials") == "true"

    # 2. Known origin: http://localhost:8501
    resp_streamlit = client.get(
        "/health",
        headers={"Origin": "http://localhost:8501"}
    )
    assert resp_streamlit.status_code == 200
    assert resp_streamlit.headers.get("access-control-allow-origin") == "http://localhost:8501"

    # 3. Disallowed external origin: https://malicious-phishing-attacker.com
    resp_invalid = client.get(
        "/health",
        headers={"Origin": "https://malicious-phishing-attacker.com"}
    )
    assert resp_invalid.status_code == 200
    assert "access-control-allow-origin" not in resp_invalid.headers


def test_usage_increment_and_plan_limit_enforcement(monkeypatch):
    from backend.tasks import process_pipeline_task
    from agents.orchestrator import ClipperOrchestratorAgent

    monkeypatch.setattr("backend.routes.projects.process_pipeline_task.delay", lambda *args, **kwargs: None)

    user = create_test_user(f"quota_user_{uuid.uuid4().hex[:8]}@example.com", plan="free")
    token = create_access_token({"sub": user.id, "email": user.email})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Initial usage check
    usage_init = client.get(f"{settings.API_V1_PREFIX}/usage/current", headers=headers).json()
    assert usage_init["clips_used"] == 0
    assert usage_init["monthly_limit"] == 5
    assert usage_init["remaining_clips"] == 5

    # 2. Mock orchestrator to render 3 clips and mock storage
    from pathlib import Path
    monkeypatch.setattr("backend.tasks.storage.upload_file", lambda path, key: f"https://mock-storage.com/{key}")

    mock_clips = [
        {"data": {"title": f"Clip {i}", "duration": 15.0, "viral_score": 90}, "path": f"temp_media/clip_{i}.mp4", "layout": "single_face"}
        for i in range(1, 4)
    ]
    def mock_run_pipeline(self, *args, **kwargs):
        yield {"agent": "mock", "status": "done", "progress": 100, "result": mock_clips}

    monkeypatch.setattr(ClipperOrchestratorAgent, "run_pipeline", mock_run_pipeline)

    # 3. Create project with num_clips=3
    proj_resp = client.post(
        f"{settings.API_V1_PREFIX}/projects/",
        json={"title": "Quota Test Project", "source_type": "upload", "source_url": "temp_media/input.mp4", "num_clips": 3},
        headers=headers
    )
    assert proj_resp.status_code == 201
    proj_id = proj_resp.json()["project_id"]

    # Run the pipeline task which renders clips and increments Usage
    process_pipeline_task(proj_id)

    # 4. Verify Usage table incremented to 3
    usage_after_3 = client.get(f"{settings.API_V1_PREFIX}/usage/current", headers=headers).json()
    assert usage_after_3["clips_used"] == 3
    assert usage_after_3["remaining_clips"] == 2

    # 5. Attempt to create project requesting 3 clips when remaining is 2 -> 403 Forbidden
    proj_overflow = client.post(
        f"{settings.API_V1_PREFIX}/projects/",
        json={"title": "Overflow Project", "source_type": "upload", "source_url": "temp_media/input.mp4", "num_clips": 3},
        headers=headers
    )
    assert proj_overflow.status_code == 403
    assert "would exceed monthly limit" in proj_overflow.json()["detail"].lower()

    # 6. Render 2 more clips to reach exact cap (5 clips)
    from backend.database import increment_user_usage
    db = SessionLocal()
    increment_user_usage(db=db, user_id=user.id, clips_delta=2)
    db.close()

    usage_capped = client.get(f"{settings.API_V1_PREFIX}/usage/current", headers=headers).json()
    assert usage_capped["clips_used"] == 5
    assert usage_capped["remaining_clips"] == 0

    # 7. Attempt project when fully capped -> 403 Forbidden
    proj_capped = client.post(
        f"{settings.API_V1_PREFIX}/projects/",
        json={"title": "Capped Project", "source_type": "upload", "source_url": "temp_media/input.mp4", "num_clips": 1},
        headers=headers
    )
    assert proj_capped.status_code == 403
    assert "limit of 5 clips reached" in proj_capped.json()["detail"].lower()

    # 8. Upgrade to Pro plan -> creation succeeds
    db = SessionLocal()
    u = db.query(User).filter(User.id == user.id).first()
    u.plan = "pro"
    db.commit()
    db.close()

    proj_pro = client.post(
        f"{settings.API_V1_PREFIX}/projects/",
        json={"title": "Pro Project", "source_type": "upload", "source_url": "temp_media/input.mp4", "num_clips": 3},
        headers=headers
    )
    assert proj_pro.status_code == 201






