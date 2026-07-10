from __future__ import annotations

from dataclasses import replace
import uuid

from backend.app.core.config import settings
from backend.app.security.passwords import hash_password, verify_password
from backend.app.security import session_tokens


def test_password_hash_round_trip() -> None:
    encoded = hash_password("CorrectHorseBatteryStaple1!")

    assert encoded.startswith("scrypt$")
    assert verify_password("CorrectHorseBatteryStaple1!", encoded) is True
    assert verify_password("wrong-password", encoded) is False


def test_password_hash_uses_unique_salt() -> None:
    first = hash_password("RepeatablePassword9!")
    second = hash_password("RepeatablePassword9!")

    assert first != second


def test_verify_password_rejects_malformed_hash() -> None:
    assert verify_password("anything", "not-a-valid-hash") is False


def test_session_token_round_trip(monkeypatch) -> None:
    monkeypatch.setattr(
        session_tokens,
        "settings",
        replace(settings, auth_secret_key="test-auth-secret"),
    )
    user_id = uuid.uuid4()

    token = session_tokens.issue_session_token(user_id, ttl_seconds=60)

    assert session_tokens.verify_session_token(token) == user_id


def test_session_token_rejects_tampering(monkeypatch) -> None:
    monkeypatch.setattr(
        session_tokens,
        "settings",
        replace(settings, auth_secret_key="test-auth-secret"),
    )
    user_id = uuid.uuid4()
    token = session_tokens.issue_session_token(user_id, ttl_seconds=60)
    tampered = f"{token[:-1]}x"

    assert session_tokens.verify_session_token(tampered) is None


def test_session_token_rejects_expired_token(monkeypatch) -> None:
    monkeypatch.setattr(
        session_tokens,
        "settings",
        replace(settings, auth_secret_key="test-auth-secret"),
    )
    user_id = uuid.uuid4()

    token = session_tokens.issue_session_token(user_id, ttl_seconds=-1)

    assert session_tokens.verify_session_token(token) is None


def test_session_cookie_settings_follow_config(monkeypatch) -> None:
    monkeypatch.setattr(
        session_tokens,
        "settings",
        replace(
            settings,
            auth_cookie_name="cial_test_session",
            auth_session_ttl_hours=12,
            auth_cookie_secure=True,
        ),
    )

    cookie_settings = session_tokens.session_cookie_settings()

    assert cookie_settings["key"] == "cial_test_session"
    assert cookie_settings["httponly"] is True
    assert cookie_settings["secure"] is True
    assert cookie_settings["max_age"] == 12 * 60 * 60
    assert cookie_settings["expires"] == 12 * 60 * 60
