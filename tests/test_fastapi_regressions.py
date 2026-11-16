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

