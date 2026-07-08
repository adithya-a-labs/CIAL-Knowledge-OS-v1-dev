"""Export endpoint schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExportFile(BaseModel):
    id: str
    name: str
    path: str
    type: str
    size_bytes: int
    modified_at: str


class ExportListResponse(BaseModel):
    exports: list[ExportFile] = Field(default_factory=list)
