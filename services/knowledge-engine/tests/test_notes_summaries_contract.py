from pathlib import Path

from backend.app.models.workspace_content import Note, NoteIndexState, NoteVersion, SavedKnowledgeItem, SummaryArtifact, SummaryCitation, SummaryConversationBinding, SummarySource
from backend.app.schemas.notes import NoteUpdate
from backend.app.schemas.summaries import SummaryCreate
from backend.app.services.note_service import _plain
from cial_knowledge_os.prompts.manager import DEFAULT_PROMPT_MANAGER


def test_note_models_preserve_private_revision_contract():
    assert Note.__table__.c.owner_user_id.nullable is False
    assert Note.__table__.c.workspace_id.nullable is False
    assert Note.__table__.c.deleted_at.nullable is True
    assert any(constraint.name == "ck_notes_revision" for constraint in Note.__table__.constraints)
    assert any(constraint.name == "uq_note_versions_note_revision" for constraint in NoteVersion.__table__.constraints)


def test_note_update_requires_expected_revision_and_plain_text_is_sanitized():
    payload = NoteUpdate(expected_revision=4, content_markdown="## Safe **text** <script>bad</script>")
    assert payload.expected_revision == 4
    assert "<" not in _plain(payload.content_markdown or "")


def test_summary_models_are_immutable_artifact_provenance_records():
    assert SummaryArtifact.__table__.c.owner_user_id.nullable is False
    assert SummarySource.__table__.c.source_snapshot.nullable is False
    assert any(constraint.name == "uq_summary_citations_id" for constraint in SummaryCitation.__table__.constraints)
    assert "content_markdown" not in SummarySource.__table__.c


def test_summary_prompts_are_registered_and_strictly_renderable():
    section = DEFAULT_PROMPT_MANAGER.render("summaries.section_v1", summary_type="executive", summary_length="brief", custom_instructions="None", source_material="[1] approved")
    merge = DEFAULT_PROMPT_MANAGER.render("summaries.merge_v1", summary_type="executive", multi_document_mode="compare", summary_length="brief", custom_instructions="None", source_summaries="[1] approved")
    assert "[1] approved" in section
    assert "Mode is compare" in merge


def test_summary_request_rejects_empty_sources():
    try:
        SummaryCreate(sources=[])
    except ValueError:
        pass
    else:
        raise AssertionError("empty source selection was accepted")


def test_migration_is_additive_and_declares_search_index():
    migration = (Path(__file__).parents[1] / "alembic/versions/20260721_0011_notes_summaries.py").read_text(encoding="utf-8")
    assert 'down_revision = "20260720_0010"' in migration
    assert "CREATE INDEX ix_notes_search" in migration
    assert "drop_column" not in migration


def test_completion_migration_adds_private_index_saved_and_follow_up_contracts():
    migration = (Path(__file__).parents[1] / "alembic/versions/20260721_0012_note_index_saved_bindings.py").read_text(encoding="utf-8")
    assert 'down_revision="20260721_0011"' in migration
    assert NoteIndexState.__table__.c.note_id.primary_key
    assert SavedKnowledgeItem.__table__.c.owner_user_id.nullable is False
    assert any(value.name == "uq_saved_knowledge_owner_summary" for value in SavedKnowledgeItem.__table__.constraints)
    assert SummaryConversationBinding.__table__.c.source_binding.nullable is False
    assert "drop_column" not in migration


def test_summary_sources_accept_folders_and_private_pasted_text():
    folder = SummaryCreate(sources=[{"source_type": "folder", "source_id": "7b5e42a3-513f-4fb2-890d-906f9715fbc8"}])
    pasted = SummaryCreate(sources=[{"source_type": "pasted_text", "title": "Incident notes", "content": "Approved private text"}])
    assert folder.sources[0].source_type == "folder"
    assert pasted.sources[0].source_id is None
    assert pasted.sources[0].content == "Approved private text"
