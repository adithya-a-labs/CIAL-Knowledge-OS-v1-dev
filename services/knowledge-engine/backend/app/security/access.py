"""Reusable access-control policy helpers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid

from fastapi import Request
from sqlalchemy import and_, exists, false, literal, or_, select
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.sql import ColumnElement, Select

from backend.app.db.session import SessionLocal
from backend.app.models.identity import DepartmentRoleAssignment, GroupMembership, Permission, Role, User
from backend.app.models.knowledge import (
    Document,
    DocumentPermission,
    FolderPermission,
    WorkspacePermission,
)


AccessScope = str
_VALID_ACCESS_SCOPES = {"enterprise", "my-workspace", "hybrid"}
_VIEW_PERMISSION_ORDER = ("view", "edit", "manage", "delete")
_ENTERPRISE_READ_PERMISSIONS = frozenset({"view_enterprise_documents", "manage_enterprise_documents"})
_DEPARTMENT_READ_PERMISSIONS = frozenset({"view_department_documents", "manage_enterprise_documents"})
_ENTERPRISE_WRITE_PERMISSIONS = frozenset({"upload_enterprise_documents", "manage_enterprise_documents"})
_CORPUS_SYNC_PERMISSIONS = frozenset({"manage_enterprise_documents", "manage_settings"})


@dataclass(frozen=True, slots=True)
class AccessPrincipal:
    user_id: uuid.UUID | None = None
    organization_id: uuid.UUID | None = None
    department_ids: frozenset[uuid.UUID] = frozenset()
    role_ids: frozenset[uuid.UUID] = frozenset()
    permission_names: frozenset[str] = frozenset()
    group_ids: frozenset[uuid.UUID] = frozenset()
    is_authenticated: bool = False


@dataclass(frozen=True, slots=True)
class RequestAccessContext:
    principal: AccessPrincipal = field(default_factory=AccessPrincipal)
    scope: AccessScope = "enterprise"
    user_header: str | None = None


def anonymous_access_context() -> RequestAccessContext:
    return RequestAccessContext(principal=AccessPrincipal(), scope="enterprise")


def resolve_access_context(request: Request) -> RequestAccessContext:
    raw_user_id = request.headers.get("X-CIAL-User-Id") or request.headers.get("X-User-Id")
    raw_scope = (request.headers.get("X-CIAL-Access-Scope") or "").strip().casefold()
    scope = raw_scope if raw_scope in _VALID_ACCESS_SCOPES else None
    if not raw_user_id or SessionLocal is None:
        return RequestAccessContext(
            principal=AccessPrincipal(),
            scope=scope or "enterprise",
            user_header=raw_user_id or None,
        )

    try:
        user_id = uuid.UUID(raw_user_id)
    except ValueError:
        return RequestAccessContext(
            principal=AccessPrincipal(),
            scope=scope or "enterprise",
            user_header=raw_user_id,
        )

    with SessionLocal() as session:
        user = session.scalar(
            select(User)
            .options(
                selectinload(User.roles).selectinload(Role.permissions),
                selectinload(User.department_memberships),
                selectinload(User.department_role_assignments)
                .selectinload(DepartmentRoleAssignment.role)
                .selectinload(Role.permissions),
                selectinload(User.group_memberships).selectinload(GroupMembership.group),
            )
            .where(User.id == user_id)
        )
        if user is None or not bool(user.is_active):
            return RequestAccessContext(
                principal=AccessPrincipal(),
                scope=scope or "enterprise",
                user_header=raw_user_id,
            )

        now = datetime.now(timezone.utc)
        department_ids = {
            department_id
            for department_id in [user.department_id]
            if department_id is not None
        }
        department_ids.update(
            membership.department_id
            for membership in user.department_memberships
            if bool(membership.active)
        )

        role_ids = {role.id for role in user.roles}
        permission_names = {
            permission.name
            for role in user.roles
            for permission in role.permissions
            if isinstance(permission, Permission)
        }
        for assignment in user.department_role_assignments:
            role_ids.add(assignment.role_id)
            permission_names.update(
                permission.name
                for permission in assignment.role.permissions
                if isinstance(permission, Permission)
            )

        group_ids = {
            membership.group_id
            for membership in user.group_memberships
            if bool(membership.is_active)
            and (membership.expires_at is None or membership.expires_at > now)
        }

        principal = AccessPrincipal(
            user_id=user.id,
            organization_id=user.organization_id,
            department_ids=frozenset(department_ids),
            role_ids=frozenset(role_ids),
            permission_names=frozenset(permission_names),
            group_ids=frozenset(group_ids),
            is_authenticated=True,
        )
        return RequestAccessContext(
            principal=principal,
            scope=scope or "hybrid",
            user_header=raw_user_id,
        )


def can_upload_enterprise_documents(access_context: RequestAccessContext) -> bool:
    permissions = access_context.principal.permission_names
    if permissions.intersection(_ENTERPRISE_WRITE_PERMISSIONS):
        return True
    return not access_context.principal.is_authenticated


def can_sync_corpus(access_context: RequestAccessContext) -> bool:
    permissions = access_context.principal.permission_names
    if permissions.intersection(_CORPUS_SYNC_PERMISSIONS):
        return True
    return not access_context.principal.is_authenticated


def has_enterprise_read_access(access_context: RequestAccessContext) -> bool:
    permissions = access_context.principal.permission_names
    return bool(permissions.intersection(_ENTERPRISE_READ_PERMISSIONS)) or not access_context.principal.is_authenticated


def has_department_read_access(access_context: RequestAccessContext) -> bool:
    permissions = access_context.principal.permission_names
    return bool(permissions.intersection(_DEPARTMENT_READ_PERMISSIONS))


def document_is_soft_deleted(document: Document) -> bool:
    lifecycle_status = str(document.lifecycle_status or "").casefold()
    indexing_status = str(document.indexing_status or "").casefold()
    return document.deleted_at is not None or lifecycle_status == "deleted" or indexing_status == "deleted"


def document_is_accessible(document: Document, access_context: RequestAccessContext) -> bool:
    if document_is_soft_deleted(document):
        return False

    principal = access_context.principal
    is_owner = principal.user_id is not None and document.owner_user_id == principal.user_id

    if access_context.scope == "my-workspace":
        return bool(
            is_owner
            and str(document.storage_scope or "").casefold() == "personal"
        )

    if str(document.storage_scope or "").casefold() == "personal":
        return is_owner

    visibility = str(document.visibility or "").casefold()
    if visibility == "enterprise":
        return has_enterprise_read_access(access_context)
    if visibility == "department":
        return (
            has_department_read_access(access_context)
            and document.department_id in principal.department_ids
        )
    if visibility in {"restricted", "private"}:
        return is_owner and access_context.scope != "enterprise"
    return False


def list_accessible_documents(session: Session, access_context: RequestAccessContext) -> list[Document]:
    statement = apply_document_access_filter(select(Document).order_by(Document.name), access_context)
    return list(session.scalars(statement))


def list_accessible_relative_paths(session: Session, access_context: RequestAccessContext) -> frozenset[str]:
    documents = list_accessible_documents(session, access_context)
    return frozenset(
        str(document.relative_path or "").replace("\\", "/").strip("/")
        for document in documents
        if document.relative_path
    )


def apply_document_access_filter(
    statement: Select[tuple[Document]] | Select,
    access_context: RequestAccessContext,
    *,
    action: str = "view",
    allowed_relative_paths: Iterable[str] | None = None,
) -> Select:
    principal = access_context.principal
    requested_permissions = _acl_permissions_for_action(action)
    deleted_clause = and_(
        Document.deleted_at.is_(None),
        or_(Document.lifecycle_status.is_(None), Document.lifecycle_status != "deleted"),
        or_(Document.indexing_status.is_(None), Document.indexing_status != "deleted"),
    )

    scope_clauses: list[ColumnElement[bool]] = []
    acl_clause = _document_acl_clause(principal, requested_permissions)
    own_personal_clause = false()
    if principal.user_id is not None:
        own_personal_clause = and_(
            Document.storage_scope == literal("personal"),
            Document.owner_user_id == principal.user_id,
        )

    if access_context.scope in {"enterprise", "hybrid"}:
        scope_clauses.append(
            and_(
                Document.storage_scope == literal("enterprise"),
                Document.visibility == literal("enterprise"),
            )
        )
        if has_department_read_access(access_context) and principal.department_ids:
            scope_clauses.append(
                and_(
                    Document.storage_scope == literal("enterprise"),
                    Document.visibility == literal("department"),
                    Document.department_id.in_(sorted(principal.department_ids)),
                )
            )
        if principal.permission_names.intersection(_ENTERPRISE_READ_PERMISSIONS):
            scope_clauses.append(
                and_(
                    Document.storage_scope == literal("enterprise"),
                    Document.visibility.in_(["restricted", "private"]),
                )
            )
        if access_context.scope == "hybrid":
            scope_clauses.append(own_personal_clause)
            scope_clauses.append(acl_clause)
        else:
            scope_clauses.append(
                and_(
                    Document.storage_scope == literal("enterprise"),
                    acl_clause,
                )
            )

    if access_context.scope == "my-workspace":
        scope_clauses.append(own_personal_clause)

    if not scope_clauses:
        scope_clauses.append(false())

    filtered = statement.where(deleted_clause, or_(*scope_clauses))
    normalized_paths = [
        str(value).replace("\\", "/").strip("/")
        for value in (allowed_relative_paths or [])
        if str(value).strip()
    ]
    if normalized_paths:
        filtered = filtered.where(Document.relative_path.in_(sorted(set(normalized_paths))))
    return filtered


def _acl_permissions_for_action(action: str) -> tuple[str, ...]:
    normalized = action.strip().casefold()
    try:
        index = _VIEW_PERMISSION_ORDER.index(normalized)
    except ValueError:
        return ("view",)
    if normalized == "manage":
        return ("manage",)
    if normalized == "delete":
        return ("delete", "manage")
    return _VIEW_PERMISSION_ORDER[index:]


def _principal_match_clause(model: type[DocumentPermission] | type[FolderPermission] | type[WorkspacePermission], principal: AccessPrincipal) -> ColumnElement[bool]:
    clauses: list[ColumnElement[bool]] = []
    if principal.user_id is not None:
        clauses.append(model.user_id == principal.user_id)
        clauses.append(
            and_(
                model.subject_type == literal("user"),
                model.subject_id == principal.user_id,
            )
        )
    if principal.department_ids:
        department_ids = sorted(principal.department_ids)
        clauses.append(model.department_id.in_(department_ids))
        clauses.append(
            and_(
                model.subject_type == literal("department"),
                model.subject_id.in_(department_ids),
            )
        )
    if principal.role_ids:
        role_ids = sorted(principal.role_ids)
        clauses.append(model.role_id.in_(role_ids))
        clauses.append(
            and_(
                model.subject_type == literal("role"),
                model.subject_id.in_(role_ids),
            )
        )
    if principal.group_ids:
        group_ids = sorted(principal.group_ids)
        clauses.append(model.group_id.in_(group_ids))
        clauses.append(
            and_(
                model.subject_type == literal("group"),
                model.subject_id.in_(group_ids),
            )
        )
    if not clauses:
        return false()
    expires_at = getattr(model, "expires_at", None)
    unexpired = literal(True) if expires_at is None else or_(expires_at.is_(None), expires_at > literal(datetime.now(timezone.utc)))
    return and_(or_(*clauses), unexpired)


def _document_acl_clause(principal: AccessPrincipal, permissions: tuple[str, ...]) -> ColumnElement[bool]:
    if not principal.is_authenticated:
        return false()

    document_acl = exists(
        select(literal(1)).where(
            DocumentPermission.document_id == Document.id,
            DocumentPermission.permission.in_(permissions),
            _principal_match_clause(DocumentPermission, principal),
        )
    )
    folder_acl = exists(
        select(literal(1)).where(
            FolderPermission.folder_id == Document.folder_id,
            FolderPermission.permission.in_(permissions),
            _principal_match_clause(FolderPermission, principal),
        )
    )
    workspace_acl = exists(
        select(literal(1)).where(
            WorkspacePermission.workspace_id == Document.workspace_id,
            WorkspacePermission.permission.in_(permissions),
            _principal_match_clause(WorkspacePermission, principal),
        )
    )
    return or_(document_acl, folder_acl, workspace_acl)
