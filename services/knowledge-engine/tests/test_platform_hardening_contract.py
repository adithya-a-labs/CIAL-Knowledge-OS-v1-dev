from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from backend.app.api.routes.notes import conflict_detail
from backend.app.api.routes.summaries import router as summaries_router
from backend.app.schemas.notes import NoteUpdate
from backend.app.services.note_service import NoteConflict


def _note_payload():
    now = datetime.now(timezone.utc)
    return {
        "id": uuid.uuid4(), "title": "Concurrent note", "content_json": None,
        "content_markdown": "latest", "content_format": "markdown", "plain_text": "latest",
        "is_pinned": False, "is_archived": False, "revision": 3,
        "created_at": now, "updated_at": now, "indexing_status": "pending",
        "indexed_revision": 2, "tags": [], "linked_documents": [],
    }


def test_note_conflict_uuid_datetime_payload_is_json_safe_and_structured():
    detail = conflict_detail(NoteConflict(_note_payload()))
    encoded = json.dumps(detail)
    assert detail["code"] == "revision_conflict"
    assert detail["current"]["revision"] == 3
    assert str(detail["current"]["id"]) in encoded
    assert "+00:00" in detail["current"]["updated_at"] or detail["current"]["updated_at"].endswith("Z")


def test_note_overwrite_requires_explicit_force_flag():
    assert NoteUpdate(expected_revision=2).force is False
    assert NoteUpdate(expected_revision=2, force=True).force is True


def test_summary_static_config_routes_precede_uuid_route():
    paths = [route.path for route in summaries_router.routes]
    dynamic = paths.index("/summaries/{summary_id}")
    assert paths.index("/summaries/config") < dynamic
    assert paths.index("/summaries/new") < dynamic


def test_note_indexing_is_delayed_coalesced_and_skips_corpus_sync():
    root = Path(__file__).parents[1]
    note_service = (root / "backend/app/services/note_service.py").read_text(encoding="utf-8")
    worker = (root / "backend/app/services/indexing_worker.py").read_text(encoding="utf-8")
    assert "timedelta(seconds=3)" in note_service
    assert "pending=next" in note_service
    assert 'entity_type != "note" and self.corpus_sync' in worker
    assert "IndexingJob.available_at <=" in worker
