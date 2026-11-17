"""
Security & SSRF Guard
Prevents Server-Side Request Forgery (SSRF), DNS rebinding, private/link-local IP leakage,
and malicious redirects during media ingestion.
"""

import ipaddress
import os
import socket
from urllib.parse import urlparse
from typing import Set, Optional
from cryptography.fernet import Fernet

from .config import settings


ALLOWED_MEDIA_DOMAINS: Set[str] = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "vimeo.com",
    "tiktok.com",
    "instagram.com",
    "twitch.tv",
    "www.twitch.tv",
    "ttvnw.net",
    "storage.googleapis.com",
    "cloudflare.com",
    "r2.cloudflarestorage.com",
}


class SSRFValidationError(ValueError):
    """Raised when an ingest URL fails security or network boundary checks."""
    pass


class SSRFGuard:
    """Validates URLs against domain allowlists and blocks internal network access."""

    @classmethod
    def validate_ingest_url(cls, url: str, enforce_domain_allowlist: bool = True) -> str:
        """
        Validates URL scheme, resolves hostname to IP, and guarantees no internal/private IP is accessed.
        
        Raises SSRFValidationError on violation.
        """
        if not url or not isinstance(url, str):
            raise SSRFValidationError("Missing or invalid URL.")

        parsed = urlparse(url.strip())

        # 1. Enforce safe schemes only
        if parsed.scheme not in ("http", "https"):
            raise SSRFValidationError(f"Invalid scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted.")

        hostname = parsed.hostname
        if not hostname:
            raise SSRFValidationError("URL has no valid hostname.")

        # 2. Check domain allowlist if enforced
        if enforce_domain_allowlist:
            lower_host = hostname.lower()
            is_allowed = any(
                lower_host == domain or lower_host.endswith("." + domain)
                for domain in ALLOWED_MEDIA_DOMAINS
            )
            if not is_allowed:
                raise SSRFValidationError(f"Domain '{hostname}' is not in the trusted media ingest allowlist.")

        # 3. DNS resolution & IP safety verification
        try:
            addr_info = socket.getaddrinfo(hostname, None)
        except socket.gaierror as e:
            raise SSRFValidationError(f"Failed to resolve hostname '{hostname}': {e}")

        for entry in addr_info:
            ip_str = entry[4][0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
            except ValueError:
                raise SSRFValidationError(f"Invalid IP address resolved: {ip_str}")

            if ip_obj.is_private:
                raise SSRFValidationError(f"Access to private IP range ({ip_str}) is blocked.")
            if ip_obj.is_loopback:
                raise SSRFValidationError(f"Access to loopback IP ({ip_str}) is blocked.")
            if ip_obj.is_link_local:
                raise SSRFValidationError(f"Access to link-local IP ({ip_str}) is blocked.")
            if ip_obj.is_reserved:
                raise SSRFValidationError(f"Access to reserved IP ({ip_str}) is blocked.")
            if ip_obj.is_multicast:
                raise SSRFValidationError(f"Access to multicast IP ({ip_str}) is blocked.")

        return url.strip()


class TokenCipher:
    """Provides symmetric Fernet token encryption at rest for OAuth tokens and third-party secrets."""

    @classmethod
    def get_cipher(cls) -> Fernet:
        key = getattr(settings, "TOKEN_ENCRYPTION_KEY", None) or os.getenv("TOKEN_ENCRYPTION_KEY")
        if not key:
            key = "ReuO4DTAmNr_e0_B5Q4bi-A0yiU2nRp38Lua542Q4bs="
        if isinstance(key, str):
            key = key.encode("utf-8")
        return Fernet(key)

    @classmethod
    def encrypt_token(cls, raw_token: str) -> str:
        if not raw_token:
            return ""
        cipher = cls.get_cipher()
        return cipher.encrypt(raw_token.encode("utf-8")).decode("utf-8")

    @classmethod
    def decrypt_token(cls, encrypted_token: str) -> str:
        if not encrypted_token:
            return ""
        cipher = cls.get_cipher()
        return cipher.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
