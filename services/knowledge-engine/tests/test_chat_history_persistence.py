from __future__ import annotations

from pathlib import Path
import uuid

from sqlalchemy.dialects import postgresql

from backend.app.repositories.chats import ChatRepository
from backend.app.schemas.chat import ChatRequest


ROOT = Path(__file__).resolve().parents[3]
CONTEXT_SOURCE = ROOT / "frontend/src/components/assistant/AssistantSessionContext.tsx"
CHAT_SOURCE = ROOT / "frontend/src/components/assistant/ChatPanel.tsx"


class RecordingSession:
    def __init__(self) -> None:
        self.statements = []

    def scalar(self, statement):
        self.statements.append(statement)
        return None

    def scalars(self, statement):
        self.statements.append(statement)
        return []


def sql(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


def test_list_read_and_message_queries_enforce_user_ownership() -> None:
    database = RecordingSession()
    repository = ChatRepository(database)  # type: ignore[arg-type]
    user_id, session_id = uuid.uuid4(), uuid.uuid4()

    repository.list_sessions_for_user(user_id)
    repository.get_session_for_user(session_id, user_id)
    repository.list_messages_for_user(session_id, user_id)

    compiled = [sql(statement) for statement in database.statements]
    assert all(str(user_id) in statement for statement in compiled)
    assert str(session_id) in compiled[1]
    assert str(session_id) in compiled[2]


def test_chat_contract_accepts_stable_session_and_context_profile_metadata() -> None:
    session_id = uuid.uuid4()
    payload = ChatRequest(
        session_id=session_id,
        question="Persist me",
        selected_document_ids=["document-1"],
        selected_folder_ids=["folder-1"],
        profile="operational",
    )
    assert payload.session_id == session_id
    assert payload.selected_document_ids == ["document-1"]
    assert payload.selected_folder_ids == ["folder-1"]
    assert payload.profile == "operational"


def test_refresh_remount_and_backend_restart_hydrate_from_api_not_browser_storage() -> None:
    source = CONTEXT_SOURCE.read_text(encoding="utf-8")
    assert "listChatSessions(controller.signal)" in source
    assert "cial-assistant-sessions" not in source
    assert "INITIAL_ASSISTANT_MESSAGES" not in source


def test_empty_database_is_a_real_empty_state_without_demo_conversation() -> None:
    source = CONTEXT_SOURCE.read_text(encoding="utf-8")
    history = (ROOT / "frontend/src/components/assistant/ConversationHistory.tsx").read_text(encoding="utf-8")
    assert "useState<AssistantSession[]>([])" in source
    assert "No conversations yet" in history
    assert "Runway edge light not working" not in source


def test_api_failure_preserves_current_history_and_is_recoverable() -> None:
    source = CONTEXT_SOURCE.read_text(encoding="utf-8")
    assert "setHistoryError" in source
    assert "setSessions(hydrated)" in source
    catch_block = source.split(".catch((error: unknown) =>", 1)[1].split(".finally", 1)[0]
    assert "setSessions" not in catch_block
    assert "retryHistory" in source


def test_slow_response_and_user_switch_guards_are_present() -> None:
    context = CONTEXT_SOURCE.read_text(encoding="utf-8")
    chat = CHAT_SOURCE.read_text(encoding="utf-8")
    assert "generation !== requestGeneration.current" in context
    assert "previousUser.current !== user.id" in context
    assert "updateSession(requestSessionId" in chat


def test_production_chat_paths_do_not_use_demo_or_default_conversations() -> None:
    production_sources = [
        CONTEXT_SOURCE,
        CHAT_SOURCE,
        ROOT / "frontend/src/components/common/CommandPalette.tsx",
        ROOT / "frontend/src/components/dashboard/blocks/AIConversationsBlock.tsx",
        ROOT / "frontend/src/pages/WorkspacePage.tsx",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in production_sources)
    assert "INITIAL_ASSISTANT_MESSAGES" not in combined
    assert "MOCK_CHAT_SOURCES" not in combined
    assert "MY_CONVERSATIONS" not in combined
    assert "cial-assistant-sessions" not in combined
