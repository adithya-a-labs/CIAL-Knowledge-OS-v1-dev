"""Owner-isolated, provenance-preserving Saved Knowledge operations."""
from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.models.conversations import ChatMessage, ChatSession
from backend.app.models.knowledge import Document
from backend.app.models.operations import AuditEvent
from backend.app.models.workspace_content import Note, SavedKnowledgeItem, SavedKnowledgeVersion
from backend.app.schemas.saved_knowledge import SavedKnowledgeCreate, SavedKnowledgeUpdate
from backend.app.schemas.notes import NoteUpdate
from backend.app.security.access import RequestAccessContext, document_is_accessible
from backend.app.services.personal_workspace_service import PersonalWorkspaceService, WorkspaceNotFound
from backend.app.services.note_service import NoteService


class SavedKnowledgeConflict(RuntimeError): pass


class SavedKnowledgeService:
    def __init__(self, session: Session): self.session=session
    def _scope(self, access): return access.principal.user_id, PersonalWorkspaceService(self.session).get_or_create(access)
    def _get(self, access, item_id):
        user_id,workspace=self._scope(access);item=self.session.scalar(select(SavedKnowledgeItem).where(SavedKnowledgeItem.id==item_id,SavedKnowledgeItem.owner_user_id==user_id,SavedKnowledgeItem.workspace_id==workspace.id,SavedKnowledgeItem.deleted_at.is_(None)))
        if item is None:raise WorkspaceNotFound("Saved Knowledge item not found.")
        return item
    @staticmethod
    def _clean_tags(values): return list(dict.fromkeys(" ".join(value.split()).strip()[:64] for value in values if value.strip()))[:30]
    @staticmethod
    def _citation_snapshot(values):
        allowed=("id","document_name","document_id","page","page_number","chunk_id","snippet","highlight_text","source_type","note_id","note_revision","block_id")
        return [{key:(value.get(key)[:500] if isinstance(value.get(key),str) and key in {"snippet","highlight_text"} else value.get(key)) for key in allowed if value.get(key) is not None} for value in values[:100]]
    def create_from_message(self,access,payload:SavedKnowledgeCreate):
        user_id,workspace=self._scope(access);message=self.session.scalar(select(ChatMessage).join(ChatSession).where(ChatMessage.id==payload.message_id,ChatMessage.role=="assistant",ChatSession.user_id==user_id))
        if message is None:raise WorkspaceNotFound("Assistant answer not found.")
        conversation=self.session.get(ChatSession,message.session_id);metadata=message.metadata_ or {};request=metadata.get("generation_request") or {}
        original=None
        if payload.save_original_question and metadata.get("user_message_id"):
            try: original_message=self.session.get(ChatMessage,uuid.UUID(str(metadata["user_message_id"])));original=original_message.content if original_message and original_message.session_id==conversation.id else None
            except ValueError: original=None
        citations=self._citation_snapshot(message.citations or []) if payload.save_citations else []
        sources=self._citation_snapshot(message.sources or []) if payload.save_citations else []
        selected=list(conversation.selected_document_ids or request.get("selected_document_ids") or [])
        digest=hashlib.sha256(f"{user_id}:{message.id}:{message.content}".encode()).hexdigest()
        existing=self.session.scalar(select(SavedKnowledgeItem).where(SavedKnowledgeItem.owner_user_id==user_id,SavedKnowledgeItem.provenance_hash==digest,SavedKnowledgeItem.deleted_at.is_(None)))
        if existing:return self._payload(access,existing)
        item=SavedKnowledgeItem(organization_id=workspace.organization_id,workspace_id=workspace.id,owner_user_id=user_id,item_type="answer",source_message_id=message.id,conversation_id=conversation.id,title=" ".join(payload.title.split()),description=payload.description,body_markdown=message.content,original_question=original,citation_snapshot=citations,source_references=sources,selected_document_ids=selected,context_scope=conversation.context_scope or ("selected_context" if selected else "all_accessible"),profile=metadata.get("profile"),model_name=metadata.get("model"),prompt_version=metadata.get("prompt_name"),collection=payload.collection,tags=self._clean_tags(payload.tags),visibility="private",provenance_hash=digest)
        self.session.add(item);self.session.flush();self._version(item,user_id);self._audit(user_id,"saved_knowledge.created",item.id);self.session.commit();self.session.refresh(item);return self._payload(access,item)
    def list(self,access,query="",favorite=False,collection=None,limit=50):
        user_id,workspace=self._scope(access);statement=select(SavedKnowledgeItem).where(SavedKnowledgeItem.owner_user_id==user_id,SavedKnowledgeItem.workspace_id==workspace.id,SavedKnowledgeItem.deleted_at.is_(None))
        if query.strip():statement=statement.where(or_(SavedKnowledgeItem.title.ilike(f"%{query.strip()}%"),SavedKnowledgeItem.body_markdown.ilike(f"%{query.strip()}%")))
        if favorite:statement=statement.where(SavedKnowledgeItem.is_favorite.is_(True))
        if collection:statement=statement.where(SavedKnowledgeItem.collection==collection)
        rows=list(self.session.scalars(statement.order_by(SavedKnowledgeItem.updated_at.desc()).limit(min(limit,100))))
        return {"items":[self._payload(access,item) for item in rows],"next_cursor":None}
    def get(self,access,item_id):return self._payload(access,self._get(access,item_id))
    def update(self,access,item_id,payload:SavedKnowledgeUpdate):
        item=self._get(access,item_id)
        if item.version!=payload.expected_version:raise SavedKnowledgeConflict("Saved Knowledge was updated in another session.")
        for field in ("title","collection","description","is_favorite","state"):
            value=getattr(payload,field,None)
            if value is not None:setattr(item,field," ".join(value.split()) if field=="title" else value)
        if payload.tags is not None:item.tags=self._clean_tags(payload.tags)
        item.version+=1;item.updated_at=datetime.now(timezone.utc);self._version(item,item.owner_user_id);self._audit(item.owner_user_id,"saved_knowledge.updated",item.id);self.session.commit();return self._payload(access,item)
    def delete(self,access,item_id):
        item=self._get(access,item_id);item.deleted_at=datetime.now(timezone.utc);self._audit(item.owner_user_id,"saved_knowledge.deleted",item.id);self.session.commit()
    def duplicate(self,access,item_id):
        source=self._get(access,item_id);copy=SavedKnowledgeItem(organization_id=source.organization_id,workspace_id=source.workspace_id,owner_user_id=source.owner_user_id,item_type=source.item_type,summary_id=source.summary_id,source_message_id=source.source_message_id,conversation_id=source.conversation_id,title=f"{source.title} copy",description=source.description,body_markdown=source.body_markdown,original_question=source.original_question,citation_snapshot=source.citation_snapshot,source_references=source.source_references,selected_document_ids=source.selected_document_ids,context_scope=source.context_scope,profile=source.profile,model_name=source.model_name,prompt_version=source.prompt_version,collection=source.collection,tags=source.tags,visibility="private",provenance_hash=hashlib.sha256(f"duplicate:{source.id}:{uuid.uuid4()}".encode()).hexdigest())
        self.session.add(copy);self.session.flush();self._version(copy,copy.owner_user_id);self._audit(copy.owner_user_id,"saved_knowledge.duplicated",copy.id);self.session.commit();return self._payload(access,copy)
    def convert_to_note(self,access,item_id):
        item=self._get(access,item_id);notes=NoteService(self.session);created=notes.create(access,item.title);content=f"{item.body_markdown}\n\n---\nSaved Knowledge provenance: `{item.id}`"
        note=notes.update(access,created["id"],NoteUpdate(expected_revision=created["revision"],content_markdown=content,content_format="markdown"));self._audit(item.owner_user_id,"saved_knowledge.converted_to_note",item.id);self.session.commit();return note
    def _payload(self,access,item):
        citations=[]
        for value in item.citation_snapshot or []:
            current=dict(value);document_id=current.get("document_id");available=False
            if document_id:
                try:
                    document=self.session.get(Document,uuid.UUID(str(document_id)));available=document is not None and document_is_accessible(document,access)
                except ValueError:available=False
            elif current.get("note_id"):
                try:
                    note=self.session.get(Note,uuid.UUID(str(current.get("note_id"))));available=note is not None and note.deleted_at is None and note.owner_user_id==access.principal.user_id
                except ValueError:available=False
            current["availability"]="available" if available else "unavailable";citations.append(current)
        return {"id":item.id,"item_type":item.item_type,"title":item.title,"description":item.description,"body_markdown":item.body_markdown,"original_question":item.original_question,"citations":citations,"source_references":item.source_references or [],"selected_document_ids":item.selected_document_ids or [],"context_scope":item.context_scope,"conversation_id":item.conversation_id,"source_message_id":item.source_message_id,"summary_id":item.summary_id,"profile":item.profile,"model_name":item.model_name,"prompt_version":item.prompt_version,"collection":item.collection,"tags":item.tags or [],"visibility":item.visibility,"is_favorite":item.is_favorite,"version":item.version,"state":item.state,"source_count":len(item.citation_snapshot or []),"created_at":item.created_at,"updated_at":item.updated_at}
    def _version(self,item,user_id):self.session.add(SavedKnowledgeVersion(saved_knowledge_id=item.id,version=item.version,title=item.title,description=item.description,body_markdown=item.body_markdown,citation_snapshot=item.citation_snapshot or [],tags=item.tags or [],created_by_user_id=user_id))
    def _audit(self,user_id,action,entity_id):self.session.add(AuditEvent(user_id=user_id,actor_user_id=user_id,action=action,entity_type="saved_knowledge",entity_id=entity_id,status="succeeded"))
