"""Email/password authentication service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
import uuid

from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.orm import selectinload

from backend.app.core.config import settings
from backend.app.db.session import SessionLocal
from backend.app.models.identity import (
    DepartmentRoleAssignment,
    GroupMembership,
    Permission,
    Role,
    User,
    UserCredential,
)
from backend.app.repositories.users import UserRepository
from backend.app.schemas.auth import AuthenticatedUser
from backend.app.security.passwords import hash_password, verify_password


_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthServiceError(RuntimeError):
    pass


class AuthValidationError(AuthServiceError):
    pass


class AuthConflictError(AuthServiceError):
    pass


class AuthInvalidCredentials(AuthServiceError):
    pass


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    user: User
    profile: AuthenticatedUser


def _normalize_email(email: str) -> str:
    return email.strip().casefold()


def _initials(display_name: str) -> str:
    parts = [part[:1].upper() for part in display_name.split() if part.strip()]
    return "".join(parts[:2]) or "CU"


def _load_user_with_access_graph(session: object, user_id: uuid.UUID) -> User | None:
    if not hasattr(session, "scalar"):
        return None
    return session.scalar(
        select(User)
        .options(
            selectinload(User.organization),
            selectinload(User.department),
            selectinload(User.roles).selectinload(Role.permissions),
            selectinload(User.department_role_assignments)
            .selectinload(DepartmentRoleAssignment.role)
            .selectinload(Role.permissions),
            selectinload(User.group_memberships).selectinload(GroupMembership.group),
            selectinload(User.local_credential),
        )
        .where(User.id == user_id)
    )


def _to_profile(user: User) -> AuthenticatedUser:
    permissions = {
        permission.name
        for role in user.roles
        for permission in role.permissions
        if isinstance(permission, Permission)
    }
    for assignment in user.department_role_assignments:
        permissions.update(
            permission.name
            for permission in assignment.role.permissions
            if isinstance(permission, Permission)
        )
    role_names = sorted({role.name for role in user.roles})
    role_names.extend(
        sorted(
            {
                assignment.role.name
                for assignment in user.department_role_assignments
                if assignment.role is not None
            }
            - set(role_names)
        )
    )
    return AuthenticatedUser(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        initials=_initials(user.display_name),
        organization_name=user.organization.name if user.organization else None,
        department_name=user.department.name if user.department else None,
        role_names=role_names,
        permission_names=sorted(permissions),
        notifications_count=0,
    )


class AuthService:
    def _require_session(self):
        if SessionLocal is None:
            raise AuthServiceError("Authentication is unavailable because DATABASE_URL is not configured.")
        return SessionLocal()

    @staticmethod
    def _validate_signup_payload(full_name: str, email: str, password: str) -> None:
        if len(full_name.strip()) < 2:
            raise AuthValidationError("Full name must be at least 2 characters.")
        if not _EMAIL_PATTERN.match(_normalize_email(email)):
            raise AuthValidationError("Enter a valid email address.")
        if len(password) < 8:
            raise AuthValidationError("Password must be at least 8 characters.")

    @staticmethod
    def _validate_login_payload(email: str, password: str) -> None:
        if not _EMAIL_PATTERN.match(_normalize_email(email)):
            raise AuthValidationError("Enter a valid email address.")
        if not password:
            raise AuthValidationError("Password is required.")

    def signup(self, *, full_name: str, email: str, password: str) -> AuthenticationResult:
        self._validate_signup_payload(full_name, email, password)
        normalized_email = _normalize_email(email)
        with self._require_session() as session:
            repository = UserRepository(session)
            if repository.get_by_email(normalized_email) is not None:
                raise AuthConflictError("An account with that email already exists.")
            organization = repository.get_organization_by_code(
                settings.auth_default_organization_code
            )
            role = repository.get_role_by_name(settings.auth_default_role_name)
            department = repository.get_default_department_by_code(
                settings.auth_default_department_code
            )
            if organization is None or role is None:
                raise AuthServiceError("Authentication defaults are not configured correctly.")
            now = datetime.now(timezone.utc)
            user = repository.add(
                User(
                    organization_id=organization.id,
                    department_id=department.id if department is not None else None,
                    designation_id=None,
                    employee_id=None,
                    email=normalized_email,
                    display_name=full_name.strip(),
                    phone=None,
                    profile_photo_url=None,
                    status="active",
                    is_active=True,
                    auth_provider="local",
                    auth_subject=normalized_email,
                    last_login_at=now,
                )
            )
            user.roles.append(role)
            repository.add_local_credential(
                UserCredential(
                    user=user,
                    password_hash=hash_password(password),
                    password_algorithm="scrypt",
                    password_updated_at=now,
                )
            )
            session.commit()
            loaded_user = _load_user_with_access_graph(session, user.id)
            if loaded_user is None:
                raise AuthServiceError("Created user could not be reloaded.")
            return AuthenticationResult(user=loaded_user, profile=_to_profile(loaded_user))

    def login(self, *, email: str, password: str) -> AuthenticationResult:
        self._validate_login_payload(email, password)
        normalized_email = _normalize_email(email)
        with self._require_session() as session:
            repository = UserRepository(session)
            user = repository.get_by_email(normalized_email)
            if user is None or not bool(user.is_active):
                raise AuthInvalidCredentials("Invalid email or password.")
            loaded_user = _load_user_with_access_graph(session, user.id)
            if loaded_user is None or loaded_user.local_credential is None:
                raise AuthInvalidCredentials("Invalid email or password.")
            if not verify_password(password, loaded_user.local_credential.password_hash):
                raise AuthInvalidCredentials("Invalid email or password.")
            loaded_user.last_login_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(loaded_user)
            loaded_user = _load_user_with_access_graph(session, loaded_user.id)
            if loaded_user is None:
                raise AuthServiceError("Authenticated user could not be reloaded.")
            return AuthenticationResult(user=loaded_user, profile=_to_profile(loaded_user))

    def get_user_profile(self, user_id: uuid.UUID) -> AuthenticatedUser | None:
        with self._require_session() as session:
            user = _load_user_with_access_graph(session, user_id)
            if user is None or not bool(user.is_active):
                return None
            return _to_profile(user)

    def revoke_sessions(self, user_id: uuid.UUID) -> None:
        """Invalidate every token issued with the user's prior version."""

        with self._require_session() as session:
            session.execute(
                update(User)
                .where(User.id == user_id)
                .values(session_version=User.session_version + 1)
            )
            session.commit()
