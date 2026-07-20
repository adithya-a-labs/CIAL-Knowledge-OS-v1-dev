"""Export endpoint schemas."""

from __future__ import annotations

from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ExportFile(BaseModel):
    id: str
    name: str
    path: str
    type: str
    size_bytes: int
    modified_at: str


class ExportListResponse(BaseModel):
    exports: list[ExportFile] = Field(default_factory=list)

class ExportOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    include_sources: bool = True
    include_generated_timestamp: bool = True
    include_conversation_context: bool = False
    page_size: Literal["A4"] = "A4"
    document_style: Literal["professional"] = "professional"

class ExportCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["pdf", "docx"]
    session_id: UUID
    message_id: UUID
    title: str = Field(min_length=1, max_length=160)
    options: ExportOptions = Field(default_factory=ExportOptions)

class ExportCreateResponse(BaseModel):
    export_id: UUID
    status: Literal["queued"]

class ExportProgress(BaseModel):
    stage: str
    percent: int

class ExportPreview(BaseModel):
    type: Literal["pdf", "html"]
    url: str

class ExportJobResponse(BaseModel):
    export_id: UUID
    format: Literal["pdf", "docx"]
    status: Literal["queued", "processing", "ready", "failed", "expired", "cancelled"]
    progress: ExportProgress
    error: dict[str, str] | None = None
    filename: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None
    preview: ExportPreview | None = None
    download_url: str | None = None
    suggested_workspace_filename: str | None = None

class ExportWorkspaceSaveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str | None = Field(default=None, max_length=255)
    folder_id: UUID | None = None

class ExportWorkspaceSaveResponse(BaseModel):
    document_id: UUID
    filename: str
    folder_id: UUID | None = None
    file_type: Literal["pdf", "docx"]
    size_bytes: int
    indexing_status: str
    indexing_job_id: UUID | None = None
    open_url: str
