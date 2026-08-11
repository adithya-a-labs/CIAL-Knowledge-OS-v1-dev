"""Ownership-scoped durable export job access."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from backend.app.models.operations import ExportJob

class ExportRepository:
    def __init__(self, session: Session) -> None: self.session = session
    def add(self, job: ExportJob) -> ExportJob: self.session.add(job); return job
    def get_for_user(self, export_id: uuid.UUID, user_id: uuid.UUID) -> ExportJob | None:
        return self.session.scalar(select(ExportJob).where(ExportJob.id == export_id, ExportJob.user_id == user_id))
    def get(self, export_id: uuid.UUID) -> ExportJob | None: return self.session.get(ExportJob, export_id)
    def list_for_user(self, user_id: uuid.UUID) -> list[ExportJob]:
        return list(self.session.scalars(select(ExportJob).where(ExportJob.user_id == user_id).order_by(ExportJob.created_at.desc()).limit(200)))
    def active_count(self, user_id: uuid.UUID | None = None) -> int:
        statement = select(func.count()).select_from(ExportJob).where(ExportJob.status.in_(("queued", "processing")))
        if user_id is not None: statement = statement.where(ExportJob.user_id == user_id)
        return int(self.session.scalar(statement) or 0)
    def mark_interrupted_failed(self) -> None:
        self.session.execute(update(ExportJob).where(ExportJob.status == "processing").values(status="failed", error_code="server_restarted", safe_error_message="Export generation was interrupted. Please retry.", completed_at=datetime.now(timezone.utc)))
