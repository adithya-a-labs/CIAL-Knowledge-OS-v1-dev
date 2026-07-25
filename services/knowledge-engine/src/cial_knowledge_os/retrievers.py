"""Composable dense, lexical, and hybrid retrieval implementations."""

from __future__ import annotations

import hashlib
import logging
import pickle
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from langchain_core.documents import Document

from .fusion import ReciprocalRankFusion
from .metadata import normalize_result

logger = logging.getLogger(__name__)
Tokenize = Callable[[str], list[str]]


class Retriever(Protocol):
    """Stable retrieval contract used by Phase 3 and future methods."""

    name: str

    def retrieve(self, query: str, *, top_k: int) -> list[dict[str, Any]]: ...


def default_bm25_tokenize(text: str) -> list[str]:
    """Tokenize lexical text deterministically without external resources."""

    return re.findall(r"[\w]+(?:[-'][\w]+)*", text.casefold(), flags=re.UNICODE)


@dataclass(slots=True)
class DenseRetriever:
    """Adapt the existing dense search function to :class:`Retriever`."""

    search: Callable[[str, int], list[dict[str, Any]]]
    name: str = "dense"

    def retrieve(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")
        results = [normalize_result(item) for item in self.search(query, top_k)]
        for rank, result in enumerate(results, start=1):
            result["retrieval_sources"] = [self.name]
            result["retrieval_ranks"] = {self.name: rank}
            result["retrieval_scores"] = {self.name: result.get("score")}
        logger.info(
            "dense_retrieval_complete",
            extra={"event": "dense_retrieval", "result_count": len(results)},
        )
        return results


@dataclass(frozen=True, slots=True)
class _BM25Cache:
    version: int
    fingerprint: str
    tokenized_corpus: list[list[str]]


class BM25Retriever:
    """In-memory BM25 retriever with validated persistent token cache."""

    name = "bm25"
    _CACHE_VERSION = 1

    def __init__(
        self,
        *,
        tokenizer: Tokenize = default_bm25_tokenize,
        k1: float = 1.5,
        b: float = 0.75,
        cache_path: str | Path | None = None,
    ) -> None:
        if k1 <= 0:
            raise ValueError("k1 must be greater than zero.")
        if not 0 <= b <= 1:
            raise ValueError("b must be between zero and one.")
        self.tokenizer = tokenizer
        self.k1 = k1
        self.b = b
        self.cache_path = (
            Path(cache_path).expanduser().resolve()
            if cache_path is not None
            else None
        )
        self._chunks: list[dict[str, Any]] = []
        self._tokenized_corpus: list[list[str]] = []
        self._index: Any | None = None
        self._fingerprint: str | None = None
        self.allowed_relative_paths: frozenset[str] | None = None
        self._authorized_indexes: OrderedDict[
            str,
            tuple[list[dict[str, Any]], list[list[str]], Any],
        ] = OrderedDict()
        self._authorized_cache_limit = 16
        self._authorized_lock = threading.RLock()

    @property
    def is_indexed(self) -> bool:
        return self._index is not None

    @staticmethod
    def _normalize_chunk(chunk: Document | Mapping[str, Any]) -> dict[str, Any]:
        if isinstance(chunk, Document):
            metadata = dict(chunk.metadata)
            return normalize_result(
                {
                    "text": chunk.page_content,
                    "metadata": metadata,
                    "source": metadata.get("file_name") or metadata.get("source"),
                    "page_number": metadata.get("page_number"),
                    "page_index": metadata.get("page_index"),
                    "sheet_name": metadata.get("sheet_name"),
                    "sheet_index": metadata.get("sheet_index"),
                    "slide_number": metadata.get("slide_number"),
                    "anchor": metadata.get("anchor"),
                    "chunk_id": metadata.get("chunk_id"),
                }
            )
        return normalize_result(chunk)

    @staticmethod
    def _normalize_relative_path(value: Any) -> str:
        return str(value or "").replace("\\", "/").strip("/")

    def set_allowed_relative_paths(
        self,
        allowed_relative_paths: frozenset[str] | None,
    ) -> None:
        if allowed_relative_paths is None:
            with self._authorized_lock:
                self.allowed_relative_paths = None
            return
        with self._authorized_lock:
            self.allowed_relative_paths = frozenset(
                self._normalize_relative_path(value)
                for value in allowed_relative_paths
                if self._normalize_relative_path(value)
            )

    def _is_allowed(
        self,
        chunk: Mapping[str, Any],
        allowed_relative_paths: frozenset[str] | None = None,
    ) -> bool:
        active_paths = (
            self.allowed_relative_paths
            if allowed_relative_paths is None
            else allowed_relative_paths
        )
        if active_paths is None:
            return True
        metadata = chunk.get("metadata")
        metadata = metadata if isinstance(metadata, Mapping) else {}
        relative_path = self._normalize_relative_path(
            chunk.get("relative_path") or metadata.get("relative_path")
        )
        return bool(relative_path and relative_path in active_paths)

    @staticmethod
    def _corpus_fingerprint(chunks: Sequence[Mapping[str, Any]]) -> str:
        digest = hashlib.sha256()
        for chunk in chunks:
            digest.update(str(chunk.get("source_path") or "").encode("utf-8"))
            digest.update(b"\0")
            digest.update(str(chunk.get("chunk_id") or "").encode("utf-8"))
            digest.update(b"\0")
            digest.update(str(chunk.get("text") or "").encode("utf-8"))
            digest.update(b"\0")
        return digest.hexdigest()

    def _load_cached_tokens(self, fingerprint: str) -> list[list[str]] | None:
        if self.cache_path is None or not self.cache_path.is_file():
            return None
        try:
            with self.cache_path.open("rb") as handle:
                cached = pickle.load(handle)
            if (
                not isinstance(cached, _BM25Cache)
                or cached.version != self._CACHE_VERSION
                or cached.fingerprint != fingerprint
            ):
                return None
            return cached.tokenized_corpus
        except (OSError, EOFError, pickle.UnpicklingError, AttributeError) as exc:
            logger.warning(
                "bm25_cache_invalid",
                extra={"event": "bm25_cache", "error": str(exc)},
            )
            return None

    def _save_cached_tokens(
        self,
        fingerprint: str,
        tokenized_corpus: list[list[str]],
    ) -> None:
        if self.cache_path is None:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        try:
            with temporary.open("wb") as handle:
                pickle.dump(
                    _BM25Cache(
                        self._CACHE_VERSION,
                        fingerprint,
                        tokenized_corpus,
                    ),
                    handle,
                    protocol=pickle.HIGHEST_PROTOCOL,
                )
            temporary.replace(self.cache_path)
        except OSError as exc:
            logger.warning(
                "bm25_cache_write_failed",
                extra={"event": "bm25_cache", "error": str(exc)},
            )
            temporary.unlink(missing_ok=True)

    def index(
        self,
        chunks: Sequence[Document | Mapping[str, Any]],
    ) -> bool:
        """Index the corpus and return whether work was performed."""

        normalized = [self._normalize_chunk(chunk) for chunk in chunks]
        if not normalized:
            performed = self._index is None or bool(self._chunks)
            self._chunks = []
            self._tokenized_corpus = []
            self._index = []
            self._fingerprint = self._corpus_fingerprint([])
            logger.info(
                "bm25_index_ready",
                extra={
                    "event": "bm25_index",
                    "chunk_count": 0,
                    "cache_hit": False,
                },
            )
            return performed
        fingerprint = self._corpus_fingerprint(normalized)
        if self._index is not None and fingerprint == self._fingerprint:
            logger.debug("bm25_index_reused", extra={"event": "bm25_index"})
            return False
        tokenized = self._load_cached_tokens(fingerprint)
        cache_hit = tokenized is not None
        if tokenized is None:
            tokenized = [self.tokenizer(chunk["text"]) for chunk in normalized]
            self._save_cached_tokens(fingerprint, tokenized)
        if not any(tokenized):
            raise ValueError(
                "Cannot build the BM25 index because all chunks are empty after "
                "tokenization. Check document extraction and tokenizer settings."
            )
        try:
            from rank_bm25 import BM25Okapi
        except ImportError as exc:
            raise RuntimeError(
                "BM25 retrieval requires rank-bm25. Install the pinned project "
                "dependencies from requirements.txt."
            ) from exc
        self._chunks = normalized
        self._tokenized_corpus = tokenized
        self._index = BM25Okapi(tokenized, k1=self.k1, b=self.b)
        self._fingerprint = fingerprint
        with self._authorized_lock:
            self._authorized_indexes.clear()
        logger.info(
            "bm25_index_ready",
            extra={
                "event": "bm25_index",
                "chunk_count": len(normalized),
                "cache_hit": cache_hit,
            },
        )
        return True

    def retrieve(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")
        if self._index is None:
            raise RuntimeError(
                "The BM25 index is not initialized. Call index(chunks) before "
                "retrieve()."
            )
        if not self._chunks:
            return []
        tokens = self.tokenizer(query)
        if not tokens:
            return []
        chunks = self._chunks
        active_corpus_tokens = self._tokenized_corpus
        active_index = self._index
        with self._authorized_lock:
            allowed_relative_paths = self.allowed_relative_paths
        if allowed_relative_paths is not None:
            cache_key = hashlib.sha256((self._fingerprint or "").encode() + b"\0" + "\0".join(sorted(allowed_relative_paths)).encode()).hexdigest()
            with self._authorized_lock:
                cached = self._authorized_indexes.get(cache_key)
            if cached is None:
                authorized = [
                    (chunk, tokens)
                    for chunk, tokens in zip(
                        self._chunks,
                        self._tokenized_corpus,
                        strict=True,
                    )
                    if self._is_allowed(chunk, allowed_relative_paths)
                ]
                chunks = [chunk for chunk, _ in authorized]
                active_corpus_tokens = [
                    chunk_tokens for _, chunk_tokens in authorized
                ]
                if not chunks:
                    return []
                try:
                    from rank_bm25 import BM25Okapi
                except ImportError as exc:
                    raise RuntimeError("BM25 retrieval requires rank-bm25.") from exc
                active_index = BM25Okapi(
                    active_corpus_tokens,
                    k1=self.k1,
                    b=self.b,
                )
                with self._authorized_lock:
                    self._authorized_indexes[cache_key] = (
                        chunks,
                        active_corpus_tokens,
                        active_index,
                    )
                    self._authorized_indexes.move_to_end(cache_key)
                    while len(self._authorized_indexes) > self._authorized_cache_limit:
                        self._authorized_indexes.popitem(last=False)
            else:
                chunks, active_corpus_tokens, active_index = cached
                with self._authorized_lock:
                    self._authorized_indexes.move_to_end(cache_key)
        scores = active_index.get_scores(tokens)
        ranked_indexes = sorted(
            range(len(scores)),
            key=lambda index: (-float(scores[index]), index),
        )
        results: list[dict[str, Any]] = []
        for index in ranked_indexes:
            score = float(scores[index])
            if score <= 0:
                if allowed_relative_paths is None:
                    continue
                overlap = len(
                    set(tokens).intersection(active_corpus_tokens[index])
                )
                if overlap <= 0:
                    continue
                score = overlap / max(len(set(tokens)), 1) * 1e-6
            result = dict(chunks[index])
            result.update(
                {
                    "score": score,
                    "retrieval_sources": [self.name],
                    "retrieval_ranks": {self.name: len(results) + 1},
                    "retrieval_scores": {self.name: score},
                }
            )
            results.append(result)
            if len(results) >= top_k:
                break
        logger.info(
            "bm25_retrieval_complete",
            extra={"event": "bm25_retrieval", "result_count": len(results)},
        )
        return results


class HybridRetriever:
    """Compose arbitrary retrievers through a configurable fusion strategy."""

    name = "hybrid"
    _HARD_TIMEOUTS_SECONDS = {
        "dense": 30.0,
        "bm25": 10.0,
        "hybrid_fusion": 5.0,
    }

    def __init__(
        self,
        retrievers: Sequence[Retriever],
        *,
        fuser: ReciprocalRankFusion,
        candidate_limits: Mapping[str, int],
        parallel: bool = True,
        stage_timeouts: Mapping[str, float] | None = None,
    ) -> None:
        if not retrievers:
            raise ValueError("HybridRetriever requires at least one retriever.")
        names = [retriever.name for retriever in retrievers]
        if len(names) != len(set(names)):
            raise ValueError("Hybrid retriever names must be unique.")
        self.retrievers = tuple(retrievers)
        self.fuser = fuser
        self.candidate_limits = dict(candidate_limits)
        self.parallel = parallel
        requested_timeouts = dict(stage_timeouts or {})
        self.stage_timeouts = {
            stage: min(
                float(requested_timeouts.get(stage, hard_timeout)),
                hard_timeout,
            )
            for stage, hard_timeout in self._HARD_TIMEOUTS_SECONDS.items()
        }
        if any(value <= 0 for value in self.stage_timeouts.values()):
            raise ValueError("Retrieval stage timeouts must be greater than zero.")
        self.last_rankings: dict[str, list[dict[str, Any]]] = {}
        self.last_stage_telemetry: dict[str, dict[str, Any]] = {}
        self.telemetry_callback: Callable[[str, str, dict[str, Any]], None] | None = None

    @staticmethod
    def _stage_name(retriever_name: str) -> str:
        return (
            "dense_retrieval"
            if retriever_name == "dense"
            else "bm25_retrieval"
        )

    def _emit_stage(
        self,
        stage: str,
        status: str,
        *,
        duration_ms: int = 0,
        candidate_count: int = 0,
        error_state: str | None = None,
    ) -> None:
        metrics = {
            "stage_started": True,
            "stage_completed": status == "completed",
            "duration_ms": duration_ms,
            "candidate_count": candidate_count,
            "error_state": error_state,
        }
        self.last_stage_telemetry[stage] = dict(metrics)
        logger.info(
            f"retrieval_{status}",
            extra={
                "event": f"stage_{status}",
                "stage": stage,
                **metrics,
            },
        )
        if self.telemetry_callback is not None:
            self.telemetry_callback(stage, status, dict(metrics))

    @staticmethod
    def _start_daemon(
        target: Callable[[], Any],
        *,
        name: str,
    ) -> tuple[threading.Event, dict[str, Any]]:
        completed = threading.Event()
        result_box: dict[str, Any] = {}

        def run() -> None:
            try:
                result_box["result"] = target()
            except BaseException as exc:
                result_box["error"] = exc
            finally:
                completed.set()

        threading.Thread(target=run, name=name, daemon=True).start()
        return completed, result_box

    def retrieve(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        self.last_stage_telemetry = {}
        operations: dict[
            str, tuple[Retriever, float, threading.Event, dict[str, Any]]
        ] = {}

        def start_search(retriever: Retriever) -> None:
            stage = self._stage_name(retriever.name)
            self._emit_stage(stage, "started")
            started = time.perf_counter()
            candidate_limit = self.candidate_limits.get(retriever.name, top_k)
            completed, result_box = self._start_daemon(
                lambda: retriever.retrieve(query, top_k=candidate_limit),
                name=f"cial-{retriever.name}-retrieval",
            )
            operations[retriever.name] = (
                retriever,
                started,
                completed,
                result_box,
            )

        rankings: dict[str, list[dict[str, Any]]] = {}
        if self.parallel and len(self.retrievers) > 1:
            for retriever in self.retrievers:
                start_search(retriever)
            pending_names = [retriever.name for retriever in self.retrievers]
        else:
            pending_names = []
            for retriever in self.retrievers:
                start_search(retriever)
                pending_names.append(retriever.name)
                fatal_error = self._collect_search(
                    retriever.name, operations, rankings
                )
                if fatal_error is not None:
                    raise fatal_error
            pending_names = []
        fatal_errors: list[BaseException] = []
        for retriever_name in pending_names:
            fatal_error = self._collect_search(
                retriever_name, operations, rankings
            )
            if fatal_error is not None:
                fatal_errors.append(fatal_error)
        if fatal_errors:
            raise fatal_errors[0]

        fusion_started = time.perf_counter()
        self._emit_stage("hybrid_fusion", "started")
        self.last_rankings = {
            name: [dict(result) for result in values]
            for name, values in rankings.items()
        }
        fusion_completed, fusion_box = self._start_daemon(
            lambda: self.fuser.fuse(rankings, limit=top_k),
            name="cial-hybrid-fusion",
        )
        fusion_error: str | None = None
        if not fusion_completed.wait(self.stage_timeouts["hybrid_fusion"]):
            fusion_error = "timeout"
            results = self._partial_ranking(rankings, top_k)
        elif "error" in fusion_box:
            fusion_exception = fusion_box["error"]
            fusion_error = type(fusion_exception).__name__
            if self._is_timeout_error(fusion_exception):
                results = self._partial_ranking(rankings, top_k)
            else:
                self._emit_stage(
                    "hybrid_fusion",
                    "completed",
                    duration_ms=int(
                        (time.perf_counter() - fusion_started) * 1000
                    ),
                    candidate_count=0,
                    error_state=fusion_error,
                )
                raise fusion_exception
        else:
            results = fusion_box["result"]
        self._emit_stage(
            "hybrid_fusion",
            "completed",
            duration_ms=int((time.perf_counter() - fusion_started) * 1000),
            candidate_count=len(results),
            error_state=fusion_error,
        )
        if fusion_error is not None:
            logger.warning(
                "hybrid_fusion_degraded",
                extra={
                    "event": "hybrid_fusion_completed",
                    "error_state": fusion_error,
                    "candidate_count": len(results),
                },
            )
        logger.info(
            "hybrid_retrieval_complete",
            extra={
                "event": "hybrid_retrieval",
                "result_count": len(results),
                "candidate_counts": {
                    name: len(values) for name, values in rankings.items()
                },
            },
        )
        return results

    def _collect_search(
        self,
        retriever_name: str,
        operations: Mapping[
            str, tuple[Retriever, float, threading.Event, dict[str, Any]]
        ],
        rankings: dict[str, list[dict[str, Any]]],
    ) -> BaseException | None:
        _, started, completed, result_box = operations[retriever_name]
        remaining = max(
            0.0,
            self.stage_timeouts[retriever_name]
            - (time.perf_counter() - started),
        )
        error_state: str | None = None
        fatal_error: BaseException | None = None
        results: list[dict[str, Any]] = []
        if not completed.wait(remaining):
            error_state = "timeout"
        elif "error" in result_box:
            retrieval_error = result_box["error"]
            error_state = type(retrieval_error).__name__
            if not self._is_timeout_error(retrieval_error):
                fatal_error = retrieval_error
        else:
            results = result_box["result"]
            rankings[retriever_name] = results
        stage = self._stage_name(retriever_name)
        self._emit_stage(
            stage,
            "completed",
            duration_ms=int((time.perf_counter() - started) * 1000),
            candidate_count=len(results),
            error_state=error_state,
        )
        if error_state is not None:
            logger.warning(
                f"{stage}_degraded",
                extra={
                    "event": f"{stage}_completed",
                    "error_state": error_state,
                    "candidate_count": 0,
                },
            )
        return fatal_error

    @staticmethod
    def _is_timeout_error(error: BaseException) -> bool:
        return isinstance(error, TimeoutError) or "timeout" in type(
            error
        ).__name__.casefold()

    def _partial_ranking(
        self,
        rankings: Mapping[str, list[dict[str, Any]]],
        top_k: int,
    ) -> list[dict[str, Any]]:
        for retriever in self.retrievers:
            available = rankings.get(retriever.name)
            if available:
                return [dict(item) for item in available[:top_k]]
        return []
