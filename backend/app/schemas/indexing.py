"""Indexing endpoint schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class RebuildIndexRequest(BaseModel):
    force: bool = False


class RebuildIndexResponse(BaseModel):
    status: Literal["started", "completed", "failed"]
    message: str


class IndexStatusResponse(BaseModel):
    status: Literal["idle", "indexing", "completed", "failed"] = "idle"
    documents_seen: int = 0
    documents_indexed: int = 0
    last_run_at: str | None = None
    message: str = ""
