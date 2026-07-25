"""Local embedded and self-hosted Qdrant storage helpers."""

from __future__ import annotations

import logging
import shutil
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import numpy as np
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from .config import KnowledgeOSConfig

logger = logging.getLogger(__name__)

_LOCK_MESSAGE = (
    "Embedded Qdrant storage is locked. Only one process can access the same "
    "local Qdrant path at a time. Close other Qdrant clients or restart notebook "
    "kernels using this path, then retry. Use Qdrant server mode when multiple "
    "processes need concurrent access."
)

_SERVER_ERROR_TEMPLATE = """Qdrant server mode is enabled but {url} is not reachable. Start local Qdrant with:
docker compose -f docker-compose.qdrant.yml up -d
or restart an existing container with:
docker start cial-qdrant"""

_QUERY_PAYLOAD_INDEXES = (
    ("metadata.relative_path", PayloadSchemaType.KEYWORD),
    ("metadata.document_id", PayloadSchemaType.KEYWORD),
    ("metadata.document_version_id", PayloadSchemaType.KEYWORD),
    ("metadata.note_id", PayloadSchemaType.KEYWORD),
    ("metadata.note_revision", PayloadSchemaType.INTEGER),
    ("metadata.repository_id", PayloadSchemaType.KEYWORD),
    ("metadata.owner_user_id", PayloadSchemaType.KEYWORD),
    ("metadata.visibility", PayloadSchemaType.KEYWORD),
    ("metadata.lifecycle_status", PayloadSchemaType.KEYWORD),
)


def _operation_timeout(config: KnowledgeOSConfig, operation: str) -> int:
    if operation in {"health", "get_collections"}:
        value = getattr(config, "qdrant_health_timeout_seconds", 5.0)
    elif operation in {"query_points", "scroll", "retrieve", "count"}:
        value = getattr(config, "qdrant_query_timeout_seconds", 30.0)
    elif operation == "upsert":
        value = getattr(config, "qdrant_upsert_timeout_seconds", 60.0)
    elif operation == "delete":
        value = getattr(config, "qdrant_delete_timeout_seconds", 60.0)
    else:
        value = getattr(config, "qdrant_collection_timeout_seconds", 120.0)
    return max(1, int(round(value)))


def _status_code(exc: BaseException) -> int | None:
    for candidate in (exc, getattr(exc, "response", None)):
        value = getattr(candidate, "status_code", None)
        if isinstance(value, int):
            return value
    return None


def is_transient_qdrant_error(exc: BaseException) -> bool:
    """Classify network/timeouts/5xx failures without retrying bad requests."""

    visited: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        status = _status_code(current)
        if status is not None:
            return status >= 500 or status in {408, 429}
        if isinstance(
            current,
            (
                httpx.ReadTimeout,
                httpx.ConnectTimeout,
                httpx.ConnectError,
                httpx.NetworkError,
                ConnectionError,
                TimeoutError,
            ),
        ):
            return True
        current = (
            getattr(current, "__cause__", None)
            or getattr(current, "__context__", None)
        )
    return False


def execute_qdrant_operation(
    config: KnowledgeOSConfig,
    operation: str,
    call: Callable[[int], Any],
    *,
    collection: str | None = None,
    affected_count: int | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Any:
    """Run one Qdrant operation with bounded transient-only retries."""

    timeout_seconds = _operation_timeout(config, operation)
    collection_name = collection or config.qdrant_collection_name
    started = time.perf_counter()
    logger.info(
        "qdrant_operation_started",
        extra={
            "event": "qdrant_operation_started",
            "operation": operation,
            "collection": collection_name,
            "timeout_seconds": timeout_seconds,
        },
    )
    query_operation = operation in {"query_points", "scroll", "retrieve", "count"}
    retry_attempts = int(
        getattr(config, "qdrant_query_retry_attempts", 2)
        if query_operation
        else getattr(config, "qdrant_retry_attempts", 3)
    )
    retry_backoff = float(
        getattr(config, "qdrant_retry_backoff_seconds", 2.0)
    )
    for attempt in range(1, retry_attempts + 1):
        try:
            result = call(timeout_seconds)
        except Exception as exc:
            transient = is_transient_qdrant_error(exc)
            if transient and attempt < retry_attempts:
                delay = retry_backoff * (2 ** (attempt - 1))
                logger.warning(
                    "qdrant_operation_retry",
                    extra={
                        "event": "qdrant_operation_retry",
                        "operation": operation,
                        "collection": collection_name,
                        "attempt": attempt + 1,
                        "exception_type": type(exc).__name__,
                        "timeout_seconds": timeout_seconds,
                    },
                )
                sleep_fn(delay)
                continue
            logger.error(
                "qdrant_operation_failed",
                extra={
                    "event": "qdrant_operation_failed",
                    "operation": operation,
                    "collection": collection_name,
                    "duration_ms": int((time.perf_counter() - started) * 1000),
                    "exception_type": type(exc).__name__,
                    "affected_count": affected_count,
                },
            )
            raise
        logger.info(
            "qdrant_operation_completed",
            extra={
                "event": "qdrant_operation_completed",
                "operation": operation,
                "collection": collection_name,
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "affected_count": affected_count,
            },
        )
        return result
    raise RuntimeError("Qdrant retry loop exhausted unexpectedly.")


def _update_completed(result: Any) -> bool:
    status = getattr(result, "status", None)
    if status is None:
        return True
    raw_value = getattr(status, "value", status)
    if not isinstance(raw_value, str):
        return True
    value = raw_value.casefold()
    return value in {"acknowledged", "completed"}


def _raise_useful_lock_error(exc: Exception) -> None:
    message = str(exc).lower()
    if any(
        token in message
        for token in (
            "lock",
            "already accessed",
            "resource busy",
            "used by another process",
            "permission denied",
            "access is denied",
        )
    ):
        raise RuntimeError(_LOCK_MESSAGE) from exc
    raise exc


def create_qdrant_client(config: KnowledgeOSConfig) -> QdrantClient:
    """Open the configured local Qdrant backend and verify server connectivity."""

    if config.qdrant_mode == "embedded":
        config.qdrant_dir.mkdir(parents=True, exist_ok=True)
        try:
            return QdrantClient(
                path=str(config.qdrant_dir),
                timeout=max(1, int(round(config.qdrant_timeout_seconds))),
            )
        except Exception as exc:
            _raise_useful_lock_error(exc)
            raise
    if config.qdrant_mode == "server":
        client: QdrantClient | None = None
        probe: QdrantClient | None = None
        try:
            probe = QdrantClient(
                url=config.qdrant_url,
                api_key=config.qdrant_api_key,
                timeout=max(
                    1,
                    int(round(config.qdrant_health_timeout_seconds)),
                ),
            )
            execute_qdrant_operation(
                config,
                "health",
                lambda timeout: probe.get_collections(),
            )
            probe.close()
            probe = None
            client = QdrantClient(
                url=config.qdrant_url,
                api_key=config.qdrant_api_key,
                timeout=max(1, int(round(config.qdrant_timeout_seconds))),
            )
        except Exception as exc:
            if probe is not None:
                probe.close()
            if client is not None:
                client.close()
            raise RuntimeError(
                _SERVER_ERROR_TEMPLATE.format(url=config.qdrant_url)
            ) from exc
        return client
    raise ValueError("Unsupported qdrant_mode")


def reset_qdrant_storage(config: KnowledgeOSConfig) -> None:
    """Delete the configured embedded store or server collection."""

    if config.qdrant_mode == "server":
        client = create_qdrant_client(config)
        try:
            exists = execute_qdrant_operation(
                config,
                "collection_exists",
                lambda timeout: client.collection_exists(
                    config.qdrant_collection_name
                ),
            )
            if exists:
                execute_qdrant_operation(
                    config,
                    "delete_collection",
                    lambda timeout: client.delete_collection(
                        config.qdrant_collection_name,
                        timeout=timeout,
                    ),
                )
        finally:
            client.close()
        return
    if config.qdrant_mode != "embedded":
        raise ValueError("Unsupported qdrant_mode")

    path = Path(config.qdrant_dir)
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
    except (OSError, PermissionError) as exc:
        _raise_useful_lock_error(exc)


def recreate_collection(
    client: QdrantClient, config: KnowledgeOSConfig, vector_size: int
) -> None:
    """Destructively recreate the collection when explicitly requested.

    Normal indexing should use :func:`ensure_collection` so reruns preserve the
    existing local collection and its points.
    """

    try:
        exists = execute_qdrant_operation(
            config,
            "collection_exists",
            lambda timeout: client.collection_exists(
                config.qdrant_collection_name
            ),
        )
        if exists:
            execute_qdrant_operation(
                config,
                "delete_collection",
                lambda timeout: client.delete_collection(
                    config.qdrant_collection_name,
                    timeout=timeout,
                ),
            )
        execute_qdrant_operation(
            config,
            "create_collection",
            lambda timeout: client.create_collection(
                collection_name=config.qdrant_collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE,
                ),
                timeout=timeout,
            ),
        )
    except Exception as exc:
        _raise_useful_lock_error(exc)


def _collection_vector_size(
    client: QdrantClient,
    collection_name: str,
    config: KnowledgeOSConfig,
) -> int:
    """Read the size of the collection's unnamed dense-vector configuration."""

    collection = execute_qdrant_operation(
        config,
        "get_collection",
        lambda timeout: client.get_collection(collection_name),
        collection=collection_name,
    )
    vectors = collection.config.params.vectors
    if isinstance(vectors, dict):
        raise ValueError(
            f"Qdrant collection '{collection_name}' uses named vectors, but this "
            "pipeline requires one unnamed dense vector."
        )
    return int(vectors.size)


def ensure_query_payload_indexes(
    client: QdrantClient,
    config: KnowledgeOSConfig,
) -> None:
    """Create keyword indexes used by authorization and replacement filters."""

    if config.qdrant_mode != "server":
        return
    collection_name = config.qdrant_collection_name
    collection = execute_qdrant_operation(
        config,
        "get_collection",
        lambda timeout: client.get_collection(collection_name),
        collection=collection_name,
    )
    existing = set((getattr(collection, "payload_schema", None) or {}).keys())
    for field_name, field_schema in _QUERY_PAYLOAD_INDEXES:
        if field_name in existing:
            continue
        execute_qdrant_operation(
            config,
            "create_payload_index",
            lambda timeout, field=field_name, schema=field_schema: client.create_payload_index(
                collection_name=collection_name,
                field_name=field,
                field_schema=schema,
                wait=True,
                timeout=timeout,
            ),
            collection=collection_name,
        )


def ensure_collection(
    client: QdrantClient, config: KnowledgeOSConfig, vector_size: int
) -> None:
    """Create the local collection once and validate it on later reruns.

    An existing collection is never recreated or deleted implicitly. A dimension
    mismatch is reported clearly because vectors from different embedding models
    cannot safely coexist in the same collection.
    """

    if vector_size <= 0:
        raise ValueError("Embedding vector size must be greater than zero.")
    collection_name = config.qdrant_collection_name
    try:
        exists = execute_qdrant_operation(
            config,
            "collection_exists",
            lambda timeout: client.collection_exists(collection_name),
            collection=collection_name,
        )
        if not exists:
            execute_qdrant_operation(
                config,
                "create_collection",
                lambda timeout: client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE,
                    ),
                    timeout=timeout,
                ),
                collection=collection_name,
            )
            ensure_query_payload_indexes(client, config)
            return

        existing_size = _collection_vector_size(client, collection_name, config)
        if existing_size != vector_size:
            raise ValueError(
                f"Qdrant collection '{collection_name}' expects vectors of size "
                f"{existing_size}, but the configured embedding model produces "
                f"{vector_size}. Use a different collection name or explicitly "
                "reset the vector store before changing embedding models."
            )
        ensure_query_payload_indexes(client, config)
    except Exception as exc:
        _raise_useful_lock_error(exc)


def _json_safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: str(value) if isinstance(value, Path) else value
        for key, value in metadata.items()
    }


def _stable_point_id(chunk: Document) -> str:
    """Return a deterministic Qdrant-compatible UUID for a chunk location."""

    metadata = chunk.metadata
    location_parts = (
        str(metadata.get("chunk_index", "")),
        str(metadata.get("start_index", "")),
        str(metadata.get("chunk_id", "")),
    )
    identity = "|".join(
        (
            str(metadata.get("repository_id", "")),
            str(metadata.get("source", "")),
            str(metadata.get("page_number", "")),
            *location_parts,
            # Public callers may supply unchunked Documents. Content prevents
            # those metadata-free points from all receiving the same UUID.
            "" if any(location_parts) else chunk.page_content,
        )
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


def index_chunks(
    client: QdrantClient,
    chunks: list[Document],
    embeddings: np.ndarray,
    config: KnowledgeOSConfig,
    *,
    execution_manager: Any | None = None,
) -> None:
    """Idempotently upsert chunk text, vectors, and metadata into local Qdrant."""

    if len(chunks) != len(embeddings):
        raise ValueError(
            f"Chunk/embedding count mismatch: {len(chunks)} chunks and "
            f"{len(embeddings)} embeddings."
        )
    if embeddings.ndim != 2:
        raise ValueError(
            f"Embeddings must be a 2D array; received shape {embeddings.shape}."
        )
    expected_size = _collection_vector_size(
        client,
        config.qdrant_collection_name,
        config,
    )
    actual_size = int(embeddings.shape[1])
    if actual_size != expected_size:
        raise ValueError(
            f"Embedding vectors have size {actual_size}, but Qdrant collection "
            f"'{config.qdrant_collection_name}' expects size {expected_size}."
        )
    if not chunks:
        return
    # Managed chunks must satisfy the same contract at the final payload
    # boundary; metadata-free notebook/test documents retain legacy support.
    from backend.app.services.chunk_metadata_contract import ChunkMetadataContractError, validate_chunk_metadata
    require_contract = bool(getattr(config, "require_authorization_metadata", False))
    for chunk in chunks:
        if require_contract or "storage_scope" in chunk.metadata or "workspace_id" in chunk.metadata:
            validation = validate_chunk_metadata(chunk.metadata)
            if not validation.valid:
                raise ChunkMetadataContractError(validation)

    batch_size = config.qdrant_batch_size
    total_points = len(chunks)
    total_batches = (total_points + batch_size - 1) // batch_size
    started_at = time.perf_counter()
    for batch_index, start in enumerate(
        range(0, total_points, batch_size),
        start=1,
    ):
        end = min(start + batch_size, total_points)
        points = [
            PointStruct(
                id=_stable_point_id(chunk),
                vector=np.asarray(vector, dtype=float).tolist(),
                payload={
                    "text": chunk.page_content,
                    "metadata": _json_safe_metadata(dict(chunk.metadata)),
                },
            )
            for chunk, vector in zip(
                chunks[start:end],
                embeddings[start:end],
                strict=True,
            )
        ]
        try:
            result = execute_qdrant_operation(
                config,
                "upsert",
                lambda timeout: client.upsert(
                    collection_name=config.qdrant_collection_name,
                    points=points,
                    wait=config.qdrant_upsert_wait,
                    timeout=timeout,
                ),
                affected_count=len(points),
            )
            if not _update_completed(result):
                raise RuntimeError("Qdrant upsert did not complete successfully.")
        except Exception as exc:
            _raise_useful_lock_error(exc)
        elapsed = time.perf_counter() - started_at
        remaining_batches = total_batches - batch_index
        estimated_remaining_seconds = (
            elapsed / batch_index * remaining_batches
            if batch_index and remaining_batches
            else 0.0
        )
        logger.info(
            "qdrant_upsert_batch_complete",
            extra={
                "event": "qdrant_upsert",
                "collection_name": config.qdrant_collection_name,
                "qdrant_mode": config.qdrant_mode,
                "batch_index": batch_index,
                "total_batches": total_batches,
                "batch_points": len(points),
                "indexed_points": end,
                "total_points": total_points,
                "elapsed_seconds": round(elapsed, 3),
                "remaining_batches": remaining_batches,
                "estimated_remaining_seconds": round(
                    estimated_remaining_seconds,
                    3,
                ),
            },
        )
        if execution_manager is not None:
            execution_manager.emit(
                "indexing_progress",
                stage="qdrant_upsert",
                status="running",
                elapsed_seconds=elapsed,
                metrics={
                    "qdrant_upsert_latency_seconds": elapsed,
                },
                payload={
                    "collection_name": config.qdrant_collection_name,
                    "qdrant_mode": config.qdrant_mode,
                    "batch_index": batch_index,
                    "total_batches": total_batches,
                    "batch_size": batch_size,
                    "points_upserted": end,
                    "total_points": total_points,
                    "eta_seconds": estimated_remaining_seconds,
                },
                source="vectorstore.index_chunks",
            )
        points = []


def load_document_chunks(
    client: QdrantClient,
    config: KnowledgeOSConfig,
    *,
    document_id: str,
    document_version_id: str | None = None,
) -> list[tuple[str, Document]]:
    """Load only one document/version from Qdrant for targeted verification."""
    must = [FieldCondition(key="metadata.document_id", match=MatchValue(value=document_id))]
    if document_version_id is not None:
        must.append(FieldCondition(key="metadata.document_version_id", match=MatchValue(value=document_version_id)))
    records: list[tuple[str, Document]] = []
    offset: Any | None = None
    while True:
        logger.info(
            "qdrant_scroll_usage",
            extra={
                "event": "qdrant_scroll_usage",
                "collection": config.qdrant_collection_name,
                "limit": 256,
                "purpose": "target_document_version_verification",
            },
        )
        points, offset = execute_qdrant_operation(
            config,
            "scroll",
            lambda timeout: client.scroll(
                collection_name=config.qdrant_collection_name,
                scroll_filter=Filter(must=must),
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
                timeout=timeout,
            ),
        )
        for point in points:
            payload = point.payload or {}
            records.append((str(point.id), Document(
                page_content=str(payload.get("text", "")), metadata=dict(payload.get("metadata") or {}),
            )))
        if offset is None:
            break
    return records


def replace_document_chunks(
    client: QdrantClient,
    chunks: list[Document],
    embeddings: np.ndarray,
    config: KnowledgeOSConfig,
    *,
    document_id: str,
    document_version_id: str,
    execution_manager: Any | None = None,
) -> int:
    """Replace one document version with native filtered deletion and verification."""

    started = time.perf_counter()
    query_filter = Filter(
        must=[
            FieldCondition(
                key="metadata.document_id",
                match=MatchValue(value=document_id),
            ),
            FieldCondition(
                key="metadata.document_version_id",
                match=MatchValue(value=document_version_id),
            ),
        ]
    )
    count_result = execute_qdrant_operation(
        config,
        "count",
        lambda timeout: client.count(
            collection_name=config.qdrant_collection_name,
            count_filter=query_filter,
            exact=True,
            timeout=timeout,
        ),
    )
    deleted_count = int(count_result.count)
    delete_result = execute_qdrant_operation(
        config,
        "delete",
        lambda timeout: client.delete(
            collection_name=config.qdrant_collection_name,
            points_selector=FilterSelector(filter=query_filter),
            wait=True,
            timeout=timeout,
        ),
        affected_count=deleted_count,
    )
    if not _update_completed(delete_result):
        raise RuntimeError("Qdrant filtered delete did not complete successfully.")

    expected_ids = [_stable_point_id(chunk) for chunk in chunks]
    if len(set(expected_ids)) != len(expected_ids):
        raise ValueError("Replacement chunks produced duplicate Qdrant point ids.")
    index_chunks(client, chunks, embeddings, config, execution_manager=execution_manager)

    verified_count = int(
        execute_qdrant_operation(
            config,
            "count",
            lambda timeout: client.count(
                collection_name=config.qdrant_collection_name,
                count_filter=query_filter,
                exact=True,
                timeout=timeout,
            ),
        ).count
    )
    if verified_count != len(chunks):
        raise RuntimeError(
            "Qdrant replacement verification failed: "
            f"expected {len(chunks)} points, found {verified_count}."
        )
    records = (
        execute_qdrant_operation(
            config,
            "retrieve",
            lambda timeout: client.retrieve(
                collection_name=config.qdrant_collection_name,
                ids=expected_ids,
                with_payload=True,
                with_vectors=False,
                timeout=timeout,
            ),
            affected_count=len(expected_ids),
        )
        if expected_ids
        else []
    )
    if len(records) != len(expected_ids):
        raise RuntimeError("Qdrant replacement verification could not retrieve all points.")
    for record in records:
        metadata = dict((record.payload or {}).get("metadata") or {})
        if (
            str(metadata.get("document_id")) != document_id
            or str(metadata.get("document_version_id")) != document_version_id
        ):
            raise RuntimeError("Qdrant replacement verification found mismatched metadata.")
    logger.info(
        "document_chunk_replacement_verified",
        extra={
            "event": "document_chunk_replacement_verified",
            "document_id": document_id,
            "document_version_id": document_version_id,
            "chunks_deleted": deleted_count,
            "chunks_inserted": len(chunks),
            "duration_ms": int((time.perf_counter() - started) * 1000),
        },
    )
    return deleted_count


def _document_filter(
    *,
    document_id: str | None = None,
    relative_path: str | None = None,
    repository_id: str | None = None,
) -> Filter:
    conditions = []
    must_conditions = []
    if repository_id:
        must_conditions.append(
            FieldCondition(
                key="metadata.repository_id",
                match=MatchValue(value=repository_id),
            )
        )
    if document_id:
        conditions.append(
            FieldCondition(
                key="metadata.document_id",
                match=MatchValue(value=document_id),
            )
        )
    if relative_path:
        conditions.append(
            FieldCondition(
                key="metadata.relative_path",
                match=MatchValue(value=relative_path),
            )
        )
    if not conditions:
        raise ValueError("document_id or relative_path is required.")
    return Filter(must=must_conditions or None, should=conditions)


def delete_document_chunks(
    client: QdrantClient,
    config: KnowledgeOSConfig,
    *,
    document_id: str | None = None,
    relative_path: str | None = None,
) -> int:
    """Delete and return the number of points belonging to one document."""

    exists = execute_qdrant_operation(
        config,
        "collection_exists",
        lambda timeout: client.collection_exists(
            config.qdrant_collection_name
        ),
    )
    if not exists:
        return 0
    query_filter = _document_filter(
        document_id=document_id,
        relative_path=relative_path,
        repository_id=getattr(config, "repository_id", None),
    )
    try:
        removed = int(
            execute_qdrant_operation(
                config,
                "count",
                lambda timeout: client.count(
                    collection_name=config.qdrant_collection_name,
                    count_filter=query_filter,
                    exact=True,
                    timeout=timeout,
                ),
            ).count
        )
        result = execute_qdrant_operation(
            config,
            "delete",
            lambda timeout: client.delete(
                collection_name=config.qdrant_collection_name,
                points_selector=FilterSelector(filter=query_filter),
                wait=True,
                timeout=timeout,
            ),
            affected_count=removed,
        )
        if not _update_completed(result):
            raise RuntimeError("Qdrant filtered delete did not complete successfully.")
        return removed
    except Exception as exc:
        _raise_useful_lock_error(exc)
        raise


def delete_stale_document_versions(
    client: QdrantClient,
    config: KnowledgeOSConfig,
    *,
    document_id: str,
    keep_document_version_id: str,
) -> int:
    """Delete older versions only after the caller verified the new version."""

    query_filter = Filter(
        must=[
            FieldCondition(
                key="metadata.document_id",
                match=MatchValue(value=document_id),
            )
        ],
        must_not=[
            FieldCondition(
                key="metadata.document_version_id",
                match=MatchValue(value=keep_document_version_id),
            )
        ],
    )
    removed = int(
        execute_qdrant_operation(
            config,
            "count",
            lambda timeout: client.count(
                collection_name=config.qdrant_collection_name,
                count_filter=query_filter,
                exact=True,
                timeout=timeout,
            ),
        ).count
    )
    if removed:
        result = execute_qdrant_operation(
            config,
            "delete",
            lambda timeout: client.delete(
                collection_name=config.qdrant_collection_name,
                points_selector=FilterSelector(filter=query_filter),
                wait=True,
                timeout=timeout,
            ),
            affected_count=removed,
        )
        if not _update_completed(result):
            raise RuntimeError("Qdrant stale-version cleanup did not complete.")
    return removed


def delete_document_version(
    client: QdrantClient,
    config: KnowledgeOSConfig,
    *,
    document_id: str,
    document_version_id: str,
) -> int:
    """Delete one exact version with a native payload filter and no scroll."""

    query_filter = Filter(
        must=[
            FieldCondition(
                key="metadata.document_id",
                match=MatchValue(value=document_id),
            ),
            FieldCondition(
                key="metadata.document_version_id",
                match=MatchValue(value=document_version_id),
            ),
        ]
    )
    removed = int(
        execute_qdrant_operation(
            config,
            "count",
            lambda timeout: client.count(
                collection_name=config.qdrant_collection_name,
                count_filter=query_filter,
                exact=True,
                timeout=timeout,
            ),
        ).count
    )
    if removed:
        result = execute_qdrant_operation(
            config,
            "delete",
            lambda timeout: client.delete(
                collection_name=config.qdrant_collection_name,
                points_selector=FilterSelector(filter=query_filter),
                wait=True,
                timeout=timeout,
            ),
            affected_count=removed,
        )
        if not _update_completed(result):
            raise RuntimeError("Qdrant exact-version cleanup did not complete.")
    return removed


def load_indexed_chunks(
    client: QdrantClient,
    config: KnowledgeOSConfig,
) -> list[Document]:
    """Read the complete stored chunk corpus for BM25 and notebook inspection."""

    exists = execute_qdrant_operation(
        config,
        "collection_exists",
        lambda timeout: client.collection_exists(
            config.qdrant_collection_name
        ),
    )
    if not exists:
        return []
    chunks: list[Document] = []
    offset: Any | None = None
    try:
        while True:
            query_filter = None
            repository_id = getattr(config, "repository_id", None)
            if repository_id:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="metadata.repository_id",
                            match=MatchValue(value=repository_id),
                        )
                    ]
                )
            logger.info(
                "qdrant_scroll_usage",
                extra={
                    "event": "qdrant_scroll_usage",
                    "collection": config.qdrant_collection_name,
                    "limit": 256,
                    "purpose": "bm25_index_reconstruction",
                },
            )
            points, offset = execute_qdrant_operation(
                config,
                "scroll",
                lambda timeout: client.scroll(
                    collection_name=config.qdrant_collection_name,
                    limit=256,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                    scroll_filter=query_filter,
                    timeout=timeout,
                ),
            )
            for point in points:
                payload = point.payload or {}
                chunks.append(
                    Document(
                        page_content=str(payload.get("text", "")),
                        metadata=dict(payload.get("metadata") or {}),
                    )
                )
            if offset is None:
                break
    except Exception as exc:
        _raise_useful_lock_error(exc)
        raise
    return chunks
