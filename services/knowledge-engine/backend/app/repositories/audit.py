"""Audit repository helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.operations import AuditEvent


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, event: AuditEvent) -> AuditEvent:
        self.session.add(event)
        return event

    def list_for_user(self, user_id: uuid.UUID) -> list[AuditEvent]:
        return list(
            self.session.scalars(
                select(AuditEvent)
                .where(AuditEvent.user_id == user_id)
                .order_by(AuditEvent.created_at.desc())
            )
        )

    def list_for_entity(self, entity_type: str, entity_id: uuid.UUID) -> list[AuditEvent]:
        return list(
            self.session.scalars(
                select(AuditEvent)
                .where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
                .order_by(AuditEvent.created_at.desc())
            )
        )

