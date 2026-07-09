"""Safe document file, preview, and thumbnail helpers for Corpus documents."""

from __future__ import annotations

import csv
import json
import mimetypes
import re
import uuid
from dataclasses import dataclass
from html import escape
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from fastapi.responses import FileResponse

from backend.app.core.config import settings


TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm", ".json", ".xml", ".yaml", ".yml"}
TABLE_EXTENSIONS = {".csv", ".xlsx", ".xls"}
OFFICE_EXTENSIONS = {".docx", ".doc", ".pptx", ".ppt"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | TABLE_EXTENSIONS | OFFICE_EXTENSIONS | IMAGE_EXTENSIONS | {".pdf"}
MAX_TEXT_PREVIEW_BYTES = 256 * 1024
MAX_PREVIEW_CHARS = 24_000
THUMBNAIL_SIZE = (360, 240)


@dataclass(frozen=True)
class ResolvedDocument:
    metadata: dict[str, Any]
    path: Path
    extension: str
    content_hash: str


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip(".-")
    return cleaned or "document"


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _cache_dir(name: str) -> Path:
    directory = settings.outputs_path / name
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _cache_key(document: ResolvedDocument, page: int | None = None) -> str:
    page_part = f"-p{max(page or 1, 1)}" if page is not None else ""
    return f"{document.metadata['id']}-{_safe_name(document.content_hash)}{page_part}"


def _preview_cache_path(document: ResolvedDocument, page: int | None, chunk_id: str | None) -> Path:
    chunk_part = f"-c{_safe_name(chunk_id)}" if chunk_id else ""
    return _cache_dir("previews") / f"{_cache_key(document, page)}{chunk_part}.json"


def _media_type(path: Path, fallback: str | None = None) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return fallback or guessed or "application/octet-stream"


def _read_text_head(path: Path, max_bytes: int = MAX_TEXT_PREVIEW_BYTES) -> str:
    with path.open("rb") as handle:
        data = handle.read(max_bytes + 1)
    suffix = "\n\n[Preview truncated.]" if len(data) > max_bytes else ""
    if len(data) > max_bytes:
        data = data[:max_bytes]
    return data.decode("utf-8", errors="replace")[:MAX_PREVIEW_CHARS] + suffix


def _csv_rows(path: Path, max_rows: int = 12, max_cols: int = 6) -> list[list[str]]:
    text = _read_text_head(path, 96 * 1024)
    reader = csv.reader(StringIO(text))
    rows: list[list[str]] = []
    for row in reader:
        rows.append([cell.strip()[:80] for cell in row[:max_cols]])
        if len(rows) >= max_rows:
            break
    return rows


def _xlsx_rows(path: Path, max_rows: int = 12, max_cols: int = 6) -> tuple[list[list[str]], int]:
    try:
        from openpyxl import load_workbook
    except Exception:
        return [], 0
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        worksheet = workbook.worksheets[0]
        rows: list[list[str]] = []
        for row in worksheet.iter_rows(max_row=max_rows, max_col=max_cols, values_only=True):
            rows.append(["" if cell is None else str(cell)[:80] for cell in row])
        return rows, len(workbook.worksheets)
    finally:
        workbook.close()


def _docx_text(path: Path) -> str:
    try:
        from docx import Document
    except Exception:
        return ""
    try:
        document = Document(path)
    except Exception:
        return ""
    lines: list[str] = []
    total = 0
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        lines.append(text)
        total += len(text)
        if total >= MAX_PREVIEW_CHARS:
            lines.append("[Preview truncated.]")
            break
    return "\n\n".join(lines)


def _pdf_page_count(path: Path) -> int | None:
    try:
        import fitz
    except Exception:
        return None
    try:
        with fitz.open(path) as document:
            return int(document.page_count)
    except Exception:
        return None


def _render_pdf_thumbnail(path: Path, output_path: Path, page: int) -> bool:
    try:
        import fitz
    except Exception:
        return False
    try:
        with fitz.open(path) as document:
            index = min(max(page, 1), document.page_count) - 1
            pixmap = document.load_page(index).get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False)
            pixmap.save(output_path)
        return True
    except Exception:
        return False


def _draw_card(output_path: Path, title: str, subtitle: str, detail: str = "", rows: list[list[str]] | None = None) -> None:
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", THUMBNAIL_SIZE, "#f8faf7")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    strong = ImageFont.load_default()
    draw.rounded_rectangle((1, 1, THUMBNAIL_SIZE[0] - 2, THUMBNAIL_SIZE[1] - 2), radius=16, outline="#dbe5d8", width=2, fill="#ffffff")
    draw.rounded_rectangle((18, 18, 78, 78), radius=12, fill="#edf6e9")
    draw.text((34, 39), (subtitle[:4] or "FILE").upper(), fill="#25611f", font=strong)
    draw.text((96, 23), title[:38], fill="#0f172a", font=strong)
    draw.text((96, 45), subtitle[:42], fill="#64748b", font=font)
    if detail:
        draw.text((96, 64), detail[:42], fill="#2f6d25", font=font)

    if rows:
        x0, y0 = 18, 96
        col_width = 52
        row_height = 18
        for row_index, row in enumerate(rows[:6]):
            for col_index, cell in enumerate(row[:6]):
                x = x0 + col_index * col_width
                y = y0 + row_index * row_height
                fill = "#f8fafc" if row_index == 0 else "#ffffff"
                draw.rectangle((x, y, x + col_width, y + row_height), outline="#e2e8f0", fill=fill)
                draw.text((x + 3, y + 4), str(cell)[:8], fill="#334155", font=font)
    else:
        wrapped = [title[i : i + 42] for i in range(0, min(len(title), 126), 42)]
        for index, line in enumerate(wrapped[:4]):
            draw.text((18, 102 + index * 20), line, fill="#334155", font=font)

    image.save(output_path, format="PNG")


def _render_image_thumbnail(path: Path, output_path: Path) -> bool:
    try:
        from PIL import Image, ImageOps
    except Exception:
        return False
    try:
        with Image.open(path) as image:
            image.seek(0)
            image = ImageOps.exif_transpose(image.convert("RGB"))
            image.thumbnail(THUMBNAIL_SIZE)
            canvas = Image.new("RGB", THUMBNAIL_SIZE, "#f8faf7")
            x = (THUMBNAIL_SIZE[0] - image.width) // 2
            y = (THUMBNAIL_SIZE[1] - image.height) // 2
            canvas.paste(image, (x, y))
            canvas.save(output_path, format="PNG")
        return True
    except Exception:
        return False


def resolve_document(metadata: dict[str, Any]) -> ResolvedDocument:
    relative_path = str(metadata.get("relative_path") or "").replace("\\", "/").strip("/")
    candidate = Path(relative_path)
    if not relative_path or candidate.is_absolute() or ".." in candidate.parts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document path metadata.")

    root = settings.data_files_path.resolve()
    path = (root / candidate).resolve()
    if not _is_within(path, root) or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file not found.")

    extension = str(metadata.get("extension") or path.suffix).casefold()
    content_hash = str(metadata.get("content_hash") or f"{path.stat().st_mtime_ns}-{path.stat().st_size}")
    return ResolvedDocument(metadata=metadata, path=path, extension=extension, content_hash=content_hash)


def file_response(
    document: ResolvedDocument,
    *,
    disposition: str = "inline",
) -> FileResponse:
    return FileResponse(
        document.path,
        media_type=_media_type(document.path, document.metadata.get("mime_type")),
        filename=document.metadata.get("name") or document.path.name,
        content_disposition_type=disposition,
    )


def thumbnail_response(document: ResolvedDocument, page: int | None = None) -> FileResponse:
    page_number = max(page or 1, 1)
    output_path = _cache_dir("thumbnails") / f"{_cache_key(document, page_number)}.png"
    if not output_path.is_file():
        rendered = False
        if document.extension == ".pdf":
            rendered = _render_pdf_thumbnail(document.path, output_path, page_number)
        elif document.extension in IMAGE_EXTENSIONS:
            rendered = _render_image_thumbnail(document.path, output_path)

        if not rendered:
            rows: list[list[str]] | None = None
            if document.extension == ".csv":
                rows = _csv_rows(document.path)
            elif document.extension in {".xlsx", ".xls"}:
                rows, _ = _xlsx_rows(document.path)
            try:
                _draw_card(
                    output_path,
                    str(document.metadata.get("name") or document.path.name),
                    document.extension.replace(".", "") or "document",
                    str(document.metadata.get("indexing_status") or "pending"),
                    rows=rows,
                )
            except Exception:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Thumbnail generation failed.")
    return FileResponse(output_path, media_type="image/png")


def _preview_content(document: ResolvedDocument) -> dict[str, Any]:
    preview_text = ""
    rows: list[list[str]] = []
    extraction_method = "metadata"
    render_kind = "card"
    extra: dict[str, Any] = {}

    if document.extension in TEXT_EXTENSIONS:
        preview_text = _read_text_head(document.path)
        extraction_method = "text_head"
        render_kind = "code" if document.extension in {".json", ".xml", ".yaml", ".yml"} else "text"
        if document.extension == ".json":
            try:
                preview_text = json.dumps(json.loads(preview_text), indent=2, ensure_ascii=False)[:MAX_PREVIEW_CHARS]
            except Exception:
                pass
    elif document.extension == ".csv":
        rows = _csv_rows(document.path)
        preview_text = "\n".join([", ".join(row) for row in rows])
        extraction_method = "csv_head"
        render_kind = "table"
    elif document.extension in {".xlsx", ".xls"}:
        rows, sheet_count = _xlsx_rows(document.path)
        preview_text = "\n".join(["\t".join(row) for row in rows])
        extraction_method = "spreadsheet_head" if rows else "metadata"
        render_kind = "table" if rows else "card"
        extra["sheet_count"] = sheet_count
    elif document.extension == ".docx":
        preview_text = _docx_text(document.path)
        extraction_method = "docx_text" if preview_text else "metadata"
        render_kind = "text" if preview_text else "card"
    elif document.extension == ".pdf":
        render_kind = "pdf"
        extraction_method = "file_stream"
        extra["page_count"] = document.metadata.get("page_count") or _pdf_page_count(document.path)
    elif document.extension in IMAGE_EXTENSIONS:
        render_kind = "image"
        extraction_method = "file_stream"
    elif document.extension in OFFICE_EXTENSIONS:
        render_kind = "office_card"

    return {
        "preview_text": preview_text,
        "table_rows": rows,
        "render_kind": render_kind,
        "extraction_method": extraction_method,
        **extra,
    }


def preview_payload(document: ResolvedDocument, *, page: int | None = None, chunk_id: str | None = None) -> dict[str, Any]:
    cache_path = _preview_cache_path(document, page, chunk_id)
    cached: dict[str, Any] | None = None
    if cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cached = None
    if cached is None:
        cached = _preview_content(document)
        try:
            cache_path.write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass

    preview_text = str(cached.get("preview_text") or "")
    rows = cached.get("table_rows") if isinstance(cached.get("table_rows"), list) else []
    if chunk_id and preview_text:
        highlight_text = preview_text[:1000]
    elif preview_text:
        highlight_text = preview_text[:1000]
    else:
        highlight_text = f"{document.metadata.get('name') or document.path.name} is available as a corpus file. Inline extracted text is not available for this format."

    file_id = str(document.metadata["id"])
    return {
        **document.metadata,
        "preview_text": preview_text,
        "highlight_text": escape(highlight_text),
        "page": page,
        "chunk_id": chunk_id,
        "open_url": f"/api/corpus/document/{file_id}/view",
        "download_url": f"/api/corpus/document/{file_id}/download",
        "file_url": f"/api/corpus/document/{file_id}/view",
        "thumbnail_url": f"/api/corpus/document/{file_id}/thumbnail?page={max(page or 1, 1)}",
        "read_error": None,
        "render_kind": cached.get("render_kind") or "card",
        "extraction_method": cached.get("extraction_method") or "metadata",
        "table_rows": rows,
        "supported_preview": document.extension in SUPPORTED_EXTENSIONS,
        **{key: value for key, value in cached.items() if key not in {"preview_text", "table_rows", "render_kind", "extraction_method"}},
    }


def parse_document_id(document_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document id.") from exc
