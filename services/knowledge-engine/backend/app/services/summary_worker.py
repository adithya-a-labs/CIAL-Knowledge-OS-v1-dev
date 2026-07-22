"""Durable single-process worker for queued document analyses."""
from __future__ import annotations

import logging
import queue
from datetime import datetime, timezone
from threading import Thread
import uuid

from sqlalchemy import select, update

from backend.app.db.session import SessionLocal
from backend.app.models.knowledge import Document, DocumentVersion
from backend.app.models.workspace_content import SummaryArtifact
from backend.app.security.access import access_context_for_user, document_is_accessible
from backend.app.services.document_summary_service import (
    DocumentSummaryError,
    DocumentSummaryPipeline,
    mark_analysis_failed,
)

logger = logging.getLogger(__name__)
_SENTINEL = object()


class SummaryWorker:
    def __init__(self, generator) -> None:
        self.generator = generator
        self._queue: queue.Queue[object] = queue.Queue()
        self._thread: Thread | None = None
        self._running = False
        self.ready = False

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._running = True
        if SessionLocal is not None:
            with SessionLocal() as db:
                db.execute(update(SummaryArtifact).where(
                    SummaryArtifact.document_id.is_not(None), SummaryArtifact.status == "running",
                ).values(status="queued", progress={"stage": "queued", "completed": 0, "total": 0, "message": "Recovered after interrupted worker"}))
                db.commit()
        self._thread = Thread(target=self._loop, name="document-summary-worker", daemon=True)
        self._thread.start(); self.ready = True; self.enqueue()
        logger.info("document_summary_worker_started")

    def stop(self) -> None:
        self._running = False; self._queue.put(_SENTINEL)
        if self._thread is not None:
            self._thread.join(timeout=30)
        self._thread = None; self.ready = False

    def enqueue(self, artifact_id: uuid.UUID | None = None) -> None:
        self._queue.put(artifact_id)

    def _loop(self) -> None:
        while self._running:
            try:
                item = self._queue.get(timeout=2)
            except queue.Empty:
                item = None
            if item is _SENTINEL:
                return
            while self._running:
                artifact_id = self._claim(item if isinstance(item, uuid.UUID) else None)
                item = None
                if artifact_id is None:
                    break
                self._process(artifact_id)

    def _claim(self, preferred: uuid.UUID | None) -> uuid.UUID | None:
        if SessionLocal is None:
            return None
        with SessionLocal() as db, db.begin():
            statement = select(SummaryArtifact).where(
                SummaryArtifact.document_id.is_not(None), SummaryArtifact.status == "queued",
                SummaryArtifact.deleted_at.is_(None),
            )
            if preferred is not None:
                statement = statement.where(SummaryArtifact.id == preferred)
            artifact = db.scalar(statement.order_by(SummaryArtifact.created_at, SummaryArtifact.id).with_for_update(skip_locked=True).limit(1))
            if artifact is None:
                return None
            artifact.status = "running"
            artifact.started_at = artifact.updated_at = datetime.now(timezone.utc)
            artifact.generation_config = {**(artifact.generation_config or {}), "queue_latency_ms": max(0, int((artifact.started_at - artifact.created_at).total_seconds() * 1000))}
            artifact.progress = {"stage": "loading_chunks", "completed": 0, "total": 0, "message": "Preparing document analysis"}
            return artifact.id

    def _process(self, artifact_id: uuid.UUID) -> None:
        if SessionLocal is None:
            return
        with SessionLocal() as db:
            try:
                artifact = db.get(SummaryArtifact, artifact_id)
                if artifact is None or artifact.status != "running" or artifact.document_id is None or artifact.document_version_id is None:
                    return
                document = db.get(Document, artifact.document_id)
                version = db.get(DocumentVersion, artifact.document_version_id)
                access = access_context_for_user(db, artifact.created_by_user_id or artifact.owner_user_id)
                if document is None or version is None or version.document_id != document.id or not document_is_accessible(document, access):
                    raise DocumentSummaryError("Analysis source is unavailable.", code="analysis_source_unavailable", status_code=404)
                DocumentSummaryPipeline(db, self.generator).run(artifact, document, version)
                logger.info("document_summary_completed", extra={"event": "document_summary_completed", "summary_id": str(artifact_id)})
            except Exception as exc:
                db.rollback(); mark_analysis_failed(db, artifact_id, exc)
                logger.exception("document_summary_failed", extra={"event": "document_summary_failed", "summary_id": str(artifact_id), "error_code": getattr(exc, "code", "analysis_generation_failed")})
