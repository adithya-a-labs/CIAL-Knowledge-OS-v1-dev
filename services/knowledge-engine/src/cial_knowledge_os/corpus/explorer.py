"""Read-only Corpus Explorer backed by PostgreSQL metadata."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.knowledge import Document, Folder

from .metadata import DELETED_STATUS, document_to_dict, folder_to_dict


class CorpusExplorer:
    def __init__(self, session: Session) -> None:
        self.session = session

    def tree(self) -> dict[str, Any]:
        folders = list(
            self.session.scalars(
                select(Folder)
                .where(Folder.last_scanned_at.is_not(None))
                .order_by(Folder.depth, Folder.name)
            )
        )
        documents = list(
            self.session.scalars(
                select(Document)
                .where(Document.indexing_status != DELETED_STATUS)
                .order_by(Document.name)
            )
        )
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
            if folder.parent_id and folder.parent_id in folders_by_id:
                folders_by_id[folder.parent_id]["children"].append(folders_by_id[folder.id])
        for document in documents:
            if document.folder_id in folders_by_id:
                folders_by_id[document.folder_id]["documents"].append(document_to_dict(document))
        return {
            "root": root,
            "folders_count": len(folders),
            "documents_count": len(documents),
        }

    def folder_contents(self, relative_path: str) -> dict[str, Any] | None:
        normalized = relative_path.replace("\\", "/").strip("/")
        folder = self.session.scalar(select(Folder).where(Folder.relative_path == normalized))
        if folder is None or folder.last_scanned_at is None:
            return None
        subfolders = list(
            self.session.scalars(
                select(Folder)
                .where(Folder.parent_id == folder.id, Folder.last_scanned_at.is_not(None))
                .order_by(Folder.name)
            )
        )
        documents = list(
            self.session.scalars(
                select(Document)
                .where(Document.folder_id == folder.id, Document.indexing_status != DELETED_STATUS)
                .order_by(Document.name)
            )
        )
        return {
            "folder": folder_to_dict(folder),
            "folders": [folder_to_dict(item) for item in subfolders],
            "documents": [document_to_dict(item) for item in documents],
        }

    def document(self, document_id: uuid.UUID) -> dict[str, Any] | None:
        document = self.session.get(Document, document_id)
        if document is None:
            return None
        return document_to_dict(document)

