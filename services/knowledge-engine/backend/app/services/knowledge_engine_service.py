"""Adapter around the existing deterministic Phase 4.5 knowledge engine."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from pathlib import Path
import sys
from threading import RLock
import time
from typing import Any, Callable

from backend.app.core.config import settings
from backend.app.core.paths import KNOWLEDGE_ENGINE_SRC, REPO_ROOT
from backend.app.schemas.chat import (
    ChatCitation,
    ChatMetadata,
    ChatRequest,
    ChatResponse,
    ChatSource,
)

logger = logging.getLogger(__name__)


class KnowledgeEngineUnavailable(RuntimeError):
    """Raised when local engine dependencies or runtime services are missing."""


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
        response_length: str = "medium",
        on_stage: Callable[[str, dict[str, int]], None] | None = None,
    ) -> dict[str, int]:
        """Run the deterministic Phase 4 startup sequence and keep it alive."""

        if not self.engine_available:
            raise KnowledgeEngineUnavailable(self._engine_error_message())

        config = self.build_config(
            response_length=response_length,
            force_rebuild_index=force_rebuild_index,
        )
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

        pipeline = self._ready_pipeline(request.response_length)
        started_at = time.perf_counter()
        try:
            response = pipeline.run(request.question)
        except Exception as exc:  # noqa: BLE001 - convert local runtime failures to API errors.
            logger.exception("knowledge_engine_answer_failed")
            raise KnowledgeEngineUnavailable(str(exc)) from exc

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        return self._to_chat_response(
            response,
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

    def _ready_pipeline(self, response_length: str) -> Any:
        with self._lock:
            pipeline = self._pipeline
        if pipeline is None or not getattr(pipeline, "is_ready_for_answering", False):
            raise KnowledgeEngineUnavailable("Phase 4.5 engine is not ready.")
        self._apply_response_length(pipeline.config, response_length)
        return pipeline

    def _get_pipeline(self, response_length: str) -> Any:
        if self._pipeline is None:
            config = self.build_config(response_length=response_length)
            self._pipeline = self._phase4_pipeline_cls(config)
        else:
            self._apply_response_length(self._pipeline.config, response_length)
        return self._pipeline

    def build_config(
        self,
        *,
        response_length: str = "medium",
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
        self._apply_response_length(config, response_length)
        return config

    @staticmethod
    def _apply_response_length(config: Any, response_length: str) -> None:
        limits = {
            "short": (120, 250, "concise"),
            "medium": (250, 700, "detailed"),
            "long": (350, 1200, "detailed"),
        }
        min_words, max_words, detail = limits.get(response_length, limits["medium"])
        config.min_answer_words = min_words
        config.max_answer_words = max_words
        config.answer_detail_level = detail

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
        include_sources: bool,
        latency_ms: int,
    ) -> ChatResponse:
        citations = self._citations(response)
        sources = self._sources(response) if include_sources else []
        metadata = ChatMetadata(
            retrieval_mode=str(response.get("retrieval_mode") or "hybrid_rrf_reranked"),
            phase=settings.phase,
            latency_ms=latency_ms,
            model=settings.ollama_model_name,
        )
        return ChatResponse(
            answer=str(response.get("answer") or ""),
            citations=citations,
            sources=sources,
            metadata=metadata,
        )

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
