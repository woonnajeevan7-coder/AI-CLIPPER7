"""
TDD Tests for Twitch OAuth 2.0, Helix API, EventSub Webhooks, and Fernet Encryption
Verifies:
1. HMAC signature verification (accept valid, reject invalid)
2. Replay attack rejection (duplicate message ID within window & expired timestamp)
3. EventSub challenge response (webhook_callback_verification -> 200 with challenge)
4. Multi-tenant channel ownership enforcement (403 for unauthorized access/delete)
5. Fernet token encryption at rest for SocialAccount credentials
6. stream.online event handler creating LiveSession(status="starting")
7. stream.offline event handler updating LiveSession(status="stopping")
8. OAuth state validation (reject invalid state)
"""

import hmac
import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from backend.config import settings
from backend.database import SessionLocal
from backend.models import User, LiveSession
from backend.auth import create_access_token, hash_password
from backend.security import TokenCipher

client = TestClient(app)


def create_user(email_prefix: str) -> User:
    db = SessionLocal()
    user = User(
        id=str(uuid.uuid4()),
        email=f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=hash_password("TwitchTestPass123!"),
        full_name="Twitch Test User",
        plan="pro",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def compute_twitch_signature(secret: str, msg_id: str, timestamp: str, body_bytes: bytes) -> str:
    """Computes Twitch EventSub HMAC-SHA256 signature: sha256=<hex>"""
    hmac_obj = hmac.new(secret.encode("utf-8"), msg_id.encode("utf-8") + timestamp.encode("utf-8") + body_bytes, hashlib.sha256)
    return f"sha256={hmac_obj.hexdigest()}"


# --------------------------------------------------------------------------
# 1. Signature Accept & Challenge Answer
# --------------------------------------------------------------------------
def test_twitch_webhook_signature_accept_and_challenge(monkeypatch):
    test_secret = "test_eventsub_secret_key_12345"
    monkeypatch.setattr(settings, "TWITCH_EVENTSUB_SECRET", test_secret)

    msg_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    challenge_token = "twitch_verification_challenge_token_98765"
    payload = {
        "challenge": challenge_token,
        "subscription": {
            "id": "sub_12345",
            "type": "stream.online",
            "version": "1",
            "status": "webhook_callback_verification_pending"
        }
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_twitch_signature(test_secret, msg_id, timestamp, body_bytes)

    headers = {
        "Twitch-Eventsub-Message-Id": msg_id,
        "Twitch-Eventsub-Message-Timestamp": timestamp,
        "Twitch-Eventsub-Message-Signature": sig,
        "Twitch-Eventsub-Message-Type": "webhook_callback_verification",
        "Content-Type": "application/json"
    }

    res = client.post("/api/v1/twitch/webhook", content=body_bytes, headers=headers)
    assert res.status_code == 200
    assert res.text == challenge_token


# --------------------------------------------------------------------------
# 2. Signature Reject (Invalid HMAC)
# --------------------------------------------------------------------------
def test_twitch_webhook_signature_reject(monkeypatch):
    test_secret = "test_eventsub_secret_key_12345"
    monkeypatch.setattr(settings, "TWITCH_EVENTSUB_SECRET", test_secret)

    msg_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {"test": "data"}
    body_bytes = json.dumps(payload).encode("utf-8")
    fake_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

    headers = {
        "Twitch-Eventsub-Message-Id": msg_id,
        "Twitch-Eventsub-Message-Timestamp": timestamp,
        "Twitch-Eventsub-Message-Signature": fake_sig,
        "Twitch-Eventsub-Message-Type": "notification",
        "Content-Type": "application/json"
    }

    res = client.post("/api/v1/twitch/webhook", content=body_bytes, headers=headers)
    assert res.status_code == 403
    assert "Invalid signature" in res.json().get("detail", "")


# --------------------------------------------------------------------------
# 3. Replayed Message ID & Expired Timestamp Rejection
# --------------------------------------------------------------------------
def test_twitch_webhook_replayed_message_rejected(monkeypatch):
    test_secret = "test_eventsub_secret_key_12345"
    monkeypatch.setattr(settings, "TWITCH_EVENTSUB_SECRET", test_secret)

    msg_id = f"replayed_id_{uuid.uuid4().hex}"
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "subscription": {"type": "stream.online"},
        "event": {"broadcaster_user_id": "999999"}
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_twitch_signature(test_secret, msg_id, timestamp, body_bytes)

    headers = {
        "Twitch-Eventsub-Message-Id": msg_id,
        "Twitch-Eventsub-Message-Timestamp": timestamp,
        "Twitch-Eventsub-Message-Signature": sig,
        "Twitch-Eventsub-Message-Type": "notification",
        "Content-Type": "application/json"
    }

    # First delivery succeeds
    res1 = client.post("/api/v1/twitch/webhook", content=body_bytes, headers=headers)
    assert res1.status_code in (200, 202)

    # Replay with same Message-Id is rejected
    res2 = client.post("/api/v1/twitch/webhook", content=body_bytes, headers=headers)
    assert res2.status_code in (400, 409)
    assert "Replay" in res2.json().get("detail", "") or "Duplicate" in res2.json().get("detail", "")


def test_twitch_webhook_expired_timestamp_rejected(monkeypatch):
    test_secret = "test_eventsub_secret_key_12345"
    monkeypatch.setattr(settings, "TWITCH_EVENTSUB_SECRET", test_secret)

    msg_id = str(uuid.uuid4())
    # Timestamp from 15 minutes ago
    expired_timestamp = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    payload = {"test": "data"}
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_twitch_signature(test_secret, msg_id, expired_timestamp, body_bytes)

    headers = {
        "Twitch-Eventsub-Message-Id": msg_id,
        "Twitch-Eventsub-Message-Timestamp": expired_timestamp,
        "Twitch-Eventsub-Message-Signature": sig,
        "Twitch-Eventsub-Message-Type": "notification",
        "Content-Type": "application/json"
    }

    res = client.post("/api/v1/twitch/webhook", content=body_bytes, headers=headers)
    assert res.status_code in (400, 403)
    assert "timestamp" in res.json().get("detail", "").lower()


# --------------------------------------------------------------------------
# 4. Multi-Tenant Channel Ownership (403 Enforcement)
# --------------------------------------------------------------------------
def test_twitch_channel_ownership_403(monkeypatch):
    # Mock Twitch Helix client call so channel registration succeeds
    from backend.twitch.client import twitch_client
    monkeypatch.setattr(twitch_client, "resolve_broadcaster", lambda login, **kw: {
        "id": "12345678", "login": login.lower(), "display_name": login
    })
    monkeypatch.setattr(twitch_client, "subscribe_eventsub", lambda **kw: "mock_sub_id")

    user_a = create_user("owner_a")
    user_b = create_user("attacker_b")
    token_a = create_access_token({"sub": user_a.id, "email": user_a.email})
    token_b = create_access_token({"sub": user_b.id, "email": user_b.email})

    # User A registers their Twitch Channel with rights confirmed
    create_res = client.post(
        "/api/v1/twitch/channels",
        json={"broadcaster_id": "12345678", "login": "streamer_a", "rights_confirmed": True},
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert create_res.status_code == 201
    channel_id = create_res.json()["id"]

    # User B attempts to delete User A's channel -> 403 Forbidden
    del_res = client.delete(
        f"/api/v1/twitch/channels/{channel_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert del_res.status_code == 403
    assert "Not authorized" in del_res.json().get("detail", "")

    # User A can delete their own channel -> 200 OK
    del_ok = client.delete(
        f"/api/v1/twitch/channels/{channel_id}",
        headers={"Authorization": f"Bearer {token_a}"}
    )
    assert del_ok.status_code == 200


# --------------------------------------------------------------------------
# 5. Token Encryption at Rest (Fernet)
# --------------------------------------------------------------------------
def test_token_encryption_with_fernet():
    raw_token = "oauth_twitch_access_token_secret_xyz123"
    encrypted = TokenCipher.encrypt_token(raw_token)
    assert encrypted != raw_token
    assert not encrypted.startswith("oauth_twitch")

    decrypted = TokenCipher.decrypt_token(encrypted)
    assert decrypted == raw_token


# --------------------------------------------------------------------------
# 6. stream.online Event Creates LiveSession(status="starting")
# --------------------------------------------------------------------------
def test_stream_online_creates_live_session(monkeypatch):
    test_secret = "test_eventsub_secret_key_12345"
    monkeypatch.setattr(settings, "TWITCH_EVENTSUB_SECRET", test_secret)

    # Setup channel in DB
    user = create_user("broadcaster_user")
    from backend.models import TwitchChannel
    db = SessionLocal()
    b_id = f"streamer_{uuid.uuid4().hex[:6]}"
    chan = TwitchChannel(
        id=str(uuid.uuid4()),
        user_id=user.id,
        broadcaster_id=b_id,
        login="progamer",
        display_name="ProGamer",
        rights_confirmed=True
    )
    db.add(chan)
    db.commit()
    db.close()

    msg_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "subscription": {
            "id": "sub_online_1",
            "type": "stream.online"
        },
        "event": {
            "id": "live_stream_999",
            "broadcaster_user_id": b_id,
            "broadcaster_user_login": "progamer",
            "broadcaster_user_name": "ProGamer",
            "type": "live",
            "started_at": timestamp
        }
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_twitch_signature(test_secret, msg_id, timestamp, body_bytes)

    headers = {
        "Twitch-Eventsub-Message-Id": msg_id,
        "Twitch-Eventsub-Message-Timestamp": timestamp,
        "Twitch-Eventsub-Message-Signature": sig,
        "Twitch-Eventsub-Message-Type": "notification",
        "Content-Type": "application/json"
    }

    res = client.post("/api/v1/twitch/webhook", content=body_bytes, headers=headers)
    assert res.status_code == 200

    # Verify LiveSession created in DB
    db = SessionLocal()
    session = db.query(LiveSession).filter(
        LiveSession.broadcaster_id == b_id,
        LiveSession.status == "starting"
    ).first()
    assert session is not None
    assert session.user_id == user.id
    assert session.platform == "twitch"
    assert session.rights_confirmed is True
    db.close()


# --------------------------------------------------------------------------
# 7. stream.offline Event Updates LiveSession(status="stopping")
# --------------------------------------------------------------------------
def test_stream_offline_marks_live_session_stopping(monkeypatch):
    test_secret = "test_eventsub_secret_key_12345"
    monkeypatch.setattr(settings, "TWITCH_EVENTSUB_SECRET", test_secret)

    user = create_user("offline_broadcaster")
    from backend.models import TwitchChannel
    db = SessionLocal()
    b_id = f"streamer_{uuid.uuid4().hex[:6]}"
    chan = TwitchChannel(
        id=str(uuid.uuid4()),
        user_id=user.id,
        broadcaster_id=b_id,
        login="offlineguy",
        rights_confirmed=True
    )
    db.add(chan)

    # Active LiveSession
    session_id = str(uuid.uuid4())
    session = LiveSession(
        id=session_id,
        user_id=user.id,
        broadcaster_id=b_id,
        title="Live Stream",
        stream_url=f"https://twitch.tv/offlineguy",
        platform="twitch",
        status="live",
        rights_confirmed=True,
        started_at=datetime.now(timezone.utc)
    )
    db.add(session)
    db.commit()
    db.close()

    msg_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {
        "subscription": {
            "id": "sub_offline_1",
            "type": "stream.offline"
        },
        "event": {
            "broadcaster_user_id": b_id,
            "broadcaster_user_login": "offlineguy",
            "broadcaster_user_name": "OfflineGuy"
        }
    }
    body_bytes = json.dumps(payload).encode("utf-8")
    sig = compute_twitch_signature(test_secret, msg_id, timestamp, body_bytes)

    headers = {
        "Twitch-Eventsub-Message-Id": msg_id,
        "Twitch-Eventsub-Message-Timestamp": timestamp,
        "Twitch-Eventsub-Message-Signature": sig,
        "Twitch-Eventsub-Message-Type": "notification",
        "Content-Type": "application/json"
    }

    res = client.post("/api/v1/twitch/webhook", content=body_bytes, headers=headers)
    assert res.status_code == 200

    # Verify session marked as stopping
    db = SessionLocal()
    updated_session = db.query(LiveSession).filter(LiveSession.id == session_id).first()
    assert updated_session is not None
    assert updated_session.status == "stopping"
    db.close()


# --------------------------------------------------------------------------
# 8. OAuth State Validation (Reject Invalid or Expired State)
# --------------------------------------------------------------------------
def test_twitch_oauth_state_validation():
    # Calling callback with an unknown state parameter must return 400
    res = client.get("/api/v1/twitch/callback?code=mock_auth_code_123&state=invalid_unregistered_state")
    assert res.status_code == 400
    assert "Invalid or expired OAuth state" in res.json().get("detail", "")

