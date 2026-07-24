"""Dedicated Corpus service facade."""

from __future__ import annotations

from datetime import datetime, timezone
import mimetypes
from pathlib import Path
import uuid

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import import_models
from backend.app.models.knowledge import Document, DocumentVersion, Folder
from backend.app.models.operations import IngestionRun
from backend.app.security.access import RequestAccessContext

from .explorer import CorpusExplorer
from .hash import hash_file
from .metadata import CorpusMetadataStore
from .models import CorpusSyncSummary
from .scanner import FilesystemCorpusScanner
from .synchronizer import CorpusSynchronizer
from .tree_builder import CorpusTreeBuilder


class CorpusServiceUnavailable(RuntimeError):
    """Raised when the metadata database is not configured."""


class CorpusService:
    """Owns Corpus discovery, metadata synchronization, and Corpus API reads."""

    def __init__(
        self,
        *,
        root: Path,
        session_factory: sessionmaker | None,
        hash_algorithm: str = "sha256",
        batch_size: int = 500,
        repository_id: str | None = None,
    ) -> None:
        self.root = root
        self.session_factory = session_factory
        self.hash_algorithm = hash_algorithm
        self.batch_size = batch_size
        self.repository_id = repository_id
        self.scanner = FilesystemCorpusScanner(root, hash_algorithm=hash_algorithm)
        self.tree_builder = CorpusTreeBuilder()
        self.synchronizer = CorpusSynchronizer(batch_size=batch_size, repository_id=repository_id)

    def sync(self, force_hash_paths: list[Path] | None = None) -> CorpusSyncSummary:
        if self.session_factory is None:
            return CorpusSyncSummary(message="DATABASE_URL is not configured; Corpus sync skipped.")
        import_models()
        with self.session_factory() as session:
            known_files = {
                row.relative_path: (
                    int(row.size_bytes or 0),
                    row.modified_at,
                    row.content_hash,
                )
                for row in session.query(Document).filter(
                    Document.repository_id == self.repository_id,
                    Document.deleted_at.is_(None),
                )
            }
        root = self.root.resolve()
        forced: set[str] = set()
        for path in force_hash_paths or ():
            try:
                forced.add(path.resolve(strict=False).relative_to(root).as_posix())
            except (OSError, ValueError):
                continue
        scan_result = self.scanner.scan(
            known_files=known_files,
            force_hash_paths=forced,
        )
        tree = self.tree_builder.build(scan_result)
        with self.session_factory() as session:
            with session.begin():
                summary = self.synchronizer.synchronize(tree, session)
        return summary

    def register_uploaded_file(
        self,
        path: Path,
        *,
        created_by_user_id: uuid.UUID | None = None,
    ) -> dict[str, str]:
        """Atomically register one durable enterprise upload and its indexing job."""

        if self.session_factory is None:
            raise CorpusServiceUnavailable("Metadata database is not configured.")
        root = self.root.resolve()
        artifact = path.resolve(strict=True)
        if root not in artifact.parents or not artifact.is_file() or artifact.is_symlink():
            raise ValueError("The enterprise upload path is outside the configured repository.")
        relative = artifact.relative_to(root).as_posix()
        stat = artifact.stat()
        modified_at = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
        digest = hash_file(artifact, algorithm=self.hash_algorithm)
        import_models()
        with self.session_factory() as session, session.begin():
            store = CorpusMetadataStore(session, repository_id=self.repository_id)
            organization_id, department_id, workspace_id = (
                store.ensure_enterprise_document_context()
            )
            root_folder = session.scalar(
                select(Folder).where(
                    Folder.repository_id == self.repository_id,
                    Folder.relative_path == "",
                )
            )
            if root_folder is None:
                root_folder = Folder(
                    workspace_id=workspace_id,
                    repository_id=self.repository_id,
                    name="Root",
                    relative_path="",
                    depth=0,
                    document_count=0,
                    subfolder_count=0,
                    last_scanned_at=datetime.now(timezone.utc),
                )
                session.add(root_folder)
                session.flush()
            document = session.scalar(
                select(Document)
                .where(
                    Document.repository_id == self.repository_id,
                    Document.relative_path == relative,
                )
                .with_for_update()
            )
            if document is None:
                document = Document(
                    organization_id=organization_id,
                    department_id=department_id,
                    workspace_id=workspace_id,
                    folder_id=root_folder.id,
                    repository_id=self.repository_id,
                    storage_scope="enterprise",
                    owner_user_id=None,
                    name=artifact.name,
                    relative_path=relative,
                    file_type=artifact.suffix.lstrip(".").casefold() or "unknown",
                    extension=artifact.suffix.casefold() or None,
                    mime_type=mimetypes.guess_type(artifact.name)[0],
                    visibility="enterprise",
                    size_bytes=stat.st_size,
                    content_hash=digest,
                    modified_at=modified_at,
                    indexed=False,
                    indexing_status="pending",
                    lifecycle_status="pending",
                    source_type="user_upload",
                    created_by_user_id=created_by_user_id,
                    updated_by_user_id=created_by_user_id,
                )
                session.add(document)
                session.flush()
                root_folder.document_count = int(root_folder.document_count or 0) + 1
                version_number = 1
            elif (
                document.content_hash == digest
                and document.current_version_id is not None
                and document.lifecycle_status != "deleted"
            ):
                version = session.get(DocumentVersion, document.current_version_id)
                job = store.add_indexing_job(
                    action="added",
                    document=document,
                    document_version=version,
                    message=f"Enterprise upload queued: {relative}",
                )
                job.priority = 100
                session.flush()
                return {
                    "document_id": str(document.id),
                    "document_version_id": str(version.id) if version else "",
                    "indexing_job_id": str(job.id),
                }
            else:
                version_number = store.next_document_version(document.id)
                document.name = artifact.name
                document.folder_id = root_folder.id
                document.size_bytes = stat.st_size
                document.content_hash = digest
                document.modified_at = modified_at
                document.deleted_at = None
                document.indexed = False
                document.indexing_status = "pending"
                document.lifecycle_status = "pending"
                document.updated_by_user_id = created_by_user_id
            version = DocumentVersion(
                document_id=document.id,
                repository_id=self.repository_id,
                version_number=version_number,
                storage_key=relative,
                content_hash=digest,
                size_bytes=stat.st_size,
                mime_type=document.mime_type,
                modified_at=modified_at,
                status="pending",
                created_by_user_id=created_by_user_id,
            )
            session.add(version)
            session.flush()
            document.current_version_id = version.id
            job = store.add_indexing_job(
                action="added" if version_number == 1 else "modified",
                document=document,
                document_version=version,
                message=f"Enterprise upload queued: {relative}",
            )
            job.priority = 100
            session.add(
                IngestionRun(
                    repository_id=self.repository_id,
                    status="completed",
                    completed_at=datetime.now(timezone.utc),
                    files_seen=1,
                    files_indexed=1,
                    files_failed=0,
                    message="Enterprise upload registered transactionally.",
                    started_by_user_id=created_by_user_id,
                )
            )
            session.flush()
            return {
                "document_id": str(document.id),
                "document_version_id": str(version.id),
                "indexing_job_id": str(job.id),
            }

    def get_tree(self, *, access_context: RequestAccessContext | None = None) -> dict[str, object]:
        if self.session_factory is None:
            raise CorpusServiceUnavailable("Metadata database is not configured.")
        import_models()
        with self.session_factory() as session:
            return CorpusExplorer(session, access_context=access_context, repository_id=self.repository_id).tree()

    def get_folder(
        self,
        relative_path: str,
        *,
        access_context: RequestAccessContext | None = None,
    ) -> dict[str, object] | None:
        if self.session_factory is None:
            raise CorpusServiceUnavailable("Metadata database is not configured.")
        import_models()
        with self.session_factory() as session:
            return CorpusExplorer(
                session,
                access_context=access_context,
                repository_id=self.repository_id,
            ).folder_contents(relative_path)

    def get_document(
        self,
        document_id: uuid.UUID,
        *,
        access_context: RequestAccessContext | None = None,
    ) -> dict[str, object] | None:
        if self.session_factory is None:
            raise CorpusServiceUnavailable("Metadata database is not configured.")
        import_models()
        with self.session_factory() as session:
            return CorpusExplorer(
                session,
                access_context=access_context,
                repository_id=self.repository_id,
            ).document(document_id)
