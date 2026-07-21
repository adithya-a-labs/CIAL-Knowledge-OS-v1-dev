"""Authoritative authorization/provenance metadata for indexed chunks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import uuid

from backend.app.models.knowledge import Document, DocumentVersion
from backend.app.core.config import settings


class ChunkMetadataContractError(ValueError):
    code = "indexing_metadata_invalid"

    def __init__(self, validation: "MetadataValidation") -> None:
        super().__init__("Managed chunk authorization metadata is incomplete.")
        self.validation = validation


def _uuid(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value) if isinstance(value, uuid.UUID) else str(uuid.UUID(str(value)))


def build_chunk_metadata(document: Document, version: DocumentVersion, *, lifecycle_status: str = "indexed") -> dict[str, Any]:
    """Build trusted metadata exclusively from persisted server-side models."""
    repository_id = document.repository_id
    if not repository_id and document.storage_scope == "personal" and document.owner_user_id:
        repository_id = f"personal:{document.owner_user_id}"
    if not repository_id and document.storage_scope == "enterprise":
        repository_id = settings.corpus_repository_id
    return {
        "document_id": _uuid(document.id),
        "document_version_id": _uuid(version.id),
        "organization_id": _uuid(document.organization_id),
        "workspace_id": _uuid(document.workspace_id),
        "storage_scope": document.storage_scope,
        "owner_user_id": _uuid(document.owner_user_id),
        "department_id": _uuid(document.department_id),
        "folder_id": _uuid(document.folder_id),
        "visibility": document.visibility,
        "lifecycle_status": lifecycle_status,
        "repository_id": repository_id,
        "relative_path": str(document.relative_path).replace("\\", "/").strip("/"),
        "file_name": document.name,
        "file_type": document.file_type,
        "mime_type": document.mime_type,
        "page_count": document.page_count,
        "content_hash": version.content_hash,
        "version_number": version.version_number,
    }


@dataclass(frozen=True)
class MetadataValidation:
    valid: bool
    missing: tuple[str, ...] = ()
    invalid: tuple[str, ...] = ()


def validate_chunk_metadata(metadata: Mapping[str, Any]) -> MetadataValidation:
    """Validate presence separately from model-permitted nullability."""
    required_keys = {
        "document_id", "document_version_id", "workspace_id", "storage_scope",
        "owner_user_id", "department_id", "folder_id", "visibility",
        "lifecycle_status", "repository_id", "relative_path", "file_name",
    }
    missing = sorted(required_keys.difference(metadata))
    invalid: set[str] = set()
    scope = metadata.get("storage_scope")
    non_null = {
        "document_id", "document_version_id", "workspace_id", "storage_scope",
        "department_id", "visibility", "lifecycle_status", "repository_id",
        "relative_path", "file_name",
    }
    for key in non_null:
        if key in metadata and metadata.get(key) in (None, "", "None"):
            invalid.add(key)
    for key in ("document_id", "document_version_id", "workspace_id", "department_id"):
        value = metadata.get(key)
        if value not in (None, "", "None"):
            try: uuid.UUID(str(value))
            except (ValueError, TypeError, AttributeError): invalid.add(key)
    if "storage_scope" in metadata and scope not in {"personal", "enterprise"}:
        invalid.add("storage_scope")
    if scope == "personal":
        if "owner_user_id" not in metadata:
            pass
        elif metadata.get("owner_user_id") in (None, "", "None"):
            invalid.add("owner_user_id")
        else:
            try: uuid.UUID(str(metadata.get("owner_user_id")))
            except (ValueError, TypeError, AttributeError): invalid.add("owner_user_id")
        if metadata.get("visibility") != "private":
            invalid.add("visibility")
    if metadata.get("lifecycle_status") != "indexed":
        invalid.add("lifecycle_status")
    return MetadataValidation(not missing and not invalid, tuple(missing), tuple(sorted(invalid)))
