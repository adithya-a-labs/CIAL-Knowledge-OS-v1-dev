"""Export artifact discovery service."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

from backend.app.core.paths import OUTPUTS_ROOT, REPO_ROOT
from backend.app.schemas.exports import ExportFile


class ExportService:
    def __init__(self, outputs_root: Path = OUTPUTS_ROOT) -> None:
        self.outputs_root = outputs_root

    def list_exports(self) -> list[ExportFile]:
        if not self.outputs_root.exists():
            return []
        allowed = {".csv", ".xlsx", ".html", ".json", ".jsonl", ".log", ".txt"}
        files = [
            path for path in self.outputs_root.rglob("*")
            if path.is_file() and path.suffix.casefold() in allowed
        ]
        exports: list[ExportFile] = []
        for path in sorted(files, key=lambda item: item.stat().st_mtime, reverse=True):
            stat = path.stat()
            relative = path.relative_to(REPO_ROOT).as_posix()
            exports.append(
                ExportFile(
                    id=hashlib.sha1(relative.encode("utf-8")).hexdigest()[:16],
                    name=path.name,
                    path=relative,
                    type=path.suffix.casefold().lstrip(".") or "file",
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                )
            )
        return exports[:200]
