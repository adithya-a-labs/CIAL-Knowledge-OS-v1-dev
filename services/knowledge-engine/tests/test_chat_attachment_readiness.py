from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch
import uuid

import pytest

from backend.app.schemas.chat import ChatRequest
from backend.app.services.knowledge_engine_service import KnowledgeEngineDocumentsNotReady, KnowledgeEngineInvalidRequest, KnowledgeEngineService


class Session:
    def __enter__(self): return self
    def __exit__(self,*args): return None


def request(document_id: uuid.UUID, scope="current_upload"):
    return ChatRequest(question="What is unique?",search_scope=scope,selected_document_ids=[str(document_id)])


def document(document_id: uuid.UUID,status: str):
    return SimpleNamespace(id=document_id,name="chat-brief.txt",relative_path="org/user/chat_uploads/brief.txt",
        indexed=status=="indexed",indexing_status=status,lifecycle_status=status)


def test_pending_and_failed_explicit_attachments_are_blocked_by_backend():
    service=KnowledgeEngineService();document_id=uuid.uuid4();access=SimpleNamespace()
    with patch("backend.app.services.knowledge_engine_service.SessionLocal",lambda:Session()):
        for state in ("pending","indexing","failed"):
            with patch.object(service,"_document_for_context_id",return_value=document(document_id,state)):
                with pytest.raises(KnowledgeEngineDocumentsNotReady) as error:
                    service._resolve_selected_context(request(document_id),access_context=access)
                assert error.value.documents==[{"document_id":str(document_id),"name":"chat-brief.txt","indexing_status":state}]


def test_attachment_becomes_generation_eligible_automatically_when_indexed():
    service=KnowledgeEngineService();document_id=uuid.uuid4();access=SimpleNamespace()
    with patch("backend.app.services.knowledge_engine_service.SessionLocal",lambda:Session()), patch.object(service,"_document_for_context_id",return_value=document(document_id,"indexed")):
        scope=service._resolve_selected_context(request(document_id),access_context=access)
    assert scope.applied and scope.effective_document_ids==(str(document_id),)
    assert scope.allowed_relative_paths==frozenset({"org/user/chat_uploads/brief.txt"})


def test_current_upload_scope_requires_final_managed_document_id():
    service=KnowledgeEngineService()
    with pytest.raises(KnowledgeEngineInvalidRequest,match="requires at least one"):
        service._resolve_selected_context(ChatRequest(question="question",search_scope="current_upload"),access_context=SimpleNamespace())
