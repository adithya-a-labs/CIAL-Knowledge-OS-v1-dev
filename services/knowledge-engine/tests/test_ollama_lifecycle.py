from __future__ import annotations

import sys
from types import SimpleNamespace

from cial_knowledge_os.llm import (
    OllamaGenerationAdapter,
    sanitize_generation_metrics,
)


class _Client:
    def __init__(self) -> None:
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return iter(
            [
                SimpleNamespace(response="hello ", done=False),
                SimpleNamespace(
                    response="world",
                    done=True,
                    done_reason="stop",
                    total_duration=2_000_000_000,
                    load_duration=500_000_000,
                    prompt_eval_duration=300_000_000,
                    prompt_eval_count=120,
                    eval_duration=1_000_000_000,
                    eval_count=20,
                ),
            ]
        )


def test_ollama_stream_uses_keep_alive_and_retains_native_metrics(monkeypatch):
    clock = iter((10.0, 10.75, 12.0))
    monkeypatch.setattr(
        sys.modules[OllamaGenerationAdapter.__module__].time,
        "perf_counter",
        lambda: next(clock),
    )
    client = _Client()
    adapter = OllamaGenerationAdapter(
        model="fixture",
        timeout=120,
        keep_alive="30m",
        num_gpu=-1,
        client=client,
    )

    assert "".join(adapter.stream("prompt")) == "hello world"
    assert client.calls[0]["keep_alive"] == "30m"
    assert client.calls[0]["options"] == {"temperature": 0, "num_gpu": -1}
    assert adapter.last_generation_metrics["gpu_layers_requested"] == -1
    assert adapter.last_generation_metrics["model_load_ms"] == 500.0
    assert adapter.last_generation_metrics["prompt_tokens"] == 120
    assert adapter.last_generation_metrics["output_tokens"] == 20
    assert adapter.last_generation_metrics["tokens_per_second"] == 20.0
    assert adapter.last_generation_metrics["first_token_ms"] == 750.0
    assert adapter.last_generation_metrics["wall_duration_ms"] == 2000.0


def test_generation_metrics_reject_negative_and_impossible_timings():
    metrics = sanitize_generation_metrics(
        {
            "first_token_ms": 1_758_803,
            "model_load_ms": -1,
            "prompt_eval_ms": float("inf"),
            "ollama_total_ms": 24_000,
            "tokens_per_second": -4,
        },
        generation_duration_ms=24_179,
        request_duration_ms=30_000,
    )

    assert metrics["first_token_ms"] is None
    assert metrics["model_load_ms"] is None
    assert metrics["prompt_eval_ms"] is None
    assert metrics["ollama_total_ms"] == 24_000
    assert metrics["tokens_per_second"] is None


def test_generation_metrics_leave_missing_values_unavailable():
    metrics = sanitize_generation_metrics(
        {},
        generation_duration_ms=500,
        request_duration_ms=700,
    )

    assert metrics["first_token_ms"] is None
    assert metrics["model_load_ms"] is None
    assert metrics["tokens_per_second"] is None


def test_backend_monitor_guard_bounds_timings_by_generation_and_request():
    from backend.app.services.knowledge_engine_service import KnowledgeEngineService

    metrics = KnowledgeEngineService._sanitize_generation_telemetry(
        {
            "first_token_ms": 1_758_803,
            "model_load_ms": 200,
            "prompt_eval_ms": 300,
            "ollama_total_ms": 800,
            "tokens_per_second": 22.5,
        },
        generation_duration_ms=1_000,
        request_duration_ms=900,
    )

    assert metrics["first_token_ms"] is None
    assert metrics["model_load_ms"] == 200
    assert metrics["prompt_eval_ms"] == 300
    assert metrics["ollama_total_ms"] == 800
    assert metrics["tokens_per_second"] == 22.5


def test_new_generation_clears_stale_metrics_before_stream_completion():
    class DelayedClient:
        def generate(self, **kwargs):
            yield SimpleNamespace(response="partial", done=False)
            raise RuntimeError("connection ended before final metrics")

    adapter = OllamaGenerationAdapter(
        model="fixture",
        timeout=120,
        keep_alive="30m",
        client=DelayedClient(),
    )
    adapter.last_generation_metrics = {"first_token_ms": 1_758_803}

    stream = adapter.stream("prompt")
    assert next(stream) == "partial"
    assert adapter.last_generation_metrics == {}
