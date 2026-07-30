"""Evidence-snapshot-only assistant message transformations.

This module intentionally has no dependency on the Phase 4 pipeline, Qdrant,
retrievers, rerankers, corpus services, or evidence selectors.
"""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
from dataclasses import dataclass
import re
import time
import uuid
from typing import Any, Callable, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.conversations import ChatMessage
from backend.app.repositories.chats import ChatRepository
from backend.app.security.access import RequestAccessContext


def _ollama_grammar_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Inline Pydantic refs and retain the JSON-Schema grammar Ollama consumes.

    Older local Ollama builds reject annotation/validation keywords such as
    ``title`` and ``maxItems`` while still supporting structural constraints.
    Pydantic remains the authoritative validator after generation.
    """
    definitions = schema.get("$defs", {})

    def clean(value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        reference = value.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            return clean(definitions[reference.rsplit("/", 1)[-1]])
        result: dict[str, Any] = {}
        for key in ("type", "enum", "const", "required", "additionalProperties"):
            if key in value:
                result[key] = value[key]
        if "properties" in value:
            result["properties"] = {name: clean(item) for name, item in value["properties"].items()}
        if "items" in value:
            result["items"] = clean(value["items"])
        for key in ("anyOf", "oneOf"):
            if key in value:
                result[key] = [clean(item) for item in value[key]]
        return result

    return clean(schema)


@dataclass(frozen=True, slots=True)
class OllamaJsonResult:
    text: str
    finish_reason: str | None
    output_tokens: int | None
    max_output_tokens: int
    schema_mode: bool
    prompt_tokens: int | None = None
    total_duration_ns: int | None = None


def _schema_mode_unavailable(error: Exception) -> bool:
    """Recognize only an Ollama schema/grammar capability rejection."""
    status = getattr(error, "status_code", None)
    message = str(error).casefold()
    return status in {400, 404, 422} and any(
        marker in message for marker in ("schema", "grammar", "format", "structured output")
    )


class TransformationGenerator(Protocol):
    def generate(self, prompt: str) -> str: ...


class OllamaTransformationGenerator:
    """Small deterministic adapter around the configured local Ollama model."""
    def __init__(
        self,
        model_name: str | None = None,
        generation_context_factory: Callable[[Any | None], Any] | None = None,
    ) -> None:
        self.model_name = model_name or settings.ollama_model_name
        self._schema_mode_available: bool | None = None
        self._generation_context_factory = generation_context_factory

    def _generation_context(self, cancel_event: Any | None = None) -> Any:
        if self._generation_context_factory is None:
            return nullcontext()
        return self._generation_context_factory(cancel_event)

    def generate(self, prompt: str) -> str:
        from langchain_ollama import OllamaLLM
        model = OllamaLLM(model=self.model_name, temperature=0)
        last_error: Exception | None = None
        for attempt in range(settings.generation_retries + 1):
            try:
                with self._generation_context():
                    return str(model.invoke(prompt)).strip()
            except Exception as exc:  # same local-runtime retry boundary as chat generation
                last_error = exc
                if attempt < settings.generation_retries and settings.retry_cooldown_seconds:
                    time.sleep(settings.retry_cooldown_seconds)
        raise RuntimeError("Local generation failed.") from last_error

    def generate_json(
        self,
        prompt: str,
        *,
        max_output_tokens: int,
        json_schema: dict[str, Any] | None = None,
    ) -> OllamaJsonResult:
        """Generate schema-bound JSON locally with the summary context budget."""
        last_error: Exception | None = None
        for attempt in range(settings.generation_retries + 1):
            try:
                from ollama import generate
                with self._generation_context():
                    schema_mode = (
                        bool(json_schema)
                        and self._schema_mode_available is not False
                    )
                    output_format: str | dict[str, Any] = (
                        json_schema if schema_mode and json_schema else "json"
                    )
                    try:
                        response = generate(
                            model=self.model_name,
                            prompt=prompt,
                            format=output_format,
                            stream=False,
                            options={
                                "temperature": 0,
                                "num_ctx": settings.summary_context_window_tokens,
                                "num_predict": max_output_tokens,
                            },
                        )
                        if schema_mode:
                            self._schema_mode_available = True
                    except Exception as exc:
                        if not schema_mode or not _schema_mode_unavailable(exc):
                            raise
                        self._schema_mode_available = False
                        response = generate(
                            model=self.model_name,
                            prompt=prompt,
                            format="json",
                            stream=False,
                            options={
                                "temperature": 0,
                                "num_ctx": settings.summary_context_window_tokens,
                                "num_predict": max_output_tokens,
                            },
                        )
                        schema_mode = False
                return OllamaJsonResult(
                    text=str(getattr(response, "response", "")).strip(),
                    finish_reason=str(getattr(response, "done_reason", "") or "") or None,
                    output_tokens=int(value) if (value := getattr(response, "eval_count", None)) is not None else None,
                    max_output_tokens=max_output_tokens,
                    schema_mode=schema_mode,
                    prompt_tokens=int(value) if (value := getattr(response, "prompt_eval_count", None)) is not None else None,
                    total_duration_ns=int(value) if (value := getattr(response, "total_duration", None)) is not None else None,
                )
            except Exception as exc:
                last_error = exc
                if attempt < settings.generation_retries and settings.retry_cooldown_seconds:
                    time.sleep(settings.retry_cooldown_seconds)
        raise RuntimeError("Local JSON generation failed.") from last_error

    def stream_generate(self, prompt: str, *, cancel_event=None, token_callback=None) -> str:
        from langchain_ollama import OllamaLLM
        model = OllamaLLM(model=self.model_name, temperature=0)
        last_error: Exception | None = None
        for attempt in range(settings.generation_retries + 1):
            emitted = False; pieces: list[str] = []; iterator = None
            try:
                with self._generation_context(cancel_event):
                    iterator = model.stream(prompt)
                    for token in iterator:
                        if cancel_event is not None and cancel_event.is_set():
                            raise RuntimeError("Generation cancelled.")
                        value = str(token)
                        if value:
                            emitted = emitted or token_callback is not None; pieces.append(value)
                            if token_callback is not None: token_callback(value)
                    return "".join(pieces).strip()
            except Exception as exc:
                last_error = exc
                if emitted or (cancel_event is not None and cancel_event.is_set()) or attempt >= settings.generation_retries: break
                if settings.retry_cooldown_seconds: time.sleep(settings.retry_cooldown_seconds)
            finally:
                close = getattr(iterator, "close", None)
                if callable(close): close()
        raise RuntimeError("Local generation failed.") from last_error


class MessageTransformationError(RuntimeError):
    def __init__(self, message: str, *, code: str, status_code: int) -> None:
        super().__init__(message)
        self.code, self.status_code = code, status_code


_CITATION = re.compile(r"\[(\d+)\]")
_FENCE = re.compile(r"^```(?:json)?\s*\n(?P<body>.*)\n```$", re.DOTALL | re.IGNORECASE)


class ChecklistItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: str = Field(min_length=1)
    citation_ids: list[int] = Field(min_length=1)
    phase: Literal["immediate", "next", "later", "validation"] | None = None
    condition: str | None = None

    @field_validator("action")
    @classmethod
    def valid_action(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value or value.casefold().rstrip(".") in {"review this", "check this", "take action", "action required"}:
            raise ValueError("placeholder or empty action")
        return value

    @field_validator("condition")
    @classmethod
    def normalize_condition(cls, value: str | None) -> str | None:
        normalized = " ".join(value.split()) if value else None
        return normalized or None


class ChecklistNote(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    text: str = Field(min_length=1)
    citation_ids: list[int] = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return " ".join(value.split())


class ChecklistResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    items: list[ChecklistItem]
    evidence_gaps: list[ChecklistNote]
    caveats: list[ChecklistNote]


class MessageTransformationService:
    def __init__(self, db: Session, generator: TransformationGenerator) -> None:
        self.db = db
        self.repository = ChatRepository(db)
        self.generator = generator

    @staticmethod
    def build_prompt(answer: str, evidence: list[dict[str, Any]]) -> str:
        blocks = []
        for item in evidence:
            blocks.append(
                f"[{item['reference_id']}]\n"
                f"chunk_id: {item.get('chunk_id') or 'unknown'}\n"
                f"source: {item.get('source_name') or 'unknown'}\n"
                f"page: {item.get('page') or 'unknown'}\n"
                f"{item['text']}"
            )
        return (
            "Rewrite the ORIGINAL ANSWER in simpler language. Use only the supplied SELECTED EVIDENCE.\n"
            "Preserve factual meaning, caveats, uncertainty, limitations, conditions, evidence gaps, and recommendation boundaries.\n"
            "Preserve exact citation IDs such as [1]. Do not invent, alter, remove, or renumber citation IDs.\n"
            "Do not add outside knowledge, new facts, unsupported explanations, new examples, controls, owners, deadlines, procedures, priorities, or recommendations.\n"
            "Use short sentences, plain language, and clear bullets where useful. Explain technical terms only when the supplied evidence supports it.\n"
            "Do not mention these transformation instructions. Return only the simplified answer.\n\n"
            f"ORIGINAL ANSWER:\n{answer}\n\nSELECTED EVIDENCE:\n" + "\n\n".join(blocks)
        )

    @staticmethod
    def build_checklist_prompt(answer: str, evidence: list[dict[str, Any]], *, remove_duplicates: bool = False) -> str:
        core = (
            "Convert the ORIGINAL ANSWER into an actionable checklist using only the supplied SELECTED EVIDENCE.\n\n"
            "Rules:\n"
            "1. Include only actions explicitly supported by the evidence.\n"
            "2. Every checklist item must include at least one valid citation ID.\n"
            "3. Preserve citation IDs exactly.\n"
            "4. Do not add owners, deadlines, frequencies, priorities, systems, approvals, dependencies, metrics, or implementation steps unless explicitly stated in the evidence.\n"
            "5. Do not convert descriptive background into a task.\n"
            "6. Do not invent tasks merely because they are common practice.\n"
            "7. Preserve caveats, conditions, and evidence gaps.\n"
            "8. Use phase labels only when the evidence supports ordering.\n"
            "9. Merge duplicate or overlapping actions.\n"
            "10. Return valid JSON matching the required schema."
        )
        schema = (
            '\n\nJSON SCHEMA (no additional fields): '
            '{"items":[{"action":"string","citation_ids":[1],"phase":"immediate|next|later|validation|null","condition":"string|null"}],'
            '"evidence_gaps":[{"text":"string","citation_ids":[1]}],"caveats":[{"text":"string","citation_ids":[1]}]}.'
            " Return JSON only. Use empty arrays where appropriate."
        )
        if remove_duplicates:
            schema += " Remove exact duplicate actions before returning the JSON."
        blocks = [
            f"[{item['reference_id']}]\nsource: {item.get('source_name') or 'unknown'}\npage: {item.get('page') or 'unknown'}\nchunk_id: {item.get('chunk_id') or 'unknown'}\n{item['text']}"
            for item in evidence
        ]
        return core + schema + f"\n\nORIGINAL ANSWER:\n{answer}\n\nSELECTED EVIDENCE:\n" + "\n\n".join(blocks)

    @staticmethod
    def _parse_checklist(raw: str) -> ChecklistResult:
        value = raw.strip()
        fence = _FENCE.fullmatch(value)
        if fence:
            value = fence.group("body").strip()
        try:
            return ChecklistResult.model_validate_json(value)
        except ValidationError as exc:
            raise MessageTransformationError("The generated checklist was invalid.", code="invalid_checklist_output", status_code=502) from exc

    @staticmethod
    def _validate_checklist(result: ChecklistResult, allowed: set[int], evidence: list[dict[str, Any]] | None = None) -> ChecklistResult:
        if not result.items:
            raise MessageTransformationError("No evidence-supported actions were found.", code="no_supported_actions", status_code=409)
        seen: set[str] = set()
        unique: list[ChecklistItem] = []
        for item in result.items:
            if _CITATION.search(item.action) or (item.condition and _CITATION.search(item.condition)):
                raise MessageTransformationError("Checklist text must use the citation_ids field.", code="invalid_checklist_output", status_code=502)
            item.citation_ids = list(dict.fromkeys(item.citation_ids))
            if not set(item.citation_ids).issubset(allowed):
                raise MessageTransformationError("The checklist contained an invalid citation.", code="invalid_citation", status_code=502)
            key = item.action.casefold()
            if key not in seen:
                seen.add(key); unique.append(item)
            if item.phase and evidence is not None:
                evidence_text = " ".join(str(entry.get("text") or "") for entry in evidence if set(item.citation_ids).intersection({entry["reference_id"]})).casefold()
                markers = {
                    "immediate": ("immediate", "before", "prior to", "urgent", "emergency"),
                    "next": ("next", "then", "after"),
                    "later": ("later", "subsequent"),
                    "validation": ("validate", "verify", "inspection", "test"),
                }
                if not any(marker in evidence_text for marker in markers[item.phase]):
                    item.phase = None
        for note in [*result.evidence_gaps, *result.caveats]:
            if _CITATION.search(note.text):
                raise MessageTransformationError("Checklist text must use the citation_ids field.", code="invalid_checklist_output", status_code=502)
            note.citation_ids = list(dict.fromkeys(note.citation_ids))
            if not set(note.citation_ids).issubset(allowed):
                raise MessageTransformationError("The checklist contained an invalid citation.", code="invalid_citation", status_code=502)
        result.items = unique
        return result

    @staticmethod
    def render_checklist(result: ChecklistResult) -> str:
        def refs(ids: list[int]) -> str: return "".join(f"[{value}]" for value in sorted(set(ids)))
        def safe(value: str) -> str: return re.sub(r"([\\`*_{}\[\]()<>|])", r"\\\1", value).strip()
        lines = ["## Action Checklist"]
        unphased = [item for item in result.items if item.phase is None]
        for item in unphased:
            lines.append(f"- [ ] {safe(item.action)} {refs(item.citation_ids)}")
            if item.condition: lines.append(f"  - Condition: {safe(item.condition)} {refs(item.citation_ids)}")
        for phase, heading in (("immediate", "Immediate"), ("next", "Next"), ("later", "Later"), ("validation", "Validation")):
            items = [item for item in result.items if item.phase == phase]
            if not items: continue
            lines.extend(["", f"### {heading}"])
            for item in items:
                lines.append(f"- [ ] {safe(item.action)} {refs(item.citation_ids)}")
                if item.condition: lines.append(f"  - Condition: {safe(item.condition)} {refs(item.citation_ids)}")
        for heading, notes in (("Evidence gaps", result.evidence_gaps), ("Caveats", result.caveats)):
            if notes:
                lines.extend(["", f"### {heading}"])
                lines.extend(f"- {safe(note.text)} {refs(note.citation_ids)}" for note in notes)
        return "\n".join(lines)

    @staticmethod
    def _usable_snapshot(metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
        value = metadata.get("evidence_snapshot")
        if not isinstance(value, list):
            return []
        result = []
        for item in value:
            if not isinstance(item, dict) or not str(item.get("text") or "").strip():
                continue
            try:
                reference_id = int(item.get("reference_id"))
            except (TypeError, ValueError):
                continue
            result.append({**item, "reference_id": reference_id, "text": str(item["text"])})
        return result

    @staticmethod
    def _validate(source_answer: str, transformed: str, allowed: set[int]) -> None:
        if not transformed.strip():
            raise MessageTransformationError("The generated transformation was empty.", code="empty_transformed_response", status_code=502)
        result_ids = {int(value) for value in _CITATION.findall(transformed)}
        introduced = result_ids.difference(allowed)
        if introduced:
            raise MessageTransformationError("The transformation introduced invalid citation IDs.", code="invalid_citation_ids", status_code=502)
        if _CITATION.search(source_answer) and not result_ids:
            raise MessageTransformationError("The transformation removed all required citations.", code="missing_required_citations", status_code=502)

    def explain_simpler(self, message_id: uuid.UUID, access: RequestAccessContext) -> ChatMessage:
        source = self.repository.get_message_for_user(message_id, access.principal.user_id)
        submitted_order = time.time_ns()
        if source is None:
            raise MessageTransformationError("Assistant response not found.", code="message_not_found", status_code=404)
        if source.role != "assistant":
            raise MessageTransformationError("Only assistant responses can be transformed.", code="invalid_source_role", status_code=422)
        if not source.content.strip():
            raise MessageTransformationError("The source response is empty.", code="empty_source_response", status_code=422)
        evidence = self._usable_snapshot(source.metadata_ or {})
        if not evidence:
            raise MessageTransformationError("No persisted evidence snapshot is available for this response.", code="missing_persisted_evidence", status_code=409)
        prompt = self.build_prompt(source.content, evidence)
        try:
            transformed = self.generator.generate(prompt)
        except Exception as exc:
            raise MessageTransformationError("Simplification generation failed.", code="generation_failure", status_code=503) from exc
        self._validate(source.content, transformed, {item["reference_id"] for item in evidence})
        item = ChatMessage(
            session_id=source.session_id, user_id=access.principal.user_id, role="assistant", content=transformed,
            turn_sequence=submitted_order, role_sequence=1,
            citations=source.citations, sources=source.sources,
            metadata_={**(source.metadata_ or {}), "transformation": "explain_simpler",
                       "source_message_id": str(source.id), "label": "Simplified explanation",
                       "evidence_snapshot": evidence},
        )
        self.repository.add_message(item)
        try:
            self.db.commit(); self.db.refresh(item)
        except Exception as exc:
            self.db.rollback()
            raise MessageTransformationError("The simplified response could not be persisted.", code="persistence_failure", status_code=500) from exc
        return item

    def create_checklist(self, message_id: uuid.UUID, access: RequestAccessContext) -> ChatMessage:
        source = self.repository.get_message_for_user(message_id, access.principal.user_id)
        submitted_order = time.time_ns()
        if source is None:
            raise MessageTransformationError("Assistant response not found.", code="message_not_found", status_code=404)
        if source.role != "assistant":
            raise MessageTransformationError("Only assistant responses can be transformed.", code="invalid_source_role", status_code=422)
        if not source.content.strip():
            raise MessageTransformationError("The source response is empty.", code="empty_source_message", status_code=422)
        evidence = self._usable_snapshot(source.metadata_ or {})
        if not evidence:
            raise MessageTransformationError("No persisted evidence snapshot is available for this response.", code="missing_persisted_evidence", status_code=409)
        prompt = self.build_checklist_prompt(source.content, evidence)
        try:
            raw = self.generator.generate(prompt)
        except Exception as exc:
            raise MessageTransformationError("Checklist generation failed.", code="generation_failed", status_code=503) from exc
        result = self._validate_checklist(self._parse_checklist(raw), {item["reference_id"] for item in evidence}, evidence)
        content = self.render_checklist(result)
        used = {citation for item in result.items for citation in item.citation_ids}
        used.update(citation for note in [*result.evidence_gaps, *result.caveats] for citation in note.citation_ids)
        def mapped(record: Mapping[str, Any]) -> bool:
            raw_id = str(record.get("id") or "")
            try: return int(raw_id.removeprefix("S")) in used
            except ValueError: return False
        item = ChatMessage(
            session_id=source.session_id, user_id=access.principal.user_id, role="assistant", content=content,
            turn_sequence=submitted_order, role_sequence=1,
            citations=[record for record in (source.citations or []) if mapped(record)],
            sources=[record for record in (source.sources or []) if mapped(record)],
            metadata_={**(source.metadata_ or {}), "transformation": "create_checklist",
                       "source_message_id": str(source.id), "label": "Action checklist",
                       "checklist_data": result.model_dump(mode="json"), "evidence_snapshot": evidence},
        )
        self.repository.add_message(item)
        try:
            self.db.commit(); self.db.refresh(item)
        except Exception as exc:
            self.db.rollback()
            raise MessageTransformationError("The checklist could not be persisted.", code="persistence_failed", status_code=500) from exc
        return item
