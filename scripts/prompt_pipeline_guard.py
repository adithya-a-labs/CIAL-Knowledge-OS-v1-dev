"""Print the active Phase 4.5 prompt/generation profile.

This guard is intentionally read-only: it does not start Qdrant, load embedding
models, load the reranker, or call Ollama. Use it before manual QA to confirm
that the elite Phase 4.5 prompt path and answer-depth settings are active.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "services" / "knowledge-engine"
ENGINE_SRC = BACKEND_ROOT / "src"

for path in (BACKEND_ROOT, ENGINE_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _active_prompt_names(config: Any) -> dict[str, str]:
    if not getattr(config, "prefer_structured_answers", True):
        section_prompt = "generation.narrative_sections"
        content_prompt = "generation.narrative_content_requirements"
    elif getattr(config, "adaptive_answer_sections", False):
        section_prompt = "generation.adaptive_sections"
        content_prompt = "generation.adaptive_content_requirements"
    else:
        section_prompt = "generation.structured_sections"
        content_prompt = "generation.structured_content_requirements"

    return {
        "active_system_prompt_name": "generation.phase4_system",
        "active_generation_prompt_name": "generation.phase4_system",
        "active_section_prompt_name": section_prompt,
        "active_content_prompt_name": content_prompt,
        "citation_context_template_name": "templates.context_template",
        "citation_appendix_template_name": "templates.answer_template",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print the effective Phase 4.5 prompt pipeline profile."
    )
    parser.add_argument(
        "--response-length",
        choices=("short", "medium", "long", "quick", "standard", "detailed", "operational", "elite"),
        default=None,
        help="Backend chat response_length/profile value to inspect.",
    )
    parser.add_argument(
        "--profile",
        choices=("quick", "standard", "detailed", "operational", "elite"),
        default="operational",
        help="Explicit chat profile to inspect.",
    )
    parser.add_argument(
        "--max-answer-words",
        type=int,
        default=None,
        help="Optional request-level max_answer_words override.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    from backend.app.services.knowledge_engine_service import KnowledgeEngineService
    from cial_knowledge_os.prompts import DEFAULT_PROMPT_MANAGER

    service = KnowledgeEngineService()
    if not service.engine_available:
        raise SystemExit(service._engine_error_message())

    response_length = args.response_length or args.profile
    config = service.build_config(
        response_length=response_length,
        profile=args.profile,
        max_answer_words=args.max_answer_words,
    )
    prompt_names = _active_prompt_names(config)
    registry = DEFAULT_PROMPT_MANAGER.registry()

    rows: list[tuple[str, Any]] = [
        ("response_length_profile", response_length),
        ("explicit_profile", args.profile),
        ("answer_mode", getattr(config, "answer_detail_level", "")),
        ("max_answer_words", getattr(config, "max_answer_words", None)),
        ("min_answer_words", getattr(config, "min_answer_words", None)),
        ("adaptive_sections_status", getattr(config, "adaptive_answer_sections", None)),
        ("prefer_structured_answers", getattr(config, "prefer_structured_answers", None)),
        ("include_decision_notes", getattr(config, "include_decision_notes", None)),
        ("citation_mode", "inline_reference_ids_plus_references_appendix"),
        ("retrieval_context_count", getattr(config, "max_selected_evidence", None)),
        ("min_retrieval_context_count", getattr(config, "min_selected_evidence", None)),
        ("evidence_token_budget", getattr(config, "evidence_token_budget", None)),
        ("selected_evidence_target_min_tokens", getattr(config, "selected_evidence_target_min_tokens", None)),
        ("selected_evidence_target_max_tokens", getattr(config, "selected_evidence_target_max_tokens", None)),
        ("model_name", getattr(config, "ollama_model_name", "")),
        ("temperature", 0),
        ("top_p", "unset"),
        ("max_tokens", "unset"),
        ("context_max_tokens", getattr(config, "max_context_tokens", None)),
        ("generation_retries", getattr(config, "generation_retries", None)),
    ]

    for key, value in prompt_names.items():
        metadata = registry.get(value, {})
        rows.append((key, value))
        rows.append((f"{key}_version", metadata.get("version", "unknown")))

    width = max(len(key) for key, _ in rows)
    for key, value in rows:
        print(f"{key.ljust(width)} : {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
