"""Administration settings routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from backend.app.core.application_config import (
    PRIMARY_REPOSITORY_NAME,
    application_config_path,
    save_primary_repository_path,
    validate_repository_path,
)
from backend.app.core.config import set_runtime_corpus_root, settings
from backend.app.db.session import SessionLocal
from backend.app.schemas.settings import (
    EnterpriseRepositoryRequest,
    EnterpriseRepositoryResponse,
)
from backend.app.security.access import can_manage_settings, resolve_access_context
from backend.app.services.document_service import DocumentService
from cial_knowledge_os.corpus.service import CorpusService

router = APIRouter()


def _response(folder: str) -> EnterpriseRepositoryResponse:
    validation = validate_repository_path(folder)
    return EnterpriseRepositoryResponse(
        name=PRIMARY_REPOSITORY_NAME,
        folder=str(validation.path),
        config_path=str(application_config_path()),
        exists=validation.exists,
        is_directory=validation.is_directory,
        readable=validation.readable,
        writable=validation.writable,
        valid=validation.valid,
        message=validation.message,
    )


@router.get("/settings/enterprise-repository", response_model=EnterpriseRepositoryResponse)
def get_enterprise_repository() -> EnterpriseRepositoryResponse:
    return _response(str(settings.corpus_root_path))


@router.post("/settings/enterprise-repository/validate", response_model=EnterpriseRepositoryResponse)
def validate_enterprise_repository(
    payload: EnterpriseRepositoryRequest,
) -> EnterpriseRepositoryResponse:
    return _response(payload.folder)


@router.put("/settings/enterprise-repository", response_model=EnterpriseRepositoryResponse)
def save_enterprise_repository(
    payload: EnterpriseRepositoryRequest,
    request: Request,
) -> EnterpriseRepositoryResponse:
    access_context = resolve_access_context(request)
    if not can_manage_settings(access_context):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to manage application settings.",
        )

    validation = validate_repository_path(payload.folder)
    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation.message,
        )

    save_primary_repository_path(validation.path)
    set_runtime_corpus_root(validation.path)

    corpus_service = CorpusService(
        root=settings.corpus_root_path,
        session_factory=SessionLocal,
        hash_algorithm=settings.corpus_hash,
        batch_size=settings.metadata_batch_size,
        repository_id=settings.corpus_repository_id,
    )
    request.app.state.corpus_service = corpus_service
    request.app.state.document_service = DocumentService(root=settings.corpus_root_path)
    if hasattr(request.app.state, "indexing_worker"):
        request.app.state.indexing_worker.corpus_sync = corpus_service.sync
    if hasattr(request.app.state, "runtime_state"):
        request.app.state.runtime_state.update(
            engine_ready=False,
            index_fresh=False,
            message=(
                "Enterprise repository setting saved. "
                "Run Corpus Sync or Rebuild Index to apply repository contents."
            ),
        )

    return _response(str(settings.corpus_root_path))
