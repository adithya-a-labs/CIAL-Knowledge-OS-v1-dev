"""Adapter around the existing deterministic Phase 4.5 knowledge engine."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import logging
from pathlib import Path
import sys
from threading import Lock, RLock
import time
from typing import Any, Callable
import uuid

from backend.app.core.config import settings
from backend.app.core.paths import KNOWLEDGE_ENGINE_SRC, REPO_ROOT
from backend.app.db.session import SessionLocal
from backend.app.models.knowledge import Document, DocumentChunk, DocumentVersion, Folder
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
    effective_document_ids: tuple[str, ...] = ()
    selected_document_count: int = 0
    selected_folder_count: int = 0
    effective_document_count: int = 0
    filter_mode: str | None = None


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
    except Exception:  # noqa: BLE001 - the normal pipeline path will report this.
        return False

    previous = load_manifest(
        config.document_manifest_path,
        corpus_root=config.knowledge_root,
        collection_name=config.qdrant_collection_name,
    )
    if not previous:
        return False

    client: QdrantClient | None = None
    try:
        client = QdrantClient(
            url=config.qdrant_url,
            api_key=config.qdrant_api_key,
        )
        if not client.collection_exists(config.qdrant_collection_name):
            return True
        collection = client.get_collection(config.qdrant_collection_name)
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
        self._load_engine_symbols()

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

    def is_ready(self) -> bool:
        with self._lock:
            pipeline = self._pipeline
        return bool(
            pipeline is not None
            and getattr(pipeline, "is_ready_for_answering", False)
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
                document_id=str(document_id), execution_manager=pipeline.execution_manager,
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

    def answer_question(
        self,
        request: ChatRequest,
        *,
        access_context: RequestAccessContext | None = None,
        progress_callback: Any | None = None,
    ) -> ChatResponse:
        def progress(stage_id: str, status: str, **metrics: Any) -> None:
            if progress_callback is not None:
                progress_callback(stage_id, status, metrics)

        progress("request.validating", "started")
        if not self.engine_available:
            raise KnowledgeEngineUnavailable(self._engine_error_message())

        access_context = access_context or anonymous_access_context()
        profile = self._resolve_profile(request.response_length, request.profile)
        pipeline = self._ready_pipeline(
            request.response_length,
            profile=request.profile,
            max_answer_words=request.max_answer_words,
        )
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
        progress("context.building", "completed", documents_searched=len(effective_relative_paths or ()))
        started_at = time.perf_counter()
        try:
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
                response = pipeline.run(request.question)
            retrieved = response.get("retrieved") if isinstance(response, Mapping) else None
            selected = response.get("selected_evidence") if isinstance(response, Mapping) else None
            progress("retrieval.searching", "completed", candidates=len(retrieved) if isinstance(retrieved, list) else 0)
            progress("evidence.selecting", "completed", selected_evidence=len(selected) if isinstance(selected, list) else 0)
        except Exception as exc:  # noqa: BLE001 - convert local runtime failures to API errors.
            logger.exception("knowledge_engine_answer_failed")
            raise KnowledgeEngineUnavailable(str(exc)) from exc

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
            qdrant_mode=settings.qdrant_mode,
            qdrant_url=settings.qdrant_url,
            qdrant_api_key=settings.qdrant_api_key,
            qdrant_batch_size=settings.qdrant_batch_size,
            qdrant_upsert_wait=settings.qdrant_upsert_wait,
            ollama_model_name=settings.ollama_model_name,
            embedding_model_name=settings.embedding_model_name,
            reranker_model_name=settings.reranker_model_name,
            reranker_device=settings.reranker_device,
            reranker_batch_size=settings.reranker_batch_size,
            reranker_local_files_only=settings.reranker_local_files_only,
            force_rebuild_index=(
                settings.force_rebuild_on_startup
                if force_rebuild_index is None
                else force_rebuild_index
            ),
            require_authorization_metadata=True,
            max_answer_words=settings.max_answer_words,
            generation_retries=settings.generation_retries,
            retry_cooldown_seconds=settings.retry_cooldown_seconds,
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
        if request.search_scope == "current_upload" and not document_ids:
            raise KnowledgeEngineInvalidRequest("Current Upload requires at least one uploaded document.")
        if not document_ids and not folder_ids:
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
                folder = self._folder_for_context_id(session, value)
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

        if not_ready:
            raise KnowledgeEngineDocumentsNotReady(not_ready)

        if not relative_paths:
            raise KnowledgeEngineInvalidRequest(
                "Selected context did not resolve to any active documents."
            )
        return SelectedContextScope(
            applied=True,
            allowed_relative_paths=frozenset(relative_paths),
            selected_document_ids=tuple(document_ids),
            selected_folder_ids=tuple(folder_ids),
            effective_document_ids=tuple(sorted(effective_document_ids)),
            selected_document_count=len(document_ids),
            selected_folder_count=len(folder_ids),
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
    def _folder_for_context_id(session: Any, value: str) -> Folder | None:
        try:
            return session.get(Folder, uuid.UUID(value))
        except ValueError:
            return session.scalar(
                select(Folder).where(
                    Folder.repository_id == settings.corpus_repository_id,
                    Folder.relative_path == value,
                )
            )

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
        for candidate in candidates:
            for allowed in allowed_relative_paths:
                if candidate == allowed or candidate.endswith(f"/{allowed}"):
                    return True
        return False

    def _run_with_selected_context(
        self,
        pipeline: Any,
        question: str,
        selected_scope: SelectedContextScope,
    ) -> Mapping[str, Any]:
        if not selected_scope.applied:
            return pipeline.run(question)
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
        candidate_floor = max(
            _SELECTED_CONTEXT_RETRIEVAL_FLOOR,
            max(len(allowed_relative_paths), 1) * 12,
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
            response = dict(pipeline.run(question))
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
        load = getattr(reranker, "load", None)
        if callable(load) and bool(getattr(pipeline.config, "reranker_enabled", True)):
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
            effective_document_count=selected_scope.effective_document_count,
            selected_context_filter_mode=selected_scope.filter_mode,
        )
        debug = (
            self._debug_payload(response, config=config, selected_scope=selected_scope)
            if include_debug
            else None
        )
        return ChatResponse(
            answer=str(response.get("answer") or ""),
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
        for index, citation in enumerate(citation_payload, start=1):
            if not isinstance(citation, Mapping):
                continue
            reference_id = int(citation.get("reference_id") or index)
            source_id = f"S{reference_id}"
            source = source_by_id.get(source_id)
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
            return list_accessible_relative_paths(session, access_context)

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
