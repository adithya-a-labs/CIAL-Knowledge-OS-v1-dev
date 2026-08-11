"""Adapter around the existing deterministic Phase 4.5 knowledge engine."""

from __future__ import annotations

from collections.abc import Mapping
import copy
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
import re
from pathlib import Path
import sys
from threading import Lock, RLock, Thread
import time
from typing import Any, Callable
import uuid

import numpy as np

from backend.app.core.config import settings
from backend.app.core.paths import KNOWLEDGE_ENGINE_SRC, REPO_ROOT
from backend.app.db.session import SessionLocal
from backend.app.models.knowledge import Document, DocumentChunk, DocumentVersion, Folder
from backend.app.models.operations import IndexGeneration
from backend.app.models.workspace_content import Note, NoteIndexState
from backend.app.services.note_indexing_service import note_relative_path
from backend.app.services.gpu_resource_coordinator import (
    GenerationGpuSampler,
    GpuResourceCoordinator,
    inspect_ollama_runtime,
    inspect_gpu_runtime,
    release_ollama_runtime,
)
from backend.app.security.access import (
    RequestAccessContext,
    anonymous_access_context,
    apply_document_access_filter,
    list_accessible_relative_paths,
)
from backend.app.schemas.chat import (
    ChatCitation,
    ChatMetadata,
    ChatRequest,
    ChatResponse,
    ChatSource,
)
from sqlalchemy import false, or_, select

logger = logging.getLogger(__name__)


class KnowledgeEngineUnavailable(RuntimeError):
    """Raised when local engine dependencies or runtime services are missing."""


class KnowledgeEngineInvalidRequest(ValueError):
    """Raised when a chat request asks for an invalid generation profile/scope."""


class KnowledgeEngineDocumentsNotReady(KnowledgeEngineInvalidRequest):
    def __init__(self, documents: list[dict[str, str]]) -> None:
        super().__init__("One or more selected files are still being prepared.")
        self.documents = documents


@dataclass(frozen=True, slots=True)
class ProfileSettings:
    profile: str
    min_answer_words: int
    max_answer_words: int | None
    answer_detail_level: str
    adaptive_answer_sections: bool = True
    include_decision_notes: bool = True


@dataclass(frozen=True, slots=True)
class SelectedContextScope:
    applied: bool
    allowed_relative_paths: frozenset[str]
    selected_document_ids: tuple[str, ...] = ()
    selected_folder_ids: tuple[str, ...] = ()
    selected_note_ids: tuple[str, ...] = ()
    effective_document_ids: tuple[str, ...] = ()
    selected_document_count: int = 0
    selected_folder_count: int = 0
    selected_note_count: int = 0
    effective_document_count: int = 0
    filter_mode: str | None = None


@dataclass(frozen=True, slots=True)
class PublishedQuerySnapshot:
    pipeline: Any
    generation: int
    bm25_generation: int
    collection_name: str


_PROFILE_SETTINGS: dict[str, ProfileSettings] = {
    "quick": ProfileSettings("quick", 120, 250, "concise"),
    "standard": ProfileSettings("standard", 250, 700, "detailed"),
    "detailed": ProfileSettings("detailed", 350, 2000, "detailed"),
    "operational": ProfileSettings("operational", 350, None, "detailed"),
    "elite": ProfileSettings("elite", 350, None, "detailed"),
}
_LEGACY_PROFILE_ALIASES = {
    "short": "quick",
    "medium": "standard",
    "long": "detailed",
}
_MIN_REQUEST_MAX_ANSWER_WORDS = 100
_MAX_REQUEST_MAX_ANSWER_WORDS = 5000
_SELECTED_CONTEXT_RETRIEVAL_FLOOR = 100
_MAX_AUTH_SCOPED_RETRIEVAL_CANDIDATES = 250


def _server_collection_requires_rebuild(config: Any) -> bool:
    """Detect a manifest that points at a different or empty Qdrant backend."""

    if (
        config.qdrant_mode != "server"
        or config.force_rebuild_index
        or not config.incremental_indexing_enabled
    ):
        return False
    try:
        from qdrant_client import QdrantClient
        from cial_knowledge_os.incremental_index import load_manifest
        from cial_knowledge_os.vectorstore import execute_qdrant_operation
    except Exception:  # noqa: BLE001 - the normal pipeline path will report this.
        return False

    previous = load_manifest(
        config.document_manifest_path,
        corpus_root=config.knowledge_root,
        collection_name=config.qdrant_collection_name,
    )
    if not previous:
        return False

    client: Any | None = None
    try:
        client = QdrantClient(
            url=config.qdrant_url,
            api_key=config.qdrant_api_key,
            timeout=max(
                1,
                int(round(getattr(config, "qdrant_timeout_seconds", 30.0))),
            ),
        )
        exists = execute_qdrant_operation(
            config,
            "collection_exists",
            lambda timeout: client.collection_exists(
                config.qdrant_collection_name
            ),
        )
        if not exists:
            return True
        collection = execute_qdrant_operation(
            config,
            "get_collection",
            lambda timeout: client.get_collection(
                config.qdrant_collection_name
            ),
        )
        return int(getattr(collection, "points_count", 0) or 0) == 0
    except Exception:  # noqa: BLE001 - preserve existing pipeline/preflight errors.
        return False
    finally:
        if client is not None:
            client.close()


class KnowledgeEngineService:
    """Lazy wrapper for Phase4RAGPipeline.

    The FastAPI layer owns HTTP concerns only. Existing Phase 4 retrieval,
    reranking, context construction, generation, and citation code remain in
    `services/knowledge-engine`.
    """

    def __init__(self) -> None:
        self._pipeline: Any | None = None
        self._retired_pipelines: list[Any] = []
        self._import_error: Exception | None = None
        self._phase4_config_cls: Any | None = None
        self._phase4_pipeline_cls: Any | None = None
        self._lock = RLock()
        self._index_lock = RLock()
        self._target_update_lock = Lock()
        self._embedding_lock = Lock()
        self._query_lock = Lock()
        self._active_query_readers = 0
        self._pending_publication_activation = False
        self._generation_refresh_lock = Lock()
        self._generation_refresh_inflight = False
        self._chat_metrics_lock = Lock()
        self._chat_debug: dict[str, Any] = {
            "status": "idle",
            "current_index_generation": 0,
            "current_stage": None,
            "current_stage_started_monotonic": None,
            "failed_stage": None,
            "timeout_reason": None,
            "validation_latency": None,
            "retrieval_latency": None,
            "qdrant_latency": None,
            "reranker_latency": None,
            "parallel_retrieval_duration_ms": None,
            "query_embedding_metrics": {},
            "qdrant_metrics": {},
            "retrieval_cache_metrics": {},
            "reranker_metrics": {},
            "generation_latency": None,
            "generation_metrics": {},
            "generation_gpu_start": {},
            "generation_gpu_end": {},
            "last_error": None,
        }
        self._loaded_generation = 0
        self._loaded_bm25_generation = 0
        self._query_embedding_warmed = False
        self._query_embedding_warm_duration_ms: float | None = None
        self._bm25_snapshot_metrics: dict[str, Any] = {
            "bm25_runtime_state": "unavailable",
            "bm25_snapshot_version": None,
            "bm25_loaded_at": None,
            "bm25_load_duration_ms": None,
            "bm25_snapshot_loaded_at": None,
            "bm25_snapshot_size": None,
            "bm25_snapshot_load_duration_ms": None,
            "bm25_index_activation_duration_ms": None,
            "bm25_document_count": 0,
            "bm25_chunk_count": 0,
        }
        self._qdrant_index_metrics: dict[str, Any] = {
            "qdrant_index_status": "unavailable",
            "qdrant_payload_index_fields": [],
            "qdrant_payload_indexes_created": [],
        }
        self._cached_embedding_model: Any | None = None
        self._embedding_runtime_diagnostics: dict[str, Any] = {}
        self._indexer_embedding_target_device: str | None = None
        self._indexer_embedding_gpu_resident = False
        self._gpu_coordinator = GpuResourceCoordinator()
        self._load_engine_symbols()
        from cial_knowledge_os.retrieval_cache import RetrievalResultCache

        self._retrieval_cache = RetrievalResultCache(
            max_entries=settings.retrieval_cache_max_entries
        )

    @property
    def engine_available(self) -> bool:
        return self._phase4_config_cls is not None and self._phase4_pipeline_cls is not None

    def set_pipeline(self, pipeline: Any) -> None:
        with self._lock:
            old_pipeline = self._pipeline
            self._pipeline = pipeline
        if old_pipeline is not None and old_pipeline is not pipeline:
            # Readers may still hold the prior immutable snapshot. Retire it
            # until service shutdown so an atomic swap cannot close a Qdrant
            # client underneath an in-flight chat request.
            self._retired_pipelines.append(old_pipeline)
            # Bound retained clients/snapshots. Shared neural resources are
            # injected into replacement pipelines and are never duplicated here.
            while len(self._retired_pipelines) > 1:
                retired = self._retired_pipelines.pop(0)
                close = getattr(retired, "close", None)
                if callable(close): close()

    @contextmanager
    def acquire_snapshot(self) -> Any:
        """Lease one already-loaded publication without holding its swap lock."""

        with self._query_lock:
            with self._lock:
                pipeline = self._pipeline
                # Preserve the service's injectable pipeline seam used by
                # diagnostics and tests. The production implementation of
                # _ready_pipeline reads the same published pointer and raises.
                if pipeline is None:
                    pipeline = self._ready_pipeline("standard")
                if pipeline is None or not getattr(
                    pipeline, "is_ready_for_answering", False
                ):
                    raise KnowledgeEngineUnavailable("Phase 4.5 engine is not ready.")
                self._active_query_readers += 1
                snapshot = PublishedQuerySnapshot(
                    pipeline=pipeline,
                    generation=self._loaded_generation,
                    bm25_generation=self._loaded_bm25_generation,
                    collection_name=str(
                        getattr(
                            pipeline.config,
                            "qdrant_collection_name",
                            settings.qdrant_collection_name,
                        )
                    ),
                )
        try:
            yield snapshot
        finally:
            refresh_pending = False
            with self._query_lock:
                with self._lock:
                    self._active_query_readers = max(
                        0, self._active_query_readers - 1
                    )
                    refresh_pending = (
                        self._active_query_readers == 0
                        and self._pending_publication_activation
                    )
                    if refresh_pending:
                        self._pending_publication_activation = False
            if refresh_pending:
                self.request_generation_refresh()

    def publication_reader_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "active_query_runtime_reader_count": self._active_query_readers,
                "pending_publication_activation": self._pending_publication_activation,
                "current_loaded_generation": self._loaded_generation,
            }

    def is_ready(self) -> bool:
        with self._lock:
            pipeline = self._pipeline
        return bool(
            pipeline is not None
            and getattr(pipeline, "is_ready_for_answering", False)
        )

    @staticmethod
    def _stable_fingerprint(payload: Mapping[str, Any]) -> str:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def _retrieval_cache_identity(
        cls,
        question: str,
        *,
        generation: int,
        access_context: RequestAccessContext,
        selected_scope: SelectedContextScope,
        effective_relative_paths: frozenset[str] | None,
    ) -> tuple[str, str, str]:
        """Build a key that cannot cross a resolved authorization boundary."""

        principal = access_context.principal
        principal_id = (
            str(principal.user_id)
            if principal.user_id is not None
            else "anonymous"
        )
        permission_boundary = cls._stable_fingerprint(
            {
                "principal_id": principal_id,
                "organization_id": principal.organization_id,
                "department_ids": sorted(map(str, principal.department_ids)),
                "role_ids": sorted(map(str, principal.role_ids)),
                "permission_names": sorted(principal.permission_names),
                "group_ids": sorted(map(str, principal.group_ids)),
                "authenticated": principal.is_authenticated,
            }
        )
        workspace_scope = cls._stable_fingerprint(
            {
                "access_scope": access_context.scope,
                "effective_relative_paths": (
                    sorted(effective_relative_paths)
                    if effective_relative_paths is not None
                    else None
                ),
                "selected_context_applied": selected_scope.applied,
                "selected_document_ids": selected_scope.selected_document_ids,
                "selected_folder_ids": selected_scope.selected_folder_ids,
                "selected_note_ids": selected_scope.selected_note_ids,
            }
        )
        normalized_query = " ".join(question.casefold().split())
        normalized_query_hash = hashlib.sha256(
            normalized_query.encode("utf-8")
        ).hexdigest()
        cache_key = cls._stable_fingerprint(
            {
                "normalized_query_hash": normalized_query_hash,
                "published_generation": int(generation),
                "workspace_scope": workspace_scope,
                "permission_boundary": permission_boundary,
            }
        )
        return cache_key, principal_id, permission_boundary

    @staticmethod
    def _sanitize_generation_telemetry(
        metrics: Mapping[str, Any],
        *,
        generation_duration_ms: float,
        request_duration_ms: float,
    ) -> dict[str, Any]:
        """Keep only finite generation values bounded by measured wall time."""

        sanitized = dict(metrics)
        maximum = min(
            max(0.0, float(generation_duration_ms)),
            max(0.0, float(request_duration_ms)),
        )
        for key in (
            "first_token_ms",
            "model_load_ms",
            "prompt_eval_ms",
            "ollama_total_ms",
        ):
            value = sanitized.get(key)
            if value is None or isinstance(value, bool):
                sanitized[key] = None
                continue
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                sanitized[key] = None
                continue
            sanitized[key] = (
                round(parsed, 3)
                if math.isfinite(parsed) and 0 <= parsed <= maximum
                else None
            )
        rate = sanitized.get("tokens_per_second")
        try:
            parsed_rate = float(rate)
        except (TypeError, ValueError):
            parsed_rate = 0.0
        sanitized["tokens_per_second"] = (
            round(parsed_rate, 3)
            if math.isfinite(parsed_rate) and parsed_rate > 0
            else None
        )
        return sanitized

    def runtime_diagnostics(self) -> dict[str, Any]:
        """Return non-sensitive model/runtime facts for health telemetry."""

        with self._lock:
            pipeline = self._pipeline
        embedding_model = getattr(pipeline, "embedding_model", None) if pipeline is not None else None
        reranker = getattr(pipeline, "reranker", None) if pipeline is not None else None
        reranker_diagnostics = getattr(reranker, "runtime_diagnostics", None)
        reranker_runtime = (
            dict(reranker_diagnostics())
            if callable(reranker_diagnostics)
            else {}
        )
        bm25_retriever = (
            getattr(pipeline, "bm25_retriever", None)
            if pipeline is not None
            else None
        )
        bm25_ready = bool(getattr(bm25_retriever, "is_indexed", False))
        reranker_loaded = bool(
            reranker_runtime.get(
                "reranker_model_loaded",
                reranker is not None,
            )
        )
        reranker_warmed = bool(
            reranker_runtime.get("reranker_warmed", reranker_loaded)
        )
        try:
            embedding_dtype = (
                str(next(embedding_model.parameters()).dtype)
                if embedding_model is not None
                else None
            )
        except (AttributeError, StopIteration, TypeError):
            embedding_dtype = "unknown" if embedding_model is not None else None
        return {
            "embedding_ready": embedding_model is not None,
            "dense_model_status": (
                "ready"
                if embedding_model is not None and self._query_embedding_warmed
                else "loaded"
                if embedding_model is not None
                else "unavailable"
            ),
            "dense_model_warmed": self._query_embedding_warmed,
            "dense_model_warm_duration_ms": (
                self._query_embedding_warm_duration_ms
            ),
            "embedding_device": (
                str(getattr(embedding_model, "device", "unknown"))
                if embedding_model is not None
                else None
            ),
            "reranker_ready": reranker_loaded and reranker_warmed,
            "reranker_status": (
                "ready"
                if reranker_loaded and reranker_warmed
                else "loaded"
                if reranker_loaded
                else "unavailable"
            ),
            "bm25_status": "ready" if bm25_ready else "unavailable",
            **reranker_runtime,
            "loaded_generation": self._loaded_generation,
            "loaded_bm25_generation": self._loaded_bm25_generation,
            **dict(self._bm25_snapshot_metrics),
            "query_embedding_device": (
                str(getattr(embedding_model, "device", "unknown"))
                if embedding_model is not None
                else None
            ),
            "query_embedding_dtype": embedding_dtype,
            "query_embedding_model_state": (
                "warmed"
                if embedding_model is not None and self._query_embedding_warmed
                else "loaded"
                if embedding_model is not None
                else "unavailable"
            ),
            "query_embedding_cache_status": (
                "model_reused" if embedding_model is not None else "unavailable"
            ),
            **dict(self._embedding_runtime_diagnostics),
            **dict(self._qdrant_index_metrics),
            **self._retrieval_cache.diagnostics(),
            "indexer_embedding_gpu_resident": self._indexer_embedding_gpu_resident,
            "ollama_keep_alive": settings.ollama_keep_alive,
            "ollama_num_gpu": settings.ollama_num_gpu,
            "ollama_gpu_priority_enabled": settings.ollama_gpu_priority_enabled,
            "indexer_gpu_cooperative_mode": settings.indexer_gpu_cooperative_mode,
            "ollama_runtime": inspect_ollama_runtime(settings.ollama_model_name),
            "generation_metrics": dict(
                getattr(getattr(pipeline, "llm", None), "last_generation_metrics", {})
                or {}
            ),
        }

    @staticmethod
    def _published_generation_valid(
        generation: IndexGeneration | None,
        collection_name: str,
    ) -> bool:
        """Validate only an atomically published pointer, never job state."""

        return bool(
            generation is not None
            and int(generation.generation or 0) > 0
            and generation.published_at is not None
            and (
                not generation.qdrant_collection
                or generation.qdrant_collection == collection_name
            )
        )

    def prepare_pipeline(
        self,
        *,
        force_rebuild_index: bool,
        response_length: str = "standard",
        on_stage: Callable[[str, dict[str, int]], None] | None = None,
        force_reindex_paths: tuple[str, ...] = (),
    ) -> dict[str, int]:
        """Run the deterministic Phase 4 startup sequence and keep it alive."""

        if not self.engine_available:
            raise KnowledgeEngineUnavailable(self._engine_error_message())

        with self._index_lock:
            return self._prepare_pipeline_locked(
                force_rebuild_index=force_rebuild_index,
                response_length=response_length,
                on_stage=on_stage,
                force_reindex_paths=force_reindex_paths,
            )

    def prepare_query_runtime(self) -> dict[str, Any]:
        """Initialize retrieval without scanning, extracting, embedding, or writing."""

        return self._prepare_live_runtime(create_collection=False, load_reranker=True)

    def prepare_indexer_runtime(self) -> dict[str, Any]:
        """Load the embedding model once and attach the shared server collection."""

        if settings.qdrant_mode.casefold() != "server":
            raise KnowledgeEngineUnavailable(
                "The standalone indexer requires CIAL_QDRANT_MODE=server; "
                "embedded Qdrant cannot be shared safely with the API."
            )
        runtime = self._prepare_live_runtime(create_collection=True, load_reranker=False)
        pipeline = self._pipeline
        if pipeline is None:
            return runtime
        device = str(getattr(pipeline.embedding_model, "device", settings.indexer_device))
        precision = settings.indexer_precision
        if precision == "auto":
            precision = "float16" if device.startswith("cuda") else "float32"
        elif not device.startswith("cuda") and precision in {"float16", "bfloat16"}:
            logger.warning(
                "embedding_precision_cpu_fallback",
                extra={
                    "event": "embedding_precision_fallback",
                    "requested_precision": precision,
                    "actual_precision": "float32",
                    "device": device,
                },
            )
            precision = "float32"
        if precision == "float16":
            half = getattr(pipeline.embedding_model, "half", None)
            if callable(half):
                half()
        elif precision == "bfloat16":
            bfloat16 = getattr(pipeline.embedding_model, "bfloat16", None)
            if callable(bfloat16):
                bfloat16()
            else:
                raise KnowledgeEngineUnavailable(
                    "The configured embedding model does not support bfloat16."
                )
        from cial_knowledge_os.embeddings import embedding_runtime_diagnostics

        embedding_diagnostics = embedding_runtime_diagnostics(
            pipeline.embedding_model,
            configured_device=settings.indexer_device,
        )
        logger.info(
            "embedding_runtime_initialized",
            extra={
                "event": "embedding_runtime_initialized",
                **embedding_diagnostics,
            },
        )
        runtime["embedding_precision"] = precision
        runtime["embedding_runtime"] = embedding_diagnostics
        return runtime

    def _prepare_live_runtime(self, *, create_collection: bool, load_reranker: bool) -> dict[str, Any]:
        if not self.engine_available:
            raise KnowledgeEngineUnavailable(self._engine_error_message())
        from cial_knowledge_os.bm25_snapshot import load_bm25_snapshot
        from cial_knowledge_os.embeddings import (
            embed_texts,
            embedding_runtime_diagnostics,
            get_embedding_dimension,
            load_embedding_model,
            resolve_embedding_device,
        )
        from cial_knowledge_os.vectorstore import (
            create_qdrant_client,
            ensure_collection,
            ensure_query_payload_indexes,
            execute_qdrant_operation,
        )

        config = self.build_config(force_rebuild_index=False)
        configured_embedding_device = (
            settings.indexer_device
            if create_collection
            else settings.query_embedding_device
        )
        resolved_embedding_device = resolve_embedding_device(
            configured_embedding_device
        )
        if create_collection and settings.indexer_gpu_cooperative_mode:
            ollama_loaded = inspect_ollama_runtime(
                settings.ollama_model_name
            ).get("model_loaded")
            if ollama_loaded and not release_ollama_runtime(
                settings.ollama_model_name
            ):
                raise KnowledgeEngineUnavailable(
                    "The indexer could not release the warm Ollama GPU runner. "
                    "Embedding was not allowed to fall back silently to CPU."
                )
        config.embedding_device = resolved_embedding_device
        if create_collection:
            config.qdrant_batch_size = settings.indexer_qdrant_batch_size
        pipeline = self._phase4_pipeline_cls(config)
        client = None
        try:
            if self._cached_embedding_model is None:
                self._cached_embedding_model = load_embedding_model(config)
            pipeline.embedding_model = self._cached_embedding_model
            if not create_collection and not self._query_embedding_warmed:
                dense_warm_started = time.perf_counter()
                embed_texts(
                    pipeline.embedding_model,
                    ["retrieval readiness"],
                    batch_size=1,
                )
                self._query_embedding_warm_duration_ms = round(
                    (time.perf_counter() - dense_warm_started) * 1000,
                    3,
                )
                self._query_embedding_warmed = True
            embedding_diagnostics = embedding_runtime_diagnostics(
                pipeline.embedding_model,
                configured_device=configured_embedding_device,
            )
            self._embedding_runtime_diagnostics = dict(embedding_diagnostics)
            if (
                embedding_diagnostics["embedding_device_actual"]
                != resolved_embedding_device
            ):
                logger.warning(
                    "embedding_device_mismatch",
                    extra={
                        "event": "embedding_device_mismatch",
                        **embedding_diagnostics,
                        "embedding_device_expected": resolved_embedding_device,
                    },
                )
                if create_collection and resolved_embedding_device.startswith("cuda"):
                    raise KnowledgeEngineUnavailable(
                        "The standalone indexer embedding model loaded on "
                        f"'{embedding_diagnostics['embedding_device_actual']}' "
                        f"instead of required device '{resolved_embedding_device}'."
                    )
            client = create_qdrant_client(config)
            collection_exists = bool(
                execute_qdrant_operation(
                    config,
                    "collection_exists",
                    lambda timeout: client.collection_exists(
                        config.qdrant_collection_name
                    ),
                )
            )
            if create_collection:
                ensure_collection(
                    client,
                    config,
                    get_embedding_dimension(pipeline.embedding_model),
                )
                collection_exists = True
            if collection_exists:
                self._qdrant_index_metrics = ensure_query_payload_indexes(
                    client,
                    config,
                )
                pipeline.qdrant_index_status = str(
                    self._qdrant_index_metrics.get(
                        "qdrant_index_status",
                        "unknown",
                    )
                )
            if not collection_exists:
                client.close()
                return {
                    "retrieval_ready": False,
                    "qdrant_ready": True,
                    "collection_exists": False,
                    "message": (
                        "The API is ready, but no retrieval index exists yet. "
                        "Start the standalone indexer to build the first generation."
                    ),
                }
            pipeline.client = client
            client = None
            pipeline._ensure_retrievers()
            generation = None
            if SessionLocal is not None:
                with SessionLocal() as session:
                    generation = session.get(IndexGeneration, "active")
            if not self._published_generation_valid(
                generation, config.qdrant_collection_name
            ):
                if create_collection:
                    # The indexer must be able to create the first publication.
                    # Its embedding/Qdrant runtime is valid without a query
                    # generation; only the API query runtime requires one.
                    pipeline.chunks = []
                    self.set_pipeline(pipeline)
                    actual_device = str(
                        getattr(
                            pipeline.embedding_model,
                            "device",
                            config.embedding_device,
                        )
                    )
                    self._indexer_embedding_target_device = resolved_embedding_device
                    self._indexer_embedding_gpu_resident = (
                        actual_device.startswith("cuda")
                    )
                    return {
                        "retrieval_ready": False,
                        "indexing_ready": True,
                        "qdrant_ready": True,
                        "collection_exists": True,
                        "generation": 0,
                        "bm25_generation": 0,
                        "bm25_chunks": 0,
                        "embedding_device": actual_device,
                        "embedding_runtime": embedding_diagnostics,
                        "message": (
                            "Indexer runtime is ready to create the first "
                            "published generation."
                        ),
                    }
                close = getattr(pipeline, "close", None)
                if callable(close):
                    close()
                return {
                    "retrieval_ready": False,
                    "qdrant_ready": True,
                    "collection_exists": True,
                    "message": (
                        "No valid published index generation is available. "
                        "The indexer must publish a verified generation before chat can start."
                    ),
                }
            snapshot_path = (
                Path(generation.bm25_snapshot_path)
                if generation is not None and generation.bm25_snapshot_path
                else settings.bm25_path / "continuous" / "current.json"
            )
            snapshot_load_started = time.perf_counter()
            snapshot = load_bm25_snapshot(snapshot_path)
            snapshot_load_duration_ms = round(
                (time.perf_counter() - snapshot_load_started) * 1000,
                3,
            )
            chunks = []
            if snapshot is not None:
                from langchain_core.documents import Document as LangchainDocument

                chunks = [
                    LangchainDocument(
                        page_content=str(item.get("text") or ""),
                        metadata=dict(item.get("metadata") or {}),
                    )
                    for item in snapshot.chunks
                ]
            pipeline.chunks = chunks
            published_versions = frozenset(
                str(item.metadata.get("document_version_id") or "").strip()
                for item in chunks
                if str(item.metadata.get("document_version_id") or "").strip()
            )
            pipeline.published_document_version_ids = published_versions
            published_notes = frozenset(
                (
                    str(item.metadata.get("note_id") or "").strip(),
                    int(item.metadata.get("note_revision") or 0),
                )
                for item in chunks
                if str(item.metadata.get("note_id") or "").strip()
                and int(item.metadata.get("note_revision") or 0) > 0
            )
            pipeline.published_note_revisions = published_notes
            bm25_activation_started = time.perf_counter()
            if pipeline.bm25_retriever is not None:
                pipeline.bm25_retriever.index(chunks)
            bm25_index_activation_duration_ms = round(
                (time.perf_counter() - bm25_activation_started) * 1000,
                3,
            )
            if load_reranker:
                self._load_reranker(pipeline)
            self.set_pipeline(pipeline)
            self._loaded_generation = int(generation.generation or 0) if generation is not None else 0
            self._retrieval_cache.activate_generation(self._loaded_generation)
            self._loaded_bm25_generation = (
                int(generation.bm25_generation or 0) if generation is not None else 0
            )
            bm25_loaded_at = datetime.now(timezone.utc).isoformat()
            self._bm25_snapshot_metrics = {
                "bm25_runtime_state": "ready",
                "bm25_snapshot_version": (
                    int(snapshot.generation) if snapshot is not None else None
                ),
                "bm25_loaded_at": bm25_loaded_at,
                "bm25_load_duration_ms": snapshot_load_duration_ms,
                "bm25_snapshot_loaded_at": bm25_loaded_at,
                "bm25_snapshot_size": (
                    snapshot_path.stat().st_size if snapshot_path.exists() else None
                ),
                "bm25_snapshot_load_duration_ms": snapshot_load_duration_ms,
                "bm25_index_activation_duration_ms": bm25_index_activation_duration_ms,
                "bm25_document_count": int(
                    getattr(pipeline.bm25_retriever, "document_count", 0) or 0
                ),
                "bm25_chunk_count": len(chunks),
            }
            actual_device = str(getattr(pipeline.embedding_model, "device", config.embedding_device))
            if create_collection:
                self._indexer_embedding_target_device = resolved_embedding_device
                self._indexer_embedding_gpu_resident = actual_device.startswith("cuda")
            return {
                "retrieval_ready": True,
                "qdrant_ready": True,
                "collection_exists": True,
                "generation": self._loaded_generation,
                "bm25_generation": self._loaded_bm25_generation,
                "bm25_chunks": len(chunks),
                "embedding_device": actual_device,
                "embedding_runtime": embedding_diagnostics,
                "message": "Query runtime loaded from the latest committed index generation.",
            }
        except Exception:
            if client is not None:
                client.close()
            close = getattr(pipeline, "close", None)
            if callable(close):
                close()
            raise

    def refresh_published_query_identities(self) -> bool:
        """Refresh the small Qdrant version allowlist without loading BM25."""

        if SessionLocal is None:
            return False
        try:
            with SessionLocal() as publication_session:
                published_versions = frozenset(
                    str(value)
                    for value in publication_session.scalars(
                        select(Document.current_version_id).where(
                            Document.current_version_id.is_not(None),
                            Document.deleted_at.is_(None),
                            Document.indexed.is_(True),
                            Document.indexing_status == "indexed",
                            Document.lifecycle_status == "indexed",
                        )
                    )
                    if value is not None
                )
                published_notes = frozenset(
                    (str(note_id), int(revision))
                    for note_id, revision in publication_session.execute(
                        select(Note.id, NoteIndexState.indexed_revision)
                        .join(
                            NoteIndexState,
                            NoteIndexState.note_id == Note.id,
                        )
                        .where(
                            Note.deleted_at.is_(None),
                            NoteIndexState.status == "indexed",
                            NoteIndexState.indexed_revision == Note.revision,
                        )
                    )
                    if revision is not None
                )
        except Exception:
            logger.warning("published_identity_refresh_failed", exc_info=True)
            return False
        with self._lock:
            pipeline = self._pipeline
            if pipeline is None:
                return False
            pipeline.published_document_version_ids = published_versions
            pipeline.published_note_revisions = published_notes
        return True

    def refresh_query_runtime_if_needed(self) -> bool:
        """Atomically replace only the BM25 snapshot when a generation advances."""

        # A publication refresh can load and index a very large BM25 snapshot.
        # Never begin that CPU- and memory-heavy work while an immutable query
        # snapshot is leased. The final reader schedules a retry after release.
        with self._lock:
            if self._active_query_readers:
                self._pending_publication_activation = True
                return False
        if SessionLocal is None:
            return False
        if not self._generation_refresh_lock.acquire(blocking=False):
            return False
        from cial_knowledge_os.bm25_snapshot import load_bm25_snapshot
        from cial_knowledge_os.retrievers import BM25Retriever

        try:
            with self._lock:
                pipeline_present = self._pipeline is not None
            try:
                with SessionLocal() as session:
                    generation = session.get(IndexGeneration, "active")
            except Exception:
                logger.warning("index_generation_check_failed", exc_info=True)
                return False
            if (
                not pipeline_present
                and generation is not None
                and int(generation.generation or 0) > 0
            ):
                with self._index_lock:
                    with self._lock:
                        if self._pipeline is not None:
                            return True
                    try:
                        runtime = self.prepare_query_runtime()
                    except Exception:
                        logger.warning("query_runtime_generation_activation_failed", exc_info=True)
                        return False
                    return bool(runtime.get("retrieval_ready"))
            if generation is None or int(generation.bm25_generation or 0) <= self._loaded_bm25_generation:
                return False
            if not self._published_generation_valid(
                generation, settings.qdrant_collection_name
            ):
                logger.warning(
                    "index_generation_invalid",
                    extra={
                        "event": "index_generation_invalid",
                        "generation": int(generation.generation or 0),
                    },
                )
                return False
            if not generation.bm25_snapshot_path:
                return False
            snapshot_path = Path(generation.bm25_snapshot_path)
            try:
                snapshot_size = snapshot_path.stat().st_size
            except OSError:
                snapshot_size = 0
            hot_reload_limit = max(0, int(settings.bm25_hot_reload_max_bytes))
            if pipeline_present and (
                hot_reload_limit == 0 or snapshot_size > hot_reload_limit
            ):
                # Parsing and rebuilding a corpus-scale lexical snapshot inside
                # the API process can transiently duplicate tens of gigabytes
                # and make unrelated HTTP routes unresponsive. Qdrant is
                # already atomically current, so advance its cache generation
                # while retaining the prior immutable lexical snapshot. The
                # next controlled API start loads the new BM25 generation once,
                # before accepting traffic.
                pending_bm25_generation = int(generation.bm25_generation or 0)
                if not self.refresh_published_query_identities():
                    return False
                with self._lock:
                    pipeline = self._pipeline
                    if pipeline is None:
                        return False
                    self._loaded_generation = int(generation.generation or 0)
                    self._retrieval_cache.activate_generation(
                        self._loaded_generation
                    )
                    self._bm25_snapshot_metrics = {
                        **self._bm25_snapshot_metrics,
                        "bm25_runtime_state": "deferred_until_restart",
                        "bm25_snapshot_size": snapshot_size,
                        "bm25_pending_generation": pending_bm25_generation,
                        "bm25_hot_reload_max_bytes": hot_reload_limit,
                    }
                logger.warning(
                    "bm25_hot_reload_deferred",
                    extra={
                        "event": "bm25_hot_reload_deferred",
                        "generation": pending_bm25_generation,
                        "snapshot_size": snapshot_size,
                        "hot_reload_max_bytes": hot_reload_limit,
                    },
                )
                return True
            snapshot_load_started = time.perf_counter()
            snapshot = load_bm25_snapshot(snapshot_path)
            snapshot_load_duration_ms = round(
                (time.perf_counter() - snapshot_load_started) * 1000,
                3,
            )
            if snapshot is None:
                logger.warning("bm25_generation_snapshot_unavailable")
                return False
            from langchain_core.documents import Document as LangchainDocument

            chunks = [
                LangchainDocument(
                    page_content=str(item.get("text") or ""),
                    metadata=dict(item.get("metadata") or {}),
                )
                for item in snapshot.chunks
            ]
            with self._lock:
                pipeline = self._pipeline
            if pipeline is None:
                return False
            lexical = BM25Retriever(
                k1=pipeline.config.bm25_k1,
                b=pipeline.config.bm25_b,
                cache_path=(
                    Path(pipeline.config.bm25_cache_dir)
                    / pipeline.config.bm25_cache_filename
                ),
            )
            bm25_activation_started = time.perf_counter()
            lexical.index(chunks)
            bm25_index_activation_duration_ms = round(
                (time.perf_counter() - bm25_activation_started) * 1000,
                3,
            )
            # Activation is opportunistic. A chat already using the immutable
            # published snapshot always wins this race; refresh retries later.
            if not self._query_lock.acquire(timeout=0.05):
                return False
            try:
                with self._lock:
                    if self._active_query_readers:
                        self._pending_publication_activation = True
                        return False
                lexical.set_allowed_relative_paths(
                    getattr(pipeline.bm25_retriever, "allowed_relative_paths", None)
                )
                pipeline.chunks = chunks
                published_versions = frozenset(
                    str(item.metadata.get("document_version_id") or "").strip()
                    for item in chunks
                    if str(item.metadata.get("document_version_id") or "").strip()
                )
                pipeline.published_document_version_ids = published_versions
                published_notes = frozenset(
                    (
                        str(item.metadata.get("note_id") or "").strip(),
                        int(item.metadata.get("note_revision") or 0),
                    )
                    for item in chunks
                    if str(item.metadata.get("note_id") or "").strip()
                    and int(item.metadata.get("note_revision") or 0) > 0
                )
                pipeline.published_note_revisions = published_notes
                pipeline.bm25_retriever = lexical
                pipeline._retrievers = {}
                pipeline._injected_retrievers = {
                    **getattr(pipeline, "_injected_retrievers", {}),
                    "bm25": lexical,
                }
                pipeline._ensure_retrievers()
                self._loaded_generation = int(generation.generation or 0)
                self._retrieval_cache.activate_generation(
                    self._loaded_generation
                )
                self._loaded_bm25_generation = int(generation.bm25_generation or 0)
                bm25_loaded_at = datetime.now(timezone.utc).isoformat()
                self._bm25_snapshot_metrics = {
                    "bm25_runtime_state": "ready",
                    "bm25_snapshot_version": int(snapshot.generation),
                    "bm25_loaded_at": bm25_loaded_at,
                    "bm25_load_duration_ms": snapshot_load_duration_ms,
                    "bm25_snapshot_loaded_at": bm25_loaded_at,
                    "bm25_snapshot_size": (
                        snapshot_path.stat().st_size
                        if snapshot_path.exists()
                        else None
                    ),
                    "bm25_snapshot_load_duration_ms": snapshot_load_duration_ms,
                    "bm25_index_activation_duration_ms": (
                        bm25_index_activation_duration_ms
                    ),
                    "bm25_document_count": lexical.document_count,
                    "bm25_chunk_count": len(chunks),
                }
            finally:
                self._query_lock.release()
            logger.info(
                "bm25_generation_reloaded",
                extra={
                    "event": "bm25_generation_reloaded",
                    "generation": self._loaded_bm25_generation,
                    "chunk_count": len(chunks),
                    **self._bm25_snapshot_metrics,
                },
            )
            return True
        finally:
            self._generation_refresh_lock.release()

    def request_generation_refresh(self) -> None:
        """Refresh publication metadata asynchronously without delaying chat."""

        with self._chat_metrics_lock:
            if self._generation_refresh_inflight:
                return
            self._generation_refresh_inflight = True

        def refresh() -> None:
            try:
                self.refresh_query_runtime_if_needed()
            finally:
                with self._chat_metrics_lock:
                    self._generation_refresh_inflight = False

        from threading import Thread
        Thread(target=refresh, name="query-generation-refresh", daemon=True).start()

    def chat_debug_snapshot(self) -> dict[str, Any]:
        with self._chat_metrics_lock:
            stage_started = self._chat_debug.get(
                "current_stage_started_monotonic"
            )
            snapshot = dict(self._chat_debug)
            snapshot.pop("current_stage_started_monotonic", None)
            return {
                **snapshot,
                "current_stage_duration_ms": (
                    int((time.monotonic() - float(stage_started)) * 1000)
                    if stage_started is not None
                    else None
                ),
                "current_index_generation": self._loaded_generation,
                "current_bm25_generation": self._loaded_bm25_generation,
                "generation_refresh_running": self._generation_refresh_inflight,
                **dict(self._bm25_snapshot_metrics),
                **dict(self._qdrant_index_metrics),
                **self._retrieval_cache.diagnostics(),
            }

    def _prepare_pipeline_locked(
        self, *, force_rebuild_index: bool, response_length: str,
        on_stage: Callable[[str, dict[str, int]], None] | None,
        force_reindex_paths: tuple[str, ...] = (),
    ) -> dict[str, int]:
        config = self.build_config(response_length=response_length, force_rebuild_index=force_rebuild_index)
        config.force_reindex_paths = tuple(force_reindex_paths)
        if _server_collection_requires_rebuild(config):
            logger.warning(
                "qdrant_manifest_backend_mismatch_rebuild",
                extra={
                    "event": "indexing",
                    "qdrant_url": config.qdrant_url,
                    "collection_name": config.qdrant_collection_name,
                    "manifest_path": str(config.document_manifest_path),
                },
            )
            config.force_rebuild_index = True
        with self._lock:
            active = self._pipeline
        shared = {}
        if active is not None:
            for name in ("embedding_model", "llm", "reranker"):
                value = getattr(active, name, None)
                if value is not None: shared[name] = value
        pipeline = self._phase4_pipeline_cls(config, **shared)
        try:
            self._emit_stage(on_stage, "load", pipeline)
            pipeline.load()
            self._emit_stage(on_stage, "loaded", pipeline)
            self._emit_stage(on_stage, "chunk", pipeline)
            pipeline.chunk()
            self._emit_stage(on_stage, "chunked", pipeline)
            self._emit_stage(on_stage, "embed", pipeline)
            pipeline.embed()
            self._emit_stage(on_stage, "embedded", pipeline)
            self._emit_stage(on_stage, "index", pipeline)
            pipeline.index()
            self._emit_stage(on_stage, "indexed", pipeline)
            self._emit_stage(on_stage, "reranker", pipeline)
            self._load_reranker(pipeline)
            self._emit_stage(on_stage, "ready", pipeline)
        except Exception:
            close = getattr(pipeline, "close", None)
            if callable(close):
                close()
            raise
        self.set_pipeline(pipeline)
        return self._pipeline_counts(pipeline)

    def prepare_document_version(
        self,
        document_id: uuid.UUID,
        document_version_id: uuid.UUID,
        *,
        on_stage: Callable[[str, dict[str, int]], None] | None = None,
    ) -> dict[str, int]:
        """Index one managed current version using the active models and client."""
        with self._target_update_lock:
            pipeline = self._ready_pipeline("standard")
            if SessionLocal is None:
                raise KnowledgeEngineUnavailable("Targeted indexing requires the metadata database.")
            with SessionLocal() as session:
                document = session.get(Document, document_id)
                version = session.get(DocumentVersion, document_version_id)
                if document is None or version is None or version.document_id != document.id or document.current_version_id != version.id:
                    raise ValueError("The current document version is unavailable for indexing.")
                trusted_metadata = self._trusted_chunk_metadata(document, version)
                root = settings.workspace_root_path.resolve() if document.storage_scope == "personal" else settings.corpus_root_path.resolve()
                storage_key = str(version.storage_key or document.relative_path or "")
                candidate = root / storage_key
                if candidate.is_symlink(): raise ValueError("The managed artifact cannot be accessed safely.")
                try: artifact = candidate.resolve(strict=True)
                except (OSError, RuntimeError): raise ValueError("The managed artifact is unavailable.") from None
                if root not in artifact.parents or not artifact.is_file():
                    raise ValueError("The managed artifact cannot be accessed safely.")

            from cial_knowledge_os.chunking import chunk_documents
            from cial_knowledge_os.embeddings import embed_texts
            from cial_knowledge_os.fusion import ReciprocalRankFusion
            from cial_knowledge_os.incremental_index import update_manifest_entry
            from cial_knowledge_os.loaders import load_pdf_paths
            from cial_knowledge_os.retrievers import BM25Retriever, DenseRetriever, HybridRetriever
            from cial_knowledge_os.vectorstore import replace_document_chunks

            self._emit_stage(on_stage, "load", pipeline)
            documents = load_pdf_paths([artifact], corpus_root=root, config=pipeline.config)
            if not documents:
                raise ValueError("The managed artifact did not produce indexable content.")
            for item in documents: item.metadata.update(trusted_metadata)
            self._emit_stage(on_stage, "loaded", pipeline)
            self._emit_stage(on_stage, "chunk", pipeline)
            chunks = chunk_documents(documents, pipeline.config)
            if not chunks: raise ValueError("The managed artifact did not produce indexable chunks.")
            self._emit_stage(on_stage, "chunked", pipeline)
            self._emit_stage(on_stage, "embed", pipeline)
            with self._embedding_lock:
                embeddings = embed_texts(
                    pipeline.embedding_model, [chunk.page_content for chunk in chunks],
                    batch_size=pipeline.config.embedding_batch_size,
                )
            self._emit_stage(on_stage, "embedded", pipeline)

            # Build the replacement lexical snapshot before touching shared state.
            current_chunks = [
                chunk for chunk in list(pipeline.chunks or [])
                if str(chunk.metadata.get("document_id")) != str(document_id)
            ]
            updated_chunks = [*current_chunks, *chunks]
            lexical = BM25Retriever(
                k1=pipeline.config.bm25_k1, b=pipeline.config.bm25_b,
                cache_path=Path(pipeline.config.bm25_cache_dir) / pipeline.config.bm25_cache_filename,
            )
            lexical.index(updated_chunks)
            old_lexical = getattr(pipeline, "bm25_retriever", None)
            lexical.set_allowed_relative_paths(getattr(old_lexical, "allowed_relative_paths", None))

            self._emit_stage(on_stage, "index", pipeline)
            removed = replace_document_chunks(
                pipeline.client, chunks, embeddings, pipeline.config,
                document_id=str(document_id),
                document_version_id=str(document_version_id),
                execution_manager=pipeline.execution_manager,
            )
            update_manifest_entry(
                manifest_path=pipeline.config.document_manifest_path,
                corpus_root=pipeline.config.knowledge_root, managed_root=root, source_path=artifact,
                collection_name=pipeline.config.qdrant_collection_name, chunk_count=len(chunks),
                repository_id=getattr(pipeline.config, "repository_id", None),
            )

            with self._lock:
                if self._pipeline is not pipeline:
                    raise RuntimeError("The live retrieval snapshot changed during targeted indexing.")
                pipeline.chunks = updated_chunks
                pipeline.documents = documents
                pipeline.embeddings = embeddings
                pipeline.bm25_retriever = lexical
                pipeline._ensure_retrievers()
                dense = pipeline._retrievers.get("dense") or DenseRetriever(pipeline._dense_search)
                pipeline._retrievers = {**pipeline._retrievers, "dense": dense, "bm25": lexical}
                pipeline.hybrid_retriever = HybridRetriever(
                    [dense, lexical],
                    fuser=ReciprocalRankFusion(rank_constant=pipeline.config.rrf_k,
                        weights={"dense": pipeline.config.dense_weight, "bm25": pipeline.config.bm25_weight}),
                    candidate_limits={"dense": pipeline.config.dense_top_k, "bm25": pipeline.config.bm25_top_k},
                    parallel=pipeline.config.parallel_retrieval,
                )
            self._emit_stage(on_stage, "indexed", pipeline)
            self._emit_stage(on_stage, "ready", pipeline)
            logger.info("document_version_index_refreshed", extra={"event": "document_version_index_refreshed",
                "document_id": str(document_id), "version_id": str(document_version_id),
                "chunks_indexed": len(chunks), "stale_points_removed": removed})
            return {"documents_seen": 1, "documents_indexed": 1, "chunks_indexed": len(chunks)}

    def extract_document_version(
        self,
        document_id: uuid.UUID,
        document_version_id: uuid.UUID,
    ) -> list[Any]:
        """CPU-only extraction/chunking for one immutable managed version."""

        pipeline = self._ready_pipeline("standard")
        if SessionLocal is None:
            raise KnowledgeEngineUnavailable("Targeted extraction requires PostgreSQL.")
        with SessionLocal() as session:
            document = session.get(Document, document_id)
            version = session.get(DocumentVersion, document_version_id)
            if (
                document is None
                or version is None
                or version.document_id != document.id
                or document.current_version_id != version.id
            ):
                raise ValueError("The current document version is unavailable for extraction.")
            trusted_metadata = self._trusted_chunk_metadata(document, version)
            root = (
                settings.workspace_root_path.resolve()
                if document.storage_scope == "personal"
                else settings.corpus_root_path.resolve()
            )
            storage_key = str(version.storage_key or document.relative_path or "")
        candidate = root / storage_key
        if candidate.is_symlink():
            raise ValueError("The managed artifact cannot be accessed safely.")
        try:
            artifact = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            raise ValueError("The managed artifact is unavailable.") from None
        if root not in artifact.parents or not artifact.is_file():
            raise ValueError("The managed artifact cannot be accessed safely.")

        from cial_knowledge_os.chunking import chunk_documents
        from cial_knowledge_os.loaders import load_pdf_paths

        documents = load_pdf_paths([artifact], corpus_root=root, config=pipeline.config)
        if not documents:
            raise ValueError("The managed artifact did not produce indexable content.")
        for item in documents:
            item.metadata.update(trusted_metadata)
        chunks = chunk_documents(documents, pipeline.config)
        if not chunks:
            raise ValueError("The managed artifact did not produce indexable chunks.")
        return chunks

    def embed_chunk_batch(self, chunks: list[Any], *, batch_size: int) -> Any:
        """GPU-only batch operation; the model was loaded once at process start."""

        pipeline = self._ready_pipeline("standard")
        from cial_knowledge_os.embeddings import embed_texts
        import torch

        with self._embedding_lock:
            self.ensure_indexer_embedding_device()
            actual_device = str(getattr(pipeline.embedding_model, "device", "unknown"))
            target = self._indexer_embedding_target_device or settings.indexer_device
            if str(target).startswith("cuda") and not actual_device.startswith("cuda"):
                raise RuntimeError(
                    "CUDA is available and configured for standalone indexing, "
                    f"but BGE-M3 is on '{actual_device}' instead of '{target}'."
                )
            device_index = (
                int(actual_device.rsplit(":", 1)[1])
                if actual_device.startswith("cuda") and ":" in actual_device
                else torch.cuda.current_device()
                if actual_device.startswith("cuda") and torch.cuda.is_available()
                else None
            )
            memory_before = (
                int(torch.cuda.memory_allocated(device_index))
                if device_index is not None
                else 0
            )
            started = time.perf_counter()
            logger.info(
                "embedding_batch_started",
                extra={
                    "event": "embedding_batch_started",
                    "batch_size": min(batch_size, len(chunks)),
                    "device": actual_device,
                    "gpu_memory_before": memory_before,
                },
            )
            vectors = embed_texts(
                pipeline.embedding_model,
                [chunk.page_content for chunk in chunks],
                batch_size=batch_size,
            )
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            memory_after = (
                int(torch.cuda.memory_allocated(device_index))
                if device_index is not None
                else 0
            )
            self._last_embedding_batch_metrics = {
                "embedding_batch_started": True,
                "batch_size": min(batch_size, len(chunks)),
                "device": actual_device,
                "gpu_memory_before": memory_before,
                "gpu_memory_after": memory_after,
                "duration_ms": duration_ms,
            }
            logger.info(
                "embedding_batch_completed",
                extra={
                    "event": "embedding_batch_completed",
                    **self._last_embedding_batch_metrics,
                },
            )
            return vectors

    def ensure_indexer_embedding_device(self) -> bool:
        """Move the indexer model back to its configured accelerator on demand."""

        pipeline = self._ready_pipeline("standard")
        target = self._indexer_embedding_target_device or settings.indexer_device
        actual_before = str(getattr(pipeline.embedding_model, "device", "unknown"))
        self._indexer_embedding_gpu_resident = actual_before.startswith("cuda")
        if not str(target).startswith("cuda") or self._indexer_embedding_gpu_resident:
            return False
        if settings.indexer_gpu_cooperative_mode:
            ollama_loaded = inspect_ollama_runtime(
                settings.ollama_model_name
            ).get("model_loaded")
            if ollama_loaded and not release_ollama_runtime(
                settings.ollama_model_name
            ):
                return False
        mover = getattr(pipeline.embedding_model, "to", None)
        if not callable(mover):
            return False
        mover(target)
        if settings.indexer_precision == "float16":
            half = getattr(pipeline.embedding_model, "half", None)
            if callable(half):
                half()
        elif settings.indexer_precision == "bfloat16":
            bfloat16 = getattr(pipeline.embedding_model, "bfloat16", None)
            if callable(bfloat16):
                bfloat16()
        actual_after = str(getattr(pipeline.embedding_model, "device", "unknown"))
        self._indexer_embedding_gpu_resident = actual_after.startswith("cuda")
        if not self._indexer_embedding_gpu_resident:
            logger.error(
                "embedding_device_mismatch",
                extra={
                    "event": "embedding_device_mismatch",
                    "embedding_device_configured": settings.indexer_device,
                    "embedding_device_expected": target,
                    "embedding_device_actual": actual_after,
                },
            )
            raise RuntimeError(
                f"BGE-M3 remained on '{actual_after}' after requesting '{target}'."
            )
        return True

    def release_indexer_gpu(self) -> bool:
        """Release indexer CUDA residency while retaining the loaded CPU model."""

        if not self._indexer_embedding_gpu_resident:
            return False
        pipeline = self._ready_pipeline("standard")
        mover = getattr(pipeline.embedding_model, "to", None)
        if not callable(mover):
            return False
        with self._embedding_lock:
            mover("cpu")
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except (ImportError, RuntimeError):
                pass
            self._indexer_embedding_gpu_resident = False
        return True

    @staticmethod
    def chunk_hash(text_value: str) -> str:
        return hashlib.sha256(text_value.encode("utf-8")).hexdigest()

    def _chunk_reuse_contract(self) -> tuple[str, str]:
        pipeline = self._ready_pipeline("standard")
        chunking_version = (
            "recursive-character-v1:"
            f"{int(pipeline.config.chunk_size)}:"
            f"{int(pipeline.config.chunk_overlap)}"
        )
        return settings.embedding_model_name, chunking_version

    def reusable_document_chunk_embeddings(
        self,
        document_id: uuid.UUID,
        chunks: list[Any],
    ) -> dict[int, np.ndarray]:
        """Load unchanged chunk vectors from the last indexed document version."""

        if SessionLocal is None or not chunks:
            return {}
        pipeline = self._ready_pipeline("standard")
        embedding_version, chunking_version = self._chunk_reuse_contract()
        hashes = [self.chunk_hash(chunk.page_content) for chunk in chunks]
        with SessionLocal() as session:
            rows = list(
                session.scalars(
                    select(DocumentChunk)
                    .where(
                        DocumentChunk.document_id == document_id,
                        DocumentChunk.chunk_hash.in_(set(hashes)),
                        DocumentChunk.embedding_model_version == embedding_version,
                        DocumentChunk.chunking_version == chunking_version,
                        DocumentChunk.qdrant_point_id.is_not(None),
                    )
                    .order_by(DocumentChunk.created_at.desc())
                )
            )
        point_by_hash: dict[str, str] = {}
        for row in rows:
            if row.chunk_hash and row.qdrant_point_id:
                point_by_hash.setdefault(row.chunk_hash, row.qdrant_point_id)
        requested = list(dict.fromkeys(point_by_hash.values()))
        if not requested:
            return {}

        from cial_knowledge_os.vectorstore import execute_qdrant_operation

        vectors_by_point: dict[str, np.ndarray] = {}
        batch_size = max(1, settings.indexer_qdrant_batch_size)
        for offset in range(0, len(requested), batch_size):
            point_ids = requested[offset : offset + batch_size]
            records = execute_qdrant_operation(
                pipeline.config,
                "retrieve",
                lambda timeout, ids=point_ids: pipeline.client.retrieve(
                    collection_name=pipeline.config.qdrant_collection_name,
                    ids=ids,
                    with_payload=False,
                    with_vectors=True,
                    timeout=timeout,
                ),
                affected_count=len(point_ids),
            )
            for record in records:
                value = record.vector
                if isinstance(value, dict):
                    value = next(iter(value.values()), None)
                if value is not None:
                    vectors_by_point[str(record.id)] = np.asarray(value, dtype=np.float32)

        reusable: dict[int, np.ndarray] = {}
        for index, chunk_hash in enumerate(hashes):
            point_id = point_by_hash.get(chunk_hash)
            vector = vectors_by_point.get(str(point_id)) if point_id else None
            if vector is not None:
                reusable[index] = vector
        return reusable

    def write_document_version(
        self,
        document_id: uuid.UUID,
        document_version_id: uuid.UUID,
        chunks: list[Any],
        embeddings: Any,
    ) -> dict[str, int]:
        """Write, verify, then remove stale versions and commit chunk metadata."""

        pipeline = self._ready_pipeline("standard")
        embedding_version, chunking_version = self._chunk_reuse_contract()
        from cial_knowledge_os.vectorstore import (
            _stable_point_id,
            delete_document_version,
            delete_stale_document_versions,
            replace_document_chunks,
        )

        if SessionLocal is None:
            raise KnowledgeEngineUnavailable("Targeted indexing requires PostgreSQL.")
        with SessionLocal() as session:
            document = session.get(Document, document_id)
            version = session.get(DocumentVersion, document_version_id)
            if (
                document is None
                or version is None
                or document.current_version_id != version.id
                or document.deleted_at is not None
                or document.lifecycle_status == "deleted"
            ):
                raise ValueError("The indexing version is no longer current.")
        replaced = replace_document_chunks(
            pipeline.client,
            chunks,
            embeddings,
            pipeline.config,
            document_id=str(document_id),
            document_version_id=str(document_version_id),
            execution_manager=pipeline.execution_manager,
        )
        with SessionLocal() as session, session.begin():
            document = session.scalar(
                select(Document).where(Document.id == document_id).with_for_update()
            )
            version = session.get(DocumentVersion, document_version_id)
            if (
                document is None
                or version is None
                or document.current_version_id != version.id
                or document.deleted_at is not None
                or document.lifecycle_status == "deleted"
            ):
                delete_document_version(
                    pipeline.client,
                    pipeline.config,
                    document_id=str(document_id),
                    document_version_id=str(document_version_id),
                )
                raise ValueError("The indexed version is no longer current.")
            stale = delete_stale_document_versions(
                pipeline.client,
                pipeline.config,
                document_id=str(document_id),
                keep_document_version_id=str(document_version_id),
            )
            session.query(DocumentChunk).filter(
                DocumentChunk.document_id == document_id
            ).delete(synchronize_session=False)
            for index, chunk in enumerate(chunks):
                item = dict(chunk.metadata)
                session.add(
                    DocumentChunk(
                        document_id=document_id,
                        document_version_id=document_version_id,
                        chunk_id=str(item.get("chunk_id") or f"{document_id}:{index}"),
                        chunk_hash=self.chunk_hash(chunk.page_content),
                        embedding_model_version=embedding_version,
                        chunking_version=chunking_version,
                        chunk_index=index,
                        qdrant_point_id=_stable_point_id(chunk),
                        page=item.get("page_number"),
                        section=item.get("section"),
                        text=chunk.page_content,
                        text_preview=chunk.page_content[:500],
                        token_count=item.get("token_count"),
                        metadata_=item,
                    )
                )
            document.indexed = True
            document.indexing_status = "indexed"
            document.lifecycle_status = "indexed"
            from datetime import datetime, timezone

            document.indexed_at = datetime.now(timezone.utc)
            version.status = "indexed"
        return {
            "chunks_indexed": len(chunks),
            "same_version_points_replaced": replaced,
            "stale_points_removed": stale,
        }

    def delete_document_asset(self, document_id: uuid.UUID) -> int:
        pipeline = self._ready_pipeline("standard")
        from cial_knowledge_os.vectorstore import delete_document_chunks

        removed = delete_document_chunks(
            pipeline.client,
            pipeline.config,
            document_id=str(document_id),
        )
        if SessionLocal is not None:
            with SessionLocal() as session, session.begin():
                session.query(DocumentChunk).filter(
                    DocumentChunk.document_id == document_id
                ).delete(synchronize_session=False)
        return removed

    def refresh_document_metadata(self, document_id: uuid.UUID) -> int:
        """Refresh authoritative access/path payloads without embeddings or scroll."""

        pipeline = self._ready_pipeline("standard")
        if SessionLocal is None:
            raise KnowledgeEngineUnavailable("Metadata refresh requires PostgreSQL.")
        from cial_knowledge_os.vectorstore import execute_qdrant_operation

        updated = 0
        with SessionLocal() as session, session.begin():
            document = session.get(Document, document_id)
            if document is None or document.current_version_id is None:
                raise ValueError("The document metadata target is unavailable.")
            version = session.get(DocumentVersion, document.current_version_id)
            if version is None:
                raise ValueError("The document version metadata is unavailable.")
            trusted = self._trusted_chunk_metadata(document, version)
            rows = list(
                session.scalars(
                    select(DocumentChunk).where(DocumentChunk.document_id == document_id)
                )
            )
            for row in rows:
                metadata = {**(row.metadata_ or {}), **trusted}
                point_id = row.qdrant_point_id
                if not point_id:
                    continue
                execute_qdrant_operation(
                    pipeline.config,
                    "set_payload",
                    lambda timeout, pid=point_id, payload=metadata: pipeline.client.set_payload(
                        collection_name=pipeline.config.qdrant_collection_name,
                        payload={"metadata": payload},
                        points=[pid],
                        wait=True,
                        timeout=timeout,
                    ),
                    affected_count=1,
                )
                row.metadata_ = metadata
                updated += 1
        return updated

    @staticmethod
    def _trusted_chunk_metadata(document: Document, version: DocumentVersion) -> dict[str, Any]:
        from backend.app.services.chunk_metadata_contract import build_chunk_metadata
        return build_chunk_metadata(document, version, lifecycle_status="indexed")

    def close(self) -> None:
        with self._lock:
            pipeline = self._pipeline
            self._pipeline = None
        if pipeline is not None:
            close = getattr(pipeline, "close", None)
            if callable(close):
                close()
        for retired in self._retired_pipelines:
            close = getattr(retired, "close", None)
            if callable(close): close()
        self._retired_pipelines.clear()
        self._cached_embedding_model = None
        self._query_embedding_warmed = False
        self._query_embedding_warm_duration_ms = None
        self._retrieval_cache.clear()

    def answer_question(
        self,
        request: ChatRequest,
        *,
        access_context: RequestAccessContext | None = None,
        progress_callback: Any | None = None,
        token_callback: Any | None = None,
        cancel_event: Any | None = None,
        request_id: str | None = None,
        resource_gate: Callable[[str], Any] | None = None,
    ) -> ChatResponse:
        chat_request_id = request_id or str(uuid.uuid4())
        conversation_id = str(request.session_id) if request.session_id else None
        request_started = time.perf_counter()
        stage_started: dict[str, float] = {}
        stage_metrics: dict[str, Any] = {}
        snapshot_context: Any | None = None
        published_snapshot: PublishedQuerySnapshot | None = None

        def progress(stage_id: str, status: str, **metrics: Any) -> None:
            now = time.perf_counter()
            if status == "started":
                stage_started[stage_id] = now
            duration_ms = (
                int((now - stage_started.get(stage_id, now)) * 1000)
                if status != "started"
                else 0
            )
            error_state = metrics.get("error_state")
            if error_state is None and status == "failed":
                error_state = metrics.get("error_type") or "failed"
            candidate_count = metrics.get("candidate_count")
            if candidate_count is None:
                candidate_count = next(
                    (
                        metrics[key]
                        for key in (
                            "candidates",
                            "selected_evidence",
                            "result_count",
                        )
                        if key in metrics
                    ),
                    0,
                )
            timeout_state = (
                "timed_out"
                if "timeout" in str(error_state or "").casefold()
                else "not_timed_out"
            )
            if (
                stage_id == "generation"
                and status in {"completed", "failed"}
                and stage_id in stage_started
            ):
                # The API stage boundary is authoritative. Do not trust a
                # lower layer's duration if it used another clock or unit.
                metrics["duration_ms"] = duration_ms
                metrics = self._sanitize_generation_telemetry(
                    metrics,
                    generation_duration_ms=duration_ms,
                    request_duration_ms=(now - request_started) * 1000,
                )
            metrics = {
                **metrics,
                "request_id": chat_request_id,
                "conversation_id": conversation_id,
                "stage": stage_id,
                "status": status,
                "duration_ms": metrics.get("duration_ms", duration_ms),
                "candidate_count": candidate_count,
                "error_state": error_state,
                "timeout_state": timeout_state,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            if status in {"completed", "failed"}:
                previous = stage_metrics.get(stage_id, {})
                stage_metrics[stage_id] = {
                    **metrics,
                    "duration_ms": int(previous.get("duration_ms", 0))
                    + int(metrics.get("duration_ms", 0)),
                }
            event_stage = {
                "retrieval.searching": "retrieval",
                "evidence.selecting": "evidence_selection",
                "bm25_retrieval": "bm25",
            }.get(stage_id, stage_id.replace(".", "_"))
            logger.info(
                event_stage + "_" + status,
                extra={
                    "event": event_stage + "_" + status,
                    **metrics,
                },
            )
            with self._chat_metrics_lock:
                if status == "started":
                    self._chat_debug.update(
                        current_stage=stage_id,
                        current_stage_started_monotonic=time.monotonic(),
                    )
                if status in {"completed", "failed"}:
                    latency_key = {
                        "request.validating": "validation_latency",
                        "retrieval.searching": "retrieval_latency",
                        "dense_retrieval": "qdrant_latency",
                        "bm25_retrieval": "bm25_latency",
                        "hybrid_fusion": "hybrid_fusion_latency",
                        "parallel_retrieval": "parallel_retrieval_duration_ms",
                        "reranking": "reranker_latency",
                        "generation": "generation_latency",
                    }.get(stage_id)
                    if latency_key is not None:
                        self._chat_debug[latency_key] = metrics["duration_ms"]
                    if stage_id == "bm25_retrieval":
                        self._chat_debug["bm25_search_duration_ms"] = metrics.get(
                            "bm25_search_duration_ms",
                            metrics["duration_ms"],
                        )
                        self._chat_debug["bm25_candidate_count"] = metrics.get(
                            "bm25_candidate_count",
                            metrics.get("candidate_count", 0),
                        )
                    if stage_id == "parallel_retrieval":
                        self._chat_debug["parallel_retrieval_duration_ms"] = (
                            metrics.get(
                                "parallel_retrieval_duration_ms",
                                metrics["duration_ms"],
                            )
                        )
                        for key in (
                            "dense_started",
                            "dense_completed",
                            "bm25_started",
                            "bm25_completed",
                        ):
                            self._chat_debug[key] = metrics.get(key)
                    if stage_id == "query_embedding":
                        self._chat_debug["query_embedding_metrics"] = dict(
                            metrics
                        )
                    if stage_id == "qdrant_search":
                        self._chat_debug["qdrant_metrics"] = dict(metrics)
                    if stage_id == "retrieval_cache":
                        self._chat_debug["retrieval_cache_metrics"] = dict(
                            metrics
                        )
                    if stage_id == "reranking":
                        self._chat_debug["reranker_metrics"] = {
                            key: metrics.get(key)
                            for key in (
                                "reranker_device",
                                "reranker_dtype",
                                "reranker_model_loaded",
                                "reranker_warmed",
                                "reranker_warm_duration_ms",
                                "reranker_gpu_memory",
                                "reranker_batch_size",
                                "reranker_candidate_count",
                                "reranker_latency_ms",
                            )
                            if metrics.get(key) is not None
                        }
                    if stage_id == "generation":
                        allowed_generation_metrics = {
                            key: metrics.get(key)
                            for key in (
                                "prompt_tokens",
                                "context_tokens",
                                "system_prompt_tokens",
                                "output_tokens",
                                "first_token_ms",
                                "tokens_per_second",
                                "model_load_ms",
                                "prompt_eval_ms",
                                "ollama_total_ms",
                                "keep_alive",
                                "retry_count",
                                "ollama_processor_type",
                                "gpu_layers_used",
                                "gpu_layers_requested",
                                "gpu_memory_used",
                                "gpu_memory_total",
                                "cpu_offload_detected",
                                "generation_gpu_utilization",
                                "generation_gpu_utilization_peak",
                                "generation_gpu_memory_peak",
                                "generation_gpu_samples",
                            )
                            if metrics.get(key) is not None
                            or key in {"gpu_layers_used", "cpu_offload_detected"}
                        }
                        self._chat_debug["generation_metrics"] = (
                            allowed_generation_metrics
                        )
                if error_state:
                    if (
                        stage_id != "chat"
                        or not self._chat_debug.get("failed_stage")
                    ):
                        self._chat_debug.update(
                            failed_stage=stage_id,
                            timeout_reason=(
                                str(error_state)
                                if timeout_state == "timed_out"
                                else None
                            ),
                        )
            if progress_callback is not None:
                progress_callback(stage_id, status, metrics)

        logger.info(
            "chat_request_started",
            extra={"event": "chat_request_started", "request_id": chat_request_id},
        )
        logger.info(
            "request_received",
            extra={"event": "request_received", "request_id": chat_request_id},
        )
        with self._chat_metrics_lock:
            self._chat_debug.update(
                status="running",
                request_id=chat_request_id,
                current_stage=None,
                current_stage_started_monotonic=None,
                failed_stage=None,
                timeout_reason=None,
                validation_latency=None,
                retrieval_latency=None,
                qdrant_latency=None,
                bm25_latency=None,
                bm25_search_duration_ms=None,
                bm25_candidate_count=None,
                hybrid_fusion_latency=None,
                parallel_retrieval_duration_ms=None,
                query_embedding_metrics={},
                qdrant_metrics={},
                retrieval_cache_metrics={},
                dense_started=None,
                dense_completed=None,
                bm25_started=None,
                bm25_completed=None,
                reranker_latency=None,
                reranker_metrics={},
                generation_latency=None,
                generation_metrics={},
                generation_gpu_start={},
                generation_gpu_end={},
                total_latency=None,
                last_error=None,
            )
        progress("request.validating", "started")
        try:
            if not self.engine_available:
                raise KnowledgeEngineUnavailable(self._engine_error_message())

            # This bounded metadata refresh makes newly committed Qdrant points
            # visible immediately. It never parses or rebuilds the BM25 corpus.
            self.refresh_published_query_identities()
            # Publication discovery is deliberately detached from this request.
            # The request uses the already-loaded stable snapshot while a daemon
            # refresh checks whether a newer complete generation is available.
            snapshot_context = self.acquire_snapshot()
            published_snapshot = snapshot_context.__enter__()
            # Lease the current immutable generation before scheduling
            # discovery. This closes the race where the refresh thread could
            # start rebuilding a corpus-scale BM25 index ahead of this query.
            self.request_generation_refresh()
            access_context = access_context or anonymous_access_context()
            profile = self._resolve_profile(request.response_length, request.profile)
            selected_scope = self._resolve_selected_context(
                request,
                access_context=access_context,
            )
            progress("request.validating", "completed")
            progress("context.building", "started")
            access_relative_paths = self._accessible_relative_paths(access_context)
            effective_relative_paths = self._effective_relative_paths(
                access_relative_paths,
                selected_scope,
            )
            requested_scope_paths = self._requested_scope_relative_paths(
                access_context,
                request.search_scope,
            )
            if requested_scope_paths is not None:
                effective_relative_paths = frozenset(
                    effective_relative_paths.intersection(requested_scope_paths)
                )
            progress("context.building", "completed", documents_searched=len(effective_relative_paths or ()))
            (
                retrieval_cache_key,
                retrieval_cache_principal,
                retrieval_permission_boundary,
            ) = self._retrieval_cache_identity(
                request.question,
                generation=published_snapshot.generation,
                access_context=access_context,
                selected_scope=selected_scope,
                effective_relative_paths=effective_relative_paths,
            )
            self._retrieval_cache.observe_permission_boundary(
                retrieval_cache_principal,
                retrieval_permission_boundary,
            )
        except Exception as exc:
            if snapshot_context is not None:
                snapshot_context.__exit__(type(exc), exc, exc.__traceback__)
                snapshot_context = None
            logger.info(
                "chat_failed",
                extra={
                    "event": "chat_failed",
                    "request_id": chat_request_id,
                    "error_type": type(exc).__name__,
                },
            )
            with self._chat_metrics_lock:
                self._chat_debug.update(
                    status="failed",
                    last_error=type(exc).__name__,
                    current_stage_started_monotonic=None,
                    completed_at=time.time(),
                )
            raise
        logger.info(
            "permission_validation_completed",
            extra={
                "event": "permission_validation_completed",
                "request_id": chat_request_id,
                "duration_ms": stage_metrics["context.building"]["duration_ms"],
            },
        )
        progress(
            "index_generation.loaded",
            "completed",
            generation=published_snapshot.generation,
            bm25_generation=published_snapshot.bm25_generation,
        )
        logger.info(
            "index_generation_loaded",
            extra={
                "event": "index_generation_loaded",
                "request_id": chat_request_id,
                "generation": published_snapshot.generation,
                "bm25_generation": published_snapshot.bm25_generation,
            },
        )
        started_at = time.perf_counter()
        pipeline = None
        priority_context = None
        generation_gpu_sampler: GenerationGpuSampler | None = None
        try:
            priority_context = self._gpu_coordinator.chat_priority(chat_request_id)
            priority_context.__enter__()
            pipeline = self._request_pipeline(
                published_snapshot.pipeline,
                request.response_length,
                profile=request.profile,
                max_answer_words=request.max_answer_words,
                resource_gate=resource_gate,
            )
            pipeline.token_callback = token_callback
            pipeline.cancel_event = cancel_event
            pipeline.retrieval_cache_getter = lambda: self._retrieval_cache.lookup(
                retrieval_cache_key
            )
            pipeline.retrieval_cache_setter = lambda payload: self._retrieval_cache.store(
                retrieval_cache_key,
                payload,
                generation=published_snapshot.generation,
                principal_id=retrieval_cache_principal,
                permission_boundary=retrieval_permission_boundary,
            )

            def pipeline_telemetry(
                stage_name: str, status: str, metrics: dict[str, Any]
            ) -> None:
                if stage_name == "generation" and status in {
                    "started",
                    "completed",
                    "failed",
                }:
                    nonlocal generation_gpu_sampler
                    gpu_key = (
                        "generation_gpu_start"
                        if status == "started"
                        else "generation_gpu_end"
                    )
                    if status == "started":
                        generation_gpu_sampler = GenerationGpuSampler(
                            settings.ollama_model_name
                        )
                        generation_gpu_sampler.start()
                        sample = inspect_gpu_runtime()
                    elif generation_gpu_sampler is not None:
                        sample = generation_gpu_sampler.stop()
                        generation_gpu_sampler = None
                        metrics.update(sample)
                    else:
                        sample = inspect_gpu_runtime()
                    with self._chat_metrics_lock:
                        self._chat_debug[gpu_key] = sample
                progress(stage_name, status, **metrics)

            pipeline.telemetry_callback = pipeline_telemetry
            progress("retrieval.searching", "started", documents_searched=len(effective_relative_paths or ()))
            if selected_scope.applied or access_relative_paths is not None:
                response = self._run_with_relative_path_filter(
                    pipeline,
                    request.question,
                    effective_relative_paths,
                    response_key=(
                        "selected_context_filter"
                        if selected_scope.applied
                        else "access_scope_filter"
                    ),
                    filter_payload=(
                        {
                            "applied": True,
                            "mode": selected_scope.filter_mode,
                            "selected_document_ids": list(selected_scope.selected_document_ids),
                            "selected_folder_ids": list(selected_scope.selected_folder_ids),
                            "selected_note_ids": list(selected_scope.selected_note_ids),
                            "effective_document_ids": list(selected_scope.effective_document_ids),
                            "effective_scope": {
                                "document_count": len(effective_relative_paths),
                                "relative_paths": sorted(effective_relative_paths),
                            },
                            "access_scope": access_context.scope,
                        }
                        if selected_scope.applied
                        else {
                            "applied": True,
                            "mode": f"access_scope:{access_context.scope}",
                            "scope": access_context.scope,
                            "effective_scope": {
                                "document_count": len(effective_relative_paths),
                                "relative_paths": sorted(effective_relative_paths),
                            },
                        }
                    ),
                )
            else:
                response = self._answer_loaded_pipeline(
                    pipeline, request.question
                )
            retrieved = response.get("retrieved") if isinstance(response, Mapping) else None
            selected = response.get("selected_evidence") if isinstance(response, Mapping) else None
            progress("retrieval.searching", "completed", candidates=len(retrieved) if isinstance(retrieved, list) else 0)
            progress("evidence.selecting", "completed", selected_evidence=len(selected) if isinstance(selected, list) else 0)
        except Exception as exc:  # noqa: BLE001 - convert local runtime failures to API errors.
            progress("chat", "failed", error_type=type(exc).__name__)
            logger.exception(
                "chat_failed",
                extra={"event": "chat_failed", "request_id": chat_request_id},
            )
            with self._chat_metrics_lock:
                self._chat_debug.update(
                    status="failed",
                    last_error=type(exc).__name__,
                    current_stage_started_monotonic=None,
                    completed_at=time.time(),
                )
            if isinstance(exc, TimeoutError):
                raise KnowledgeEngineUnavailable(
                    "The assistant timed out while searching or generating. Please retry."
                ) from exc
            raise KnowledgeEngineUnavailable(
                "The assistant could not complete the retrieval pipeline."
            ) from exc
        finally:
            if generation_gpu_sampler is not None:
                generation_gpu_sampler.stop()
            if pipeline is not None:
                pipeline.token_callback = None
                pipeline.cancel_event = None
                pipeline.telemetry_callback = None
                pipeline.retrieval_cache_getter = None
                pipeline.retrieval_cache_setter = None
            if priority_context is not None:
                priority_context.__exit__(None, None, None)
            if snapshot_context is not None:
                snapshot_context.__exit__(None, None, None)
                snapshot_context = None

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        progress("citations.linking", "started")
        result = self._to_chat_response(
            response,
            config=pipeline.config,
            profile=profile.profile,
            selected_scope=selected_scope,
            include_debug=request.include_debug,
            include_sources=request.include_sources,
            latency_ms=latency_ms,
            access_context=access_context,
            allowed_relative_paths=effective_relative_paths if effective_relative_paths else None,
        )
        progress("citations.linking", "completed", citations=len(result.citations))
        total_ms = int((time.perf_counter() - request_started) * 1000)
        progress("chat", "completed", duration_ms=total_ms)
        debug_update = {
            "status": "completed",
            "request_id": chat_request_id,
            "current_index_generation": published_snapshot.generation,
            "current_stage": "complete",
            "current_stage_started_monotonic": None,
            "validation_latency": stage_metrics.get("request.validating", {}).get("duration_ms"),
            "retrieval_latency": stage_metrics.get("retrieval.searching", {}).get("duration_ms"),
            "qdrant_latency": stage_metrics.get("dense_retrieval", {}).get("duration_ms"),
            "bm25_latency": stage_metrics.get("bm25_retrieval", {}).get("duration_ms"),
            "hybrid_fusion_latency": stage_metrics.get("hybrid_fusion", {}).get("duration_ms"),
            "reranker_latency": stage_metrics.get("reranking", {}).get("duration_ms"),
            "generation_latency": stage_metrics.get("generation", {}).get("duration_ms"),
            "total_latency": total_ms,
            "last_error": None,
            "completed_at": time.time(),
        }
        with self._chat_metrics_lock:
            self._chat_debug.update(debug_update)
        return result

    def rebuild_index(self, *, force: bool) -> tuple[bool, str, int, int]:
        if not self.engine_available:
            return False, self._engine_error_message(), 0, 0
        try:
            counts = self.prepare_pipeline(force_rebuild_index=force)
        except Exception as exc:  # noqa: BLE001
            logger.exception("knowledge_engine_index_failed")
            return False, str(exc), 0, 0
        return True, "Index rebuild completed.", counts["documents_seen"], counts["documents_indexed"]

    def _load_engine_symbols(self) -> None:
        if str(KNOWLEDGE_ENGINE_SRC) not in sys.path:
            sys.path.insert(0, str(KNOWLEDGE_ENGINE_SRC))
        try:
            from cial_knowledge_os.config import Phase4Config
            from cial_knowledge_os.phase4_pipeline import Phase4RAGPipeline
        except Exception as exc:  # noqa: BLE001
            self._import_error = exc
            self._phase4_config_cls = None
            self._phase4_pipeline_cls = None
            return
        self._phase4_config_cls = Phase4Config
        self._phase4_pipeline_cls = Phase4RAGPipeline
        self._import_error = None

    def _ready_pipeline(
        self,
        response_length: str,
        *,
        profile: str | None = None,
        max_answer_words: int | None = None,
    ) -> Any:
        with self._lock:
            pipeline = self._pipeline
        if pipeline is None or not getattr(pipeline, "is_ready_for_answering", False):
            raise KnowledgeEngineUnavailable("Phase 4.5 engine is not ready.")
        self._apply_response_profile(
            pipeline.config,
            response_length,
            profile=profile,
            max_answer_words=max_answer_words,
        )
        return pipeline

    def _request_pipeline(
        self,
        base_pipeline: Any,
        response_length: str,
        *,
        profile: str | None,
        max_answer_words: int | None,
        resource_gate: Callable[[str], Any] | None = None,
    ) -> Any:
        """Create a lightweight request-local query view over shared models."""

        config = copy.deepcopy(base_pipeline.config)
        self._apply_response_profile(
            config,
            response_length,
            profile=profile,
            max_answer_words=max_answer_words,
        )
        if not isinstance(base_pipeline, self._phase4_pipeline_cls):
            pipeline = copy.copy(base_pipeline)
            pipeline.config = config
            pipeline.resource_gate = resource_gate
            return pipeline
        lexical = getattr(base_pipeline, "bm25_retriever", None)
        request_lexical = None
        if lexical is not None:
            request_lexical = copy.copy(lexical)
            request_lexical.allowed_relative_paths = None
            request_lexical.last_search_metrics = {}
            # Authorized index maps are immutable after publication; the small
            # LRU and active scope are request-local.
            request_lexical._authorized_lock = RLock()
            request_lexical._authorized_indexes = copy.copy(
                getattr(lexical, "_authorized_indexes", {})
            )
        injected_retrievers = (
            {"bm25": request_lexical} if request_lexical is not None else None
        )
        pipeline = self._phase4_pipeline_cls(
            config,
            embedding_model=base_pipeline.embedding_model,
            llm=base_pipeline.llm,
            query_transformer=base_pipeline.query_transformer,
            tokenizer=getattr(base_pipeline, "_provided_tokenizer", None),
            retrievers=injected_retrievers,
            reranker=base_pipeline.reranker,
        )
        pipeline.client = base_pipeline.client
        pipeline.documents = base_pipeline.documents
        pipeline.chunks = base_pipeline.chunks
        pipeline.embeddings = base_pipeline.embeddings
        pipeline.published_document_version_ids = getattr(
            base_pipeline, "published_document_version_ids", None
        )
        pipeline.published_note_revisions = getattr(
            base_pipeline, "published_note_revisions", None
        )
        pipeline.query_embedding_model_state = getattr(
            base_pipeline, "query_embedding_model_state", "loaded"
        )
        pipeline.query_embedding_cache_status = getattr(
            base_pipeline, "query_embedding_cache_status", "model_reused"
        )
        pipeline.qdrant_index_status = getattr(
            base_pipeline, "qdrant_index_status", "unknown"
        )
        pipeline.resource_gate = resource_gate
        return pipeline

    def _get_pipeline(
        self,
        response_length: str,
        *,
        profile: str | None = None,
        max_answer_words: int | None = None,
    ) -> Any:
        if self._pipeline is None:
            config = self.build_config(
                response_length=response_length,
                profile=profile,
                max_answer_words=max_answer_words,
            )
            self._pipeline = self._phase4_pipeline_cls(config)
        else:
            self._apply_response_profile(
                self._pipeline.config,
                response_length,
                profile=profile,
                max_answer_words=max_answer_words,
            )
        return self._pipeline

    def build_config(
        self,
        *,
        response_length: str = "standard",
        profile: str | None = None,
        max_answer_words: int | None = None,
        force_rebuild_index: bool | None = None,
    ) -> Any:
        config = self._phase4_config_cls(
            project_root=REPO_ROOT,
            data_dir=settings.data_root_path,
            knowledge_root=settings.corpus_root_path,
            additional_knowledge_roots=(settings.workspace_root_path,),
            # The live collection is shared by enterprise and personal managed
            # repositories. Per-document repository ids are hydrated from the DB.
            repository_id=None,
            document_manifest_path=settings.indexes_path / "document_manifest.json",
            bm25_cache_dir=settings.bm25_path / "cial_phase4",
            output_root=settings.outputs_path / "batch_answers",
            observability_output_dir=settings.outputs_path / "runs",
            qdrant_collection_name=settings.qdrant_collection_name,
            qdrant_mode=settings.qdrant_mode,
            qdrant_url=settings.qdrant_url,
            qdrant_api_key=settings.qdrant_api_key,
            qdrant_batch_size=settings.qdrant_batch_size,
            qdrant_upsert_wait=settings.qdrant_upsert_wait,
            qdrant_timeout_seconds=settings.qdrant_timeout_seconds,
            qdrant_retry_attempts=settings.qdrant_retry_attempts,
            qdrant_retry_backoff_seconds=settings.qdrant_retry_backoff_seconds,
            qdrant_health_timeout_seconds=settings.qdrant_health_timeout_seconds,
            qdrant_query_timeout_seconds=settings.qdrant_query_timeout_seconds,
            qdrant_query_retry_attempts=settings.qdrant_query_retry_attempts,
            qdrant_upsert_timeout_seconds=settings.qdrant_upsert_timeout_seconds,
            qdrant_delete_timeout_seconds=settings.qdrant_delete_timeout_seconds,
            qdrant_collection_timeout_seconds=settings.qdrant_collection_timeout_seconds,
            ollama_model_name=settings.ollama_model_name,
            ollama_keep_alive=settings.ollama_keep_alive,
            ollama_num_gpu=settings.ollama_num_gpu,
            embedding_model_name=settings.embedding_model_name,
            embedding_batch_size=settings.indexer_embed_batch_size,
            reranker_model_name=settings.reranker_model_name,
            reranker_device=settings.reranker_device,
            reranker_batch_size=settings.reranker_batch_size,
            reranker_local_files_only=settings.reranker_local_files_only,
            reranker_timeout_seconds=settings.reranker_timeout_seconds,
            evidence_selection_timeout_seconds=(
                settings.evidence_selection_timeout_seconds
            ),
            force_rebuild_index=(
                settings.force_rebuild_on_startup
                if force_rebuild_index is None
                else force_rebuild_index
            ),
            require_authorization_metadata=True,
            max_answer_words=settings.max_answer_words,
            generation_retries=settings.generation_retries,
            retry_cooldown_seconds=settings.retry_cooldown_seconds,
            generation_timeout_seconds=settings.generation_timeout_seconds,
            observability_console=False,
        )
        self._apply_response_profile(
            config,
            response_length,
            profile=profile,
            max_answer_words=max_answer_words,
        )
        return config

    @staticmethod
    def _resolve_profile(
        response_length: str = "standard",
        profile: str | None = None,
    ) -> ProfileSettings:
        requested = (profile or response_length or "standard").strip().casefold()
        canonical = _LEGACY_PROFILE_ALIASES.get(requested, requested)
        try:
            return _PROFILE_SETTINGS[canonical]
        except KeyError as exc:
            allowed = ", ".join(
                [*sorted(_PROFILE_SETTINGS), *sorted(_LEGACY_PROFILE_ALIASES)]
            )
            raise KnowledgeEngineInvalidRequest(
                f"Unsupported response profile '{requested}'. Allowed values: {allowed}."
            ) from exc

    @staticmethod
    def _validate_max_answer_words(value: int | None) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            raise KnowledgeEngineInvalidRequest("max_answer_words must be an integer.")
        if not _MIN_REQUEST_MAX_ANSWER_WORDS <= value <= _MAX_REQUEST_MAX_ANSWER_WORDS:
            raise KnowledgeEngineInvalidRequest(
                "max_answer_words must be between "
                f"{_MIN_REQUEST_MAX_ANSWER_WORDS} and {_MAX_REQUEST_MAX_ANSWER_WORDS}."
            )
        return value

    @classmethod
    def _apply_response_profile(
        cls,
        config: Any,
        response_length: str,
        *,
        profile: str | None = None,
        max_answer_words: int | None = None,
    ) -> ProfileSettings:
        resolved = cls._resolve_profile(response_length, profile)
        override_max = cls._validate_max_answer_words(max_answer_words)
        config.min_answer_words = resolved.min_answer_words
        config.max_answer_words = (
            override_max
            if override_max is not None
            else resolved.max_answer_words
        )
        config.answer_detail_level = resolved.answer_detail_level
        config.prefer_structured_answers = True
        config.adaptive_answer_sections = resolved.adaptive_answer_sections
        config.include_decision_notes = resolved.include_decision_notes
        return resolved

    def _resolve_selected_context(
        self,
        request: ChatRequest,
        *,
        access_context: RequestAccessContext,
    ) -> SelectedContextScope:
        document_ids = [value for value in request.selected_document_ids if value.strip()]
        folder_ids = [value for value in request.selected_folder_ids if value.strip()]
        note_ids = [value for value in request.selected_note_ids if value.strip()]
        if request.search_scope == "current_upload" and not document_ids:
            raise KnowledgeEngineInvalidRequest("Current Upload requires at least one uploaded document.")
        if not document_ids and not folder_ids and not note_ids:
            return SelectedContextScope(
                applied=False,
                allowed_relative_paths=frozenset(),
            )
        if SessionLocal is None:
            raise KnowledgeEngineInvalidRequest(
                "Selected context requires the metadata database, but DATABASE_URL is not configured."
            )

        relative_paths: set[str] = set()
        effective_document_ids: set[str] = set()
        not_ready: list[dict[str, str]] = []
        with SessionLocal() as session:
            for value in document_ids:
                document = self._document_for_context_id(
                    session,
                    value,
                    access_context=access_context,
                )
                if document is None:
                    raise KnowledgeEngineInvalidRequest(
                        f"Selected document was not found: {value}"
                    )
                if not (document.indexed and document.indexing_status == "indexed" and document.lifecycle_status == "indexed"):
                    not_ready.append({"document_id": str(document.id), "name": document.name,
                                      "indexing_status": str(document.indexing_status or "pending")})
                    continue
                relative_paths.add(self._normalize_relative_path(document.relative_path))
                effective_document_ids.add(str(document.id))

            for value in folder_ids:
                folder = self._folder_for_context_id(session, value, access_context)
                if folder is None:
                    raise KnowledgeEngineInvalidRequest(
                        f"Selected folder was not found: {value}"
                    )
                folder_path = self._normalize_relative_path(folder.relative_path)
                if str(folder.repository_id or "").startswith("personal:"):
                    statement = select(Document).where(
                        Document.folder_id == folder.id,
                        Document.indexing_status == "indexed", Document.indexed.is_(True),
                        Document.lifecycle_status == "indexed",
                    )
                elif folder_path:
                    statement = select(Document).where(
                        Document.relative_path.like(f"{folder_path}/%"),
                        Document.indexing_status == "indexed", Document.indexed.is_(True),
                        Document.lifecycle_status == "indexed",
                    )
                else:
                    statement = select(Document).where(Document.indexing_status == "indexed", Document.indexed.is_(True), Document.lifecycle_status == "indexed")
                statement = apply_document_access_filter(statement, access_context)
                for document in session.scalars(statement):
                    relative_paths.add(
                        self._normalize_relative_path(document.relative_path)
                    )
                    effective_document_ids.add(str(document.id))
            for value in note_ids:
                try: note_uuid=uuid.UUID(value)
                except ValueError as exc: raise KnowledgeEngineInvalidRequest("Selected note was not found.") from exc
                note=session.scalar(select(Note).where(Note.id==note_uuid,Note.owner_user_id==access_context.principal.user_id,Note.deleted_at.is_(None),Note.is_archived.is_(False)))
                state=session.get(NoteIndexState,note_uuid)
                if note is None: raise KnowledgeEngineInvalidRequest("Selected note was not found.")
                if state is None or state.status!="indexed" or state.indexed_revision!=note.revision:
                    not_ready.append({"document_id":str(note.id),"name":note.title,"indexing_status":state.status if state else "pending"});continue
                relative_paths.add(note_relative_path(note.id))

        if not_ready:
            raise KnowledgeEngineDocumentsNotReady(not_ready)

        if not relative_paths:
            raise KnowledgeEngineInvalidRequest(
                "Selected context did not resolve to any active sources."
            )
        return SelectedContextScope(
            applied=True,
            allowed_relative_paths=frozenset(relative_paths),
            selected_document_ids=tuple(document_ids),
            selected_folder_ids=tuple(folder_ids),
            selected_note_ids=tuple(note_ids),
            effective_document_ids=tuple(sorted(effective_document_ids)),
            selected_document_count=len(document_ids),
            selected_folder_count=len(folder_ids),
            selected_note_count=len(note_ids),
            effective_document_count=len(relative_paths),
            filter_mode="hard_relative_path_filter",
        )

    @staticmethod
    def _document_for_context_id(
        session: Any,
        value: str,
        *,
        access_context: RequestAccessContext,
    ) -> Document | None:
        try:
            document_id = uuid.UUID(value)
            return session.scalar(
                apply_document_access_filter(
                    select(Document).where(Document.id == document_id),
                    access_context,
                )
            )
        except ValueError:
            return session.scalar(
                apply_document_access_filter(
                    select(Document).where(Document.relative_path == value),
                    access_context,
                )
            )

    @staticmethod
    def _folder_for_context_id(session: Any, value: str, access_context: RequestAccessContext) -> Folder | None:
        try:
            folder = session.get(Folder, uuid.UUID(value))
        except ValueError:
            folder = session.scalar(
                select(Folder).where(
                    Folder.repository_id == settings.corpus_repository_id,
                    Folder.relative_path == value,
                )
            )
        if folder is None:
            return None
        visible_document = session.scalar(
            apply_document_access_filter(
                select(Document.id).where(Document.folder_id == folder.id),
                access_context,
            ).limit(1)
        )
        return folder if visible_document is not None else None

    @staticmethod
    def _normalize_relative_path(value: Any) -> str:
        return str(value or "").replace("\\", "/").strip("/")

    @classmethod
    def _result_matches_selected_context(
        cls,
        result: Mapping[str, Any],
        allowed_relative_paths: frozenset[str],
    ) -> bool:
        metadata = result.get("metadata")
        metadata = metadata if isinstance(metadata, Mapping) else {}
        candidates = {
            cls._normalize_relative_path(metadata.get("relative_path")),
            cls._normalize_relative_path(result.get("relative_path")),
            cls._normalize_relative_path(metadata.get("source")),
            cls._normalize_relative_path(result.get("source_path")),
            cls._normalize_relative_path(result.get("source")),
            cls._normalize_relative_path(metadata.get("absolute_path")),
        }
        candidates.discard("")
        return bool(candidates.intersection(allowed_relative_paths))

    def _run_with_selected_context(
        self,
        pipeline: Any,
        question: str,
        selected_scope: SelectedContextScope,
    ) -> Mapping[str, Any]:
        if not selected_scope.applied:
            return self._answer_loaded_pipeline(pipeline, question)
        return self._run_with_relative_path_filter(
            pipeline,
            question,
            selected_scope.allowed_relative_paths,
            response_key="selected_context_filter",
            filter_payload={
                "applied": True,
                "mode": selected_scope.filter_mode,
                "selected_document_ids": list(selected_scope.selected_document_ids),
                "selected_folder_ids": list(selected_scope.selected_folder_ids),
                "selected_note_ids": list(selected_scope.selected_note_ids),
                "effective_document_ids": list(selected_scope.effective_document_ids),
                "effective_scope": {
                    "document_count": selected_scope.effective_document_count,
                    "relative_paths": sorted(selected_scope.allowed_relative_paths),
                },
            },
        )

    def _run_with_relative_path_filter(
        self,
        pipeline: Any,
        question: str,
        allowed_relative_paths: frozenset[str],
        *,
        response_key: str,
        filter_payload: dict[str, Any],
    ) -> Mapping[str, Any]:
        if not allowed_relative_paths:
            answer = (
                "No relevant evidence found in the selected context."
                if response_key == "selected_context_filter"
                else "No accessible information found for the current access scope."
            )
            return {
                "question": question,
                "retrieved": [],
                "context": "",
                "raw_answer": answer,
                "answer": answer,
                "citations": [],
                "sources": [],
                "selected_evidence": [],
                "context_stages": {"retrieved": [], "compressed": []},
                "weak_evidence": True,
                "answer_status": "insufficient_evidence",
                response_key: {
                    **filter_payload,
                    "candidate_floor": 0,
                    "query_count": 0,
                    "before_filter_counts": [],
                    "after_filter_counts": [],
                    "before_filter_count": 0,
                    "after_filter_count": 0,
                    "filtered_count": 0,
                    "final_retrieved_document_ids": [],
                    "final_retrieved_relative_paths": [],
                },
            }
        original_search = pipeline._search
        config = pipeline.config
        saved_values = {
            "retrieval_top_k": getattr(config, "retrieval_top_k", None),
            "dense_top_k": getattr(config, "dense_top_k", None),
            "bm25_top_k": getattr(config, "bm25_top_k", None),
            "reranker_candidate_top_k": getattr(config, "reranker_candidate_top_k", None),
        }
        candidate_floor = min(
            _MAX_AUTH_SCOPED_RETRIEVAL_CANDIDATES,
            max(
                _SELECTED_CONTEXT_RETRIEVAL_FLOOR,
                max(len(allowed_relative_paths), 1) * 12,
            ),
        )
        search_stats: dict[str, Any] = {
            "query_count": 0,
            "raw_counts": [],
            "filtered_counts": [],
        }

        def selected_search(query: str) -> list[dict[str, Any]]:
            raw_results = original_search(query)
            filtered_results = [
                dict(result)
                for result in raw_results
                if self._result_matches_selected_context(
                    result,
                    allowed_relative_paths,
                )
            ]
            search_stats["query_count"] = int(search_stats["query_count"]) + 1
            search_stats["raw_counts"].append(len(raw_results))
            search_stats["filtered_counts"].append(len(filtered_results))
            return filtered_results

        try:
            for name, value in saved_values.items():
                if value is not None:
                    setattr(config, name, max(int(value), candidate_floor))
            on_config_changed = getattr(pipeline, "on_config_changed", None)
            if callable(on_config_changed):
                on_config_changed()
            set_retrieval_relative_paths = getattr(
                pipeline,
                "set_retrieval_relative_paths",
                None,
            )
            if callable(set_retrieval_relative_paths):
                set_retrieval_relative_paths(allowed_relative_paths)
            else:
                pipeline._search = selected_search
            response = dict(
                self._answer_loaded_pipeline(pipeline, question)
            )
            raw_total = sum(int(count) for count in search_stats["raw_counts"])
            filtered_total = sum(int(count) for count in search_stats["filtered_counts"])
            selected_evidence = response.get("selected_evidence")
            selected_evidence_count = len(selected_evidence) if isinstance(selected_evidence, list) else 0
            retrieved_chunks = response.get("retrieved")
            retrieved_count = len(retrieved_chunks) if isinstance(retrieved_chunks, list) else 0
            context_stages = response.get("context_stages")
            compressed_chunks = (
                list(context_stages.get("compressed") or [])
                if isinstance(context_stages, Mapping)
                else []
            )
            answer_status = str(response.get("answer_status") or "").strip()
            citations = response.get("citations")
            citation_count = len(citations) if isinstance(citations, list) else 0
            has_matching_evidence = any(
                (
                    filtered_total > 0,
                    selected_evidence_count > 0,
                    retrieved_count > 0,
                    len(compressed_chunks) > 0,
                )
            )
            selected_context_no_relevant_evidence = (
                response_key == "selected_context_filter"
                and answer_status == "insufficient_evidence"
                and citation_count == 0
            )
            if not has_matching_evidence or selected_context_no_relevant_evidence:
                response["answer"] = (
                    "No relevant evidence found in the selected context."
                    if response_key == "selected_context_filter"
                    else "No accessible information found for the current access scope."
                )
                response["raw_answer"] = response["answer"]
                response["answer_status"] = "insufficient_evidence"
                response["citations"] = []
                response["sources"] = []
                response["retrieved"] = []
                response["selected_evidence"] = []
                response["context_stages"] = {"retrieved": [], "compressed": []}
                response["weak_evidence"] = True
            response_filter_payload = {
                "candidate_floor": candidate_floor,
                "query_count": search_stats["query_count"],
                "before_filter_counts": list(search_stats["raw_counts"]),
                "after_filter_counts": list(search_stats["filtered_counts"]),
                "before_filter_count": raw_total,
                "after_filter_count": filtered_total,
                "filtered_count": max(raw_total - filtered_total, 0),
            }
            payload = {
                **filter_payload,
                **response_filter_payload,
                "final_retrieved_document_ids": sorted(
                    {
                        str(
                            (item.get("metadata") or {}).get("document_id")
                            or ""
                        ).strip()
                        for item in (response.get("retrieved") or [])
                        if isinstance(item, Mapping)
                        and str(
                            ((item.get("metadata") or {}).get("document_id") or "")
                        ).strip()
                    }
                ),
                "final_retrieved_relative_paths": sorted(
                    {
                        self._normalize_relative_path(
                            (item.get("metadata") or {}).get("relative_path")
                            or item.get("relative_path")
                        )
                        for item in (response.get("retrieved") or [])
                        if isinstance(item, Mapping)
                    }
                    - {""}
                ),
            }
            response[response_key] = payload
            logger.info(
                "knowledge_engine_scope_filter_applied",
                extra={
                    "event": (
                        "selected_context"
                        if response_key == "selected_context_filter"
                        else "access_scope"
                    ),
                    "requested_selected_document_ids": filter_payload.get("selected_document_ids", []),
                    "requested_selected_folder_ids": filter_payload.get("selected_folder_ids", []),
                    "resolved_authorized_document_ids": filter_payload.get("effective_document_ids", []),
                    "resolved_authorized_relative_paths": filter_payload.get("effective_scope", {}).get("relative_paths", []),
                    "final_retrieved_document_ids": payload["final_retrieved_document_ids"],
                    "final_retrieved_relative_paths": payload["final_retrieved_relative_paths"],
                },
            )
            return response
        finally:
            set_retrieval_relative_paths = getattr(
                pipeline,
                "set_retrieval_relative_paths",
                None,
            )
            if callable(set_retrieval_relative_paths):
                set_retrieval_relative_paths(None)
            pipeline._search = original_search
            for name, value in saved_values.items():
                if value is not None:
                    setattr(config, name, value)
            on_config_changed = getattr(pipeline, "on_config_changed", None)
            if callable(on_config_changed):
                on_config_changed()

    @staticmethod
    def _answer_loaded_pipeline(
        pipeline: Any,
        question: str,
    ) -> Mapping[str, Any]:
        """Execute only the query path over the active published generation.

        ``BasicRAGPipeline.run`` is the notebook/batch bootstrap and may load,
        chunk, embed, or index when those experiment fields are empty. The
        production runtime deliberately keeps only its Qdrant client, models,
        and published BM25 snapshot, so chat must enter at ``answer``.
        """

        answer = getattr(pipeline, "answer", None)
        if not callable(answer):
            raise KnowledgeEngineUnavailable(
                "The published retrieval runtime has no query entrypoint."
            )
        return answer(question)

    def _engine_error_message(self) -> str:
        if self._import_error is None:
            return "Phase 4.5 engine is unavailable."
        return f"Phase 4.5 engine import failed: {self._import_error}"

    def check_ollama_model(self, config: Any | None = None) -> tuple[bool, str]:
        """Check the configured local generation model without answering."""

        config = config or self.build_config()
        try:
            from ollama import ResponseError, list as list_ollama_models
            from httpx import HTTPError
        except Exception as exc:  # noqa: BLE001
            return False, f"Ollama dependencies are unavailable: {exc}"

        try:
            available_models = {
                model.model
                for model in list_ollama_models().models
                if model.model is not None
            }
        except (HTTPError, OSError, ResponseError) as exc:
            return False, (
                "The local Ollama service is unavailable. Start Ollama and "
                f"confirm that '{config.ollama_model_name}' is installed. {exc}"
            )
        if config.ollama_model_name not in available_models:
            return False, (
                f"Configured Ollama model '{config.ollama_model_name}' is not "
                "installed locally."
            )
        return True, "Configured Ollama model is available."

    @staticmethod
    def _load_reranker(pipeline: Any) -> None:
        reranker = getattr(pipeline, "reranker", None)
        warm = getattr(reranker, "warm", None)
        load = getattr(reranker, "load", None)
        if not bool(getattr(pipeline.config, "reranker_enabled", True)):
            return
        if callable(warm):
            warm()
        elif callable(load):
            load()

    @classmethod
    def _emit_stage(
        cls,
        on_stage: Callable[[str, dict[str, int]], None] | None,
        stage: str,
        pipeline: Any,
    ) -> None:
        if on_stage is not None:
            on_stage(stage, cls._pipeline_counts(pipeline))

    @staticmethod
    def _pipeline_counts(pipeline: Any) -> dict[str, int]:
        plan = getattr(pipeline, "indexing_plan", None)
        if plan is not None:
            documents_seen = sum(
                len(getattr(plan, name, []) or [])
                for name in ("new", "changed", "unchanged")
            )
        else:
            documents_seen = len(getattr(pipeline, "documents", []) or [])
        documents_indexed = documents_seen
        return {
            "documents_seen": int(documents_seen),
            "documents_indexed": int(documents_indexed),
            "chunks_indexed": len(getattr(pipeline, "chunks", []) or []),
        }

    def _to_chat_response(
        self,
        response: Mapping[str, Any],
        *,
        config: Any,
        profile: str,
        selected_scope: SelectedContextScope,
        include_debug: bool,
        include_sources: bool,
        latency_ms: int,
        access_context: RequestAccessContext | None = None,
        allowed_relative_paths: frozenset[str] | None = None,
    ) -> ChatResponse:
        citations = self._citations(
            response,
            access_context=access_context,
            allowed_relative_paths=allowed_relative_paths,
        )
        sources = (
            self._sources(
                response,
                access_context=access_context,
                allowed_relative_paths=allowed_relative_paths,
            )
            if include_sources
            else []
        )
        context_stages = response.get("context_stages")
        compressed_chunks = (
            list(context_stages.get("compressed") or [])
            if isinstance(context_stages, Mapping)
            else []
        )
        retrieved_chunks = (
            list(response.get("retrieved") or [])
            if isinstance(response.get("retrieved"), list)
            else []
        )
        selected_evidence = (
            list(response.get("selected_evidence") or [])
            if isinstance(response.get("selected_evidence"), list)
            else []
        )
        metadata = ChatMetadata(
            retrieval_mode=str(response.get("retrieval_mode") or "hybrid_rrf_reranked"),
            phase=settings.phase,
            latency_ms=latency_ms,
            model=settings.ollama_model_name,
            profile=profile,
            effective_min_answer_words=getattr(config, "min_answer_words", None),
            effective_max_answer_words=getattr(config, "max_answer_words", None),
            answer_detail_level=str(getattr(config, "answer_detail_level", "detailed")),
            adaptive_sections=bool(getattr(config, "adaptive_answer_sections", True)),
            temperature=0,
            evidence_token_budget=getattr(config, "evidence_token_budget", None),
            max_context_tokens=getattr(config, "max_context_tokens", None),
            retrieved_count=len(retrieved_chunks),
            selected_evidence_count=len(selected_evidence),
            context_sections=len(compressed_chunks),
            weak_evidence=bool(response.get("weak_evidence")),
            selected_context_applied=selected_scope.applied,
            selected_document_count=selected_scope.selected_document_count,
            selected_folder_count=selected_scope.selected_folder_count,
            selected_note_count=getattr(selected_scope,"selected_note_count",0),
            effective_document_count=selected_scope.effective_document_count,
            selected_context_filter_mode=selected_scope.filter_mode,
        )
        debug = (
            self._debug_payload(response, config=config, selected_scope=selected_scope)
            if include_debug
            else None
        )
        valid_citation_ids = {
            int(item.id.removeprefix("S"))
            for item in citations
            if item.id.removeprefix("S").isdigit()
        }
        answer = re.sub(
            r"\[(\d+)\]",
            lambda match: match.group(0)
            if int(match.group(1)) in valid_citation_ids
            else "[citation unavailable]",
            str(response.get("answer") or ""),
        )
        return ChatResponse(
            answer=answer,
            citations=citations,
            sources=sources,
            metadata=metadata,
            debug=debug,
            evidence_snapshot=self._evidence_snapshot(compressed_chunks or selected_evidence),
        )

    @staticmethod
    def _evidence_snapshot(chunks: list[Any]) -> list[dict[str, Any]]:
        """Freeze the exact final prompt evidence independently of the index."""
        snapshot: list[dict[str, Any]] = []
        for index, item in enumerate(chunks, start=1):
            if not isinstance(item, Mapping):
                continue
            metadata = item.get("metadata") if isinstance(item.get("metadata"), Mapping) else {}
            text = str(item.get("text") or item.get("page_content") or item.get("content") or "")
            if not text.strip():
                continue
            snapshot.append({
                "reference_id": int(item.get("reference_id") or metadata.get("reference_id") or index),
                "document_id": item.get("document_id") or metadata.get("document_id"),
                "document_version_id": item.get("document_version_id") or metadata.get("document_version_id"),
                "chunk_id": item.get("chunk_id") or metadata.get("chunk_id"),
                "page": item.get("page_number") or item.get("page") or metadata.get("page_number") or metadata.get("page"),
                "source_name": item.get("source_name") or item.get("source") or metadata.get("file_name") or metadata.get("source"),
                "relative_path": item.get("relative_path") or metadata.get("relative_path"),
                "text": text,
                "score": item.get("reranker_score") or item.get("score") or item.get("rrf_score"),
                "provenance": item.get("provenance") or metadata.get("provenance"),
            })
        return snapshot

    @staticmethod
    def _debug_payload(
        response: Mapping[str, Any],
        *,
        config: Any,
        selected_scope: SelectedContextScope,
    ) -> dict[str, Any]:
        selected_evidence = response.get("selected_evidence") or []
        if not isinstance(selected_evidence, list):
            selected_evidence = []
        evidence_summaries = []
        for item in selected_evidence[:8]:
            if not isinstance(item, Mapping):
                continue
            metadata = item.get("metadata")
            metadata = metadata if isinstance(metadata, Mapping) else {}
            evidence_summaries.append(
                {
                    "source": item.get("source") or metadata.get("file_name"),
                    "relative_path": metadata.get("relative_path"),
                    "page": item.get("page_number") or metadata.get("page_number"),
                    "chunk_id": item.get("chunk_id") or metadata.get("chunk_id"),
                    "score": item.get("reranker_score") or item.get("score"),
                    "preview": " ".join(str(item.get("text") or "").split())[:500],
                }
            )
        return {
            "prompt_name": "generation.phase4_system",
            "profile": str(getattr(config, "answer_detail_level", "detailed")),
            "effective_min_answer_words": getattr(config, "min_answer_words", None),
            "effective_max_answer_words": getattr(config, "max_answer_words", None),
            "prompt_preview": str(response.get("prompt") or "")[:4000],
            "context_preview": str(response.get("context") or "")[:4000],
            "selected_evidence": evidence_summaries,
            "access_scope_filter": response.get("access_scope_filter"),
            "selected_context_filter": response.get("selected_context_filter")
            or {
                "applied": selected_scope.applied,
                "mode": selected_scope.filter_mode,
                "selected_document_ids": list(selected_scope.selected_document_ids),
                "selected_folder_ids": list(selected_scope.selected_folder_ids),
                "selected_note_ids": list(selected_scope.selected_note_ids),
                "effective_document_ids": list(selected_scope.effective_document_ids),
                "effective_scope": {
                    "document_count": selected_scope.effective_document_count,
                    "relative_paths": sorted(selected_scope.allowed_relative_paths),
                },
            },
        }

    def _citations(
        self,
        response: Mapping[str, Any],
        *,
        access_context: RequestAccessContext | None = None,
        allowed_relative_paths: frozenset[str] | None = None,
    ) -> list[ChatCitation]:
        citation_payload = response.get("citations") or []
        sources = self._sources(
            response,
            access_context=access_context,
            allowed_relative_paths=allowed_relative_paths,
        )
        source_by_id = {source.id: source for source in sources}
        citations: list[ChatCitation] = []
        seen_reference_ids: set[int] = set()
        for index, citation in enumerate(citation_payload, start=1):
            if not isinstance(citation, Mapping):
                continue
            try:
                reference_id = int(citation.get("reference_id") or index)
            except (TypeError, ValueError):
                continue
            if reference_id < 1 or reference_id in seen_reference_ids:
                continue
            source_id = f"S{reference_id}"
            source = source_by_id.get(source_id)
            if source is None:
                continue
            seen_reference_ids.add(reference_id)
            normalized_page = (
                self._optional_page(citation.get("page_number"))
                if citation.get("page_number") not in {None, ""}
                else self._page_from_index(citation.get("page_index"))
                if citation.get("page_index") not in {None, ""}
                else (source.page if source else None)
            )
            logger.debug(
                "citation_pdf_navigation_metadata",
                extra={
                    "citation_id": source_id,
                    "document_id": source.document_id if source else None,
                    "repository_id": source.repository_id if source else None,
                    "version_id": source.document_version_id if source else None,
                    "mime_type": source.mime_type if source else None,
                    "extracted_page": citation.get("page_number"),
                    "page_index": citation.get("page_index"),
                    "normalized_page": normalized_page,
                    "pdf_endpoint_url": source.file_url if source else None,
                    "fallback_reason": None if source and normalized_page else "missing_source_or_page_metadata",
                },
            )
            citations.append(
                ChatCitation(
                    id=source_id,
                    document_name=str(
                        citation.get("source_file")
                        or citation.get("source")
                        or "Unknown document"
                    ),
                    document_id=source.document_id if source else None,
                    document_version_id=source.document_version_id if source else None,
                    repository_id=source.repository_id if source else None,
                    relative_path=source.relative_path if source else None,
                    page=normalized_page,
                    page_number=normalized_page,
                    page_index=(
                        self._optional_page_index(citation.get("page_index"))
                        if citation.get("page_index") not in {None, ""}
                        else (source.page_index if source else None)
                    ),
                    location_label=(f"Page {normalized_page}" if normalized_page is not None else None),
                    page_count=source.page_count if source else None,
                    sheet_name=self._optional_str(
                        citation.get("sheet_name")
                        or (source.sheet_name if source else None)
                    ),
                    sheet_index=self._optional_int(
                        citation.get("sheet_index")
                        or (source.sheet_index if source else None)
                    ),
                    slide_number=self._optional_int(
                        citation.get("slide_number")
                        or (source.slide_number if source else None)
                    ),
                    anchor=self._optional_str(
                        citation.get("anchor")
                        or (source.anchor if source else None)
                        or (source.chunk_id if source else None)
                    ),
                    chunk_id=source.chunk_id if source else None,
                    snippet=(source.text[:400] if source else ""),
                    highlight_text=source.highlight_text if source else None,
                    preview_text=source.preview_text if source else None,
                    file_type=source.file_type if source else None,
                    mime_type=source.mime_type if source else None,
                    file_url=source.file_url if source else None,
                    preview_url=source.file_url if source else None,
                    download_url=(
                        source.file_url.replace("/file", "/download")
                        if source and source.file_url else None
                    ),
                    score=self._optional_float(citation.get("score")),
                    source_type=source.source_type if source else "document",
                    note_id=source.note_id if source else None,
                    note_revision=source.note_revision if source else None,
                    workspace_id=source.workspace_id if source else None,
                    block_id=source.block_id if source else None,
                )
            )
        return citations

    def _sources(
        self,
        response: Mapping[str, Any],
        *,
        access_context: RequestAccessContext | None = None,
        allowed_relative_paths: frozenset[str] | None = None,
    ) -> list[ChatSource]:
        stages = response.get("context_stages")
        chunks: list[Any] = []
        if isinstance(stages, Mapping):
            chunks = list(stages.get("compressed") or stages.get("retrieved") or [])
        if not chunks:
            chunks = list(response.get("retrieved") or [])
        if allowed_relative_paths:
            chunks = [
                chunk
                for chunk in chunks
                if isinstance(chunk, Mapping)
                and self._result_matches_selected_context(chunk, allowed_relative_paths)
            ]
        document_context = self._document_context(
            chunks,
            access_context=access_context,
            allowed_relative_paths=allowed_relative_paths,
        )
        sources: list[ChatSource] = []
        for index, chunk in enumerate(chunks, start=1):
            if not isinstance(chunk, Mapping):
                continue
            metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), Mapping) else {}
            context = self._context_for_chunk(chunk, metadata, document_context)
            relative_path = context.get("relative_path") or self._normalize_relative_path(
                metadata.get("relative_path") or chunk.get("relative_path")
            )
            path = relative_path or str(metadata.get("source") or chunk.get("source") or "")
            document_name = (
                str(context.get("name") or metadata.get("file_name"))
                if context.get("name") or metadata.get("file_name")
                else Path(relative_path or path).name if (relative_path or path) else "Unknown document"
            )
            preview_text = str(chunk.get("page_content") or chunk.get("text") or chunk.get("content") or "")
            file_id = context.get("document_id")
            sources.append(
                ChatSource(
                    id=f"S{index}",
                    document_name=document_name,
                    path=path,
                    document_id=str(file_id) if file_id else None,
                    document_version_id=self._optional_str(context.get("document_version_id") or metadata.get("document_version_id")),
                    repository_id=self._optional_str(
                        context.get("repository_id") or metadata.get("repository_id")
                    ),
                    relative_path=relative_path or None,
                    page=self._result_page(chunk, metadata, context),
                    page_number=self._result_page(chunk, metadata, context),
                    page_index=self._optional_page_index(
                        self._first_present(chunk.get("page_index"), metadata.get("page_index"))
                    ),
                    location_label=(
                        f"Page {self._result_page(chunk, metadata, context)}"
                        if self._result_page(chunk, metadata, context) is not None else None
                    ),
                    page_count=self._optional_int(context.get("page_count")),
                    sheet_name=self._optional_str(
                        chunk.get("sheet_name")
                        or metadata.get("sheet_name")
                        or context.get("active_sheet")
                    ),
                    sheet_index=self._optional_int(
                        chunk.get("sheet_index")
                        or metadata.get("sheet_index")
                        or context.get("active_sheet_index")
                    ),
                    slide_number=self._optional_int(
                        chunk.get("slide_number")
                        or metadata.get("slide_number")
                        or context.get("slide_number")
                    ),
                    anchor=self._optional_str(
                        chunk.get("anchor")
                        or metadata.get("anchor")
                        or context.get("anchor")
                        or chunk.get("chunk_id")
                        or metadata.get("chunk_id")
                    ),
                    chunk_id=str(chunk.get("chunk_id") or metadata.get("chunk_id") or ""),
                    text=preview_text,
                    highlight_text=str(context.get("highlight_text") or preview_text[:1000] or ""),
                    preview_text=preview_text[:4000] or None,
                    file_type=str(context.get("file_type") or metadata.get("file_type") or ""),
                    mime_type=self._optional_str(context.get("mime_type") or metadata.get("mime_type")),
                    file_url=(
                        f"/api/corpus/document/{file_id}/file"
                        if file_id
                        else None
                    ),
                    score=self._optional_float(
                        chunk.get("reranker_score")
                        or chunk.get("score")
                        or chunk.get("rrf_score")
                    ),
                    source_type="note" if metadata.get("entity_type")=="note" else "document",
                    note_id=self._optional_str(metadata.get("note_id")),
                    note_revision=self._optional_int(metadata.get("note_revision")),
                    workspace_id=self._optional_str(metadata.get("workspace_id")),
                    block_id=self._optional_str(metadata.get("block_id")),
                )
            )
        return sources

    def _document_context(
        self,
        chunks: list[Any],
        *,
        access_context: RequestAccessContext | None = None,
        allowed_relative_paths: frozenset[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        relative_paths: set[str] = set()
        document_ids: set[uuid.UUID] = set()
        chunk_ids_by_document: dict[uuid.UUID, set[str]] = {}

        for chunk in chunks:
            if not isinstance(chunk, Mapping):
                continue
            metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), Mapping) else {}
            relative_path = self._normalize_relative_path(
                metadata.get("relative_path") or chunk.get("relative_path")
            )
            if relative_path:
                relative_paths.add(relative_path)
            try:
                document_id = uuid.UUID(str(metadata.get("document_id") or ""))
            except (TypeError, ValueError):
                document_id = None
            if document_id is not None:
                document_ids.add(document_id)
                chunk_id = str(chunk.get("chunk_id") or metadata.get("chunk_id") or "").strip()
                if chunk_id:
                    chunk_ids_by_document.setdefault(document_id, set()).add(chunk_id)

        if SessionLocal is None or (not relative_paths and not document_ids):
            return {}

        by_document_id: dict[uuid.UUID, dict[str, Any]] = {}
        with SessionLocal() as session:
            statement = select(Document)
            if document_ids:
                statement = statement.where(
                    or_(
                        Document.id.in_(sorted(document_ids)),
                        Document.relative_path.in_(sorted(relative_paths)) if relative_paths else false(),
                    )
                )
            elif relative_paths:
                statement = statement.where(Document.relative_path.in_(sorted(relative_paths)))
            statement = statement.where(Document.repository_id == settings.corpus_repository_id)
            if access_context is not None:
                statement = apply_document_access_filter(
                    statement,
                    access_context,
                    allowed_relative_paths=allowed_relative_paths,
                )
            elif allowed_relative_paths:
                statement = statement.where(Document.relative_path.in_(sorted(allowed_relative_paths)))
            documents = session.scalars(statement).all()
            for document in documents:
                by_document_id[document.id] = self._serialize_document_context(document)

            for document_id, chunk_ids in chunk_ids_by_document.items():
                if document_id not in by_document_id or not chunk_ids:
                    continue
                chunk_rows = session.scalars(
                    select(DocumentChunk).where(
                        DocumentChunk.document_id == document_id,
                        DocumentChunk.chunk_id.in_(sorted(chunk_ids)),
                    )
                ).all()
                chunk_map = {
                    row.chunk_id: {
                        "page": row.page,
                        "text_preview": row.text_preview,
                        "sheet_name": (
                            row.metadata_.get("sheet_name")
                            if isinstance(row.metadata_, dict)
                            else None
                        ),
                        "sheet_index": (
                            row.metadata_.get("sheet_index")
                            if isinstance(row.metadata_, dict)
                            else None
                        ),
                        "slide_number": (
                            row.metadata_.get("slide_number")
                            if isinstance(row.metadata_, dict)
                            else None
                        ),
                        "anchor": (
                            row.metadata_.get("anchor")
                            if isinstance(row.metadata_, dict)
                            else row.chunk_id
                        ),
                    }
                    for row in chunk_rows
                }
                by_document_id[document_id]["chunks"] = chunk_map

        by_relative_path: dict[str, dict[str, Any]] = {}
        for context in by_document_id.values():
            relative_path = self._normalize_relative_path(context.get("relative_path"))
            if relative_path:
                by_relative_path[relative_path] = context
            document_id = context.get("document_id")
            if document_id:
                by_relative_path[str(document_id)] = context
        return by_relative_path

    def _accessible_relative_paths(
        self,
        access_context: RequestAccessContext,
    ) -> frozenset[str] | None:
        if SessionLocal is None:
            return None
        with SessionLocal() as session:
            paths = set(list_accessible_relative_paths(session, access_context))
            if (
                access_context.scope in {"hybrid", "my-workspace"}
                and access_context.principal.user_id is not None
            ):
                rows = session.execute(
                    select(Note, NoteIndexState)
                    .join(NoteIndexState, NoteIndexState.note_id == Note.id)
                    .where(
                        Note.owner_user_id == access_context.principal.user_id,
                        Note.deleted_at.is_(None),
                        Note.is_archived.is_(False),
                        NoteIndexState.status == "indexed",
                        NoteIndexState.indexed_revision == Note.revision,
                    )
                ).all()
                # Text comes only from the committed generation snapshot. This
                # query contributes authorization paths, never a second mutable
                # lexical corpus.
                paths.update(note_relative_path(note.id) for note, _ in rows)
            return frozenset(paths)

    def _requested_scope_relative_paths(
        self,
        access_context: RequestAccessContext,
        search_scope: str,
    ) -> frozenset[str] | None:
        """Narrow authorized sources to the caller's explicit retrieval scope."""

        if SessionLocal is None or search_scope == "hybrid":
            return None
        with SessionLocal() as session:
            storage_scope = "enterprise" if search_scope == "enterprise" else "personal"
            statement = select(Document.relative_path).where(Document.storage_scope == storage_scope)
            paths = {
                self._normalize_relative_path(value)
                for value in session.scalars(apply_document_access_filter(statement, access_context))
                if value
            }
            if search_scope in {"workspace", "current_upload"} and access_context.principal.user_id is not None:
                paths.update(
                    note_relative_path(note_id)
                    for note_id in session.scalars(
                        select(Note.id).where(
                            Note.owner_user_id == access_context.principal.user_id,
                            Note.deleted_at.is_(None),
                            Note.is_archived.is_(False),
                        )
                    )
                )
            return frozenset(paths)

    @staticmethod
    def _effective_relative_paths(
        access_relative_paths: frozenset[str] | None,
        selected_scope: SelectedContextScope,
    ) -> frozenset[str]:
        if access_relative_paths is None:
            return selected_scope.allowed_relative_paths
        if not selected_scope.applied:
            return access_relative_paths
        return frozenset(access_relative_paths.intersection(selected_scope.allowed_relative_paths))

    @staticmethod
    def _serialize_document_context(document: Document) -> dict[str, Any]:
        return {
            "document_id": str(document.id),
            "document_version_id": str(document.current_version_id) if document.current_version_id else None,
            "repository_id": document.repository_id,
            "name": document.name,
            "relative_path": document.relative_path,
            "page_count": document.page_count,
            "file_type": document.file_type,
            "mime_type": document.mime_type,
            "chunks": {},
        }

    def _context_for_chunk(
        self,
        chunk: Mapping[str, Any],
        metadata: Mapping[str, Any],
        document_context: Mapping[str, dict[str, Any]],
    ) -> dict[str, Any]:
        relative_path = self._normalize_relative_path(
            metadata.get("relative_path") or chunk.get("relative_path")
        )
        raw_document_id = metadata.get("document_id")
        context = {}
        if raw_document_id:
            context = document_context.get(str(raw_document_id), {})
        if not context and relative_path:
            context = document_context.get(relative_path, {})
        context = dict(context)
        chunk_id = str(chunk.get("chunk_id") or metadata.get("chunk_id") or "").strip()
        chunk_context = context.get("chunks", {}).get(chunk_id, {}) if context else {}
        text_preview = str(chunk_context.get("text_preview") or "").strip()
        if chunk_context.get("page") is not None:
            context["page"] = chunk_context.get("page")
        if chunk_context.get("sheet_name") is not None:
            context["sheet_name"] = chunk_context.get("sheet_name")
        if chunk_context.get("sheet_index") is not None:
            context["active_sheet_index"] = chunk_context.get("sheet_index")
        if chunk_context.get("slide_number") is not None:
            context["slide_number"] = chunk_context.get("slide_number")
        if chunk_context.get("anchor") is not None:
            context["anchor"] = chunk_context.get("anchor")
        if text_preview:
            context["highlight_text"] = text_preview
        elif chunk.get("text") or chunk.get("page_content") or chunk.get("content"):
            context["highlight_text"] = str(
                chunk.get("text")
                or chunk.get("page_content")
                or chunk.get("content")
                or ""
            )[:1000]
        if not context.get("page_count") and self._optional_int(metadata.get("page_count")) is not None:
            context["page_count"] = self._optional_int(metadata.get("page_count"))
        if not context.get("file_type") and metadata.get("file_type"):
            context["file_type"] = str(metadata.get("file_type"))
        if not context.get("mime_type") and metadata.get("mime_type"):
            context["mime_type"] = str(metadata.get("mime_type"))
        if not context.get("document_version_id") and metadata.get("document_version_id"):
            context["document_version_id"] = str(metadata.get("document_version_id"))
        if not context.get("relative_path") and relative_path:
            context["relative_path"] = relative_path
        if not context.get("document_id") and raw_document_id:
            context["document_id"] = str(raw_document_id)
        if not context.get("repository_id") and metadata.get("repository_id"):
            context["repository_id"] = str(metadata.get("repository_id"))
        return context

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _optional_page(cls, value: Any) -> int | None:
        parsed = cls._optional_int(value)
        if parsed is None or parsed <= 0:
            return None
        return parsed

    @classmethod
    def _optional_page_index(cls, value: Any) -> int | None:
        parsed = cls._optional_int(value)
        return parsed if parsed is not None and parsed >= 0 else None

    @classmethod
    def _page_from_index(cls, value: Any) -> int | None:
        index = cls._optional_page_index(value)
        return index + 1 if index is not None else None

    @classmethod
    def _result_page(
        cls,
        chunk: Mapping[str, Any],
        metadata: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> int | None:
        explicit = cls._optional_page(
            cls._first_present(
                chunk.get("page_number"),
                metadata.get("page_number"),
                context.get("page"),
            )
        )
        if explicit is not None:
            return explicit
        return cls._page_from_index(
            cls._first_present(chunk.get("page_index"), metadata.get("page_index"))
        )

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _first_present(*values: Any) -> Any:
        for value in values:
            if value is not None and value != "":
                return value
        return None
