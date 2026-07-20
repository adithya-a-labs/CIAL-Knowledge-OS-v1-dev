"""Storage-provider scanners for Corpus synchronization."""

from __future__ import annotations

from datetime import datetime, timezone
import mimetypes
from pathlib import Path
from time import perf_counter

from .hash import hash_file
from .models import ScanResult, ScannedFile, ScannedFolder, normalize_relative_path, parent_relative_path
from cial_knowledge_os.file_formats import inspect_ingestion_candidate

_IGNORED_DIRECTORIES = {
    ".git", ".venv", "node_modules", "__pycache__", "indexes", "qdrant",
    "bm25", "models", "cache", "caches", "thumbnails", "previews",
    "rendered-assets", "export-staging",
}


def is_ignored_managed_path(path: Path, root: Path) -> bool:
    """Apply the shared managed-storage ignore policy without following escapes."""
    try:
        relative = path.resolve(strict=False).relative_to(root.resolve())
    except (OSError, ValueError):
        return True
    parts = relative.parts
    name = path.name.casefold()
    return (
        any(part.casefold() in _IGNORED_DIRECTORIES or part.startswith(".") for part in parts[:-1])
        or name.startswith("~$")
        or name.endswith((".tmp", ".part", ".crdownload", ".swp", ".uploading", ".lock"))
        or name in {"thumbs.db", "desktop.ini"}
    )


class FilesystemCorpusScanner:
    """Recursive scanner for the current local filesystem storage provider."""

    def __init__(self, root: Path, *, hash_algorithm: str = "sha256") -> None:
        self.root = root
        self.hash_algorithm = hash_algorithm

    def scan(self) -> ScanResult:
        started = perf_counter()
        scanned_at = datetime.now(timezone.utc)
        root = self.root.resolve()
        folders: list[ScannedFolder] = [
            ScannedFolder(name="Root", relative_path="", parent_relative_path=None, depth=0)
        ]
        files: list[ScannedFile] = []
        if not root.exists():
            elapsed_ms = int((perf_counter() - started) * 1000)
            return ScanResult(str(root), tuple(folders), tuple(files), scanned_at, elapsed_ms)

        for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix().casefold()):
            if is_ignored_managed_path(path, root):
                continue
            relative_path = normalize_relative_path(path.relative_to(root).as_posix())
            if path.is_dir():
                folders.append(
                    ScannedFolder(
                        name=path.name,
                        relative_path=relative_path,
                        parent_relative_path=parent_relative_path(relative_path),
                        depth=relative_path.count("/") + 1 if relative_path else 0,
                    )
                )
                continue
            if not path.is_file():
                continue
            inspection = inspect_ingestion_candidate(path, corpus_root=root)
            if not inspection["eligible"]:
                continue
            folder_path = parent_relative_path(relative_path)
            extension = path.suffix.casefold()
            mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            stat = path.stat()
            files.append(
                ScannedFile(
                    name=path.name,
                    relative_path=relative_path,
                    folder_relative_path=folder_path,
                    extension=extension,
                    mime_type=mime_type,
                    size_bytes=stat.st_size,
                    modified_at=datetime.fromtimestamp(stat.st_mtime, timezone.utc),
                    content_hash=hash_file(path, algorithm=self.hash_algorithm),
                )
            )

        elapsed_ms = int((perf_counter() - started) * 1000)
        return ScanResult(str(root), tuple(folders), tuple(files), scanned_at, elapsed_ms)
