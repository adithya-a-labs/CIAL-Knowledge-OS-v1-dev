"""Document routes."""

from __future__ import annotations

from fastapi import APIRouter, File, Request, UploadFile

from backend.app.schemas.documents import DocumentListResponse, DocumentMetadata

router = APIRouter()


@router.get("/documents", response_model=DocumentListResponse)
def list_documents(request: Request) -> DocumentListResponse:
    documents = request.app.state.document_service.list_documents()
    return DocumentListResponse(documents=documents)


@router.post("/documents/upload", response_model=DocumentMetadata)
def upload_document(
    request: Request,
    file: UploadFile = File(...),
) -> DocumentMetadata:
    return request.app.state.document_service.save_upload(
        file.filename or "upload",
        file.file,
    )
