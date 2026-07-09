"""Document routes."""

from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile

from backend.app.schemas.documents import DocumentListResponse, DocumentMetadata, UploadResponse

router = APIRouter()


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(request: Request) -> DocumentListResponse:
    documents = request.app.state.document_service.list_documents()
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

    return request.app.state.document_service.save_upload_with_indexing(
        file.filename or "upload",
        file.file,
        corpus_sync=corpus_sync,
        indexing_worker=indexing_worker,
    )
