"""Owner-stamped personal workspace orchestration."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from pathlib import Path
import hashlib
import mimetypes
from typing import BinaryIO

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.conversations import ChatSession
from backend.app.models.identity import User
from backend.app.models.knowledge import Document, DocumentVersion, Folder, Workspace, WorkspaceUserPreference
from backend.app.models.operations import AuditEvent, IndexingJob
from cial_knowledge_os.file_formats import validate_ingestion_file
from backend.app.schemas.workspaces import WorkspacePreferences
from backend.app.security.access import RequestAccessContext


DEFAULT_WIDGETS = ["storage_usage", "pinned_items", "recent_activity"]
SYSTEM_DEFAULTS = WorkspacePreferences(
    visibleWidgets=DEFAULT_WIDGETS,
    widgetOrder=[*DEFAULT_WIDGETS, "indexing_status", "recent_notes", "recent_conversations"],
)


class WorkspaceAuthenticationRequired(RuntimeError):
    pass


class WorkspaceNotFound(RuntimeError):
    pass


class PersonalWorkspaceService:
    def __init__(self, session: Session):
        self.session = session

    def _identity(self, access: RequestAccessContext) -> tuple[uuid.UUID, uuid.UUID]:
        principal = access.principal
        if not principal.is_authenticated or principal.user_id is None or principal.organization_id is None:
            raise WorkspaceAuthenticationRequired("Authentication is required for My Workspace.")
        return principal.user_id, principal.organization_id

    def get_or_create(self, access: RequestAccessContext) -> Workspace:
        user_id, organization_id = self._identity(access)
        workspace = self._find_personal_workspace(user_id, organization_id)
        if workspace is None:
            workspace = Workspace(
                organization_id=organization_id,
                owner_user_id=user_id,
                created_by_user_id=user_id,
                updated_by_user_id=user_id,
                name="My Workspace",
                slug=f"personal-{user_id}",
                workspace_type="personal",
                visibility="private",
                description="Private user-owned knowledge workspace.",
                metadata_={"preference_defaults": {}},
            )
            self.session.add(workspace)
            try:
                self.session.flush()
            except IntegrityError:
                self.session.rollback()
                workspace = self._find_personal_workspace(user_id, organization_id)
                if workspace is None:
                    raise
        self._ensure_system_folder(workspace, "chat_uploads", "Chat Uploads")
        self._ensure_system_folder(workspace, "personal_uploads", "Personal Uploads")
        return workspace

    def _find_personal_workspace(self, user_id: uuid.UUID, organization_id: uuid.UUID) -> Workspace | None:
        workspace = self.session.scalar(select(Workspace).where(
            Workspace.workspace_type == "personal",
            Workspace.owner_user_id == user_id,
            Workspace.organization_id == organization_id,
            Workspace.deleted_at.is_(None),
        ))
        return workspace

    def _ensure_system_folder(self, workspace: Workspace, system_key: str, name: str) -> Folder:
        folder = self.session.scalar(select(Folder).where(
            Folder.workspace_id == workspace.id, Folder.system_key == system_key
        ))
        if folder is None:
            relative_path = system_key.replace("_", "-")
            folder = Folder(
                workspace_id=workspace.id,
                repository_id=f"personal:{workspace.owner_user_id}",
                system_key=system_key,
                name=name,
                relative_path=relative_path,
                depth=0,
            )
            self.session.add(folder)
            try:
                self.session.flush()
            except IntegrityError:
                self.session.rollback()
                folder = self.session.scalar(select(Folder).where(
                    Folder.workspace_id == workspace.id, Folder.system_key == system_key
                ))
                if folder is None:
                    raise
        return folder

    def preferences(self, access: RequestAccessContext) -> WorkspacePreferences:
        user_id, _ = self._identity(access)
        workspace = self.get_or_create(access)
        row = self.session.scalar(select(WorkspaceUserPreference).where(
            WorkspaceUserPreference.workspace_id == workspace.id,
            WorkspaceUserPreference.user_id == user_id,
        ))
        workspace_defaults = (workspace.metadata_ or {}).get("preference_defaults", {})
        merged = SYSTEM_DEFAULTS.model_dump(by_alias=True)
        if isinstance(workspace_defaults, dict):
            merged.update(workspace_defaults)
        if row is not None:
            merged.update(row.preferences or {})
        return WorkspacePreferences.model_validate(merged)

    def save_preferences(self, access: RequestAccessContext, value: WorkspacePreferences) -> WorkspacePreferences:
        user_id, _ = self._identity(access)
        workspace = self.get_or_create(access)
        row = self.session.scalar(select(WorkspaceUserPreference).where(
            WorkspaceUserPreference.workspace_id == workspace.id,
            WorkspaceUserPreference.user_id == user_id,
        ))
        if row is None:
            row = WorkspaceUserPreference(workspace_id=workspace.id, user_id=user_id, preferences={})
            self.session.add(row)
        row.preferences = value.model_dump(by_alias=True)
        self._audit(user_id, "workspace.preferences.updated", "workspace", workspace.id)
        self.session.commit()
        return value

    def reset_preferences(self, access: RequestAccessContext) -> WorkspacePreferences:
        user_id, _ = self._identity(access)
        workspace = self.get_or_create(access)
        row = self.session.scalar(select(WorkspaceUserPreference).where(
            WorkspaceUserPreference.workspace_id == workspace.id,
            WorkspaceUserPreference.user_id == user_id,
        ))
        if row is not None:
            self.session.delete(row)
        self.session.commit()
        return self.preferences(access)

    def summary(self, access: RequestAccessContext) -> dict[str, object]:
        user_id, _ = self._identity(access)
        workspace = self.get_or_create(access)
        documents = list(self.session.scalars(select(Document).where(
            Document.workspace_id == workspace.id,
            Document.owner_user_id == user_id,
            Document.storage_scope == "personal",
            Document.visibility == "private",
            Document.deleted_at.is_(None),
            Document.lifecycle_status != "deleted",
        ).order_by(Document.modified_at.desc().nullslast(), Document.created_at.desc())))
        used = sum(document.size_bytes for document in documents)
        quota = settings.workspace_quota_bytes if settings.workspace_quota_bytes > 0 else None
        activities = list(self.session.scalars(select(AuditEvent).where(
            AuditEvent.user_id == user_id
        ).order_by(AuditEvent.created_at.desc()).limit(10)))
        conversations = list(self.session.scalars(select(ChatSession).where(
            ChatSession.user_id == user_id
        ).order_by(ChatSession.updated_at.desc()).limit(10)))
        return {
            "workspace": self._workspace_payload(workspace),
            "storage": {"used_bytes": used, "quota_bytes": quota, "available": True},
            "pinned": [self._document_payload(item) for item in documents if bool((item.metadata_ or {}).get("pinned"))][:5],
            "recent_activity": [{"id": str(item.id), "action": item.action, "created_at": item.created_at.isoformat()} for item in activities],
            "recent_conversations": [{"id": str(item.id), "title": item.title or "Untitled conversation", "updated_at": item.updated_at.isoformat()} for item in conversations],
        }

    def tree(self, access: RequestAccessContext) -> dict[str, object]:
        workspace = self.get_or_create(access)
        folders = list(self.session.scalars(select(Folder).where(Folder.workspace_id == workspace.id).order_by(Folder.depth, Folder.name)))
        return {"workspace": self._workspace_payload(workspace), "folders": [self._folder_payload(folder) for folder in folders]}

    def folder(self, access: RequestAccessContext, folder_id: uuid.UUID | None) -> dict[str, object]:
        user_id, _ = self._identity(access)
        workspace = self.get_or_create(access)
        if folder_id is not None:
            selected = self.session.scalar(select(Folder).where(Folder.id == folder_id, Folder.workspace_id == workspace.id))
            if selected is None:
                raise WorkspaceNotFound("Folder not found.")
        folders = list(self.session.scalars(select(Folder).where(
            Folder.workspace_id == workspace.id, Folder.parent_id == folder_id
        ).order_by(Folder.name)))
        documents = list(self.session.scalars(select(Document).where(
            Document.workspace_id == workspace.id,
            Document.owner_user_id == user_id,
            Document.storage_scope == "personal",
            Document.visibility == "private",
            Document.folder_id == folder_id,
            Document.deleted_at.is_(None),
            Document.lifecycle_status != "deleted",
        ).order_by(Document.modified_at.desc().nullslast(), Document.name)))
        return {"folder_id": str(folder_id) if folder_id else None, "folders": [self._folder_payload(item) for item in folders], "documents": [self._document_payload(item) for item in documents]}

    def create_folder(self, access: RequestAccessContext, name: str, parent_id: uuid.UUID | None) -> dict[str, object]:
        workspace = self.get_or_create(access)
        parent = None
        if parent_id:
            parent = self.session.scalar(select(Folder).where(Folder.id == parent_id, Folder.workspace_id == workspace.id))
            if parent is None:
                raise WorkspaceNotFound("Parent folder not found.")
        safe_name = " ".join(name.split()).strip()
        folder = Folder(
            workspace_id=workspace.id,
            parent_id=parent_id,
            repository_id=f"personal:{workspace.owner_user_id}",
            name=safe_name,
            relative_path=f"{parent.relative_path + '/' if parent else ''}{uuid.uuid4()}",
            depth=(parent.depth + 1) if parent else 0,
        )
        self.session.add(folder)
        self.session.flush()
        self._audit(workspace.owner_user_id, "workspace.folder.created", "folder", folder.id)
        self.session.commit()
        return self._folder_payload(folder)

    def upload(self, access: RequestAccessContext, filename: str, stream: BinaryIO, folder_id: uuid.UUID | None = None, *, metadata: dict[str, object] | None = None, source_type: str = "user_upload", audit_action: str = "workspace.document.uploaded", resolve_collision: bool = False, system_folder_key: str = "personal_uploads") -> dict[str, object]:
        user_id, organization_id = self._identity(access)
        workspace = self.get_or_create(access)
        user = self.session.get(User, user_id)
        if user is None or user.department_id is None:
            raise WorkspaceNotFound("A department classification is required before uploading.")
        if folder_id is None:
            folder_name = "Chat Uploads" if system_folder_key == "chat_uploads" else "Personal Uploads"
            folder = self._ensure_system_folder(workspace, system_folder_key, folder_name)
        else:
            folder = self.session.scalar(select(Folder).where(Folder.id == folder_id, Folder.workspace_id == workspace.id))
            if folder is None:
                raise WorkspaceNotFound("Upload folder not found.")

        display_name = Path(filename).name[:255] or "upload"
        if resolve_collision:
            self.session.scalar(select(Workspace.id).where(Workspace.id == workspace.id).with_for_update())
            display_name = self._available_name(workspace.id, folder.id, display_name)
        extension = Path(display_name).suffix.casefold()
        if not validate_ingestion_file(display_name)["valid_for_ingestion"]:
            raise ValueError("This file type is not supported for indexing.")
        relative_path = Path(str(organization_id), str(user_id), folder.system_key or str(folder.id), f"{uuid.uuid4()}{extension}")
        root = settings.workspace_root_path.resolve()
        destination = (root / relative_path).resolve()
        if root not in destination.parents:
            raise WorkspaceNotFound("Invalid upload destination.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".uploading")
        digest = hashlib.sha256()
        size = 0
        try:
            used_bytes = self._used_bytes(workspace.id, user_id)
            with temporary.open("wb") as target:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if settings.workspace_quota_bytes > 0 and used_bytes + size > settings.workspace_quota_bytes:
                        raise ValueError("Workspace storage quota reached.")
                    digest.update(chunk)
                    target.write(chunk)
            temporary.replace(destination)
            now = datetime.now(timezone.utc)
            document = Document(
                organization_id=organization_id, department_id=user.department_id, workspace_id=workspace.id,
                folder_id=folder.id, repository_id=f"personal:{user_id}", storage_scope="personal",
                owner_user_id=user_id, name=display_name, relative_path=relative_path.as_posix(),
                file_type=extension.lstrip(".") or "unknown", extension=extension or None,
                mime_type=mimetypes.guess_type(display_name)[0], visibility="private", size_bytes=size,
                content_hash=digest.hexdigest(), modified_at=now, indexed=False, indexing_status="pending",
                lifecycle_status="pending", source_type=source_type, created_by_user_id=user_id,
                updated_by_user_id=user_id, metadata_={"pinned": False, **(metadata or {})},
            )
            self.session.add(document)
            self.session.flush()
            version = DocumentVersion(
                document_id=document.id, repository_id=document.repository_id, version_number=1,
                storage_key=relative_path.as_posix(), content_hash=document.content_hash or digest.hexdigest(),
                size_bytes=size, mime_type=document.mime_type, created_by_user_id=user_id,
                modified_at=now, status="pending",
            )
            self.session.add(version)
            self.session.flush()
            document.current_version_id = version.id
            job = IndexingJob(
                document_id=document.id, document_version_id=version.id, content_hash=document.content_hash,
                repository_id=document.repository_id, status="pending", force_rebuild=False,
                metadata_={"source": source_type, "action": "added", "document_id": str(document.id),
                    "document_version_id": str(version.id), "relative_path": document.relative_path,
                    "content_hash": document.content_hash, "repository_id": document.repository_id,
                    "storage_scope": "personal", "workspace_id": str(workspace.id),
                    "owner_user_id": str(user_id), "department_id": str(document.department_id),
                    "folder_id": str(folder.id), "visibility": "private", "lifecycle_status": "pending"},
            )
            self.session.add(job)
            folder.document_count = int(folder.document_count or 0) + 1
            self._audit(user_id, audit_action, "document", document.id)
            self.session.commit()
            payload = self._document_payload(document)
            payload["indexing_job_id"] = str(job.id)
            payload["document_version_id"] = str(version.id)
            payload["mime_type"] = document.mime_type
            return payload
        except Exception:
            self.session.rollback()
            temporary.unlink(missing_ok=True)
            destination.unlink(missing_ok=True)
            raise

    def save_export_artifact(self, access: RequestAccessContext, source: Path, filename: str, folder_id: uuid.UUID | None, provenance: dict[str, object]) -> dict[str, object]:
        """Copy a trusted completed export through the normal personal-upload transaction."""
        if source.is_symlink() or not source.is_file():
            raise WorkspaceNotFound("Export artifact is unavailable.")
        with source.open("rb") as stream:
            return self.upload(
                access, filename, stream, folder_id, metadata={"source_export": provenance},
                source_type="system_import", audit_action="export_saved_to_workspace", resolve_collision=True,
            )

    def _available_name(self, workspace_id: uuid.UUID, folder_id: uuid.UUID, requested: str) -> str:
        existing = {name.casefold() for name in self.session.scalars(select(Document.name).where(
            Document.workspace_id == workspace_id, Document.folder_id == folder_id,
            Document.deleted_at.is_(None), Document.lifecycle_status != "deleted",
        ))}
        if requested.casefold() not in existing:
            return requested
        path=Path(requested);stem=path.stem;suffix=path.suffix
        counter=2
        collision_suffix=f"-{counter}{suffix}";candidate=f"{stem[:160-len(collision_suffix)].rstrip('-.')}{collision_suffix}"
        while candidate.casefold() in existing:
            counter += 1
            collision_suffix=f"-{counter}{suffix}";candidate=f"{stem[:160-len(collision_suffix)].rstrip('-.')}{collision_suffix}"
        return candidate

    def _used_bytes(self, workspace_id: uuid.UUID, user_id: uuid.UUID) -> int:
        return int(self.session.scalar(select(func.coalesce(func.sum(Document.size_bytes), 0)).where(
            Document.workspace_id == workspace_id, Document.owner_user_id == user_id,
            Document.deleted_at.is_(None), Document.lifecycle_status != "deleted",
        )) or 0)

    def delete_document(self, access: RequestAccessContext, document_id: uuid.UUID) -> str | None:
        user_id, _ = self._identity(access)
        document = self.session.scalar(select(Document).where(
            Document.id == document_id, Document.owner_user_id == user_id,
            Document.storage_scope == "personal", Document.visibility == "private",
        ))
        if document is None:
            raise WorkspaceNotFound("Document not found.")
        document.deleted_at = datetime.now(timezone.utc)
        document.deleted_by_user_id = user_id
        document.lifecycle_status = "deleted"
        document.indexing_status = "deleted"; document.indexed = False
        active = self.session.scalar(select(IndexingJob).where(
            IndexingJob.document_version_id == document.current_version_id,
            IndexingJob.status.in_(("pending", "running")),
        )) if document.current_version_id else None
        if active is not None:
            active.metadata_ = {**(active.metadata_ or {}), "action": "deleted"}
            job = active
        else:
            job = IndexingJob(document_id=document.id, document_version_id=document.current_version_id,
                content_hash=document.content_hash, repository_id=document.repository_id, status="pending",
                force_rebuild=False, attempts=0, message="Personal document deleted.",
                metadata_={"source":"personal_workspace", "action":"deleted", "document_id":str(document.id),
                           "document_version_id":str(document.current_version_id) if document.current_version_id else None,
                           "relative_path":document.relative_path, "workspace_id":str(document.workspace_id),
                           "owner_user_id":str(document.owner_user_id), "storage_scope":"personal", "visibility":"private"})
            self.session.add(job); self.session.flush()
        source = (settings.workspace_root_path.resolve() / document.relative_path).resolve()
        root = settings.workspace_root_path.resolve()
        if root not in source.parents or source.is_symlink():
            raise WorkspaceNotFound("Document storage path is invalid.")
        trash = root / ".trash" / str(user_id) / f"{document.id}{source.suffix}"
        trash.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file(): source.replace(trash)
        self._audit(user_id, "workspace.document.deleted", "document", document.id)
        try:
            self.session.commit()
        except Exception:
            if trash.is_file(): trash.replace(source)
            raise
        return str(job.id)

    @staticmethod
    def _workspace_payload(workspace: Workspace) -> dict[str, object]:
        return {"id": str(workspace.id), "name": workspace.name, "workspace_type": workspace.workspace_type, "visibility": workspace.visibility}

    @staticmethod
    def _folder_payload(folder: Folder) -> dict[str, object]:
        return {"id": str(folder.id), "parent_id": str(folder.parent_id) if folder.parent_id else None, "name": folder.name, "system_key": folder.system_key, "document_count": folder.document_count}

    @staticmethod
    def _document_payload(document: Document) -> dict[str, object]:
        indexing_metadata = document.metadata_ or {}
        return {
            "id": str(document.id), "folder_id": str(document.folder_id) if document.folder_id else None,
            "name": document.name, "file_type": document.file_type, "size_bytes": document.size_bytes,
            "modified_at": document.modified_at.isoformat() if document.modified_at else document.created_at.isoformat(),
            "status": document.indexing_status, "indexed": document.indexed,
            "indexing_stage": indexing_metadata.get("indexing_stage"),
            "indexing_safe_message": indexing_metadata.get("indexing_safe_message"),
            "indexing_error_code": indexing_metadata.get("indexing_error_code"),
            "retry_allowed": document.indexing_status == "failed" and indexing_metadata.get("indexing_retry_allowed", True) is not False,
            "indexing_updated_at": (document.updated_at or document.modified_at or document.created_at).isoformat(),
        }

    def _audit(self, user_id: uuid.UUID | None, action: str, entity_type: str, entity_id: uuid.UUID) -> None:
        self.session.add(AuditEvent(user_id=user_id, actor_user_id=user_id, action=action, entity_type=entity_type, entity_id=entity_id, status="succeeded"))
