from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest

from fastapi import HTTPException

from backend.app.services import document_preview_service
from backend.app.services.document_preview_service import ResolvedDocument, file_response, preview_payload, resolve_document
from backend.app.services.knowledge_engine_service import KnowledgeEngineService


def _pdf_document(path: Path, *, document_id: uuid.UUID | None = None, page_count: int = 3) -> ResolvedDocument:
    document_id = document_id or uuid.uuid4()
    return ResolvedDocument(
        metadata={
            "id": str(document_id),
            "repository_id": "repo-main",
            "name": path.name,
            "relative_path": f"Manuals/{path.name}",
            "extension": ".pdf",
            "mime_type": "application/pdf",
            "file_type": "pdf",
            "page_count": page_count,
            "content_hash": "hash-123",
            "indexing_status": "indexed",
        },
        path=path,
        extension=".pdf",
        content_hash="hash-123",
    )


def _write_pdf(path: Path, pages: int = 3) -> None:
    fitz = pytest.importorskip("fitz")
    document = fitz.open()
    try:
        for page_number in range(1, pages + 1):
            page = document.new_page()
            page.insert_text((72, 72), f"Citation navigation page {page_number}")
        document.save(path)
    finally:
        document.close()


def _chunk(document_id: uuid.UUID, relative_path: str, page: int | None, chunk_id: str) -> dict[str, object]:
    metadata: dict[str, object] = {
        "document_id": str(document_id),
        "repository_id": "repo-main",
        "relative_path": relative_path,
        "file_name": Path(relative_path).name,
        "file_type": "pdf",
        "page_count": 9,
        "chunk_id": chunk_id,
    }
    if page is not None:
        metadata["page_number"] = page
    return {
        "chunk_id": chunk_id,
        "text": f"Evidence from {relative_path} page {page}",
        "score": 0.9,
        "metadata": metadata,
    }


def test_pdf_preview_payload_preserves_first_middle_and_last_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "Airport Manual With Spaces.pdf"
    _write_pdf(pdf_path, pages=3)
    document = _pdf_document(pdf_path, page_count=3)

    first = preview_payload(document, page=1, chunk_id="p1")
    middle = preview_payload(document, page=2, chunk_id="p2")
    last = preview_payload(document, page=3, chunk_id="p3")

    assert first["page"] == 1
    assert middle["page"] == 2
    assert last["page"] == 3
    assert last["viewer_url"].endswith("/file")
    assert last["viewer_format"] == "pdf"
    assert last["viewer_ready"] is True
    assert last["file_url"].endswith("/file")


def test_pdf_file_response_is_inline_application_pdf_for_paths_with_spaces(tmp_path: Path) -> None:
    pdf_path = tmp_path / "Airport Manual With Spaces.pdf"
    _write_pdf(pdf_path, pages=1)
    document = _pdf_document(pdf_path, page_count=1)

    response = file_response(document, disposition="inline")

    assert response.media_type == "application/pdf"
    assert "inline" in response.headers["content-disposition"]
    assert str(pdf_path) not in response.headers["content-disposition"]


def test_pptx_preview_iterates_slides_without_unsupported_collection_slice(
    tmp_path: Path,
) -> None:
    pptx = pytest.importorskip("pptx")
    path = tmp_path / "Release deck with spaces.pptx"
    presentation = pptx.Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "Release readiness"
    slide.placeholders[1].text = "Production Caddy validation"
    presentation.save(path)
    document = ResolvedDocument(
        metadata={
            "id": str(uuid.uuid4()),
            "name": path.name,
            "relative_path": f"Presentations/{path.name}",
            "extension": ".pptx",
            "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "content_hash": "pptx-hash",
            "indexing_status": "indexed",
        },
        path=path,
        extension=".pptx",
        content_hash="pptx-hash",
    )

    payload = preview_payload(document, slide_number=1)

    assert payload["render_kind"] == "slides"
    assert payload["slides"][0]["title"] == "Release readiness"
    assert "Production Caddy validation" in payload["slides"][0]["body"]


@pytest.mark.parametrize(("slide_count", "expected_count"), [(0, 0), (11, 11), (12, 12), (13, 12)])
def test_pptx_preview_bounds_slide_materialization(
    tmp_path: Path,
    slide_count: int,
    expected_count: int,
) -> None:
    pptx = pytest.importorskip("pptx")
    path = tmp_path / f"bounded-{slide_count}.pptx"
    presentation = pptx.Presentation()
    for index in range(slide_count):
        slide = presentation.slides.add_slide(presentation.slide_layouts[5])
        slide.shapes.title.text = f"Slide {index + 1}"
    presentation.save(path)

    slides, preview = document_preview_service._pptx_preview(path)

    assert len(slides) == expected_count
    assert "Slide 13" not in preview


def test_malformed_pptx_preview_fails_safely(tmp_path: Path) -> None:
    path = tmp_path / "malformed.pptx"
    path.write_bytes(b"not an office package")

    assert document_preview_service._pptx_preview(path) == ([], "")


def test_missing_pdf_file_resolution_fails_without_exposing_filesystem_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        document_preview_service,
        "settings",
        SimpleNamespace(corpus_root_path=tmp_path),
    )
    metadata = {
        "id": str(uuid.uuid4()),
        "name": "Missing Manual.pdf",
        "relative_path": "Manuals/Missing Manual.pdf",
        "extension": ".pdf",
        "mime_type": "application/pdf",
        "content_hash": "missing",
    }

    with pytest.raises(HTTPException) as exc_info:
        resolve_document(metadata)

    assert exc_info.value.status_code == 404
    assert str(tmp_path) not in str(exc_info.value.detail)


def test_chat_sources_and_citations_preserve_pdf_navigation_metadata() -> None:
    service = KnowledgeEngineService()
    manual_id = uuid.uuid4()
    handbook_id = uuid.uuid4()
    chunks = [
        _chunk(manual_id, "Manuals/manual.pdf", 1, "manual-p1"),
        _chunk(manual_id, "Manuals/manual.pdf", 5, "manual-p5"),
        _chunk(manual_id, "Manuals/manual.pdf", 9, "manual-p9"),
        _chunk(handbook_id, "Manuals/handbook.pdf", 3, "handbook-p3"),
    ]
    response = {
        "retrieved": chunks,
        "context_stages": {"compressed": chunks},
        "citations": [
            {"reference_id": 1, "source_file": "manual.pdf", "page_number": 1},
            {"reference_id": 2, "source_file": "manual.pdf", "page_number": 5},
            {"reference_id": 3, "source_file": "manual.pdf", "page_number": 9},
            {"reference_id": 4, "source_file": "handbook.pdf", "page_number": 3},
        ],
    }

    sources = service._sources(response)
    citations = service._citations(response)

    assert [source.page for source in sources] == [1, 5, 9, 3]
    assert [citation.page for citation in citations] == [1, 5, 9, 3]
    assert all(source.repository_id == "repo-main" for source in sources)
    assert all(citation.repository_id == "repo-main" for citation in citations)
    assert sources[0].document_id == str(manual_id)
    assert sources[0].chunk_id == "manual-p1"
    assert sources[0].file_url == f"/api/corpus/document/{manual_id}/file"
    assert citations[1].file_url == f"/api/corpus/document/{manual_id}/file"
    assert citations[3].document_id == str(handbook_id)


def test_missing_or_zero_page_metadata_is_not_silently_mapped_to_page_one() -> None:
    service = KnowledgeEngineService()
    document_id = uuid.uuid4()
    chunks = [
        _chunk(document_id, "Manuals/manual.pdf", None, "missing-page"),
        _chunk(document_id, "Manuals/manual.pdf", 0, "zero-page"),
    ]
    response = {
        "retrieved": chunks,
        "context_stages": {"compressed": chunks},
        "citations": [
            {"reference_id": 1, "source_file": "manual.pdf"},
            {"reference_id": 2, "source_file": "manual.pdf", "page_number": 0},
        ],
    }

    sources = service._sources(response)
    citations = service._citations(response)

    assert [source.page for source in sources] == [None, None]
    assert [citation.page for citation in citations] == [None, None]


def test_zero_based_page_index_resolves_to_first_human_facing_page() -> None:
    service = KnowledgeEngineService()
    document_id = uuid.uuid4()
    chunk = _chunk(document_id, "Manuals/manual.pdf", None, "page-index-zero")
    chunk["metadata"]["page_index"] = 0
    response = {
        "retrieved": [chunk],
        "context_stages": {"compressed": [chunk]},
        "citations": [{"reference_id": 1, "source_file": "manual.pdf", "page_index": 0}],
    }

    source = service._sources(response)[0]
    citation = service._citations(response)[0]

    assert source.page == 1
    assert source.page_number == 1
    assert source.page_index == 0
    assert citation.page == 1
    assert citation.page_number == 1
    assert citation.page_index == 0
    assert citation.location_label == "Page 1"


def test_chat_response_metadata_uses_preserved_sources_when_restored() -> None:
    service = KnowledgeEngineService()
    document_id = uuid.uuid4()
    chunks = [_chunk(document_id, "Manuals/restored.pdf", 4, "restored-p4")]
    response = {
        "answer": "Restored answer. [1]",
        "retrieved": chunks,
        "context_stages": {"compressed": chunks},
        "citations": [{"reference_id": 1, "source_file": "restored.pdf", "page_number": 4}],
    }

    chat_response = service._to_chat_response(
        response,
        config=SimpleNamespace(
            answer_detail_level="detailed",
            min_answer_words=250,
            max_answer_words=700,
            evidence_token_budget=12000,
            max_context_tokens=16000,
            retrieval_mode="hybrid",
        ),
        profile="standard",
        selected_scope=SimpleNamespace(
            applied=False,
            selected_document_count=0,
            selected_folder_count=0,
            effective_document_count=0,
            filter_mode=None,
        ),
        include_debug=False,
        include_sources=True,
        latency_ms=10,
        access_context=None,
        allowed_relative_paths=None,
    )

    assert chat_response.citations[0].document_id == str(document_id)
    assert chat_response.citations[0].repository_id == "repo-main"
    assert chat_response.citations[0].page == 4
    assert chat_response.sources[0].file_url == f"/api/corpus/document/{document_id}/file"
