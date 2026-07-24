"""Environment-backed settings for the development API."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re

from .application_config import (
    application_config_path,
    configured_corpus_root,
    configured_repository_id,
    repository_identity_for_path,
)
from .paths import (
    BACKEND_ROOT,
    DATA_ROOT,
    DEFAULT_CORPUS_ROOT,
    OUTPUTS_ROOT,
    REPO_ROOT,
    SERVICE_ROOT,
    resolve_repo_path,
)


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for raw_line in lines:
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


def _env_csv(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    parsed = tuple(item.strip() for item in value.split(",") if item.strip())
    return parsed or default


@dataclass
class Settings:
    app_name: str = "cial-knowledge-os"
    phase: str = "4.5"
    environment: str = _env_str("CIAL_ENV", "ENV", default="development").casefold()
    repo_root: str = str(REPO_ROOT)
    application_config_file: str = str(application_config_path())
    auto_index_on_startup: bool = _env_bool("CIAL_AUTO_INDEX_ON_STARTUP", False)
    force_rebuild_on_startup: bool = _env_bool("CIAL_FORCE_REBUILD_ON_STARTUP", False)
    startup_index_timeout_seconds: int = _env_int("CIAL_STARTUP_INDEX_TIMEOUT_SECONDS", 0)
    app_data_root: str = str(resolve_repo_path(_env_str("CIAL_APP_DATA_DIR", default=str(DATA_ROOT))))
    corpus_root: str = str(configured_corpus_root(DEFAULT_CORPUS_ROOT))
    workspace_root: str = str(resolve_repo_path(_env_str("CIAL_WORKSPACE_ROOT", default="data/user-workspaces")))
    workspace_quota_bytes: int = _env_int("CIAL_WORKSPACE_QUOTA_BYTES", 0)
    corpus_repository_id: str = configured_repository_id(DEFAULT_CORPUS_ROOT)
    outputs_root: str = str(resolve_repo_path(_env_str("CIAL_OUTPUTS_DIR", default=str(OUTPUTS_ROOT))))
    export_root: str = str(resolve_repo_path(_env_str("CIAL_EXPORT_ROOT", default=str(OUTPUTS_ROOT / "exports"))))
    export_ttl_hours: int = _env_int("CIAL_EXPORT_TTL_HOURS", 24)
    export_max_content_bytes: int = _env_int("CIAL_EXPORT_MAX_CONTENT_BYTES", 2_000_000)
    export_queue_limit: int = _env_int("CIAL_EXPORT_QUEUE_LIMIT", 100)
    models_root: str = str(resolve_repo_path(_env_str("CIAL_MODELS_DIR", default="models")))
    cors_origins: tuple[str, ...] = _env_csv("CIAL_CORS_ORIGINS", (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ))
    qdrant_mode: str = _env_str("CIAL_QDRANT_MODE", "QDRANT_MODE", default="server")
    qdrant_url: str = _env_str("CIAL_QDRANT_URL", "QDRANT_URL", default="http://localhost:6335")
    qdrant_collection_name: str = _env_str("CIAL_QDRANT_COLLECTION", default="cial_phase4")
    qdrant_api_key: str | None = _env_str("CIAL_QDRANT_API_KEY", "QDRANT_API_KEY", default="") or None
    qdrant_batch_size: int = _env_int("CIAL_QDRANT_BATCH_SIZE", _env_int("QDRANT_BATCH_SIZE", 32))
    qdrant_upsert_wait: bool = _env_bool("CIAL_QDRANT_UPSERT_WAIT", _env_bool("QDRANT_UPSERT_WAIT", True))
    qdrant_timeout_seconds: float = _env_float("QDRANT_TIMEOUT_SECONDS", 30.0)
    qdrant_retry_attempts: int = _env_int("QDRANT_RETRY_ATTEMPTS", 3)
    qdrant_retry_backoff_seconds: float = _env_float("QDRANT_RETRY_BACKOFF_SECONDS", 2.0)
    qdrant_health_timeout_seconds: float = _env_float("QDRANT_HEALTH_TIMEOUT_SECONDS", 5.0)
    qdrant_query_timeout_seconds: float = _env_float("QDRANT_QUERY_TIMEOUT_SECONDS", 30.0)
    qdrant_upsert_timeout_seconds: float = _env_float("QDRANT_UPSERT_TIMEOUT_SECONDS", 60.0)
    qdrant_delete_timeout_seconds: float = _env_float("QDRANT_DELETE_TIMEOUT_SECONDS", 60.0)
    qdrant_collection_timeout_seconds: float = _env_float("QDRANT_COLLECTION_TIMEOUT_SECONDS", 120.0)
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
    summary_context_window_tokens: int = _env_int("CIAL_SUMMARY_CONTEXT_WINDOW_TOKENS", 8192)
    summary_map_input_tokens: int = _env_int("CIAL_SUMMARY_MAP_INPUT_TOKENS", 4000)
    summary_map_output_tokens: int = _env_int("CIAL_SUMMARY_MAP_OUTPUT_TOKENS", 700)
    summary_reduce_input_tokens: int = _env_int("CIAL_SUMMARY_REDUCE_INPUT_TOKENS", 5000)
    summary_intermediate_output_tokens: int = _env_int("CIAL_SUMMARY_INTERMEDIATE_OUTPUT_TOKENS", 700)
    summary_final_output_tokens: int = _env_int("CIAL_SUMMARY_FINAL_OUTPUT_TOKENS", 1200)
    summary_repair_output_tokens: int = _env_int("CIAL_SUMMARY_REPAIR_OUTPUT_TOKENS", 800)
    summary_checkpoint_retention_days: int = _env_int("CIAL_SUMMARY_CHECKPOINT_RETENTION_DAYS", 14)
    summary_max_document_tokens: int = _env_int("CIAL_SUMMARY_MAX_DOCUMENT_TOKENS", 2_000_000)
    summary_max_chunks: int = _env_int("CIAL_SUMMARY_MAX_CHUNKS", 20_000)
    chat_debug: bool = _env_bool("CIAL_CHAT_DEBUG", False)
    database_url: str = _env_str("DATABASE_URL", default="")
    corpus_sync_on_startup: bool = _env_bool("CIAL_CORPUS_SYNC_ON_STARTUP", False)
    corpus_watch: bool = _env_bool("CIAL_CORPUS_WATCH", True)
    corpus_watch_debounce_ms: int = _env_int("CIAL_CORPUS_WATCH_DEBOUNCE_MS", 750)
    corpus_file_stability_interval_ms: int = _env_int("CIAL_CORPUS_FILE_STABILITY_INTERVAL_MS", 500)
    corpus_file_stability_checks: int = _env_int("CIAL_CORPUS_FILE_STABILITY_CHECKS", 3)
    corpus_reconcile_interval_seconds: int = _env_int("CIAL_CORPUS_RECONCILE_INTERVAL_SECONDS", 300)
    corpus_hash: str = _env_str("CIAL_CORPUS_HASH", default="sha256")
    metadata_batch_size: int = _env_int("CIAL_METADATA_BATCH_SIZE", 500)
    indexer_enabled: bool = _env_bool("CIAL_INDEXER_ENABLED", True)
    indexer_worker_id: str = _env_str("CIAL_INDEXER_WORKER_ID", default="")
    indexer_poll_seconds: float = _env_float("CIAL_INDEXER_POLL_SECONDS", 1.0)
    indexer_lease_seconds: int = _env_int("CIAL_INDEXER_LEASE_SECONDS", 120)
    indexer_heartbeat_seconds: int = _env_int("CIAL_INDEXER_HEARTBEAT_SECONDS", 15)
    indexer_heartbeat_stale_seconds: int = _env_int("CIAL_INDEXER_HEARTBEAT_STALE_SECONDS", 45)
    indexer_max_attempts: int = _env_int("CIAL_INDEXER_MAX_ATTEMPTS", 5)
    indexer_retry_backoff_seconds: float = _env_float("CIAL_INDEXER_RETRY_BACKOFF_SECONDS", 5.0)
    indexer_extraction_workers: int = _env_int(
        "CIAL_INDEXER_EXTRACTION_WORKERS",
        max(1, min(4, (os.cpu_count() or 2) - 1)),
    )
    indexer_prepared_queue_size: int = _env_int("CIAL_INDEXER_PREPARED_QUEUE_SIZE", 8)
    indexer_embed_queue_size: int = _env_int("CIAL_INDEXER_EMBED_QUEUE_SIZE", 4096)
    indexer_write_queue_size: int = _env_int("CIAL_INDEXER_WRITE_QUEUE_SIZE", 16)
    indexer_embed_batch_size: int = _env_int("CIAL_INDEXER_EMBED_BATCH_SIZE", 64)
    indexer_embed_max_batch_tokens: int = _env_int("CIAL_INDEXER_EMBED_MAX_BATCH_TOKENS", 32768)
    indexer_embed_max_wait_ms: int = _env_int("CIAL_INDEXER_EMBED_MAX_WAIT_MS", 75)
    indexer_qdrant_batch_size: int = _env_int("CIAL_INDEXER_QDRANT_BATCH_SIZE", 128)
    indexer_device: str = _env_str("CIAL_INDEXER_DEVICE", default="auto").casefold()
    indexer_precision: str = _env_str("CIAL_INDEXER_PRECISION", default="auto").casefold()
    indexer_gpu_policy: str = _env_str("CIAL_INDEXER_GPU_POLICY", default="balanced").casefold()
    bm25_refresh_debounce_seconds: float = _env_float("CIAL_BM25_REFRESH_DEBOUNCE_SECONDS", 2.0)
    auth_secret_key: str = _env_str(
        "CIAL_AUTH_SECRET_KEY",
        "AUTH_SECRET_KEY",
        default="cial-dev-auth-secret-change-me",
    )
    auth_cookie_name: str = _env_str(
        "CIAL_AUTH_COOKIE_NAME",
        default="cial_auth_session",
    )
    auth_session_ttl_hours: int = _env_int("CIAL_AUTH_SESSION_TTL_HOURS", 168)
    auth_cookie_secure: bool = _env_bool(
        "CIAL_AUTH_COOKIE_SECURE",
        _env_str("CIAL_ENV", "ENV", default="development").casefold() == "production",
    )
    auth_cookie_samesite: str = _env_str("CIAL_AUTH_COOKIE_SAMESITE", default="lax")
    auth_allow_user_headers: bool = _env_bool(
        "CIAL_AUTH_ALLOW_USER_HEADERS",
        _env_str("CIAL_ENV", "ENV", default="development").casefold() != "production",
    )
    auth_default_organization_code: str = _env_str(
        "CIAL_AUTH_DEFAULT_ORGANIZATION_CODE",
        default="CIAL",
    )
    auth_default_role_name: str = _env_str(
        "CIAL_AUTH_DEFAULT_ROLE_NAME",
        default="Viewer",
    )
    auth_default_department_code: str = _env_str(
        "CIAL_AUTH_DEFAULT_DEPARTMENT_CODE",
        default="shared-knowledge",
    )

    def __post_init__(self) -> None:
        positive = {
            "CIAL_INDEXER_POLL_SECONDS": self.indexer_poll_seconds,
            "CIAL_INDEXER_LEASE_SECONDS": self.indexer_lease_seconds,
            "CIAL_INDEXER_HEARTBEAT_SECONDS": self.indexer_heartbeat_seconds,
            "CIAL_INDEXER_HEARTBEAT_STALE_SECONDS": self.indexer_heartbeat_stale_seconds,
            "CIAL_INDEXER_MAX_ATTEMPTS": self.indexer_max_attempts,
            "CIAL_INDEXER_RETRY_BACKOFF_SECONDS": self.indexer_retry_backoff_seconds,
            "CIAL_INDEXER_EXTRACTION_WORKERS": self.indexer_extraction_workers,
            "CIAL_INDEXER_PREPARED_QUEUE_SIZE": self.indexer_prepared_queue_size,
            "CIAL_INDEXER_EMBED_QUEUE_SIZE": self.indexer_embed_queue_size,
            "CIAL_INDEXER_WRITE_QUEUE_SIZE": self.indexer_write_queue_size,
            "CIAL_INDEXER_EMBED_BATCH_SIZE": self.indexer_embed_batch_size,
            "CIAL_INDEXER_EMBED_MAX_BATCH_TOKENS": self.indexer_embed_max_batch_tokens,
            "CIAL_INDEXER_EMBED_MAX_WAIT_MS": self.indexer_embed_max_wait_ms,
            "CIAL_INDEXER_QDRANT_BATCH_SIZE": self.indexer_qdrant_batch_size,
            "CIAL_CORPUS_RECONCILE_INTERVAL_SECONDS": self.corpus_reconcile_interval_seconds,
            "CIAL_CORPUS_WATCH_DEBOUNCE_MS": self.corpus_watch_debounce_ms,
            "CIAL_CORPUS_FILE_STABILITY_INTERVAL_MS": self.corpus_file_stability_interval_ms,
            "CIAL_CORPUS_FILE_STABILITY_CHECKS": self.corpus_file_stability_checks,
            "CIAL_BM25_REFRESH_DEBOUNCE_SECONDS": self.bm25_refresh_debounce_seconds,
            "QDRANT_TIMEOUT_SECONDS": self.qdrant_timeout_seconds,
            "QDRANT_RETRY_ATTEMPTS": self.qdrant_retry_attempts,
            "QDRANT_RETRY_BACKOFF_SECONDS": self.qdrant_retry_backoff_seconds,
            "QDRANT_HEALTH_TIMEOUT_SECONDS": self.qdrant_health_timeout_seconds,
            "QDRANT_QUERY_TIMEOUT_SECONDS": self.qdrant_query_timeout_seconds,
            "QDRANT_UPSERT_TIMEOUT_SECONDS": self.qdrant_upsert_timeout_seconds,
            "QDRANT_DELETE_TIMEOUT_SECONDS": self.qdrant_delete_timeout_seconds,
            "QDRANT_COLLECTION_TIMEOUT_SECONDS": self.qdrant_collection_timeout_seconds,
        }
        invalid = [name for name, value in positive.items() if value <= 0]
        if invalid:
            raise ValueError(f"Continuous-indexing settings must be positive: {', '.join(invalid)}")
        if self.indexer_gpu_policy not in {"max_throughput", "balanced"}:
            raise ValueError("CIAL_INDEXER_GPU_POLICY must be max_throughput or balanced.")
        if self.indexer_precision not in {"auto", "float32", "float16", "bfloat16"}:
            raise ValueError(
                "CIAL_INDEXER_PRECISION must be auto, float32, float16, or bfloat16."
            )
        if not re.fullmatch(r"(?:auto|cpu|cuda(?::\d+)?)", self.indexer_device):
            raise ValueError(
                "CIAL_INDEXER_DEVICE must be auto, cpu, cuda, or cuda:<index>."
            )
        if self.indexer_lease_seconds <= self.indexer_heartbeat_seconds:
            raise ValueError(
                "CIAL_INDEXER_LEASE_SECONDS must exceed CIAL_INDEXER_HEARTBEAT_SECONDS."
            )
        if self.indexer_heartbeat_stale_seconds < self.indexer_heartbeat_seconds * 2:
            raise ValueError(
                "CIAL_INDEXER_HEARTBEAT_STALE_SECONDS must be at least two heartbeat intervals."
            )

    @property
    def repo_path(self) -> Path:
        return Path(self.repo_root)

    @property
    def corpus_root_path(self) -> Path:
        return Path(self.corpus_root)

    @property
    def data_files_path(self) -> Path:
        return self.corpus_root_path

    @property
    def workspace_root_path(self) -> Path:
        return Path(self.workspace_root)

    @property
    def data_files_root(self) -> str:
        return self.corpus_root

    @property
    def data_root_path(self) -> Path:
        return Path(self.app_data_root)

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
    def export_root_path(self) -> Path:
        return Path(self.export_root)

    @property
    def models_path(self) -> Path:
        return Path(self.models_root)


settings = Settings()


def set_runtime_corpus_root(path: str | Path) -> None:
    """Apply a saved repository path to the running process."""

    resolved = resolve_repo_path(path)
    settings.corpus_root = str(resolved)
    settings.corpus_repository_id = repository_identity_for_path(resolved)
