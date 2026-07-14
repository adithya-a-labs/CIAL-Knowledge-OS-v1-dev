"""Token-conscious semantic retrieval helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Collection

from qdrant_client.models import FieldCondition, Filter, MatchValue

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from .config import KnowledgeOSConfig
from .embeddings import embed_texts
from .prompts import DEFAULT_PROMPT_MANAGER


def search_similar_chunks(
    client: QdrantClient,
    query: str,
    embedding_model: SentenceTransformer,
    config: KnowledgeOSConfig,
    *,
    top_k: int | None = None,
    allowed_relative_paths: Collection[str] | None = None,
) -> list[dict[str, Any]]:
    """Embed a query locally and return normalized, inspectable search results.

    ``top_k`` is an additive Phase 2 extension. Omitting it preserves the Phase 1
    behavior of reading ``config.top_k``.
    """

    retrieval_limit = config.top_k if top_k is None else top_k
    if retrieval_limit <= 0:
        raise ValueError("top_k must be greater than zero.")
    query_vector = embed_texts(embedding_model, [query])[0]
    filter_must = []
    repository_id = getattr(config, "repository_id", None)
    if repository_id:
        filter_must.append(
            FieldCondition(
                key="metadata.repository_id",
                match=MatchValue(value=repository_id),
            )
        )
    query_filter = Filter(must=filter_must) if filter_must else None
    if allowed_relative_paths:
        normalized_paths = sorted({str(value).replace("\\", "/").strip("/") for value in allowed_relative_paths if str(value).strip()})
        if not normalized_paths:
            return []
        query_filter = Filter(
            must=filter_must,
            should=[
                FieldCondition(
                    key="metadata.relative_path",
                    match=MatchValue(value=value),
                )
                for value in normalized_paths
            ]
        )
    response = client.query_points(
        collection_name=config.qdrant_collection_name,
        query=query_vector.tolist(),
        limit=retrieval_limit,
        with_payload=True,
        query_filter=query_filter,
    )
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
