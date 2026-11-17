"""
Twitch REST & Webhook Router (/api/v1/twitch)
Handles OAuth 2.0 authorization code flow with state validation,
TwitchChannel CRUD with ownership checks, and EventSub webhook ingestion.
"""

import json
import secrets
import urllib.parse
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, Header
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.models import User, SocialAccount, TwitchChannel, LiveSession
from backend.auth import get_current_user
from backend.security import TokenCipher
from backend.telemetry import logger
from .client import twitch_client
from .webhook import (
    verify_twitch_signature,
    validate_twitch_timestamp,
    handle_eventsub_payload,
    replay_cache
)

router = APIRouter(prefix="/twitch", tags=["Twitch"])

# In-memory OAuth state registry (user_id -> (state, expires_at))
_oauth_states: Dict[str, tuple[str, float]] = {}


class RegisterChannelRequest(BaseModel):
    broadcaster_id: Optional[str] = None
    login: str
    rights_confirmed: bool = False


class TwitchChannelResponse(BaseModel):
    id: str
    broadcaster_id: str
    login: str
    display_name: Optional[str]
    rights_confirmed: bool
    created_at: str


# --------------------------------------------------------------------------
# 1. OAuth 2.0 Flow
# --------------------------------------------------------------------------
@router.get("/auth")
def get_twitch_auth_url(current_user: User = Depends(get_current_user)):
    """
    Initiates Twitch OAuth 2.0 Authorization Code flow.
    Generates a secure state parameter bound to current_user.
    """
    state_token = secrets.token_urlsafe(32)
    # Store state for 15 minutes
    _oauth_states[state_token] = (current_user.id, datetime.now(timezone.utc).timestamp() + 900)

    scopes = [
        "user:read:email",
        "channel:read:subscriptions",
        "channel:read:stream_key",
    ]
    query_params = {
        "client_id": settings.TWITCH_CLIENT_ID,
        "redirect_uri": settings.TWITCH_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state_token,
    }
    auth_url = f"https://id.twitch.tv/oauth2/authorize?{urllib.parse.urlencode(query_params)}"
    return {
        "authorization_url": auth_url,
        "state": state_token,
    }


@router.get("/callback")
def handle_twitch_oauth_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """
    Exchanges code for tokens, encrypts tokens at rest with Fernet,
    resolves broadcaster profile, and registers SocialAccount + TwitchChannel.
    """
    # 1. Validate State
    now = datetime.now(timezone.utc).timestamp()
    state_data = _oauth_states.pop(state, None)
    if not state_data or state_data[1] < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state parameter."
        )
    user_id = state_data[0]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    # 2. Exchange authorization code for tokens
    try:
        token_data = twitch_client.exchange_code_for_token(code)
    except Exception as e:
        logger.error(f"[TwitchAuth] Token exchange failed: {e}")
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {str(e)}")

    access_token = token_data.get("access_token", "")
    refresh_token = token_data.get("refresh_token", "")
    expires_in = token_data.get("expires_in", 3600)
    scope_str = " ".join(token_data.get("scope", []))
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # 3. Resolve broadcaster identity
    try:
        broadcaster_info = twitch_client.resolve_broadcaster(login_or_id="", access_token=access_token)
    except Exception:
        # Fallback if resolve requires login: get self
        try:
            import requests
            headers = {"Client-ID": settings.TWITCH_CLIENT_ID, "Authorization": f"Bearer {access_token}"}
            res = requests.get("https://api.twitch.tv/helix/users", headers=headers, timeout=10)
            data = res.json().get("data", [{}])[0]
            broadcaster_info = {
                "id": data.get("id", ""),
                "login": data.get("login", ""),
                "display_name": data.get("display_name", data.get("login", "")),
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to resolve Twitch profile: {str(exc)}")

    broadcaster_id = broadcaster_info["id"]
    login = broadcaster_info["login"]
    display_name = broadcaster_info["display_name"]

    # 4. Encrypt tokens at rest using Fernet
    encrypted_access = TokenCipher.encrypt_token(access_token)
    encrypted_refresh = TokenCipher.encrypt_token(refresh_token) if refresh_token else None

    social = db.query(SocialAccount).filter(
        SocialAccount.user_id == user.id,
        SocialAccount.provider == "twitch"
    ).first()

    if not social:
        social = SocialAccount(
            user_id=user.id,
            provider="twitch",
            provider_user_id=broadcaster_id,
            encrypted_access_token=encrypted_access,
            encrypted_refresh_token=encrypted_refresh,
            token_expires_at=expires_at,
            scope=scope_str
        )
        db.add(social)
    else:
        social.provider_user_id = broadcaster_id
        social.encrypted_access_token = encrypted_access
        social.encrypted_refresh_token = encrypted_refresh
        social.token_expires_at = expires_at
        social.scope = scope_str

    # 5. Create or update TwitchChannel
    channel = db.query(TwitchChannel).filter(
        TwitchChannel.user_id == user.id,
        TwitchChannel.broadcaster_id == broadcaster_id
    ).first()

    if not channel:
        channel = TwitchChannel(
            user_id=user.id,
            broadcaster_id=broadcaster_id,
            login=login,
            display_name=display_name,
            rights_confirmed=False
        )
        db.add(channel)
    else:
        channel.login = login
        channel.display_name = display_name

    db.commit()
    db.refresh(channel)

    return {
        "status": "connected",
        "channel_id": channel.id,
        "broadcaster_id": channel.broadcaster_id,
        "login": channel.login,
        "display_name": channel.display_name,
    }


# --------------------------------------------------------------------------
# 2. Twitch Channels Management (Auth + Ownership)
# --------------------------------------------------------------------------
@router.post("/channels", status_code=status.HTTP_201_CREATED)
def register_twitch_channel(
    req: RegisterChannelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Registers a Twitch channel for live highlight clipping.
    Resolves broadcaster ID if not supplied and sets up EventSub webhooks.
    """
    broadcaster_id = req.broadcaster_id
    display_name = req.login

    # Resolve from Helix if broadcaster_id is missing
    if not broadcaster_id:
        try:
            profile = twitch_client.resolve_broadcaster(req.login)
            broadcaster_id = profile["id"]
            display_name = profile.get("display_name", req.login)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not resolve broadcaster '{req.login}': {str(e)}")

    # Check if channel already registered by this user
    existing = db.query(TwitchChannel).filter(
        TwitchChannel.user_id == current_user.id,
        TwitchChannel.broadcaster_id == broadcaster_id
    ).first()

    if existing:
        existing.rights_confirmed = req.rights_confirmed
        db.commit()
        db.refresh(existing)
        return {
            "id": existing.id,
            "broadcaster_id": existing.broadcaster_id,
            "login": existing.login,
            "display_name": existing.display_name,
            "rights_confirmed": existing.rights_confirmed,
            "created_at": existing.created_at.isoformat(),
        }

    # Subscribe to EventSub for stream.online & stream.offline if callback URL is configured
    sub_online_id = None
    sub_offline_id = None
    if settings.TWITCH_WEBHOOK_CALLBACK_URL:
        try:
            sub_online_id = twitch_client.subscribe_eventsub(broadcaster_id, "stream.online")
            sub_offline_id = twitch_client.subscribe_eventsub(broadcaster_id, "stream.offline")
        except Exception as e:
            logger.warning(f"[TwitchChannels] Failed to subscribe EventSub for {broadcaster_id}: {e}")

    channel = TwitchChannel(
        user_id=current_user.id,
        broadcaster_id=broadcaster_id,
        login=req.login.lower().strip(),
        display_name=display_name,
        rights_confirmed=req.rights_confirmed,
        eventsub_subscription_id_online=sub_online_id,
        eventsub_subscription_id_offline=sub_offline_id
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)

    return {
        "id": channel.id,
        "broadcaster_id": channel.broadcaster_id,
        "login": channel.login,
        "display_name": channel.display_name,
        "rights_confirmed": channel.rights_confirmed,
        "created_at": channel.created_at.isoformat(),
    }


@router.get("/channels")
def list_twitch_channels(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all Twitch channels owned by the current authenticated user."""
    channels = db.query(TwitchChannel).filter(
        TwitchChannel.user_id == current_user.id
    ).order_by(TwitchChannel.created_at.desc()).all()

    return [
        {
            "id": c.id,
            "broadcaster_id": c.broadcaster_id,
            "login": c.login,
            "display_name": c.display_name,
            "rights_confirmed": c.rights_confirmed,
            "created_at": c.created_at.isoformat(),
        }
        for c in channels
    ]


@router.delete("/channels/{channel_id}")
def delete_twitch_channel(
    channel_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Deletes a registered Twitch channel.
    Enforces strict ownership check (403 Forbidden if channel belongs to another user).
    """
    channel = db.query(TwitchChannel).filter(TwitchChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found.")

    if channel.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this channel."
        )

    # Clean up EventSub subscriptions
    if channel.eventsub_subscription_id_online:
        try:
            twitch_client.delete_eventsub(channel.eventsub_subscription_id_online)
        except Exception:
            pass
    if channel.eventsub_subscription_id_offline:
        try:
            twitch_client.delete_eventsub(channel.eventsub_subscription_id_offline)
        except Exception:
            pass

    db.delete(channel)
    db.commit()

    return {"status": "deleted", "id": channel_id}


# --------------------------------------------------------------------------
# 3. EventSub Webhook Ingestion
# --------------------------------------------------------------------------
@router.post("/webhook")
async def handle_twitch_webhook(
    request: Request,
    db: Session = Depends(get_db),
    twitch_eventsub_message_id: Optional[str] = Header(None, alias="Twitch-Eventsub-Message-Id"),
    twitch_eventsub_message_timestamp: Optional[str] = Header(None, alias="Twitch-Eventsub-Message-Timestamp"),
    twitch_eventsub_message_signature: Optional[str] = Header(None, alias="Twitch-Eventsub-Message-Signature"),
    twitch_eventsub_message_type: Optional[str] = Header(None, alias="Twitch-Eventsub-Message-Type"),
):
    """
    Webhook handler for Twitch EventSub notifications.
    Verifies HMAC-SHA256 signature, rejects replay attacks and expired timestamps,
    answers challenge verification, and reacts to stream.online/offline.
    """
    raw_body = await request.body()

    # 1. Require Headers
    if not twitch_eventsub_message_id or not twitch_eventsub_message_timestamp or not twitch_eventsub_message_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required Twitch EventSub headers."
        )

    # 2. Verify HMAC Signature
    is_valid_sig = verify_twitch_signature(
        secret=settings.TWITCH_EVENTSUB_SECRET,
        message_id=twitch_eventsub_message_id,
        timestamp=twitch_eventsub_message_timestamp,
        raw_body=raw_body,
        expected_signature=twitch_eventsub_message_signature
    )
    if not is_valid_sig:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid signature: HMAC verification failed."
        )

    # 3. Replay Protection: Check timestamp window (10 minutes)
    if not validate_twitch_timestamp(twitch_eventsub_message_timestamp, max_age_seconds=600):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message timestamp expired or out of allowed window."
        )

    # 4. Replay Protection: Check Duplicate Message ID
    if replay_cache.has_seen(twitch_eventsub_message_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Replay detected: Message ID '{twitch_eventsub_message_id}' already processed."
        )
    replay_cache.mark_seen(twitch_eventsub_message_id)

    # Parse JSON payload
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    # 5. Answer Challenge Handshake
    if twitch_eventsub_message_type == "webhook_callback_verification":
        challenge = payload.get("challenge", "")
        logger.info("[TwitchWebhook] Answering EventSub challenge handshake.")
        return Response(content=challenge, media_type="text/plain", status_code=200)

    # 6. Handle Event Notification
    status_code, result = handle_eventsub_payload(payload, db)
    return Response(content=json.dumps(result), media_type="application/json", status_code=status_code)
