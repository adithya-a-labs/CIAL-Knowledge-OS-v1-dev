from __future__ import annotations

from pathlib import Path
import tempfile
import uuid

from backend.app.services.export_service import ExportService
from cial_knowledge_os.corpus.watcher import CorpusWatcher


def test_watcher_stability_accepts_closed_file_and_deleted_path():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "document.pdf"
        path.write_bytes(b"complete")
        assert CorpusWatcher._wait_until_stable(path, attempts=2, interval=0)
        path.unlink()
        assert CorpusWatcher._wait_until_stable(path, attempts=2, interval=0)


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
