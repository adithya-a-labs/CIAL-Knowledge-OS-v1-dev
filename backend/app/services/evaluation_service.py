"""Evaluation run discovery and starter service."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from backend.app.core.paths import OUTPUTS_ROOT, resolve_repo_path
from backend.app.schemas.evaluation import (
    EvaluationRunRequest,
    EvaluationRunResponse,
    EvaluationRunSummary,
)


class EvaluationService:
    def __init__(self, outputs_root: Path = OUTPUTS_ROOT) -> None:
        self.outputs_root = outputs_root

    def run(self, request: EvaluationRunRequest) -> EvaluationRunResponse:
        questions_path = resolve_repo_path(request.questions_file)
        run_id = f"api-eval-{uuid.uuid4().hex[:10]}"
        runs_dir = self.outputs_root / "evaluations"
        runs_dir.mkdir(parents=True, exist_ok=True)
        record = {
            "run_id": run_id,
            "questions_file": str(questions_path),
            "limit": request.limit,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "started" if questions_path.is_file() else "failed",
            "message": (
                "Evaluation request recorded. Batch execution remains a manual Phase 4 workflow."
                if questions_path.is_file()
                else "Questions file was not found."
            ),
        }
        (runs_dir / f"{run_id}.json").write_text(
            json.dumps(record, indent=2),
            encoding="utf-8",
        )
        return EvaluationRunResponse(
            status=record["status"],
            run_id=run_id,
            message=record["message"],
        )

    def list_runs(self) -> list[EvaluationRunSummary]:
        roots = [self.outputs_root / "evaluations", self.outputs_root / "batch_answers"]
        runs: list[EvaluationRunSummary] = []
        for root in roots:
            if not root.exists():
                continue
            for path in sorted(root.rglob("*"), key=lambda item: item.stat().st_mtime, reverse=True):
                if not path.is_file():
                    continue
                if path.suffix.casefold() not in {".json", ".csv", ".xlsx", ".html"}:
                    continue
                stat = path.stat()
                runs.append(
                    EvaluationRunSummary(
                        id=path.stem,
                        path=path.as_posix(),
                        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    )
                )
        return runs[:100]
