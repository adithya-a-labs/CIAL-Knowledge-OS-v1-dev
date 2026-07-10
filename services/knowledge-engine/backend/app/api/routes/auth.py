"""Authentication API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request, Response, status

from backend.app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    LogoutResponse,
    SignupRequest,
)
from backend.app.security.session_tokens import (
    issue_session_token,
    session_cookie_settings,
    verify_session_token,
)
from backend.app.services.auth_service import (
    AuthConflictError,
    AuthInvalidCredentials,
    AuthService,
    AuthServiceError,
    AuthValidationError,
)

router = APIRouter()
auth_service = AuthService()


def _set_auth_cookie(response: Response, *, user_id: uuid.UUID) -> None:
    response.set_cookie(
        value=issue_session_token(user_id),
        **session_cookie_settings(),
    )


@router.post("/auth/signup", response_model=AuthResponse)
def signup(payload: SignupRequest, response: Response) -> AuthResponse:
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
    _set_auth_cookie(response, user_id=result.user.id)
    return AuthResponse(user=result.profile, message="Account created successfully.")


@router.post("/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, response: Response) -> AuthResponse:
    try:
        result = auth_service.login(email=payload.email, password=payload.password)
    except AuthValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except AuthInvalidCredentials as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except AuthServiceError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    _set_auth_cookie(response, user_id=result.user.id)
    return AuthResponse(user=result.profile, message="Logged in successfully.")


@router.get("/auth/me", response_model=AuthResponse)
def me(request: Request) -> AuthResponse:
    token = request.cookies.get(session_cookie_settings()["key"])
    user_id = verify_session_token(token) if token else None
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    profile = auth_service.get_user_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return AuthResponse(user=profile, message="Authenticated.")


@router.post("/auth/logout", response_model=LogoutResponse)
def logout(response: Response) -> LogoutResponse:
    response.delete_cookie(
        key=session_cookie_settings()["key"],
        path="/",
        samesite="lax",
        secure=session_cookie_settings()["secure"],
    )
    return LogoutResponse(message="Logged out successfully.")
