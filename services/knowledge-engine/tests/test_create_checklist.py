from __future__ import annotations

import json
import uuid

import pytest

from backend.app.services.message_transformation_service import (
    ChecklistItem, ChecklistNote, ChecklistResult, MessageTransformationError,
    MessageTransformationService,
)
from test_explain_simpler import DB, EVIDENCE, Generator, Repo, access, assistant


VALID = {
    "items": [
        {"action": "Inspect the light before reopening.", "citation_ids": [1, 1], "phase": "immediate", "condition": "Before reopening."},
        {"action": "Record the inspection result.", "citation_ids": [1], "phase": "validation", "condition": None},
    ],
    "evidence_gaps": [{"text": "The evidence does not name an owner.", "citation_ids": [1]}],
    "caveats": [{"text": "Reopening depends on inspection.", "citation_ids": [1]}],
}


def checklist_service(output):
    source = assistant(); db, generator = DB(), Generator(output)
    value = MessageTransformationService(db, generator)  # type: ignore[arg-type]
    value.repository = Repo(source)  # type: ignore[assignment]
    return source, value, db, generator


def test_valid_checklist_uses_exact_evidence_and_appends_same_session():
    source, value, db, generator = checklist_service(json.dumps(VALID))
    result = value.create_checklist(source.id, access(source.user_id))
    assert EVIDENCE[0]["text"] in generator.prompts[0] and "chunk-1" in generator.prompts[0]
    assert "pipeline" not in value.__dict__ and "retriever" not in value.__dict__ and "qdrant" not in value.__dict__
    assert result.session_id == source.session_id and result.metadata_["source_message_id"] == str(source.id)
    assert result.metadata_["transformation"] == "create_checklist"
    assert result.metadata_["label"] == "Action checklist"
    assert result.metadata_["evidence_snapshot"] == EVIDENCE
    assert result.citations == source.citations and result.sources == source.sources
    assert result.turn_sequence > 0 and result.role_sequence == 1
    assert source.content.startswith("The operator") and db.commits == 1


def test_markdown_rendering_is_deterministic_and_orders_phases_notes_and_conditions():
    result = ChecklistResult.model_validate(VALID)
    rendered = MessageTransformationService.render_checklist(result)
    assert rendered.startswith("## Action Checklist")
    assert rendered.index("### Immediate") < rendered.index("### Validation") < rendered.index("### Evidence gaps") < rendered.index("### Caveats")
    assert "- [ ] Inspect the light before reopening. [1]" in rendered
    assert "  - Condition: Before reopening. [1]" in rendered
    assert "- The evidence does not name an owner. [1]" in rendered


def test_unphased_items_render_before_phase_sections():
    result = ChecklistResult(items=[ChecklistItem(action="Act", citation_ids=[1]), ChecklistItem(action="Validate", citation_ids=[1], phase="validation")], evidence_gaps=[], caveats=[])
    rendered = MessageTransformationService.render_checklist(result)
    assert rendered.index("- [ ] Act [1]") < rendered.index("### Validation")


@pytest.mark.parametrize("payload", [
    {**VALID, "owner": "ops"},
    {**VALID, "items": [{"action": "Act", "citation_ids": [1], "phase": "urgent", "condition": None}]},
    {**VALID, "items": [{"action": "", "citation_ids": [1], "phase": None, "condition": None}]},
    {**VALID, "items": [{"action": "Act", "citation_ids": [], "phase": None, "condition": None}]},
])
def test_strict_schema_rejects_unknown_phase_empty_action_and_no_citation(payload):
    _, value, db, _ = checklist_service(json.dumps(payload))
    with pytest.raises(MessageTransformationError) as error: value.create_checklist(value.repository.source.id, access(value.repository.source.user_id))
    assert error.value.code == "invalid_checklist_output" and db.commits == 0


def test_invented_citation_is_rejected():
    payload = {**VALID, "items": [{"action": "Act", "citation_ids": [2], "phase": None, "condition": None}]}
    source, value, db, _ = checklist_service(json.dumps(payload))
    with pytest.raises(MessageTransformationError) as error: value.create_checklist(source.id, access(source.user_id))
    assert error.value.code == "invalid_citation" and db.commits == 0


def test_empty_items_returns_no_supported_actions():
    source, value, db, _ = checklist_service(json.dumps({"items": [], "evidence_gaps": [], "caveats": []}))
    with pytest.raises(MessageTransformationError) as error: value.create_checklist(source.id, access(source.user_id))
    assert error.value.code == "no_supported_actions" and db.commits == 0


def test_exact_duplicates_are_removed_and_citations_deduplicated():
    payload = {"items": [VALID["items"][0], VALID["items"][0]], "evidence_gaps": [], "caveats": []}
    result = MessageTransformationService._validate_checklist(ChecklistResult.model_validate(payload), {1})
    assert len(result.items) == 1 and result.items[0].citation_ids == [1]


def test_single_json_fence_is_accepted_but_malformed_json_is_rejected():
    parsed = MessageTransformationService._parse_checklist(f"```json\n{json.dumps(VALID)}\n```")
    assert len(parsed.items) == 2
    with pytest.raises(MessageTransformationError) as error: MessageTransformationService._parse_checklist("not json")
    assert error.value.code == "invalid_checklist_output"


def test_prompt_matches_required_core_and_contains_no_unrelated_chunk():
    prompt = MessageTransformationService.build_checklist_prompt("Answer [1]", EVIDENCE)
    assert prompt.startswith("Convert the ORIGINAL ANSWER into an actionable checklist using only the supplied SELECTED EVIDENCE.")
    assert "1. Include only actions explicitly supported by the evidence." in prompt
    assert "10. Return valid JSON matching the required schema." in prompt
    assert EVIDENCE[0]["text"] in prompt and "chunk-1" in prompt and "chunk-2" not in prompt


def test_legacy_missing_evidence_and_invalid_role_never_generate():
    for source, code in ((assistant({}), "missing_persisted_evidence"), (assistant(), "invalid_source_role")):
        if code == "invalid_source_role": source.role = "user"
        db, generator = DB(), Generator(json.dumps(VALID)); value = MessageTransformationService(db, generator)  # type: ignore[arg-type]
        value.repository = Repo(source)  # type: ignore[assignment]
        with pytest.raises(MessageTransformationError) as error: value.create_checklist(source.id, access(source.user_id))
        assert error.value.code == code and generator.prompts == []


def test_cross_user_filtered_lookup_returns_not_found_without_generation():
    source, value, db, generator = checklist_service(json.dumps(VALID))
    value.repository = Repo(None)  # ownership-filtered repository hides another user's row
    with pytest.raises(MessageTransformationError) as error: value.create_checklist(source.id, access(uuid.uuid4()))
    assert error.value.code == "message_not_found" and generator.prompts == [] and db.commits == 0


def test_generation_failure_leaves_original_and_database_unchanged():
    class Failure(Generator):
        def generate(self, prompt): self.prompts.append(prompt); raise RuntimeError("ollama failure")
    source = assistant(); db, generator = DB(), Failure(""); value = MessageTransformationService(db, generator)  # type: ignore[arg-type]
    value.repository = Repo(source)  # type: ignore[assignment]
    with pytest.raises(MessageTransformationError) as error: value.create_checklist(source.id, access(source.user_id))
    assert error.value.code == "generation_failed" and value.repository.added == [] and db.commits == 0
    assert source.content.startswith("The operator")


def test_checklist_persistence_failure_rolls_back_atomically():
    class FailingDB(DB):
        def commit(self): raise RuntimeError("database unavailable")
    source = assistant(); db, generator = FailingDB(), Generator(json.dumps(VALID)); value = MessageTransformationService(db, generator)  # type: ignore[arg-type]
    value.repository = Repo(source)  # type: ignore[assignment]
    with pytest.raises(MessageTransformationError) as error: value.create_checklist(source.id, access(source.user_id))
    assert error.value.code == "persistence_failed" and db.rollbacks == 1
