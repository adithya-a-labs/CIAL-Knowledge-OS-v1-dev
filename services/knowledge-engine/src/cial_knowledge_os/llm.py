"""Grounded generation through a local Ollama runtime."""

from __future__ import annotations

from typing import Any, Protocol

from httpx import HTTPError
from langchain_ollama import OllamaLLM
from ollama import ResponseError, list as list_ollama_models

from .config import KnowledgeOSConfig
from .prompts import DEFAULT_PROMPT_MANAGER

PHASE1_NO_EVIDENCE_RESPONSE = DEFAULT_PROMPT_MANAGER.get(
    "evaluation.phase1_no_evidence"
).text


class GenerationFailedError(RuntimeError):
    """Report an exhausted Phase 4 generation attempt without losing its cause.

    Inputs are the original exception and total attempt count. The raised error
    exposes the original type/message for batch row metadata and chains the
    source exception for full logs. Earlier phases do not use this exception;
    it is raised only by the Phase 4 retry boundary.
    """

    def __init__(self, original: Exception, *, attempts: int) -> None:
        self.original_error_type = type(original).__name__
        self.original_error_message = str(original)
        self.attempts = attempts
        super().__init__(
            f"{self.original_error_type}: {self.original_error_message} "
            f"(generation attempts: {attempts})"
        )


class LocalLLM(Protocol):
    """Minimal interface implemented by supported local inference adapters."""

    def invoke(self, prompt: str) -> Any: ...


def create_local_llm(config: KnowledgeOSConfig) -> OllamaLLM:
    """Validate and create a deterministic local Ollama model interface."""

    try:
        available_models = {
            model.model
            for model in list_ollama_models().models
            if model.model is not None
        }
    except (HTTPError, OSError, ResponseError) as exc:
        raise RuntimeError(
            "The local Ollama service is unavailable. Start Ollama and confirm "
            f"that the configured model '{config.ollama_model_name}' is installed."
        ) from exc

    if config.ollama_model_name not in available_models:
        raise RuntimeError(
            f"Configured Ollama model '{config.ollama_model_name}' is not installed "
            "locally. Install or transfer that model, or change "
            "KnowledgeOSConfig.ollama_model_name. No model was downloaded."
        )

    return OllamaLLM(model=config.ollama_model_name, temperature=0)


def build_grounded_prompt(
    question: str,
    context: str,
    *,
    no_evidence_response: str = PHASE1_NO_EVIDENCE_RESPONSE,
) -> str:
    """Build a strict grounded prompt that requires direct evidence."""

    return DEFAULT_PROMPT_MANAGER.render(
        "generation.grounded_qa",
        no_evidence_response=no_evidence_response,
        context=context,
        question=question,
    )


def generate_answer(
    llm: LocalLLM,
    question: str,
    context: str,
    *,
    no_evidence_response: str = PHASE1_NO_EVIDENCE_RESPONSE,
) -> str:
    """Generate a grounded answer using the configured local runtime."""

    if not context.strip():
        return no_evidence_response
    prompt = build_grounded_prompt(
        question,
        context,
        no_evidence_response=no_evidence_response,
    )
    return str(llm.invoke(prompt)).strip()
