from pathlib import Path
import uuid

import pytest
from pydantic import ValidationError

from backend.app.models.conversations import ChatSession
from backend.app.models.notebooks import Notebook, NotebookArtifact, NotebookSession, NotebookSource
from backend.app.schemas.notebooks import NotebookCreate, NotebookSourceAttach, NotebookSourceReorder
from backend.app.services.conversation_service import ConversationService


ROOT = Path(__file__).parents[1]


def test_notebook_models_are_owner_scoped_reference_only_records():
    assert Notebook.__table__.c.owner_user_id.nullable is False
    assert Notebook.__table__.c.workspace_id.nullable is False
    assert Notebook.__table__.c.visibility.server_default.arg == "private"
    assert "content" not in NotebookSource.__table__.c
    assert "relative_path" not in NotebookSource.__table__.c
    assert "embedding" not in NotebookSource.__table__.c
    assert NotebookSession.__table__.c.notebook_id.primary_key
    assert NotebookArtifact.__table__.c.source_snapshot.nullable is False


def test_notebook_source_requires_exactly_one_matching_target():
    document_id = uuid.uuid4()
    payload = NotebookSourceAttach(source_type="document", document_id=document_id)
    assert payload.document_id == document_id
    with pytest.raises(ValidationError):
        NotebookSourceAttach(source_type="document", note_id=uuid.uuid4())
    with pytest.raises(ValidationError):
        NotebookSourceAttach(source_type="note", document_id=document_id, note_id=uuid.uuid4())


def test_source_reorder_rejects_duplicate_ids():
    source_id = uuid.uuid4()
    with pytest.raises(ValidationError):
        NotebookSourceReorder(source_ids=[source_id, source_id])


def test_titles_are_bounded_and_security_fields_are_forbidden():
    assert NotebookCreate(title="Operations review").title == "Operations review"
    with pytest.raises(ValidationError):
        NotebookCreate(title="Operations review", owner_user_id=uuid.uuid4())
    with pytest.raises(ValidationError):
        NotebookCreate(title="x" * 256)


def test_migration_is_additive_reversible_and_uses_latest_head():
    migration = (ROOT / "alembic/versions/20260802_0019_notebook_workspaces.py").read_text(encoding="utf-8")
    assert 'down_revision = "20260729_0018"' in migration
    for table in ("notebooks", "notebook_sources", "notebook_sessions", "notebook_artifacts"):
        assert f'"{table}"' in migration
    assert "num_nonnulls(document_id,note_id,summary_artifact_id) = 1" in migration
    assert "def downgrade()" in migration
    assert 'op.drop_table("notebooks")' in migration


def test_notebook_chat_binding_reuses_existing_chat_context_contract():
    session = ChatSession(
        id=uuid.uuid4(), user_id=uuid.uuid4(), title="Notebook",
        context_scope="selected_context", selected_document_ids=[str(uuid.uuid4())],
        selected_note_ids=[str(uuid.uuid4())], context_snapshot=[],
    )
    from backend.app.schemas.chat import ChatRequest
    payload = ChatRequest(question="Question", selected_document_ids=[str(uuid.uuid4())])
    enforced = ConversationService.enforce(session, payload)
    assert enforced.selected_document_ids == session.selected_document_ids
    assert enforced.selected_note_ids == session.selected_note_ids
    assert enforced.selected_folder_ids == []


def test_notebook_router_adds_no_stream_or_preview_fork():
    routes = (ROOT / "backend/app/api/routes/notebooks.py").read_text(encoding="utf-8")
    assert '"/notebooks/{notebook_id}/chat-session"' in routes
    assert "/chat/stream" not in routes
    assert "/preview" not in routes
    service = (ROOT / "backend/app/services/notebook_service.py").read_text(encoding="utf-8")
    assert "SummaryService" in service
    assert "apply_document_access_filter" in service
    assert "qdrant" not in service.casefold()


def test_frontend_composes_existing_assistant_viewer_notes_and_real_apis():
    page = (ROOT.parents[1] / "frontend/src/pages/NotebookWorkspacePage.tsx").read_text(encoding="utf-8")
    assert "AssistantSessionsProvider" in page and "<ChatPanel contextLocked" in page
    assert "SourceViewerPanel" in page and "DocumentViewerPanel" in page
    assert "<NotesWorkspace" in page
    assert "uploadMyWorkspaceFiles" in page and "getCorpusTree" in page
    assert "demo" not in page.casefold()
