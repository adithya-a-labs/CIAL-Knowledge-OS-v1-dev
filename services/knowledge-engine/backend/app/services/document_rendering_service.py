"""Rendering helpers for previewable and converted document assets."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Protocol

from fastapi import HTTPException, status
from fastapi.responses import FileResponse

from backend.app.core.config import settings


LEGACY_CONVERSION_TARGETS = {
    ".doc": "pdf",
    ".ppt": "pdf",
}


class RenderingDocument(Protocol):
    metadata: dict[str, Any]
    path: Path
    extension: str
    content_hash: str


def _rendered_dir() -> Path:
    directory = settings.outputs_path / "rendered"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _safe_name(value: str) -> str:
    cleaned = "".join(character if character.isalnum() or character in "._-" else "-" for character in value).strip(".-")
    return cleaned or "document"


def _cache_key(document: RenderingDocument, page: int | None = None) -> str:
    page_part = f"-p{max(page or 1, 1)}" if page is not None else ""
    return f"{document.metadata['id']}-{_safe_name(document.content_hash)}{page_part}"


def _soffice_binary() -> str | None:
    for candidate in ("soffice", "libreoffice"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def _converted_path(document: RenderingDocument, output_format: str) -> Path:
    extension = output_format.lower().lstrip(".")
    directory = _rendered_dir() / _cache_key(document)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{document.path.stem}.{extension}"


def _ensure_converted(document: RenderingDocument, output_format: str) -> Path | None:
    soffice = _soffice_binary()
    if not soffice:
        return None

    output_path = _converted_path(document, output_format)
    if output_path.is_file():
        return output_path

    command = [
        soffice,
        "--headless",
        "--convert-to",
        output_format,
        "--outdir",
        str(output_path.parent),
        str(document.path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0 or not output_path.is_file():
        return None
    return output_path


def rendered_preview_path(document: RenderingDocument, output_format: str) -> Path | None:
    return _ensure_converted(document, output_format)


def viewer_asset_payload(document: RenderingDocument) -> dict[str, Any]:
    document_id = str(document.metadata["id"])
    payload: dict[str, Any] = {
        "viewer_url": f"/api/corpus/document/{document_id}/file",
        "viewer_format": document.extension.replace(".", "") or "file",
        "viewer_ready": True,
        "preview_notice": None,
    }

    target_format = LEGACY_CONVERSION_TARGETS.get(document.extension)
    if not target_format:
        return payload

    converted = _ensure_converted(document, target_format)
    if converted is None:
        return {
            **payload,
            "viewer_ready": False,
            "preview_notice": "Native preview is limited for this legacy Office format. Open or download the original file for the exact layout.",
        }

    return {
        **payload,
        "viewer_url": f"/api/corpus/document/{document_id}/rendered?format={target_format}",
        "viewer_format": target_format,
        "viewer_ready": True,
        "preview_notice": "Showing a cached converted preview for this legacy Office file.",
    }


def rendered_response(document: RenderingDocument, output_format: str) -> FileResponse:
    converted = _ensure_converted(document, output_format)
    if converted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rendered preview is not available for this document.",
        )
    return FileResponse(
        converted,
        media_type="application/pdf" if output_format == "pdf" else None,
        filename=converted.name,
        content_disposition_type="inline",
    )
