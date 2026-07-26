"""Token-conscious semantic retrieval helpers."""

from __future__ import annotations

from pathlib import Path
import time
from typing import Any, Callable, Collection

from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from .config import KnowledgeOSConfig
from .embeddings import embed_texts
from .prompts import DEFAULT_PROMPT_MANAGER
from .vectorstore import execute_qdrant_operation


def search_similar_chunks(
    client: QdrantClient,
    query: str,
    embedding_model: SentenceTransformer,
    config: KnowledgeOSConfig,
    *,
    top_k: int | None = None,
    allowed_relative_paths: Collection[str] | None = None,
    allowed_document_version_ids: Collection[str] | None = None,
    allowed_note_revisions: Collection[tuple[str, int]] | None = None,
    telemetry_callback: Callable[[str, str, dict[str, Any]], None] | None = None,
    query_embedding_model_state: str = "loaded",
    query_embedding_cache_status: str = "model_reused",
    qdrant_index_status: str = "unknown",
) -> list[dict[str, Any]]:
    """Embed a query locally and return normalized, inspectable search results.

    ``top_k`` is an additive Phase 2 extension. Omitting it preserves the Phase 1
    behavior of reading ``config.top_k``.
    """

    retrieval_limit = config.top_k if top_k is None else top_k
    if retrieval_limit <= 0:
        raise ValueError("top_k must be greater than zero.")
    normalized_paths: list[str] | None = None
    if allowed_relative_paths is not None:
        normalized_paths = sorted(
            {
                str(value).replace("\\", "/").strip("/")
                for value in allowed_relative_paths
                if str(value).strip()
            }
        )
        if not normalized_paths:
            return []
    normalized_versions: list[str] | None = None
    if allowed_document_version_ids is not None:
        normalized_versions = sorted(
            {
                str(value).strip()
                for value in allowed_document_version_ids
                if str(value).strip()
            }
        )
    normalized_note_revisions = sorted(set(allowed_note_revisions or ()))
    filter_must = []
    qdrant_filter_fields: list[str] = []
    repository_id = None if allowed_relative_paths is not None else getattr(config, "repository_id", None)
    if repository_id:
        qdrant_filter_fields.append("metadata.repository_id")
        filter_must.append(
            FieldCondition(
                key="metadata.repository_id",
                match=MatchValue(value=repository_id),
            )
        )
    if normalized_versions is not None or normalized_note_revisions:
        version_conditions = []
        if normalized_versions:
            qdrant_filter_fields.append("metadata.document_version_id")
            version_conditions.append(
                FieldCondition(
                    key="metadata.document_version_id",
                    match=MatchAny(any=normalized_versions),
                )
            )
        version_conditions.extend(
            Filter(
                must=[
                    FieldCondition(
                        key="metadata.note_id",
                        match=MatchValue(value=note_id),
                    ),
                    FieldCondition(
                        key="metadata.note_revision",
                        match=MatchValue(value=revision),
                    ),
                ]
            )
            for note_id, revision in normalized_note_revisions
        )
        if not version_conditions:
            return []
        if normalized_note_revisions:
            qdrant_filter_fields.extend(
                ("metadata.note_id", "metadata.note_revision")
            )
        filter_must.append(
            Filter(should=version_conditions)
        )
    if normalized_paths is not None:
        qdrant_filter_fields.append("metadata.relative_path")
        filter_must.append(
            Filter(
                should=[
                    FieldCondition(
                        key="metadata.relative_path",
                        match=MatchAny(any=normalized_paths),
                    )
                ]
            )
        )
    query_filter = Filter(must=filter_must) if filter_must else None
    embedding_device = str(getattr(embedding_model, "device", "unknown"))
    try:
        embedding_dtype = str(next(embedding_model.parameters()).dtype)
    except (AttributeError, StopIteration, TypeError):
        embedding_dtype = "unknown"
    embedding_metrics = {
        "query_embedding_started": True,
        "query_embedding_completed": False,
        "query_embedding_device": embedding_device,
        "query_embedding_dtype": embedding_dtype,
        "query_embedding_model_state": query_embedding_model_state,
        "query_embedding_cache_status": query_embedding_cache_status,
    }
    if telemetry_callback is not None:
        telemetry_callback("query_embedding", "started", dict(embedding_metrics))
    embedding_started = time.perf_counter()
    query_vector = embed_texts(embedding_model, [query])[0]
    embedding_duration_ms = round(
        (time.perf_counter() - embedding_started) * 1000,
        3,
    )
    embedding_metrics.update(
        query_embedding_completed=True,
        query_embedding_duration_ms=embedding_duration_ms,
    )
    if telemetry_callback is not None:
        telemetry_callback("query_embedding", "completed", dict(embedding_metrics))

    qdrant_started = time.perf_counter()
    qdrant_metrics = {
        "qdrant_index_status": qdrant_index_status,
        # Qdrant exposes total filtered search duration at this API boundary,
        # not an independently measured server-side filter evaluation duration.
        "qdrant_filter_latency_ms": None,
        "qdrant_filter_fields": list(dict.fromkeys(qdrant_filter_fields)),
    }
    if telemetry_callback is not None:
        telemetry_callback("qdrant_search", "started", dict(qdrant_metrics))
    response = execute_qdrant_operation(
        config,
        "query_points",
        lambda timeout: client.query_points(
            collection_name=config.qdrant_collection_name,
            query=query_vector.tolist(),
            limit=retrieval_limit,
            with_payload=True,
            query_filter=query_filter,
            timeout=timeout,
        ),
    )
    qdrant_metrics["qdrant_search_latency_ms"] = round(
        (time.perf_counter() - qdrant_started) * 1000,
        3,
    )
    if telemetry_callback is not None:
        telemetry_callback("qdrant_search", "completed", dict(qdrant_metrics))
    results: list[dict[str, Any]] = []
    for point in response.points:
        payload = point.payload or {}
        metadata = dict(payload.get("metadata") or {})
        results.append(
            {
                "id": point.id,
                "score": float(point.score),
                "text": str(payload.get("text", "")),
                "metadata": metadata,
                "source": str(metadata.get("file_name") or metadata.get("source", "")),
                "page_number": metadata.get("page_number"),
                "page_index": metadata.get("page_index"),
                "sheet_name": metadata.get("sheet_name"),
                "sheet_index": metadata.get("sheet_index"),
                "slide_number": metadata.get("slide_number"),
                "anchor": metadata.get("anchor"),
                "chunk_id": metadata.get("chunk_id"),
            }
        )
    return results


def format_retrieved_context(
    results: list[dict[str, Any]], max_chars: int
) -> str:
    """Format a bounded context with citation metadata."""

    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero.")
    blocks: list[str] = []
    used = 0
    for rank, result in enumerate(results, start=1):
        source = Path(str(result.get("source") or "unknown")).name
        page = result.get("page_number")
        page_label = f"p. {page}" if page is not None else "page n/a"
        header = DEFAULT_PROMPT_MANAGER.render(
            "templates.retrieval_context_block",
            rank=rank,
            source=source,
            page_label=page_label,
            chunk_id=result.get("chunk_id", "n/a"),
            score=f"{result.get('score', 0.0):.3f}",
            text="",
        )
        remaining = max_chars - used - len(header)
        if remaining <= 0:
            break
        text = str(result.get("text", "")).strip()[:remaining]
        block = header + text
        blocks.append(block)
        used += len(block) + 2
        if used >= max_chars:
            break
    return "\n\n".join(blocks)


def print_retrieval_results(results: list[dict[str, Any]]) -> None:
    """Print scores, citation fields, and compact text previews."""

    if not results:
        print("No chunks retrieved.")
        return
    for rank, result in enumerate(results, start=1):
        preview = " ".join(str(result.get("text", "")).split())
        if len(preview) > 240:
            preview = preview[:237] + "..."
        page = result.get("page_number")
        score = result.get("score")
        score_label = f"{float(score):.4f}" if score is not None else "Not scored"
        print(
            f"{rank}. Similarity Score={score_label} | "
            f"Document={result.get('source') or 'Unknown document'} | "
            f"Page={page if page is not None else 'Not provided'} | "
            f"Chunk ID={result.get('chunk_id') or 'Not provided'}"
        )
        print(f"   {preview}")
