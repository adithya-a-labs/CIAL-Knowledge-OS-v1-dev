"""Access-control helpers for backend routes and services."""

from .access import (
    AccessPrincipal,
    RequestAccessContext,
    anonymous_access_context,
    apply_document_access_filter,
    can_sync_corpus,
    can_upload_enterprise_documents,
    document_is_accessible,
    list_accessible_documents,
    list_accessible_relative_paths,
    resolve_access_context,
)

__all__ = [
    "AccessPrincipal",
    "RequestAccessContext",
    "anonymous_access_context",
    "apply_document_access_filter",
    "can_sync_corpus",
    "can_upload_enterprise_documents",
    "document_is_accessible",
    "list_accessible_documents",
    "list_accessible_relative_paths",
    "resolve_access_context",
]
