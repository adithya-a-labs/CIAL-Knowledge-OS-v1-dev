"""Host and forwarded-header boundary for loopback plus optional LAN gateway."""

from __future__ import annotations

import ipaddress
from pathlib import Path

from starlette.datastructures import Headers
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.app.core.config import settings
from backend.app.lan.status import read_status


FORWARDED_HEADERS = {
    b"forwarded",
    b"x-forwarded-for",
    b"x-forwarded-host",
    b"x-forwarded-port",
    b"x-forwarded-proto",
}


def _without_port(host: str) -> str:
    if host.startswith("["):
        return host.split("]", 1)[0].removeprefix("[")
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def allowed_hosts(status_path: Path | None = None) -> set[str]:
    allowed = {"localhost", "127.0.0.1", "::1", "testserver"}
    if settings.lan_access_enabled:
        allowed.add(settings.lan_domain.casefold())
        status = read_status(status_path or (settings.outputs_path / "lan-server" / "status.json"))
        for key in ("ip_fallback_url", "domain_url"):
            value = status.get(key)
            if not value:
                continue
            try:
                from urllib.parse import urlsplit

                hostname = urlsplit(str(value)).hostname
            except ValueError:
                hostname = None
            if hostname:
                allowed.add(hostname.casefold())
    return allowed


class LanHostBoundaryMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in {"http", "websocket"}:
            await self.app(scope, receive, send)
            return
        client_host = str((scope.get("client") or ("", 0))[0])
        try:
            loopback = ipaddress.ip_address(client_host).is_loopback
        except ValueError:
            loopback = client_host.casefold() in {"localhost", "testclient"}
        if not loopback:
            scope["headers"] = [
                (name, value)
                for name, value in scope.get("headers", [])
                if name.lower() not in FORWARDED_HEADERS
            ]
        host = _without_port(Headers(scope=scope).get("host", "")).casefold()
        if host not in allowed_hosts():
            response = PlainTextResponse("Invalid host header", status_code=400)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
