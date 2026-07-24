"""Incremental, revision-safe indexing primitives for private Notes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import re
import uuid
from typing import Any

import numpy as np
from langchain_core.documents import Document as LangchainDocument
from qdrant_client.models import (
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.identity import User
from backend.app.models.workspace_content import Note, NoteIndexState
from cial_knowledge_os.embeddings import embed_texts
from cial_knowledge_os.vectorstore import execute_qdrant_operation


class SupersededNoteRevision(RuntimeError):
    """The queued revision is no longer the note's committed revision."""


@dataclass(frozen=True, slots=True)
class PreparedNoteRevision:
    note_id: uuid.UUID
    revision: int
    action: str
    content_hash: str | None
    chunks: list[LangchainDocument]


def note_relative_path(note_id: uuid.UUID | str) -> str:
    return f"notes/{note_id}"


def _blocks(note: Note) -> list[tuple[str, str, str]]:
    raw_blocks = [
        value.strip()
        for value in re.split(r"\n\s*\n", note.content_markdown or "")
        if value.strip()
    ]
    editor_ids: list[str] = []
    if isinstance(note.content_json, dict) and isinstance(note.content_json.get("content"), list):
        for block in note.content_json["content"]:
            if isinstance(block, dict):
                attributes = block.get("attrs")
                value = attributes.get("blockId") if isinstance(attributes, dict) else None
                editor_ids.append(str(value) if value else "")
    result: list[tuple[str, str, str]] = []
    for index, text_value in enumerate(raw_blocks):
        first = text_value.splitlines()[0].strip()
        section = re.sub(r"^#{1,6}\s+", "", first)[:160] or note.title
        block_id = (
            editor_ids[index]
            if index < len(editor_ids) and editor_ids[index]
            else str(uuid.uuid5(uuid.NAMESPACE_URL, f"cial-note-block:{note.id}:{index}"))
        )
        result.append((block_id, section, text_value))
    return result


class NoteIndexingService:
    def __init__(self, session: Session, engine: Any) -> None:
        self.session = session
        self.engine = engine

    def prepare(
        self,
        note_id: uuid.UUID,
        revision: int,
        action: str,
    ) -> PreparedNoteRevision:
        """Hydrate authoritative note chunks without loading or invoking an embedding model."""

        note = self.session.get(Note, note_id)
        if note is None:
            raise ValueError("The note indexing target no longer exists.")
        if revision != note.revision:
            raise SupersededNoteRevision(
                f"Note revision {revision} was superseded by revision {note.revision}."
            )
        remove = action == "remove" or note.deleted_at is not None or note.is_archived
        if remove:
            return PreparedNoteRevision(
                note_id=note.id,
                revision=revision,
                action="remove",
                content_hash=None,
                chunks=[],
            )

        user = self.session.get(User, note.owner_user_id)
        department_id = user.department_id if user else None
        digest = hashlib.sha256((note.content_markdown or "").encode()).hexdigest()
        chunks: list[LangchainDocument] = []
        for index, (block_id, section, body) in enumerate(_blocks(note)):
            chunk_id = f"note:{note.id}:{note.revision}:{index}"
            metadata = {
                "entity_type": "note",
                "note_id": str(note.id),
                "note_revision": note.revision,
                "workspace_id": str(note.workspace_id),
                "organization_id": str(note.organization_id),
                "repository_id": f"personal:{note.owner_user_id}",
                "storage_scope": "personal",
                "owner_user_id": str(note.owner_user_id),
                "department_id": str(department_id) if department_id else None,
                "folder_id": None,
                "visibility": "private",
                "lifecycle_status": "active",
                "title": note.title,
                "file_name": note.title,
                "relative_path": note_relative_path(note.id),
                "section": section,
                "block_ids": [block_id],
                "block_id": block_id,
                "chunk_index": index,
                "chunk_id": chunk_id,
                "content_hash": digest,
                "created_at": note.created_at.isoformat(),
                "updated_at": note.updated_at.isoformat(),
            }
            chunks.append(LangchainDocument(page_content=body, metadata=metadata))
        return PreparedNoteRevision(
            note_id=note.id,
            revision=revision,
            action="index",
            content_hash=digest,
            chunks=chunks,
        )

    def write_prepared(
        self,
        prepared: PreparedNoteRevision,
        embeddings: np.ndarray,
    ) -> dict[str, int]:
        """Write and verify the new revision before deleting stale note points."""

        note = self.session.scalar(
            select(Note).where(Note.id == prepared.note_id).with_for_update()
        )
        if note is None:
            raise ValueError("The note indexing target no longer exists.")
        if note.revision != prepared.revision:
            raise SupersededNoteRevision(
                f"Note revision {prepared.revision} was superseded by revision {note.revision}."
            )
        pipeline = self.engine._pipeline
        if pipeline is None or pipeline.client is None:
            raise RuntimeError("Knowledge index is not ready for note indexing.")
        state = self.session.get(NoteIndexState, note.id)
        if state is None:
            state = NoteIndexState(note_id=note.id, status="pending")
            self.session.add(state)
            self.session.flush()
        state.status = "indexing"
        state.last_error = None
        self.session.commit()

        note_filter = Filter(
            must=[
                FieldCondition(
                    key="metadata.note_id",
                    match=MatchValue(value=str(note.id)),
                )
            ]
        )
        if prepared.action == "remove":
            self.session.expire_all()
            note = self.session.scalar(
                select(Note).where(Note.id == prepared.note_id).with_for_update()
            )
            if note is None or note.revision != prepared.revision:
                raise SupersededNoteRevision("The note changed before removal finalization.")
            removed = self._count(pipeline, note_filter)
            self._delete_filter(pipeline, note_filter, affected_count=removed)
            state = self.session.get(NoteIndexState, note.id)
            state.status = "removed"
            state.indexed_revision = note.revision
            state.point_count = 0
            state.content_hash = None
            state.updated_at = datetime.now(timezone.utc)
            self.session.commit()
            return {
                "documents_seen": 1,
                "documents_indexed": 1,
                "chunks_indexed": 0,
            }

        if len(prepared.chunks) != len(embeddings):
            raise ValueError("Note chunk and embedding counts do not match.")
        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.metadata["chunk_id"])),
                vector=np.asarray(vector).tolist(),
                payload={"text": chunk.page_content, "metadata": chunk.metadata},
            )
            for chunk, vector in zip(prepared.chunks, embeddings, strict=True)
        ]
        if points:
            execute_qdrant_operation(
                pipeline.config,
                "upsert",
                lambda timeout: pipeline.client.upsert(
                    collection_name=pipeline.config.qdrant_collection_name,
                    points=points,
                    wait=True,
                    timeout=timeout,
                ),
                affected_count=len(points),
            )
        revision_filter = Filter(
            must=[
                *note_filter.must,
                FieldCondition(
                    key="metadata.note_revision",
                    match=MatchValue(value=prepared.revision),
                ),
            ]
        )
        verified = self._count(pipeline, revision_filter)
        if verified != len(points):
            raise RuntimeError(
                f"Qdrant note verification expected {len(points)} points and found {verified}."
            )
        # Lock only for the short stale-delete/finalization window. If a new
        # save committed during embedding/upsert, remove the now-obsolete new
        # points and leave the last previously verified revision untouched.
        self.session.expire_all()
        note = self.session.scalar(
            select(Note).where(Note.id == prepared.note_id).with_for_update()
        )
        if note is None or note.revision != prepared.revision:
            self._delete_filter(
                pipeline,
                revision_filter,
                affected_count=verified,
            )
            raise SupersededNoteRevision("The note changed during index writing.")
        stale_filter = Filter(
            must=note_filter.must,
            must_not=[
                FieldCondition(
                    key="metadata.note_revision",
                    match=MatchValue(value=prepared.revision),
                )
            ],
        )
        stale = self._count(pipeline, stale_filter)
        self._delete_filter(pipeline, stale_filter, affected_count=stale)

        state = self.session.get(NoteIndexState, note.id)
        state.status = "indexed"
        state.indexed_revision = prepared.revision
        state.content_hash = prepared.content_hash
        state.point_count = len(points)
        state.last_error = None
        state.updated_at = datetime.now(timezone.utc)
        self.session.commit()
        return {
            "documents_seen": 1,
            "documents_indexed": 1,
            "chunks_indexed": len(points),
        }

    def process(self, note_id: uuid.UUID, revision: int, action: str) -> dict[str, int]:
        """Compatibility wrapper for explicit single-note tools and tests."""

        prepared = self.prepare(note_id, revision, action)
        pipeline = self.engine._pipeline
        if pipeline is None or pipeline.embedding_model is None:
            raise RuntimeError("Knowledge index is not ready for note indexing.")
        vectors = (
            np.asarray(
                embed_texts(
                    pipeline.embedding_model,
                    [chunk.page_content for chunk in prepared.chunks],
                    batch_size=pipeline.config.embedding_batch_size,
                )
            )
            if prepared.chunks
            else np.empty((0, 0), dtype=np.float32)
        )
        return self.write_prepared(prepared, vectors)

    @staticmethod
    def _count(pipeline: Any, query_filter: Filter) -> int:
        result = execute_qdrant_operation(
            pipeline.config,
            "count",
            lambda timeout: pipeline.client.count(
                collection_name=pipeline.config.qdrant_collection_name,
                count_filter=query_filter,
                exact=True,
                timeout=timeout,
            ),
        )
        return int(result.count)

    @staticmethod
    def _delete_filter(pipeline: Any, query_filter: Filter, *, affected_count: int) -> None:
        if affected_count <= 0:
            return
        execute_qdrant_operation(
            pipeline.config,
            "delete",
            lambda timeout: pipeline.client.delete(
                collection_name=pipeline.config.qdrant_collection_name,
                points_selector=FilterSelector(filter=query_filter),
                wait=True,
                timeout=timeout,
            ),
            affected_count=affected_count,
        )
