from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest

from backend.app.models.conversations import ChatMessage
from backend.app.services.message_transformation_service import (
    MessageTransformationError,
    MessageTransformationService,
)
from backend.app.services.knowledge_engine_service import KnowledgeEngineService


EVIDENCE = [{
    "reference_id": 1, "document_id": "doc-1", "document_version_id": "v1",
    "chunk_id": "chunk-1", "page": 7, "source_name": "Manual.pdf",
    "relative_path": "ops/Manual.pdf", "text": "The operator must inspect the light before reopening.",
    "score": 0.91,
}]


class DB:
    def __init__(self): self.commits = 0; self.rollbacks = 0
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1
    def refresh(self, item): item.id = item.id or uuid.uuid4(); item.created_at = datetime.now(timezone.utc)


class Repo:
    def __init__(self, source): self.source = source; self.added = []
    def get_message_for_user(self, message_id, user_id): return self.source
    def add_message(self, item): self.added.append(item); return item


class Generator:
    def __init__(self, result): self.result = result; self.prompts = []
    def generate(self, prompt): self.prompts.append(prompt); return self.result


class FailingGenerator(Generator):
    def generate(self, prompt): self.prompts.append(prompt); raise RuntimeError("ollama down")


def service(source, result="Inspect the light before reopening. [1]"):
    db, generator = DB(), Generator(result)
    value = MessageTransformationService(db, generator)  # type: ignore[arg-type]
    value.repository = Repo(source)  # type: ignore[assignment]
    return value, db, generator


def assistant(metadata=None):
    return ChatMessage(id=uuid.uuid4(), session_id=uuid.uuid4(), user_id=uuid.uuid4(), role="assistant",
                       content="The operator must inspect the light before reopening. [1]",
                       citations=[{"id": "S1", "document_id": "doc-1", "page": 7, "chunk_id": "chunk-1"}],
                       sources=[{"id": "S1", "document_id": "doc-1", "page": 7, "chunk_id": "chunk-1"}],
                       metadata_=metadata if metadata is not None else {"evidence_snapshot": EVIDENCE})


def access(user_id): return SimpleNamespace(principal=SimpleNamespace(user_id=user_id))


def test_uses_exact_snapshot_and_appends_linked_message_without_retrieval():
    source = assistant(); value, db, generator = service(source)
    result = value.explain_simpler(source.id, access(source.user_id))
    assert "chunk-1" in generator.prompts[0] and EVIDENCE[0]["text"] in generator.prompts[0]
    assert "dense" not in value.__dict__ and "pipeline" not in value.__dict__ and "retriever" not in value.__dict__
    assert result.session_id == source.session_id and result.metadata_["source_message_id"] == str(source.id)
    assert result.metadata_["transformation"] == "explain_simpler"
    assert result.turn_sequence > 0 and result.role_sequence == 1
    assert source.content.startswith("The operator") and db.commits == 1


@pytest.mark.parametrize("output,code", [("Invented [2]", "invalid_citation_ids"), ("No citation", "missing_required_citations"), ("", "empty_transformed_response")])
def test_rejects_invalid_output_without_persistence(output, code):
    source = assistant(); value, db, _ = service(source, output)
    with pytest.raises(MessageTransformationError) as error: value.explain_simpler(source.id, access(source.user_id))
    assert error.value.code == code and db.commits == 0


def test_legacy_message_has_controlled_error_and_no_generator_call():
    source = assistant({}); value, db, generator = service(source)
    with pytest.raises(MessageTransformationError) as error: value.explain_simpler(source.id, access(source.user_id))
    assert error.value.code == "missing_persisted_evidence"
    assert generator.prompts == [] and db.commits == 0


def test_prompt_builder_contains_only_supplied_evidence():
    prompt = MessageTransformationService.build_prompt("Original [1]", EVIDENCE)
    assert "chunk-1" in prompt and "Manual.pdf" in prompt and EVIDENCE[0]["text"] in prompt
    assert "chunk-2" not in prompt


def test_cross_user_or_missing_message_is_not_found_without_generation():
    source = assistant(); value, db, generator = service(source)
    value.repository = Repo(None)  # the ownership-filtered repository returns no row
    with pytest.raises(MessageTransformationError) as error: value.explain_simpler(source.id, access(uuid.uuid4()))
    assert error.value.code == "message_not_found" and generator.prompts == [] and db.commits == 0


@pytest.mark.parametrize("role,content,code", [("user", "question", "invalid_source_role"), ("assistant", "   ", "empty_source_response")])
def test_invalid_source_message_is_rejected(role, content, code):
    source = assistant(); source.role = role; source.content = content
    value, db, generator = service(source)
    with pytest.raises(MessageTransformationError) as error: value.explain_simpler(source.id, access(source.user_id))
    assert error.value.code == code and generator.prompts == [] and db.commits == 0


def test_ollama_failure_does_not_stage_or_persist_a_message():
    source = assistant(); value, db, _ = service(source)
    generator = FailingGenerator(""); value.generator = generator
    with pytest.raises(MessageTransformationError) as error: value.explain_simpler(source.id, access(source.user_id))
    assert error.value.code == "generation_failure" and value.repository.added == [] and db.commits == 0


def test_persistence_failure_rolls_back():
    class FailingDB(DB):
        def commit(self): raise RuntimeError("database unavailable")
    source = assistant(); db, generator = FailingDB(), Generator("Simple [1]")
    value = MessageTransformationService(db, generator)  # type: ignore[arg-type]
    value.repository = Repo(source)  # type: ignore[assignment]
    with pytest.raises(MessageTransformationError) as error: value.explain_simpler(source.id, access(source.user_id))
    assert error.value.code == "persistence_failure" and db.rollbacks == 1


def test_normal_chat_snapshot_freezes_exact_selected_evidence_text():
    chunks = [{"chunk_id": "stable-1", "text": "Exact prompt evidence.", "metadata": {"document_id": "doc", "page_number": 4}}]
    snapshot = KnowledgeEngineService._evidence_snapshot(chunks)
    assert snapshot == [{"reference_id": 1, "document_id": "doc", "document_version_id": None,
                         "chunk_id": "stable-1", "page": 4, "source_name": None,
                         "relative_path": None, "text": "Exact prompt evidence.", "score": None,
                         "provenance": None}]
