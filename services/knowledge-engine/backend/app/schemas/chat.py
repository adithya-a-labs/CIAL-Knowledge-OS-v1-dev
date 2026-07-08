"""Chat endpoint schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    selected_document_ids: list[str] = Field(default_factory=list)
    response_length: Literal["short", "medium", "long"] = "medium"
    include_sources: bool = True


class ChatCitation(BaseModel):
    id: str
    document_name: str
    page: int | None = None
    snippet: str = ""
    score: float | None = None


class ChatSource(BaseModel):
    id: str
    document_name: str
    path: str = ""
    page: int | None = None
    chunk_id: str = ""
    text: str = ""
    score: float | None = None


class ChatMetadata(BaseModel):
    retrieval_mode: str = "hybrid_rrf_reranked"
    phase: str = "4.5"
    latency_ms: int = 0
    model: str = ""


class ChatResponse(BaseModel):
    answer: str
    citations: list[ChatCitation] = Field(default_factory=list)
    sources: list[ChatSource] = Field(default_factory=list)
    metadata: ChatMetadata
