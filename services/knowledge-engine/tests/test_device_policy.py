from __future__ import annotations

import pytest

from backend.app.core.config import Settings


def test_explicit_cpu_indexer_rejects_half_precision() -> None:
    with pytest.raises(ValueError, match="CIAL_INDEXER_PRECISION"):
        Settings(indexer_device="cpu", indexer_precision="fp16")


def test_explicit_cpu_indexer_accepts_float32() -> None:
    configured = Settings(indexer_device="cpu", indexer_precision="fp32")

    assert configured.indexer_device == "cpu"
    assert configured.indexer_precision == "float32"


def test_invalid_reranker_device_is_rejected() -> None:
    with pytest.raises(ValueError, match="CIAL_RERANKER_DEVICE"):
        Settings(reranker_device="gpu")


def test_invalid_ollama_gpu_layer_count_is_rejected() -> None:
    with pytest.raises(ValueError, match="CIAL_OLLAMA_NUM_GPU"):
        Settings(ollama_num_gpu=-2)


def test_local_generation_concurrency_is_one() -> None:
    with pytest.raises(ValueError, match="CIAL_CHAT_GENERATION_CONCURRENCY"):
        Settings(chat_generation_concurrency=2)
