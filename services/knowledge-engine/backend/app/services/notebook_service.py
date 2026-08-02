"""Owner-scoped notebook orchestration around existing CIAL services."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models.conversations import ChatSession
from backend.app.models.knowledge import Document
from backend.app.models.notebooks import Notebook, NotebookArtifact, NotebookSession, NotebookSource
from backend.app.models.operations import AuditEvent
from backend.app.models.workspace_content import Note, NoteIndexState, SummaryArtifact
from backend.app.schemas.notebooks import NotebookArtifactCreate, NotebookCreate, NotebookSourceAttach, NotebookUpdate
from backend.app.schemas.summaries import SummaryCreate, SummarySourceRequest
from backend.app.security.access import RequestAccessContext, apply_document_access_filter
from backend.app.services.personal_workspace_service import PersonalWorkspaceService, WorkspaceNotFound
from backend.app.services.summary_service import SummaryService


class NotebookNotFound(WorkspaceNotFound):
    pass


def _clean(value: str) -> str:
    return " ".join(value.split())


class NotebookService:
    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _identity(access: RequestAccessContext) -> tuple[uuid.UUID, uuid.UUID]:
        if access.principal.user_id is None or access.principal.organization_id is None:
            raise NotebookNotFound("Notebook was not found.")
        return access.principal.user_id, access.principal.organization_id

    def get(self, access: RequestAccessContext, notebook_id: uuid.UUID) -> Notebook:
        user_id, organization_id = self._identity(access)
        item = self.session.scalar(select(Notebook).where(
            Notebook.id == notebook_id,
            Notebook.owner_user_id == user_id,
            Notebook.organization_id == organization_id,
            Notebook.lifecycle_status != "deleted",
            Notebook.deleted_at.is_(None),
        ))
        if item is None:
            raise NotebookNotFound("Notebook was not found.")
        return item

    def create(self, access: RequestAccessContext, payload: NotebookCreate) -> Notebook:
        user_id, organization_id = self._identity(access)
        workspace = PersonalWorkspaceService(self.session).get_or_create(access)
        notebook = Notebook(
            organization_id=organization_id, workspace_id=workspace.id,
            owner_user_id=user_id, created_by_user_id=user_id, updated_by_user_id=user_id,
            title=_clean(payload.title)[:255], description=_clean(payload.description)[:2000] if payload.description else None,
            visibility="private", lifecycle_status="active", metadata_={},
        )
        self.session.add(notebook)
        self.session.flush()
        chat = ChatSession(
            user_id=user_id, organization_id=organization_id, workspace_id=workspace.id,
            title=notebook.title, origin="assistant", context_scope="selected_context",
            selected_document_ids=[], selected_note_ids=[], context_snapshot=[],
        )
        self.session.add(chat)
        self.session.flush()
        self.session.add(NotebookSession(notebook_id=notebook.id, chat_session_id=chat.id))
        self._audit(user_id, "notebook_created", notebook.id, {"source_count": 0, "active_count": 0})
        self.session.commit()
        self.session.refresh(notebook)
        return notebook

    def list(self, access: RequestAccessContext) -> list[Notebook]:
        user_id, organization_id = self._identity(access)
        return list(self.session.scalars(select(Notebook).where(
            Notebook.owner_user_id == user_id, Notebook.organization_id == organization_id,
            Notebook.lifecycle_status != "deleted", Notebook.deleted_at.is_(None),
        ).order_by(Notebook.updated_at.desc())))

    def update(self, access: RequestAccessContext, notebook_id: uuid.UUID, payload: NotebookUpdate) -> Notebook:
        item = self.get(access, notebook_id)
        if payload.title is not None:
            item.title = _clean(payload.title)[:255]
        if "description" in payload.model_fields_set:
            item.description = _clean(payload.description)[:2000] if payload.description else None
        item.updated_by_user_id = access.principal.user_id
        binding = self.session.get(NotebookSession, item.id)
        if binding and payload.title is not None:
            chat = self.session.get(ChatSession, binding.chat_session_id)
            if chat is not None:
                chat.title = item.title
        self.session.commit(); self.session.refresh(item)
        return item

    def delete(self, access: RequestAccessContext, notebook_id: uuid.UUID) -> None:
        item = self.get(access, notebook_id)
        item.deleted_at = datetime.now(timezone.utc)
        item.lifecycle_status = "deleted"
        item.updated_by_user_id = access.principal.user_id
        self._audit(access.principal.user_id, "notebook_deleted", item.id, None)
        self.session.commit()

    def payload(self, item: Notebook) -> dict:
        source_count = self.session.scalar(select(func.count(NotebookSource.id)).where(NotebookSource.notebook_id == item.id)) or 0
        active_count = self.session.scalar(select(func.count(NotebookSource.id)).where(NotebookSource.notebook_id == item.id, NotebookSource.is_default_active.is_(True))) or 0
        artifact_count = self.session.scalar(select(func.count(NotebookArtifact.id)).where(NotebookArtifact.notebook_id == item.id)) or 0
        binding = self.session.get(NotebookSession, item.id)
        return {
            "id": item.id, "organization_id": item.organization_id, "workspace_id": item.workspace_id,
            "title": item.title, "description": item.description, "visibility": item.visibility,
            "lifecycle_status": item.lifecycle_status, "source_count": source_count,
            "active_source_count": active_count, "artifact_count": artifact_count,
            "chat_session_id": binding.chat_session_id if binding else None,
            "created_at": item.created_at, "updated_at": item.updated_at,
            "last_activity_at": item.updated_at,
        }

    def _audit(self, user_id: uuid.UUID | None, action: str, entity_id: uuid.UUID, metadata: dict | None) -> None:
        self.session.add(AuditEvent(user_id=user_id, actor_user_id=user_id, action=action, entity_type="notebook", entity_id=entity_id, metadata_=metadata, status="succeeded"))


class NotebookSourceService:
    def __init__(self, session: Session):
        self.session = session
        self.notebooks = NotebookService(session)

    def _document(self, access: RequestAccessContext, document_id: uuid.UUID) -> Document:
        item = self.session.scalar(apply_document_access_filter(select(Document).where(Document.id == document_id), access))
        if item is None:
            raise NotebookNotFound("Source was not found.")
        return item

    def _note(self, access: RequestAccessContext, note_id: uuid.UUID) -> Note:
        user_id, _ = self.notebooks._identity(access)
        item = self.session.scalar(select(Note).where(Note.id == note_id, Note.owner_user_id == user_id, Note.deleted_at.is_(None)))
        if item is None:
            raise NotebookNotFound("Source was not found.")
        return item

    def _note_ready(self, note: Note) -> tuple[bool, str]:
        state = self.session.get(NoteIndexState, note.id)
        ready = bool(state and state.status == "indexed" and state.indexed_revision == note.revision)
        return ready, state.status if state else "pending"

    def _summary(self, access: RequestAccessContext, summary_id: uuid.UUID) -> SummaryArtifact:
        user_id, _ = self.notebooks._identity(access)
        item = self.session.scalar(select(SummaryArtifact).where(SummaryArtifact.id == summary_id, SummaryArtifact.owner_user_id == user_id, SummaryArtifact.deleted_at.is_(None)))
        if item is None:
            raise NotebookNotFound("Source was not found.")
        return item

    def attach(self, access: RequestAccessContext, notebook_id: uuid.UUID, values: list[NotebookSourceAttach]) -> list[NotebookSource]:
        notebook = self.notebooks.get(access, notebook_id)
        position_value = self.session.scalar(select(func.coalesce(func.max(NotebookSource.position), -1)).where(NotebookSource.notebook_id == notebook.id))
        position = int(position_value if position_value is not None else -1)
        added: list[NotebookSource] = []
        for value in values:
            target_id = value.document_id or value.note_id or value.summary_artifact_id
            target_column = {"document": NotebookSource.document_id, "note": NotebookSource.note_id, "summary": NotebookSource.summary_artifact_id}[value.source_type]
            existing = self.session.scalar(select(NotebookSource).where(NotebookSource.notebook_id == notebook.id, target_column == target_id))
            if existing is not None:
                existing.is_default_active = existing.is_default_active or value.is_default_active
                added.append(existing)
                continue
            if value.source_type == "document": self._document(access, value.document_id)
            elif value.source_type == "note": self._note(access, value.note_id)
            else: self._summary(access, value.summary_artifact_id)
            position += 1
            row = NotebookSource(
                notebook_id=notebook.id, source_type=value.source_type,
                document_id=value.document_id, note_id=value.note_id, summary_artifact_id=value.summary_artifact_id,
                attached_by_user_id=access.principal.user_id, position=position,
                is_default_active=value.is_default_active,
            )
            self.session.add(row); added.append(row)
        try:
            self.session.flush()
        except IntegrityError as exc:
            self.session.rollback(); raise ValueError("A source was already attached.") from exc
        notebook.updated_by_user_id = access.principal.user_id
        notebook.updated_at = datetime.now(timezone.utc)
        self.sync_chat(access, notebook.id)
        self.notebooks._audit(access.principal.user_id, "notebook_source_attached", notebook.id, {"attached_count": len(values)})
        self.session.commit()
        return added

    def list(self, access: RequestAccessContext, notebook_id: uuid.UUID) -> list[NotebookSource]:
        self.notebooks.get(access, notebook_id)
        rows = list(self.session.scalars(select(NotebookSource).where(NotebookSource.notebook_id == notebook_id).order_by(NotebookSource.position, NotebookSource.created_at)))
        self.sync_chat(access, notebook_id)
        self.session.commit()
        return rows

    def update(self, access: RequestAccessContext, notebook_id: uuid.UUID, source_id: uuid.UUID, active: bool) -> NotebookSource:
        self.notebooks.get(access, notebook_id)
        row = self.session.scalar(select(NotebookSource).where(NotebookSource.id == source_id, NotebookSource.notebook_id == notebook_id))
        if row is None: raise NotebookNotFound("Source was not found.")
        row.is_default_active = active
        self.sync_chat(access, notebook_id); self.session.commit(); self.session.refresh(row)
        return row

    def detach(self, access: RequestAccessContext, notebook_id: uuid.UUID, source_id: uuid.UUID) -> None:
        self.notebooks.get(access, notebook_id)
        row = self.session.scalar(select(NotebookSource).where(NotebookSource.id == source_id, NotebookSource.notebook_id == notebook_id))
        if row is None: raise NotebookNotFound("Source was not found.")
        self.session.delete(row); self.session.flush(); self.sync_chat(access, notebook_id)
        self.notebooks._audit(access.principal.user_id, "notebook_source_detached", notebook_id, None)
        self.session.commit()

    def reorder(self, access: RequestAccessContext, notebook_id: uuid.UUID, source_ids: list[uuid.UUID]) -> list[NotebookSource]:
        rows = self.list(access, notebook_id)
        if set(source_ids) != {row.id for row in rows}: raise ValueError("Source order must include every attached source exactly once.")
        by_id = {row.id: row for row in rows}
        for position, source_id in enumerate(source_ids): by_id[source_id].position = position
        self.session.commit()
        return [by_id[source_id] for source_id in source_ids]

    def sync_chat(self, access: RequestAccessContext, notebook_id: uuid.UUID) -> ChatSession:
        binding = NotebookChatBindingService(self.session).get_or_create(access, notebook_id, commit=False)
        chat = self.session.get(ChatSession, binding.chat_session_id)
        documents: list[Document] = []; notes: list[Note] = []
        for row in self.session.scalars(select(NotebookSource).where(NotebookSource.notebook_id == notebook_id, NotebookSource.is_default_active.is_(True)).order_by(NotebookSource.position)):
            if row.document_id:
                try:
                    document = self._document(access, row.document_id)
                except NotebookNotFound:
                    continue
                if document.indexed and document.indexing_status == "indexed" and document.lifecycle_status == "indexed": documents.append(document)
            elif row.note_id:
                try:
                    note = self._note(access, row.note_id)
                except NotebookNotFound: continue
                if self._note_ready(note)[0]: notes.append(note)
        chat.context_scope = "selected_context"
        chat.selected_document_ids = [str(item.id) for item in documents]
        chat.selected_note_ids = [str(item.id) for item in notes]
        chat.context_snapshot = ([{"id": str(item.id), "type": "document", "title": item.name, "file_type": item.file_type} for item in documents] + [{"id": str(item.id), "type": "note", "title": item.title} for item in notes])
        return chat

    def payload(self, access: RequestAccessContext, row: NotebookSource) -> dict:
        common = {"id": row.id, "notebook_id": row.notebook_id, "source_type": row.source_type, "position": row.position, "is_default_active": row.is_default_active, "created_at": row.created_at}
        if row.document_id:
            try: item = self._document(access, row.document_id)
            except NotebookNotFound:
                return {**common, "target_id": row.document_id, "title": "Unavailable source", "origin": "knowledge_center", "available": False, "ready": False, "unavailable_reason": "Access was revoked or the document was removed."}
            ready = bool(item.indexed and item.indexing_status == "indexed" and item.lifecycle_status == "indexed")
            return {**common, "target_id": item.id, "title": item.name, "origin": "my_workspace" if item.storage_scope == "personal" else "knowledge_center", "available": True, "ready": ready, "indexing_status": item.indexing_status, "file_type": item.file_type, "mime_type": item.mime_type, "page_count": item.page_count, "size_bytes": item.size_bytes, "preview_document_id": item.id}
        if row.note_id:
            try: note = self._note(access, row.note_id)
            except NotebookNotFound: return {**common, "target_id": row.note_id, "title": "Unavailable note", "origin": "note", "available": False, "ready": False, "unavailable_reason": "Access was revoked or the note was removed."}
            ready, status = self._note_ready(note)
            return {**common, "target_id": note.id, "title": note.title, "origin": "note", "available": True, "ready": ready, "indexing_status": status}
        try: summary = self._summary(access, row.summary_artifact_id)
        except NotebookNotFound: return {**common, "target_id": row.summary_artifact_id, "title": "Unavailable summary", "origin": "summary", "available": False, "ready": False, "unavailable_reason": "The summary was removed."}
        return {**common, "target_id": summary.id, "title": summary.title, "origin": "summary", "available": True, "ready": summary.status == "completed", "indexing_status": summary.status}


class NotebookChatBindingService:
    def __init__(self, session: Session): self.session = session; self.notebooks = NotebookService(session)

    def get_or_create(self, access: RequestAccessContext, notebook_id: uuid.UUID, *, commit: bool = True) -> NotebookSession:
        notebook = self.notebooks.get(access, notebook_id)
        binding = self.session.get(NotebookSession, notebook.id)
        if binding is not None:
            chat = self.session.get(ChatSession, binding.chat_session_id)
            if chat is not None and chat.user_id == access.principal.user_id: return binding
            raise NotebookNotFound("Notebook chat was not found.")
        chat = ChatSession(user_id=access.principal.user_id, organization_id=notebook.organization_id, workspace_id=notebook.workspace_id, title=notebook.title, origin="assistant", context_scope="selected_context", selected_document_ids=[], selected_note_ids=[], context_snapshot=[])
        self.session.add(chat); self.session.flush()
        binding = NotebookSession(notebook_id=notebook.id, chat_session_id=chat.id); self.session.add(binding); self.session.flush()
        self.notebooks._audit(access.principal.user_id, "notebook_chat_bound", notebook.id, None)
        if commit: self.session.commit(); self.session.refresh(binding)
        return binding

    def payload(self, access: RequestAccessContext, binding: NotebookSession) -> dict:
        chat = self.session.get(ChatSession, binding.chat_session_id)
        if chat is None or chat.user_id != access.principal.user_id: raise NotebookNotFound("Notebook chat was not found.")
        return {"notebook_id": binding.notebook_id, "chat_session_id": binding.chat_session_id, "selected_document_ids": [uuid.UUID(value) for value in chat.selected_document_ids or []], "selected_note_ids": [uuid.UUID(value) for value in chat.selected_note_ids or []], "context_snapshot": chat.context_snapshot or [], "created_at": binding.created_at}


class NotebookArtifactService:
    def __init__(self, session: Session, generator): self.session = session; self.notebooks = NotebookService(session); self.sources = NotebookSourceService(session); self.generator = generator

    def list(self, access, notebook_id):
        self.notebooks.get(access, notebook_id)
        return list(self.session.scalars(select(NotebookArtifact).where(NotebookArtifact.notebook_id == notebook_id).order_by(NotebookArtifact.created_at.desc())))

    def create(self, access: RequestAccessContext, notebook_id: uuid.UUID, payload: NotebookArtifactCreate) -> NotebookArtifact:
        notebook = self.notebooks.get(access, notebook_id)
        active = [row for row in self.sources.list(access, notebook_id) if row.is_default_active and row.source_type in {"document", "note"}]
        requests = []; snapshot = []
        for row in active:
            projected = self.sources.payload(access, row)
            if not projected.get("ready"): continue
            target_id = row.document_id or row.note_id
            requests.append(SummarySourceRequest(source_type=row.source_type, source_id=target_id))
            version = None
            if row.document_id:
                document = self.sources._document(access, row.document_id); version = str(document.current_version_id) if document.current_version_id else None
            elif row.note_id:
                note = self.sources._note(access, row.note_id); version = note.revision
            snapshot.append({"source_type": row.source_type, "source_id": str(target_id), "version": version})
        if not requests: raise ValueError("Select at least one ready document or note source.")
        summary_type = "detailed" if payload.artifact_type == "comparison" else payload.artifact_type
        mode = "compare" if payload.artifact_type == "comparison" else "together"
        result = SummaryService(self.session, self.generator).create(access, SummaryCreate(sources=requests, summary_type=summary_type, summary_length=payload.summary_length, multi_document_mode=mode, custom_instructions=payload.custom_instructions, title=payload.title or f"{notebook.title} {payload.artifact_type.replace('_', ' ').title()}"))
        artifact = NotebookArtifact(notebook_id=notebook.id, artifact_type=payload.artifact_type, status=result["status"], title=result["title"], source_snapshot=snapshot, summary_artifact_id=result["id"], created_by_user_id=access.principal.user_id, metadata_={})
        self.session.add(artifact); self.notebooks._audit(access.principal.user_id, "notebook_artifact_completed" if result["status"] == "completed" else "notebook_artifact_started", notebook.id, {"artifact_type": payload.artifact_type, "artifact_status": result["status"]}); self.session.commit(); self.session.refresh(artifact)
        return artifact

    def get(self, access, notebook_id, artifact_id):
        self.notebooks.get(access, notebook_id)
        item = self.session.scalar(select(NotebookArtifact).where(NotebookArtifact.id == artifact_id, NotebookArtifact.notebook_id == notebook_id))
        if item is None: raise NotebookNotFound("Artifact was not found.")
        return item

    def delete(self, access, notebook_id, artifact_id):
        item = self.get(access, notebook_id, artifact_id); self.session.delete(item); self.session.commit()

    def payload(self, item: NotebookArtifact):
        summary = self.session.get(SummaryArtifact, item.summary_artifact_id) if item.summary_artifact_id else None
        if summary is not None:
            item.status = summary.status; item.error_code = summary.error_code
        return {"id": item.id, "notebook_id": item.notebook_id, "artifact_type": item.artifact_type, "status": item.status, "title": item.title, "source_snapshot": item.source_snapshot, "summary_artifact_id": item.summary_artifact_id, "note_id": item.note_id, "citation_count": summary.citation_count if summary else 0, "source_count": len(item.source_snapshot), "error_code": item.error_code, "created_at": item.created_at, "updated_at": item.updated_at}
