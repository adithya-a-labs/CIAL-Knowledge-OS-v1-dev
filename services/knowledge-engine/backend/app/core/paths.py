"""Path helpers for the service-local FastAPI backend."""

from __future__ import annotations

from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[3]
REPO_ROOT = SERVICE_ROOT.parent.parent
BACKEND_ROOT = SERVICE_ROOT / "backend"
KNOWLEDGE_ENGINE_ROOT = SERVICE_ROOT
KNOWLEDGE_ENGINE_SRC = KNOWLEDGE_ENGINE_ROOT / "src"
DATA_ROOT = REPO_ROOT / "data"
DATA_FILES_ROOT = DATA_ROOT / "files"
OUTPUTS_ROOT = REPO_ROOT / "outputs"


def resolve_repo_path(value: str | Path) -> Path:
    """Resolve a user/config path from the repository root."""

    path = Path(value).expanduser()
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()
