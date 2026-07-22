"""Authenticated, complete-material map/reduce summaries with immutable provenance."""
from __future__ import annotations
import hashlib, re, uuid
from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from backend.app.models.conversations import ChatMessage, ChatSession
from backend.app.models.knowledge import Document, DocumentChunk, DocumentVersion, Folder
from backend.app.models.operations import AuditEvent
from backend.app.models.workspace_content import Note, NoteVersion, SavedKnowledgeItem, SummaryArtifact, SummaryCitation, SummaryConversationBinding, SummarySource
from backend.app.schemas.summaries import SummaryCreate
from backend.app.security.access import RequestAccessContext, document_is_accessible
from backend.app.services.note_service import NoteService
from backend.app.services.personal_workspace_service import PersonalWorkspaceService, WorkspaceNotFound
from cial_knowledge_os.prompts.manager import DEFAULT_PROMPT_MANAGER

_REF=re.compile(r"\[(\d+)\]")

class SummaryError(RuntimeError): pass
class SummaryCancelled(SummaryError): pass

class SummaryService:
    def __init__(self,db:Session,generator): self.db=db; self.generator=generator
    def _identity(self,access):
        workspace=PersonalWorkspaceService(self.db).get_or_create(access); return access.principal.user_id,workspace
    def _artifact(self,access,summary_id):
        user_id,workspace=self._identity(access)
        row=self.db.scalar(select(SummaryArtifact).where(SummaryArtifact.id==summary_id,SummaryArtifact.owner_user_id==user_id,SummaryArtifact.workspace_id==workspace.id,SummaryArtifact.deleted_at.is_(None)))
        if row is None: raise WorkspaceNotFound("Summary not found.")
        return row
    def _resolve(self,access,payload):
        user_id,workspace=self._identity(access); resolved=[]; seen=set(); ref=1; requested_sources=list(payload.sources)
        expanded=[]
        for requested in requested_sources:
            if requested.source_type!="folder": expanded.append(requested);continue
            if requested.source_id is None: raise WorkspaceNotFound("Source folder not found.")
            folder=self.db.get(Folder,requested.source_id)
            if folder is None: raise WorkspaceNotFound("Source folder not found.")
            pending=[folder.id];folder_ids=[]
            while pending:
                current=pending.pop();folder_ids.append(current);pending.extend(self.db.scalars(select(Folder.id).where(Folder.parent_id==current)).all())
            documents=list(self.db.scalars(select(Document).where(Document.folder_id.in_(folder_ids),Document.deleted_at.is_(None))))
            authorized=[document for document in documents if document_is_accessible(document,access)]
            if not authorized: raise WorkspaceNotFound("Source folder not found or contains no accessible documents.")
            from types import SimpleNamespace
            expanded.extend(SimpleNamespace(source_type="document",source_id=document.id,title=None,content=None) for document in authorized)
        for requested in expanded:
            key=(requested.source_type,requested.source_id or hashlib.sha256((requested.content or "").encode()).hexdigest())
            if key in seen: continue
            seen.add(key)
            if requested.source_type=="pasted_text":
                content=(requested.content or "").strip()
                if not content: raise SummaryError("Pasted text is empty.")
                digest=hashlib.sha256(content.encode()).hexdigest(); title=(requested.title or "Pasted text").strip() or "Pasted text"
                evidence=[{"id":ref,"text":content,"page":None,"section":title,"chunk_id":f"pasted:{digest[:16]}","document_id":None,"note_id":None}];ref+=1
                resolved.append({"type":"pasted_text","id":None,"version_id":None,"title":title,"hash":digest,"evidence":evidence,"snapshot_content":content})
            elif requested.source_type=="document":
                if requested.source_id is None: raise WorkspaceNotFound("Source not found.")
                doc=self.db.get(Document,requested.source_id)
                if doc is None or not document_is_accessible(doc,access) or doc.current_version_id is None: raise WorkspaceNotFound("Source not found.")
                version=self.db.get(DocumentVersion,doc.current_version_id)
                if version is None or version.status!="indexed": raise SummaryError(f"{doc.name} is not ready for summarization.")
                chunks=list(self.db.scalars(select(DocumentChunk).where(DocumentChunk.document_id==doc.id,DocumentChunk.document_version_id==version.id).order_by(DocumentChunk.chunk_index)))
                if not chunks: raise SummaryError(f"{doc.name} has no extracted text.")
                evidence=[]
                for chunk in chunks:
                    if not (chunk.text or "").strip(): continue
                    evidence.append({"id":ref,"text":chunk.text.strip(),"page":chunk.page,"section":chunk.section,"chunk_id":chunk.chunk_id,"document_id":doc.id,"note_id":None}); ref+=1
                resolved.append({"type":"document","id":doc.id,"version_id":version.id,"title":doc.name,"hash":version.content_hash,"evidence":evidence})
            elif requested.source_type=="note":
                if requested.source_id is None: raise WorkspaceNotFound("Source not found.")
                note=self.db.scalar(select(Note).where(Note.id==requested.source_id,Note.owner_user_id==user_id,Note.workspace_id==workspace.id,Note.deleted_at.is_(None)))
                if note is None: raise WorkspaceNotFound("Source not found.")
                version=self.db.scalar(select(NoteVersion).where(NoteVersion.note_id==note.id,NoteVersion.revision==note.revision))
                if version is None or not version.plain_text.strip(): raise SummaryError(f"{note.title} is empty.")
                digest=hashlib.sha256(version.content_markdown.encode()).hexdigest(); evidence=[{"id":ref,"text":version.content_markdown,"page":None,"section":note.title,"chunk_id":f"note:{note.id}:{note.revision}:0","document_id":None,"note_id":note.id}]; ref+=1
                resolved.append({"type":"note","id":note.id,"version_id":version.id,"title":note.title,"hash":digest,"evidence":evidence})
            else:
                if requested.source_id is None: raise WorkspaceNotFound("Source not found.")
                session=self.db.scalar(select(ChatSession).where(ChatSession.id==requested.source_id,ChatSession.user_id==user_id))
                if session is None: raise WorkspaceNotFound("Source not found.")
                messages=list(self.db.scalars(select(ChatMessage).where(ChatMessage.session_id==session.id).order_by(ChatMessage.created_at)))
                content="\n\n".join(f"{m.role}: {m.content}" for m in messages)
                if not content.strip(): raise SummaryError("Conversation is empty.")
                digest=hashlib.sha256(content.encode()).hexdigest(); evidence=[{"id":ref,"text":content,"page":None,"section":"Conversation","chunk_id":f"conversation:{session.id}","document_id":None,"note_id":None}]; ref+=1
                resolved.append({"type":"conversation","id":session.id,"version_id":None,"title":session.title or "Conversation","hash":digest,"evidence":evidence,"snapshot_extra":{"message_ids":[str(message.id) for message in messages],"message_hashes":[hashlib.sha256(message.content.encode()).hexdigest() for message in messages]}})
        if not resolved: raise SummaryError("Select at least one source.")
        return resolved
    @staticmethod
    def _blocks(evidence,max_chars=10000):
        blocks=[]; current=[]; size=0
        for item in evidence:
            rendered=f"[{item['id']}] page={item['page'] or 'n/a'} section={item['section'] or 'n/a'} chunk={item['chunk_id']}\n{item['text']}"
            if current and size+len(rendered)>max_chars: blocks.append("\n\n".join(current)); current=[]; size=0
            current.append(rendered); size+=len(rendered)
        if current: blocks.append("\n\n".join(current))
        return blocks
    def create(self,access,payload:SummaryCreate,event=None,token_callback=None,cancel_event=None):
        user_id,workspace=self._identity(access); emit=event or (lambda *_:None)
        emit("source.authorizing",{"status":"started"}); resolved=self._resolve(access,payload); emit("source.authorizing",{"status":"completed","sources":len(resolved)})
        fingerprint=hashlib.sha256("|".join(f"{r['type']}:{r['id']}:{r['version_id']}:{r['hash']}" for r in resolved).encode()).hexdigest()
        artifact=SummaryArtifact(organization_id=workspace.organization_id,workspace_id=workspace.id,owner_user_id=user_id,title=payload.title or f"{payload.summary_type.replace('_',' ').title()} Summary",summary_type=payload.summary_type,summary_length=payload.summary_length,multi_document_mode=payload.multi_document_mode,custom_instructions=payload.custom_instructions,status="running",prompt_name="summaries.merge_v1",prompt_version="v1",source_fingerprint=fingerprint,document_count=sum(r["type"]=="document" for r in resolved),started_at=datetime.now(timezone.utc))
        self.db.add(artifact); self.db.flush(); sources=[]
        for ordinal,item in enumerate(resolved,1):
            source=SummarySource(summary_id=artifact.id,ordinal=ordinal,source_type=item["type"],source_id=item["id"],document_version_id=item["version_id"] if item["type"]=="document" else None,note_version_id=item["version_id"] if item["type"]=="note" else None,chat_session_id=item["id"] if item["type"]=="conversation" else None,title=item["title"],content_hash=item["hash"],source_snapshot={"source_id":str(item["id"]) if item["id"] else None,"version_id":str(item["version_id"]) if item["version_id"] else None,**({"content":item["snapshot_content"]} if item["type"]=="pasted_text" else {}),**item.get("snapshot_extra",{})})
            self.db.add(source); self.db.flush(); sources.append(source)
            for ev in item["evidence"]:
                self.db.add(SummaryCitation(summary_id=artifact.id,citation_id=str(ev["id"]),source_record_id=source.id,document_id=ev["document_id"],note_id=ev["note_id"],page_number=ev["page"],section=ev["section"],chunk_id=ev["chunk_id"],excerpt=ev["text"][:500]))
        self.db.commit()
        try:
            mapped=[]; total=sum(len(self._blocks(r["evidence"])) for r in resolved); done=0; emit("source.loading",{"status":"completed","sources":len(resolved)})
            for item in resolved:
                parts=[]
                for block in self._blocks(item["evidence"]):
                    if cancel_event is not None and cancel_event.is_set(): raise SummaryCancelled("Summary generation cancelled.")
                    emit("sections.summarizing",{"status":"started","completed":done,"total":total})
                    prompt=DEFAULT_PROMPT_MANAGER.render("summaries.section_v1",summary_type=payload.summary_type,summary_length=payload.summary_length,custom_instructions=payload.custom_instructions or "None",source_material=block)
                    map_stream=getattr(self.generator,"stream_generate",None);parts.append(map_stream(prompt,cancel_event=cancel_event) if callable(map_stream) else self.generator.generate(prompt)); done+=1; emit("sections.summarizing",{"status":"completed","completed":done,"total":total})
                mapped.append(f"## {item['title']}\n"+"\n\n".join(parts))
            emit("documents.merging",{"status":"started","documents":len(resolved)})
            prompt=DEFAULT_PROMPT_MANAGER.render("summaries.merge_v1",summary_type=payload.summary_type,multi_document_mode=payload.multi_document_mode,summary_length=payload.summary_length,custom_instructions=payload.custom_instructions or "None",source_summaries="\n\n".join(mapped))
            stream_generate=getattr(self.generator,"stream_generate",None)
            content=stream_generate(prompt,cancel_event=cancel_event,token_callback=token_callback) if token_callback is not None and callable(stream_generate) else self.generator.generate(prompt)
            if cancel_event is not None and cancel_event.is_set(): raise SummaryCancelled("Summary generation cancelled.")
            emit("documents.merging",{"status":"completed"})
            allowed={str(ev["id"]) for item in resolved for ev in item["evidence"]}; emit("citations.validating",{"status":"started"})
            content=_REF.sub(lambda m:m.group(0) if m.group(1) in allowed else "",content); used=list(dict.fromkeys(_REF.findall(content)))
            artifact.content_markdown=content.strip(); artifact.citation_count=len(used); artifact.status="completed"; artifact.completed_at=datetime.now(timezone.utc)
            self.db.add(AuditEvent(user_id=user_id,actor_user_id=user_id,action="summary.generated",entity_type="summary",entity_id=artifact.id,status="succeeded",metadata_={"source_count":len(resolved),"citation_count":len(used)})); self.db.commit(); emit("citations.validating",{"status":"completed","citations":len(used)}); emit("artifact.saving",{"status":"completed"}); return self.payload(access,artifact)
        except SummaryCancelled:
            self.db.rollback(); failed=self.db.get(SummaryArtifact,artifact.id)
            if failed: failed.status="cancelled"; failed.error_code="cancelled"; failed.error_message_safe="Summary generation cancelled."; self.db.commit()
            raise
        except Exception as exc:
            self.db.rollback(); failed=self.db.get(SummaryArtifact,artifact.id)
            if failed: failed.status="failed"; failed.error_code="generation_failed"; failed.error_message_safe="Local summary generation failed."; self.db.commit()
            raise SummaryError("Local summary generation failed.") from exc
    def payload(self,access,artifact):
        self._artifact(access,artifact.id); sources=list(self.db.scalars(select(SummarySource).where(SummarySource.summary_id==artifact.id).order_by(SummarySource.ordinal))); citations=list(self.db.scalars(select(SummaryCitation).where(SummaryCitation.summary_id==artifact.id).order_by(SummaryCitation.citation_id)))
        return {"id":artifact.id,"title":artifact.title,"summary_type":artifact.summary_type,"summary_length":artifact.summary_length,"multi_document_mode":artifact.multi_document_mode,"status":artifact.status,"content_markdown":artifact.content_markdown,"citation_count":artifact.citation_count,"document_count":artifact.document_count,"prompt_name":artifact.prompt_name,"prompt_version":artifact.prompt_version,"created_at":artifact.created_at,"completed_at":artifact.completed_at,"sources":[{"id":str(s.id),"source_type":s.source_type,"source_id":str(s.source_id) if s.source_id else None,"title":s.title,"version_id":str(s.document_version_id or s.note_version_id) if (s.document_version_id or s.note_version_id) else None} for s in sources],"citations":[{"citation_id":c.citation_id,"document_id":str(c.document_id) if c.document_id else None,"note_id":str(c.note_id) if c.note_id else None,"page_number":c.page_number,"section":c.section,"chunk_id":c.chunk_id,"excerpt":c.excerpt} for c in citations],"stale":False}
    def get(self,access,summary_id): return self.payload(access,self._artifact(access,summary_id))
    def list(self,access):
        user_id,workspace=self._identity(access); rows=list(self.db.scalars(select(SummaryArtifact).where(SummaryArtifact.owner_user_id==user_id,SummaryArtifact.workspace_id==workspace.id,SummaryArtifact.deleted_at.is_(None)).order_by(SummaryArtifact.created_at.desc()).limit(50)))
        return {"items":[self.payload(access,row) for row in rows]}
    def delete(self,access,summary_id):
        row=self._artifact(access,summary_id); row.deleted_at=datetime.now(timezone.utc); self.db.add(AuditEvent(user_id=row.owner_user_id,actor_user_id=row.owner_user_id,action="summary.deleted",entity_type="summary",entity_id=row.id,status="succeeded")); self.db.commit()
    def save_to_note(self,access,summary_id,title=None):
        row=self._artifact(access,summary_id)
        if row.status!="completed" or not row.content_markdown: raise SummaryError("Only completed summaries can be saved.")
        notes=NoteService(self.db); created=notes.create(access,title or row.title); from backend.app.schemas.notes import NoteUpdate
        content=f"{row.content_markdown}\n\n---\nGenerated from summary `{row.id}`."
        result=notes.update(access,created["id"],NoteUpdate(expected_revision=created["revision"],content_markdown=content,content_format="markdown")); self.db.add(AuditEvent(user_id=row.owner_user_id,actor_user_id=row.owner_user_id,action="summary.saved_to_note",entity_type="summary",entity_id=row.id,status="succeeded",metadata_={"note_id":str(result["id"])})); self.db.commit(); return result
    def save_to_saved_knowledge(self,access,summary_id):
        row=self._artifact(access,summary_id)
        if row.status!="completed": raise SummaryError("Only completed summaries can be saved.")
        existing=self.db.scalar(select(SavedKnowledgeItem).where(SavedKnowledgeItem.owner_user_id==row.owner_user_id,SavedKnowledgeItem.summary_id==row.id))
        if existing:
            if existing.deleted_at is not None: existing.deleted_at=None; existing.title=row.title; self.db.commit()
            return self._saved_payload(existing,row,self.db.scalar(select(func.count()).select_from(SummarySource).where(SummarySource.summary_id==row.id)) or 0)
        item=SavedKnowledgeItem(organization_id=row.organization_id,workspace_id=row.workspace_id,owner_user_id=row.owner_user_id,item_type="summary",summary_id=row.id,title=row.title)
        self.db.add(item);self.db.add(AuditEvent(user_id=row.owner_user_id,actor_user_id=row.owner_user_id,action="saved_knowledge.created",entity_type="summary",entity_id=row.id,status="succeeded"));self.db.commit();self.db.refresh(item);return self._saved_payload(item,row,self.db.scalar(select(func.count()).select_from(SummarySource).where(SummarySource.summary_id==row.id)) or 0)
    @staticmethod
    def _saved_payload(item,summary,source_count): return {"id":item.id,"item_type":item.item_type,"summary_id":item.summary_id,"title":item.title,"source_count":source_count,"created_at":item.created_at,"updated_at":item.updated_at}
    def list_saved_knowledge(self,access):
        user_id,workspace=self._identity(access); rows=list(self.db.execute(select(SavedKnowledgeItem,SummaryArtifact).join(SummaryArtifact,SummaryArtifact.id==SavedKnowledgeItem.summary_id).where(SavedKnowledgeItem.owner_user_id==user_id,SavedKnowledgeItem.workspace_id==workspace.id,SavedKnowledgeItem.deleted_at.is_(None)).order_by(SavedKnowledgeItem.created_at.desc())).all())
        return {"items":[self._saved_payload(item,summary,self.db.scalar(select(func.count()).select_from(SummarySource).where(SummarySource.summary_id==summary.id)) or 0) for item,summary in rows]}
    def remove_saved_knowledge(self,access,item_id):
        user_id,workspace=self._identity(access);item=self.db.scalar(select(SavedKnowledgeItem).where(SavedKnowledgeItem.id==item_id,SavedKnowledgeItem.owner_user_id==user_id,SavedKnowledgeItem.workspace_id==workspace.id,SavedKnowledgeItem.deleted_at.is_(None)))
        if item is None: raise WorkspaceNotFound("Saved item not found.")
        item.deleted_at=datetime.now(timezone.utc);self.db.add(AuditEvent(user_id=user_id,actor_user_id=user_id,action="saved_knowledge.removed",entity_type="summary",entity_id=item.summary_id,status="succeeded"));self.db.commit()
    def ask_follow_up(self,access,summary_id,mode="original_versions"):
        row=self._artifact(access,summary_id)
        if row.status!="completed": raise SummaryError("Only completed summaries support follow-up.")
        sources=list(self.db.scalars(select(SummarySource).where(SummarySource.summary_id==row.id).order_by(SummarySource.ordinal)))
        if mode=="original_versions":
            for source in sources:
                if source.source_type=="document" and (source.document_version_id is None or self.db.get(DocumentVersion,source.document_version_id) is None): raise SummaryError("Source version unavailable.")
                if source.source_type=="note" and (source.note_version_id is None or self.db.get(NoteVersion,source.note_version_id) is None): raise SummaryError("Source version unavailable.")
        session=ChatSession(user_id=row.owner_user_id,title=f"Follow-up: {row.title}"[:255]);self.db.add(session);self.db.flush()
        binding=[{"source_type":source.source_type,"source_id":str(source.source_id) if source.source_id else None,"title":source.title,"document_version_id":str(source.document_version_id) if source.document_version_id else None,"note_version_id":str(source.note_version_id) if source.note_version_id else None,"chat_session_id":str(source.chat_session_id) if source.chat_session_id else None} for source in sources]
        self.db.add(SummaryConversationBinding(summary_id=row.id,chat_session_id=session.id,owner_user_id=row.owner_user_id,mode=mode,source_binding=binding));self.db.add(AuditEvent(user_id=row.owner_user_id,actor_user_id=row.owner_user_id,action="summary.follow_up.created",entity_type="summary",entity_id=row.id,status="succeeded",metadata_={"chat_session_id":str(session.id),"mode":mode}));self.db.commit();return {"chat_session_id":session.id,"url":f"/assistant?session={session.id}","mode":mode,"sources":binding}
