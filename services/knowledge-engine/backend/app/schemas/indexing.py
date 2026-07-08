"""Indexing endpoint schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class RebuildIndexRequest(BaseModel):
    force: bool = False


class RebuildIndexResponse(BaseModel):
    status: Literal["starting", "ready", "indexing", "degraded", "failed", "no_documents"]
    message: str


class IndexStatusResponse(BaseModel):
    status: Literal["starting", "ready", "indexing", "degraded", "failed", "no_documents"] = "starting"
    engine_available: bool = False
    engine_ready: bool = False
    documents_seen: int = 0
    documents_indexed: int = 0
    index_fresh: bool = False
    qdrant_ready: bool = False
    models_ready: bool = False
    last_startup_check_at: str | None = None
    last_index_run_at: str | None = None
    message: str = ""
