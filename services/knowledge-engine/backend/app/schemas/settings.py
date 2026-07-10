"""Settings endpoint schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EnterpriseRepositoryRequest(BaseModel):
    folder: str = Field(min_length=1)


class EnterpriseRepositoryResponse(BaseModel):
    name: str
    folder: str
    config_path: str
    exists: bool
    is_directory: bool
    readable: bool
    writable: bool
    valid: bool
    message: str
