from pathlib import Path

from backend.app.api.routes.search import router as search_router
from backend.app.api.routes.saved_knowledge import router as saved_router
from backend.app.models.conversations import ChatSession
from backend.app.models.operations import SearchHistory
from backend.app.models.workspace_content import SavedKnowledgeItem, SavedKnowledgeVersion
from backend.app.schemas.chat import ChatSessionCreate
from backend.app.schemas.saved_knowledge import SavedKnowledgeCreate
from backend.app.schemas.search import SearchRequest
from backend.app.services.conversation_service import ConversationService
from backend.app.services.search_service import _excerpt, _rank, normalize_query


def test_search_normalization_and_ranking_are_stable_and_user_facing():
    assert normalize_query("  Fire—Safety!!! ") == "fire safety"
    exact, reasons = _rank("Fire Safety", None, "fire safety")
    phrase, _ = _rank("Airport Fire Safety Manual", None, "fire safety")
    body, _ = _rank("Manual", "Fire safety procedure", "fire safety")
    assert exact > phrase > body > 0
    assert reasons == ["Exact title"]
    assert len(_excerpt("x " * 500, "missing") or "") <= 321


def test_search_contract_is_bounded_and_routes_are_typed():
    payload = SearchRequest(query="recent fire procedures", limit=50)
    assert payload.limit == 50
    assert {route.path for route in search_router.routes} >= {"/search", "/search/recent", "/search/recent/{history_id}"}
    assert SearchHistory.__table__.c.user_id.nullable is False


def test_persisted_session_context_overrides_client_scope():
    session = ChatSession(context_scope="selected_documents", selected_document_ids=["doc-a"], selected_note_ids=[])
    request = type("Request", (), {"model_copy": lambda self, update: update})()
    enforced = ConversationService.enforce(session, request)
    assert enforced["selected_document_ids"] == ["doc-a"]
    assert enforced["selected_folder_ids"] == []
    create = ChatSessionCreate(title="Document chat", origin="knowledge_center", context_scope="selected_documents", selected_document_ids=["7b5e42a3-513f-4fb2-890d-906f9715fbc8"])
    assert create.origin == "knowledge_center"


def test_saved_knowledge_is_a_versioned_answer_asset_not_summary_bookmark_only():
    assert SavedKnowledgeItem.__table__.c.body_markdown.nullable is False
    assert SavedKnowledgeItem.__table__.c.summary_id.nullable is True
    assert SavedKnowledgeVersion.__table__.c.saved_knowledge_id.nullable is False
    create = SavedKnowledgeCreate(message_id="7b5e42a3-513f-4fb2-890d-906f9715fbc8", title="Grounded answer")
    assert create.save_citations is True
    assert {route.path for route in saved_router.routes} >= {"/saved-knowledge", "/saved-knowledge/{item_id}", "/saved-knowledge/{item_id}/convert-to-note"}


def test_platform_migration_is_reversible_and_indexes_search_assets():
    migration = (Path(__file__).parents[1] / "alembic/versions/20260722_0013_platform_hardening.py").read_text(encoding="utf-8")
    assert 'down_revision = "20260721_0012"' in migration
    assert "search_history" in migration
    assert "saved_knowledge_versions" in migration
    assert "ix_saved_knowledge_title_search" in migration
    assert "def downgrade" in migration
