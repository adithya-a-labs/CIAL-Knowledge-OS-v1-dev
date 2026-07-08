"""Document discovery and upload service."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
from typing import BinaryIO

from backend.app.core.paths import DATA_FILES_ROOT, REPO_ROOT
from backend.app.schemas.documents import DocumentMetadata, DocumentType


_TYPE_BY_SUFFIX: dict[str, DocumentType] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".doc": "docx",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".csv": "csv",
    ".pptx": "pptx",
    ".ppt": "pptx",
    ".txt": "txt",
    ".md": "md",
    ".markdown": "md",
    ".html": "html",
    ".htm": "html",
    ".json": "json",
    ".xml": "xml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tif": "image",
    ".tiff": "image",
}


class DocumentService:
    """Work with local files under the canonical `data/files` root."""

    def __init__(self, root: Path = DATA_FILES_ROOT) -> None:
        self.root = root

    def list_documents(self) -> list[DocumentMetadata]:
        indexed_paths = self._indexed_paths()
        if not self.root.exists():
            return []
        documents: list[DocumentMetadata] = []
        for path in sorted(item for item in self.root.rglob("*") if item.is_file()):
            documents.append(self._metadata_for(path, indexed_paths=indexed_paths))
        return documents

    def save_upload(self, filename: str, stream: BinaryIO) -> DocumentMetadata:
        self.root.mkdir(parents=True, exist_ok=True)
        safe_name = self._safe_filename(filename)
        destination = self._available_path(self.root / safe_name)
        with destination.open("wb") as handle:
            shutil.copyfileobj(stream, handle)
        return self._metadata_for(destination, indexed_paths=self._indexed_paths())

    def _metadata_for(
        self,
        path: Path,
        *,
        indexed_paths: set[str],
    ) -> DocumentMetadata:
        stat = path.stat()
        relative = path.relative_to(REPO_ROOT).as_posix()
        return DocumentMetadata(
            id=hashlib.sha1(relative.encode("utf-8")).hexdigest()[:16],
            name=path.name,
            path=relative,
            type=_TYPE_BY_SUFFIX.get(path.suffix.casefold(), "unknown"),
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(
                stat.st_mtime,
                tz=timezone.utc,
            ).isoformat(),
            indexed=str(path.resolve()) in indexed_paths or relative in indexed_paths,
        )

    def _indexed_paths(self) -> set[str]:
        manifest_path = REPO_ROOT / "data" / "indexes" / "document_manifest.json"
        if not manifest_path.is_file():
            return set()
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        candidates: set[str] = set()
        documents = payload.get("documents")
        if isinstance(documents, dict):
            for key, value in documents.items():
                candidates.add(str(key))
                if isinstance(value, dict):
                    for field in ("path", "source", "source_path", "relative_path"):
                        if value.get(field):
                            candidates.add(str(value[field]))
        return candidates

    @staticmethod
    def _safe_filename(filename: str) -> str:
        name = Path(filename).name.strip() or "upload"
        return re.sub(r"[^A-Za-z0-9._ -]+", "_", name)

    @staticmethod
    def _available_path(path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        counter = 2
        while True:
            candidate = parent / f"{stem}-{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1
