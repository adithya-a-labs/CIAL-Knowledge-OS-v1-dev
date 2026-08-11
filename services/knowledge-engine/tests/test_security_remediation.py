from __future__ import annotations

from dataclasses import replace
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.core.application_config import validate_repository_path
from backend.app.core.config import settings
from backend.app.schemas.chat import ChatRequest
from backend.app.security.http_security import HttpSecurityMiddleware
from backend.app.security.rate_limit import AuthenticationRateLimiter
from backend.app.security.session_tokens import (
    issue_csrf_token,
    issue_session_token,
    verify_session_claims,
)
from backend.app.services.document_preview_service import (
    ResolvedDocument,
    _html_to_safe_fragment,
    file_response,
)
from backend.app.services.document_service import DocumentService, DocumentUploadError


def _security_test_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(HttpSecurityMiddleware)

    @app.post("/change")
    def change() -> dict[str, bool]:
        return {"ok": True}

    return TestClient(app)


def test_session_claims_are_versioned_and_tamper_evident() -> None:
    user_id = uuid.uuid4()
    token = issue_session_token(user_id, session_version=7, ttl_seconds=60)
    claims = verify_session_claims(token)

    assert claims is not None
    assert claims.user_id == user_id
    assert claims.session_version == 7
    assert verify_session_claims(f"{token[:-1]}{'A' if token[-1] != 'A' else 'B'}") is None


def test_csrf_and_origin_checks_fail_closed_for_cookie_sessions() -> None:
    client = _security_test_client()
    client.cookies.set(settings.auth_cookie_name, "synthetic-session")

    assert client.post("/change").status_code == 403
    assert client.post(
        "/change",
        headers={"Origin": "https://untrusted.invalid", "Sec-Fetch-Site": "cross-site"},
    ).status_code == 403

    token = issue_csrf_token()
    client.cookies.set("cial_csrf", token)
    response = client.post("/change", headers={"X-CIAL-CSRF-Token": token})

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"


def test_authentication_rate_limit_is_account_and_address_scoped() -> None:
    limiter = AuthenticationRateLimiter()
    decisions = [
        limiter.check(action="login", client_ip="127.0.0.1", account="USER@example.test")
        for _ in range(9)
    ]

    assert all(decision.allowed for decision in decisions[:8])
    assert decisions[-1].allowed is False
    assert decisions[-1].retry_after_seconds > 0
    assert limiter.check(action="login", client_ip="127.0.0.2", account="user@example.test").allowed


def test_active_content_is_attachment_only_and_sandboxed(tmp_path) -> None:
    source = tmp_path / "active.html"
    source.write_text("<script>alert(1)</script>", encoding="utf-8")
    response = file_response(
        ResolvedDocument(
            metadata={"name": "active.html", "mime_type": "text/html"},
            path=source,
            extension=".html",
            content_hash="synthetic",
        ),
        disposition="inline",
    )

    assert response.media_type == "application/octet-stream"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "sandbox" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_preview_sanitizer_removes_active_markup_and_attributes() -> None:
    cleaned = _html_to_safe_fragment(
        '<svg onload="alert(1)"></svg><a href="javascript:alert(2)">link</a><p style="x">safe</p>'
    )

    assert "svg" not in cleaned
    assert "javascript:" not in cleaned
    assert "href=" not in cleaned
    assert "style=" not in cleaned
    assert "<p>safe</p>" in cleaned


def test_repository_roots_and_windows_reserved_names_fail_closed(tmp_path, monkeypatch) -> None:
    repository = tmp_path / "outside"
    repository.mkdir()
    monkeypatch.delenv("CIAL_ALLOWED_CORPUS_ROOTS", raising=False)

    validation = validate_repository_path(repository)

    assert validation.valid is False
    assert "outside" in validation.message.casefold()
    with pytest.raises(DocumentUploadError):
        DocumentService._safe_filename("..\\CON.txt")


def test_chat_request_bounds_context_and_question_size() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(question="x" * 8_001)
    with pytest.raises(ValidationError):
        ChatRequest(question="ok", selected_document_ids=[str(index) for index in range(21)])


def test_production_model_policy_requires_consistent_offline_flags(monkeypatch) -> None:
    monkeypatch.setenv("CIAL_AUTH_SECRET_KEY", "a" * 32)
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    with pytest.raises(ValueError, match="CIAL_LOCAL_FILES_ONLY"):
        replace(
            settings,
            environment="production",
            auth_secret_key="a" * 32,
            qdrant_api_key="q" * 24,
            reranker_local_files_only=False,
        )

    monkeypatch.setenv("CIAL_LOCAL_FILES_ONLY", "true")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "0")
    with pytest.raises(ValueError, match="TRANSFORMERS_OFFLINE"):
        replace(
            settings,
            environment="production",
            auth_secret_key="a" * 32,
            qdrant_api_key="q" * 24,
            reranker_local_files_only=True,
        )


def test_production_auth_secret_remains_fail_closed(monkeypatch) -> None:
    monkeypatch.delenv("CIAL_AUTH_SECRET_KEY", raising=False)
    monkeypatch.delenv("AUTH_SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="CIAL_AUTH_SECRET_KEY is required"):
        replace(
            settings,
            environment="production",
            qdrant_api_key="q" * 24,
        )

    monkeypatch.setenv("CIAL_AUTH_SECRET_KEY", "change-me")
    with pytest.raises(ValueError, match="strong, non-default"):
        replace(
            settings,
            environment="production",
            auth_secret_key="change-me",
            qdrant_api_key="q" * 24,
        )
