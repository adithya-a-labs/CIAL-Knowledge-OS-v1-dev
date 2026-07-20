from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_regeneration_uses_persisted_generation_request_without_user_insert():
    source = (ROOT / "backend/app/services/chat_action_service.py").read_text(encoding="utf-8")
    assert 'metadata.get("generation_request")' in source
    assert 'question=user_message.content' in source
    assert 'role="user"' not in source


def test_transform_is_evidence_gated_and_preserves_citations():
    source = (ROOT / "backend/app/services/chat_action_service.py").read_text(encoding="utf-8")
    assert "if not source.sources or not source.citations" in source
    assert "citations=source.citations" in source
    assert 'f"- [ ] {s}"' in source


def test_export_download_rejects_unsafe_filenames():
    source = (ROOT / "backend/app/api/routes/exports.py").read_text(encoding="utf-8")
    service = (ROOT / "backend/app/services/export_service.py").read_text(encoding="utf-8")
    assert "export_id:uuid.UUID" in source
    assert "if self.root not in path.parents" in service
    assert "path.is_symlink()" in service
