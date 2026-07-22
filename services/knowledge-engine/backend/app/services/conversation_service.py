"""Creation and enforcement of persisted conversation context scopes."""
from __future__ import annotations

import uuid
from sqlalchemy.orm import Session

from backend.app.models.conversations import ChatSession
from backend.app.models.knowledge import Document
from backend.app.models.workspace_content import Note
from backend.app.repositories.chats import ChatRepository
from backend.app.schemas.chat import ChatSessionCreate
from backend.app.security.access import RequestAccessContext, document_is_accessible
from backend.app.services.personal_workspace_service import PersonalWorkspaceService, WorkspaceNotFound


class ConversationService:
    def __init__(self, session: Session):
        self.session = session

    def create(self, access: RequestAccessContext, payload: ChatSessionCreate) -> ChatSession:
        user_id = access.principal.user_id
        organization_id = access.principal.organization_id
        if user_id is None or organization_id is None:
            raise WorkspaceNotFound("Authenticated organization context is required.")
        workspace = PersonalWorkspaceService(self.session).get_or_create(access)
        documents: list[Document] = []
        for document_id in dict.fromkeys(payload.selected_document_ids):
            document = self.session.get(Document, document_id)
            if document is None or not document_is_accessible(document, access):
                raise WorkspaceNotFound("Selected context was not found.")
            documents.append(document)
        notes: list[Note] = []
        for note_id in dict.fromkeys(payload.selected_note_ids):
            note = self.session.get(Note, note_id)
            if note is None or note.deleted_at is not None or note.owner_user_id != user_id or note.workspace_id != workspace.id:
                raise WorkspaceNotFound("Selected context was not found.")
            notes.append(note)
        if payload.created_from_document and payload.created_from_document not in {item.id for item in documents}:
            raise ValueError("created_from_document must be included in selected_document_ids.")
        if payload.context_scope == "selected_documents" and not documents:
            raise ValueError("selected_documents context requires at least one authorized document.")
        snapshot = [
            {"id": str(item.id), "type": "document", "title": item.name, "file_type": item.file_type}
            for item in documents
        ] + [{"id": str(item.id), "type": "note", "title": item.title} for item in notes]
        session = ChatSession(
            user_id=user_id, organization_id=organization_id, workspace_id=workspace.id,
            title=" ".join(payload.title.split())[:255], origin=payload.origin,
            created_from_document=payload.created_from_document, context_scope=payload.context_scope,
            selected_document_ids=[str(item.id) for item in documents],
            selected_note_ids=[str(item.id) for item in notes], context_snapshot=snapshot,
        )
        ChatRepository(self.session).add_session(session)
        self.session.commit()
        self.session.refresh(session)
        return session

    @staticmethod
    def enforce(session: ChatSession, payload):
        if session.context_scope not in {"selected_documents", "selected_context"}:
            return payload
        return payload.model_copy(update={
            "selected_document_ids": list(session.selected_document_ids or []),
            "selected_folder_ids": [],
            "selected_note_ids": list(session.selected_note_ids or []),
        })
