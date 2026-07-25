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
- `evidence_selection_started/completed`
- `generation_started/completed`
- `chat_completed` or `chat_failed`

Every stage event carries request id, optional conversation id, stage, status,
UTC timestamp, `duration_ms`, `candidate_count`, `error_state`, and
`timeout_state`. A timed-out stage completes with its timeout error state so a
successful partial response remains observable. Reranking also includes the
resolved device and bounded candidate count. Logs exclude questions, prompts,
evidence bodies, document paths, credentials, and unrestricted exception
content.

Authenticated `GET /api/chat/debug` exposes the loaded dense/BM25 generation,
whether a publication refresh or index update is running, the safe queue
summary, current stage and elapsed stage time, exact failed stage/timeout
reason, and the last request's retrieval, Qdrant, BM25, fusion, reranker,
generation, and total latencies. It is an operational snapshot, not a query
log, and never includes prompt or document content.

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
Large authorized path and published-version sets use Qdrant `MatchAny` filters;
all live filter keys retain payload indexes. Authorization-scoped candidate
depth and any selected-scope reranker expansion are bounded at 250.
BM25 reuses published corpus tokens and a lock-protected bounded authorized
sub-index cache rather than retokenizing or rebuilding the corpus per query.

Hard failure ceilings are dense/Qdrant 30 seconds, BM25 10 seconds, fusion
5 seconds, reranking 15 seconds, and evidence selection 5 seconds. Dense/BM25
timeouts preserve the surviving authorized branch; fusion uses stable
available-branch order; reranker uses the fused order; evidence timeout
selects no evidence. The response trace, NDJSON stream, chat debug endpoint,
and administrator monitor all expose the failed component.

### Retrieval debugging workflow

1. Follow one opaque request id from `request_received` through
   `retrieval_started` and the component start/completion pairs.
2. If no component start follows retrieval entry, verify that the live service
   calls the loaded pipeline's `answer()` method, never the batch `run()`
   lifecycle.
3. Compare `/api/chat/debug` current stage and duration with the administrator
   monitor's current/failed stage and timeout reason.
4. For dense failures, inspect the bounded Qdrant call and indexed filter keys;
   for lexical failures, verify that the active published BM25 generation is
   loaded and no query-time build was attempted.
5. Confirm the NDJSON terminal result/error identifies the same failed stage
   and that a degraded success contains only the documented safe fallback.

The regression fixed on 2026-07-25 occurred at step 2: the service entered
batch `run()` before the instrumented retrieval call. Because the production
pipeline intentionally does not retain source `documents` or corpus
`embeddings`, `run()` began corpus loading and whole-snapshot embedding. The
query-only call boundary removes that work from chat without changing the
retrieval, authorization, indexing, citation, or prompt algorithms.

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

## Admin Operations Stream

The authenticated assistant status remains the user-facing availability
contract. Administrators additionally receive the restricted
`/api/admin/system/monitor` snapshot and `/api/admin/system/stream` SSE feed.
Both require `monitor_system` or `manage_settings`; authentication alone is
insufficient.

The query section reports the number of requests currently inside the actual
chat route lifecycle, current stage and live stage duration, the exact failed
stage/timeout reason, and the latest validation, retrieval, reranking,
generation, and total timings already recorded by the query engine.
`chat_started`, `chat_completed`, `retrieval_stage_failed`, and
`retrieval_failed` are emitted at those real lifecycle boundaries. A later
chat-level error does not overwrite the component that failed. No question,
prompt, answer, evidence, user id, or workspace id is included.

Indexing events are state-transition projections over durable queue and
publication telemetry. Supported types include `document_detected`,
`extraction_started`, `extraction_completed`, `chunking_completed`,
`embedding_started`, `embedding_batch_completed`,
`qdrant_write_completed`, `generation_published`, `worker_started`, and
`worker_failed`. `service_failed` identifies a component and exception type
only. A bounded in-process event buffer supports the live console; PostgreSQL
job/history tables remain the durable source of truth.

## Generation And GPU Performance Telemetry

Generation completion/failure events additionally carry content-free workload
and runtime measurements: prompt, context, system-instruction and output token
counts; first-token latency; tokens per second; Ollama model-load,
prompt-evaluation and total duration; retry count; and effective keep-alive.
Generation deadlines retain `error_state=generation_timeout` rather than being
collapsed to the outer wrapper failure.

GPU samples run asynchronously at generation boundaries so telemetry cannot
delay the answer path. Samples include total utilization and VRAM plus bounded
active CUDA process IDs classified as Ollama, Python, or other. Indexer
heartbeats separately report active embedding jobs, embedding queue depth, GPU
residency/state, chat-priority waits, and process-local allocation/reservation.
Driver-unavailable values remain unavailable rather than inferred.
