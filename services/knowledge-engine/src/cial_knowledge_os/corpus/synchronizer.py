"""Synchronize a Corpus Tree into PostgreSQL metadata."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from time import perf_counter

from sqlalchemy.orm import Session

from backend.app.models.knowledge import Document, DocumentVersion, Folder
from backend.app.models.operations import IngestionRun

from .metadata import CorpusMetadataStore, DELETED_STATUS
from .models import CorpusFile, CorpusSyncSummary, CorpusTree

logger = logging.getLogger(__name__)

PENDING_STATUS = "pending"
INDEXED_STATUS = "indexed"


class CorpusSynchronizer:
    def __init__(self, *, batch_size: int = 500) -> None:
        self.batch_size = batch_size

    def synchronize(self, tree: CorpusTree, session: Session) -> CorpusSyncSummary:
        started = perf_counter()
        store = CorpusMetadataStore(session)
        snapshot = store.snapshot()
        organization_id, default_department_id = store.ensure_enterprise_document_context()
        counters = _Counters(
            folders_scanned=tree.folders_scanned,
            files_scanned=tree.files_scanned,
        )

        ingestion_run = IngestionRun(
            status="running",
            files_seen=tree.files_scanned,
            message="Corpus synchronization started.",
        )
        session.add(ingestion_run)
        session.flush()

        try:
            folders_by_path = self._sync_folders(tree, snapshot, session, counters)
            jobs_created = self._sync_documents(
                tree,
                snapshot,
                folders_by_path,
                store,
                session,
                counters,
                organization_id=organization_id,
                default_department_id=default_department_id,
            )
            counters.indexing_jobs_created = jobs_created
            ingestion_run.status = "completed"
            ingestion_run.completed_at = datetime.now(timezone.utc)
            ingestion_run.files_indexed = jobs_created
            ingestion_run.files_failed = 0
            ingestion_run.message = "Corpus synchronization completed."
        except Exception:
            ingestion_run.status = "failed"
            ingestion_run.completed_at = datetime.now(timezone.utc)
            ingestion_run.files_failed = tree.files_scanned
            ingestion_run.message = "Corpus synchronization failed."
            raise

        summary = counters.to_summary(
            elapsed_ms=int((perf_counter() - started) * 1000),
            message="Corpus synchronization completed.",
        )
        log_payload = summary.to_dict()
        log_payload["sync_message"] = log_payload.pop("message", "")
        logger.info(
            "corpus_sync_completed",
            extra={"event": "corpus_sync", **log_payload},
        )
        return summary

    def _sync_folders(
        self,
        tree: CorpusTree,
        snapshot,
        session: Session,
        counters: "_Counters",
    ) -> dict[str, Folder]:
        folders_by_path = dict(snapshot.folders_by_path)
        scanned_paths = set(tree.folders_by_path)
        existing_paths = set(snapshot.folders_by_path)
        active_existing_paths = {
            path
            for path, folder in snapshot.folders_by_path.items()
            if folder.last_scanned_at is not None
        }
        new_paths = set(scanned_paths - existing_paths)
        missing_paths = set(active_existing_paths - scanned_paths - {""})

        scanned_signatures = self._tree_folder_signatures(tree)
        existing_signatures = CorpusMetadataStore.folder_signatures(snapshot.active_documents)
        used_new_paths: set[str] = set()
        moved_missing_paths: set[str] = set()

        for missing_path in sorted(missing_paths, key=len, reverse=True):
            signature = existing_signatures.get(missing_path)
            if not signature:
                continue
            match_path = next(
                (
                    path
                    for path in sorted(new_paths)
                    if path not in used_new_paths and scanned_signatures.get(path) == signature
                ),
                None,
            )
            if match_path is None:
                continue
            folder = folders_by_path.pop(missing_path)
            scanned_folder = tree.folders_by_path[match_path]
            folder.name = scanned_folder.name
            folder.relative_path = scanned_folder.relative_path
            folder.depth = scanned_folder.depth
            folder.last_scanned_at = tree.scanned_at
            folders_by_path[match_path] = folder
            used_new_paths.add(match_path)
            moved_missing_paths.add(missing_path)
            counters.folders_moved += 1

        for relative_path, corpus_folder in sorted(tree.folders_by_path.items(), key=lambda item: item[1].depth):
            folder = folders_by_path.get(relative_path)
            if folder is None:
                folder = Folder(
                    name=corpus_folder.name,
                    relative_path=relative_path,
                    depth=corpus_folder.depth,
                )
                session.add(folder)
                folders_by_path[relative_path] = folder
                counters.folders_added += 1
            elif folder.last_scanned_at is None:
                counters.folders_added += 1
            folder.name = corpus_folder.name
            folder.depth = corpus_folder.depth
            folder.document_count = corpus_folder.document_count
            folder.subfolder_count = corpus_folder.subfolder_count
            folder.last_scanned_at = tree.scanned_at
        session.flush()

        for relative_path, corpus_folder in tree.folders_by_path.items():
            folder = folders_by_path[relative_path]
            parent_path = corpus_folder.parent_relative_path
            folder.parent_id = folders_by_path[parent_path].id if parent_path is not None else None

        for missing_path in sorted(missing_paths - moved_missing_paths):
            folder = snapshot.folders_by_path.get(missing_path)
            if folder is not None:
                folder.last_scanned_at = None
                folder.document_count = 0
                folder.subfolder_count = 0
                counters.folders_removed += 1

        return folders_by_path

    def _sync_documents(
        self,
        tree: CorpusTree,
        snapshot,
        folders_by_path: dict[str, Folder],
        store: CorpusMetadataStore,
        session: Session,
        counters: "_Counters",
        *,
        organization_id,
        default_department_id,
    ) -> int:
        jobs_created = 0
        scanned_paths = set(tree.files_by_path)
        existing_by_path = dict(snapshot.documents_by_path)
        unmatched_existing = {
            path: document
            for path, document in existing_by_path.items()
            if path not in scanned_paths and document.indexing_status != DELETED_STATUS
        }
        matched_existing_ids: set[object] = set()

        for relative_path, file in sorted(tree.files_by_path.items()):
            existing = existing_by_path.get(relative_path)
            action: str | None = None
            queue_indexing = False
            if existing is None:
                existing = self._match_moved_document(file, unmatched_existing, matched_existing_ids)
                if existing is None:
                    existing = self._new_document(
                        file,
                        organization_id=organization_id,
                        department_id=default_department_id,
                    )
                    session.add(existing)
                    counters.files_added += 1
                    action = "added"
                    queue_indexing = True
                else:
                    old_path = existing.relative_path
                    old_name = existing.name
                    old_folder = existing.folder.relative_path if existing.folder else ""
                    self._apply_file_metadata(existing, file)
                    matched_existing_ids.add(existing.id)
                    unmatched_existing.pop(old_path, None)
                    if old_folder != file.folder_relative_path:
                        counters.files_moved += 1
                    if old_name != file.name:
                        counters.files_renamed += 1
                    action = "moved"
            else:
                content_changed = (
                    existing.content_hash != file.content_hash
                    or existing.size_bytes != file.size_bytes
                    or existing.indexing_status == DELETED_STATUS
                )
                self._apply_file_metadata(existing, file)
                if content_changed:
                    counters.files_modified += 1
                    action = "modified"
                    queue_indexing = True
                else:
                    counters.files_unchanged += 1

            existing.folder_id = folders_by_path[file.folder_relative_path].id
            if existing.organization_id is None:
                existing.organization_id = organization_id
            if existing.department_id is None:
                existing.department_id = default_department_id
            if not existing.storage_scope:
                existing.storage_scope = "enterprise"
            if not existing.visibility:
                existing.visibility = "enterprise"
            if not existing.source_type:
                existing.source_type = "corpus_sync"
            if existing.deleted_at is not None:
                existing.deleted_at = None
                existing.deleted_by_user_id = None
                existing.delete_reason = None
            if action is not None:
                if queue_indexing:
                    existing.indexed = False
                    existing.indexing_status = PENDING_STATUS
                    existing.lifecycle_status = "pending"
                    version = self._add_document_version(existing, file, store, session)
                    store.add_indexing_job(
                        action=action,
                        document=existing,
                        document_version=version,
                        message=f"Corpus document {action}: {existing.relative_path}",
                    )
                    jobs_created += 1
            elif existing.indexing_status != DELETED_STATUS and existing.indexing_status != PENDING_STATUS:
                existing.indexing_status = INDEXED_STATUS if existing.indexed else existing.indexing_status
                if existing.indexed and existing.lifecycle_status != "archived":
                    existing.lifecycle_status = "indexed"

        for path, document in unmatched_existing.items():
            if document.id in matched_existing_ids:
                continue
            document.indexed = False
            document.indexing_status = DELETED_STATUS
            document.lifecycle_status = "deleted"
            document.deleted_at = datetime.now(timezone.utc)
            counters.files_removed += 1

        return jobs_created

    @staticmethod
    def _new_document(file: CorpusFile, *, organization_id, department_id) -> Document:
        document = Document(
            organization_id=organization_id,
            department_id=department_id,
            storage_scope="enterprise",
            name=file.name,
            relative_path=file.relative_path,
            file_type=file.extension.removeprefix(".") or "unknown",
            extension=file.extension,
            mime_type=file.mime_type,
            visibility="enterprise",
            size_bytes=file.size_bytes,
            content_hash=file.content_hash,
            modified_at=file.modified_at,
            indexed=False,
            indexing_status=PENDING_STATUS,
            lifecycle_status=PENDING_STATUS,
            source_type="corpus_sync",
        )
        return document

    @staticmethod
    def _apply_file_metadata(document: Document, file: CorpusFile) -> None:
        document.name = file.name
        document.relative_path = file.relative_path
        document.file_type = file.extension.removeprefix(".") or "unknown"
        document.extension = file.extension
        document.mime_type = file.mime_type
        document.size_bytes = file.size_bytes
        document.content_hash = file.content_hash
        document.modified_at = file.modified_at

    @staticmethod
    def _match_moved_document(
        file: CorpusFile,
        candidates: dict[str, Document],
        matched_ids: set[object],
    ) -> Document | None:
        for document in candidates.values():
            if document.id in matched_ids:
                continue
            if document.content_hash == file.content_hash and document.size_bytes == file.size_bytes:
                return document
        return None

    @staticmethod
    def _add_document_version(
        document: Document,
        file: CorpusFile,
        store: CorpusMetadataStore,
        session: Session,
    ) -> DocumentVersion:
        session.flush()
        version = DocumentVersion(
            document_id=document.id,
            version_number=store.next_document_version(document.id),
            storage_key=file.relative_path,
            content_hash=file.content_hash,
            size_bytes=file.size_bytes,
            mime_type=file.mime_type,
            modified_at=file.modified_at,
            status="pending",
        )
        session.add(version)
        session.flush()
        document.current_version_id = version.id
        return version

    @staticmethod
    def _tree_folder_signatures(tree: CorpusTree) -> dict[str, tuple[str, ...]]:
        signatures: dict[str, tuple[str, ...]] = {}
        for relative_path in tree.folders_by_path:
            if relative_path:
                prefix = f"{relative_path}/"
                hashes = [
                    file.content_hash
                    for path, file in tree.files_by_path.items()
                    if path.startswith(prefix)
                ]
            else:
                hashes = [file.content_hash for file in tree.files_by_path.values()]
            signatures[relative_path] = tuple(sorted(hashes))
        return signatures


class _Counters:
    def __init__(self, *, folders_scanned: int, files_scanned: int) -> None:
        self.folders_scanned = folders_scanned
        self.files_scanned = files_scanned
        self.folders_added = 0
        self.folders_removed = 0
        self.folders_moved = 0
        self.files_added = 0
        self.files_removed = 0
        self.files_modified = 0
        self.files_moved = 0
        self.files_renamed = 0
        self.files_unchanged = 0
        self.indexing_jobs_created = 0
        self.skipped = 0

    def to_summary(self, *, elapsed_ms: int, message: str) -> CorpusSyncSummary:
        return CorpusSyncSummary(
            folders_scanned=self.folders_scanned,
            files_scanned=self.files_scanned,
            folders_added=self.folders_added,
            folders_removed=self.folders_removed,
            folders_moved=self.folders_moved,
            files_added=self.files_added,
            files_removed=self.files_removed,
            files_modified=self.files_modified,
            files_moved=self.files_moved,
            files_renamed=self.files_renamed,
            files_unchanged=self.files_unchanged,
            indexing_jobs_created=self.indexing_jobs_created,
            skipped=self.skipped,
            elapsed_ms=elapsed_ms,
            message=message,
        )
