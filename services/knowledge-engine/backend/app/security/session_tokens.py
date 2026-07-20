"""Signed session token helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

from backend.app.core.config import settings


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _sign(message: bytes) -> str:
    digest = hmac.new(
        settings.auth_secret_key.encode("utf-8"),
        message,
        hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


def issue_session_token(user_id: uuid.UUID, *, ttl_seconds: int | None = None) -> str:
    now = int(time.time())
    expires_at = now + int(
        ttl_seconds
        if ttl_seconds is not None
        else settings.auth_session_ttl_hours * 60 * 60
    )
    header = _b64url_encode(
        json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    payload = _b64url_encode(
        json.dumps(
            {
                "sub": str(user_id),
                "iat": now,
                "exp": expires_at,
            },
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = _sign(signing_input)
    return f"{header}.{payload}.{signature}"


def verify_session_token(token: str) -> uuid.UUID | None:
    try:
        header, payload, signature = token.split(".", 2)
    except ValueError:
        return None
    signing_input = f"{header}.{payload}".encode("ascii")
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(signature, expected_signature):
        return None
    try:
        payload_data = json.loads(_b64url_decode(payload).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload_data, dict):
        return None
    try:
        expires_at = int(payload_data.get("exp"))
        subject = uuid.UUID(str(payload_data.get("sub")))
    except (TypeError, ValueError):
        return None
    if expires_at <= int(time.time()):
        return None
    return subject


def session_cookie_settings() -> dict[str, Any]:
    max_age = settings.auth_session_ttl_hours * 60 * 60
    same_site = str(settings.auth_cookie_samesite or "lax").strip().lower()
    if same_site not in {"lax", "strict", "none"}:
        same_site = "lax"
    return {
        "key": settings.auth_cookie_name,
        "httponly": True,
        "max_age": max_age,
        "expires": max_age,
        "path": "/",
        "samesite": same_site,
        "secure": settings.auth_cookie_secure,
    }
