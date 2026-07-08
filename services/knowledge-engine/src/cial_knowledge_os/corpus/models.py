"""Corpus object model used between storage scanners and metadata sync."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any


def normalize_relative_path(path: str) -> str:
    value = path.replace("\\", "/").strip("/")
    if value in {"", "."}:
        return ""
    return PurePosixPath(value).as_posix()


def parent_relative_path(path: str) -> str:
    normalized = normalize_relative_path(path)
    if not normalized:
        return ""
    parent = PurePosixPath(normalized).parent.as_posix()
    return "" if parent == "." else parent


@dataclass(frozen=True)
class ScannedFile:
    name: str
    relative_path: str
    folder_relative_path: str
    extension: str
    mime_type: str
    size_bytes: int
    modified_at: datetime
    content_hash: str


@dataclass(frozen=True)
class ScannedFolder:
    name: str
    relative_path: str
    parent_relative_path: str | None
    depth: int


@dataclass(frozen=True)
class ScanResult:
    root_path: str
    folders: tuple[ScannedFolder, ...]
    files: tuple[ScannedFile, ...]
    scanned_at: datetime
    elapsed_ms: int


@dataclass
class CorpusFile:
    name: str
    relative_path: str
    folder_relative_path: str
    extension: str
    mime_type: str
    size_bytes: int
    modified_at: datetime
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "relative_path": self.relative_path,
            "folder_relative_path": self.folder_relative_path,
            "extension": self.extension,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "modified_at": self.modified_at.isoformat(),
            "content_hash": self.content_hash,
        }


@dataclass
class CorpusFolder:
    name: str
    relative_path: str
    parent_relative_path: str | None
    depth: int
    children: list["CorpusFolder"] = field(default_factory=list)
    files: list[CorpusFile] = field(default_factory=list)

    @property
    def document_count(self) -> int:
        return len(self.files)

    @property
    def subfolder_count(self) -> int:
        return len(self.children)

    def to_dict(self, *, include_files: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "relative_path": self.relative_path,
            "parent_relative_path": self.parent_relative_path,
            "depth": self.depth,
            "document_count": self.document_count,
            "subfolder_count": self.subfolder_count,
            "children": [child.to_dict(include_files=include_files) for child in self.children],
        }
        if include_files:
            payload["files"] = [file.to_dict() for file in self.files]
        return payload


@dataclass
class CorpusTree:
    root: CorpusFolder
    scanned_at: datetime
    folders_by_path: dict[str, CorpusFolder]
    files_by_path: dict[str, CorpusFile]

    @property
    def folders_scanned(self) -> int:
        return len(self.folders_by_path)

    @property
    def files_scanned(self) -> int:
        return len(self.files_by_path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned_at": self.scanned_at.isoformat(),
            "folders_scanned": self.folders_scanned,
            "files_scanned": self.files_scanned,
            "root": self.root.to_dict(),
        }


@dataclass(frozen=True)
class CorpusSyncSummary:
    folders_scanned: int = 0
    files_scanned: int = 0
    folders_added: int = 0
    folders_removed: int = 0
    folders_moved: int = 0
    files_added: int = 0
    files_removed: int = 0
    files_modified: int = 0
    files_moved: int = 0
    files_renamed: int = 0
    files_unchanged: int = 0
    indexing_jobs_created: int = 0
    skipped: int = 0
    elapsed_ms: int = 0
    message: str = ""

    @property
    def differences_found(self) -> bool:
        return any(
            (
                self.folders_added,
                self.folders_removed,
                self.folders_moved,
                self.files_added,
                self.files_removed,
                self.files_modified,
                self.files_moved,
                self.files_renamed,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "folders_scanned": self.folders_scanned,
            "files_scanned": self.files_scanned,
            "folders_added": self.folders_added,
            "folders_removed": self.folders_removed,
            "folders_moved": self.folders_moved,
            "files_added": self.files_added,
            "files_removed": self.files_removed,
            "files_modified": self.files_modified,
            "files_moved": self.files_moved,
            "files_renamed": self.files_renamed,
            "files_unchanged": self.files_unchanged,
            "indexing_jobs_created": self.indexing_jobs_created,
            "skipped": self.skipped,
            "elapsed_ms": self.elapsed_ms,
            "differences_found": self.differences_found,
            "message": self.message,
        }

