from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from backend.app.services.knowledge_engine_service import (
    KnowledgeEngineInvalidRequest,
    KnowledgeEngineService,
    SelectedContextScope,
)
from cial_knowledge_os.config import Phase4Config
from cial_knowledge_os.phase4_pipeline import Phase4RAGPipeline
from cial_knowledge_os.reranker import MockReranker


class _CharacterTokenizer:
    def encode(self, text: str, **_: Any) -> list[int]:
        return [ord(character) for character in text]

    def decode(self, values: list[int], **_: Any) -> str:
        return "".join(chr(value) for value in values)


class _StaticRetriever:
    def __init__(self, name: str, results: list[dict[str, Any]]) -> None:
        self.name = name
        self.results = results

    def retrieve(self, query: str, *, top_k: int) -> list[dict[str, Any]]:
        return [dict(item) for item in self.results[:top_k]]


class _PromptCapturingLLM:
    def __init__(self) -> None:
        self.prompt = ""

    def invoke(self, prompt: str) -> str:
        self.prompt = prompt
        return "Grounded answer [1]."


def _candidate(
    chunk_id: str,
    text: str,
    *,
    relative_path: str,
    score: float = 0.8,
) -> dict[str, Any]:
    return {
        "id": chunk_id,
        "text": text,
        "score": score,
        "source": Path(relative_path).name,
        "page_number": 1,
        "chunk_id": chunk_id,
        "metadata": {
            "source": f"C:/corpus/{relative_path}",
            "file_name": Path(relative_path).name,
            "relative_path": relative_path,
            "page_number": 1,
            "chunk_id": chunk_id,
            "chunk_index": 1,
        },
    }


def test_operational_profile_preserves_elite_phase45_defaults() -> None:
    service = KnowledgeEngineService()
    config = service.build_config(response_length="operational", profile="operational")

    assert config.answer_detail_level == "detailed"
    assert config.adaptive_answer_sections is True
    assert config.include_decision_notes is True
    assert config.max_answer_words is None


def test_legacy_long_maps_to_detailed_profile() -> None:
    service = KnowledgeEngineService()
    config = service.build_config(response_length="long")

    assert config.answer_detail_level == "detailed"
    assert config.min_answer_words == 350
    assert config.max_answer_words == 2000


def test_request_max_answer_words_overrides_profile_safely() -> None:
    service = KnowledgeEngineService()
    config = service.build_config(
        response_length="operational",
        profile="operational",
        max_answer_words=900,
    )

    assert config.max_answer_words == 900

    with pytest.raises(KnowledgeEngineInvalidRequest):
        service.build_config(
            response_length="operational",
            profile="operational",
            max_answer_words=50,
        )


def test_selected_context_filter_restricts_retrieval_candidates() -> None:
    service = KnowledgeEngineService()
    allowed = _candidate(
        "allowed",
        "Allowed evidence.",
        relative_path="CERT-In/allowed.pdf",
    )
    blocked = _candidate(
        "blocked",
        "Blocked evidence.",
        relative_path="Other/blocked.pdf",
    )

    class FakePipeline:
        def __init__(self) -> None:
            self.config = SimpleNamespace(
                retrieval_top_k=3,
                dense_top_k=3,
                bm25_top_k=3,
                reranker_candidate_top_k=3,
            )
            self.changed = 0
            self.allowed_relative_paths = None

        def _search(self, query: str) -> list[dict[str, Any]]:
            if self.allowed_relative_paths:
                return [
                    item
                    for item in [allowed, blocked]
                    if item["metadata"]["relative_path"] in self.allowed_relative_paths
                ]
            return [allowed, blocked]

        def set_retrieval_relative_paths(self, allowed_relative_paths) -> None:
            self.allowed_relative_paths = allowed_relative_paths

        def on_config_changed(self) -> None:
            self.changed += 1

        def run(self, question: str) -> dict[str, Any]:
            results = self._search(question)
            return {
                "answer": "ok",
                "retrieved": results,
                "context_stages": {"compressed": results},
                "selected_evidence": results,
                "citations": [],
            }

    pipeline = FakePipeline()
    scope = SelectedContextScope(
        applied=True,
        allowed_relative_paths=frozenset({"CERT-In/allowed.pdf"}),
        effective_document_ids=("11111111-1111-4111-8111-111111111111",),
        selected_document_count=1,
        effective_document_count=1,
        filter_mode="hard_relative_path_filter",
    )

    response = service._run_with_selected_context(pipeline, "Question?", scope)

    assert [item["chunk_id"] for item in response["retrieved"]] == ["allowed"]
    assert pipeline.allowed_relative_paths is None
    assert pipeline.config.retrieval_top_k == 3
    assert pipeline.changed == 2
    assert response["selected_context_filter"]["final_retrieved_relative_paths"] == [
        "CERT-In/allowed.pdf"
    ]


def test_selected_context_metadata_is_reflected() -> None:
    service = KnowledgeEngineService()
    config = SimpleNamespace(
        min_answer_words=350,
        max_answer_words=None,
        answer_detail_level="detailed",
        adaptive_answer_sections=True,
        evidence_token_budget=2400,
        max_context_tokens=4096,
    )
    scope = SelectedContextScope(
        applied=True,
        allowed_relative_paths=frozenset({"CERT-In/allowed.pdf"}),
        effective_document_ids=("11111111-1111-4111-8111-111111111111",),
        selected_document_count=1,
        selected_folder_count=1,
        effective_document_count=3,
        filter_mode="hard_relative_path_filter",
    )

    response = service._to_chat_response(
        {
            "answer": "ok",
            "retrieved": [],
            "context_stages": {"compressed": []},
            "selected_evidence": [],
            "citations": [],
        },
        config=config,
        profile="operational",
        selected_scope=scope,
        include_debug=False,
        include_sources=True,
        latency_ms=12,
    )

    assert response.metadata.profile == "operational"
    assert response.metadata.effective_max_answer_words is None
    assert response.metadata.selected_context_applied is True
    assert response.metadata.selected_document_count == 1
    assert response.metadata.selected_folder_count == 1
    assert response.metadata.effective_document_count == 3


def test_selected_context_no_match_does_not_fall_back_to_global_results() -> None:
    service = KnowledgeEngineService()

    class FakePipeline:
        def __init__(self) -> None:
            self.config = SimpleNamespace(
                retrieval_top_k=3,
                dense_top_k=3,
                bm25_top_k=3,
                reranker_candidate_top_k=3,
            )
            self.allowed_relative_paths = None

        def _search(self, query: str) -> list[dict[str, Any]]:
            return []

        def set_retrieval_relative_paths(self, allowed_relative_paths) -> None:
            self.allowed_relative_paths = allowed_relative_paths

        def on_config_changed(self) -> None:
            return None

        def run(self, question: str) -> dict[str, Any]:
            return {
                "answer": "global fallback would be wrong",
                "retrieved": [],
                "context_stages": {"compressed": []},
                "selected_evidence": [],
                "citations": [],
            }

    response = service._run_with_relative_path_filter(
        FakePipeline(),
        "Question?",
        frozenset({"CERT-In/allowed.pdf"}),
        response_key="selected_context_filter",
        filter_payload={
            "applied": True,
            "mode": "hard_relative_path_filter",
            "selected_document_ids": ["11111111-1111-4111-8111-111111111111"],
            "selected_folder_ids": [],
            "effective_document_ids": ["11111111-1111-4111-8111-111111111111"],
            "effective_scope": {
                "document_count": 1,
                "relative_paths": ["CERT-In/allowed.pdf"],
            },
        },
    )

    assert response["answer"] == "No relevant evidence found in the selected context."
    assert response["retrieved"] == []
    assert response["citations"] == []


def test_selected_context_insufficient_evidence_is_normalized_to_no_match() -> None:
    service = KnowledgeEngineService()
    allowed = _candidate(
        "allowed",
        "Weak in-scope evidence.",
        relative_path="CERT-In/allowed.pdf",
    )

    class FakePipeline:
        def __init__(self) -> None:
            self.config = SimpleNamespace(
                retrieval_top_k=3,
                dense_top_k=3,
                bm25_top_k=3,
                reranker_candidate_top_k=3,
            )
            self.allowed_relative_paths = None

        def _search(self, query: str) -> list[dict[str, Any]]:
            return [allowed]

        def set_retrieval_relative_paths(self, allowed_relative_paths) -> None:
            self.allowed_relative_paths = allowed_relative_paths

        def run(self, question: str) -> dict[str, Any]:
            return {
                "answer": "The retrieved documents do not contain sufficient evidence to answer this question.",
                "raw_answer": "The retrieved documents do not contain sufficient evidence to answer this question.",
                "answer_status": "insufficient_evidence",
                "retrieved": [allowed],
                "context_stages": {"compressed": [allowed]},
                "selected_evidence": [allowed],
                "sources": [{"id": "S1"}],
                "citations": [],
            }

    pipeline = FakePipeline()
    response = service._run_with_relative_path_filter(
        pipeline,
        "Question?",
        frozenset({"CERT-In/allowed.pdf"}),
        response_key="selected_context_filter",
        filter_payload={
            "applied": True,
            "mode": "hard_relative_path_filter",
            "selected_document_ids": [],
            "selected_folder_ids": ["folder-1"],
            "effective_document_ids": ["doc-1"],
            "effective_scope": {
                "document_count": 1,
                "relative_paths": ["CERT-In/allowed.pdf"],
            },
        },
    )

    assert response["answer"] == "No relevant evidence found in the selected context."
    assert response["raw_answer"] == "No relevant evidence found in the selected context."
    assert response["sources"] == []
    assert response["retrieved"] == []
    assert response["citations"] == []


def test_citations_fall_back_to_source_page_when_citation_page_is_missing() -> None:
    service = KnowledgeEngineService()

    citations = service._citations(
        {
            "citations": [
                {
                    "reference_id": 1,
                    "source_file": "manual.pdf",
                }
            ],
            "context_stages": {
                "compressed": [
                    {
                        "page_number": 7,
                        "chunk_id": "chunk-1",
                        "text": "Quoted context for the viewer.",
                        "metadata": {
                            "document_id": "11111111-1111-4111-8111-111111111111",
                            "relative_path": "Policies/manual.pdf",
                            "file_name": "manual.pdf",
                            "file_type": "pdf",
                            "page_count": 18,
                        },
                    }
                ]
            },
        }
    )

    assert len(citations) == 1
    assert citations[0].page == 7


def test_golden_phase45_prompt_for_operational_profile(tmp_path: Path) -> None:
    evidence = _candidate(
        "chunk-a",
        "The selected control requires governance review and source verification.",
        relative_path="CERT-In/allowed.pdf",
    )
    llm = _PromptCapturingLLM()
    config = Phase4Config(
        project_root=tmp_path,
        max_query_variants=1,
        max_context_tokens=400,
        evidence_token_budget=180,
        max_answer_words=None,
        min_answer_words=350,
        adaptive_answer_sections=True,
        include_decision_notes=True,
    )
    pipeline = Phase4RAGPipeline(
        config,
        llm=llm,
        tokenizer=_CharacterTokenizer(),
        retrievers={
            "dense": _StaticRetriever("dense", [evidence]),
            "bm25": _StaticRetriever("bm25", [evidence]),
        },
        reranker=MockReranker({"chunk-a": 0.95}),
    )

    pipeline.answer("What should leadership do?")

    assert "You are a strict grounded-answering system" in llm.prompt
    assert "Choose the answer structure that best fits the question" in llm.prompt
    assert "Cite every key factual claim and recommendation" in llm.prompt
    assert "[1]\nDocument:" in llm.prompt
    assert "SELECTED EVIDENCE" in llm.prompt
    assert "Do not exceed" not in llm.prompt


def test_sources_expose_relative_paths_and_deep_link_metadata() -> None:
    service = KnowledgeEngineService()

    sources = service._sources(
        {
            "context_stages": {
                "compressed": [
                    {
                        "page_number": 5,
                        "chunk_id": "chunk-1",
                        "text": "Quoted context for the viewer.",
                        "metadata": {
                            "document_id": "11111111-1111-4111-8111-111111111111",
                            "relative_path": "Policies/manual.pdf",
                            "file_name": "manual.pdf",
                            "file_type": "pdf",
                            "page_count": 18,
                            "source": "C:/absolute/path/manual.pdf",
                        },
                    }
                ]
            }
        }
    )

    assert len(sources) == 1
    assert sources[0].document_id == "11111111-1111-4111-8111-111111111111"
    assert sources[0].relative_path == "Policies/manual.pdf"
    assert sources[0].path == "Policies/manual.pdf"
    assert sources[0].page == 5
    assert sources[0].page_count == 18
    assert sources[0].file_type == "pdf"
    assert sources[0].file_url == "/api/corpus/document/11111111-1111-4111-8111-111111111111/file"
