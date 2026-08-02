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

BM25 lifecycle and query telemetry is sourced from the loaded publication:

- `bm25_runtime_state`, `bm25_status`: whether the in-memory publication is
  ready;
- `bm25_snapshot_version`: active published generation;
- `bm25_loaded_at` and `bm25_load_duration_ms`: authoritative activation time
  and measured load duration;
- `bm25_snapshot_loaded_at`: UTC activation timestamp;
- `bm25_snapshot_size`: actual published snapshot size in bytes;
- `bm25_snapshot_load_duration_ms`: measured JSON snapshot load time;
- `bm25_index_activation_duration_ms`: measured in-memory index/posting
  activation time;
- `bm25_document_count` and `bm25_chunk_count`: counts from the active snapshot;
- `bm25_search_duration_ms`: measured lexical request duration; and
- `bm25_candidate_count`: candidates actually returned by lexical retrieval.

The same search metrics are attached to the `bm25_retrieval` completion event
and projected by the administrator monitor. Missing measurements remain null;
the monitor does not synthesize values.

Hybrid retrieval additionally emits `parallel_retrieval` start/completion
telemetry with `dense_started`, `dense_completed`, `bm25_started`,
`bm25_completed`, and `parallel_retrieval_duration_ms`. Branch duration uses
the worker's actual completion timestamp, not the later collection timestamp.
The ordinary dense/BM25 stage events and candidate counts remain present.

Reranking completion reports `reranker_device`, `reranker_dtype`,
`reranker_model_loaded`, real PyTorch allocated/load-delta bytes,
`reranker_batch_size`, `reranker_candidate_count`, and
`reranker_latency_ms`. One `predict()` receives the full ordered candidate
batch; telemetry does not imply one model invocation per candidate. Readiness
also exposes `dense_model_status`, `reranker_status`, and `bm25_status`.

Normal performance objectives are permission validation below 100 ms, Qdrant
below 500 ms, fusion below 200 ms, reranking below 2 seconds, and retrieval
before generation below 3 seconds. Component deadlines are failure ceilings,
not performance targets. The BM25 search objective is below 100 ms. Qdrant
authorization keys are keyword-indexed, while BM25 uses the in-memory published
snapshot, a published posting map, and a bounded cache of authorization-to-chunk
index mappings. Neither retrieval branch reads source corpus files. BM25 query
terms access only their posting lists and therefore do not scan the full
published chunk corpus. Permission
resolution projects only indexed documents' relative paths through the existing
PostgreSQL RBAC predicates instead of hydrating complete document rows. Dense
filters also include the document versions and note revisions in the loaded
publication, preventing in-progress Qdrant points from leaking into results.
Large authorized path and published-version sets use Qdrant `MatchAny` filters;
all live filter keys retain payload indexes. Authorization-scoped candidate
depth and any selected-scope reranker expansion are bounded at 250.
BM25 reuses the single published BM25 model and its posting lists. The bounded
authorization cache stores only integer chunk-index arrays; it never contains
or constructs another BM25 model.

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
   loaded, compare snapshot load/activation telemetry separately from search
   duration, and verify that no query-time build was attempted.
5. Confirm the NDJSON terminal result/error identifies the same failed stage
   and that a degraded success contains only the documented safe fallback.

The regression fixed on 2026-07-25 occurred at step 2: the service entered
batch `run()` before the instrumented retrieval call. Because the production
pipeline intentionally does not retain source `documents` or corpus
`embeddings`, `run()` began corpus loading and whole-snapshot embedding. The
query-only call boundary removes that work from chat without changing the
retrieval, authorization, indexing, citation, or prompt algorithms.

The BM25 regression investigated on 2026-07-26 had two measured query-path
causes. An unseen authorization scope built a new `BM25Okapi` over authorized
chunks (15,626 ms for the generation-29 broad scope), and subsequent searches
called the library's full-corpus score loop plus full result sort (roughly
828-911 ms after removing only the rebuild). The corrected request path scores
only prebuilt query-term postings from the already-loaded publication, applies
authorized chunk indexes, and partially selects top candidates. On the same
459,715-chunk snapshot, measured searches were 2.48-11.15 ms. Snapshot load
(17,194 ms) and activation (35,725 ms) remain observable startup/background
refresh work rather than search latency.

Phase 1 performance validation on the same generation retained all configured
candidate and evidence counts. With dense/BM25 running concurrently and the
dense/reranker inference paths initialized before readiness, the warm repeated
retrieval measured 1,919 ms end to end. Component measurements were 81 ms
parallel retrieval, 30.5 ms internal BM25 search, 2 ms fusion, 38 ms batched
CUDA reranking of 28 candidates, and 7 ms evidence selection. A first
post-start probe measured 2,103 ms. These are measured workstation results,
not universal latency guarantees.

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

Generation timing uses one unit and explicit clock boundaries:

- the adapter and API use monotonic `perf_counter()` timestamps for local
  elapsed time;
- `first_token_ms` is the first non-empty streamed-token timestamp minus the
  generation-start timestamp;
- `generation_latency_ms` is the API generation-completion timestamp minus its
  matching generation-start timestamp;
- `model_load_ms`, `prompt_eval_ms`, and `ollama_total_ms` are Ollama's native
  nanosecond durations converted once to milliseconds; Ollama's
  `load_duration` is the runtime's model-ready minus model-load-start interval;
- `tokens_per_second` is Ollama's output-token count divided by its positive
  evaluation duration in seconds.

The adapter clears prior metrics before every request. Completion telemetry is
accepted only when finite and non-negative. First-token, model-load,
prompt-evaluation, and Ollama-total durations cannot exceed the API-measured
generation or request duration. Invalid, stale, missing, negative, non-finite,
or unit-inconsistent values are omitted and rendered as `Unavailable`; no
fallback timestamp or fabricated zero is displayed. The 1,758,803 ms
first-token observation was rejected because it exceeded the corresponding
24,179 ms generation boundary.

GPU samples run asynchronously at generation boundaries so telemetry cannot
delay the answer path. Samples include total utilization and VRAM plus bounded
active CUDA process IDs classified as Ollama, Python, or other. Indexer
heartbeats separately report active embedding jobs, embedding queue depth, GPU
residency/state, chat-priority waits, and process-local allocation/reservation.
Driver-unavailable values remain unavailable rather than inferred.

## Standalone Embedding GPU Telemetry

The indexer heartbeat and administrator monitor expose real measurements from
the standalone process:

- configured and actual embedding device;
- embedding model state and current GPU residency;
- PyTorch version, CUDA build/availability, CUDA device name, and model dtype;
- process-local allocated/reserved CUDA memory;
- total device utilization and used/total VRAM from `nvidia-smi`;
- active adaptive batch size, last batch size/device/duration, and allocated
  memory before/after `model.encode()`; and
- chunks/minute plus measured batch throughput.

`embedding_runtime_initialized`, `embedding_device_mismatch`,
`embedding_batch_started`, and `embedding_batch_completed` are content-free.
They contain no source text, vectors, paths, credentials, or workspace/user
identifiers. CPU extraction and Qdrant/network activity do not emit synthetic
GPU utilization. An idle-released model reports actual device `cpu` and
resident `false`; the next real batch must report `cuda:<index>` before encode
when CUDA is available.

## Phase 2 Query Infrastructure Telemetry

The dense branch exposes two nested measured stages:

1. `query_embedding` records `query_embedding_started`,
   `query_embedding_completed`, `query_embedding_duration_ms`, actual device,
   actual parameter dtype, warmed/loaded model state, and
   `query_embedding_cache_status=model_reused`.
2. `qdrant_search` records `qdrant_index_status`,
   `qdrant_search_latency_ms`, and the exact payload field names present in the
   unchanged query filter.

Both durations use `perf_counter()` within their own boundaries. Qdrant's
Python query response does not provide a separate server-side filter duration,
so `qdrant_filter_latency_ms` is null. It must not be inferred by subtracting
embedding time or transport time.

The `retrieval_cache` stage reports mutually exclusive hit/miss flags, measured
lookup latency, current bounded entry count, and the last applicable
invalidation reason. Cache entries contain candidate ids, text/document data,
scores, metadata, modality rankings, active generation, and UTC creation time.
They contain no prompts, generated answer, or generation metrics.

On a miss, dense Qdrant and BM25 run concurrently and unchanged, then the fused
result is stored. On a hit, those stored fused candidates are defensively
copied in their original order and processing resumes at the unchanged
reranker. Thus a hit must show no new dense/BM25 work but must still show real
reranking, evidence selection, context, citation, and generation telemetry.

Cache security is fail-closed at key construction:

- `normalized_query_hash` contains no raw question;
- `published_generation` prevents cross-publication reuse;
- `workspace_scope` fingerprints access scope, effective authorized paths, and
  explicitly selected documents/folders/notes; and
- `permission_boundary` fingerprints the resolved principal and current
  organization, role, permission, department, and group grants.

A generation change clears the cache. A permission-boundary change evicts all
entries belonging to that principal before lookup. Different scopes or
authorized path sets generate different keys and cannot collide at lookup.

## LAN Edge Observability

The LAN manager writes bounded structured lifecycle events and Caddy writes
rotating access records with request headers and URIs removed. The backend
projects only a sanitized `lan_access` health object; it excludes secrets,
tokens, cookies, MAC addresses, repository paths, and hotspot credentials.
Gateway or discovery degradation is non-critical to retrieval health and does
not alter retrieval tracing, authorization, or cache keys.

## Device placement telemetry

Authenticated status now distinguishes requested and resolved device, dtype,
model-load count, and bounded fallback reason for query embedding and
reranking. GPU telemetry adds device name, driver, and used/free/total VRAM.
The measured production choice is CPU for query BGE-M3 and CUDA for the small
reranker; benchmark and contention evidence are in
`GPU_WORKLOAD_PLACEMENT.md`. These fields remain content-free and do not expose
questions, documents, paths, credentials, or raw process command lines.
