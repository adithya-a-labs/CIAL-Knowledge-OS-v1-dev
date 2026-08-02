"""Local and deterministic rerankers for Phase 4 candidate precision."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol, runtime_checkable


def resolve_reranker_device(configured_device: str) -> str:
    """Resolve the default accelerator once without changing explicit CPU use."""

    requested = configured_device.strip().casefold()
    if requested not in {"auto", "cuda"} and not requested.startswith("cuda:"):
        return requested
    try:
        import torch
    except ImportError as exc:
        if requested != "auto":
            raise RuntimeError(
                f"Reranker device '{requested}' requires PyTorch with CUDA support."
            ) from exc
        return "cpu"
    if torch.cuda.is_available():
        if requested == "auto":
            return f"cuda:{torch.cuda.current_device()}"
        if requested == "cuda":
            return f"cuda:{torch.cuda.current_device()}"
        device_index = int(requested.split(":", 1)[1])
        if device_index >= torch.cuda.device_count():
            raise RuntimeError(
                f"Reranker device '{requested}' was requested, but only "
                f"{torch.cuda.device_count()} CUDA device(s) are visible."
            )
        return requested
    if requested != "auto":
        raise RuntimeError(
            f"Reranker device '{requested}' was requested, but CUDA is unavailable."
        )
    return "cpu"


def _print_status(message: str, *, ascii_fallback: str | None = None) -> None:
    """Print a model-loading status without turning display errors into failures.

    ``message`` is the preferred notebook/UTF-8 output and ``ascii_fallback`` is
    used only when the active Windows console cannot encode it. This helper has
    no effect on model loading or reranking outputs; it prevents an optional
    status glyph from making an otherwise successful offline cache load fail.
    """

    try:
        print(message, flush=True)
    except UnicodeEncodeError:
        print(
            ascii_fallback or message.encode("ascii", errors="replace").decode(),
            flush=True,
        )


def _chunk_id(candidate: Mapping[str, Any], position: int) -> str:
    metadata = candidate.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    return str(
        candidate.get("chunk_id")
        or metadata.get("chunk_id")
        or candidate.get("id")
        or position
    )


def _numeric_score(value: Any) -> float:
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, (list, tuple)):
        if not value:
            return 0.0
        value = value[-1]
    return float(value)


@dataclass(frozen=True, slots=True)
class RerankResult:
    """Represent one reranking operation and its measured local latency.

    ``candidates`` contains copies of the input chunks ordered by cross-encoder
    relevance, with ``reranker_score``, ``original_rrf_rank``, and
    ``reranked_rank`` added. ``latency_seconds`` covers model scoring and local
    sorting. No retrieval score is overwritten, which keeps Phase 3 diagnostic
    fields backward compatible.
    """

    candidates: tuple[dict[str, Any], ...]
    latency_seconds: float
    model_name: str


@runtime_checkable
class Reranker(Protocol):
    """Score and reorder a Phase 3 candidate pool for one question.

    Inputs are a question and ordered RRF candidates. The output is a
    :class:`RerankResult`. Implementations must preserve chunk metadata and raw
    retriever scores because dense, BM25, RRF, and cross-encoder values are not
    calibrated to a shared scale and must never be directly averaged.
    """

    def rerank(
        self,
        question: str,
        candidates: Sequence[Mapping[str, Any]],
    ) -> RerankResult:
        """Return scored candidates without mutating the input sequence.

        Implementations receive one question and its post-RRF candidate pool.
        They return preserved Phase 3 fields plus additive reranker ranks,
        scores, model identity, and latency in :class:`RerankResult`.
        """

        ...


class CrossEncoderReranker:
    """Apply an offline SentenceTransformers cross-encoder to RRF candidates.

    ``model_name`` identifies an approved model, ``device`` selects CPU/GPU
    (``"auto"`` delegates to SentenceTransformers), and ``batch_size`` bounds
    scoring batches. Loading always checks the local Hugging Face cache first.
    When ``local_files_only=False`` (the developer default), a cache miss stages
    the model once; ``True`` preserves strict enterprise offline execution.

    The result is a new ranked list with one model score per chunk and measured
    latency. Model loading is lazy so configuration, export-only workflows, and
    tests can construct the pipeline without loading a large model. Phase 3
    candidates and score fields remain unchanged.
    """

    def __init__(
        self,
        model_name: str,
        *,
        device: str = "auto",
        batch_size: int = 16,
        local_files_only: bool = False,
        model: Any | None = None,
    ) -> None:
        if not model_name.strip():
            raise ValueError("model_name must not be blank.")
        if not device.strip():
            raise ValueError("device must not be blank.")
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero.")
        self.model_name = model_name.strip()
        self.configured_device = device.strip()
        self.device = resolve_reranker_device(self.configured_device)
        self.batch_size = batch_size
        self.local_files_only = local_files_only
        self._model = model
        self.load_source: str | None = "injected" if model is not None else None
        self.last_rerank_metrics: dict[str, Any] = {}
        self._gpu_memory_before_load: int | None = None
        self._gpu_memory_after_load: int | None = None
        self._warmed = False
        self._warm_duration_ms: float | None = None
        self._model_load_count = 0

    @property
    def resolved_device(self) -> str:
        """Report the loaded model device rather than the requested alias."""

        model_device = getattr(self._model, "device", None)
        if model_device is None:
            model_device = getattr(getattr(self._model, "model", None), "device", None)
        return str(model_device or self.device)

    @staticmethod
    def _model_dtype(model: Any | None) -> str | None:
        module = getattr(model, "model", model)
        parameters = getattr(module, "parameters", None)
        if not callable(parameters):
            return None
        try:
            return str(next(parameters()).dtype)
        except (StopIteration, TypeError):
            return None

    def _gpu_memory_allocated(self) -> int | None:
        if not self.resolved_device.startswith("cuda"):
            return None
        try:
            import torch

            return int(torch.cuda.memory_allocated(self.resolved_device))
        except (ImportError, RuntimeError, ValueError):
            return None

    def runtime_diagnostics(self) -> dict[str, Any]:
        """Expose only observed model/device state and CUDA allocation."""

        allocated = self._gpu_memory_allocated()
        before = self._gpu_memory_before_load
        after = self._gpu_memory_after_load
        return {
            "reranker_device": self.resolved_device,
            "reranker_dtype": self._model_dtype(self._model),
            "reranker_model_loaded": self._model is not None,
            "reranker_model_load_count": self._model_load_count,
            "reranker_device_configured": self.configured_device,
            "reranker_fallback_reason": (
                "auto_resolved_to_cpu_cuda_unavailable"
                if self.configured_device.casefold() == "auto"
                and self.resolved_device == "cpu"
                else None
            ),
            "reranker_warmed": self._warmed,
            "reranker_warm_duration_ms": self._warm_duration_ms,
            "reranker_gpu_memory": {
                "allocated_bytes": allocated,
                "load_delta_bytes": (
                    max(0, after - before)
                    if after is not None and before is not None
                    else None
                ),
            },
            "reranker_batch_size": self.batch_size,
        }

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model

        from sentence_transformers import CrossEncoder

        self._gpu_memory_before_load = self._gpu_memory_allocated()
        model_kwargs = {
            "device": self.device,
        }
        try:
            # Cache-first loading keeps normal runs network-free after the
            # initial staging step and guarantees no network attempt in strict
            # enterprise mode.
            self._model = CrossEncoder(
                self.model_name,
                local_files_only=True,
                **model_kwargs,
            )
            self._model_load_count += 1
            is_local_path = Path(self.model_name).expanduser().exists()
            self.load_source = "local path" if is_local_path else "cache"
            location = (
                "path"
                if is_local_path
                else "Hugging Face cache"
            )
            _print_status(
                f'✓ Reranker model "{self.model_name}" loaded from local '
                f"{location}.",
                ascii_fallback=(
                    f'[OK] Reranker model "{self.model_name}" loaded from local '
                    f"{location}."
                ),
            )
            self._gpu_memory_after_load = self._gpu_memory_allocated()
            return self._model
        except Exception as cache_exc:
            if self.local_files_only:
                print(
                    f'Reranker model "{self.model_name}" was not found in the '
                    "local Hugging Face cache. Download skipped because "
                    "enterprise offline mode is enabled.",
                    flush=True,
                )
                raise RuntimeError(
                    f'Configured reranker model: "{self.model_name}". '
                    "Local-only mode: enabled. The model is missing from the "
                    "local Hugging Face cache and downloads are disabled. "
                    "Stage it on a connected machine with "
                    f"`CrossEncoder({self.model_name!r}, "
                    "local_files_only=False)`, copy the resulting Hugging Face "
                    "cache into the offline environment, or inject "
                    "MockReranker for automated tests."
                ) from cache_exc

        # Developer mode permits one explicit download on a cache miss. Hugging
        # Face persists the files, so subsequent processes take the cache-first
        # path above and remain offline without code changes.
        print(f'Downloading reranker model "{self.model_name}"...', flush=True)
        try:
            self._model = CrossEncoder(
                self.model_name,
                local_files_only=False,
                **model_kwargs,
            )
        except Exception as download_exc:
            raise RuntimeError(
                f'Configured reranker model: "{self.model_name}". '
                "Local-only mode: disabled. The model was not present in the "
                "local Hugging Face cache and the automatic download failed. "
                "Check network/proxy access, or stage it manually with "
                f"`CrossEncoder({self.model_name!r}, "
                "local_files_only=False)`. Use MockReranker for automated "
                "tests that must not access model files or the network."
            ) from download_exc
        self.load_source = "download"
        self._model_load_count += 1
        self._gpu_memory_after_load = self._gpu_memory_allocated()
        _print_status(
            "✓ Reranker downloaded and cached successfully.",
            ascii_fallback="[OK] Reranker downloaded and cached successfully.",
        )
        return self._model

    def load(self) -> Any:
        """Load the configured model now and return the reusable model object.

        Reranking remains lazy for existing API and notebook callers. Terminal
        surfaces can call this additive method to expose model load source and
        duration before question execution begins.
        """

        return self._load_model()

    def warm(self) -> Any:
        """Load the model and initialize its inference path before a query."""

        model = self._load_model()
        if self._warmed:
            return model
        started = perf_counter()
        model.predict(
            [("retrieval readiness", "retrieval readiness")],
            batch_size=1,
            show_progress_bar=False,
            device=self.device,
        )
        self._warm_duration_ms = round(
            (perf_counter() - started) * 1000,
            3,
        )
        self._warmed = True
        return model

    def rerank(
        self,
        question: str,
        candidates: Sequence[Mapping[str, Any]],
    ) -> RerankResult:
        """Score ``(question, chunk text)`` pairs and return descending relevance.

        The question must be non-blank. Candidate dictionaries are copied, so
        callers retain their Phase 3 objects unchanged. Empty input returns an
        empty, zero-latency-compatible result without loading the model.
        """

        if not question.strip():
            raise ValueError("question must not be blank.")
        if not candidates:
            return RerankResult((), 0.0, self.model_name)

        copied = [dict(candidate) for candidate in candidates]
        pairs = [
            (question, str(candidate.get("text") or candidate.get("page_content") or ""))
            for candidate in copied
        ]
        started = perf_counter()
        scores = self._load_model().predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False,
            device=self.device,
        )
        if len(scores) != len(copied):
            raise RuntimeError(
                "Reranker returned a different number of scores than candidates."
            )
        enriched = []
        for original_rank, (candidate, score) in enumerate(
            zip(copied, scores, strict=True),
            start=1,
        ):
            candidate["original_rrf_rank"] = original_rank
            candidate["reranker_score"] = _numeric_score(score)
            enriched.append(candidate)
        enriched.sort(
            key=lambda item: (
                -float(item["reranker_score"]),
                int(item["original_rrf_rank"]),
            )
        )
        for reranked_rank, candidate in enumerate(enriched, start=1):
            candidate["reranked_rank"] = reranked_rank
        result = RerankResult(
            tuple(enriched),
            perf_counter() - started,
            self.model_name,
        )
        self.last_rerank_metrics = {
            **self.runtime_diagnostics(),
            "reranker_batch_size": self.batch_size,
            "reranker_candidate_count": len(copied),
            "reranker_latency_ms": round(result.latency_seconds * 1000, 3),
        }
        return result


class MockReranker:
    """Provide deterministic reranker scores for automated Phase 4 tests.

    ``scores`` may map chunk IDs to numeric values or be a callable receiving a
    candidate and its zero-based position. Missing IDs receive
    ``default_score``. The output matches :class:`CrossEncoderReranker`, which
    lets pipeline and reporting tests exercise real control flow without model
    files, GPU availability, nondeterminism, or network access.
    """

    def __init__(
        self,
        scores: Mapping[str, float]
        | Callable[[Mapping[str, Any], int], float]
        | None = None,
        *,
        default_score: float = 0.0,
        model_name: str = "mock-reranker",
    ) -> None:
        self.scores = scores or {}
        self.default_score = float(default_score)
        self.model_name = model_name
        self.load_source = "mock"

    def rerank(
        self,
        question: str,
        candidates: Sequence[Mapping[str, Any]],
    ) -> RerankResult:
        """Return candidates ordered by deterministic test scores.

        Inputs and outputs follow :class:`Reranker`; latency is measured but no
        external model is loaded. Existing Phase 3 score fields are preserved.
        """

        if not question.strip():
            raise ValueError("question must not be blank.")
        started = perf_counter()
        enriched: list[dict[str, Any]] = []
        for position, value in enumerate(candidates):
            candidate = dict(value)
            if callable(self.scores):
                score = self.scores(candidate, position)
            else:
                score = self.scores.get(
                    _chunk_id(candidate, position),
                    self.default_score,
                )
            candidate["original_rrf_rank"] = position + 1
            candidate["reranker_score"] = float(score)
            enriched.append(candidate)
        enriched.sort(
            key=lambda item: (
                -float(item["reranker_score"]),
                int(item["original_rrf_rank"]),
            )
        )
        for reranked_rank, candidate in enumerate(enriched, start=1):
            candidate["reranked_rank"] = reranked_rank
        return RerankResult(
            tuple(enriched),
            perf_counter() - started,
            self.model_name,
        )
