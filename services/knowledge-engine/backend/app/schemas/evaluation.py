"""Evaluation endpoint schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvaluationRunRequest(BaseModel):
    questions_file: str = Field(min_length=1)
    limit: int = 10


class EvaluationRunResponse(BaseModel):
    status: Literal["started", "completed", "failed"]
    run_id: str
    message: str


class EvaluationRunSummary(BaseModel):
    id: str
    path: str
    modified_at: str


class EvaluationRunsResponse(BaseModel):
    runs: list[EvaluationRunSummary] = Field(default_factory=list)
