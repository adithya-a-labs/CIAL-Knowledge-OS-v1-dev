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
- deep runtime wiring is deferred to keep retrieval stable

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
