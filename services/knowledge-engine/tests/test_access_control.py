from __future__ import annotations

from types import SimpleNamespace
import uuid

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from backend.app.models.knowledge import Document
from backend.app.security.access import (
    AccessPrincipal,
    RequestAccessContext,
    apply_document_access_filter,
    can_upload_enterprise_documents,
    document_is_accessible,
)
from backend.app.services.knowledge_engine_service import KnowledgeEngineService


def _access_context(
    *,
    user_id: uuid.UUID | None = None,
    department_ids: set[uuid.UUID] | None = None,
    permission_names: set[str] | None = None,
    scope: str = "enterprise",
) -> RequestAccessContext:
    return RequestAccessContext(
        principal=AccessPrincipal(
            user_id=user_id,
            department_ids=frozenset(department_ids or set()),
            permission_names=frozenset(permission_names or set()),
            is_authenticated=user_id is not None,
        ),
        scope=scope,
    )


def _document(
    *,
    storage_scope: str = "enterprise",
    visibility: str = "enterprise",
    owner_user_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    lifecycle_status: str = "indexed",
    indexing_status: str = "indexed",
) -> Document:
    organization_id = uuid.uuid4()
    return Document(
        organization_id=organization_id,
        department_id=department_id or uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        folder_id=None,
        storage_scope=storage_scope,
        owner_user_id=owner_user_id,
        name="manual.pdf",
        relative_path="Policies/manual.pdf",
        file_type="pdf",
        extension=".pdf",
        mime_type="application/pdf",
        visibility=visibility,
        size_bytes=1024,
        content_hash="a" * 64,
        indexed=True,
        indexing_status=indexing_status,
        lifecycle_status=lifecycle_status,
        source_type="corpus_sync",
    )


def test_anonymous_context_can_view_public_enterprise_document() -> None:
    document = _document()

    assert document_is_accessible(document, _access_context()) is True


def test_anonymous_context_cannot_view_personal_document() -> None:
    document = _document(
        storage_scope="personal",
        visibility="private",
        owner_user_id=uuid.uuid4(),
    )

    assert document_is_accessible(document, _access_context()) is False


def test_owner_can_view_personal_document_in_hybrid_scope() -> None:
    owner_id = uuid.uuid4()
    document = _document(
        storage_scope="personal",
        visibility="private",
        owner_user_id=owner_id,
    )

    assert document_is_accessible(
        document,
        _access_context(
            user_id=owner_id,
            permission_names={"view_own_documents"},
            scope="hybrid",
        ),
    ) is True


def test_department_document_requires_department_permission() -> None:
    department_id = uuid.uuid4()
    document = _document(
        visibility="department",
        department_id=department_id,
    )

    denied = _access_context(
        user_id=uuid.uuid4(),
        department_ids={department_id},
        scope="hybrid",
    )
    allowed = _access_context(
        user_id=uuid.uuid4(),
        department_ids={department_id},
        permission_names={"view_department_documents"},
        scope="hybrid",
    )

    assert document_is_accessible(document, denied) is False
    assert document_is_accessible(document, allowed) is True


def test_enterprise_sql_filter_requires_read_permission() -> None:
    denied = _access_context(user_id=uuid.uuid4(), scope="hybrid")
    allowed = _access_context(
        user_id=uuid.uuid4(),
        permission_names={"view_enterprise_documents"},
        scope="hybrid",
    )

    def compiled_filter(context: RequestAccessContext) -> str:
        return str(
            apply_document_access_filter(select(Document), context).compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )

    enterprise_visibility_clause = "documents.visibility = 'enterprise'"
    assert enterprise_visibility_clause not in compiled_filter(denied)
    assert enterprise_visibility_clause in compiled_filter(allowed)


def test_upload_permission_preserves_legacy_anonymous_behavior_but_checks_authenticated_users() -> None:
    anonymous = _access_context()
    denied = _access_context(user_id=uuid.uuid4(), scope="hybrid")
    allowed = _access_context(
        user_id=uuid.uuid4(),
        permission_names={"upload_enterprise_documents"},
        scope="hybrid",
    )

    assert can_upload_enterprise_documents(anonymous) is True
    assert can_upload_enterprise_documents(denied) is False
    assert can_upload_enterprise_documents(allowed) is True


def test_access_scope_filter_restricts_retrieval_candidates() -> None:
    service = KnowledgeEngineService()
    allowed = {
        "chunk_id": "allowed",
        "text": "Allowed evidence.",
        "score": 0.8,
        "metadata": {"relative_path": "Policies/allowed.pdf"},
    }
    blocked = {
        "chunk_id": "blocked",
        "text": "Blocked evidence.",
        "score": 0.6,
        "metadata": {"relative_path": "Private/blocked.pdf"},
    }

    class FakePipeline:
        def __init__(self) -> None:
            self.config = SimpleNamespace(
                retrieval_top_k=3,
                dense_top_k=3,
                bm25_top_k=3,
                reranker_candidate_top_k=3,
            )
            self.changed = 0

        def _search(self, query: str) -> list[dict[str, object]]:
            return [allowed, blocked]

        def on_config_changed(self) -> None:
            self.changed += 1

        def answer(self, question: str) -> dict[str, object]:
            results = self._search(question)
            return {
                "answer": "ok",
                "retrieved": results,
                "context_stages": {"compressed": results},
                "selected_evidence": results,
                "citations": [],
            }

    response = service._run_with_relative_path_filter(
        FakePipeline(),
        "Question?",
        frozenset({"Policies/allowed.pdf"}),
        response_key="access_scope_filter",
        filter_payload={"applied": True, "mode": "access_scope:enterprise"},
    )

    assert [item["chunk_id"] for item in response["retrieved"]] == ["allowed"]
    assert response["access_scope_filter"]["filtered_count"] == 1


def test_authorized_scope_candidate_expansion_is_bounded_before_reranking() -> None:
    service = KnowledgeEngineService()

    class FakePipeline:
        def __init__(self) -> None:
            self.config = SimpleNamespace(
                retrieval_top_k=10,
                dense_top_k=10,
                bm25_top_k=10,
                reranker_candidate_top_k=30,
            )
            self.observed = None

        def _search(self, query):
            return []

        def on_config_changed(self):
            return None

        def set_retrieval_relative_paths(self, allowed):
            return None

        def answer(self, question):
            self.observed = (
                self.config.dense_top_k,
                self.config.bm25_top_k,
                self.config.reranker_candidate_top_k,
            )
            return {
                "answer": "none",
                "answer_status": "insufficient_evidence",
                "retrieved": [],
                "context_stages": {"compressed": []},
                "selected_evidence": [],
                "citations": [],
            }

    pipeline = FakePipeline()
    allowed = frozenset(f"public/{index}.pdf" for index in range(1_000))

    response = service._run_with_relative_path_filter(
        pipeline,
        "Question?",
        allowed,
        response_key="access_scope_filter",
        filter_payload={"applied": True, "mode": "access_scope:enterprise"},
    )

    assert pipeline.observed == (250, 250, 250)
    assert response["access_scope_filter"]["candidate_floor"] == 250
