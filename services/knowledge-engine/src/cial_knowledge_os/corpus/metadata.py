"""PostgreSQL metadata access for the Corpus layer."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.knowledge import Document, Folder
from backend.app.models.operations import IndexingJob, IngestionRun


DELETED_STATUS = "deleted"


@dataclass(frozen=True)
class MetadataSnapshot:
    folders_by_path: dict[str, Folder]
    documents_by_path: dict[str, Document]
    active_documents: list[Document]


class CorpusMetadataStore:
    def __init__(self, session: Session) -> None:
        self.session = session

    def snapshot(self) -> MetadataSnapshot:
        folders = list(self.session.scalars(select(Folder)))
        documents = list(self.session.scalars(select(Document)))
        return MetadataSnapshot(
            folders_by_path={folder.relative_path: folder for folder in folders},
            documents_by_path={document.relative_path: document for document in documents},
            active_documents=[
                document for document in documents if document.indexing_status != DELETED_STATUS
            ],
        )

    def next_document_version(self, document_id: uuid.UUID) -> int:
        current = self.session.scalar(
            select(func.max(DocumentVersion.version_number)).where(  # type: ignore[name-defined]
                DocumentVersion.document_id == document_id  # type: ignore[name-defined]
            )
        )
        return int(current or 0) + 1

    def add_indexing_job(self, *, action: str, document: Document, message: str) -> IndexingJob:
        job = IndexingJob(
            status="pending",
            force_rebuild=False,
            message=message,
            metadata_={
                "source": "corpus_sync",
                "action": action,
                "document_id": str(document.id),
                "relative_path": document.relative_path,
                "content_hash": document.content_hash,
            },
        )
        self.session.add(job)
        return job

    @staticmethod
    def folder_signatures(documents: list[Document]) -> dict[str, tuple[str, ...]]:
        signatures: dict[str, list[str]] = defaultdict(list)
        for document in documents:
            if not document.content_hash:
                continue
            path = document.relative_path
            parts = path.split("/")[:-1]
            signatures[""].append(document.content_hash)
            for index in range(len(parts)):
                folder_path = "/".join(parts[: index + 1])
                signatures[folder_path].append(document.content_hash)
        return {path: tuple(sorted(values)) for path, values in signatures.items()}


from backend.app.models.knowledge import DocumentVersion  # noqa: E402


def folder_to_dict(folder: Folder) -> dict[str, Any]:
    return {
        "id": str(folder.id),
        "parent_id": str(folder.parent_id) if folder.parent_id else None,
        "name": folder.name,
        "relative_path": folder.relative_path,
        "depth": folder.depth,
        "document_count": folder.document_count,
        "subfolder_count": folder.subfolder_count,
        "last_scanned_at": folder.last_scanned_at.isoformat() if folder.last_scanned_at else None,
        "created_at": folder.created_at.isoformat(),
        "updated_at": folder.updated_at.isoformat(),
    }


def document_to_dict(document: Document) -> dict[str, Any]:
    return {
        "id": str(document.id),
        "folder_id": str(document.folder_id) if document.folder_id else None,
        "name": document.name,
        "relative_path": document.relative_path,
        "extension": document.extension,
        "mime_type": document.mime_type,
        "file_type": document.file_type,
        "size_bytes": document.size_bytes,
        "content_hash": document.content_hash,
        "modified_at": document.modified_at.isoformat() if document.modified_at else None,
        "indexed": document.indexed,
        "indexing_status": document.indexing_status,
        "indexed_at": document.indexed_at.isoformat() if document.indexed_at else None,
        "page_count": document.page_count,
        "created_at": document.created_at.isoformat(),
        "updated_at": document.updated_at.isoformat(),
    }

