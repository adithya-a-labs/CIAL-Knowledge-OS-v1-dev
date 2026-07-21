"""Persistent corpus fingerprinting and incremental indexing plans."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .file_formats import is_supported_file
from .corpus.scanner import is_ignored_managed_path

MANIFEST_VERSION = 1
CITATION_METADATA_VERSION = 2


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def document_id(relative_path: str, repository_id: str | None = None) -> str:
    """Return a stable identifier that survives document content changes."""

    identity = f"{repository_id or 'default'}:{relative_path}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


@dataclass(frozen=True, slots=True)
class DocumentManifestEntry:
    relative_path: str
    sha256: str
    size_bytes: int
    modified_time: float
    document_type: str
    category: str | None
    collection: str | None
    chunk_count: int = 0
    indexed_at: str | None = None
    document_id: str = ""
    index_version: int = MANIFEST_VERSION
    citation_metadata_version: int = 1
    source_root: str | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DocumentManifestEntry":
        relative_path = str(value["relative_path"])
        return cls(
            relative_path=relative_path,
            sha256=str(value["sha256"]),
            size_bytes=int(value["size_bytes"]),
            modified_time=float(value["modified_time"]),
            document_type=str(value["document_type"]),
            category=value.get("category"),
            collection=value.get("collection"),
            chunk_count=int(value.get("chunk_count", 0)),
            indexed_at=value.get("indexed_at"),
            document_id=str(value.get("document_id") or document_id(relative_path)),
            index_version=int(value.get("index_version", MANIFEST_VERSION)),
            citation_metadata_version=int(value.get("citation_metadata_version", 1)),
            source_root=str(value["source_root"]) if value.get("source_root") else None,
        )


@dataclass(frozen=True, slots=True)
class IndexingPlan:
    corpus_root: Path
    manifest_path: Path
    new: tuple[DocumentManifestEntry, ...] = ()
    unchanged: tuple[DocumentManifestEntry, ...] = ()
    changed: tuple[DocumentManifestEntry, ...] = ()
    deleted: tuple[DocumentManifestEntry, ...] = ()
    previous: dict[str, DocumentManifestEntry] = field(default_factory=dict)
    force_rebuild: bool = False
    incremental_enabled: bool = True
    repository_id: str | None = None

    @property
    def files_to_process(self) -> tuple[DocumentManifestEntry, ...]:
        return (*self.new, *self.changed)

    @property
    def corpus_changed(self) -> bool:
        return bool(self.new or self.changed or self.deleted or self.force_rebuild)


def _fingerprint(path: Path, root: Path, *, repository_id: str | None = None) -> DocumentManifestEntry:
    relative = path.resolve().relative_to(root.resolve()).as_posix()
    parts = Path(relative).parts[:-1]
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    stat = path.stat()
    return DocumentManifestEntry(
        relative_path=relative,
        sha256=digest.hexdigest(),
        size_bytes=stat.st_size,
        modified_time=stat.st_mtime,
        document_type=path.suffix.lstrip(".").lower(),
        category=parts[0] if parts else None,
        collection=parts[1] if len(parts) > 1 else None,
        document_id=document_id(relative, repository_id),
        citation_metadata_version=(
            CITATION_METADATA_VERSION if path.suffix.casefold() == ".pdf" else 1
        ),
        source_root=str(root.resolve()),
    )


def scan_corpus(root: Path, *, repository_id: str | None = None) -> dict[str, DocumentManifestEntry]:
    """Hash every implemented document below the canonical corpus root."""

    if not root.exists():
        return {}
    entries = (
        _fingerprint(path, root, repository_id=repository_id)
        for path in sorted(root.rglob("*"))
        if path.is_file() and not path.is_symlink()
        and not is_ignored_managed_path(path, root) and is_supported_file(path.name)
    )
    return {entry.relative_path: entry for entry in entries}


def load_manifest(
    path: Path,
    *,
    corpus_root: Path | None = None,
    collection_name: str | None = None,
) -> dict[str, DocumentManifestEntry]:
    """Load a compatible manifest, treating missing/foreign manifests as empty."""

    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            return {}
        if int(value.get("version", 0)) != MANIFEST_VERSION:
            return {}
        if corpus_root is not None and value.get("corpus_root") != str(
            corpus_root.resolve()
        ):
            return {}
        if (
            collection_name is not None
            and value.get("collection_name") != collection_name
        ):
            return {}
        entries = value.get("documents", [])
        return {
            entry.relative_path: entry
            for entry in (
                DocumentManifestEntry.from_dict(item)
                for item in entries
                if isinstance(item, dict)
            )
        }
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return {}


def create_indexing_plan(
    *,
    corpus_root: Path,
    manifest_path: Path,
    collection_name: str,
    incremental_enabled: bool = True,
    force_rebuild: bool = False,
    repository_id: str | None = None,
    additional_roots: Iterable[Path] = (),
    force_reindex_paths: Iterable[str] = (),
) -> IndexingPlan:
    roots = (corpus_root, *(Path(value) for value in additional_roots))
    current: dict[str, DocumentManifestEntry] = {}
    for root in roots:
        for key, entry in scan_corpus(root, repository_id=repository_id).items():
            if key in current:
                raise RuntimeError(f"Duplicate managed relative path: {key}")
            current[key] = entry
    previous = load_manifest(
        manifest_path,
        corpus_root=corpus_root,
        collection_name=collection_name,
    )
    rebuild = force_rebuild or not incremental_enabled
    if rebuild:
        return IndexingPlan(
            corpus_root=corpus_root,
            manifest_path=manifest_path,
            new=tuple(current[key] for key in sorted(current)),
            deleted=tuple(previous[key] for key in sorted(previous)),
            previous=previous,
            force_rebuild=force_rebuild,
            incremental_enabled=incremental_enabled,
            repository_id=repository_id,
        )
    new: list[DocumentManifestEntry] = []
    unchanged: list[DocumentManifestEntry] = []
    changed: list[DocumentManifestEntry] = []
    forced = {str(value).replace("\\", "/").strip("/") for value in force_reindex_paths if str(value).strip()}
    for key in sorted(current):
        entry = current[key]
        old = previous.get(key)
        if old is None:
            new.append(entry)
        elif key in forced:
            changed.append(entry)
        elif old.sha256 == entry.sha256 and (
            entry.document_type != "pdf"
            or old.citation_metadata_version >= CITATION_METADATA_VERSION
        ):
            value = asdict(entry)
            value.update(
                {
                    "chunk_count": old.chunk_count,
                    "indexed_at": old.indexed_at,
                    "document_id": old.document_id,
                    "index_version": old.index_version,
                    "citation_metadata_version": old.citation_metadata_version,
                }
            )
            unchanged.append(DocumentManifestEntry(**value))
        else:
            changed.append(entry)
    deleted = [previous[key] for key in sorted(previous.keys() - current.keys())]
    return IndexingPlan(
        corpus_root=corpus_root,
        manifest_path=manifest_path,
        new=tuple(new),
        unchanged=tuple(unchanged),
        changed=tuple(changed),
        deleted=tuple(deleted),
        previous=previous,
        incremental_enabled=True,
        repository_id=repository_id,
    )


def write_manifest(
    plan: IndexingPlan,
    *,
    collection_name: str,
    chunk_counts: dict[str, int],
) -> dict[str, DocumentManifestEntry]:
    """Atomically persist successful current-corpus indexing state."""

    now = _now_iso()
    entries: dict[str, DocumentManifestEntry] = {
        entry.relative_path: entry for entry in plan.unchanged
    }
    for entry in plan.files_to_process:
        value = asdict(entry)
        value["chunk_count"] = int(chunk_counts.get(entry.relative_path, 0))
        value["indexed_at"] = now
        entries[entry.relative_path] = DocumentManifestEntry(**value)
    payload = {
        "version": MANIFEST_VERSION,
        "corpus_root": str(plan.corpus_root.resolve()),
        "collection_name": collection_name,
        "repository_id": plan.repository_id,
        "updated_at": now,
        "documents": [
            asdict(entries[key]) for key in sorted(entries, key=str.casefold)
        ],
    }
    target = plan.manifest_path
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(target)
    return entries


def update_manifest_entry(
    *,
    manifest_path: Path,
    corpus_root: Path,
    managed_root: Path,
    source_path: Path,
    collection_name: str,
    chunk_count: int,
    repository_id: str | None = None,
) -> DocumentManifestEntry:
    """Atomically update one successfully indexed file without scanning the corpus."""
    entries = load_manifest(manifest_path, corpus_root=corpus_root, collection_name=collection_name)
    fresh = _fingerprint(source_path, managed_root, repository_id=repository_id)
    value = asdict(fresh)
    value.update({"chunk_count": int(chunk_count), "indexed_at": _now_iso()})
    entry = DocumentManifestEntry(**value)
    entries[entry.relative_path] = entry
    payload = {
        "version": MANIFEST_VERSION, "corpus_root": str(corpus_root.resolve()),
        "collection_name": collection_name, "repository_id": repository_id,
        "updated_at": _now_iso(),
        "documents": [asdict(entries[key]) for key in sorted(entries, key=str.casefold)],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest_path.with_name(f".{manifest_path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(manifest_path)
    return entry


def entry_paths(
    plan: IndexingPlan,
    entries: Iterable[DocumentManifestEntry],
) -> list[Path]:
    return [
        (Path(entry.source_root) if entry.source_root else plan.corpus_root)
        / entry.relative_path
        for entry in entries
    ]
