"""Folder metadata repository helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.knowledge import Folder, FolderPermission


class FolderRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, folder_id: uuid.UUID) -> Folder | None:
        return self.session.get(Folder, folder_id)

    def get_by_relative_path(self, relative_path: str) -> Folder | None:
        return self.session.scalar(
            select(Folder).where(
                Folder.repository_id == settings.corpus_repository_id,
                Folder.relative_path == relative_path,
            )
        )

    def list_children(self, parent_id: uuid.UUID | None = None) -> list[Folder]:
        statement = select(Folder).order_by(Folder.name)
        if parent_id is None:
            statement = statement.where(
                Folder.repository_id == settings.corpus_repository_id,
                Folder.parent_id.is_(None),
            )
        else:
            statement = statement.where(
                Folder.repository_id == settings.corpus_repository_id,
                Folder.parent_id == parent_id,
            )
        return list(self.session.scalars(statement))

    def add(self, folder: Folder) -> Folder:
        self.session.add(folder)
        return folder

    def add_permission(self, permission: FolderPermission) -> FolderPermission:
        self.session.add(permission)
        return permission
