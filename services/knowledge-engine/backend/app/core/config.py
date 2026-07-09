"""Environment-backed settings for the development API."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from .paths import (
    BACKEND_ROOT,
    DATA_FILES_ROOT,
    OUTPUTS_ROOT,
    REPO_ROOT,
    SERVICE_ROOT,
    resolve_repo_path,
)


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        if not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def _load_env_files() -> None:
    """Load repo/service/backend .env files without overriding the shell."""

    original_environment = set(os.environ)
    loaded: dict[str, str] = {}
    for path in (REPO_ROOT / ".env", SERVICE_ROOT / ".env", BACKEND_ROOT / ".env"):
        loaded.update(_parse_env_file(path))
    for key, value in loaded.items():
        if key not in original_environment:
            os.environ[key] = value


_load_env_files()


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


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)


def _env_str(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip()
    return default


@dataclass(frozen=True)
class Settings:
    app_name: str = "cial-knowledge-os"
    phase: str = "4.5"
    repo_root: str = str(REPO_ROOT)
    auto_index_on_startup: bool = _env_bool("CIAL_AUTO_INDEX_ON_STARTUP", True)
    force_rebuild_on_startup: bool = _env_bool("CIAL_FORCE_REBUILD_ON_STARTUP", False)
    startup_index_timeout_seconds: int = _env_int("CIAL_STARTUP_INDEX_TIMEOUT_SECONDS", 0)
    data_files_root: str = str(resolve_repo_path(_env_str("CIAL_DATA_DIR", default=str(DATA_FILES_ROOT))))
    outputs_root: str = str(resolve_repo_path(_env_str("CIAL_OUTPUTS_DIR", default=str(OUTPUTS_ROOT))))
    models_root: str = str(resolve_repo_path(_env_str("CIAL_MODELS_DIR", default="models")))
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )
    qdrant_mode: str = _env_str("CIAL_QDRANT_MODE", "QDRANT_MODE", default="server")
    qdrant_url: str = _env_str("CIAL_QDRANT_URL", "QDRANT_URL", default="http://localhost:6335")
    qdrant_api_key: str | None = _env_str("CIAL_QDRANT_API_KEY", "QDRANT_API_KEY", default="") or None
    qdrant_batch_size: int = _env_int("CIAL_QDRANT_BATCH_SIZE", _env_int("QDRANT_BATCH_SIZE", 32))
    qdrant_upsert_wait: bool = _env_bool("CIAL_QDRANT_UPSERT_WAIT", _env_bool("QDRANT_UPSERT_WAIT", True))
    ollama_model_name: str = _env_str("CIAL_OLLAMA_MODEL_NAME", "OLLAMA_MODEL_NAME", default="gemma3:12b")
    embedding_model_name: str = _env_str("CIAL_EMBEDDING_MODEL_NAME", "EMBEDDING_MODEL_NAME", default="BAAI/bge-m3")
    reranker_model_name: str = _env_str(
        "CIAL_RERANKER_MODEL_NAME",
        "RERANKER_MODEL_NAME",
        default="cross-encoder/ms-marco-MiniLM-L-6-v2",
    )
    reranker_device: str = _env_str("CIAL_RERANKER_DEVICE", default="auto")
    reranker_batch_size: int = _env_int("CIAL_RERANKER_BATCH_SIZE", 16)
    reranker_local_files_only: bool = _env_bool(
        "CIAL_LOCAL_FILES_ONLY",
        _env_bool("RERANKER_LOCAL_FILES_ONLY", False),
    )
    max_answer_words: int = _env_int("CIAL_MAX_ANSWER_WORDS", 1200)
    generation_retries: int = _env_int("CIAL_GENERATION_RETRIES", 2)
    retry_cooldown_seconds: float = _env_float("CIAL_RETRY_COOLDOWN_SECONDS", 20.0)
    database_url: str = _env_str("DATABASE_URL", default="")
    corpus_sync_on_startup: bool = _env_bool("CIAL_CORPUS_SYNC_ON_STARTUP", True)
    corpus_watch: bool = _env_bool("CIAL_CORPUS_WATCH", False)
    corpus_hash: str = _env_str("CIAL_CORPUS_HASH", default="sha256")
    metadata_batch_size: int = _env_int("CIAL_METADATA_BATCH_SIZE", 500)

    @property
    def repo_path(self) -> Path:
        return Path(self.repo_root)

    @property
    def data_files_path(self) -> Path:
        return Path(self.data_files_root)

    @property
    def data_root_path(self) -> Path:
        return self.data_files_path.parent

    @property
    def indexes_path(self) -> Path:
        return self.data_root_path / "indexes"

    @property
    def bm25_path(self) -> Path:
        return self.data_root_path / "bm25"

    @property
    def outputs_path(self) -> Path:
        return Path(self.outputs_root)

    @property
    def models_path(self) -> Path:
        return Path(self.models_root)


settings = Settings()
