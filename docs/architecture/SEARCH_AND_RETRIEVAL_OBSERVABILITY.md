# Search And Retrieval Observability

## Purpose

The PostgreSQL schema now includes lightweight control-plane tables that support future search quality work without changing the current Qdrant-centric retrieval path.

These additions do not rewrite retrieval. They create durable metadata surfaces that can be populated incrementally.

## Document Search Metadata

`document_search_metadata` exists so search-oriented attributes do not have to be forced into vector payloads or overloaded onto the main `documents` table.

It stores:

- `document_id`
- `organization_id`
- `title`
- `normalized_title`
- `summary`
- `keywords`
- `entities`
- `topics`
- `language`
- `ocr_quality`
- `classification`
- `metadata`

Backfill behavior:

- `title` comes from the existing document name
- `organization_id` comes from the document row
- `normalized_title` is a simple lowercase normalized form
- summary and enrichment fields start empty when unavailable

The unique constraint on `document_id` guarantees one metadata row per document and serves as the primary lookup index.

## Document Relationships

`document_relationships` stores explicit graph edges between documents, including:

- `related`
- `references`
- `supersedes`
- `duplicate`
- `derived_from`
- `translation_of`
- `attachment_of`

This is intended for future cross-document navigation, deduplication hints, lineage, and metadata search. It is not yet populated automatically by the runtime.

## Retrieval Events

`retrieval_events` is a telemetry table for future RAG quality analysis. It can capture:

- the query text
- selected document and folder scope
- retrieved documents and chunks
- reranker outputs
- applied filters
- latency
- result count

Current decision:

- the table exists now
- durable per-query writes remain deferred to keep retrieval stable
- live structured timing and the safe debug snapshot are implemented

## Conversation Summaries

`conversation_summaries` provides a durable place for:

- running summaries
- final summaries
- topic summaries
- handoff summaries

This supports future long-thread memory and handoff workflows without changing the current chat execution path today.

## Deferred Wiring

The following are intentionally deferred:

- automatic enrichment of search metadata during indexing
- automatic relationship extraction
- retrieval event writes during production RAG calls
- conversation summary generation during chat sessions

The schema is ready for those additions when the service contracts are defined.

## Continuous Indexing Observability

Indexing observability is separate from per-chat `retrieval_events`.
`GET /api/index/status` reads durable worker heartbeats, reconciliation state,
queue counts by state/operation, last completion, dense/BM25 generations,
actual embedding device, internal queue depths, and safe throughput data.
Structured logs cover watcher stability, leases, stage changes, cross-asset
batch composition, Qdrant verification, stale cleanup, and BM25 swap. Bodies,
embeddings, prompt text, credentials, and absolute personal paths are excluded.

`GET /api/indexer/status` is an additive alias. Heartbeat metrics include
system/process CPU utilization, logical cores, documents/hour, chunks/minute,
the adaptive embedding limit, assigned-device GPU utilization, and GPU memory.

## Live Chat Pipeline Telemetry

Every chat request has an opaque request id and emits structured, content-free
events for:

- `request_received`
- `permission_validation_completed`
- `index_generation_loaded`
- `dense_retrieval_started/completed`
- `bm25_started/completed`
- `hybrid_fusion_started/completed`
- `reranking_started/completed`
- `generation_started/completed`
- `chat_completed` or `chat_failed`

Completed and failed events include `duration_ms`. Dense/BM25/fusion events
include candidate counts; reranking includes the resolved device, bounded
candidate count, and latency. Logs exclude questions, prompts, evidence bodies,
document paths, credentials, and unrestricted exception content.

Authenticated `GET /api/chat/debug` exposes the loaded dense/BM25 generation,
whether a publication refresh or index update is running, the safe queue
summary, and the last request's retrieval, Qdrant, BM25, fusion, reranker,
generation, and total latencies. It is an operational snapshot, not a query log,
and never includes prompt or document content.

Normal performance objectives are permission validation below 100 ms, Qdrant
below 500 ms, fusion below 200 ms, reranking below 2 seconds, and retrieval
before generation below 3 seconds. Component deadlines are failure ceilings,
not performance targets. Qdrant authorization keys are keyword-indexed, BM25
uses the in-memory published snapshot plus a bounded authorization-index cache,
and neither retrieval branch reads or scans source corpus files. Permission
resolution projects only indexed documents' relative paths through the existing
PostgreSQL RBAC predicates instead of hydrating complete document rows. Dense
filters also include the document versions and note revisions in the loaded
publication, preventing in-progress Qdrant points from leaking into results.

## Live System Status

Authenticated `GET /api/system/status` complements request-level chat debug
telemetry with current dependency telemetry. PostgreSQL and queue checks use
their real stores; Qdrant checks the configured collection with a bounded
request; Ollama checks `/api/tags` for the exact configured model; embedding
readiness and loaded generation come from the live query runtime; worker,
queue, publication and GPU data come from PostgreSQL heartbeats/generations.
Independent Qdrant and Ollama probes run concurrently and have hard timeouts.

The response provides safe per-component availability, detail, check timestamp
and latency plus total latency. Structured `health_check_completed` events
(`telemetry_type=system_status_snapshot`)
record only color, chat availability, indexing activity, generation, queue
depth and duration. Component failures log the component and exception type,
never URLs with secrets, credentials, document content, prompts, or raw
exception messages.
