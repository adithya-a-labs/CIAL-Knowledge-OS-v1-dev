"""Chat endpoint schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

ChatProfile = Literal[
    "quick",
    "standard",
    "detailed",
    "operational",
    "elite",
    "short",
    "medium",
    "long",
]


class ChatRequest(BaseModel):
    session_id: UUID | None = None
    question: str = Field(min_length=1)
    search_scope: Literal["enterprise", "workspace", "hybrid", "current_upload"] = "hybrid"
    selected_document_ids: list[str] = Field(default_factory=list)
    selected_folder_ids: list[str] = Field(default_factory=list)
    response_length: ChatProfile = "standard"
    profile: ChatProfile | None = None
    max_answer_words: int | None = None
    include_sources: bool = True
    include_debug: bool = False


class ChatCitation(BaseModel):
    id: str
    document_name: str
    document_id: str | None = None
    document_version_id: str | None = None
    repository_id: str | None = None
    relative_path: str | None = None
    page: int | None = None
    page_number: int | None = None
    page_index: int | None = None
    location_label: str | None = None
    page_count: int | None = None
    sheet_name: str | None = None
    sheet_index: int | None = None
    slide_number: int | None = None
    anchor: str | None = None
    chunk_id: str | None = None
    snippet: str = ""
    highlight_text: str | None = None
    preview_text: str | None = None
    file_type: str | None = None
    mime_type: str | None = None
    file_url: str | None = None
    preview_url: str | None = None
    download_url: str | None = None
    score: float | None = None


class ChatSource(BaseModel):
    id: str
    document_name: str
    path: str = ""
    document_id: str | None = None
    document_version_id: str | None = None
    repository_id: str | None = None
    relative_path: str | None = None
    page: int | None = None
    page_number: int | None = None
    page_index: int | None = None
    location_label: str | None = None
    page_count: int | None = None
    sheet_name: str | None = None
    sheet_index: int | None = None
    slide_number: int | None = None
    anchor: str | None = None
    chunk_id: str = ""
    text: str = ""
    highlight_text: str | None = None
    preview_text: str | None = None
    file_type: str | None = None
    mime_type: str | None = None
    file_url: str | None = None
    score: float | None = None


class ChatMetadata(BaseModel):
    retrieval_mode: str = "hybrid_rrf_reranked"
    phase: str = "4.5"
    latency_ms: int = 0
    model: str = ""
    profile: str = "standard"
    effective_min_answer_words: int | None = None
    effective_max_answer_words: int | None = None
    answer_detail_level: str = "detailed"
    prompt_name: str = "generation.phase4_system"
    adaptive_sections: bool = True
    citation_mode: str = "inline_reference_ids_only"
    temperature: float = 0
    evidence_token_budget: int | None = None
    max_context_tokens: int | None = None
    retrieved_count: int = 0
    selected_evidence_count: int = 0
    context_sections: int = 0
    weak_evidence: bool = False
    index_fresh: bool | None = None
    selected_context_applied: bool = False
    selected_document_count: int = 0
    selected_folder_count: int = 0
    effective_document_count: int = 0
    selected_context_filter_mode: str | None = None


class ChatResponse(BaseModel):
    session_id: UUID | None = None
    user_message_id: UUID | None = None
    assistant_message_id: UUID | None = None
    answer: str
    citations: list[ChatCitation] = Field(default_factory=list)
    sources: list[ChatSource] = Field(default_factory=list)
    metadata: ChatMetadata
    debug: dict[str, Any] | None = None
    # Internal persistence payload. Pydantic excludes exact evidence text from
    # API serialization so it is never exposed outside existing debug gating.
    evidence_snapshot: list[dict[str, Any]] = Field(default_factory=list, exclude=True)


class ChatMessageRecord(BaseModel):
    id: UUID
    role: Literal["user", "assistant"]
    content: str
    citations: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    feedback: list[str] = Field(default_factory=list)


class MessageFeedbackRequest(BaseModel):
    feedback: Literal["helpful", "not_helpful", "incorrect", "missing_sources", "hallucination"]


class MessageFeedbackResponse(BaseModel):
    active: list[str] = Field(default_factory=list)


class MessageTransformRequest(BaseModel):
    operation: Literal["explain_simpler", "create_checklist"]




class ChatSessionRecord(BaseModel):
    id: UUID
    title: str
    messages: list[ChatMessageRecord] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ChatSessionList(BaseModel):
    sessions: list[ChatSessionRecord] = Field(default_factory=list)
