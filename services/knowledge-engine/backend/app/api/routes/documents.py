"""Document routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session
import logging
import uuid

from backend.app.db.session import get_db_session
from backend.app.models.knowledge import Document
from backend.app.models.operations import IndexingJob
from backend.app.schemas.documents import DocumentIndexingStatus, DocumentListResponse, DocumentMetadata, UploadResponse
from backend.app.security.access import apply_document_access_filter, can_upload_enterprise_documents, require_authenticated_access_context, resolve_access_context
from backend.app.services.indexing_retry_service import IndexingRetryError, IndexingRetryService

router = APIRouter()
logger = logging.getLogger(__name__)


def _indexing_status(document: Document, job: IndexingJob | None, *, retry_permitted: bool = True) -> DocumentIndexingStatus:
    status_value = "indexed" if document.indexed and document.indexing_status == "indexed" else document.indexing_status
    if status_value not in {"pending", "indexing", "indexed", "failed", "deleted"}: status_value = "failed"
    safe_message = None
    metadata = document.metadata_ or {}
    if status_value == "pending": safe_message = "Queued for preparation."
    elif status_value == "indexing": safe_message = "Preparing this file for grounded generation."
    elif status_value == "failed": safe_message = str(metadata.get("indexing_safe_message") or "Preparation failed. You can retry this file.")
    return DocumentIndexingStatus(document_id=document.id, document_version_id=document.current_version_id,
        name=document.name, indexing_status=status_value, indexing_stage=(job.metadata_ or {}).get("stage") if job else None,
        indexing_safe_message=safe_message, indexing_updated_at=(job.updated_at if job else document.updated_at),
        indexing_error_code=str(metadata.get("indexing_error_code")) if metadata.get("indexing_error_code") else None,
        retry_allowed=retry_permitted and status_value == "failed" and metadata.get("indexing_retry_allowed", True) is not False)


@router.get("/documents/{document_id}/indexing-status", response_model=DocumentIndexingStatus)
def document_indexing_status(document_id: uuid.UUID, request: Request, db: Session = Depends(get_db_session)) -> DocumentIndexingStatus:
    access = require_authenticated_access_context(request)
    document = db.scalar(apply_document_access_filter(select(Document).where(Document.id == document_id), access))
    if document is None: raise HTTPException(status_code=404, detail="Document not found.")
    job = db.scalar(select(IndexingJob).where(IndexingJob.document_version_id == document.current_version_id).order_by(IndexingJob.created_at.desc()).limit(1)) if document.current_version_id else None
    retry_permitted = document.storage_scope == "personal" or can_upload_enterprise_documents(access)
    return _indexing_status(document, job, retry_permitted=retry_permitted)


@router.post("/documents/{document_id}/retry-indexing", response_model=DocumentIndexingStatus)
def retry_document_indexing(document_id: uuid.UUID, request: Request, db: Session = Depends(get_db_session)) -> DocumentIndexingStatus:
    access = require_authenticated_access_context(request)
    worker = getattr(request.app.state, "indexing_worker", None)
    if worker is None:
        raise HTTPException(status_code=503, detail={"code": "indexing_retry_enqueue_failed", "message": "Indexing is temporarily unavailable. Please retry shortly."})
    try:
        result = IndexingRetryService(db).retry(document_id, access)
    except IndexingRetryError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    if not result.deduplicated:
        try:
            worker.enqueue(result.job.id)
        except Exception:
            logger.exception("index_retry_enqueue_failed", extra={"event": "index_retry_enqueue_failed", "document_id": str(document_id), "job_id": str(result.job.id)})
            # The durable pending row remains recoverable by the worker's normal drain loop.
    return _indexing_status(result.document, result.job)


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(request: Request) -> DocumentListResponse:
    access_context = resolve_access_context(request)
    documents = request.app.state.document_service.list_documents(access_context=access_context)
    return DocumentListResponse(documents=documents)


@router.post("/documents/upload", response_model=UploadResponse)
def upload_document(
    request: Request,
    file: UploadFile = File(...),
) -> UploadResponse:
    """Upload a document and trigger background indexing.

    The file is saved to disk immediately, metadata and an indexing job are
    created via corpus sync, and indexing is queued in the background worker.
    The response returns immediately — the caller can poll ``/api/index/status``
    to track progress.
    """
    corpus_sync = None
    indexing_worker = None
    if hasattr(request.app.state, "corpus_service") and request.app.state.corpus_service is not None:
        corpus_sync = request.app.state.corpus_service.sync
    if hasattr(request.app.state, "indexing_worker") and request.app.state.indexing_worker is not None:
        indexing_worker = request.app.state.indexing_worker
    access_context = resolve_access_context(request)
    if not can_upload_enterprise_documents(access_context):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to upload enterprise documents.",
        )

    return request.app.state.document_service.save_upload_with_indexing(
        file.filename or "upload",
        file.file,
        corpus_sync=corpus_sync,
        indexing_worker=indexing_worker,
        access_context=access_context,
    )
