"""Rendering helpers for previewable and converted document assets."""

from __future__ import annotations

import shutil
import subprocess
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, Protocol

from fastapi import HTTPException, status
from fastapi.responses import FileResponse

from backend.app.core.config import settings


INLINE_CONVERSION_TARGETS = {
    ".doc": "pdf",
    ".docx": "pdf",
    ".ppt": "pdf",
    ".pptx": "pdf",
    ".xls": "pdf",
    ".xlsx": "pdf",
    ".tif": "png",
    ".tiff": "png",
}
DIRECT_VIEWER_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
    ".gif",
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".yaml",
    ".yml",
    ".csv",
}
_SUPPORTED_RENDER_TARGETS = frozenset({"pdf", "png", "jpg", "jpeg", "webp"})
_conversion_locks: dict[str, threading.Lock] = {}
_conversion_locks_guard = threading.Lock()


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
    if extension not in _SUPPORTED_RENDER_TARGETS:
        raise ValueError("Unsupported render target.")
    directory = _rendered_dir() / _cache_key(document)
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{document.path.stem}.{extension}"


def _ensure_converted(document: RenderingDocument, output_format: str) -> Path | None:
    normalized_target = output_format.casefold().lstrip(".")
    expected_target = INLINE_CONVERSION_TARGETS.get(document.extension.casefold())
    if normalized_target not in _SUPPORTED_RENDER_TARGETS or normalized_target != expected_target:
        return None
    image_converted = _ensure_image_converted(document, output_format)
    if image_converted is not None:
        return image_converted

    soffice = _soffice_binary()
    if not soffice:
        return None

    output_path = _converted_path(document, output_format)
    if output_path.is_file():
        return output_path

    lock_key = str(output_path)
    with _conversion_locks_guard:
        lock = _conversion_locks.setdefault(lock_key, threading.Lock())
    with lock:
        if output_path.is_file():
            return output_path
        with tempfile.TemporaryDirectory(prefix="cial-render-") as temporary_directory:
            temporary_root = Path(temporary_directory)
            profile_uri = (temporary_root / "profile").resolve().as_uri()
            command = [
                soffice,
                "--headless",
                f"-env:UserInstallation={profile_uri}",
                "--convert-to",
                normalized_target,
                "--outdir",
                str(temporary_root),
                str(document.path),
            ]
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=temporary_root,
                )
            except (OSError, subprocess.TimeoutExpired):
                return None
            staged = temporary_root / f"{document.path.stem}.{normalized_target}"
            if completed.returncode != 0 or not staged.is_file() or staged.stat().st_size <= 0:
                return None
            os.replace(staged, output_path)
            return output_path


def _ensure_image_converted(document: RenderingDocument, output_format: str) -> Path | None:
    extension = document.extension.casefold()
    target = output_format.lower().lstrip(".")
    if extension not in {".tif", ".tiff"} or target not in {"png", "jpg", "jpeg", "webp"}:
        return None

    output_path = _converted_path(document, target)
    if output_path.is_file():
        return output_path

    try:
        from PIL import Image, ImageOps
    except Exception:
        return None

    try:
        with Image.open(document.path) as image:
            image.seek(0)
            converted = ImageOps.exif_transpose(image.convert("RGB"))
            save_format = "JPEG" if target in {"jpg", "jpeg"} else target.upper()
            temporary = output_path.with_suffix(f"{output_path.suffix}.tmp")
            converted.save(temporary, format=save_format)
            os.replace(temporary, output_path)
    except Exception:
        return None

    return output_path if output_path.is_file() else None


def rendered_preview_path(document: RenderingDocument, output_format: str) -> Path | None:
    return _ensure_converted(document, output_format)


def viewer_asset_payload(document: RenderingDocument) -> dict[str, Any]:
    document_id = str(document.metadata["id"])
    extension = document.extension.casefold()
    payload: dict[str, Any] = {
        "viewer_url": f"/api/corpus/document/{document_id}/file",
        "viewer_format": extension.replace(".", "") or "file",
        "viewer_ready": extension in DIRECT_VIEWER_EXTENSIONS,
        "preview_notice": None,
    }

    target_format = INLINE_CONVERSION_TARGETS.get(extension)
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
        "preview_notice": "Showing a cached converted preview for this document.",
    }


def rendered_response(document: RenderingDocument, output_format: str) -> FileResponse:
    normalized = output_format.casefold().lstrip(".")
    if normalized != INLINE_CONVERSION_TARGETS.get(document.extension.casefold()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported render target for this document type.")
    converted = _ensure_converted(document, output_format)
    if converted is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rendered preview is not available for this document.",
        )
    return FileResponse(
        converted,
        media_type=_rendered_media_type(output_format),
        filename=converted.name,
        content_disposition_type="inline",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'; frame-ancestors 'self'; sandbox",
        },
    )


def _rendered_media_type(output_format: str) -> str | None:
    normalized = output_format.lower().lstrip(".")
    if normalized == "pdf":
        return "application/pdf"
    if normalized == "png":
        return "image/png"
    if normalized in {"jpg", "jpeg"}:
        return "image/jpeg"
    if normalized == "webp":
        return "image/webp"
    return None
