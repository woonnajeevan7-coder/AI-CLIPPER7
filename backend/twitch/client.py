"""
Twitch Helix & OAuth 2.0 Client
Implements OAuth authorization code exchange, user/broadcaster resolution,
stream metadata retrieval, and EventSub webhook subscription lifecycle.
"""

import time
from typing import Dict, Any, Optional, List
import requests

from backend.config import settings
from backend.telemetry import logger


class TwitchHelixClient:
    """Async/Sync-compatible client for Twitch Helix REST API and EventSub."""

    OAUTH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
    HELIX_BASE_URL = "https://api.twitch.tv/helix"

    def __init__(self):
        self._app_token: Optional[str] = None
        self._app_token_expires_at: float = 0

    @property
    def client_id(self) -> str:
        return settings.TWITCH_CLIENT_ID

    @property
    def client_secret(self) -> str:
        return settings.TWITCH_CLIENT_SECRET

    @property
    def redirect_uri(self) -> str:
        return settings.TWITCH_REDIRECT_URI

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchanges an authorization code for an OAuth access and refresh token."""
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        res = requests.post(self.OAUTH_TOKEN_URL, data=payload, timeout=10)
        res.raise_for_status()
        return res.json()

    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refreshes an expired user access token."""
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        res = requests.post(self.OAUTH_TOKEN_URL, data=payload, timeout=10)
        res.raise_for_status()
        return res.json()

    def get_app_access_token(self) -> str:
        """Retrieves or returns a cached app access token (Client Credentials grant)."""
        now = time.time()
        if self._app_token and now < (self._app_token_expires_at - 60):
            return self._app_token

        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }
        res = requests.post(self.OAUTH_TOKEN_URL, data=payload, timeout=10)
        res.raise_for_status()
        data = res.json()
        self._app_token = data["access_token"]
        self._app_token_expires_at = now + data.get("expires_in", 3600)
        return self._app_token

    def _get_headers(self, token: Optional[str] = None) -> Dict[str, str]:
        bearer = token or self.get_app_access_token()
        return {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
        }

    def resolve_broadcaster(self, login_or_id: str, access_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Resolves a broadcaster profile by login name or broadcaster ID.
        Returns dict with keys: id, login, display_name, profile_image_url.
        """
        headers = self._get_headers(access_token)
        param = "id" if login_or_id.isdigit() else "login"
        url = f"{self.HELIX_BASE_URL}/users?{param}={login_or_id.lower().strip()}"
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json().get("data", [])
        if not data:
            raise ValueError(f"Twitch broadcaster '{login_or_id}' not found.")
        user_info = data[0]
        return {
            "id": user_info["id"],
            "login": user_info["login"],
            "display_name": user_info.get("display_name", user_info["login"]),
            "profile_image_url": user_info.get("profile_image_url", ""),
        }

    def get_stream_metadata(self, broadcaster_id: str, access_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Fetches live stream metadata for broadcaster_id.
        Returns dict with title, game_name, viewer_count, started_at or None if offline.
        """
        headers = self._get_headers(access_token)
        url = f"{self.HELIX_BASE_URL}/streams?user_id={broadcaster_id}"
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json().get("data", [])
        if not data:
            return None
        stream = data[0]
        return {
            "id": stream.get("id"),
            "broadcaster_id": stream.get("user_id"),
            "broadcaster_login": stream.get("user_login"),
            "title": stream.get("title", ""),
            "game_name": stream.get("game_name", ""),
            "viewer_count": stream.get("viewer_count", 0),
            "started_at": stream.get("started_at"),
            "type": stream.get("type", "live"),
        }

    def subscribe_eventsub(
        self,
        broadcaster_id: str,
        event_type: str,
        callback_url: Optional[str] = None,
        secret: Optional[str] = None,
    ) -> str:
        """
        Creates an EventSub webhook subscription on Twitch for stream.online or stream.offline.
        Returns the subscription ID string.
        """
        callback = callback_url or settings.TWITCH_WEBHOOK_CALLBACK_URL
        sec = secret or settings.TWITCH_EVENTSUB_SECRET
        if not callback:
            raise ValueError("TWITCH_WEBHOOK_CALLBACK_URL is required for EventSub.")

        payload = {
            "type": event_type,
            "version": "1",
            "condition": {"broadcaster_user_id": broadcaster_id},
            "transport": {
                "method": "webhook",
                "callback": callback,
                "secret": sec,
            },
        }

        headers = self._get_headers()
        res = requests.post(f"{self.HELIX_BASE_URL}/eventsub/subscriptions", json=payload, headers=headers, timeout=10)
        res.raise_for_status()
        data = res.json().get("data", [])
        if not data:
            raise RuntimeError(f"Failed to subscribe to EventSub {event_type}")
        return data[0]["id"]

    def delete_eventsub(self, subscription_id: str) -> bool:
        """Deletes an active EventSub subscription."""
        headers = self._get_headers()
        url = f"{self.HELIX_BASE_URL}/eventsub/subscriptions?id={subscription_id}"
        res = requests.delete(url, headers=headers, timeout=10)
        return res.status_code in (200, 204)


twitch_client = TwitchHelixClient()
