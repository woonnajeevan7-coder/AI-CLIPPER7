"""
Phase 5 Verification Tests: Platform Backend
Tests SSRF security guard, JWT tokens, PostgreSQL models, usage limits, and FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from backend.security import SSRFGuard, SSRFValidationError
from backend.auth import hash_password, verify_password, create_access_token, decode_token
from backend.app import app
from backend.config import settings

client = TestClient(app)


def test_ssrf_guard_blocks_private_and_loopback_ips():
    # Loopback IP attack
    with pytest.raises(SSRFValidationError, match="Access to loopback IP|not in the trusted"):
        SSRFGuard.validate_ingest_url("http://127.0.0.1:8080/internal-data")

    # Private LAN IP attack
    with pytest.raises(SSRFValidationError, match="Access to private IP|not in the trusted"):
        SSRFGuard.validate_ingest_url("http://192.168.1.100/admin")

    # AWS/Cloud metadata service IP (169.254.169.254)
    with pytest.raises(SSRFValidationError, match="Access to link-local IP|not in the trusted"):
        SSRFGuard.validate_ingest_url("http://169.254.169.254/latest/meta-data/")

    # Dangerous scheme
    with pytest.raises(SSRFValidationError, match="Invalid scheme"):
        SSRFGuard.validate_ingest_url("file:///etc/passwd")


def test_ssrf_guard_allows_trusted_youtube_domain():
    valid_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    res = SSRFGuard.validate_ingest_url(valid_url, enforce_domain_allowlist=True)
    assert res == valid_url


def test_jwt_auth_lifecycle():
    plain = "SuperSecurePassword123!"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

    token = create_access_token({"sub": "user_123", "email": "test@example.com"})
    payload = decode_token(token)
    assert payload["sub"] == "user_123"
    assert payload["email"] == "test@example.com"
    assert payload["type"] == "access"


def test_fastapi_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["api_version"] == "v1"


def test_auth_register_and_login_flow():
    import uuid
    unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
    
    # Register
    reg_resp = client.post(
        f"{settings.API_V1_PREFIX}/auth/register",
        json={"email": unique_email, "password": "Password123!", "full_name": "Test User"}
    )
    assert reg_resp.status_code == 200
    reg_data = reg_resp.json()
    assert "access_token" in reg_data
    assert reg_data["email"] == unique_email
    assert reg_data["plan"] == "free"

    # Login
    login_resp = client.post(
        f"{settings.API_V1_PREFIX}/auth/login",
        json={"email": unique_email, "password": "Password123!"}
    )
    assert login_resp.status_code == 200
    login_data = login_resp.json()
    assert "access_token" in login_data

    # Protected me endpoint
    headers = {"Authorization": f"Bearer {login_data['access_token']}"}
    me_resp = client.get(f"{settings.API_V1_PREFIX}/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == unique_email


def test_usage_plans_endpoint():
    resp = client.get(f"{settings.API_V1_PREFIX}/usage/plans")
    assert resp.status_code == 200
    plans = resp.json()
    assert len(plans) >= 3
    plan_names = [p["id"] for p in plans]
    assert "free" in plan_names
    assert "pro" in plan_names
    assert "agency" in plan_names
