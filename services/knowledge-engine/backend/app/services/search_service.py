"""Deterministic, federated, authorization-first global search."""
from __future__ import annotations

import base64
import hashlib
import re
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from backend.app.models.conversations import ChatSession
from backend.app.models.identity import Department
from backend.app.models.knowledge import Document, DocumentChunk, Workspace
from backend.app.models.operations import RetrievalEvent, SearchHistory
from backend.app.models.workspace_content import Note, SavedKnowledgeItem, SummaryArtifact
from backend.app.schemas.search import SearchRequest
from backend.app.security.access import RequestAccessContext, apply_document_access_filter
from backend.app.services.personal_workspace_service import PersonalWorkspaceService


def normalize_query(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s-]", " ", value.casefold())).strip()


def _excerpt(value: str | None, query: str, limit: int = 320) -> str | None:
    if not value:
        return None
    clean = re.sub(r"<[^>]+>", " ", value)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return None
    position = clean.casefold().find(query)
    start = max(0, position - 80) if position >= 0 else 0
    clipped = clean[start:start + limit]
    return ("…" if start else "") + clipped + ("…" if start + limit < len(clean) else "")


def _rank(title: str, body: str | None, query: str) -> tuple[int, list[str]]:
    title_normalized = normalize_query(title)
    body_normalized = normalize_query(body or "")
    query_tokens = query.split()
    acronym = "".join(part[0] for part in title_normalized.split() if part)
    if title_normalized == query:
        return 100, ["Exact title"]
    if query in title_normalized:
        return (94 if title_normalized.startswith(query) else 90), ["Title phrase"]
    if len(query) >= 2 and acronym.startswith(query.replace(" ", "")):
        return 87, ["Acronym"]
    if query_tokens and all(token in title_normalized for token in query_tokens):
        return 84, ["Title terms"]
    if query in body_normalized:
        return 74, ["Exact phrase"]
    if query_tokens and all(token in body_normalized for token in query_tokens):
        return 66, ["Matching terms"]
    return 0, []


def _band(score: int) -> str:
    return "Highly relevant" if score >= 88 else "Relevant" if score >= 70 else "Related"


class SearchService:
    def __init__(self, session: Session):
        self.session = session

    def search(self, access: RequestAccessContext, payload: SearchRequest):
        started = time.perf_counter()
        user_id = access.principal.user_id
        organization_id = access.principal.organization_id
        workspace = PersonalWorkspaceService(self.session).get_or_create(access)
        query = normalize_query(payload.query)
        if not query:
            raise ValueError("Search query must contain letters or numbers.")
        requested = set(payload.filters.types)
        include = lambda kind: not requested or kind in requested
        rows: list[dict] = []

        document_statement = apply_document_access_filter(select(Document), access)
        if payload.filters.scope == "enterprise":
            document_statement = document_statement.where(Document.storage_scope == "enterprise")
        elif payload.filters.scope == "my_workspace":
            document_statement = document_statement.where(Document.storage_scope == "personal", Document.owner_user_id == user_id)
        if payload.filters.file_types:
            document_statement = document_statement.where(func.lower(Document.file_type).in_([item.casefold() for item in payload.filters.file_types]))
        if payload.filters.updated_after:
            document_statement = document_statement.where(Document.modified_at >= payload.filters.updated_after)
        if payload.filters.department_ids:
            try: document_statement = document_statement.where(Document.department_id.in_([uuid.UUID(item) for item in payload.filters.department_ids]))
            except ValueError as exc: raise ValueError("Invalid department filter.") from exc
        if payload.filters.workspace_ids:
            try: document_statement = document_statement.where(Document.workspace_id.in_([uuid.UUID(item) for item in payload.filters.workspace_ids]))
            except ValueError as exc: raise ValueError("Invalid workspace filter.") from exc
        documents = list(self.session.scalars(document_statement.order_by(Document.modified_at.desc().nullslast()).limit(250)))
        accessible_ids = [item.id for item in documents]
        departments = {item.id: item.name for item in self.session.scalars(select(Department).where(Department.id.in_({item.department_id for item in documents})))} if documents else {}
        workspaces = {item.id: item.name for item in self.session.scalars(select(Workspace).where(Workspace.id.in_({item.workspace_id for item in documents})))} if documents else {}

        if include("document"):
            for item in documents:
                score, reasons = _rank(item.name, item.relative_path, query)
                if not score: continue
                rows.append({"id": str(item.id), "type": "document", "title": item.name, "excerpt": None,
                    "match_reasons": reasons, "relevance": _band(score), "_score": score,
                    "workspace": workspaces.get(item.workspace_id), "department": departments.get(item.department_id),
                    "file_type": item.file_type.upper(), "updated_at": item.modified_at or item.updated_at,
                    "document_id": str(item.id), "page": None, "chunk_id": None, "can_use_as_context": True,
                    "deep_link": f"/knowledge/document/{item.id}"})

        if payload.mode == "full" and include("passage") and accessible_ids:
            terms = [f"%{token}%" for token in query.split()[:8]]
            clauses = [func.lower(func.coalesce(DocumentChunk.text_preview, DocumentChunk.text, "")).like(term) for term in terms]
            chunks = list(self.session.scalars(select(DocumentChunk).where(DocumentChunk.document_id.in_(accessible_ids), or_(*clauses)).limit(80))) if clauses else []
            by_id = {item.id: item for item in documents}
            for chunk in chunks:
                document = by_id.get(chunk.document_id)
                if document is None: continue
                body = chunk.text_preview or chunk.text or ""
                score, reasons = _rank(document.name, body, query)
                if not score: continue
                rows.append({"id": str(chunk.id), "type": "passage", "title": document.name,
                    "excerpt": _excerpt(body, query), "match_reasons": reasons, "relevance": _band(score), "_score": score,
                    "workspace": workspaces.get(document.workspace_id), "department": departments.get(document.department_id),
                    "file_type": document.file_type.upper(), "updated_at": document.modified_at or document.updated_at,
                    "document_id": str(document.id), "page": chunk.page, "chunk_id": chunk.chunk_id,
                    "can_use_as_context": True, "deep_link": f"/knowledge/document/{document.id}?page={chunk.page or 1}&chunk={chunk.chunk_id}"})

        if include("note") and payload.filters.scope != "enterprise":
            notes = list(self.session.scalars(select(Note).where(Note.owner_user_id == user_id, Note.workspace_id == workspace.id, Note.deleted_at.is_(None)).order_by(Note.updated_at.desc()).limit(150)))
            for item in notes:
                score, reasons = _rank(item.title, item.plain_text, query)
                if score: rows.append({"id": str(item.id), "type": "note", "title": item.title, "excerpt": _excerpt(item.plain_text, query),
                    "match_reasons": reasons, "relevance": _band(score), "_score": score, "workspace": "My Workspace", "department": None,
                    "file_type": None, "updated_at": item.updated_at, "document_id": None, "page": None, "chunk_id": None,
                    "can_use_as_context": True, "deep_link": f"/workspace/notes?note={item.id}"})

        if include("conversation") and payload.filters.scope != "enterprise":
            sessions = list(self.session.scalars(select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.updated_at.desc()).limit(150)))
            for item in sessions:
                score, reasons = _rank(item.title or "New conversation", None, query)
                if score: rows.append({"id": str(item.id), "type": "conversation", "title": item.title or "New conversation", "excerpt": None,
                    "match_reasons": reasons, "relevance": _band(score), "_score": score, "workspace": "My Workspace", "department": None,
                    "file_type": None, "updated_at": item.updated_at, "document_id": None, "page": None, "chunk_id": None,
                    "can_use_as_context": False, "deep_link": f"/assistant?session={item.id}"})

        if payload.mode == "full" and include("summary") and payload.filters.scope != "enterprise":
            summaries = list(self.session.scalars(select(SummaryArtifact).where(SummaryArtifact.owner_user_id == user_id, SummaryArtifact.workspace_id == workspace.id, SummaryArtifact.deleted_at.is_(None)).order_by(SummaryArtifact.updated_at.desc()).limit(150)))
            for item in summaries:
                score, reasons = _rank(item.title, item.content_markdown, query)
                if score: rows.append({"id": str(item.id), "type": "summary", "title": item.title, "excerpt": _excerpt(item.content_markdown, query),
                    "match_reasons": reasons, "relevance": _band(score), "_score": score, "workspace": "My Workspace", "department": None,
                    "file_type": None, "updated_at": item.updated_at, "document_id": None, "page": None, "chunk_id": None,
                    "can_use_as_context": False, "deep_link": f"/workspace/summaries/{item.id}"})

        if payload.mode == "full" and include("saved_knowledge") and payload.filters.scope != "enterprise":
            saved = list(self.session.scalars(select(SavedKnowledgeItem).where(SavedKnowledgeItem.owner_user_id == user_id, SavedKnowledgeItem.workspace_id == workspace.id, SavedKnowledgeItem.deleted_at.is_(None)).order_by(SavedKnowledgeItem.updated_at.desc()).limit(150)))
            for item in saved:
                score, reasons = _rank(item.title, item.body_markdown, query)
                if score: rows.append({"id": str(item.id), "type": "saved_knowledge", "title": item.title, "excerpt": _excerpt(item.body_markdown, query),
                    "match_reasons": reasons, "relevance": _band(score), "_score": score, "workspace": "My Workspace", "department": None,
                    "file_type": None, "updated_at": item.updated_at, "document_id": None, "page": None, "chunk_id": None,
                    "can_use_as_context": False, "deep_link": f"/saved-knowledge?item={item.id}"})

        rows.sort(key=lambda item: (-item["_score"], -(item["updated_at"] or datetime.min.replace(tzinfo=timezone.utc)).timestamp(), item["title"].casefold(), item["id"]))
        offset = self._decode_cursor(payload.cursor)
        page = rows[offset:offset + payload.limit]
        next_cursor = self._encode_cursor(offset + payload.limit) if offset + payload.limit < len(rows) else None
        counts = dict(Counter(item["type"] for item in rows))
        for item in page: item.pop("_score", None)
        interpretation = self._interpret(payload.query, payload.interpret)
        if payload.mode == "full": self._record(access, payload, len(rows), int((time.perf_counter() - started) * 1000))
        return {"query": payload.query.strip(), "items": page, "counts": counts, "next_cursor": next_cursor,
            "interpretation": interpretation, "lexical_available": True, "semantic_available": False}

    def recent(self, access: RequestAccessContext):
        rows = list(self.session.scalars(select(SearchHistory).where(SearchHistory.user_id == access.principal.user_id).order_by(SearchHistory.updated_at.desc()).limit(10)))
        return {"items": [{"id": str(item.id), "query": item.query_text, "updated_at": item.updated_at} for item in rows]}

    def clear_recent(self, access: RequestAccessContext, history_id: uuid.UUID | None = None):
        statement = delete(SearchHistory).where(SearchHistory.user_id == access.principal.user_id)
        if history_id: statement = statement.where(SearchHistory.id == history_id)
        self.session.execute(statement); self.session.commit()

    def _record(self, access, payload, result_count, latency_ms):
        normalized = normalize_query(payload.query)
        item = self.session.scalar(select(SearchHistory).where(SearchHistory.user_id == access.principal.user_id, SearchHistory.normalized_query == normalized))
        if item is None:
            item = SearchHistory(organization_id=access.principal.organization_id, user_id=access.principal.user_id, query_text=payload.query.strip(), normalized_query=normalized)
            self.session.add(item)
        item.query_text=payload.query.strip(); item.result_count=result_count; item.updated_at=datetime.now(timezone.utc)
        self.session.add(RetrievalEvent(organization_id=access.principal.organization_id, user_id=access.principal.user_id,
            query_text=f"sha256:{hashlib.sha256(normalized.encode()).hexdigest()}", retrieval_scope="global_search",
            filters_applied=payload.filters.model_dump(mode="json"), latency_ms=latency_ms, result_count=result_count))
        self.session.flush()
        keep=list(self.session.scalars(select(SearchHistory.id).where(SearchHistory.user_id==access.principal.user_id).order_by(SearchHistory.updated_at.desc()).offset(10)))
        if keep:self.session.execute(delete(SearchHistory).where(SearchHistory.id.in_(keep)))
        self.session.commit()

    @staticmethod
    def _interpret(raw: str, enabled: bool):
        if not enabled: return {"applied": False, "explanation": None, "chips": []}
        lowered=raw.casefold(); chips=[]
        if any(term in lowered for term in ("recent", "recently", "latest")): chips.append("Recently updated")
        type_terms={"documents":"Documents","passages":"Passages","notes":"Notes","conversations":"Conversations","summaries":"Summaries"}
        chips.extend(label for term,label in type_terms.items() if re.search(rf"\b{term}\b",lowered))
        return {"applied": bool(chips), "explanation": f"Interpreted as {', '.join(chips)}." if chips else None, "chips": chips}

    @staticmethod
    def _decode_cursor(value: str | None) -> int:
        if not value:return 0
        try:return max(0,int(base64.urlsafe_b64decode(value.encode()).decode()))
        except Exception as exc:raise ValueError("Invalid search cursor.") from exc

    @staticmethod
    def _encode_cursor(offset: int) -> str:
        return base64.urlsafe_b64encode(str(offset).encode()).decode()
