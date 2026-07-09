"""Adapter around the existing deterministic Phase 4.5 knowledge engine."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import logging
from pathlib import Path
import sys
from threading import RLock
import time
from typing import Any, Callable
import uuid

from backend.app.core.config import settings
from backend.app.core.paths import KNOWLEDGE_ENGINE_SRC, REPO_ROOT
from backend.app.db.session import SessionLocal
from backend.app.models.knowledge import Document, Folder
from backend.app.schemas.chat import (
    ChatCitation,
    ChatMetadata,
    ChatRequest,
    ChatResponse,
    ChatSource,
)
from sqlalchemy import select

logger = logging.getLogger(__name__)


class KnowledgeEngineUnavailable(RuntimeError):
    """Raised when local engine dependencies or runtime services are missing."""


class KnowledgeEngineInvalidRequest(ValueError):
    """Raised when a chat request asks for an invalid generation profile/scope."""


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
        self._import_error: Exception | None = None
        self._phase4_config_cls: Any | None = None
        self._phase4_pipeline_cls: Any | None = None
        self._lock = RLock()
        self._load_engine_symbols()

    @property
    def engine_available(self) -> bool:
        return self._phase4_config_cls is not None and self._phase4_pipeline_cls is not None

    def set_pipeline(self, pipeline: Any) -> None:
        with self._lock:
            old_pipeline = self._pipeline
            self._pipeline = pipeline
        if old_pipeline is not None and old_pipeline is not pipeline:
            close = getattr(old_pipeline, "close", None)
            if callable(close):
                close()

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
    ) -> dict[str, int]:
        """Run the deterministic Phase 4 startup sequence and keep it alive."""

        if not self.engine_available:
            raise KnowledgeEngineUnavailable(self._engine_error_message())

        config = self.build_config(
            response_length=response_length,
            force_rebuild_index=force_rebuild_index,
        )
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
        pipeline = self._phase4_pipeline_cls(config)
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

    def close(self) -> None:
        with self._lock:
            pipeline = self._pipeline
            self._pipeline = None
        if pipeline is not None:
            close = getattr(pipeline, "close", None)
            if callable(close):
                close()

    def answer_question(self, request: ChatRequest) -> ChatResponse:
        if not self.engine_available:
            raise KnowledgeEngineUnavailable(self._engine_error_message())

        profile = self._resolve_profile(request.response_length, request.profile)
        pipeline = self._ready_pipeline(
            request.response_length,
            profile=request.profile,
            max_answer_words=request.max_answer_words,
        )
        selected_scope = self._resolve_selected_context(request)
        started_at = time.perf_counter()
        try:
            response = self._run_with_selected_context(
                pipeline,
                request.question,
                selected_scope,
            )
        except Exception as exc:  # noqa: BLE001 - convert local runtime failures to API errors.
            logger.exception("knowledge_engine_answer_failed")
            raise KnowledgeEngineUnavailable(str(exc)) from exc

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return self._to_chat_response(
            response,
            config=pipeline.config,
            profile=profile.profile,
            selected_scope=selected_scope,
            include_debug=request.include_debug,
            include_sources=request.include_sources,
            latency_ms=latency_ms,
        )

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
            knowledge_root=settings.data_files_path,
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

    def _resolve_selected_context(self, request: ChatRequest) -> SelectedContextScope:
        document_ids = [value for value in request.selected_document_ids if value.strip()]
        folder_ids = [value for value in request.selected_folder_ids if value.strip()]
        if not document_ids and not folder_ids:
            return SelectedContextScope(applied=False, allowed_relative_paths=frozenset())
        if SessionLocal is None:
            raise KnowledgeEngineInvalidRequest(
                "Selected context requires the metadata database, but DATABASE_URL is not configured."
            )

        relative_paths: set[str] = set()
        with SessionLocal() as session:
            for value in document_ids:
                document = self._document_for_context_id(session, value)
                if document is None:
                    raise KnowledgeEngineInvalidRequest(
                        f"Selected document was not found: {value}"
                    )
                relative_paths.add(self._normalize_relative_path(document.relative_path))

            for value in folder_ids:
                folder = self._folder_for_context_id(session, value)
                if folder is None:
                    raise KnowledgeEngineInvalidRequest(
                        f"Selected folder was not found: {value}"
                    )
                folder_path = self._normalize_relative_path(folder.relative_path)
                if folder_path:
                    statement = select(Document).where(
                        Document.relative_path.like(f"{folder_path}/%"),
                        Document.indexing_status != "deleted",
                    )
                else:
                    statement = select(Document).where(
                        Document.indexing_status != "deleted"
                    )
                for document in session.scalars(statement):
                    relative_paths.add(
                        self._normalize_relative_path(document.relative_path)
                    )

        if not relative_paths:
            raise KnowledgeEngineInvalidRequest(
                "Selected context did not resolve to any active documents."
            )
        return SelectedContextScope(
            applied=True,
            allowed_relative_paths=frozenset(relative_paths),
            selected_document_count=len(document_ids),
            selected_folder_count=len(folder_ids),
            effective_document_count=len(relative_paths),
            filter_mode="post_retrieval_relative_path",
        )

    @staticmethod
    def _document_for_context_id(session: Any, value: str) -> Document | None:
        try:
            return session.get(Document, uuid.UUID(value))
        except ValueError:
            return session.scalar(
                select(Document).where(Document.relative_path == value)
            )

    @staticmethod
    def _folder_for_context_id(session: Any, value: str) -> Folder | None:
        try:
            return session.get(Folder, uuid.UUID(value))
        except ValueError:
            return session.scalar(select(Folder).where(Folder.relative_path == value))

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
            selected_scope.effective_document_count * 12,
        )

        def selected_search(query: str) -> list[dict[str, Any]]:
            raw_results = original_search(query)
            return [
                dict(result)
                for result in raw_results
                if self._result_matches_selected_context(
                    result,
                    selected_scope.allowed_relative_paths,
                )
            ]

        try:
            for name, value in saved_values.items():
                if value is not None:
                    setattr(config, name, max(int(value), candidate_floor))
            on_config_changed = getattr(pipeline, "on_config_changed", None)
            if callable(on_config_changed):
                on_config_changed()
            pipeline._search = selected_search
            response = dict(pipeline.run(question))
            response["selected_context_filter"] = {
                "applied": True,
                "mode": selected_scope.filter_mode,
                "effective_document_count": selected_scope.effective_document_count,
                "allowed_relative_paths": sorted(selected_scope.allowed_relative_paths),
                "candidate_floor": candidate_floor,
            }
            return response
        finally:
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
    ) -> ChatResponse:
        citations = self._citations(response)
        sources = self._sources(response) if include_sources else []
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
            if include_debug and settings.chat_debug
            else None
        )
        return ChatResponse(
            answer=str(response.get("answer") or ""),
            citations=citations,
            sources=sources,
            metadata=metadata,
            debug=debug,
        )

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
            "selected_context_filter": response.get("selected_context_filter")
            or {
                "applied": selected_scope.applied,
                "mode": selected_scope.filter_mode,
                "effective_document_count": selected_scope.effective_document_count,
            },
        }

    def _citations(self, response: Mapping[str, Any]) -> list[ChatCitation]:
        citation_payload = response.get("citations") or []
        sources = self._sources(response)
        snippets_by_id = {source.id: source.text[:400] for source in sources}
        citations: list[ChatCitation] = []
        for index, citation in enumerate(citation_payload, start=1):
            if not isinstance(citation, Mapping):
                continue
            reference_id = int(citation.get("reference_id") or index)
            source_id = f"S{reference_id}"
            citations.append(
                ChatCitation(
                    id=source_id,
                    document_name=str(
                        citation.get("source_file")
                        or citation.get("source")
                        or "Unknown document"
                    ),
                    page=self._optional_int(citation.get("page_number")),
                    snippet=snippets_by_id.get(source_id, ""),
                    score=self._optional_float(citation.get("score")),
                )
            )
        return citations

    def _sources(self, response: Mapping[str, Any]) -> list[ChatSource]:
        stages = response.get("context_stages")
        chunks: list[Any] = []
        if isinstance(stages, Mapping):
            chunks = list(stages.get("compressed") or stages.get("retrieved") or [])
        if not chunks:
            chunks = list(response.get("retrieved") or [])
        sources: list[ChatSource] = []
        for index, chunk in enumerate(chunks, start=1):
            if not isinstance(chunk, Mapping):
                continue
            metadata = chunk.get("metadata") if isinstance(chunk.get("metadata"), Mapping) else {}
            path = str(metadata.get("source") or chunk.get("source") or "")
            document_name = (
                str(metadata.get("file_name"))
                if metadata.get("file_name")
                else Path(path).name if path else "Unknown document"
            )
            sources.append(
                ChatSource(
                    id=f"S{index}",
                    document_name=document_name,
                    path=path,
                    document_id=(
                        str(metadata.get("document_id"))
                        if metadata.get("document_id")
                        else None
                    ),
                    page=self._optional_int(chunk.get("page_number") or metadata.get("page_number")),
                    chunk_id=str(chunk.get("chunk_id") or metadata.get("chunk_id") or ""),
                    text=str(
                        chunk.get("page_content")
                        or chunk.get("text")
                        or chunk.get("content")
                        or ""
                    ),
                    score=self._optional_float(
                        chunk.get("reranker_score")
                        or chunk.get("score")
                        or chunk.get("rrf_score")
                    ),
                )
            )
        return sources

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_float(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
