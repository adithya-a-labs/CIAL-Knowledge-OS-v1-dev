from __future__ import annotations

from types import SimpleNamespace

from cial_knowledge_os.llm import OllamaGenerationAdapter


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


def test_ollama_stream_uses_keep_alive_and_retains_native_metrics():
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
    assert adapter.last_generation_metrics["first_token_ms"] is not None
