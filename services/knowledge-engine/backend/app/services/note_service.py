"""Owner-scoped private note operations with optimistic revisions."""
from __future__ import annotations
import base64, hashlib, re, uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.knowledge import Document
from backend.app.models.operations import AuditEvent, IndexingJob
from backend.app.models.workspace_content import Note, NoteDocumentLink, NoteIndexState, NoteTag, NoteTagLink, NoteVersion
from backend.app.security.access import RequestAccessContext, apply_document_access_filter, document_is_accessible
from backend.app.services.personal_workspace_service import PersonalWorkspaceService, WorkspaceNotFound

class NoteConflict(RuntimeError):
    def __init__(self, current: dict): super().__init__("This note was updated in another session."); self.current = current

def _plain(markdown: str) -> str:
    value = re.sub(r"<[^>]+>", " ", markdown)
    value = re.sub(r"[`*_>#\[\]()~-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()

class NoteService:
    def __init__(self, session: Session): self.session = session; self.last_index_job_id: uuid.UUID | None = None
    def _scope(self, access: RequestAccessContext):
        workspace = PersonalWorkspaceService(self.session).get_or_create(access)
        return access.principal.user_id, workspace
    def _get(self, access, note_id: uuid.UUID, include_deleted=False):
        user_id, workspace = self._scope(access)
        clauses=[Note.id==note_id, Note.owner_user_id==user_id, Note.workspace_id==workspace.id]
        if not include_deleted: clauses.append(Note.deleted_at.is_(None))
        note=self.session.scalar(select(Note).where(*clauses))
        if note is None: raise WorkspaceNotFound("Note not found.")
        return note
    def _payload(self, note: Note, access: RequestAccessContext):
        tags=list(self.session.execute(select(NoteTag).join(NoteTagLink, NoteTagLink.tag_id==NoteTag.id).where(NoteTagLink.note_id==note.id)).scalars())
        linked_statement=select(Document).join(NoteDocumentLink, NoteDocumentLink.document_id==Document.id).where(NoteDocumentLink.note_id==note.id, Document.deleted_at.is_(None))
        docs=list(self.session.scalars(apply_document_access_filter(linked_statement,access)))
        state=self.session.get(NoteIndexState,note.id)
        return {"id":note.id,"title":note.title,"content_json":note.content_json,"content_markdown":note.content_markdown,"content_format":note.content_format,"plain_text":note.plain_text,"is_pinned":note.is_pinned,"is_archived":note.is_archived,"revision":note.revision,"created_at":note.created_at,"updated_at":note.updated_at,"indexing_status":state.status if state else "pending","indexed_revision":state.indexed_revision if state else None,"tags":[{"id":str(t.id),"name":t.name,"color":t.color} for t in tags],"linked_documents":[{"id":str(d.id),"name":d.name,"file_type":d.file_type,"scope":d.storage_scope} for d in docs]}
    def list(self, access, query="", filter_name="all", tag_id=None, cursor=None, limit=25):
        user_id, workspace=self._scope(access); clauses=[Note.owner_user_id==user_id,Note.workspace_id==workspace.id]
        clauses.append(Note.deleted_at.is_not(None) if filter_name=="trash" else Note.deleted_at.is_(None))
        if filter_name=="pinned": clauses.append(Note.is_pinned.is_(True))
        elif filter_name=="recent": clauses.append(Note.updated_at>=datetime.now(timezone.utc)-timedelta(days=30))
        elif filter_name=="archived": clauses.append(Note.is_archived.is_(True))
        elif filter_name not in {"all","trash"}: raise ValueError("Unsupported note filter.")
        if query.strip():
            document=func.coalesce(Note.title,"")+" "+func.coalesce(Note.plain_text,"")
            clauses.append(func.to_tsvector("simple",document).op("@@")(func.plainto_tsquery("simple",query.strip())))
        statement=select(Note).where(*clauses)
        if tag_id: statement=statement.join(NoteTagLink,NoteTagLink.note_id==Note.id).where(NoteTagLink.tag_id==tag_id)
        if cursor:
            try:
                stamp,raw_id=base64.urlsafe_b64decode(cursor.encode()).decode().split("|",1); dt=datetime.fromisoformat(stamp); cid=uuid.UUID(raw_id)
                statement=statement.where(or_(Note.updated_at<dt,and_(Note.updated_at==dt,Note.id<cid)))
            except Exception as exc: raise ValueError("Invalid notes cursor.") from exc
        rows=list(self.session.scalars(statement.order_by(desc(Note.is_pinned),desc(Note.updated_at),desc(Note.id)).limit(limit+1)))
        more=len(rows)>limit; rows=rows[:limit]
        next_cursor=base64.urlsafe_b64encode(f"{rows[-1].updated_at.isoformat()}|{rows[-1].id}".encode()).decode() if more else None
        self.session.commit(); return {"items":[self._payload(n,access) for n in rows],"next_cursor":next_cursor}
    def create(self, access, title="Untitled"):
        user_id, workspace=self._scope(access); clean=" ".join(title.split()).strip() or "Untitled"
        note=Note(organization_id=workspace.organization_id,workspace_id=workspace.id,owner_user_id=user_id,title=clean)
        self.session.add(note); self.session.flush(); self._version(note,user_id); self._audit(user_id,"workspace.note.created",note.id); self._schedule_index(note,"index"); self.session.commit(); self.session.refresh(note); return self._payload(note,access)
    def get(self, access, note_id): return self._payload(self._get(access,note_id),access)
    def update(self, access, note_id, payload):
        note=self._get(access,note_id)
        if note.revision!=payload.expected_revision and not payload.force: raise NoteConflict(self._payload(note,access))
        before=(note.is_pinned,note.is_archived)
        for field in ("title","content_json","content_markdown","content_format","is_pinned","is_archived"):
            value=getattr(payload,field,None)
            if value is not None: setattr(note,field,value)
        note.title=" ".join(note.title.split()).strip() or "Untitled"; note.plain_text=_plain(note.content_markdown); note.revision+=1; note.updated_at=datetime.now(timezone.utc)
        self._version(note,note.owner_user_id)
        action="workspace.note.updated"
        if before[0]!=note.is_pinned: action="workspace.note.pinned" if note.is_pinned else "workspace.note.unpinned"
        elif before[1]!=note.is_archived: action="workspace.note.archived" if note.is_archived else "workspace.note.unarchived"
        self._audit(note.owner_user_id,action,note.id); self._schedule_index(note,"remove" if note.is_archived else "index"); self.session.commit(); return self._payload(note,access)
    def delete(self, access,note_id):
        note=self._get(access,note_id); note.deleted_at=datetime.now(timezone.utc); note.deleted_by_user_id=note.owner_user_id; self._audit(note.owner_user_id,"workspace.note.deleted",note.id); self._schedule_index(note,"remove"); self.session.commit()
    def restore(self, access,note_id):
        note=self._get(access,note_id,True); note.deleted_at=None; note.deleted_by_user_id=None; self._audit(note.owner_user_id,"workspace.note.restored",note.id); self._schedule_index(note,"index"); self.session.commit(); return self._payload(note,access)
    def duplicate(self, access,note_id):
        source=self._get(access,note_id); created=self.create(access,f"{source.title} copy"); target=self._get(access,created["id"]); target.content_json=source.content_json; target.content_markdown=source.content_markdown; target.plain_text=source.plain_text; target.revision+=1; self._version(target,target.owner_user_id); self._audit(target.owner_user_id,"workspace.note.duplicated",target.id); self._schedule_index(target,"index"); self.session.commit(); return self._payload(target,access)
    def versions(self, access,note_id):
        note=self._get(access,note_id); rows=list(self.session.scalars(select(NoteVersion).where(NoteVersion.note_id==note.id).order_by(NoteVersion.revision.desc())))
        return [{"id":str(v.id),"revision":v.revision,"title":v.title,"created_at":v.created_at} for v in rows]
    def tags(self, access):
        user_id,workspace=self._scope(access); rows=list(self.session.execute(select(NoteTag,func.count(NoteTagLink.note_id)).outerjoin(NoteTagLink,NoteTagLink.tag_id==NoteTag.id).where(NoteTag.owner_user_id==user_id,NoteTag.workspace_id==workspace.id).group_by(NoteTag.id).order_by(NoteTag.name)))
        return [{"id":str(tag.id),"name":tag.name,"color":tag.color,"count":int(count)} for tag,count in rows]
    def create_tag(self,access,name,color=None):
        user_id,workspace=self._scope(access); clean=" ".join(name.split()).strip(); normalized=clean.casefold()
        tag=self.session.scalar(select(NoteTag).where(NoteTag.owner_user_id==user_id,NoteTag.normalized_name==normalized))
        if tag is None: tag=NoteTag(workspace_id=workspace.id,owner_user_id=user_id,name=clean,normalized_name=normalized,color=color); self.session.add(tag); self.session.flush(); self._audit(user_id,"workspace.note.tag_created",tag.id); self.session.commit()
        return {"id":str(tag.id),"name":tag.name,"color":tag.color}
    def rename_tag(self,access,tag_id,name,color=None):
        user_id,workspace=self._scope(access);tag=self.session.scalar(select(NoteTag).where(NoteTag.id==tag_id,NoteTag.owner_user_id==user_id,NoteTag.workspace_id==workspace.id))
        if tag is None: raise WorkspaceNotFound("Tag not found.")
        clean=" ".join(name.split()).strip();normalized=clean.casefold();duplicate=self.session.scalar(select(NoteTag).where(NoteTag.owner_user_id==user_id,NoteTag.normalized_name==normalized,NoteTag.id!=tag.id))
        if duplicate is not None: raise ValueError("A tag with that name already exists.")
        tag.name=clean;tag.normalized_name=normalized;tag.color=color;self._audit(user_id,"workspace.note.tag_renamed",tag.id);self.session.commit();return {"id":str(tag.id),"name":tag.name,"color":tag.color}
    def delete_tag(self,access,tag_id):
        user_id,workspace=self._scope(access);tag=self.session.scalar(select(NoteTag).where(NoteTag.id==tag_id,NoteTag.owner_user_id==user_id,NoteTag.workspace_id==workspace.id))
        if tag is None: raise WorkspaceNotFound("Tag not found.")
        self._audit(user_id,"workspace.note.tag_deleted",tag.id);self.session.delete(tag);self.session.commit()
    def add_tag(self,access,note_id,tag_id):
        note=self._get(access,note_id); tag=self.session.scalar(select(NoteTag).where(NoteTag.id==tag_id,NoteTag.owner_user_id==note.owner_user_id,NoteTag.workspace_id==note.workspace_id))
        if tag is None: raise WorkspaceNotFound("Tag not found.")
        if self.session.get(NoteTagLink,{"note_id":note.id,"tag_id":tag.id}) is None: self.session.add(NoteTagLink(note_id=note.id,tag_id=tag.id)); self._audit(note.owner_user_id,"workspace.note.tag_added",note.id); self.session.commit()
        return self._payload(note,access)
    def remove_tag(self,access,note_id,tag_id):
        note=self._get(access,note_id); link=self.session.get(NoteTagLink,{"note_id":note.id,"tag_id":tag_id})
        if link: self.session.delete(link); self._audit(note.owner_user_id,"workspace.note.tag_removed",note.id); self.session.commit()
    def link_document(self,access,note_id,document_id):
        note=self._get(access,note_id); doc=self.session.get(Document,document_id)
        if doc is None or not document_is_accessible(doc,access,self.session): raise WorkspaceNotFound("Document not found.")
        if self.session.get(NoteDocumentLink,{"note_id":note.id,"document_id":doc.id}) is None: self.session.add(NoteDocumentLink(note_id=note.id,document_id=doc.id)); self._audit(note.owner_user_id,"workspace.note.document_linked",note.id); self.session.commit()
        return self._payload(note,access)
    def unlink_document(self,access,note_id,document_id):
        note=self._get(access,note_id); link=self.session.get(NoteDocumentLink,{"note_id":note.id,"document_id":document_id})
        if link: self.session.delete(link); self._audit(note.owner_user_id,"workspace.note.document_unlinked",note.id); self.session.commit()
    def _version(self,note,user_id): self.session.add(NoteVersion(note_id=note.id,revision=note.revision,title=note.title,content_json=note.content_json,content_markdown=note.content_markdown,plain_text=note.plain_text,created_by_user_id=user_id))
    def _audit(self,user_id,action,entity_id): self.session.add(AuditEvent(user_id=user_id,actor_user_id=user_id,action=action,entity_type="note",entity_id=entity_id,status="succeeded"))
    def _schedule_index(self,note:Note,action:str):
        self.session.flush()
        note_version=self.session.scalar(select(NoteVersion).where(NoteVersion.note_id==note.id,NoteVersion.revision==note.revision))
        active=list(self.session.scalars(select(IndexingJob).where(
            IndexingJob.note_id==note.id,
            IndexingJob.status.in_(("pending","retry_wait")),
        )))
        pending=next((job for job in active if job.note_version_id==(note_version.id if note_version else None)),None)
        for obsolete in active:
            if obsolete is not pending:
                obsolete.status="superseded"
                obsolete.completed_at=datetime.now(timezone.utc)
                obsolete.message="Superseded by a newer committed note revision."
        state=self.session.get(NoteIndexState,note.id)
        if state is None:state=NoteIndexState(note_id=note.id,status="pending");self.session.add(state)
        state.status="pending"
        metadata={"entity_type":"note","note_id":str(note.id),"note_revision":note.revision,"action":action,"owner_user_id":str(note.owner_user_id),"workspace_id":str(note.workspace_id)}
        available_at=datetime.now(timezone.utc)+timedelta(seconds=3)
        if pending is None:
            pending=IndexingJob(
                asset_type="note", note_id=note.id,
                note_version_id=note_version.id if note_version else None,
                operation="delete_asset" if action=="remove" else "upsert_version",
                status="pending", priority=120 if action=="remove" else 100,
                force_rebuild=False,
                max_attempts=settings.indexer_max_attempts,
                repository_id=f"personal:{note.owner_user_id}",
            )
            self.session.add(pending)
        pending.content_hash=hashlib.sha256((note.content_markdown or "").encode()).hexdigest()
        pending.operation="delete_asset" if action=="remove" else "upsert_version"
        pending.metadata_=metadata
        pending.available_at=available_at
        pending.priority=120 if action=="remove" else 100
        pending.message="Coalescing note changes before incremental indexing."
        pending.attempts=0
        self.session.flush();self.last_index_job_id=pending.id
