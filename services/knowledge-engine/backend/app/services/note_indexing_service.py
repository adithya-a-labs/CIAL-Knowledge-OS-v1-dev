"""Incremental, revision-safe indexing for private Notes."""
from __future__ import annotations
import hashlib, re, uuid
from datetime import datetime, timezone
from typing import Any
from langchain_core.documents import Document as LangchainDocument
from qdrant_client.models import FieldCondition, Filter, FilterSelector, MatchValue, PointIdsList, PointStruct
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.identity import User
from backend.app.models.workspace_content import Note, NoteIndexState
from cial_knowledge_os.embeddings import embed_texts


def note_relative_path(note_id: uuid.UUID | str) -> str:
    return f"notes/{note_id}"


def _blocks(note: Note) -> list[tuple[str, str, str]]:
    raw_blocks = [value.strip() for value in re.split(r"\n\s*\n", note.content_markdown or "") if value.strip()]
    editor_ids=[]
    if isinstance(note.content_json,dict) and isinstance(note.content_json.get("content"),list):
        for block in note.content_json["content"]:
            if isinstance(block,dict):
                attributes=block.get("attrs")
                value=attributes.get("blockId") if isinstance(attributes,dict) else None
                editor_ids.append(str(value) if value else "")
    result=[]
    for index, text in enumerate(raw_blocks):
        first=text.splitlines()[0].strip(); section=re.sub(r"^#{1,6}\s+","",first)[:160] or note.title
        block_id=editor_ids[index] if index<len(editor_ids) and editor_ids[index] else str(uuid.uuid5(uuid.NAMESPACE_URL,f"cial-note-block:{note.id}:{index}"))
        result.append((block_id,section,text))
    return result


class NoteIndexingService:
    def __init__(self,session:Session,engine:Any): self.session=session;self.engine=engine
    def process(self,note_id:uuid.UUID,revision:int,action:str)->dict[str,int]:
        note=self.session.scalar(select(Note).where(Note.id==note_id).with_for_update())
        if note is None: return {"documents_seen":0,"documents_indexed":0,"chunks_indexed":0}
        state=self.session.get(NoteIndexState,note_id)
        if state is None:
            state=NoteIndexState(note_id=note_id,status="pending");self.session.add(state);self.session.flush()
        if revision != note.revision:
            return {"documents_seen":1,"documents_indexed":0,"chunks_indexed":0}
        pipeline=self.engine._pipeline
        if pipeline is None or pipeline.client is None or pipeline.embedding_model is None: raise RuntimeError("Knowledge index is not ready for note indexing.")
        state.status="indexing";state.last_error=None;self.session.commit()
        if action=="remove" or note.deleted_at is not None or note.is_archived:
            removed=self._delete_all(pipeline,note.id);self._refresh_lexical(pipeline,note.id,[])
            state=self.session.get(NoteIndexState,note.id);state.status="removed";state.indexed_revision=note.revision;state.point_count=0;state.content_hash=None;state.updated_at=datetime.now(timezone.utc);self.session.commit()
            return {"documents_seen":1,"documents_indexed":1,"chunks_indexed":0}
        user=self.session.get(User,note.owner_user_id); department_id=user.department_id if user else None
        blocks=_blocks(note);digest=hashlib.sha256((note.content_markdown or "").encode()).hexdigest();chunks=[];points=[]
        texts=[text for _,_,text in blocks]
        vectors=embed_texts(pipeline.embedding_model,texts,batch_size=pipeline.config.embedding_batch_size) if texts else []
        for index,((block_id,section,body),vector) in enumerate(zip(blocks,vectors,strict=True)):
            chunk_id=f"note:{note.id}:{note.revision}:{index}"; point_id=str(uuid.uuid5(uuid.NAMESPACE_URL,chunk_id))
            metadata={"entity_type":"note","note_id":str(note.id),"note_revision":note.revision,"workspace_id":str(note.workspace_id),"organization_id":str(note.organization_id),"repository_id":f"personal:{note.owner_user_id}","storage_scope":"personal","owner_user_id":str(note.owner_user_id),"department_id":str(department_id) if department_id else None,"folder_id":None,"visibility":"private","lifecycle_status":"active","title":note.title,"file_name":note.title,"relative_path":note_relative_path(note.id),"section":section,"block_ids":[block_id],"block_id":block_id,"chunk_index":index,"chunk_id":chunk_id,"content_hash":digest,"created_at":note.created_at.isoformat(),"updated_at":note.updated_at.isoformat()}
            chunks.append(LangchainDocument(page_content=body,metadata=metadata));points.append(PointStruct(id=point_id,vector=vector.tolist(),payload={"text":body,"metadata":metadata}))
        if points: pipeline.client.upsert(collection_name=pipeline.config.qdrant_collection_name,points=points,wait=True)
        current={str(point.id) for point in points}; previous=self._point_ids(pipeline,note.id); stale=[value for value in previous if value not in current]
        if stale: pipeline.client.delete(collection_name=pipeline.config.qdrant_collection_name,points_selector=PointIdsList(points=stale),wait=True)
        self._refresh_lexical(pipeline,note.id,chunks)
        state=self.session.get(NoteIndexState,note.id)
        if note.revision==revision:
            state.status="indexed";state.indexed_revision=revision;state.content_hash=digest;state.point_count=len(points);state.last_error=None;state.updated_at=datetime.now(timezone.utc);self.session.commit()
        return {"documents_seen":1,"documents_indexed":1,"chunks_indexed":len(points)}
    def _point_ids(self,pipeline,note_id):
        ids=[];offset=None;query=Filter(must=[FieldCondition(key="metadata.note_id",match=MatchValue(value=str(note_id)))])
        while True:
            points,offset=pipeline.client.scroll(collection_name=pipeline.config.qdrant_collection_name,scroll_filter=query,limit=128,offset=offset,with_payload=False,with_vectors=False);ids.extend(str(point.id) for point in points)
            if offset is None:break
        return ids
    def _delete_all(self,pipeline,note_id):
        ids=self._point_ids(pipeline,note_id)
        if ids:pipeline.client.delete(collection_name=pipeline.config.qdrant_collection_name,points_selector=PointIdsList(points=ids),wait=True)
        return len(ids)
    @staticmethod
    def _refresh_lexical(pipeline,note_id,chunks):
        note_map=getattr(pipeline,"_note_chunks",{});note_map[str(note_id)]=chunks
        if not chunks:note_map.pop(str(note_id),None)
        pipeline._note_chunks=note_map
        if pipeline.bm25_retriever is not None:pipeline.bm25_retriever.index([*(pipeline.chunks or []),*[chunk for values in note_map.values() for chunk in values]])
