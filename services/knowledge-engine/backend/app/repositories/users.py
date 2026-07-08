"""User and role repository helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.identity import Organization, Role, User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalar(select(User).where(User.email == email))

    def list_roles(self) -> list[Role]:
        return list(self.session.scalars(select(Role).order_by(Role.name)))

    def get_organization_by_code(self, code: str) -> Organization | None:
        return self.session.scalar(select(Organization).where(Organization.code == code))

    def add(self, user: User) -> User:
        self.session.add(user)
        return user

