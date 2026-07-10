"""Corpus API routes backed by PostgreSQL metadata."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request, status

from backend.app.security.access import can_sync_corpus, resolve_access_context
from backend.app.services.document_preview_service import (
    file_response,
    parse_document_id,
    preview_payload,
    resolve_document,
    thumbnail_response,
    view_response,
)
from backend.app.services.document_rendering_service import rendered_response
from cial_knowledge_os.corpus.service import CorpusServiceUnavailable

router = APIRouter()


@router.post("/corpus/sync")
def corpus_sync(request: Request) -> dict[str, object]:
    access_context = resolve_access_context(request)
    if not can_sync_corpus(access_context):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to synchronize corpus metadata.",
        )
    try:
        return request.app.state.corpus_service.sync().to_dict()
    except CorpusServiceUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/corpus/tree")
def corpus_tree(request: Request) -> dict[str, object]:
    access_context = resolve_access_context(request)
    try:
        return request.app.state.corpus_service.get_tree(access_context=access_context)
    except CorpusServiceUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/corpus/folder")
def corpus_folder(
    request: Request,
    path: str = Query(default="", description="Corpus-relative folder path."),
) -> dict[str, object]:
    access_context = resolve_access_context(request)
    try:
        payload = request.app.state.corpus_service.get_folder(path, access_context=access_context)
    except CorpusServiceUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corpus folder not found.")
    return payload


def _get_corpus_document_or_404(document_id: str, request: Request) -> dict[str, object]:
    parsed_document_id = parse_document_id(document_id)
    access_context = resolve_access_context(request)
    try:
        document = request.app.state.corpus_service.get_document(
            parsed_document_id,
            access_context=access_context,
        )
    except CorpusServiceUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Corpus document not found.")
    return document


@router.get("/corpus/document/{document_id}/file")
def corpus_document_file(document_id: str, request: Request):
    document = _get_corpus_document_or_404(document_id, request)
    return file_response(resolve_document(document), disposition="inline")


@router.get("/corpus/document/{document_id}/view")
def corpus_document_view(document_id: str, request: Request):
    document = _get_corpus_document_or_404(document_id, request)
    return view_response(resolve_document(document))


@router.get("/corpus/document/{document_id}/download")
def corpus_document_download(document_id: str, request: Request):
    document = _get_corpus_document_or_404(document_id, request)
    return file_response(resolve_document(document), disposition="attachment")


@router.get("/corpus/document/{document_id}/rendered")
def corpus_document_rendered(
    document_id: str,
    request: Request,
    format: str = Query(default="pdf"),
):
    document = _get_corpus_document_or_404(document_id, request)
    return rendered_response(resolve_document(document), format)


@router.get("/corpus/document/{document_id}/thumbnail")
def corpus_document_thumbnail(
    document_id: str,
    request: Request,
    page: int | None = Query(default=1, ge=1),
):
    document = _get_corpus_document_or_404(document_id, request)
    return thumbnail_response(resolve_document(document), page=page)


@router.get("/corpus/document/{document_id}/preview")
def corpus_document_preview(
    document_id: str,
    request: Request,
    chunk_id: str | None = Query(default=None),
    page: int | None = Query(default=None, ge=1),
    sheet_name: str | None = Query(default=None),
    sheet_index: int | None = Query(default=None, ge=1),
    slide_number: int | None = Query(default=None, ge=1),
) -> dict[str, object]:
    document = _get_corpus_document_or_404(document_id, request)
    return preview_payload(
        resolve_document(document),
        page=page,
        chunk_id=chunk_id,
        sheet_name=sheet_name,
        sheet_index=sheet_index,
        slide_number=slide_number,
    )


@router.get("/corpus/document/{document_id}")
def corpus_document(document_id: str, request: Request) -> dict[str, object]:
    return _get_corpus_document_or_404(document_id, request)
