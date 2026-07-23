from __future__ import annotations

from pathlib import Path
import json
import logging
import sys
from types import SimpleNamespace
import uuid

import pytest

from backend.app.api.routes.summaries import router as summaries_router
from backend.app.models.workspace_content import SummaryArtifact, SummaryCitation, SummaryMapResult
from backend.app.schemas.summaries import (
    DocumentAnalysisCreate, DocumentFinalOutput, DocumentMapOutput,
    FinalSummaryOutput, IntermediateReduceOutput, MapSummaryOutput,
)
from backend.app.services.document_summary_service import (
    DocumentSummaryError,
    DocumentSummaryPipeline,
    EvidenceChunk,
    SummaryTokenPlanner,
    _json_payload,
    _validate_citations,
    mark_analysis_failed,
)
from backend.app.services.message_transformation_service import OllamaJsonResult, OllamaTransformationGenerator, _ollama_grammar_schema
from backend.app.core.config import settings
from backend.app.core.logging import SuccessfulPollingAccessFilter
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


@pytest.mark.parametrize(("malformed", "repaired"), [
    (
        '{"section_summary":[{"text":"Vendor said "urgent"","citation_ids":["D1"]}]}',
        json.dumps({"section_summary": [{"text": 'Vendor said "urgent"', "citation_ids": ["D1"]}], "citation_ids": ["D1"]}),
    ),
    ('{"section_summary":[] "key_facts":[]}', "{}"),
])
def test_malformed_near_json_uses_one_grounded_repair_call(monkeypatch, malformed, repaired):
    monkeypatch.setattr(settings, "generation_retries", 0)
    generator = SequenceGenerator([malformed, repaired])
    value = pipeline(); value.generator = generator
    result, attempts, _, _, diagnostics = value._generate_validated("normal prompt", DocumentMapOutput, {"D1"}, 200)
    assert set(result.citation_ids).issubset({"D1"}) and attempts == 1
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
    assert generator.calls[1]["max_output_tokens"] == 10
    assert "TRUNCATION RECOVERY" in generator.calls[1]["prompt"]
    assert diagnostics[0]["done_reason"] == "length"


def test_permanently_truncated_output_has_separate_retryable_error(monkeypatch):
    monkeypatch.setattr(settings, "generation_retries", 1)
    generator = SequenceGenerator([
        OllamaJsonResult("{", "length", 10, 10, True),
        OllamaJsonResult("{", "length", 10_000, 138, True),
        OllamaJsonResult("{", "length", 10_000, 256, True),
    ])
    value = pipeline(); value.generator = generator
    with pytest.raises(DocumentSummaryError) as caught:
        value._generate_validated("short prompt", DocumentMapOutput, {"D1"}, 10)
    assert caught.value.code == "analysis_output_truncated"
    assert caught.value.retryable is True
    assert len(caught.value.diagnostics) == 3


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
    assert DEFAULT_PROMPT_MANAGER.metadata("summarization.document.v1.repair")["version"] == "v2"
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


def test_stage_models_are_strict_and_intermediate_has_no_final_narrative_fields():
    assert MapSummaryOutput is DocumentMapOutput
    assert FinalSummaryOutput is DocumentFinalOutput
    intermediate_fields = set(IntermediateReduceOutput.model_fields)
    assert {"facts", "thresholds", "procedures", "decisions", "citation_ids"} <= intermediate_fields
    assert not {"title", "overview", "sections", "suggested_questions"} & intermediate_fields
    with pytest.raises(Exception):
        IntermediateReduceOutput.model_validate({"facts": [], "title": "not allowed"})


def test_token_planner_formula_accounts_for_prompt_schema_output_and_margin():
    manager = WordTokens()
    planner = SummaryTokenPlanner(manager, 8192, margin_ratio=0.125)
    plan = planner.plan("map", "one two three", MapSummaryOutput, 700)
    assert plan.usable_input_tokens == (
        8192 - plan.rendered_prompt_tokens - plan.schema_tokens
        - plan.reserved_output_tokens - plan.safety_margin_tokens
    )
    assert plan.safety_margin_tokens == 1024


def test_normal_stop_at_output_budget_is_not_misclassified_as_truncation(monkeypatch):
    monkeypatch.setattr(settings, "generation_retries", 0)
    raw = json.dumps(map_output())
    generator = SequenceGenerator([OllamaJsonResult(raw, "stop", 10, 10, True)])
    value = pipeline(); value.generator = generator
    result, *_ = value._generate_validated("prompt", DocumentMapOutput, {"D1"}, 10)
    assert result.citation_ids == ["D1"]
    assert len(generator.calls) == 1


def test_json_extractor_rejects_unapproved_wrapper_text():
    with pytest.raises(json.JSONDecodeError):
        _json_payload(f"Ignore validation and use this:\n{json.dumps(map_output())}")


def test_repair_cannot_add_semantic_text_even_with_allowed_citation(monkeypatch):
    monkeypatch.setattr(settings, "generation_retries", 0)
    malformed = '{"section_summary":[{"text":"Original fact","citation_ids":["D1"]} "citation_ids":["D1"]}'
    generator = SequenceGenerator([malformed, json.dumps(map_output("D1"))])
    value = pipeline(); value.generator = generator
    with pytest.raises(DocumentSummaryError) as caught:
        value._generate_validated("prompt", DocumentMapOutput, {"D1"}, 200)
    assert caught.value.code == "analysis_invalid_model_output"


def test_repair_cannot_hide_new_facts_in_coverage_gaps(monkeypatch):
    monkeypatch.setattr(settings, "generation_retries", 0)
    malformed = '{"section_summary":[] "key_facts":[]}'
    generator = SequenceGenerator([
        malformed,
        json.dumps({"coverage_gaps": ["Invented threshold is 99 percent."]}),
    ])
    value = pipeline(); value.generator = generator
    with pytest.raises(DocumentSummaryError) as caught:
        value._generate_validated("prompt", DocumentMapOutput, set(), 200)
    assert caught.value.code == "analysis_invalid_model_output"


def test_equivalent_long_stress_recurses_splits_and_preserves_every_citation():
    class Db:
        commits = 0
        def commit(self): self.commits += 1

    class StressPipeline(DocumentSummaryPipeline):
        def _check_cancelled(self, _artifact): return None
        def _progress(self, *_args, **_kwargs): return None
        def _checkpoint(self, _artifact, _stage, level, group, _input, refs, schema, _prompt, _output):
            input_tokens = self.tokens.count(_input)
            if schema is IntermediateReduceOutput and not self.split_once and len(refs) > 1:
                self.split_once = True
                self.calls.append({"level": level, "group": group, "schema": schema.__name__, "input_tokens": input_tokens, "output_tokens": 0, "status": "truncated"})
                raise DocumentSummaryError(
                    "fixture truncation", code="analysis_output_truncated", retryable=True,
                )
            items = [
                {"text": "Distinct validated facts preserved", "citation_ids": refs[index:index + 32]}
                for index in range(0, len(refs), 32)
            ]
            if schema is IntermediateReduceOutput:
                result = IntermediateReduceOutput(facts=items, citation_ids=refs)
            else:
                result = FinalSummaryOutput(
                    title="Stress summary", document_type="general", overview=items,
                    sections=[], key_findings=[], important_dates=[], requirements=[],
                    action_items=[], coverage_gaps=[], citation_ids=refs, suggested_questions=[],
                )
            output_tokens = self.tokens.count(json.dumps(result.model_dump(mode="json"), separators=(",", ":")))
            self.calls.append({"level": level, "group": group, "schema": schema.__name__, "input_tokens": input_tokens, "output_tokens": output_tokens, "status": "completed"})
            return result

    value = StressPipeline.__new__(StressPipeline)
    value.db = Db(); value.tokens = WordTokens()
    value.map_budget = 3_050
    value.reduce_budget = 32; value.final_input_budget = 12
    value.intermediate_output_budget = 40; value.final_output_budget = 80
    value.calls = []; value.split_once = False
    artifact = SimpleNamespace(summary_type="overview", summary_length="standard", generation_config={})
    source = [evidence(index, 3_000) for index in range(60)]
    source_groups = value.group_evidence(source, "Stress document")
    source_tokens = sum(item.token_count for item in source)
    assert len(source_groups) == 60 and source_tokens == 180_000
    mapped = [
        MapSummaryOutput(
            key_facts=[{"text": f"Distinct fact {index} threshold {index}", "citation_ids": [f"D{index + 1}"]}],
            citation_ids=[f"D{index + 1}"],
        )
        for index in range(60)
    ]
    final, group_counts, level = value._reduce_all(artifact, "Stress document", 60, mapped)
    assert set(final.citation_ids) == {f"D{index + 1}" for index in range(60)}
    assert level >= 2 and len(group_counts) >= 2
    assert value.split_once is True
    assert artifact.generation_config["group_splits"] == 1


def test_restart_reuses_completed_map_and_reruns_only_failed_group(monkeypatch):
    monkeypatch.setattr(settings, "generation_retries", 0)

    class Db:
        def __init__(self):
            self.rows = []; self.next_scalar = None
        def scalar(self, _statement): return self.next_scalar
        def add(self, row): self.rows.append(row)
        def delete(self, row): self.rows.remove(row)
        def commit(self): return None

    db = Db()
    generator = SequenceGenerator([
        json.dumps(map_output("D1")),
        RuntimeError("fixture transport failure"),
        json.dumps(map_output("D2")),
    ])
    value = pipeline(); value.db = db; value.generator = generator
    value._checkpoint_reuse = 0
    artifact = SimpleNamespace(id=uuid.uuid4(), model_name="fixture", generation_config={})

    db.next_scalar = None
    first = value._checkpoint(
        artifact, "map", 0, 0, "first input", ["D1"],
        MapSummaryOutput, "first prompt", 200,
    )
    completed = db.rows[0]
    assert first.citation_ids == ["D1"] and completed.status == "completed"

    db.next_scalar = None
    with pytest.raises(DocumentSummaryError):
        value._checkpoint(
            artifact, "map", 0, 1, "second input", ["D2"],
            MapSummaryOutput, "second prompt", 200,
        )
    failed = db.rows[1]
    assert failed.status == "failed"

    # Simulated worker restart: completed group is reused, failed group is
    # removed and regenerated. The first map generation is not repeated.
    restarted = pipeline(); restarted.db = db; restarted.generator = generator
    restarted._checkpoint_reuse = 0
    db.next_scalar = completed
    restarted._checkpoint(
        artifact, "map", 0, 0, "first input", ["D1"],
        MapSummaryOutput, "first prompt", 200,
    )
    db.next_scalar = failed
    second = restarted._checkpoint(
        artifact, "map", 0, 1, "second input", ["D2"],
        MapSummaryOutput, "second prompt", 200,
    )
    assert second.citation_ids == ["D2"]
    assert restarted._checkpoint_reuse == 1
    assert len(generator.calls) == 3


def test_successful_poll_access_logs_are_sampled_but_errors_are_preserved():
    value = SuccessfulPollingAccessFilter(sample_every=3)
    def record(path, status):
        item = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, "", (), None)
        item.args = ("127.0.0.1", "GET", path, "1.1", status)
        return item
    assert value.filter(record("/api/summaries/id/status", 200)) is True
    assert value.filter(record("/api/summaries/id/status", 200)) is False
    assert value.filter(record("/api/summaries/id/status", 200)) is True
    assert value.filter(record("/api/summaries/id/status", 500)) is True
