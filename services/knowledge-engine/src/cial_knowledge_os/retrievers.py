"""Composable dense, lexical, and hybrid retrieval implementations."""

from __future__ import annotations

import hashlib
import logging
import pickle
import re
import threading
import time
from array import array
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from langchain_core.documents import Document
import numpy as np

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
        self.allowed_document_version_ids: frozenset[str] | None = None
        self.allowed_note_revisions: frozenset[tuple[str, int]] | None = None
        self._allowed_publication_indexes: np.ndarray | None = None
        self._authorized_indexes: OrderedDict[str, np.ndarray] = OrderedDict()
        self._authorized_cache_limit = 16
        self._authorized_lock = threading.RLock()
        self._relative_path_indexes: dict[str, np.ndarray] = {}
        self._publication_identity_indexes: dict[tuple[str, str, int], np.ndarray] = {}
        self._term_postings: dict[str, tuple[array, array]] = {}
        self._document_lengths = np.empty(0, dtype=np.float64)
        self.document_count = 0
        self.last_search_metrics: dict[str, Any] = {}

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

    def set_allowed_publication_identities(
        self,
        document_version_ids: frozenset[str] | None,
        note_revisions: frozenset[tuple[str, int]] | None,
    ) -> None:
        """Restrict lexical candidates to the currently published identities."""

        normalized_versions = (
            None
            if document_version_ids is None
            else frozenset(
                str(value).strip()
                for value in document_version_ids
                if str(value).strip()
            )
        )
        normalized_notes = (
            None
            if note_revisions is None
            else frozenset(
                (str(note_id).strip(), int(revision))
                for note_id, revision in note_revisions
                if str(note_id).strip() and int(revision) > 0
            )
        )
        with self._authorized_lock:
            if (
                normalized_versions == self.allowed_document_version_ids
                and normalized_notes == self.allowed_note_revisions
            ):
                return
            self.allowed_document_version_ids = normalized_versions
            self.allowed_note_revisions = normalized_notes
            if normalized_versions is None and normalized_notes is None:
                self._allowed_publication_indexes = None
                return
            keys = (
                [("document", value, 0) for value in normalized_versions or ()]
                + [
                    ("note", note_id, revision)
                    for note_id, revision in normalized_notes or ()
                ]
            )
            arrays = [
                self._publication_identity_indexes[key]
                for key in keys
                if key in self._publication_identity_indexes
            ]
            self._allowed_publication_indexes = (
                np.unique(np.concatenate(arrays))
                if arrays
                else np.empty(0, dtype=np.int64)
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
            self._relative_path_indexes = {}
            self._publication_identity_indexes = {}
            self._allowed_publication_indexes = None
            self._term_postings = {}
            self._document_lengths = np.empty(0, dtype=np.float64)
            self.document_count = 0
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
        path_indexes: dict[str, list[int]] = {}
        publication_indexes: dict[tuple[str, str, int], list[int]] = {}
        document_ids: set[str] = set()
        for index, chunk in enumerate(normalized):
            metadata = chunk.get("metadata")
            metadata = metadata if isinstance(metadata, Mapping) else {}
            relative_path = self._normalize_relative_path(
                chunk.get("relative_path") or metadata.get("relative_path")
            )
            if relative_path:
                path_indexes.setdefault(relative_path, []).append(index)
            document_version_id = str(
                chunk.get("document_version_id")
                or metadata.get("document_version_id")
                or ""
            ).strip()
            if document_version_id:
                publication_indexes.setdefault(
                    ("document", document_version_id, 0), []
                ).append(index)
            note_id = str(
                chunk.get("note_id") or metadata.get("note_id") or ""
            ).strip()
            note_revision = int(
                chunk.get("note_revision") or metadata.get("note_revision") or 0
            )
            if note_id and note_revision > 0:
                publication_indexes.setdefault(
                    ("note", note_id, note_revision), []
                ).append(index)
            document_id = str(
                chunk.get("document_id") or metadata.get("document_id") or ""
            ).strip()
            if document_id:
                document_ids.add(document_id)
        self._relative_path_indexes = {
            path: np.asarray(indexes, dtype=np.int64)
            for path, indexes in path_indexes.items()
        }
        self._publication_identity_indexes = {
            identity: np.asarray(indexes, dtype=np.int64)
            for identity, indexes in publication_indexes.items()
        }
        # Recompute a previously configured publication boundary for the new corpus.
        configured_versions = self.allowed_document_version_ids
        configured_notes = self.allowed_note_revisions
        self.allowed_document_version_ids = None
        self.allowed_note_revisions = None
        self.set_allowed_publication_identities(configured_versions, configured_notes)
        term_postings: dict[str, tuple[array, array]] = {}
        for index, frequencies in enumerate(self._index.doc_freqs):
            for token, frequency in frequencies.items():
                indexes, counts = term_postings.setdefault(
                    token,
                    (array("I"), array("I")),
                )
                indexes.append(index)
                counts.append(frequency)
        self._term_postings = term_postings
        self._document_lengths = np.asarray(
            self._index.doc_len,
            dtype=np.float64,
        )
        self.document_count = len(document_ids)
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
        started = time.perf_counter()
        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")
        if self._index is None:
            raise RuntimeError(
                "The BM25 index is not initialized. Call index(chunks) before "
                "retrieve()."
            )
        if not self._chunks:
            self.last_search_metrics = {
                "bm25_search_duration_ms": round(
                    (time.perf_counter() - started) * 1000, 3
                ),
                "bm25_candidate_count": 0,
                "document_count": self.document_count,
                "chunk_count": 0,
            }
            return []
        tokens = self.tokenizer(query)
        if not tokens:
            self.last_search_metrics = {
                "bm25_search_duration_ms": round(
                    (time.perf_counter() - started) * 1000, 3
                ),
                "bm25_candidate_count": 0,
                "document_count": self.document_count,
                "chunk_count": len(self._chunks),
            }
            return []
        with self._authorized_lock:
            allowed_relative_paths = self.allowed_relative_paths
            publication_indexes = self._allowed_publication_indexes
        allowed_indexes: np.ndarray | None = None
        if allowed_relative_paths is not None:
            cache_key = hashlib.sha256(
                (self._fingerprint or "").encode()
                + b"\0"
                + "\0".join(sorted(allowed_relative_paths)).encode()
            ).hexdigest()
            with self._authorized_lock:
                cached = self._authorized_indexes.get(cache_key)
            if cached is None:
                arrays = [
                    self._relative_path_indexes[path]
                    for path in allowed_relative_paths
                    if path in self._relative_path_indexes
                ]
                allowed_indexes = (
                    np.sort(np.concatenate(arrays))
                    if arrays
                    else np.empty(0, dtype=np.int64)
                )
                with self._authorized_lock:
                    self._authorized_indexes[cache_key] = allowed_indexes
                    self._authorized_indexes.move_to_end(cache_key)
                    while len(self._authorized_indexes) > self._authorized_cache_limit:
                        self._authorized_indexes.popitem(last=False)
            else:
                allowed_indexes = cached
                with self._authorized_lock:
                    self._authorized_indexes.move_to_end(cache_key)
            if allowed_indexes.size == 0:
                self.last_search_metrics = {
                    "bm25_search_duration_ms": round(
                        (time.perf_counter() - started) * 1000, 3
                    ),
                    "bm25_candidate_count": 0,
                    "document_count": self.document_count,
                    "chunk_count": len(self._chunks),
                }
                return []
        if publication_indexes is not None:
            allowed_indexes = (
                publication_indexes
                if allowed_indexes is None
                else np.intersect1d(
                    allowed_indexes,
                    publication_indexes,
                    assume_unique=True,
                )
            )
            if allowed_indexes.size == 0:
                self.last_search_metrics = {
                    "bm25_search_duration_ms": round(
                        (time.perf_counter() - started) * 1000, 3
                    ),
                    "bm25_candidate_count": 0,
                    "document_count": self.document_count,
                    "chunk_count": len(self._chunks),
                }
                return []
        scores = np.zeros(len(self._chunks), dtype=np.float64)
        average_document_length = float(self._index.avgdl)
        for token in tokens:
            posting = self._term_postings.get(token)
            if posting is None:
                continue
            posting_indexes = np.frombuffer(posting[0], dtype=np.uint32)
            frequencies = np.frombuffer(posting[1], dtype=np.uint32)
            idf = float(self._index.idf.get(token) or 0.0)
            denominator = frequencies + self.k1 * (
                1.0
                - self.b
                + self.b
                * self._document_lengths[posting_indexes]
                / average_document_length
            )
            scores[posting_indexes] += (
                idf * frequencies * (self.k1 + 1.0) / denominator
            )
        candidate_indexes = (
            np.flatnonzero(scores != 0)
            if allowed_indexes is None
            else allowed_indexes[scores[allowed_indexes] != 0]
        )
        effective_scores = scores[candidate_indexes].copy()
        for offset in np.flatnonzero(effective_scores <= 0):
            index = int(candidate_indexes[offset])
            overlap = len(
                set(tokens).intersection(self._tokenized_corpus[index])
            )
            effective_scores[offset] = (
                overlap / max(len(set(tokens)), 1) * 1e-6
                if overlap > 0
                else 0
            )
        positive = effective_scores > 0
        candidate_indexes = candidate_indexes[positive]
        effective_scores = effective_scores[positive]
        if (
            candidate_indexes.size == 0
            and allowed_indexes is not None
            and allowed_indexes.size <= 10_000
        ):
            fallback_indexes: list[int] = []
            fallback_scores: list[float] = []
            query_tokens = set(tokens)
            for value in allowed_indexes:
                index = int(value)
                overlap = len(query_tokens.intersection(self._tokenized_corpus[index]))
                if overlap > 0:
                    fallback_indexes.append(index)
                    fallback_scores.append(
                        overlap / max(len(query_tokens), 1) * 1e-6
                    )
            candidate_indexes = np.asarray(fallback_indexes, dtype=np.int64)
            effective_scores = np.asarray(fallback_scores, dtype=np.float64)
        if candidate_indexes.size > top_k:
            threshold = np.partition(effective_scores, -top_k)[-top_k]
            selected = effective_scores >= threshold
            candidate_indexes = candidate_indexes[selected]
            effective_scores = effective_scores[selected]
        order = np.lexsort((candidate_indexes, -effective_scores))
        ranked_indexes = candidate_indexes[order][:top_k]
        ranked_scores = effective_scores[order][:top_k]
        results: list[dict[str, Any]] = []
        for index, score_value in zip(ranked_indexes, ranked_scores, strict=True):
            score = float(score_value)
            result = dict(self._chunks[int(index)])
            result.update(
                {
                    "score": score,
                    "retrieval_sources": [self.name],
                    "retrieval_ranks": {self.name: len(results) + 1},
                    "retrieval_scores": {self.name: score},
                }
            )
            results.append(result)
        duration_ms = round((time.perf_counter() - started) * 1000, 3)
        self.last_search_metrics = {
            "bm25_search_duration_ms": duration_ms,
            "bm25_candidate_count": len(results),
            "document_count": self.document_count,
            "chunk_count": len(self._chunks),
        }
        logger.info(
            "bm25_retrieval_complete",
            extra={
                "event": "bm25_retrieval",
                "result_count": len(results),
                **self.last_search_metrics,
            },
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
        extra_metrics: Mapping[str, Any] | None = None,
    ) -> None:
        metrics = {
            "stage_started": True,
            "stage_completed": status == "completed",
            "duration_ms": duration_ms,
            "candidate_count": candidate_count,
            "error_state": error_state,
            **dict(extra_metrics or {}),
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
                result_box["completed_at"] = time.perf_counter()
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
            parallel_started = time.perf_counter()
            branch_names = {retriever.name for retriever in self.retrievers}
            self._emit_stage(
                "parallel_retrieval",
                "started",
                extra_metrics={
                    "dense_started": "dense" in branch_names,
                    "dense_completed": False,
                    "bm25_started": "bm25" in branch_names,
                    "bm25_completed": False,
                    "parallel_retrieval_duration_ms": 0,
                },
            )
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
        if self.parallel and len(self.retrievers) > 1:
            parallel_duration_ms = int(
                (time.perf_counter() - parallel_started) * 1000
            )
            self._emit_stage(
                "parallel_retrieval",
                "completed",
                duration_ms=parallel_duration_ms,
                candidate_count=sum(len(values) for values in rankings.values()),
                extra_metrics={
                    "dense_started": "dense" in branch_names,
                    "dense_completed": (
                        "dense" not in branch_names
                        or operations["dense"][2].is_set()
                    ),
                    "bm25_started": "bm25" in branch_names,
                    "bm25_completed": (
                        "bm25" not in branch_names
                        or operations["bm25"][2].is_set()
                    ),
                    "parallel_retrieval_duration_ms": parallel_duration_ms,
                },
            )

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
        retriever, started, completed, result_box = operations[retriever_name]
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
            duration_ms=int(
                (
                    float(result_box.get("completed_at") or time.perf_counter())
                    - started
                )
                * 1000
            ),
            candidate_count=len(results),
            error_state=error_state,
            extra_metrics=(
                getattr(retriever, "last_search_metrics", {})
                if retriever_name == "bm25"
                else None
            ),
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
