"""Environment-backed settings for the development API."""

from __future__ import annotations

from dataclasses import dataclass
import os

from .paths import DATA_FILES_ROOT, OUTPUTS_ROOT, REPO_ROOT


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return int(value)


@dataclass(frozen=True)
class Settings:
    app_name: str = "cial-knowledge-os"
    phase: str = "4.5"
    repo_root: str = str(REPO_ROOT)
    data_files_root: str = str(DATA_FILES_ROOT)
    outputs_root: str = str(OUTPUTS_ROOT)
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://localhost:3000",
    )
    qdrant_mode: str = os.getenv("QDRANT_MODE", "embedded")
    qdrant_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key: str | None = os.getenv("QDRANT_API_KEY") or None
    qdrant_batch_size: int = _env_int("QDRANT_BATCH_SIZE", 32)
    qdrant_upsert_wait: bool = _env_bool("QDRANT_UPSERT_WAIT", True)
    ollama_model_name: str = os.getenv("OLLAMA_MODEL_NAME", "gemma3:12b")
    embedding_model_name: str = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3")
    reranker_model_name: str = os.getenv(
        "RERANKER_MODEL_NAME",
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
    )
    reranker_local_files_only: bool = _env_bool("RERANKER_LOCAL_FILES_ONLY", False)


settings = Settings()
