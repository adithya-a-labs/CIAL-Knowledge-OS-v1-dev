"""Saved Knowledge request and response contracts."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class SavedKnowledgeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message_id: UUID
    title: str = Field(min_length=1, max_length=255)
    collection: str | None = Field(default=None, max_length=255)
    tags: list[str] = Field(default_factory=list, max_length=30)
    description: str | None = Field(default=None, max_length=2000)
    save_citations: bool = True
    save_original_question: bool = True
    save_conversation_context: bool = False


class SavedKnowledgeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    collection: str | None = Field(default=None, max_length=255)
    tags: list[str] | None = Field(default=None, max_length=30)
    description: str | None = Field(default=None, max_length=2000)
    is_favorite: bool | None = None
    state: str | None = Field(default=None, pattern="^(active|archived)$")


class SavedKnowledgeRecord(BaseModel):
    id: UUID
    item_type: str
    title: str
    description: str | None
    body_markdown: str
    original_question: str | None
    citations: list[dict] = Field(default_factory=list)
    source_references: list[dict] = Field(default_factory=list)
    selected_document_ids: list[str] = Field(default_factory=list)
    context_scope: str | None
    conversation_id: UUID | None
    source_message_id: UUID | None
    summary_id: UUID | None
    profile: str | None
    model_name: str | None
    prompt_version: str | None
    collection: str | None
    tags: list[str] = Field(default_factory=list)
    visibility: str
    is_favorite: bool
    version: int
    state: str
    source_count: int
    created_at: datetime
    updated_at: datetime


class SavedKnowledgeList(BaseModel):
    items: list[SavedKnowledgeRecord]
    next_cursor: str | None = None
