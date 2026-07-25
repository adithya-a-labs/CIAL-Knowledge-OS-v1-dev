"""Health route."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.app.core.config import settings
from backend.app.db.health import check_database_health
from backend.app.security.access import (
    AccessPrincipal,
    RequestAccessContext,
    require_authenticated_access_context,
    session_user_id_from_request,
)

router = APIRouter()


def require_system_status_access(request: Request) -> RequestAccessContext:
    """Authenticate status without requiring a healthy metadata database."""

    session_user_id = session_user_id_from_request(request)
    if session_user_id is not None:
        return RequestAccessContext(
            principal=AccessPrincipal(
                user_id=session_user_id,
                is_authenticated=True,
            ),
            scope="enterprise",
        )
    return require_authenticated_access_context(request)


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    runtime = request.app.state.runtime_state.snapshot()
    database = check_database_health().as_dict()
    indexing = request.app.state.indexing_service.status()
    return {
        "status": runtime["status"],
        "service": settings.app_name,
        "application_version": "0.1.0",
        "phase": settings.phase,
        "repository_id": settings.corpus_repository_id,
        "qdrant_url": settings.qdrant_url,
        "ollama_model": settings.ollama_model_name,
        "embedding_model": settings.embedding_model_name,
        "reranker_model": settings.reranker_model_name,
        "engine_available": runtime["engine_available"],
        "engine_ready": runtime["engine_ready"],
        "stage": runtime["stage"],
        "knowledge_engine": {
            "status": runtime["status"],
            "ready": runtime["engine_ready"],
            "stage": runtime["stage"],
        },
        "qdrant_ready": runtime["qdrant_ready"],
        "models_ready": runtime["models_ready"],
        "documents_seen": runtime["documents_seen"],
        "documents_indexed": runtime["documents_indexed"],
        "index_fresh": runtime["index_fresh"],
        "message": runtime["message"],
        "watcher_enabled": settings.corpus_watch,
        "watcher_ready": bool(indexing.get("indexer_seen")),
        **indexing,
        **database,
    }


@router.get("/system/status")
def system_status(
    request: Request,
    _access_context: object = Depends(require_system_status_access),
) -> dict[str, object]:
    """Return the authenticated AI Assistant health contract."""

    return request.app.state.system_status_service.snapshot()
