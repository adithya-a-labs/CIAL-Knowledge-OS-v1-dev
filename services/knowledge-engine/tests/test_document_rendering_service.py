from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from backend.app.services import document_rendering_service


def _document(extension: str):
    return SimpleNamespace(
        metadata={"id": "11111111-1111-4111-8111-111111111111"},
        path=Path(f"sample{extension}"),
        extension=extension,
        content_hash="hash-123",
    )


def test_pdf_viewer_payload_uses_native_file_route() -> None:
    payload = document_rendering_service.viewer_asset_payload(_document(".pdf"))

    assert payload["viewer_ready"] is True
    assert payload["viewer_format"] == "pdf"
    assert payload["viewer_url"] == "/api/corpus/document/11111111-1111-4111-8111-111111111111/file"


def test_legacy_doc_payload_falls_back_when_conversion_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(document_rendering_service, "_soffice_binary", lambda: None)

    payload = document_rendering_service.viewer_asset_payload(_document(".doc"))

    assert payload["viewer_ready"] is False
    assert payload["viewer_format"] == "doc"
    assert "Native preview is limited" in str(payload["preview_notice"])
