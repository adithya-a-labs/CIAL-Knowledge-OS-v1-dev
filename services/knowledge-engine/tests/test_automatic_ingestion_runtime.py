from __future__ import annotations

from pathlib import Path
import tempfile
import uuid

from backend.app.services.export_service import ExportService
from cial_knowledge_os.corpus.scanner import FilesystemCorpusScanner, is_ignored_managed_path
from cial_knowledge_os.corpus.watcher import CorpusWatcher


def test_watcher_stability_accepts_closed_file_and_deleted_path():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "document.pdf"
        path.write_bytes(b"complete")
        assert CorpusWatcher._wait_until_stable(path, attempts=2, interval=0)
        path.unlink()
        assert CorpusWatcher._wait_until_stable(path, attempts=2, interval=0)


def test_watcher_passes_coalesced_event_paths_to_reconciliation():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "document.txt"
        path.write_text("stable", encoding="utf-8")
        calls = []
        watcher = CorpusWatcher(
            root=root,
            sync_callback=calls.append,
            debounce_seconds=0,
            stability_attempts=2,
            stability_interval=0,
        )
        watcher._run_sync([path, path])
        assert len(calls) == 1
        assert set(calls[0]) == {path}


def test_scanner_reuses_hash_after_size_and_mtime_precheck(monkeypatch):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "document.txt"
        path.write_text("stable", encoding="utf-8")
        scanner = FilesystemCorpusScanner(root)
        first = scanner.scan().files[0]
        monkeypatch.setattr(
            "cial_knowledge_os.corpus.scanner.hash_file",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("unchanged files must not be re-hashed")
            ),
        )
        second = scanner.scan(
            known_files={
                first.relative_path: (
                    first.size_bytes,
                    first.modified_at,
                    first.content_hash,
                )
            }
        ).files[0]
        assert second.content_hash == first.content_hash


def test_watcher_target_forces_hash_even_when_size_and_mtime_match(monkeypatch):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        path = root / "document.txt"
        path.write_text("stable", encoding="utf-8")
        scanner = FilesystemCorpusScanner(root)
        first = scanner.scan().files[0]
        calls = []
        monkeypatch.setattr(
            "cial_knowledge_os.corpus.scanner.hash_file",
            lambda *_args, **_kwargs: calls.append(path) or "forced-hash",
        )
        result = scanner.scan(
            known_files={
                first.relative_path: (
                    first.size_bytes,
                    first.modified_at,
                    first.content_hash,
                )
            },
            force_hash_paths={first.relative_path},
        )
        assert calls == [path]
        assert result.files[0].content_hash == "forced-hash"


def test_managed_ignore_and_containment_policy():
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        assert is_ignored_managed_path(root / "~$draft.docx", root)
        assert is_ignored_managed_path(root / "copy.uploading", root)
        assert is_ignored_managed_path(root.parent / "outside.pdf", root)
        assert not is_ignored_managed_path(root / "approved.pdf", root)


def test_export_save_wakes_exact_job_once(monkeypatch):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory); artifact = root / "result.pdf"; artifact.write_bytes(b"pdf")
        job_id = uuid.uuid4(); wakes = []

        class Workspace:
            def __init__(self, db): pass
            def save_export_artifact(self, *args):
                return {"id": str(uuid.uuid4()), "name": "result.pdf", "folder_id": None,
                    "file_type": "pdf", "size_bytes": 3, "status": "pending", "indexing_job_id": str(job_id)}

        monkeypatch.setattr("backend.app.services.export_service.PersonalWorkspaceService", Workspace)
        job = type("Job", (), {"status":"ready", "format":"pdf", "storage_key":"result.pdf",
            "id":uuid.uuid4(), "session_id":uuid.uuid4(), "message_id":uuid.uuid4(),
            "source_content_hash":"hash", "completed_at":None, "title":"Result", "source_snapshot":{}})()
        access = type("Access", (), {"principal":type("Principal", (), {"user_id":uuid.uuid4()})()})()

        ExportService(root, indexing_wakeup=wakes.append).save_to_workspace(object(), access, job)
        assert wakes == [job_id]
