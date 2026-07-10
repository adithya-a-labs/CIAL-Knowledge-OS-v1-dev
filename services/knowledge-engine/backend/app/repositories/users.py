"""User and role repository helpers."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.identity import Department, Organization, Role, User, UserCredential


class UserRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, user_id: uuid.UUID) -> User | None:
        return self.session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        normalized_email = email.strip().casefold()
        return self.session.scalar(
            select(User).where(func.lower(User.email) == normalized_email)
        )

    def get_role_by_name(self, name: str) -> Role | None:
        return self.session.scalar(select(Role).where(Role.name == name))

    def list_roles(self) -> list[Role]:
        return list(self.session.scalars(select(Role).order_by(Role.name)))

    def get_organization_by_code(self, code: str) -> Organization | None:
        return self.session.scalar(select(Organization).where(Organization.code == code))

    def get_default_department_by_code(self, code: str) -> Department | None:
        return self.session.scalar(select(Department).where(Department.code == code))

    def add(self, user: User) -> User:
        self.session.add(user)
        return user

    def add_local_credential(self, credential: UserCredential) -> UserCredential:
        self.session.add(credential)
        return credential
