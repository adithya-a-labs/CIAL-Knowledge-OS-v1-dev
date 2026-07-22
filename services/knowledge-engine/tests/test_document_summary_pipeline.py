from __future__ import annotations

from pathlib import Path
import json
import sys
from types import SimpleNamespace
import uuid

import pytest

from backend.app.api.routes.summaries import router as summaries_router
from backend.app.models.workspace_content import SummaryArtifact, SummaryCitation, SummaryMapResult
from backend.app.schemas.summaries import DocumentAnalysisCreate, DocumentFinalOutput, DocumentMapOutput
from backend.app.services.document_summary_service import (
    DocumentSummaryError,
    DocumentSummaryPipeline,
    EvidenceChunk,
    _json_payload,
    _validate_citations,
    mark_analysis_failed,
)
from backend.app.services.message_transformation_service import OllamaJsonResult, OllamaTransformationGenerator, _ollama_grammar_schema
from backend.app.core.config import settings
from cial_knowledge_os.prompts.manager import DEFAULT_PROMPT_MANAGER


class WordTokens:
    encoding_name = "test_words"

    def __init__(self):
        self.tokenizer = self

    def token_ids(self, text):
        return text.split()

    def count(self, text):
        return len(text.split())

    def decode(self, values, **_):
        return " ".join(values)


def evidence(index: int, words: int = 4) -> EvidenceChunk:
    return EvidenceChunk(
        reference_id=f"D{index + 1}", row_id=uuid.uuid4(), chunk_id=f"chunk-{index}",
        chunk_index=index, page=index + 1, section=f"Section {index + 1}",
        text=" ".join(f"word{value}" for value in range(words)), token_count=words,
    )


def pipeline(map_budget: int = 30) -> DocumentSummaryPipeline:
    value = DocumentSummaryPipeline.__new__(DocumentSummaryPipeline)
    value.db = None; value.generator = None; value.tokens = WordTokens(); value.map_budget = map_budget; value.reduce_budget = 50
    return value


def map_output(citation_id: str = "D1") -> dict:
    return {
        "section_summary": [{"text": "Grounded statement", "citation_ids": [citation_id]}],
        "key_facts": [], "dates": [], "obligations": [], "exceptions": [], "risks": [],
        "actions": [], "definitions": [], "coverage_gaps": [], "citation_ids": [citation_id],
    }


class SequenceGenerator:
    def __init__(self, values):
        self.values = list(values)
        self.calls = []

    def generate_json(self, prompt, *, max_output_tokens, json_schema=None):
        self.calls.append({"prompt": prompt, "max_output_tokens": max_output_tokens, "json_schema": json_schema})
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def test_all_chunks_are_grouped_once_in_deterministic_contiguous_order():
    items = [evidence(index) for index in range(8)]
    groups = pipeline(34).group_evidence(items, "Approved document")
    flattened = [chunk.reference_id for group in groups for chunk in group.chunks]
    assert flattened == [item.reference_id for item in items]
    assert all(group.token_count <= 34 for group in groups)
    assert [group.index for group in groups] == list(range(len(groups)))


def test_oversized_chunk_splits_without_losing_original_reference():
    groups = pipeline(24).group_evidence([evidence(0, 80)], "Approved document")
    segments = [chunk for group in groups for chunk in group.chunks]
    assert len(segments) > 1
    assert {item.reference_id for item in segments} == {"D1"}
    assert [item.segment_index for item in segments] == list(range(1, len(segments) + 1))
    assert all(item.segment_count == len(segments) for item in segments)


def test_length_configuration_never_changes_source_group_coverage():
    items = [evidence(index, 7) for index in range(12)]
    coverage = []
    for length in ("brief", "standard", "detailed"):
        DocumentAnalysisCreate(summary_type="overview", length=length)
        coverage.append([chunk.reference_id for group in pipeline(36).group_evidence(items, "Document") for chunk in group.chunks])
    assert coverage[0] == coverage[1] == coverage[2]


def test_unknown_original_chunk_citation_is_rejected():
    output = DocumentMapOutput.model_validate({
        "section_summary": [{"text": "Grounded", "citation_ids": ["D99"]}],
        "key_facts": [], "dates": [], "obligations": [], "exceptions": [], "risks": [],
        "actions": [], "definitions": [], "coverage_gaps": [], "citation_ids": ["D99"],
    })
    with pytest.raises(ValueError, match="unknown source chunk"):
        _validate_citations(output, {"D1"})


@pytest.mark.parametrize("raw", [
    json.dumps(map_output()),
    f"```json\n{json.dumps(map_output())}\n```",
    f"Here is the object:\n{json.dumps(map_output())}\nEnd of response.",
])
def test_json_object_extractor_accepts_valid_fenced_and_surrounded_json(raw):
    assert _json_payload(raw)["citation_ids"] == ["D1"]


@pytest.mark.parametrize("raw", ["not json", "[1,2,3]", '{"broken": }'])
def test_json_object_extractor_rejects_non_object_or_genuinely_malformed_json(raw):
    with pytest.raises((json.JSONDecodeError, ValueError)):
        _json_payload(raw)


@pytest.mark.parametrize("malformed", [
    '{"section_summary":[{"text":"Vendor said "urgent"","citation_ids":["D1"]}]}',
    '{"section_summary":[] "key_facts":[]}',
])
def test_malformed_near_json_uses_one_grounded_repair_call(monkeypatch, malformed):
    monkeypatch.setattr(settings, "generation_retries", 0)
    generator = SequenceGenerator([malformed, json.dumps(map_output())])
    value = pipeline(); value.generator = generator
    result, attempts, _, _, diagnostics = value._generate_validated("normal prompt", DocumentMapOutput, {"D1"}, 200)
    assert result.citation_ids == ["D1"] and attempts == 1
    assert len(generator.calls) == 2
    assert "Preserve only information already present" in generator.calls[1]["prompt"]
    assert diagnostics[0]["repair_attempted"] is True
    assert diagnostics[0]["json_error_line"] == 1
    assert diagnostics[1]["phase"] == "repair"


def test_repair_hallucinated_citation_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "generation_retries", 0)
    generator = SequenceGenerator(['{"section_summary": [}', json.dumps(map_output("D99"))])
    value = pipeline(); value.generator = generator
    with pytest.raises(DocumentSummaryError) as caught:
        value._generate_validated("normal prompt", DocumentMapOutput, {"D1"}, 200)
    assert caught.value.code == "analysis_invalid_model_output"
    assert caught.value.retryable is True
    assert len(generator.calls) == 2


def test_failed_repair_returns_to_bounded_normal_regeneration(monkeypatch):
    monkeypatch.setattr(settings, "generation_retries", 1)
    generator = SequenceGenerator([
        '{"section_summary": [}',
        json.dumps(map_output("D99")),
        json.dumps(map_output("D1")),
    ])
    value = pipeline(); value.generator = generator
    result, attempts, _, _, _ = value._generate_validated("normal prompt", DocumentMapOutput, {"D1"}, 200)
    assert result.citation_ids == ["D1"] and attempts == 2
    assert len(generator.calls) == 3


def test_truncated_output_retries_with_increased_bounded_budget(monkeypatch):
    monkeypatch.setattr(settings, "generation_retries", 1)
    generator = SequenceGenerator([
        OllamaJsonResult('{"section_summary": [', "length", 10, 10, True),
        OllamaJsonResult(json.dumps(map_output()), "stop", 8, 138, True),
    ])
    value = pipeline(); value.generator = generator
    result, attempts, _, _, diagnostics = value._generate_validated("short prompt", DocumentMapOutput, {"D1"}, 10)
    assert result.citation_ids == ["D1"] and attempts == 2
    assert generator.calls[0]["max_output_tokens"] == 10
    assert 10 < generator.calls[1]["max_output_tokens"] <= settings.summary_context_window_tokens
    assert diagnostics[0]["finish_reason"] == "length"


def test_permanently_truncated_output_has_separate_retryable_error(monkeypatch):
    monkeypatch.setattr(settings, "generation_retries", 1)
    generator = SequenceGenerator([
        OllamaJsonResult("{", "length", 10, 10, True),
        OllamaJsonResult("{", "length", 10_000, 138, True),
    ])
    value = pipeline(); value.generator = generator
    with pytest.raises(DocumentSummaryError) as caught:
        value._generate_validated("short prompt", DocumentMapOutput, {"D1"}, 10)
    assert caught.value.code == "analysis_output_truncated"
    assert caught.value.retryable is True
    assert len(caught.value.diagnostics) == 2


def test_schema_mode_falls_back_to_json_only_when_grammar_is_unavailable(monkeypatch):
    class GrammarUnavailable(Exception):
        status_code = 400
    formats = []
    def generate(**kwargs):
        formats.append(kwargs["format"])
        if len(formats) == 1:
            raise GrammarUnavailable("failed to parse grammar schema format")
        return SimpleNamespace(response=json.dumps(map_output()), done_reason="stop", eval_count=12)
    monkeypatch.setitem(sys.modules, "ollama", SimpleNamespace(generate=generate))
    monkeypatch.setattr(settings, "generation_retries", 0)
    adapter = OllamaTransformationGenerator("fixture-model")
    result = adapter.generate_json("prompt", max_output_tokens=77, json_schema=DocumentMapOutput.model_json_schema())
    assert isinstance(formats[0], dict) and formats[1] == "json"
    assert result.schema_mode is False and result.max_output_tokens == 77


def test_permanent_invalid_output_failure_persists_safe_retryable_diagnostics():
    artifact = SimpleNamespace(
        status="running", error_code=None, error_message_safe=None, generation_config={},
        completed_at=None, progress=None, map_group_count=2,
    )
    class FakeDb:
        committed = False
        def get(self, _model, _id): return artifact
        def commit(self): self.committed = True
    db = FakeDb()
    error = DocumentSummaryError(
        "Local model output failed grounded schema validation.", code="analysis_invalid_model_output",
        retryable=True, diagnostics=[{"schema_name": "DocumentMapOutput", "response_character_count": 42}],
    )
    mark_analysis_failed(db, uuid.uuid4(), error)
    assert artifact.status == "failed" and artifact.error_code == "analysis_invalid_model_output"
    assert artifact.generation_config["error_retryable"] is True
    assert artifact.progress["retryable"] is True
    assert "malformed" not in str(artifact.generation_config).casefold()
    assert db.committed is True


def test_ollama_schema_is_structural_inline_and_pydantic_remains_validator():
    schema = _ollama_grammar_schema(DocumentMapOutput.model_json_schema())
    rendered = str(schema)
    assert "$defs" not in rendered and "$ref" not in rendered
    assert "maxItems" not in rendered and "title" not in rendered
    assert schema["properties"]["key_facts"]["items"]["properties"]["citation_ids"]["items"] == {"type": "string"}


@pytest.mark.parametrize("document_type", ["general", "calendar", "policy", "standard", "contract", "report"])
def test_evaluation_document_families_accept_empty_actions_without_invention(document_type):
    output = DocumentFinalOutput.model_validate({
        "title": f"{document_type} fixture", "document_type": document_type,
        "sections": [], "key_findings": [], "important_dates": [], "requirements": [],
        "action_items": [], "coverage_gaps": [], "citation_ids": [], "suggested_questions": [],
    })
    assert output.action_items == []


def test_document_prompts_are_registered_json_only_and_phase4_is_untouched():
    map_prompt = DEFAULT_PROMPT_MANAGER.render(
        "summarization.document.v1.map", document_label="Calendar", summary_type="overview",
        summary_length="brief", evidence_blocks="[D1] approved text",
    )
    reduce_prompt = DEFAULT_PROMPT_MANAGER.render(
        "summarization.document.v1.reduce", document_label="Calendar", summary_type="overview",
        summary_length="brief", output_kind="final synthesis", allowed_reference_ids="D1",
        partial_summaries='[{"citation_ids":["D1"]}]',
    )
    assert "untrusted content" in map_prompt
    assert "Return valid JSON only" in map_prompt
    assert "Do not rank sections by query relevance" in reduce_prompt
    assert DEFAULT_PROMPT_MANAGER.metadata("summarization.document.v1.repair")["version"] == "v1"
    assert DEFAULT_PROMPT_MANAGER.metadata("generation.phase4_system")["version"] == "phase4"


def test_models_and_migration_define_identity_progress_checkpoints_and_original_version_citations():
    assert "document_version_id" in SummaryArtifact.__table__.c
    assert "reuse_key" in SummaryArtifact.__table__.c
    assert "progress" in SummaryArtifact.__table__.c
    assert "document_version_id" in SummaryCitation.__table__.c
    assert "ordering" in SummaryCitation.__table__.c
    assert SummaryMapResult.__table__.c.structured_output.nullable is False
    migration = (Path(__file__).parents[1] / "alembic/versions/20260722_0014_document_analysis.py").read_text(encoding="utf-8")
    assert 'down_revision = "20260722_0013"' in migration
    assert "uq_summary_artifacts_active_document_analysis" in migration
    assert "summary_map_results" in migration


def test_routes_expose_document_analysis_status_and_safe_cancellation():
    paths = {(route.path, next(iter(route.methods))) for route in summaries_router.routes if route.methods}
    route_paths = {path for path, _ in paths}
    assert "/documents/{document_id}/analysis" in route_paths
    assert "/summaries/{summary_id}/status" in route_paths
    assert "/summaries/{summary_id}/cancel" in route_paths
    assert "/summaries/config" in route_paths


def test_pipeline_has_no_retriever_reranker_or_vector_search_dependency():
    source = (Path(__file__).parents[1] / "backend/app/services/document_summary_service.py").read_text(encoding="utf-8")
    assert "KnowledgeEngineService" not in source
    assert "qdrant" not in source.casefold()
    assert "rerank" not in source.casefold()
    assert ".search(" not in source


def test_summary_follow_up_persists_visible_context_snapshot_and_version_binding():
    source = (Path(__file__).parents[1] / "backend/app/services/summary_service.py").read_text(encoding="utf-8")
    assert "context_snapshot=context_snapshot" in source
    assert "document_version_id" in source
    assert 'mode="original_versions"' in source
