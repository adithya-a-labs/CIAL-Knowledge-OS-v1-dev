"""Tests for incremental and real-time indexing reliability."""

from __future__ import annotations

import io
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cial_knowledge_os.corpus.models import (
    CorpusFile,
    CorpusFolder,
    CorpusSyncSummary,
    CorpusTree,
)


def test_missing_or_expired_in_progress_lease_is_recoverable() -> None:
    from backend.app.services.indexing_queue import _expired_lease_predicate

    predicate = str(
        _expired_lease_predicate(datetime.now(timezone.utc)).compile(
            compile_kwargs={"literal_binds": True}
        )
    )
    assert "lease_expires_at IS NULL" in predicate
    assert "lease_expires_at <" in predicate
    assert " OR " in predicate


def test_completed_job_restores_verified_document_and_version_state() -> None:
    from backend.app.models.knowledge import Document, DocumentVersion
    from backend.app.services.indexing_queue import DurableIndexQueue

    document = SimpleNamespace(
        lifecycle_status="indexing",
        indexing_status="indexing",
        indexed=False,
        indexed_at=None,
        metadata_={"indexing_stage": "verifying"},
    )
    version = SimpleNamespace(status="indexing")
    document_id, version_id = uuid.uuid4(), uuid.uuid4()
    session = MagicMock()
    session.get.side_effect = lambda model, identity: (
        document if model is Document and identity == document_id
        else version if model is DocumentVersion and identity == version_id
        else None
    )
    completed_at = datetime.now(timezone.utc)
    DurableIndexQueue._set_target_completed(
        session,
        SimpleNamespace(
            document_id=document_id,
            document_version_id=version_id,
            note_id=None,
            note_version_id=None,
            operation="upsert_version",
        ),
        completed_at,
    )
    assert document.indexed is True
    assert document.indexing_status == document.lifecycle_status == "indexed"
    assert document.indexed_at == completed_at
    assert document.metadata_["indexing_stage"] == "completed"
    assert version.status == "indexed"


class TestCorpusSyncSummarySkipLogic(unittest.TestCase):
    """Verify the skip-logic uses CorpusSyncSummary.differences_found."""

    def test_no_differences_found_means_skip(self) -> None:
        summary = CorpusSyncSummary(
            files_scanned=5,
            files_unchanged=5,
            message="ok",
        )
        self.assertFalse(summary.differences_found)

    def test_files_added_means_no_skip(self) -> None:
        summary = CorpusSyncSummary(files_scanned=6, files_added=1)
        self.assertTrue(summary.differences_found)

    def test_files_modified_means_no_skip(self) -> None:
        summary = CorpusSyncSummary(files_scanned=5, files_modified=1)
        self.assertTrue(summary.differences_found)

    def test_files_removed_means_no_skip(self) -> None:
        summary = CorpusSyncSummary(files_scanned=4, files_removed=1)
        self.assertTrue(summary.differences_found)


class TestCorpusSyncSummaryCounters(unittest.TestCase):
    """Ensure all counter fields are correctly tracked."""

    def test_all_counters_in_to_dict(self) -> None:
        summary = CorpusSyncSummary(
            folders_scanned=3,
            files_scanned=10,
            folders_added=1,
            folders_removed=0,
            folders_moved=0,
            files_added=2,
            files_removed=1,
            files_modified=1,
            files_moved=0,
            files_renamed=0,
            files_unchanged=6,
            indexing_jobs_created=3,
            elapsed_ms=42,
            message="test",
        )
        payload = summary.to_dict()
        self.assertEqual(payload["files_scanned"], 10)
        self.assertEqual(payload["files_added"], 2)
        self.assertEqual(payload["files_removed"], 1)
        self.assertEqual(payload["files_modified"], 1)
        self.assertEqual(payload["files_unchanged"], 6)
        self.assertEqual(payload["indexing_jobs_created"], 3)
        self.assertTrue(payload["differences_found"])


class TestIndexingJobModelEnhancements(unittest.TestCase):
    """Verify the IndexingJob model has the new columns."""

    def test_indexing_job_has_required_columns(self) -> None:
        from backend.app.models.operations import IndexingJob

        self.assertTrue(
            {
                "id",
                "document_id",
                "content_hash",
                "status",
                "force_rebuild",
                "started_at",
                "completed_at",
                "error_detail",
                "message",
                "metadata",
            }.issubset(IndexingJob.__table__.columns.keys())
        )

    def test_indexing_job_has_document_id_column(self) -> None:
        from backend.app.models.operations import IndexingJob
        self.assertTrue(hasattr(IndexingJob, "document_id"))

    def test_indexing_job_has_content_hash_column(self) -> None:
        from backend.app.models.operations import IndexingJob
        self.assertTrue(hasattr(IndexingJob, "content_hash"))

    def test_indexing_job_has_error_detail_column(self) -> None:
        from backend.app.models.operations import IndexingJob
        self.assertTrue(hasattr(IndexingJob, "error_detail"))

    def test_indexing_job_uses_safe_attribute_for_metadata_column(self) -> None:
        from backend.app.models.operations import IndexingJob

        self.assertTrue(hasattr(IndexingJob, "metadata_"))
        self.assertEqual(IndexingJob.__table__.columns["metadata"].name, "metadata")


class TestDocumentServiceHashDeduplication(unittest.TestCase):
    """Test hash computation and safe filenames for uploads."""

    def test_hash_file_deterministic(self) -> None:
        from backend.app.services.document_service import DocumentService
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test content for hashing")
            f.flush()
            path = Path(f.name)
        try:
            hash1 = DocumentService._hash_file(path)
            hash2 = DocumentService._hash_file(path)
            self.assertEqual(hash1, hash2)
            self.assertEqual(len(hash1), 64)  # SHA256 hex digest length
        finally:
            path.unlink(missing_ok=True)

    def test_safe_filename_strips_dangerous_chars(self) -> None:
        from backend.app.services.document_service import DocumentService
        self.assertEqual(DocumentService._safe_filename("normal.pdf"), "normal.pdf")
        self.assertEqual(DocumentService._safe_filename("a<b>c.pdf"), "a_b_c.pdf")
        self.assertEqual(DocumentService._safe_filename("../../etc/passwd"), "passwd")

    def test_available_path_returns_original_when_free(self) -> None:
        from backend.app.services.document_service import DocumentService
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.pdf"
            result = DocumentService._available_path(path)
            self.assertEqual(result, path)

    def test_available_path_increments_when_taken(self) -> None:
        from backend.app.services.document_service import DocumentService
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "test.pdf"
            path.touch()
            result = DocumentService._available_path(path)
            self.assertEqual(result.name, "test-2.pdf")


class TestUploadResponseSchema(unittest.TestCase):
    """Ensure the UploadResponse schema has all required fields."""

    def test_upload_response_schema_fields(self) -> None:
        from backend.app.schemas.documents import UploadResponse
        response = UploadResponse(
            id="abc123",
            name="test.pdf",
            path="data/files/test.pdf",
            type="pdf",
            size_bytes=1024,
            modified_at="2026-01-01T00:00:00+00:00",
            indexing_status="pending",
            indexing_job_id="some-uuid",
            content_hash="abc123def456",
        )
        self.assertEqual(response.indexing_status, "pending")
        self.assertEqual(response.indexing_job_id, "some-uuid")
        self.assertFalse(response.duplicate_detected)
        self.assertEqual(response.message, "Upload accepted. Background indexing queued.")


class TestIndexingWorkerLifecycle(unittest.TestCase):
    """Basic lifecycle tests for the IndexingWorker."""

    def test_worker_starts_and_stops(self) -> None:
        from backend.app.services.indexing_worker import IndexingWorker
        engine = MagicMock()
        runtime_state = MagicMock()
        worker = IndexingWorker(
            engine=engine,
            runtime_state=runtime_state,
        )
        worker.start()
        self.assertTrue(worker._thread is not None and worker._thread.is_alive())
        worker.stop()
        # After stop(), _thread is set to None
        self.assertIsNone(worker._thread)

    def test_worker_does_not_start_twice(self) -> None:
        from backend.app.services.indexing_worker import IndexingWorker
        engine = MagicMock()
        runtime_state = MagicMock()
        worker = IndexingWorker(engine=engine, runtime_state=runtime_state)
        worker.start()
        thread1 = worker._thread
        worker.start()  # Should be a no-op
        thread2 = worker._thread
        self.assertIs(thread1, thread2)
        worker.stop()


class TestStartupServiceSkipLogic(unittest.TestCase):
    """Test the _should_skip_indexing logic."""

    def _make_service(self, force_rebuild: bool = False) -> object:
        from backend.app.services.startup_service import StartupService
        engine = MagicMock()
        runtime_state = MagicMock()
        service = StartupService(engine=engine, runtime_state=runtime_state)
        return service

    @patch("backend.app.services.startup_service.settings")
    def test_skip_when_no_changes_and_no_pending_jobs(self, mock_settings: MagicMock) -> None:
        mock_settings.force_rebuild_on_startup = False
        service = self._make_service()
        summary = CorpusSyncSummary(files_scanned=5, files_unchanged=5)
        with patch.object(service, "_has_pending_jobs", return_value=False):
            self.assertTrue(service._should_skip_indexing(summary))

    @patch("backend.app.services.startup_service.settings")
    def test_no_skip_when_differences_found(self, mock_settings: MagicMock) -> None:
        mock_settings.force_rebuild_on_startup = False
        service = self._make_service()
        summary = CorpusSyncSummary(files_scanned=6, files_added=1)
        with patch.object(service, "_has_pending_jobs", return_value=False):
            self.assertFalse(service._should_skip_indexing(summary))

    @patch("backend.app.services.startup_service.settings")
    def test_no_skip_when_pending_jobs_exist(self, mock_settings: MagicMock) -> None:
        mock_settings.force_rebuild_on_startup = False
        service = self._make_service()
        summary = CorpusSyncSummary(files_scanned=5, files_unchanged=5)
        with patch.object(service, "_has_pending_jobs", return_value=True):
            self.assertFalse(service._should_skip_indexing(summary))

    @patch("backend.app.services.startup_service.settings")
    def test_no_skip_when_force_rebuild(self, mock_settings: MagicMock) -> None:
        mock_settings.force_rebuild_on_startup = True
        service = self._make_service()
        summary = CorpusSyncSummary(files_scanned=5, files_unchanged=5)
        self.assertFalse(service._should_skip_indexing(summary))

    @patch("backend.app.services.startup_service.settings")
    def test_skip_when_no_summary_and_no_pending_jobs(self, mock_settings: MagicMock) -> None:
        mock_settings.force_rebuild_on_startup = False
        service = self._make_service()
        with patch.object(service, "_has_pending_jobs", return_value=False):
            self.assertTrue(service._should_skip_indexing(None))


class TestJobStateValues(unittest.TestCase):
    """Verify the valid job statuses match the requirement."""

    def test_valid_job_statuses(self) -> None:
        from cial_knowledge_os.corpus.metadata import _VALID_JOB_STATUSES
        self.assertEqual(
            set(_VALID_JOB_STATUSES),
            {"pending", "running", "succeeded", "failed", "skipped"},
        )


if __name__ == "__main__":
    unittest.main()
