"""Origin, CSRF, response-header, and request-boundary middleware."""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from backend.app.core.config import settings
from backend.app.security.session_tokens import (
    csrf_cookie_settings,
    session_cookie_settings,
    verify_csrf_token,
)


_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_AUTH_BOOTSTRAP_PATHS = frozenset({"/api/auth/login", "/api/auth/signup"})


class HttpSecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method in _UNSAFE_METHODS:
            origin = request.headers.get("origin")
            fetch_site = (request.headers.get("sec-fetch-site") or "").casefold()
            if fetch_site == "cross-site" or (origin and origin.rstrip("/") not in settings.cors_origins):
                return JSONResponse({"detail": "Cross-site request rejected."}, status_code=403)
            session_cookie = request.cookies.get(session_cookie_settings()["key"])
            if session_cookie and request.url.path not in _AUTH_BOOTSTRAP_PATHS:
                csrf_cookie = request.cookies.get(csrf_cookie_settings()["key"])
                csrf_header = request.headers.get("X-CIAL-CSRF-Token")
                if (
                    not csrf_cookie
                    or not csrf_header
                    or csrf_cookie != csrf_header
                    or not verify_csrf_token(csrf_cookie)
                ):
                    return JSONResponse({"detail": "CSRF validation failed."}, status_code=403)

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cache-Control", "no-store")
        return response
