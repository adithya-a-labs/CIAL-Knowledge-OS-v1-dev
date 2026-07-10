"""Document metadata repository helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.knowledge import Document, DocumentChunk, DocumentPermission, DocumentVersion


class DocumentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, document_id: uuid.UUID) -> Document | None:
        return self.session.get(Document, document_id)

    def get_by_relative_path(self, relative_path: str) -> Document | None:
        return self.session.scalar(
            select(Document).where(
                Document.repository_id == settings.corpus_repository_id,
                Document.relative_path == relative_path,
            )
        )

    def list_by_folder(self, folder_id: uuid.UUID | None = None) -> list[Document]:
        statement = select(Document).order_by(Document.name)
        if folder_id is None:
            statement = statement.where(
                Document.repository_id == settings.corpus_repository_id,
                Document.folder_id.is_(None),
            )
        else:
            statement = statement.where(
                Document.repository_id == settings.corpus_repository_id,
                Document.folder_id == folder_id,
            )
        return list(self.session.scalars(statement))

    def add(self, document: Document) -> Document:
        self.session.add(document)
        return document

    def add_version(self, version: DocumentVersion) -> DocumentVersion:
        self.session.add(version)
        return version

    def add_chunk(self, chunk: DocumentChunk) -> DocumentChunk:
        self.session.add(chunk)
        return chunk

    def add_permission(self, permission: DocumentPermission) -> DocumentPermission:
        self.session.add(permission)
        return permission
