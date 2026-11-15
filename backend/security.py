"""
Security & SSRF Guard
Prevents Server-Side Request Forgery (SSRF), DNS rebinding, private/link-local IP leakage,
and malicious redirects during media ingestion.
"""

import ipaddress
import socket
from urllib.parse import urlparse
from typing import Set, Optional


ALLOWED_MEDIA_DOMAINS: Set[str] = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "vimeo.com",
    "tiktok.com",
    "instagram.com",
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
