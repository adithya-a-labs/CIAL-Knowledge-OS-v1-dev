"""Private note API schemas."""
from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class NoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Untitled", max_length=255)

class NoteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=255)
    content_json: dict[str, Any] | None = None
    content_markdown: str | None = Field(default=None, max_length=1_000_000)
    content_format: Literal["markdown", "editor_json"] | None = None
    is_pinned: bool | None = None
    is_archived: bool | None = None

class TagCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=64)
    color: str | None = Field(default=None, max_length=32)

class TagUpdate(TagCreate): pass

class LinkDocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: UUID

class NoteRecord(BaseModel):
    id: UUID; title: str; content_json: dict[str, Any] | None; content_markdown: str; content_format: str; plain_text: str
    is_pinned: bool; is_archived: bool; revision: int; created_at: datetime; updated_at: datetime
    indexing_status: str = "pending"; indexed_revision: int | None = None
    tags: list[dict[str, Any]] = Field(default_factory=list); linked_documents: list[dict[str, Any]] = Field(default_factory=list)

class NoteList(BaseModel):
    items: list[NoteRecord]; next_cursor: str | None = None
