"""Authenticated administrator system-monitor endpoints."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from backend.app.security.access import (
    RequestAccessContext,
    can_monitor_system,
    require_authenticated_access_context,
)


router = APIRouter()


def require_admin_monitor_access(request: Request) -> RequestAccessContext:
    access = require_authenticated_access_context(request)
    if not can_monitor_system(access):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System monitoring permission is required.",
        )
    return access


@router.get("/admin/system/monitor")
def monitor_snapshot(
    request: Request,
    _access: RequestAccessContext = Depends(require_admin_monitor_access),
) -> dict[str, object]:
    return request.app.state.admin_system_monitor_service.snapshot()


@router.get("/admin/system/stream")
async def monitor_stream(
    request: Request,
    _access: RequestAccessContext = Depends(require_admin_monitor_access),
) -> StreamingResponse:
    async def events():
        while True:
            if await request.is_disconnected():
                break
            payload = request.app.state.admin_system_monitor_service.snapshot()
            yield (
                "event: monitor\n"
                f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
            )
            await asyncio.sleep(float(payload.get("connection_hint_seconds") or 2))

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
