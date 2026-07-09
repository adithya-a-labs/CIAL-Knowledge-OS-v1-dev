"""Document endpoint schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


DocumentType = Literal[
    "pdf",
    "docx",
    "xlsx",
    "csv",
    "pptx",
    "txt",
    "md",
    "html",
    "json",
    "xml",
    "yaml",
    "image",
    "unknown",
]


class DocumentMetadata(BaseModel):
    id: str
    name: str
    path: str
    type: DocumentType
    size_bytes: int = 0
    modified_at: str
    indexed: bool = False


class DocumentListResponse(BaseModel):
    documents: list[DocumentMetadata] = Field(default_factory=list)


class UploadResponse(BaseModel):
    """Response for document upload with indexing pipeline status."""
    id: str
    name: str
    path: str
    type: DocumentType
    size_bytes: int = 0
    modified_at: str
    indexed: bool = False
    indexing_status: str = "pending"
    indexing_job_id: str | None = None
    content_hash: str | None = None
    duplicate_detected: bool = False
    message: str = "Upload accepted. Background indexing queued."
