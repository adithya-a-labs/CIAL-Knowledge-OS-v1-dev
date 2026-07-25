"""Indexing endpoint schemas."""

from __future__ import annotations

from typing import Literal
import uuid

from pydantic import BaseModel, Field, field_validator


class RebuildIndexRequest(BaseModel):
    force: bool = False
    confirm: bool = False
    scope: dict[str, str] | None = None

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is None:
            return None
        allowed = {"asset_type", "document_id", "workspace_id", "repository_id"}
        unsupported = set(value) - allowed
        if unsupported:
            raise ValueError(
                f"Unsupported rebuild scope fields: {', '.join(sorted(unsupported))}."
            )
        if not value or any(not str(item).strip() for item in value.values()):
            raise ValueError("Rebuild scope values must be non-empty.")
        if value.get("asset_type") not in {None, "document", "note", "all"}:
            raise ValueError("asset_type must be document, note, or all.")
        if value.get("asset_type") == "note" and "document_id" in value:
            raise ValueError("document_id cannot be combined with asset_type=note.")
        for key in ("document_id", "workspace_id"):
            if key in value:
                try:
                    uuid.UUID(value[key])
                except ValueError as exc:
                    raise ValueError(f"{key} must be a UUID.") from exc
        return value


class RebuildIndexResponse(BaseModel):
    status: Literal["accepted"]
    job_id: str
    message: str


class IndexStatusResponse(BaseModel):
    status: Literal["starting", "ready", "indexing", "degraded", "failed", "no_documents"] = "starting"
    engine_available: bool = False
    api_ready: bool = False
    retrieval_ready: bool = False
    engine_ready: bool = False
    documents_seen: int = 0
    documents_indexed: int = 0
    index_fresh: bool = False
    qdrant_ready: bool = False
    models_ready: bool = False
    database_ready: bool = False
    indexer_seen: bool = False
    indexer_state: str = "unknown"
    worker_id: str | None = None
    worker_heartbeat_at: str | None = None
    reconciliation_state: str | None = None
    last_reconciliation_at: str | None = None
    queue_counts: dict[str, int] = Field(default_factory=dict)
    queue_by_operation: dict[str, int] = Field(default_factory=dict)
    queue_depth: int = 0
    active_jobs: list[dict[str, object]] = Field(default_factory=list)
    recent_errors: list[dict[str, object]] = Field(default_factory=list)
    latest_index_generation: int = 0
    bm25_generation: int = 0
    generation_published_at: str | None = None
    qdrant_collection: str | None = None
    qdrant_point_count: int = 0
    embedding_device: str | None = None
    embedding_precision: str | None = None
    active_batch_limit: int = 0
    cpu_extraction_workers: int = 0
    internal_queue_depths: dict[str, int] = Field(default_factory=dict)
    throughput: dict[str, int | float] = Field(default_factory=dict)
    reconciliation_metrics: dict[str, object] = Field(default_factory=dict)
    bm25_metrics: dict[str, object] = Field(default_factory=dict)
    gpu_metrics: dict[str, float] = Field(default_factory=dict)
    cpu_metrics: dict[str, float] = Field(default_factory=dict)
    last_successful_index_at: str | None = None
    last_startup_check_at: str | None = None
    last_index_run_at: str | None = None
    message: str = ""
