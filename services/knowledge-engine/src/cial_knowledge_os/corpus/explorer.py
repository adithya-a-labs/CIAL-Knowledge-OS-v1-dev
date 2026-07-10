"""Read-only Corpus Explorer backed by PostgreSQL metadata."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.security.access import (
    RequestAccessContext,
    apply_document_access_filter,
    anonymous_access_context,
)
from backend.app.models.knowledge import Document, Folder

from .metadata import DELETED_STATUS, document_to_dict, folder_to_dict


class CorpusExplorer:
    def __init__(
        self,
        session: Session,
        *,
        access_context: RequestAccessContext | None = None,
        repository_id: str | None = None,
    ) -> None:
        self.session = session
        self.access_context = access_context or anonymous_access_context()
        self.repository_id = repository_id

    def _folder_statement(self):
        statement = select(Folder)
        if self.repository_id is not None:
            statement = statement.where(Folder.repository_id == self.repository_id)
        return statement

    def _document_statement(self):
        statement = select(Document)
        if self.repository_id is not None:
            statement = statement.where(Document.repository_id == self.repository_id)
        return statement

    def tree(self) -> dict[str, Any]:
        folders = list(
            self.session.scalars(
                self._folder_statement()
                .where(Folder.last_scanned_at.is_not(None))
                .order_by(Folder.depth, Folder.name)
            )
        )
        documents = list(
            self.session.scalars(
                apply_document_access_filter(
                    self._document_statement().order_by(Document.name),
                    self.access_context,
                )
            )
        )
        visible_folder_ids = self._visible_folder_ids(folders, documents)
        folders_by_id = {folder.id: {**folder_to_dict(folder), "children": [], "documents": []} for folder in folders}
        root = next((payload for folder_id, payload in folders_by_id.items() if folders_by_id[folder_id]["relative_path"] == ""), None)
        if root is None:
            root = {
                "id": None,
                "parent_id": None,
                "name": "Root",
                "relative_path": "",
                "depth": 0,
                "document_count": 0,
                "subfolder_count": 0,
                "last_scanned_at": None,
                "children": [],
                "documents": [],
            }
        for folder in folders:
            if folder.id not in visible_folder_ids:
                continue
            if folder.parent_id and folder.parent_id in folders_by_id and folder.parent_id in visible_folder_ids:
                folders_by_id[folder.parent_id]["children"].append(folders_by_id[folder.id])
        for document in documents:
            if document.folder_id in folders_by_id and document.folder_id in visible_folder_ids:
                folders_by_id[document.folder_id]["documents"].append(document_to_dict(document))
        return {
            "root": root,
            "folders_count": len(visible_folder_ids),
            "documents_count": len(documents),
        }

    def folder_contents(self, relative_path: str) -> dict[str, Any] | None:
        normalized = relative_path.replace("\\", "/").strip("/")
        folder = self.session.scalar(self._folder_statement().where(Folder.relative_path == normalized))
        if folder is None or folder.last_scanned_at is None:
            return None
        documents = list(
            self.session.scalars(
                apply_document_access_filter(
                    self._document_statement()
                    .where(Document.indexing_status != DELETED_STATUS)
                    .order_by(Document.name),
                    self.access_context,
                )
            )
        )
        visible_folder_ids = self._visible_folder_ids(
            list(
                self.session.scalars(
                    self._folder_statement()
                    .where(Folder.last_scanned_at.is_not(None))
                    .order_by(Folder.depth, Folder.name)
                )
            ),
            documents,
        )
        if folder.id not in visible_folder_ids and normalized != "":
            return None
        subfolders = list(
            self.session.scalars(
                self._folder_statement()
                .where(Folder.parent_id == folder.id, Folder.last_scanned_at.is_not(None))
                .order_by(Folder.name)
            )
        )
        return {
            "folder": folder_to_dict(folder),
            "folders": [folder_to_dict(item) for item in subfolders if item.id in visible_folder_ids],
            "files": [document_to_dict(item) for item in documents if item.folder_id == folder.id],
            "documents": [document_to_dict(item) for item in documents if item.folder_id == folder.id],
        }

    def document(self, document_id: uuid.UUID) -> dict[str, Any] | None:
        document = self.session.scalar(
            apply_document_access_filter(
                self._document_statement().where(Document.id == document_id),
                self.access_context,
            )
        )
        if document is None:
            return None
        return document_to_dict(document)

    @staticmethod
    def _visible_folder_ids(folders: list[Folder], documents: list[Document]) -> set[uuid.UUID]:
        folders_by_id = {folder.id: folder for folder in folders}
        visible: set[uuid.UUID] = set()
        for document in documents:
            folder_id = document.folder_id
            while folder_id is not None and folder_id not in visible:
                visible.add(folder_id)
                folder = folders_by_id.get(folder_id)
                folder_id = folder.parent_id if folder is not None else None
        return visible
