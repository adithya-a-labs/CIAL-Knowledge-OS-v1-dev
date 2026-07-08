"""Corpus API routes backed by PostgreSQL metadata."""

from __future__ import annotations

import uuid
from html import escape
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request, status

from backend.app.core.config import settings
from cial_knowledge_os.corpus.service import CorpusServiceUnavailable

router = APIRouter()
TEXT_PREVIEW_EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm", ".json", ".xml", ".yaml", ".yml", ".csv"}


@router.post("/corpus/sync")
def corpus_sync(request: Request) -> dict[str, object]:
    try:
        return request.app.state.corpus_service.sync().to_dict()
    except CorpusServiceUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/corpus/tree")
def corpus_tree(request: Request) -> dict[str, object]:
    try:
        return request.app.state.corpus_service.get_tree()
    except CorpusServiceUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/corpus/folder")
def corpus_folder(
    request: Request,
    path: str = Query(default="", description="Corpus-relative folder path."),
) -> dict[str, object]:
    try:
        payload = request.app.state.corpus_service.get_folder(path)
    except CorpusServiceUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corpus folder not found.")
    return payload


@router.get("/corpus/document/{document_id}/preview")
def corpus_document_preview(
    document_id: str,
    request: Request,
    chunk_id: str | None = Query(default=None),
    page: int | None = Query(default=None),
) -> dict[str, object]:
    try:
        parsed_document_id = uuid.UUID(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document id.") from exc
    try:
        document = request.app.state.corpus_service.get_document(parsed_document_id)
    except CorpusServiceUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corpus document not found.")

    relative_path = str(document.get("relative_path") or "").replace("\\", "/").strip("/")
    document_path = (settings.data_files_path / relative_path).resolve()
    root = settings.data_files_path.resolve()
    preview_text = ""
    read_error = None
    if root in document_path.parents or document_path == root:
        extension = str(document.get("extension") or Path(relative_path).suffix).casefold()
        if extension in TEXT_PREVIEW_EXTENSIONS and document_path.is_file():
            try:
                preview_text = document_path.read_text(encoding="utf-8", errors="replace")[:12000]
            except OSError as exc:
                read_error = str(exc)
    else:
        read_error = "Document path is outside the configured corpus root."

    highlight_text = preview_text[:1000] if preview_text else ""
    if not highlight_text and document.get("name"):
        highlight_text = f"{document['name']} is indexed as corpus metadata. Text preview is not available for this file type yet."

    return {
        **document,
        "preview_text": preview_text,
        "highlight_text": escape(highlight_text),
        "page": page,
        "chunk_id": chunk_id,
        "open_url": None,
        "download_url": None,
        "read_error": read_error,
    }


@router.get("/corpus/document/{document_id}")
def corpus_document(document_id: str, request: Request) -> dict[str, object]:
    try:
        parsed_document_id = uuid.UUID(document_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document id.") from exc
    try:
        payload = request.app.state.corpus_service.get_document(parsed_document_id)
    except CorpusServiceUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corpus document not found.")
    return payload
