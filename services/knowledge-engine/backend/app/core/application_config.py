"""Application-level configuration persisted outside source code."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .paths import BACKEND_ROOT, DATA_FILES_ROOT, DATA_ROOT, OUTPUTS_ROOT, REPO_ROOT, resolve_repo_path


APPLICATION_CONFIG_VERSION = 1
DEFAULT_APPLICATION_CONFIG_PATH = DATA_ROOT / "config" / "application.json"
PRIMARY_REPOSITORY_ID = "enterprise"
PRIMARY_REPOSITORY_NAME = "Enterprise Knowledge Repository"


@dataclass(frozen=True, slots=True)
class RepositoryPathValidation:
    path: Path
    exists: bool
    is_directory: bool
    readable: bool
    writable: bool
    valid: bool
    message: str

    def to_dict(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "exists": self.exists,
            "is_directory": self.is_directory,
            "readable": self.readable,
            "writable": self.writable,
            "valid": self.valid,
            "message": self.message,
        }


def application_config_path() -> Path:
    configured = (
        os.getenv("CIAL_APPLICATION_CONFIG")
        or os.getenv("CIAL_APP_CONFIG_FILE")
        or os.getenv("CIAL_CONFIG_FILE")
    )
    if configured and configured.strip():
        return resolve_repo_path(configured.strip())
    return DEFAULT_APPLICATION_CONFIG_PATH.resolve()


def read_application_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or application_config_path()
    if not config_path.is_file():
        return {}
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def repository_identity_for_path(path: str | Path) -> str:
    """Return a stable repository identity derived from the configured location."""

    resolved = resolve_repo_path(path)
    normalized = str(resolved).casefold()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"repo-{digest}"


def _primary_repository_from_config(payload: dict[str, Any]) -> dict[str, Any] | None:
    repositories = payload.get("repositories")
    if isinstance(repositories, list):
        for item in repositories:
            if not isinstance(item, dict):
                continue
            if str(item.get("id") or "") != PRIMARY_REPOSITORY_ID:
                continue
            if item.get("enabled", True) is False:
                continue
            path = str(item.get("path") or "").strip()
            if path:
                return item
        for item in repositories:
            if not isinstance(item, dict) or item.get("enabled", True) is False:
                continue
            path = str(item.get("path") or "").strip()
            if path:
                return item
    legacy_path = str(payload.get("corpus_root") or "").strip()
    if legacy_path:
        return {
            "id": PRIMARY_REPOSITORY_ID,
            "name": PRIMARY_REPOSITORY_NAME,
            "type": "filesystem",
            "path": legacy_path,
            "enabled": True,
            "role": "primary",
        }
    return None


def _repository_path_from_config(payload: dict[str, Any]) -> str | None:
    repository = _primary_repository_from_config(payload)
    if repository is None:
        return None
    path = str(repository.get("path") or "").strip()
    return path or None


def repository_identity_from_config(payload: dict[str, Any], default_path: Path) -> str:
    repository = _primary_repository_from_config(payload)
    if repository is None:
        return repository_identity_for_path(default_path)
    configured = str(repository.get("repository_id") or repository.get("repository_uid") or "").strip()
    if configured:
        return configured
    path = str(repository.get("path") or "").strip()
    return repository_identity_for_path(path or default_path)


def configured_repository_id(default: Path) -> str:
    env_path = os.getenv("CIAL_CORPUS_ROOT") or os.getenv("CORPUS_ROOT")
    if env_path and env_path.strip():
        return repository_identity_for_path(env_path.strip())

    config_path = application_config_path()
    payload = read_application_config(config_path) if config_path.is_file() else {}
    configured = _repository_path_from_config(payload)
    if configured:
        return repository_identity_from_config(payload, resolve_repo_path(configured))

    legacy_path = os.getenv("CIAL_DATA_DIR")
    if legacy_path and legacy_path.strip():
        return repository_identity_for_path(legacy_path.strip())
    return repository_identity_for_path(default)


def configured_corpus_root(default: Path) -> Path:
    env_path = os.getenv("CIAL_CORPUS_ROOT") or os.getenv("CORPUS_ROOT")
    config_path = application_config_path()
    config_value = None
    if config_path.is_file():
        config_value = _repository_path_from_config(read_application_config(config_path))
    if env_path and env_path.strip() and config_value:
        env_resolved = resolve_repo_path(env_path.strip())
        config_resolved = resolve_repo_path(config_value)
        environment = (os.getenv("CIAL_ENV") or os.getenv("ENV") or "development").casefold()
        if env_resolved != config_resolved and environment in {"uat", "production"}:
            raise RuntimeError("Conflicting corpus roots are configured; startup refused.")
    if env_path and env_path.strip():
        return resolve_repo_path(env_path.strip())

    if config_value:
        return resolve_repo_path(config_value)

    legacy_path = os.getenv("CIAL_DATA_DIR")
    if legacy_path and legacy_path.strip():
        return resolve_repo_path(legacy_path.strip())
    return default.resolve()


def repository_config_payload(path: Path) -> dict[str, Any]:
    repository_path = resolve_repo_path(path)
    return {
        "version": APPLICATION_CONFIG_VERSION,
        "repositories": [
            {
                "id": PRIMARY_REPOSITORY_ID,
                "repository_id": repository_identity_for_path(repository_path),
                "name": PRIMARY_REPOSITORY_NAME,
                "type": "filesystem",
                "path": str(repository_path),
                "enabled": True,
                "role": "primary",
            }
        ],
    }


def save_primary_repository_path(path: Path, config_path: Path | None = None) -> Path:
    target = config_path or application_config_path()
    existing = read_application_config(target)
    payload = dict(existing)
    primary = repository_config_payload(path)["repositories"][0]
    repositories = [
        item
        for item in existing.get("repositories", [])
        if isinstance(item, dict) and str(item.get("id") or "") != PRIMARY_REPOSITORY_ID
    ]
    payload["version"] = APPLICATION_CONFIG_VERSION
    payload["repositories"] = [primary, *repositories]
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return target


def validate_repository_path(value: str | Path) -> RepositoryPathValidation:
    path = resolve_repo_path(value)
    exists = path.exists()
    is_directory = path.is_dir()
    readable = False
    writable = False
    message = "Repository path is valid."

    raw_value = str(value).strip()
    if raw_value.startswith("\\\\"):
        return RepositoryPathValidation(path, False, False, False, False, False, "UNC corpus roots are not permitted.")

    configured_allowed = [
        resolve_repo_path(item)
        for item in (os.getenv("CIAL_ALLOWED_CORPUS_ROOTS") or "").split(os.pathsep)
        if item.strip()
    ]
    allowed_roots = [DATA_FILES_ROOT.resolve(), *configured_allowed]
    if not any(path == root or root in path.parents for root in allowed_roots):
        return RepositoryPathValidation(
            path, path.exists(), path.is_dir(), False, False, False,
            "Repository root is outside CIAL_ALLOWED_CORPUS_ROOTS.",
        )

    sensitive_roots = {
        BACKEND_ROOT.resolve(),
        OUTPUTS_ROOT.resolve(),
        (REPO_ROOT / "frontend").resolve(),
        (REPO_ROOT / "scripts").resolve(),
        (REPO_ROOT / ".git").resolve(),
        (REPO_ROOT / "models").resolve(),
        (DATA_ROOT / "config").resolve(),
        (DATA_ROOT / "user-workspaces").resolve(),
        Path.home().resolve(),
    }
    for environment_name in ("WINDIR", "ProgramFiles", "ProgramFiles(x86)", "ProgramData"):
        configured = os.getenv(environment_name)
        if configured:
            sensitive_roots.add(Path(configured).resolve())
    if any(path == root or path in root.parents or root in path.parents for root in sensitive_roots):
        return RepositoryPathValidation(
            path, path.exists(), path.is_dir(), False, False, False,
            "Repository root overlaps a protected application, workspace, model, configuration, output, home, or system path.",
        )

    if os.name == "nt":
        try:
            for component in [path, *path.parents]:
                if component.exists() and component.stat().st_file_attributes & 0x400:
                    return RepositoryPathValidation(path, True, path.is_dir(), False, False, False, "Repository roots may not traverse Windows reparse points.")
        except (AttributeError, OSError):
            return RepositoryPathValidation(path, path.exists(), path.is_dir(), False, False, False, "Repository path security attributes could not be verified.")

    if not exists:
        return RepositoryPathValidation(
            path=path,
            exists=False,
            is_directory=False,
            readable=False,
            writable=False,
            valid=False,
            message=f"Configured corpus directory does not exist: {path}",
        )
    if not is_directory:
        return RepositoryPathValidation(
            path=path,
            exists=True,
            is_directory=False,
            readable=False,
            writable=False,
            valid=False,
            message=f"Configured corpus path is not a directory: {path}",
        )

    try:
        next(path.iterdir(), None)
        readable = os.access(path, os.R_OK)
    except OSError as exc:
        return RepositoryPathValidation(
            path=path,
            exists=True,
            is_directory=True,
            readable=False,
            writable=False,
            valid=False,
            message=f"Configured corpus directory is not readable: {exc}",
        )

    writable = os.access(path, os.W_OK)
    if not readable:
        message = f"Configured corpus directory is not readable by the service: {path}"
    return RepositoryPathValidation(
        path=path,
        exists=True,
        is_directory=True,
        readable=readable,
        writable=writable,
        valid=readable,
        message=message,
    )
