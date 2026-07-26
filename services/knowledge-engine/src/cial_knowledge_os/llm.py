"""Grounded generation through a local Ollama runtime."""

from __future__ import annotations

import math
import time
from typing import Any, Iterator, Protocol

from httpx import HTTPError
from ollama import Client, ResponseError

from .config import KnowledgeOSConfig
from .prompts import DEFAULT_PROMPT_MANAGER

PHASE1_NO_EVIDENCE_RESPONSE = DEFAULT_PROMPT_MANAGER.get(
    "evaluation.phase1_no_evidence"
).text


def valid_milliseconds(
    value: Any,
    *,
    maximum: float | None = None,
) -> float | None:
    """Return a finite, non-negative millisecond duration within its boundary."""

    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed < 0:
        return None
    if maximum is not None and parsed > maximum:
        return None
    return round(parsed, 3)


def sanitize_generation_metrics(
    metrics: dict[str, Any],
    *,
    generation_duration_ms: float,
    request_duration_ms: float | None = None,
) -> dict[str, Any]:
    """Reject impossible generation timings without manufacturing replacements."""

    sanitized = dict(metrics)
    generation_maximum = valid_milliseconds(generation_duration_ms)
    request_maximum = valid_milliseconds(request_duration_ms)
    if generation_maximum is None:
        generation_maximum = 0.0
    maximum = (
        min(generation_maximum, request_maximum)
        if request_maximum is not None
        else generation_maximum
    )
    for key in (
        "first_token_ms",
        "model_load_ms",
        "prompt_eval_ms",
        "ollama_total_ms",
        "wall_duration_ms",
    ):
        sanitized[key] = valid_milliseconds(
            sanitized.get(key),
            maximum=maximum,
        )
    tokens_per_second = sanitized.get("tokens_per_second")
    try:
        parsed_rate = float(tokens_per_second)
    except (TypeError, ValueError):
        parsed_rate = 0.0
    sanitized["tokens_per_second"] = (
        round(parsed_rate, 3)
        if math.isfinite(parsed_rate) and parsed_rate > 0
        else None
    )
    return sanitized


class GenerationFailedError(RuntimeError):
    """Report an exhausted Phase 4 generation attempt without losing its cause.

    Inputs are the original exception and total attempt count. The raised error
    exposes the original type/message for batch row metadata and chains the
    source exception for full logs. Earlier phases do not use this exception;
    it is raised only by the Phase 4 retry boundary.
    """

    def __init__(self, original: Exception, *, attempts: int) -> None:
        self.original_error_type = type(original).__name__
        self.original_error_message = str(original)
        self.attempts = attempts
        super().__init__(
            f"{self.original_error_type}: {self.original_error_message} "
            f"(generation attempts: {attempts})"
        )


class LocalLLM(Protocol):
    """Minimal interface implemented by supported local inference adapters."""

    def invoke(self, prompt: str) -> Any: ...


class OllamaGenerationAdapter:
    """Ollama adapter that retains native generation performance metrics."""

    def __init__(
        self,
        *,
        model: str,
        timeout: float,
        keep_alive: str,
        num_gpu: int = -1,
        client: Client | None = None,
    ) -> None:
        self.model = model
        self.keep_alive = keep_alive
        self.num_gpu = num_gpu
        self.client = client or Client(timeout=timeout)
        self.last_generation_metrics: dict[str, Any] = {}

    @staticmethod
    def _milliseconds(value: Any) -> float | None:
        if value is None:
            return None
        try:
            milliseconds = float(value) / 1_000_000
        except (TypeError, ValueError):
            return None
        return valid_milliseconds(milliseconds)

    def _complete_metrics(
        self,
        response: Any,
        *,
        started: float,
        first_token_at: float | None,
    ) -> None:
        completed_at = time.perf_counter()
        wall_duration_ms = round((completed_at - started) * 1000, 3)
        output_tokens = int(getattr(response, "eval_count", 0) or 0)
        eval_duration = int(getattr(response, "eval_duration", 0) or 0)
        metrics = {
            "model": self.model,
            "keep_alive": self.keep_alive,
            "gpu_layers_requested": self.num_gpu,
            "wall_duration_ms": wall_duration_ms,
            "model_load_ms": self._milliseconds(
                getattr(response, "load_duration", None)
            ),
            "prompt_eval_ms": self._milliseconds(
                getattr(response, "prompt_eval_duration", None)
            ),
            "ollama_total_ms": self._milliseconds(
                getattr(response, "total_duration", None)
            ),
            "first_token_ms": (
                round((first_token_at - started) * 1000, 3)
                if first_token_at is not None
                else None
            ),
            "prompt_tokens": int(getattr(response, "prompt_eval_count", 0) or 0),
            "output_tokens": output_tokens,
            "tokens_per_second": (
                round(output_tokens / (eval_duration / 1_000_000_000), 3)
                if output_tokens and eval_duration > 0
                else None
            ),
            "done_reason": getattr(response, "done_reason", None),
        }
        self.last_generation_metrics = sanitize_generation_metrics(
            metrics,
            generation_duration_ms=wall_duration_ms,
        )

    def stream(self, prompt: str) -> Iterator[str]:
        started = time.perf_counter()
        first_token_at: float | None = None
        final_response: Any | None = None
        self.last_generation_metrics = {}
        responses = self.client.generate(
            model=self.model,
            prompt=prompt,
            stream=True,
            options={"temperature": 0, "num_gpu": self.num_gpu},
            keep_alive=self.keep_alive,
        )
        for response in responses:
            final_response = response
            value = str(getattr(response, "response", "") or "")
            if value and first_token_at is None:
                first_token_at = time.perf_counter()
            if value:
                yield value
        if final_response is not None:
            self._complete_metrics(
                final_response,
                started=started,
                first_token_at=first_token_at,
            )

    def invoke(self, prompt: str) -> str:
        started = time.perf_counter()
        self.last_generation_metrics = {}
        response = self.client.generate(
            model=self.model,
            prompt=prompt,
            stream=False,
            options={"temperature": 0, "num_gpu": self.num_gpu},
            keep_alive=self.keep_alive,
        )
        self._complete_metrics(
            response,
            started=started,
            first_token_at=None,
        )
        return str(getattr(response, "response", "") or "")


def create_local_llm(config: KnowledgeOSConfig) -> OllamaGenerationAdapter:
    """Validate and create a deterministic local Ollama model interface."""

    try:
        timeout = float(getattr(config, "generation_timeout_seconds", 120.0))
        availability_timeout = min(5.0, timeout)
        available_models = {
            model.model
            for model in Client(timeout=availability_timeout).list().models
            if model.model is not None
        }
    except (HTTPError, OSError, ResponseError) as exc:
        raise RuntimeError(
            "The local Ollama service is unavailable. Start Ollama and confirm "
            f"that the configured model '{config.ollama_model_name}' is installed."
        ) from exc

    if config.ollama_model_name not in available_models:
        raise RuntimeError(
            f"Configured Ollama model '{config.ollama_model_name}' is not installed "
            "locally. Install or transfer that model, or change "
            "KnowledgeOSConfig.ollama_model_name. No model was downloaded."
        )

    return OllamaGenerationAdapter(
        model=config.ollama_model_name,
        timeout=timeout,
        keep_alive=str(getattr(config, "ollama_keep_alive", "30m")),
        num_gpu=int(getattr(config, "ollama_num_gpu", -1)),
    )


def build_grounded_prompt(
    question: str,
    context: str,
    *,
    no_evidence_response: str = PHASE1_NO_EVIDENCE_RESPONSE,
) -> str:
    """Build a strict grounded prompt that requires direct evidence."""

    return DEFAULT_PROMPT_MANAGER.render(
        "generation.grounded_qa",
        no_evidence_response=no_evidence_response,
        context=context,
        question=question,
    )


def generate_answer(
    llm: LocalLLM,
    question: str,
    context: str,
    *,
    no_evidence_response: str = PHASE1_NO_EVIDENCE_RESPONSE,
) -> str:
    """Generate a grounded answer using the configured local runtime."""

    if not context.strip():
        return no_evidence_response
    prompt = build_grounded_prompt(
        question,
        context,
        no_evidence_response=no_evidence_response,
    )
    return str(llm.invoke(prompt)).strip()
