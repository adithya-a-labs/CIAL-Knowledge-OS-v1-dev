"""Authentication API routes."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from backend.app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutResponse,
    SignupRequest,
)
from backend.app.security.session_tokens import (
    issue_session_token,
    issue_csrf_token,
    csrf_cookie_settings,
    session_cookie_settings,
)
from backend.app.security.access import require_authenticated_access_context, resolve_access_context
from backend.app.security.rate_limit import authentication_rate_limiter
from backend.app.services.auth_service import (
    AuthConflictError,
    AuthInvalidCredentials,
    AuthService,
    AuthServiceError,
    AuthValidationError,
)

router = APIRouter()
auth_service = AuthService()
logger = logging.getLogger(__name__)


def _set_auth_cookie(response: Response, *, user_id: uuid.UUID, session_version: int) -> None:
    response.set_cookie(
        value=issue_session_token(user_id, session_version=session_version),
        **session_cookie_settings(),
    )
    response.set_cookie(value=issue_csrf_token(), **csrf_cookie_settings())


def _enforce_rate_limit(request: Request, *, action: str, account: str) -> None:
    client_ip = request.client.host if request.client is not None else "unknown"
    decision = authentication_rate_limiter.check(
        action=action,
        client_ip=client_ip,
        account=account,
    )
    if not decision.allowed:
        logger.warning("authentication_rate_limited", extra={"action": action})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Try again later.",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )


@router.post("/auth/signup", response_model=AuthResponse)
def signup(payload: SignupRequest, request: Request, response: Response) -> AuthResponse:
    _enforce_rate_limit(request, action="signup", account=payload.email)
    try:
        result = auth_service.signup(
            full_name=payload.full_name,
            email=payload.email,
            password=payload.password,
        )
    except AuthValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except AuthConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AuthServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    _set_auth_cookie(response, user_id=result.user.id, session_version=int(getattr(result.user, "session_version", 0) or 0))
    return AuthResponse(user=result.profile, message="Account created successfully.")


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> AuthResponse:
    _enforce_rate_limit(request, action="login", account=payload.email)
    try:
        result = auth_service.login(email=payload.email, password=payload.password)
    except AuthValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except AuthInvalidCredentials as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except AuthServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    _set_auth_cookie(response, user_id=result.user.id, session_version=int(getattr(result.user, "session_version", 0) or 0))
    return AuthResponse(user=result.profile, message="Logged in successfully.")


@router.get("/auth/me", response_model=AuthResponse)
def me(access_context=Depends(require_authenticated_access_context)) -> AuthResponse:
    user_id = access_context.principal.user_id
    profile = auth_service.get_user_profile(user_id) if user_id is not None else None
    if profile is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return AuthResponse(user=profile, message="Authenticated.")


@router.post("/auth/logout", response_model=LogoutResponse)
def logout(request: Request, response: Response) -> LogoutResponse:
    access = resolve_access_context(request)
    if access.principal.is_authenticated and access.principal.user_id is not None:
        auth_service.revoke_sessions(access.principal.user_id)
    cookie_settings = session_cookie_settings()
    response.delete_cookie(
        key=cookie_settings["key"],
        path=cookie_settings["path"],
        samesite=cookie_settings["samesite"],
        secure=cookie_settings["secure"],
    )
    csrf_settings = csrf_cookie_settings()
    response.delete_cookie(
        key=csrf_settings["key"],
        path=csrf_settings["path"],
        samesite=csrf_settings["samesite"],
        secure=csrf_settings["secure"],
    )
    return LogoutResponse(message="Logged out successfully.")
