"""Signed session token helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Any

from backend.app.core.config import settings


@dataclass(frozen=True, slots=True)
class SessionClaims:
    user_id: uuid.UUID
    session_version: int
    issued_at: int
    expires_at: int


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


def issue_session_token(
    user_id: uuid.UUID,
    *,
    session_version: int = 0,
    ttl_seconds: int | None = None,
) -> str:
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
                "ver": int(session_version),
                "iat": now,
                "exp": expires_at,
            },
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = _sign(signing_input)
    return f"{header}.{payload}.{signature}"


def verify_session_claims(token: str) -> SessionClaims | None:
    try:
        header, payload, signature = token.split(".", 2)
    except ValueError:
        return None
    signing_input = f"{header}.{payload}".encode("ascii")
    expected_signature = _sign(signing_input)
    if not hmac.compare_digest(signature, expected_signature):
        return None
    try:
        header_data = json.loads(_b64url_decode(header).decode("utf-8"))
        payload_data = json.loads(_b64url_decode(payload).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if header_data != {"alg": "HS256", "typ": "JWT"} or not isinstance(payload_data, dict):
        return None
    try:
        expires_at = int(payload_data.get("exp"))
        issued_at = int(payload_data.get("iat"))
        session_version = int(payload_data.get("ver", 0))
        subject = uuid.UUID(str(payload_data.get("sub")))
    except (TypeError, ValueError):
        return None
    now = int(time.time())
    if expires_at <= now or issued_at > now + 60 or expires_at <= issued_at or session_version < 0:
        return None
    return SessionClaims(
        user_id=subject,
        session_version=session_version,
        issued_at=issued_at,
        expires_at=expires_at,
    )


def verify_session_token(token: str) -> uuid.UUID | None:
    claims = verify_session_claims(token)
    return claims.user_id if claims is not None else None


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


def issue_csrf_token() -> str:
    nonce = secrets.token_urlsafe(32)
    return f"{nonce}.{_sign(f'csrf:{nonce}'.encode('ascii'))}"


def verify_csrf_token(token: str) -> bool:
    try:
        nonce, signature = token.rsplit(".", 1)
    except ValueError:
        return False
    if len(nonce) < 32:
        return False
    return hmac.compare_digest(signature, _sign(f"csrf:{nonce}".encode("ascii")))


def csrf_cookie_settings() -> dict[str, Any]:
    settings_ = session_cookie_settings()
    return {
        "key": "cial_csrf",
        "httponly": False,
        "max_age": settings_["max_age"],
        "expires": settings_["expires"],
        "path": "/",
        "samesite": settings_["samesite"],
        "secure": settings_["secure"],
    }
