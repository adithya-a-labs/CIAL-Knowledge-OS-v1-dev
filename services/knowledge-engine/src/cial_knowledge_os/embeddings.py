"""Local Sentence Transformers embedding helpers."""

from __future__ import annotations

import os
from typing import Any

import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from .config import KnowledgeOSConfig


_MODEL_LOAD_COUNT = 0


def _offline_enabled(name: str) -> bool:
    return os.environ.get(name, "1").strip().lower() not in {"0", "false", "no"}


def resolve_embedding_device(configured_device: str) -> str:
    """Resolve auto to the concrete device owned by the current process."""

    configured = str(configured_device or "auto").casefold()
    if configured == "auto":
        return f"cuda:{torch.cuda.current_device()}" if torch.cuda.is_available() else "cpu"
    if configured.startswith("cuda") and not torch.cuda.is_available():
        raise RuntimeError(
            f"Embedding device '{configured}' was requested, but this PyTorch "
            f"build cannot access CUDA (torch={torch.__version__}, "
            f"torch.version.cuda={torch.version.cuda!r}). Install the CUDA-enabled "
            "PyTorch build and verify NVIDIA driver/device visibility."
        )
    if configured == "cuda":
        return f"cuda:{torch.cuda.current_device()}"
    if configured.startswith("cuda:"):
        try:
            device_index = int(configured.split(":", 1)[1])
        except ValueError as exc:
            raise RuntimeError(f"Invalid embedding CUDA device '{configured}'.") from exc
        if device_index >= torch.cuda.device_count():
            raise RuntimeError(
                f"Embedding device '{configured}' was requested, but only "
                f"{torch.cuda.device_count()} CUDA device(s) are visible."
            )
    return configured


def embedding_fallback_reason(configured_device: str, resolved_device: str) -> str | None:
    """Explain the only supported automatic fallback without hiding it."""

    if str(configured_device).casefold() == "auto" and resolved_device == "cpu":
        return "auto_resolved_to_cpu_cuda_unavailable"
    return None


def embedding_runtime_diagnostics(
    model: SentenceTransformer,
    *,
    configured_device: str,
) -> dict[str, Any]:
    """Return measured model/CUDA state for logs and worker telemetry."""

    actual_device = str(getattr(model, "device", "unknown"))
    try:
        model_dtype = str(next(model.parameters()).dtype)
    except (AttributeError, StopIteration, TypeError):
        model_dtype = "unknown"
    device_index: int | None = None
    if actual_device.startswith("cuda") and torch.cuda.is_available():
        device_index = (
            int(actual_device.rsplit(":", 1)[1])
            if ":" in actual_device
            else torch.cuda.current_device()
        )
    return {
        "embedding_device_configured": str(configured_device),
        "embedding_device_actual": actual_device,
        "embedding_device_resolved": actual_device,
        "embedding_fallback_reason": embedding_fallback_reason(
            configured_device,
            actual_device,
        ),
        "embedding_model_load_count": _MODEL_LOAD_COUNT,
        "torch_cuda_available": bool(torch.cuda.is_available()),
        "torch_version": str(torch.__version__),
        "torch_cuda_build": torch.version.cuda,
        "cuda_device_name": (
            torch.cuda.get_device_name(device_index)
            if device_index is not None
            else None
        ),
        "model_device": actual_device,
        "model_dtype": model_dtype,
        "gpu_memory_allocated": (
            int(torch.cuda.memory_allocated(device_index))
            if device_index is not None
            else 0
        ),
        "gpu_memory_reserved": (
            int(torch.cuda.memory_reserved(device_index))
            if device_index is not None
            else 0
        ),
    }


def load_embedding_model(config: KnowledgeOSConfig) -> SentenceTransformer:
    """Load an embedding model from local storage only."""

    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    device = resolve_embedding_device(config.embedding_device)

    print(
        f"Embedding device: {device} "
        f"(TRANSFORMERS_OFFLINE={_offline_enabled('TRANSFORMERS_OFFLINE')}, "
        f"HF_HUB_OFFLINE={_offline_enabled('HF_HUB_OFFLINE')})"
    )
    global _MODEL_LOAD_COUNT
    try:
        model = SentenceTransformer(
            config.embedding_model_name,
            device=device,
            local_files_only=True,
        )
        _MODEL_LOAD_COUNT += 1
        return model
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            f"Embedding model '{config.embedding_model_name}' is not available "
            "in the local Hugging Face cache. Download it on an approved connected "
            "machine, transfer the cache to this host, and retry offline."
        ) from exc


def embed_texts(
    model: SentenceTransformer,
    texts: list[str],
    *,
    batch_size: int = 8,
) -> np.ndarray:
    """Create normalized local embeddings."""

    if isinstance(batch_size, bool) or batch_size <= 0:
        raise ValueError("Embedding batch size must be greater than zero.")
    if not texts:
        dimension = get_embedding_dimension(model)
        return np.empty((0, dimension), dtype=np.float32)
    with torch.inference_mode():
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
    return np.asarray(vectors, dtype=np.float32)


def get_embedding_dimension(model: SentenceTransformer) -> int:
    """Return the model's output vector size."""

    dimension = model.get_sentence_embedding_dimension()
    if dimension is None:
        dimension = int(embed_texts(model, ["dimension probe"]).shape[1])
    return int(dimension)
