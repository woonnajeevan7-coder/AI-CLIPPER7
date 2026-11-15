"""
Phase 9 Verification Tests: Production Hardening
Tests operational cost accounting, request correlation IDs, Sentry/logging, DMCA takedown flow, and CI config.
"""

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.telemetry import CostTracker, JobCostReport

client = TestClient(app)


def test_cost_tracker_calculation():
    report = CostTracker.calculate_cost(
        job_id="job_prod_001",
        prompt_tokens=15000,
        completion_tokens=2500,
        audio_duration_seconds=120.0,
        render_seconds=45.0
    )
    assert isinstance(report, JobCostReport)
    assert report.job_id == "job_prod_001"
    assert report.llm_cost_cents > 0
    assert report.transcription_cost_cents > 0
    assert report.compute_cost_cents > 0
    assert report.total_cost_cents == round(
        report.llm_cost_cents + report.transcription_cost_cents + report.compute_cost_cents, 4
    )


def test_request_id_middleware():
    # Auto-generated Request ID
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) > 10

    # Custom Request ID propagation
    custom_id = "req_custom_trace_9999"
    resp2 = client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp2.headers["X-Request-ID"] == custom_id


def test_legal_and_dmca_compliance_endpoints():
    # Terms of service
    t_resp = client.get("/api/v1/legal/terms")
    assert t_resp.status_code == 200
    assert "Terms of Service" in t_resp.json()["title"]

    # Privacy policy
    p_resp = client.get("/api/v1/legal/privacy")
    assert p_resp.status_code == 200
    assert "Privacy Policy" in p_resp.json()["title"]

    # DMCA rejection without good-faith statements
    bad_dmca = client.post(
        "/api/v1/legal/dmca",
        json={
            "reporter_name": "John Doe",
            "reporter_email": "john@example.com",
            "copyright_owner_name": "Studio LLC",
            "original_work_url": "https://youtube.com/original",
            "infringing_clip_id": "clip_xyz",
            "statement_of_authority": False,
            "good_faith_statement": False
        }
    )
    assert bad_dmca.status_code == 400

    # Valid DMCA takedown notice
    good_dmca = client.post(
        "/api/v1/legal/dmca",
        json={
            "reporter_name": "John Doe",
            "reporter_email": "john@example.com",
            "copyright_owner_name": "Studio LLC",
            "original_work_url": "https://youtube.com/original",
            "infringing_clip_id": "clip_xyz",
            "statement_of_authority": True,
            "good_faith_statement": True
        }
    )
    assert good_dmca.status_code == 201
    assert good_dmca.json()["status"] == "received"
    assert "DMCA-" in good_dmca.json()["ticket_id"]


def test_ci_pipeline_configuration():
    ci_file = Path(".github/workflows/ci.yml")
    assert ci_file.exists()
    content = ci_file.read_text(encoding="utf-8")
    assert "pytest -v" in content
    assert "docker/build-push-action" in content
