"""Typed permission-safe global search contracts."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

SearchType = Literal["document", "passage", "note", "conversation", "summary", "saved_knowledge", "folder"]


class SearchFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    types: list[SearchType] = Field(default_factory=list, max_length=7)
    scope: Literal["all_accessible", "enterprise", "my_workspace"] = "all_accessible"
    file_types: list[str] = Field(default_factory=list, max_length=20)
    updated_after: datetime | None = None
    department_ids: list[str] = Field(default_factory=list, max_length=20)
    workspace_ids: list[str] = Field(default_factory=list, max_length=20)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=300)
    mode: Literal["instant", "full"] = "full"
    filters: SearchFilters = Field(default_factory=SearchFilters)
    cursor: str | None = Field(default=None, max_length=100)
    limit: int = Field(default=30, ge=1, le=50)
    interpret: bool = True


class SearchResult(BaseModel):
    id: str
    type: SearchType
    title: str
    excerpt: str | None = None
    match_reasons: list[str] = Field(default_factory=list)
    relevance: Literal["Highly relevant", "Relevant", "Related"]
    workspace: str | None = None
    department: str | None = None
    file_type: str | None = None
    updated_at: datetime | None = None
    document_id: str | None = None
    page: int | None = None
    chunk_id: str | None = None
    summary_type: str | None = None
    summary_length: str | None = None
    can_use_as_context: bool = False
    deep_link: str


class SearchInterpretation(BaseModel):
    applied: bool = False
    explanation: str | None = None
    chips: list[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    query: str
    items: list[SearchResult]
    counts: dict[str, int]
    next_cursor: str | None = None
    interpretation: SearchInterpretation = Field(default_factory=SearchInterpretation)
    lexical_available: bool = True
    semantic_available: bool = False


class RecentSearch(BaseModel):
    id: str
    query: str
    updated_at: datetime


class RecentSearchList(BaseModel):
    items: list[RecentSearch]
