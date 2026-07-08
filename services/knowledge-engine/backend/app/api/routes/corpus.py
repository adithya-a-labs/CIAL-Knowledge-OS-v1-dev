"""Corpus API routes backed by PostgreSQL metadata."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, Request, status

from cial_knowledge_os.corpus.service import CorpusServiceUnavailable

router = APIRouter()


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
