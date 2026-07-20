from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes import auth, workspaces
from backend.app.core.config import settings
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.schemas.workspaces import WorkspacePreferences
from backend.app.security import access
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
            auth_cookie_samesite="none",
        ),
    )

    cookie_settings = session_tokens.session_cookie_settings()

    assert cookie_settings["key"] == "cial_test_session"
    assert cookie_settings["httponly"] is True
    assert cookie_settings["secure"] is True
    assert cookie_settings["samesite"] == "none"
    assert cookie_settings["max_age"] == 12 * 60 * 60
    assert cookie_settings["expires"] == 12 * 60 * 60


class _FakeAuthService:
    def __init__(self, user_id: uuid.UUID, profile: AuthenticatedUser) -> None:
        self.user_id = user_id
        self.profile = profile

    def login(self, *, email: str, password: str):
        if email != "session.user@cial.in" or password != "CorrectHorseBatteryStaple1!":
            raise auth.AuthInvalidCredentials("Invalid email or password.")
        return SimpleNamespace(user=SimpleNamespace(id=self.user_id), profile=self.profile)

    def get_user_profile(self, user_id: uuid.UUID):
        if user_id != self.user_id:
            return None
        return self.profile


class _FakeSession:
    def __init__(self, user) -> None:
        self.user = user

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def scalar(self, _statement):
        return self.user


def _auth_test_client(monkeypatch):
    user_id = uuid.uuid4()
    profile = AuthenticatedUser(
        id=str(user_id),
        email="session.user@cial.in",
        display_name="Session User",
        initials="SU",
        organization_name="CIAL",
        department_name="Shared Knowledge",
        role_names=["Viewer"],
        permission_names=["view_enterprise_documents"],
        notifications_count=0,
    )
    test_settings = replace(
        settings,
        auth_secret_key="route-test-auth-secret",
        auth_cookie_name="cial_route_test_session",
        auth_session_ttl_hours=12,
        auth_cookie_secure=False,
        auth_cookie_samesite="lax",
    )
    user = SimpleNamespace(
        id=user_id,
        organization_id=uuid.uuid4(),
        department_id=None,
        is_active=True,
        roles=[],
        department_memberships=[],
        department_role_assignments=[],
        group_memberships=[],
    )
    monkeypatch.setattr(session_tokens, "settings", test_settings)
    monkeypatch.setattr(access, "SessionLocal", lambda: _FakeSession(user))
    monkeypatch.setattr(auth, "auth_service", _FakeAuthService(user_id, profile))

    app = FastAPI()
    app.include_router(auth.router, prefix="/api")
    return TestClient(app), test_settings


class _CommitRecorder:
    def __init__(self) -> None:
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1


class _FakeWorkspaceService:
    def __init__(self) -> None:
        self.session = _CommitRecorder()

    @staticmethod
    def _user(access_context) -> str:
        return str(access_context.principal.user_id)

    def get_or_create(self, access_context):
        return SimpleNamespace(id=uuid.uuid4(), owner_user_id=access_context.principal.user_id)

    def _workspace_payload(self, workspace):
        return {"id": str(workspace.id), "owner_user_id": str(workspace.owner_user_id)}

    def tree(self, access_context):
        return {"root": {"id": None, "name": "My Workspace", "owner_user_id": self._user(access_context)}, "folders_count": 0, "documents_count": 0}

    def summary(self, access_context):
        return {"owner_user_id": self._user(access_context), "storage": {}, "pinned": [], "recent_activity": [], "recent_conversations": []}

    def folder(self, access_context, _folder_id):
        return {"folder": {"id": None, "name": "My Workspace", "owner_user_id": self._user(access_context)}, "folders": [], "files": []}

    def preferences(self, _access_context):
        return WorkspacePreferences.model_validate(
            {
                "version": 1,
                "defaultTab": "files",
                "defaultView": "list",
                "density": "comfortable",
                "rightRailVisible": True,
                "rightRailCollapsed": False,
                "visibleWidgets": ["storage_usage", "pinned_items"],
                "widgetOrder": ["storage_usage", "pinned_items"],
                "defaultSort": "modified_desc",
                "pageSize": 25,
                "recentItemLimit": 5,
            }
        )


def _auth_workspace_test_client(monkeypatch):
    client, test_settings = _auth_test_client(monkeypatch)
    client.app.include_router(workspaces.router, prefix="/api")
    client.app.dependency_overrides[workspaces._service] = lambda: _FakeWorkspaceService()
    return client, test_settings


def test_login_cookie_restores_current_user(monkeypatch) -> None:
    client, test_settings = _auth_test_client(monkeypatch)

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "session.user@cial.in",
            "password": "CorrectHorseBatteryStaple1!",
        },
    )

    assert login_response.status_code == 200
    assert test_settings.auth_cookie_name in login_response.cookies

    me_response = client.get("/api/auth/me")

    assert me_response.status_code == 200
    assert me_response.json()["user"]["email"] == "session.user@cial.in"


def test_login_cookie_authorizes_workspace_me_endpoints(monkeypatch) -> None:
    client, _test_settings = _auth_workspace_test_client(monkeypatch)

    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "session.user@cial.in",
            "password": "CorrectHorseBatteryStaple1!",
        },
    )

    assert login_response.status_code == 200
    for path in (
        "/api/workspaces/me/tree",
        "/api/workspaces/me/summary",
        "/api/workspaces/me/root",
        "/api/workspaces/me/preferences",
    ):
        response = client.get(path)
        assert response.status_code == 200, path


def test_workspace_me_endpoints_require_session(monkeypatch) -> None:
    client, _test_settings = _auth_workspace_test_client(monkeypatch)

    for path in (
        "/api/workspaces/me/tree",
        "/api/workspaces/me/summary",
        "/api/workspaces/me/root",
        "/api/workspaces/me/preferences",
    ):
        response = client.get(path)
        assert response.status_code == 401, path


def test_invalid_login_does_not_issue_session_cookie(monkeypatch) -> None:
    client, test_settings = _auth_test_client(monkeypatch)

    response = client.post(
        "/api/auth/login",
        json={
            "email": "session.user@cial.in",
            "password": "wrong-password",
        },
    )

    assert response.status_code == 401
    assert test_settings.auth_cookie_name not in response.cookies


def test_invalid_session_cookie_rejects_current_user(monkeypatch) -> None:
    client, test_settings = _auth_test_client(monkeypatch)
    client.cookies.set(test_settings.auth_cookie_name, "not-a-valid-session")

    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_logout_clears_matching_session_cookie(monkeypatch) -> None:
    client, test_settings = _auth_test_client(monkeypatch)

    response = client.post("/api/auth/logout")

    assert response.status_code == 200
    set_cookie = response.headers["set-cookie"]
    assert f"{test_settings.auth_cookie_name}=" in set_cookie
    assert "Max-Age=0" in set_cookie
    assert "Path=/" in set_cookie
    assert "SameSite=lax" in set_cookie
