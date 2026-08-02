"""Typed API contracts for persistent personal notebook workspaces."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

NotebookSourceType = Literal["document", "note", "summary"]
NotebookArtifactType = Literal["executive", "detailed", "key_points", "action_items", "comparison"]


class NotebookCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class NotebookUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class NotebookRecord(BaseModel):
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    title: str
    description: str | None = None
    visibility: str
    lifecycle_status: str
    source_count: int = 0
    active_source_count: int = 0
    artifact_count: int = 0
    chat_session_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    last_activity_at: datetime


class NotebookList(BaseModel):
    items: list[NotebookRecord] = Field(default_factory=list)


class NotebookSourceAttach(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_type: NotebookSourceType
    document_id: UUID | None = None
    note_id: UUID | None = None
    summary_artifact_id: UUID | None = None
    is_default_active: bool = False

    @model_validator(mode="after")
    def validate_target(self):
        targets = [self.document_id, self.note_id, self.summary_artifact_id]
        if sum(value is not None for value in targets) != 1:
            raise ValueError("Exactly one source target is required.")
        expected = {"document": self.document_id, "note": self.note_id, "summary": self.summary_artifact_id}
        if expected[self.source_type] is None:
            raise ValueError("Source type does not match its target.")
        return self


class NotebookSourcesAttach(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sources: list[NotebookSourceAttach] = Field(min_length=1, max_length=100)


class NotebookSourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_default_active: bool


class NotebookSourceReorder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_ids: list[UUID] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_ids(self):
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("Source order contains duplicates.")
        return self


class NotebookSourceRecord(BaseModel):
    id: UUID
    notebook_id: UUID
    source_type: NotebookSourceType
    target_id: UUID
    title: str
    origin: Literal["my_workspace", "knowledge_center", "note", "summary"]
    position: int
    is_default_active: bool
    available: bool
    ready: bool
    indexing_status: str | None = None
    file_type: str | None = None
    mime_type: str | None = None
    page_count: int | None = None
    size_bytes: int | None = None
    preview_document_id: UUID | None = None
    unavailable_reason: str | None = None
    created_at: datetime


class NotebookSourceList(BaseModel):
    items: list[NotebookSourceRecord] = Field(default_factory=list)
    attached_count: int = 0
    active_count: int = 0
    ready_count: int = 0


class NotebookChatBindingRecord(BaseModel):
    notebook_id: UUID
    chat_session_id: UUID
    selected_document_ids: list[UUID] = Field(default_factory=list)
    selected_note_ids: list[UUID] = Field(default_factory=list)
    context_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class NotebookArtifactCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    artifact_type: NotebookArtifactType
    title: str | None = Field(default=None, max_length=255)
    summary_length: Literal["brief", "standard", "detailed"] = "standard"
    custom_instructions: str | None = Field(default=None, max_length=2000)


class NotebookArtifactRecord(BaseModel):
    id: UUID
    notebook_id: UUID
    artifact_type: NotebookArtifactType
    status: str
    title: str
    source_snapshot: list[dict[str, Any]] = Field(default_factory=list)
    summary_artifact_id: UUID | None = None
    note_id: UUID | None = None
    citation_count: int = 0
    source_count: int = 0
    error_code: str | None = None
    created_at: datetime
    updated_at: datetime


class NotebookArtifactList(BaseModel):
    items: list[NotebookArtifactRecord] = Field(default_factory=list)
