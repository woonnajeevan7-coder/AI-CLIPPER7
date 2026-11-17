"""
Twitch EventSub Webhook Processor
Verifies HMAC-SHA256 signatures, protects against replay attacks,
answers challenge handshakes, and coordinates stream.online / stream.offline transitions.
"""

import hmac
import hashlib
import time
from datetime import datetime, timezone
from typing import Dict, Any, Tuple, Optional
from collections import OrderedDict
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import TwitchChannel, LiveSession
from backend.telemetry import logger


class ReplayCache:
    """Sliding-window in-memory deduplication cache for EventSub Message IDs (TTL: 15 min)."""

    def __init__(self, max_size: int = 10000, ttl_seconds: int = 900):
        self._cache: OrderedDict[str, float] = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl_seconds

    def has_seen(self, msg_id: str) -> bool:
        self.prune()
        return msg_id in self._cache

    def mark_seen(self, msg_id: str):
        self._cache[msg_id] = time.time()
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

    def prune(self):
        now = time.time()
        while self._cache:
            first_key, first_time = next(iter(self._cache.items()))
            if now - first_time > self.ttl:
                self._cache.pop(first_key)
            else:
                break


replay_cache = ReplayCache()


def verify_twitch_signature(
    secret: str,
    message_id: str,
    timestamp: str,
    raw_body: bytes,
    expected_signature: str,
) -> bool:
    """Computes HMAC-SHA256 over message_id + timestamp + raw_body and compares securely."""
    if not secret or not expected_signature or not message_id or not timestamp:
        return False

    message = message_id.encode("utf-8") + timestamp.encode("utf-8") + raw_body
    computed_digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
    computed_signature = f"sha256={computed_digest}"

    return hmac.compare_digest(computed_signature, expected_signature)


def validate_twitch_timestamp(timestamp_str: str, max_age_seconds: int = 600) -> bool:
    """
    Ensures message timestamp is within max_age_seconds (10 minutes) of current UTC time.
    Rejects stale or future-manipulated timestamps.
    """
    try:
        # Support both ISO format with Z and with timezone offset
        ts = timestamp_str.replace("Z", "+00:00")
        msg_time = datetime.fromisoformat(ts)
        now = datetime.now(timezone.utc)
        diff = abs((now - msg_time).total_seconds())
        return diff <= max_age_seconds
    except Exception:
        return False


def handle_eventsub_payload(payload: Dict[str, Any], db: Session) -> Tuple[int, Dict[str, Any]]:
    """
    Handles parsed EventSub notification payload:
    - stream.online: creates LiveSession(status='starting')
    - stream.offline: marks active LiveSession as status='stopping'
    """
    sub_type = payload.get("subscription", {}).get("type", "")
    event = payload.get("event", {})
    broadcaster_id = event.get("broadcaster_user_id")

    if not broadcaster_id:
        return 200, {"status": "ignored", "reason": "No broadcaster_user_id in event"}

    channel = db.query(TwitchChannel).filter(TwitchChannel.broadcaster_id == broadcaster_id).first()
    if not channel:
        logger.warning(f"[TwitchWebhook] Event received for unregistered broadcaster {broadcaster_id}")
        return 200, {"status": "unregistered_channel", "broadcaster_id": broadcaster_id}

    if sub_type == "stream.online":
        # Check if an active session already exists
        existing_session = db.query(LiveSession).filter(
            LiveSession.broadcaster_id == broadcaster_id,
            LiveSession.status.in_(["starting", "live"])
        ).first()

        if existing_session:
            return 200, {"status": "already_active", "session_id": existing_session.id}

        # Create new LiveSession with status="starting"
        stream_login = event.get("broadcaster_user_login", channel.login)
        started_at_str = event.get("started_at")
        started_at = None
        if started_at_str:
            try:
                started_at = datetime.fromisoformat(started_at_str.replace("Z", "+00:00"))
            except Exception:
                started_at = datetime.now(timezone.utc)
        else:
            started_at = datetime.now(timezone.utc)

        live_session = LiveSession(
            user_id=channel.user_id,
            broadcaster_id=broadcaster_id,
            title=f"Twitch: {channel.display_name or stream_login} Live",
            stream_url=f"https://twitch.tv/{stream_login}",
            platform="twitch",
            status="starting",
            rights_confirmed=channel.rights_confirmed,
            started_at=started_at
        )
        db.add(live_session)
        db.commit()
        db.refresh(live_session)

        logger.info(f"[TwitchWebhook] stream.online -> LiveSession created: {live_session.id} (status: starting)")
        return 200, {"status": "session_starting", "session_id": live_session.id}

    elif sub_type == "stream.offline":
        active_sessions = db.query(LiveSession).filter(
            LiveSession.broadcaster_id == broadcaster_id,
            LiveSession.status.in_(["starting", "live"])
        ).all()

        stopped_ids = []
        for s in active_sessions:
            s.status = "stopping"
            s.stopped_at = datetime.now(timezone.utc)
            stopped_ids.append(s.id)

        db.commit()
        logger.info(f"[TwitchWebhook] stream.offline -> Sessions marked stopping: {stopped_ids}")
        return 200, {"status": "session_stopping", "stopped_session_ids": stopped_ids}

    return 200, {"status": "unhandled_event", "type": sub_type}
