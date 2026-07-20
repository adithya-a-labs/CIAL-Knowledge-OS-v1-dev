"""Document routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import uuid

from backend.app.db.session import get_db_session
from backend.app.models.knowledge import Document, DocumentVersion
from backend.app.models.operations import IndexingJob
from backend.app.schemas.documents import DocumentIndexingStatus, DocumentListResponse, DocumentMetadata, UploadResponse
from backend.app.security.access import apply_document_access_filter, can_upload_enterprise_documents, require_authenticated_access_context, resolve_access_context

router = APIRouter()


def _indexing_status(document: Document, job: IndexingJob | None) -> DocumentIndexingStatus:
    status_value = "indexed" if document.indexed and document.indexing_status == "indexed" else document.indexing_status
    if status_value not in {"pending", "indexing", "indexed", "failed", "deleted"}: status_value = "failed"
    safe_message = None
    if status_value == "pending": safe_message = "Queued for preparation."
    elif status_value == "indexing": safe_message = "Preparing this file for grounded generation."
    elif status_value == "failed": safe_message = "Preparation failed. You can retry this file."
    return DocumentIndexingStatus(document_id=document.id, document_version_id=document.current_version_id,
        name=document.name, indexing_status=status_value, indexing_stage=(job.metadata_ or {}).get("stage") if job else None,
        indexing_safe_message=safe_message, indexing_updated_at=(job.updated_at if job else document.updated_at),
        retry_allowed=status_value == "failed")


@router.get("/documents/{document_id}/indexing-status", response_model=DocumentIndexingStatus)
def document_indexing_status(document_id: uuid.UUID, request: Request, db: Session = Depends(get_db_session)) -> DocumentIndexingStatus:
    access = require_authenticated_access_context(request)
    document = db.scalar(apply_document_access_filter(select(Document).where(Document.id == document_id), access))
    if document is None: raise HTTPException(status_code=404, detail="Document not found.")
    job = db.scalar(select(IndexingJob).where(IndexingJob.document_version_id == document.current_version_id).order_by(IndexingJob.created_at.desc()).limit(1)) if document.current_version_id else None
    return _indexing_status(document, job)


@router.post("/documents/{document_id}/retry-indexing", response_model=DocumentIndexingStatus)
def retry_document_indexing(document_id: uuid.UUID, request: Request, db: Session = Depends(get_db_session)) -> DocumentIndexingStatus:
    access = require_authenticated_access_context(request)
    document = db.scalar(apply_document_access_filter(select(Document).where(Document.id == document_id), access, action="edit"))
    if document is None: raise HTTPException(status_code=404, detail="Document not found.")
    job = db.scalar(select(IndexingJob).where(IndexingJob.document_version_id == document.current_version_id, IndexingJob.status == "failed").order_by(IndexingJob.created_at.desc()).limit(1))
    if job is None: raise HTTPException(status_code=409, detail="This document does not have a failed indexing job.")
    job.status = "pending"; job.attempts = 0; job.error_detail = None; job.completed_at = None
    job.updated_at = datetime.now(timezone.utc); job.message = "Manual retry queued."
    document.indexed = False; document.indexing_status = document.lifecycle_status = "pending"
    version = db.get(DocumentVersion, document.current_version_id)
    if version is not None: version.status = "pending"
    db.commit(); request.app.state.indexing_worker.enqueue(job.id)
    return _indexing_status(document, job)


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
