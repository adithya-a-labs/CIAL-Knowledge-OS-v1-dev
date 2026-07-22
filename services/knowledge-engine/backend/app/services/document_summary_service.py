"""Deterministic, retrieval-free, full-document summarization."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable, TypeVar
import uuid

from pydantic import BaseModel, ValidationError
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.knowledge import Document, DocumentChunk, DocumentVersion
from backend.app.models.operations import AuditEvent
from backend.app.models.workspace_content import SummaryArtifact, SummaryCitation, SummaryMapResult, SummarySource
from backend.app.schemas.summaries import (
    DocumentAnalysisCreate,
    DocumentFinalOutput,
    DocumentMapOutput,
    GroundedItem,
)
from backend.app.security.access import RequestAccessContext, document_is_accessible
from cial_knowledge_os.prompts.manager import DEFAULT_PROMPT_MANAGER
from cial_knowledge_os.token_budget import TokenManager, create_token_manager


MAP_PROMPT = "summarization.document.v1.map"
REDUCE_PROMPT = "summarization.document.v1.reduce"
REPAIR_PROMPT = "summarization.document.v1.repair"
PROMPT_VERSION = "v1"
T = TypeVar("T", bound=BaseModel)


class DocumentSummaryError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "analysis_failed",
        status_code: int = 422,
        retryable: bool = False,
        diagnostics: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable
        self.diagnostics = diagnostics or []


@dataclass(frozen=True, slots=True)
class EvidenceChunk:
    reference_id: str
    row_id: uuid.UUID
    chunk_id: str
    chunk_index: int | None
    page: int | None
    section: str | None
    text: str
    token_count: int
    segment_index: int = 1
    segment_count: int = 1

    def block(self, document_label: str) -> str:
        segment = f" Segment:{self.segment_index}/{self.segment_count}" if self.segment_count > 1 else ""
        return (
            f"[{self.reference_id}] Document:{document_label} "
            f"Page:{self.page if self.page is not None else 'not_provided'} "
            f"Section:{self.section or 'not_provided'} Chunk ID:{self.chunk_id}{segment}\n{self.text}"
        )


@dataclass(frozen=True, slots=True)
class EvidenceGroup:
    index: int
    chunks: tuple[EvidenceChunk, ...]
    rendered: str
    token_count: int

    @property
    def reference_ids(self) -> list[str]:
        return list(dict.fromkeys(chunk.reference_id for chunk in self.chunks))


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _json_payload(raw: str) -> dict[str, Any]:
    """Extract the first JSON object without repairing or rewriting model text."""
    value = raw.strip()
    if value.startswith("```"):
        newline = value.find("\n")
        if newline >= 0 and value[3:newline].strip().casefold() in {"", "json"}:
            value = value[newline + 1:].rstrip()
            if value.endswith("```"):
                value = value[:-3].rstrip()
    start = value.find("{")
    if start < 0:
        raise json.JSONDecodeError("No JSON object found", value, 0)
    payload, _ = json.JSONDecoder().raw_decode(value, start)
    if not isinstance(payload, dict):
        raise ValueError("Structured output must be a JSON object.")
    return payload


def _grounded_items(output: DocumentMapOutput | DocumentFinalOutput) -> Iterable[GroundedItem]:
    if isinstance(output, DocumentMapOutput):
        for field in ("section_summary", "key_facts", "dates", "obligations", "exceptions", "risks", "actions", "definitions"):
            yield from getattr(output, field)
        return
    for section in output.sections:
        yield from section.items
    for field in ("key_findings", "important_dates", "requirements", "action_items"):
        yield from getattr(output, field)


def _validate_citations(output: DocumentMapOutput | DocumentFinalOutput, allowed: set[str]) -> None:
    cited: set[str] = set()
    for item in _grounded_items(output):
        unknown = set(item.citation_ids) - allowed
        if unknown:
            raise ValueError("Generated output referenced an unknown source chunk.")
        cited.update(item.citation_ids)
    declared = set(output.citation_ids)
    if declared - allowed:
        raise ValueError("Generated output declared an unknown source chunk.")
    output.citation_ids = sorted(cited, key=lambda value: int(value[1:]) if value[1:].isdigit() else value)


def _deterministic_questions(document_type: str) -> list[str]:
    return {
        "calendar": ["What dates and deadlines does this document specify?", "What exceptions affect the schedule?"],
        "policy": ["What roles and controls does this policy define?", "What exceptions or escalation paths are stated?"],
        "standard": ["What requirements and controls does this standard specify?", "What implementation risks are stated?"],
        "contract": ["What obligations and dates does this document specify?", "What exceptions, remedies, or termination terms are stated?"],
        "report": ["What findings and evidence does this report present?", "What limitations does the report state?"],
    }.get(document_type, ["What are the document's major sections?", "What caveats or exceptions does the document state?"])


class DocumentSummaryPipeline:
    """All-chunk map/reduce pipeline. It has no retrieval dependency by design."""

    def __init__(self, db: Session, generator: Any, token_manager: TokenManager | None = None) -> None:
        self.db = db
        self.generator = generator
        self.tokens = token_manager or create_token_manager()
        context = max(2048, int(settings.summary_context_window_tokens))
        self.map_budget = min(max(512, int(settings.summary_map_input_tokens)), context - int(settings.summary_map_output_tokens) - 1024)
        self.reduce_budget = min(max(1024, int(settings.summary_reduce_input_tokens)), context - int(settings.summary_final_output_tokens) - 1024)

    def _progress(self, artifact: SummaryArtifact, stage: str, completed: int = 0, total: int = 0, message: str | None = None) -> None:
        artifact.progress = {"stage": stage, "completed": completed, "total": total, "message": message or stage.replace("_", " ").title()}
        artifact.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    def _check_cancelled(self, artifact: SummaryArtifact) -> None:
        self.db.expire(artifact, ["status"])
        if artifact.status == "cancelled":
            raise DocumentSummaryError("Analysis was cancelled.", code="analysis_cancelled", status_code=409)

    def _hydrate_exact_version(self, document: Document, version: DocumentVersion) -> list[DocumentChunk]:
        configured_roots = [Path(settings.repo_root), settings.corpus_root_path, settings.workspace_root_path]
        hydrated: list[tuple[str, int | None, str | None, dict[str, Any]]] = []
        if version.extracted_text_path:
            stored = Path(version.extracted_text_path)
            candidates = [stored] if stored.is_absolute() else [root / stored for root in configured_roots]
            artifact_path = next((candidate.resolve() for candidate in candidates if any(candidate.resolve().is_relative_to(root.resolve()) for root in configured_roots) and candidate.resolve().is_file()), None)
            if artifact_path is not None:
                try:
                    text = artifact_path.read_text(encoding="utf-8").strip()
                except (OSError, UnicodeError):
                    text = ""
                if text:
                    max_chunk_tokens = min(1200, self.map_budget)
                    token_ids = self.tokens.token_ids(text)
                    for index in range(0, len(token_ids), max_chunk_tokens):
                        piece = self.tokens.tokenizer.decode(token_ids[index:index + max_chunk_tokens]).strip()
                        if piece:
                            hydrated.append((piece, None, None, {"hydrated_from_version_artifact": True}))

        if not hydrated:
            relative = Path(str(document.relative_path or "").replace("\\", "/").strip("/"))
            root = settings.workspace_root_path.resolve() if str(document.repository_id or "").startswith("personal:") else settings.corpus_root_path.resolve()
            source_path = (root / relative).resolve()
            if relative.is_absolute() or ".." in relative.parts or not source_path.is_relative_to(root) or not source_path.is_file():
                return []
            from cial_knowledge_os.corpus.hash import hash_file
            if hash_file(source_path) != version.content_hash:
                return []
            try:
                from cial_knowledge_os.chunking import chunk_documents
                from cial_knowledge_os.config import KnowledgeOSConfig
                from cial_knowledge_os.loaders import _load_supported_path
                config = KnowledgeOSConfig(
                    project_root=Path(settings.repo_root), knowledge_root=root,
                    repository_id=document.repository_id, chunk_size=700, chunk_overlap=120,
                )
                parsed = _load_supported_path(source_path, config, root)
                for chunk in chunk_documents(parsed, config):
                    metadata = chunk.metadata or {}
                    text = chunk.page_content.strip()
                    if text:
                        hydrated.append((
                            text, metadata.get("page_number"), metadata.get("section"),
                            {"hydrated_from_verified_source": True, "anchor": metadata.get("anchor")},
                        ))
            except Exception:
                return []

        rows: list[DocumentChunk] = []
        for index, (piece, page, section, safe_metadata) in enumerate(hydrated):
            row = DocumentChunk(
                document_id=document.id,
                document_version_id=version.id,
                chunk_id=f"hydrated:{version.id}:{index}",
                chunk_index=index,
                page=page,
                section=section,
                text=piece,
                text_preview=piece[:500],
                token_count=self.tokens.count(piece),
                metadata_={**safe_metadata, "segment_index": index},
            )
            self.db.add(row)
            rows.append(row)
        self.db.commit()
        return rows

    def load_complete_material(self, document: Document, version: DocumentVersion) -> tuple[list[EvidenceChunk], list[str]]:
        rows = list(self.db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id, DocumentChunk.document_version_id == version.id)
            .order_by(DocumentChunk.chunk_index.asc().nullslast(), DocumentChunk.page.asc().nullslast(), DocumentChunk.section.asc().nullslast(), DocumentChunk.created_at, DocumentChunk.id)
        ))
        if not rows:
            rows = self._hydrate_exact_version(document, version)
        if not rows:
            raise DocumentSummaryError("Document text is unavailable for analysis.", code="analysis_source_unavailable", status_code=422)
        if len(rows) > settings.summary_max_chunks:
            raise DocumentSummaryError("Document exceeds the configured chunk limit.", code="analysis_document_too_large", status_code=422)

        gaps: list[str] = []
        indexed = [row.chunk_index for row in rows if row.chunk_index is not None]
        duplicates = sorted({value for value in indexed if indexed.count(value) > 1})
        if duplicates:
            gaps.append(f"Duplicate chunk indices: {', '.join(map(str, duplicates[:20]))}")
        if indexed:
            missing = sorted(set(range(min(indexed), max(indexed) + 1)) - set(indexed))
            if missing:
                gaps.append(f"Missing chunk indices: {', '.join(map(str, missing[:20]))}")
        evidence: list[EvidenceChunk] = []
        for row in rows:
            text = (row.text or "").strip()
            if not text:
                gaps.append(f"Empty or unreadable chunk: {row.chunk_id}")
                continue
            evidence.append(EvidenceChunk(
                reference_id=f"D{len(evidence) + 1}", row_id=row.id, chunk_id=row.chunk_id,
                chunk_index=row.chunk_index, page=row.page, section=row.section, text=text,
                token_count=self.tokens.count(text),
            ))
        if not evidence:
            raise DocumentSummaryError("Document contains no usable text chunks.", code="analysis_empty_document", status_code=422)
        total_tokens = sum(item.token_count for item in evidence)
        if total_tokens > settings.summary_max_document_tokens:
            raise DocumentSummaryError("Document exceeds the configured token limit.", code="analysis_document_too_large", status_code=422)
        return evidence, gaps

    def _split_chunk(self, chunk: EvidenceChunk, document_label: str) -> list[EvidenceChunk]:
        header = replace(chunk, text="", token_count=0).block(document_label)
        available = max(1, self.map_budget - self.tokens.count(header) - 8)
        ids = self.tokens.token_ids(chunk.text)
        if len(ids) <= available:
            return [chunk]
        pieces = [self.tokens.tokenizer.decode(ids[index:index + available]).strip() for index in range(0, len(ids), available)]
        pieces = [piece for piece in pieces if piece]
        return [replace(chunk, text=piece, token_count=self.tokens.count(piece), segment_index=index + 1, segment_count=len(pieces)) for index, piece in enumerate(pieces)]

    def group_evidence(self, evidence: list[EvidenceChunk], document_label: str) -> list[EvidenceGroup]:
        segments = [segment for chunk in evidence for segment in self._split_chunk(chunk, document_label)]
        groups: list[EvidenceGroup] = []
        current: list[EvidenceChunk] = []
        rendered: list[str] = []
        used = 0
        for segment in segments:
            block = segment.block(document_label)
            count = self.tokens.count(block)
            if current and used + count > self.map_budget:
                groups.append(EvidenceGroup(len(groups), tuple(current), "\n\n".join(rendered), used))
                current, rendered, used = [], [], 0
            current.append(segment); rendered.append(block); used += count
        if current:
            groups.append(EvidenceGroup(len(groups), tuple(current), "\n\n".join(rendered), used))
        return groups

    def _call_json(self, prompt: str, schema: type[T], max_output_tokens: int) -> tuple[str, str | None, int, bool | None]:
        method = getattr(self.generator, "generate_json", None)
        if callable(method):
            try:
                raw = method(prompt, max_output_tokens=max_output_tokens, json_schema=schema.model_json_schema())
            except TypeError as exc:
                if "json_schema" not in str(exc):
                    raise
                raw = method(prompt, max_output_tokens=max_output_tokens)
        else:
            raw = self.generator.generate(prompt)
        text = str(getattr(raw, "text", raw))
        finish_reason = getattr(raw, "finish_reason", None)
        reported_tokens = getattr(raw, "output_tokens", None)
        output_tokens = int(reported_tokens) if reported_tokens is not None else self.tokens.count(text)
        return text, str(finish_reason) if finish_reason else None, output_tokens, getattr(raw, "schema_mode", None)

    @staticmethod
    def _diagnostic(
        *, text: str, finish_reason: str | None, output_tokens: int, max_output_tokens: int,
        attempt: int, repair_attempted: bool, schema: type[BaseModel], error: Exception | None = None,
        phase: str = "generation", schema_mode: bool | None = None,
    ) -> dict[str, Any]:
        return {
            "finish_reason": finish_reason,
            "response_character_count": len(text),
            "output_token_count": output_tokens,
            "max_output_tokens": max_output_tokens,
            "json_error_line": error.lineno if isinstance(error, json.JSONDecodeError) else None,
            "json_error_column": error.colno if isinstance(error, json.JSONDecodeError) else None,
            "attempt_number": attempt,
            "repair_attempted": repair_attempted,
            "schema_name": schema.__name__,
            "phase": phase,
            "schema_mode": schema_mode,
        }

    def _next_output_budget(self, prompt: str, current: int) -> int:
        available = max(1, int(settings.summary_context_window_tokens) - self.tokens.count(prompt) - 256)
        return min(available, max(current + 128, current * 2))

    @staticmethod
    def _validation_detail(error: Exception) -> str:
        if isinstance(error, json.JSONDecodeError):
            return f"JSON decode error: {error.msg}; line={error.lineno}; column={error.colno}"
        if isinstance(error, ValidationError):
            return json.dumps(error.errors(include_input=False), ensure_ascii=False, separators=(",", ":"))
        return type(error).__name__

    def _repair_prompt(self, malformed: str, error: Exception, schema: type[T], allowed: set[str]) -> str:
        return DEFAULT_PROMPT_MANAGER.render(
            REPAIR_PROMPT,
            malformed_output=malformed,
            validation_error=self._validation_detail(error),
            target_schema=json.dumps(schema.model_json_schema(), ensure_ascii=False, separators=(",", ":")),
            allowed_citation_ids=", ".join(sorted(allowed)) or "none",
        )

    def _generate_validated(
        self, prompt: str, schema: type[T], allowed: set[str], max_output_tokens: int,
    ) -> tuple[T, int, int, int, list[dict[str, Any]]]:
        last_error: Exception | None = None
        last_failure_code = "analysis_invalid_model_output"
        diagnostics: list[dict[str, Any]] = []
        started = perf_counter()
        output_budget = max_output_tokens
        for attempt in range(1, settings.generation_retries + 2):
            try:
                text, finish_reason, output_tokens, schema_mode = self._call_json(prompt, schema, output_budget)
                truncated = (finish_reason or "").casefold() in {"length", "max_tokens", "token_limit"} or output_tokens >= output_budget
                if truncated:
                    diagnostics.append(self._diagnostic(
                        text=text, finish_reason=finish_reason, output_tokens=output_tokens,
                        max_output_tokens=output_budget, attempt=attempt, repair_attempted=False,
                        schema=schema, phase="generation", schema_mode=schema_mode,
                    ))
                    last_error = ValueError("Structured output reached its token cap.")
                    last_failure_code = "analysis_output_truncated"
                    increased = self._next_output_budget(prompt, output_budget)
                    if increased > output_budget:
                        output_budget = increased
                    continue
                try:
                    result = schema.model_validate(_json_payload(text))
                except (json.JSONDecodeError, ValidationError) as validation_error:
                    diagnostics.append(self._diagnostic(
                        text=text, finish_reason=finish_reason, output_tokens=output_tokens,
                        max_output_tokens=output_budget, attempt=attempt, repair_attempted=True,
                        schema=schema, error=validation_error, phase="generation", schema_mode=schema_mode,
                    ))
                    last_error = validation_error
                    last_failure_code = "analysis_invalid_model_output"
                    repair_prompt = self._repair_prompt(text, validation_error, schema, allowed)
                    try:
                        repaired_text, repaired_finish, repaired_tokens, repaired_schema_mode = self._call_json(repair_prompt, schema, output_budget)
                        repair_truncated = (repaired_finish or "").casefold() in {"length", "max_tokens", "token_limit"} or repaired_tokens >= output_budget
                        repair_error: Exception | None = None
                        if repair_truncated:
                            repair_error = ValueError("Repair output reached its token cap.")
                        else:
                            try:
                                repaired = schema.model_validate(_json_payload(repaired_text))
                                _validate_citations(repaired, allowed)
                            except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                                repair_error = exc
                        diagnostics.append(self._diagnostic(
                            text=repaired_text, finish_reason=repaired_finish, output_tokens=repaired_tokens,
                            max_output_tokens=output_budget, attempt=attempt, repair_attempted=True,
                            schema=schema, error=repair_error, phase="repair", schema_mode=repaired_schema_mode,
                        ))
                        if repair_error is None:
                            return repaired, attempt, repaired_tokens, int((perf_counter() - started) * 1000), diagnostics
                        last_error = repair_error
                        if repair_truncated:
                            last_failure_code = "analysis_output_truncated"
                            increased = self._next_output_budget(prompt, output_budget)
                            if increased > output_budget:
                                output_budget = increased
                    except (RuntimeError, OSError) as repair_transport_error:
                        last_error = repair_transport_error
                    continue
                diagnostic = self._diagnostic(
                    text=text, finish_reason=finish_reason, output_tokens=output_tokens,
                    max_output_tokens=output_budget, attempt=attempt, repair_attempted=False,
                    schema=schema, phase="generation", schema_mode=schema_mode,
                )
                try:
                    _validate_citations(result, allowed)
                except ValueError:
                    diagnostics.append(diagnostic)
                    raise
                diagnostics.append(diagnostic)
                return result, attempt, output_tokens, int((perf_counter() - started) * 1000), diagnostics
            except (RuntimeError, OSError, ValueError) as exc:
                last_error = exc
                last_failure_code = "analysis_invalid_model_output"
        message = "Local model output was truncated." if last_failure_code == "analysis_output_truncated" else "Local model output failed grounded schema validation."
        # Do not chain validation exceptions: Pydantic may embed malformed model
        # output in its exception text, and worker tracebacks must stay content-free.
        raise DocumentSummaryError(
            message, code=last_failure_code, status_code=422, retryable=True, diagnostics=diagnostics,
        ) from None

    def _checkpoint(self, artifact: SummaryArtifact, stage: str, level: int, group_index: int, input_text: str, refs: list[str], schema: type[T], prompt: str, max_output: int) -> T:
        digest = hashlib.sha256(input_text.encode("utf-8")).hexdigest()
        existing = self.db.scalar(select(SummaryMapResult).where(
            SummaryMapResult.summary_id == artifact.id, SummaryMapResult.stage == stage,
            SummaryMapResult.level == level, SummaryMapResult.group_index == group_index,
        ))
        if existing is not None:
            if existing.input_hash != digest:
                raise DocumentSummaryError("Analysis checkpoint does not match its immutable source.", code="analysis_checkpoint_mismatch")
            result = schema.model_validate(existing.structured_output)
            _validate_citations(result, set(refs))
            return result
        result, attempts, output_tokens, latency_ms, diagnostics = self._generate_validated(prompt, schema, set(refs), max_output)
        artifact.generation_config = {
            **(artifact.generation_config or {}),
            "structured_output_diagnostics": [
                *(artifact.generation_config or {}).get("structured_output_diagnostics", []),
                *diagnostics,
            ],
        }
        self.db.add(SummaryMapResult(
            summary_id=artifact.id, stage=stage, level=level, group_index=group_index,
            input_hash=digest, source_reference_ids=refs, structured_output=result.model_dump(mode="json"),
            input_token_count=self.tokens.count(input_text), output_token_count=output_tokens,
            attempts=attempts, latency_ms=latency_ms,
        ))
        self.db.commit()
        return result

    def _group_partials(self, partials: list[DocumentMapOutput | DocumentFinalOutput]) -> list[list[DocumentMapOutput | DocumentFinalOutput]]:
        groups: list[list[DocumentMapOutput | DocumentFinalOutput]] = []
        current: list[DocumentMapOutput | DocumentFinalOutput] = []
        used = 0
        for item in partials:
            count = self.tokens.count(json.dumps(item.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")))
            if current and used + count > self.reduce_budget:
                groups.append(current); current = []; used = 0
            current.append(item); used += count
        if current:
            groups.append(current)
        return groups

    def run(self, artifact: SummaryArtifact, document: Document, version: DocumentVersion) -> None:
        self._progress(artifact, "loading_chunks", message="Reading document sections")
        evidence, coverage_gaps = self.load_complete_material(document, version)
        groups = self.group_evidence(evidence, document.name)
        boundaries = [{"group": group.index, "reference_ids": group.reference_ids, "tokens": group.token_count} for group in groups]
        artifact.source_chunk_count = len(evidence)
        artifact.source_token_count = sum(item.token_count for item in evidence)
        artifact.map_group_count = len(groups)
        artifact.generation_config = {
            **(artifact.generation_config or {}),
            "temperature": 0, "context_window_tokens": settings.summary_context_window_tokens,
            "map_input_budget": self.map_budget, "map_output_budget": settings.summary_map_output_tokens,
            "reduce_input_budget": self.reduce_budget, "final_output_budget": settings.summary_final_output_tokens,
            "tokenizer": self.tokens.encoding_name, "ordered_chunk_ids": [item.chunk_id for item in evidence],
            "map_boundaries": boundaries, "coverage_gaps": coverage_gaps,
            "map_prompt": MAP_PROMPT, "reduce_prompt": REDUCE_PROMPT, "repair_prompt": REPAIR_PROMPT,
        }
        self.db.commit()

        mapped: list[DocumentMapOutput] = []
        for group in groups:
            self._check_cancelled(artifact)
            self._progress(artifact, "mapping", group.index, len(groups), f"Reading {group.index + 1} of {len(groups)} sections")
            prompt = DEFAULT_PROMPT_MANAGER.render(
                MAP_PROMPT, document_label=document.name, summary_type=artifact.summary_type,
                summary_length=artifact.summary_length, evidence_blocks=group.rendered,
            )
            mapped.append(self._checkpoint(
                artifact, "map", 0, group.index, group.rendered, group.reference_ids,
                DocumentMapOutput, prompt, settings.summary_map_output_tokens,
            ))

        current: list[DocumentMapOutput | DocumentFinalOutput] = list(mapped)
        level = 0
        while True:
            self._check_cancelled(artifact)
            partial_groups = self._group_partials(current)
            final_level = len(partial_groups) == 1
            reduced: list[DocumentFinalOutput] = []
            total = len(partial_groups)
            for index, partial_group in enumerate(partial_groups):
                self._progress(artifact, "reducing", index, total, "Combining grounded section summaries")
                input_text = json.dumps([item.model_dump(mode="json") for item in partial_group], ensure_ascii=False, separators=(",", ":"))
                refs = sorted({ref for item in partial_group for ref in item.citation_ids}, key=lambda value: int(value[1:]) if value[1:].isdigit() else value)
                prompt = DEFAULT_PROMPT_MANAGER.render(
                    REDUCE_PROMPT, document_label=document.name, summary_type=artifact.summary_type,
                    summary_length=artifact.summary_length, output_kind="final synthesis" if final_level else f"recursive reduction level {level}",
                    allowed_reference_ids=", ".join(refs), partial_summaries=input_text,
                )
                reduced.append(self._checkpoint(
                    artifact, "reduce", level, index, input_text, refs,
                    DocumentFinalOutput, prompt, settings.summary_final_output_tokens,
                ))
            if final_level:
                final = reduced[0]
                break
            current = reduced
            level += 1

        self._progress(artifact, "validating", message="Validating citations and coverage")
        if coverage_gaps:
            final.coverage_gaps = list(dict.fromkeys([*coverage_gaps, *final.coverage_gaps]))
        final.suggested_questions = _deterministic_questions(final.document_type)
        if artifact.summary_type == "action_items":
            final.sections = []; final.key_findings = []; final.important_dates = []; final.requirements = []
        allowed = {item.reference_id for item in evidence}
        _validate_citations(final, allowed)
        used_refs = set(final.citation_ids)
        by_ref = {item.reference_id: item for item in evidence}

        self._progress(artifact, "persisting", message="Saving immutable analysis")
        source = self.db.scalar(select(SummarySource).where(SummarySource.summary_id == artifact.id).order_by(SummarySource.ordinal).limit(1))
        if source is None:
            raise DocumentSummaryError("Analysis source record is unavailable.", code="analysis_source_unavailable")
        self.db.execute(delete(SummaryCitation).where(SummaryCitation.summary_id == artifact.id))
        snapshots: list[dict[str, Any]] = []
        for ordering, reference_id in enumerate(sorted(used_refs, key=lambda value: int(value[1:])), 1):
            item = by_ref[reference_id]
            snapshot = {
                "reference_id": reference_id, "document_id": str(document.id), "document_version_id": str(version.id),
                "chunk_id": item.chunk_id, "page": item.page, "section": item.section, "excerpt": item.text[:500], "ordering": ordering,
            }
            snapshots.append(snapshot)
            self.db.add(SummaryCitation(
                summary_id=artifact.id, citation_id=reference_id, source_record_id=source.id,
                document_id=document.id, document_version_id=version.id, page_number=item.page,
                section=item.section, chunk_id=item.chunk_id, excerpt=item.text[:500], ordering=ordering,
                metadata_={"chunk_row_id": str(item.row_id), "chunk_index": item.chunk_index},
            ))
        artifact.title = final.title
        artifact.content_json = final.model_dump(mode="json")
        artifact.content_markdown = self.render_markdown(final)
        artifact.citation_snapshot = snapshots
        artifact.citation_count = len(snapshots)
        artifact.provenance_hash = _canonical_hash({
            "document_version_id": str(version.id), "content_hash": version.content_hash,
            "ordered_chunk_ids": [item.chunk_id for item in evidence], "map_boundaries": boundaries,
            "prompt_version": PROMPT_VERSION, "model": artifact.model_name, "temperature": 0,
        })
        checkpoints = list(self.db.scalars(select(SummaryMapResult).where(SummaryMapResult.summary_id == artifact.id)))
        completed_at = datetime.now(timezone.utc)
        artifact.generation_config = {
            **(artifact.generation_config or {}),
            "model_calls": len(checkpoints),
            "input_tokens": sum(row.input_token_count for row in checkpoints),
            "output_tokens": sum(row.output_token_count for row in checkpoints),
            "retries": sum(max(0, row.attempts - 1) for row in checkpoints),
            "map_latency_ms": sum(row.latency_ms for row in checkpoints if row.stage == "map"),
            "reduce_latency_ms": sum(row.latency_ms for row in checkpoints if row.stage == "reduce"),
            "total_latency_ms": max(0, int((completed_at - (artifact.started_at or artifact.created_at)).total_seconds() * 1000)),
            "coverage_gap_count": len(final.coverage_gaps),
            "citation_count": len(snapshots),
            "invalid_citation_count": 0,
        }
        artifact.status = "completed"
        artifact.completed_at = artifact.updated_at = completed_at
        artifact.progress = {"stage": "completed", "completed": len(groups), "total": len(groups), "message": "Document analysis ready"}
        previous = list(self.db.scalars(select(SummaryArtifact).where(
            SummaryArtifact.document_id == document.id, SummaryArtifact.id != artifact.id,
            SummaryArtifact.status == "completed", SummaryArtifact.deleted_at.is_(None),
        )))
        for old in previous:
            if old.document_version_id != version.id or old.reuse_key == artifact.reuse_key:
                old.status = "stale"; old.superseded_by_id = artifact.id
        self.db.add(AuditEvent(
            user_id=artifact.created_by_user_id, actor_user_id=artifact.created_by_user_id,
            action="document_analysis.generated", entity_type="summary", entity_id=artifact.id, status="succeeded",
            metadata_={"document_id": str(document.id), "document_version_id": str(version.id), "chunks": len(evidence), "groups": len(groups), "citations": len(snapshots)},
        ))
        self.db.commit()

    @staticmethod
    def render_markdown(final: DocumentFinalOutput) -> str:
        lines = [f"# {final.title}"]
        def add_items(heading: str, items: list[GroundedItem]) -> None:
            if not items:
                return
            lines.extend(["", f"## {heading}"])
            for item in items:
                markers = " ".join(f"[{value}]" for value in item.citation_ids)
                lines.append(f"- {item.text} {markers}".rstrip())
        for section in final.sections:
            add_items(section.heading, section.items)
        add_items("Key Findings", final.key_findings)
        add_items("Important Dates", final.important_dates)
        add_items("Requirements", final.requirements)
        add_items("Action Items", final.action_items)
        if final.coverage_gaps:
            lines.extend(["", "## Coverage Gaps", *[f"- {value}" for value in final.coverage_gaps]])
        return "\n".join(lines).strip()


class DocumentSummaryService:
    def __init__(self, db: Session, generator: Any) -> None:
        self.db = db
        self.generator = generator

    @staticmethod
    def _model_name(generator: Any) -> str:
        return str(getattr(generator, "model_name", settings.ollama_model_name))

    def _document(self, access: RequestAccessContext, document_id: uuid.UUID) -> tuple[Document, DocumentVersion]:
        document = self.db.get(Document, document_id)
        if document is None or not document_is_accessible(document, access) or document.current_version_id is None:
            raise DocumentSummaryError("Document unavailable.", code="document_not_found", status_code=404)
        version = self.db.get(DocumentVersion, document.current_version_id)
        if version is None or version.document_id != document.id:
            raise DocumentSummaryError("Document unavailable.", code="document_not_found", status_code=404)
        if version.status != "indexed":
            raise DocumentSummaryError("Document is not ready for analysis.", code="document_not_ready", status_code=409)
        return document, version

    def _artifact(self, access: RequestAccessContext, summary_id: uuid.UUID) -> SummaryArtifact:
        artifact = self.db.scalar(select(SummaryArtifact).where(SummaryArtifact.id == summary_id, SummaryArtifact.deleted_at.is_(None)))
        if artifact is None or artifact.document_id is None:
            raise DocumentSummaryError("Analysis unavailable.", code="analysis_not_found", status_code=404)
        document = self.db.get(Document, artifact.document_id)
        if document is None or not document_is_accessible(document, access):
            raise DocumentSummaryError("Analysis unavailable.", code="analysis_not_found", status_code=404)
        return artifact

    def _reuse_key(self, version: DocumentVersion, payload: DocumentAnalysisCreate) -> str:
        return _canonical_hash({
            "document_version_id": str(version.id), "content_hash": version.content_hash,
            "summary_type": payload.summary_type, "length": payload.length,
            "prompt_version": PROMPT_VERSION, "language": payload.language.casefold(),
            "model": self._model_name(self.generator),
        })

    def create(self, access: RequestAccessContext, document_id: uuid.UUID, payload: DocumentAnalysisCreate) -> dict[str, Any]:
        document, version = self._document(access, document_id)
        user_id = access.principal.user_id
        if user_id is None:
            raise DocumentSummaryError("Authentication required.", code="authentication_required", status_code=401)
        key = self._reuse_key(version, payload)
        active = self.db.scalar(select(SummaryArtifact).where(
            SummaryArtifact.reuse_key == key, SummaryArtifact.status.in_(["queued", "running"]), SummaryArtifact.deleted_at.is_(None),
        ).order_by(SummaryArtifact.created_at.desc()).limit(1))
        if active is not None:
            return {"disposition": active.status, "summary": self.payload(access, active)}
        if not payload.force_regenerate:
            completed = self.db.scalar(select(SummaryArtifact).where(
                SummaryArtifact.reuse_key == key, SummaryArtifact.status == "completed", SummaryArtifact.deleted_at.is_(None),
            ).order_by(SummaryArtifact.completed_at.desc()).limit(1))
            if completed is not None:
                return {"disposition": "reused", "summary": self.payload(access, completed)}
        artifact = SummaryArtifact(
            organization_id=document.organization_id, workspace_id=document.workspace_id,
            owner_user_id=user_id, created_by_user_id=user_id, document_id=document.id, document_version_id=version.id,
            title=f"{payload.summary_type.replace('_', ' ').title()} · {document.name}",
            summary_type=payload.summary_type, summary_length=payload.length, multi_document_mode="together",
            status="queued", prompt_name=REDUCE_PROMPT, prompt_version=PROMPT_VERSION,
            model_name=self._model_name(self.generator), source_fingerprint=version.content_hash,
            reuse_key=key, language=payload.language.casefold(), document_count=1,
            generation_config={"temperature": 0},
            progress={"stage": "queued", "completed": 0, "total": 0, "message": "Waiting to prepare document analysis"},
        )
        self.db.add(artifact)
        try:
            self.db.flush()
            self.db.add(SummarySource(
                summary_id=artifact.id, ordinal=1, source_type="document", source_id=document.id,
                document_version_id=version.id, title=document.name, content_hash=version.content_hash,
                source_snapshot={"document_id": str(document.id), "document_version_id": str(version.id), "version_number": version.version_number, "content_hash": version.content_hash},
            ))
            self.db.commit(); self.db.refresh(artifact)
        except IntegrityError:
            self.db.rollback()
            active = self.db.scalar(select(SummaryArtifact).where(
                SummaryArtifact.reuse_key == key, SummaryArtifact.status.in_(["queued", "running"]), SummaryArtifact.deleted_at.is_(None),
            ).order_by(SummaryArtifact.created_at.desc()).limit(1))
            if active is None:
                raise
            return {"disposition": active.status, "summary": self.payload(access, active)}
        return {"disposition": "queued", "summary": self.payload(access, artifact)}

    def get_analysis(self, access: RequestAccessContext, document_id: uuid.UUID, summary_type: str, length: str) -> dict[str, Any]:
        document, version = self._document(access, document_id)
        rows = list(self.db.scalars(select(SummaryArtifact).where(
            SummaryArtifact.document_id == document.id, SummaryArtifact.summary_type == summary_type,
            SummaryArtifact.summary_length == length, SummaryArtifact.deleted_at.is_(None),
        ).order_by(SummaryArtifact.created_at.desc()).limit(25)))
        for row in rows:
            if row.document_version_id != version.id and row.status == "completed":
                row.status = "stale"
        if any(self.db.is_modified(row) for row in rows):
            self.db.commit()
        current = next((row for row in rows if row.document_version_id == version.id), None)
        previous = [row for row in rows if row.document_version_id != version.id]
        return {
            "document_id": document.id, "current_version_id": version.id,
            "summary_type": summary_type, "length": length,
            "current": self.payload(access, current) if current else None,
            "previous": [self.payload(access, row) for row in previous[:5]],
        }

    def get(self, access: RequestAccessContext, summary_id: uuid.UUID) -> dict[str, Any]:
        return self.payload(access, self._artifact(access, summary_id))

    def cancel(self, access: RequestAccessContext, summary_id: uuid.UUID) -> dict[str, Any]:
        artifact = self._artifact(access, summary_id)
        if artifact.status not in {"queued", "running"}:
            raise DocumentSummaryError("Only queued or running analysis can be cancelled.", code="analysis_not_cancellable", status_code=409)
        artifact.status = "cancelled"
        artifact.completed_at = datetime.now(timezone.utc)
        artifact.progress = {"stage": "cancelled", "completed": 0, "total": artifact.map_group_count, "message": "Analysis cancelled"}
        self.db.commit()
        return self.payload(access, artifact)

    def payload(self, access: RequestAccessContext, artifact: SummaryArtifact | None) -> dict[str, Any] | None:
        if artifact is None:
            return None
        self._artifact(access, artifact.id)
        version = self.db.get(DocumentVersion, artifact.document_version_id) if artifact.document_version_id else None
        document = self.db.get(Document, artifact.document_id) if artifact.document_id else None
        stale = bool(document and artifact.document_version_id != document.current_version_id)
        sources = list(self.db.scalars(select(SummarySource).where(SummarySource.summary_id == artifact.id).order_by(SummarySource.ordinal)))
        citations = list(self.db.scalars(select(SummaryCitation).where(SummaryCitation.summary_id == artifact.id).order_by(SummaryCitation.ordering.asc().nullslast(), SummaryCitation.citation_id)))
        return {
            "id": artifact.id, "title": artifact.title, "summary_type": artifact.summary_type,
            "summary_length": artifact.summary_length, "multi_document_mode": artifact.multi_document_mode,
            "status": "stale" if stale and artifact.status == "completed" else artifact.status,
            "content_markdown": artifact.content_markdown, "structured_payload": artifact.content_json,
            "citation_snapshot": artifact.citation_snapshot or [], "citation_count": artifact.citation_count,
            "document_count": artifact.document_count, "document_id": artifact.document_id,
            "document_version_id": artifact.document_version_id, "document_version_number": version.version_number if version else None,
            "prompt_name": artifact.prompt_name, "prompt_version": artifact.prompt_version,
            "model_name": artifact.model_name, "language": artifact.language,
            "source_chunk_count": artifact.source_chunk_count, "source_token_count": artifact.source_token_count,
            "map_group_count": artifact.map_group_count, "generation_config": artifact.generation_config or {},
            "provenance_hash": artifact.provenance_hash, "progress": artifact.progress or {},
            "created_at": artifact.created_at, "updated_at": artifact.updated_at,
            "started_at": artifact.started_at, "completed_at": artifact.completed_at,
            "error_code": artifact.error_code, "error_message": artifact.error_message_safe,
            "retryable": bool((artifact.generation_config or {}).get("error_retryable", False)),
            "stale": stale or artifact.status == "stale",
            "suggested_questions": (artifact.content_json or {}).get("suggested_questions", []),
            "sources": [{"id": str(source.id), "source_type": source.source_type, "source_id": str(source.source_id) if source.source_id else None, "title": source.title, "version_id": str(source.document_version_id) if source.document_version_id else None} for source in sources],
            "citations": [{
                "citation_id": row.citation_id, "reference_id": row.citation_id,
                "document_id": str(row.document_id) if row.document_id else None,
                "document_version_id": str(row.document_version_id) if row.document_version_id else None,
                "note_id": str(row.note_id) if row.note_id else None, "page_number": row.page_number,
                "section": row.section, "chunk_id": row.chunk_id, "excerpt": row.excerpt, "ordering": row.ordering,
            } for row in citations],
        }


def mark_analysis_failed(db: Session, artifact_id: uuid.UUID, error: Exception) -> None:
    artifact = db.get(SummaryArtifact, artifact_id)
    if artifact is None or artifact.status == "cancelled":
        return
    artifact.status = "failed"
    artifact.error_code = error.code if isinstance(error, DocumentSummaryError) else "analysis_generation_failed"
    retryable = bool(getattr(error, "retryable", False))
    artifact.error_message_safe = (
        "The model output reached its safe length limit. Retry the analysis."
        if artifact.error_code == "analysis_output_truncated"
        else "The model output could not be validated. Retry the analysis."
        if artifact.error_code == "analysis_invalid_model_output"
        else "Document analysis could not be completed."
    )
    artifact.generation_config = {
        **(artifact.generation_config or {}),
        "error_retryable": retryable,
        "terminal_error_code": artifact.error_code,
        **({"structured_output_diagnostics": getattr(error, "diagnostics", [])} if getattr(error, "diagnostics", None) else {}),
    }
    artifact.completed_at = datetime.now(timezone.utc)
    artifact.progress = {"stage": "failed", "completed": 0, "total": artifact.map_group_count, "message": artifact.error_message_safe, "retryable": retryable}
    db.commit()
