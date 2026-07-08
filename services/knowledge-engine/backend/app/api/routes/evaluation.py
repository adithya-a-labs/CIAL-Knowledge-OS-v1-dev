"""Evaluation routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.app.schemas.evaluation import (
    EvaluationRunRequest,
    EvaluationRunResponse,
    EvaluationRunsResponse,
)

router = APIRouter()


@router.post("/evaluation/run", response_model=EvaluationRunResponse)
def run_evaluation(payload: EvaluationRunRequest, request: Request) -> EvaluationRunResponse:
    return request.app.state.evaluation_service.run(payload)


@router.get("/evaluation/runs", response_model=EvaluationRunsResponse)
def list_evaluation_runs(request: Request) -> EvaluationRunsResponse:
    return EvaluationRunsResponse(runs=request.app.state.evaluation_service.list_runs())
