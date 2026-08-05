# Bounded multi-request chat architecture

Status: implemented and verified on 2026-07-30. Runtime evidence and known
limits are recorded in
`docs/verification/MULTI_REQUEST_CHAT_VERIFICATION.md`.

## Scope and invariants

CIAL chat remains a live FastAPI request/NDJSON stream. It is not a durable
background job and does not use `indexing_jobs`. The four existing runtime
commands remain infrastructure, one FastAPI query process, one standalone
indexer process, and one React/Vite frontend. No chat worker process, broker, or
additional Uvicorn worker is introduced.

Completed PostgreSQL history remains authoritative. Under the existing live
stream contract, a backend restart, full browser reload, or network disconnect
cancels in-flight work; it does not resume it. A cancelled or failed turn
persists neither the user message nor a partial assistant message.

The following existing contracts remain unchanged:

- HttpOnly-cookie authentication and request-time RBAC;
- query-only use of the loaded Qdrant/BM25 publication;
- Phase 4.5 retrieval, RRF, evidence, prompt, citation, and profile behavior;
- NDJSON `stage`, `token`, `result`, `error`, and `cancelled` event types;
- `chat_available` readiness independent of an active indexing queue;
- document preview/deep-link behavior and Light/System/Dark presentation.

## Verified current bottlenecks

The pre-change audit proved these single-flight and isolation hazards:

- `POST /api/chat/stream` creates an unbounded `queue.Queue` and one daemon
  thread for every accepted request.
- `KnowledgeEngineService.answer_question` holds `_query_lock` across loaded
  retrieval, reranking, evidence selection, generation, and callback cleanup.
- `_ready_pipeline` mutates the shared `pipeline.config`; the answer path also
  assigns shared token, cancellation, telemetry, retrieval-cache, selected-path,
  and `_search` state.
- BM25 authorization state and Phase 3/4 `last_*` result fields are mutable on
  the shared pipeline.
- the GPU priority marker is owned by one request id, so one overlapping
  request can remove another request's lease.
- `ChatPanel` has one `isLoading`, one submission guard, one abort controller,
  one request id, one token buffer, and one event list.
- history is ordered only by `chat_messages.created_at`, which reflects
  completion-time insertion and cannot preserve turn submission order when B
  completes before A.

## Target process and request flow

The implemented request flow is:

1. authenticate and resolve the immutable access context;
2. validate session ownership and selected document/folder/note scope;
3. reserve bounded global and per-user outstanding capacity;
4. assign opaque server request id, client correlation id, deadline, and
   submission sequence;
5. register only content-free live state;
6. open the compatible NDJSON response immediately;
7. enqueue in a per-user FIFO queue selected round-robin across users;
8. dispatch within global and per-user active limits;
9. acquire an immutable loaded-query-runtime reader lease;
10. execute a request-local Phase 4.5 query view over shared read-only model,
    Qdrant client, and publication resources;
11. pass fair query-embedding, reranker, and generation gates at their actual
    resource boundaries;
12. persist the user/assistant pair transactionally with submission ordering;
13. emit one canonical result and release every lease in `finally`.

## Request state and binding boundaries

The request binding contains request id, authenticated internal
principal key, organization, session id, client correlation id, submitted
sequence/time, copied `ChatRequest`, copied effective profile/config, authorized
scope fingerprint, selected ids and effective relative paths, publication
handle, monotonic deadline, cancellation event, progress/token callbacks, and
request-local cache functions.

The process-local registry must not retain question, prompt, evidence, answer,
document names, paths, email, cookies, or credentials. A live record contains
only ids already permitted for internal structured logging, lifecycle state,
monotonic timestamps, safe error code, visible-token flag, bounded queue,
future, and cleanup state. Terminal records are removed immediately after
cleanup.

Lifecycle states are `accepted`, `queued`, `validating`,
`loading_published_generation`, `waiting_for_query_embedding`, `searching`,
`waiting_for_reranker`, `reranking`, `selecting_evidence`,
`waiting_for_generation`, `generating`, `persisting`, `completed`,
`cancelled`, `timed_out`, and `failed`.

## Admission, scheduling, and backpressure

The controller owns a fixed worker pool and an explicitly bounded
admission queue. It does not rely on `ThreadPoolExecutor`'s internal unbounded
queue for admission. FIFO is preserved within a user; eligible users are
selected round-robin. A user's active count is limited independently of its
queued count, allowing two same-user requests by default while reserving fair
progress for other users.

Capacity rejection occurs before creating a session, message, execution future,
or model call. HTTP 429 returns `Retry-After` and a safe detail containing
`code=chat_capacity_reached`, scope, retry delay, aggregate active/queued counts,
and the applicable limit. No other user's identity or workload is exposed.

Cancellation removes queued work without affecting neighbors. Deadlines use
monotonic time. Shutdown first stops admission, then cancels queued work,
cooperatively cancels active requests, wakes gate waiters, and joins lifecycle
threads within a bounded interval.

## Fair resource gates

The cancellation-aware gates use per-user FIFO queues and round-robin
selection across users. Query embedding defaults to one, reranking to one, and
generation to one; retrieval execution defaults to four. Acquisition reports
the corresponding waiting/running lifecycle stage. Release is idempotent.

All live Ollama entry points must use the shared generation coordinator. Chat,
regeneration, message transforms, and grounded summaries may retain distinct
prompt/retrieval workflows, but none may bypass the configured local-model
capacity. A summary map loop reacquires between bounded model calls so
interactive users can progress.

## Request-local query runtime

The query view copies mutable configuration and all per-request
pipeline result/callback/filter state. It shares only deliberately read-only or
separately gated objects: the loaded Qdrant client, query embedding model,
reranker model, tokenizer/prompt registry, local LLM, and immutable BM25
publication arrays/maps.

No request assigns to the active publication pipeline's `config`,
`token_callback`, `cancel_event`, `telemetry_callback`,
`retrieval_cache_getter/setter`, active relative-path filter, BM25 allowed paths,
or `_search`. Request-local candidate lists are defensively copied at cache and
pipeline boundaries.

The profile matrix remains quick 120/250, standard 250/700, detailed 350/2000,
operational 350/unbounded, elite 350/unbounded, with legacy aliases and explicit
100..5000 maximums. Active prompt text, temperature, safety responses, budgets,
retrieval limits, fusion order, and citation rules are unchanged.

## Published generation reader leases

The active-query publication handle captures generation, Qdrant
collection, published document-version/note-revision boundaries, BM25 runtime,
and path maps under a short activation lock. Retrieval does not hold that lock.
Active reader count prevents publication replacement or retirement; the last
release permits a pending opportunistic activation. Refresh still builds away
from the request path and a chat never waits for PostgreSQL generation
discovery or indexing.

GPU/indexer priority becomes owner-counted. The cross-process marker remains
present until the last process-local query owner releases it. Release by one
request cannot remove priority held by another.

## Streaming and slow-client behavior

Each accepted request owns a bounded event channel. Token callbacks coalesce
deltas by the configured time/character thresholds, preserving order while
bounding memory. Operational stage transitions are retained preferentially;
tokens are coalesced rather than allowing unbounded growth. A disconnect or
Stop sets only that request's cancellation event, removes a queued waiter, and
closes a live Ollama iterator in `finally`. Generation retries remain permitted
only before a visible token.

## Transactional persistence and order

The stable ordering key is allocated when a turn is admitted, not when
it completes. One transaction materializes or locks the owned session, inserts
the user and assistant rows with the same turn order, and commits the pair.
History orders by turn order, role order, then stable row id. A minimal additive
Alembic revision is allowed only if existing fields cannot safely encode this.
No chat queue, worker, or event table is added.

For a draft session, the browser supplies one client session correlation id and
the backend materializes at most one owned session. Multiple accepted turns can
then execute independently against that id. Another user's existing UUID always
returns the same safe not-found behavior.

## Frontend state model

The session provider owns ordered request messages and draft-to-persisted
session aliases. The mounted chat panel owns live request runtimes keyed by
client request id and session id. Each submission captures its profile and
selected context, adds one ordered user/assistant placeholder pair, and owns an
independent abort controller, stage list, token buffer, status, error, and
result. The composer remains usable while another request runs unless local
capacity is rejected.

Result completion updates the matching placeholder without moving it. Stop and
Retry are request-specific and accessibly labelled. Session navigation preserves
live in-memory request state while the provider remains mounted. Auth
invalidation aborts all local streams and removes provisional unpersisted state.
A restrained polite live region announces state changes, not token deltas.

## Observability and security

Content-free process-local metrics include active/queued totals, counts by
stage, gate use/capacity/waiters, aggregate capacity rejections, queue/gate wait
p50/p95, cancellation/timeout/completed/failed counts, first-token latency,
tokens per second, reader count, pending activation, and priority owner count.
`/api/chat/debug` remains authenticated; admin projections remain permission
gated. Neither returns queue items, user identities, questions, prompts,
answers, evidence, paths, or raw exceptions. No durable `retrieval_events`
writes are added.

Threat-model tests cover callback/config/filter/cache cross-talk, personal and
selected-context isolation, session ownership/materialization, capacity
exhaustion, per-request cancellation, priority lease release, publication
use-after-swap, bounded slow consumers, error/debug leakage, auth invalidation,
and message-order corruption.

## Configuration

Conservative defaults are:

| Setting | Default |
| --- | ---: |
| `CIAL_CHAT_MULTI_REQUEST_ENABLED` | `true` |
| `CIAL_CHAT_EXECUTOR_WORKERS` | `8` |
| `CIAL_CHAT_MAX_ACTIVE_GLOBAL` | `8` |
| `CIAL_CHAT_MAX_ACTIVE_PER_USER` | `2` |
| `CIAL_CHAT_MAX_QUEUED_GLOBAL` | `64` |
| `CIAL_CHAT_MAX_QUEUED_PER_USER` | `8` |
| `CIAL_CHAT_QUERY_EMBEDDING_CONCURRENCY` | `1` |
| `CIAL_CHAT_RETRIEVAL_CONCURRENCY` | `4` |
| `CIAL_CHAT_RERANK_CONCURRENCY` | `1` |
| `CIAL_CHAT_GENERATION_CONCURRENCY` | `1` |
| `CIAL_CHAT_QUEUE_WAIT_TIMEOUT_SECONDS` | `120` |
| `CIAL_CHAT_EVENT_QUEUE_SIZE` | `256` |
| `CIAL_CHAT_TOKEN_FLUSH_MS` | `40` |
| `CIAL_CHAT_TOKEN_FLUSH_CHARS` | `256` |
| `CIAL_CHAT_FAIR_SCHEDULING` | `true` |

All counts are positive, executor workers may not exceed global active
capacity, and per-user active/queued values may not exceed corresponding global
values. Generation is never auto-sized from CPU, CUDA, or queue depth.

## Failure behavior, rollback, and limits

Capacity is a local busy condition, not dependency failure. A healthy scheduler
under pressure does not turn system status red. Dependency loss, publication
loss, deadline, cancellation, and internal failure use safe existing public
errors and roll back message persistence.

Rollback disables multi-request admission and returns execution to the existing
compatible endpoint behavior; it does not alter PostgreSQL/Qdrant/indexing
state. Any additive ordering columns remain backward-readable.

This design intentionally provides no durable in-flight recovery, cross-process
scheduler, distributed fairness, or multi-worker model sharing. A future
distributed design is justified only if one query process can no longer meet
measured throughput or availability requirements.

## Verification plan

Deterministic barrier-based tests must cover the backend and frontend race
matrix in the implementation brief, including same/different-user concurrency,
fairness, bounds, every gate cancellation point, request-state isolation,
publication leases, atomic ordered history, single draft materialization,
shutdown, and compatibility routes. Existing prompt, access, indexing,
preview, summary, theme, typecheck, and build tests remain green.

Integrated Playwright verification uses the real FastAPI scheduler with a
deterministic streaming model and stores traces, JSON, and representative
screenshots below `outputs/playwright/multi-request-chat/`. A bounded local
probe covers 1/2/4/8/16 submissions across 1/2/4/8 users and records admission,
queue/gate waits, concurrency maxima, fairness, first token, total latency,
throughput, cancellation release, queue high-water, memory, and database
connection use. Real Ollama/Qdrant results are reported only if those services
and models are actually exercised.

## Implementation record

The process-local controller in
`backend/app/services/chat_concurrency.py` provides bounded admission, a fixed
executor, configurable per-user/global active and queued limits, fair
round-robin dispatch, cancellation-aware fair resource gates, a bounded
coalescing event channel, content-free metrics, draft materialization locks,
and bounded shutdown. `CIAL_CHAT_MULTI_REQUEST_ENABLED=false` restores a
single-active-request mode. `CIAL_CHAT_FAIR_SCHEDULING=false` restores FIFO
selection without removing the safety bounds.

`KnowledgeEngineService` now leases a stable published pipeline, constructs a
request-local mutable query view, and shares only heavyweight model/client and
published read-only resources. Query embedding, retrieval, reranking, and
generation are gated at their actual call sites. The GPU priority marker is
owner-counted. Regeneration, transformations, and summary model calls share the
same generation gate.

Both stream and compatibility POST routes use the controller. Admission
failure is a safe HTTP 429 with `Retry-After`; cancellation and deadlines are
request-local; persistence occurs only after a final cancellation checkpoint.
Migration `20260729_0018_chat_turn_order.py` adds `turn_sequence` and
`role_sequence`; history reads by submission order and role order before
timestamp/id fallbacks.

The frontend replaces its global loading/controller/buffer state with one
runtime per client request. It keeps the composer available, displays one
accessible Stop/Retry/status surface per request, replaces placeholders
in-place, aliases a single draft session UUID to the persisted session, and
aborts/removes provisional state on auth invalidation or chat-panel unmount.

The chat viewport follows streamed updates only while the reader is within the
near-bottom threshold. Intentional upward scrolling suspends follow; returning
near the bottom or submitting a new prompt resumes it. The one-second request
clock and loading-state updates never initiate scrolling. Programmatic follow
does not enqueue repeated smooth-scroll animations, and reduced-motion mode is
always instant. Desktop pane resizing is direct manipulation: flex, width,
margin, and answer-card geometry do not transition while the pointer is down.

Verification includes the 541-test backend suite, final targeted
concurrency/isolation tests, 85 frontend contract tests, TypeScript typecheck,
an isolated production build, offline Alembic SQL rendering, deterministic
controller performance probes, and Playwright browser evidence. Exact commands,
results, artifacts, and limitations are in
`docs/verification/MULTI_REQUEST_CHAT_VERIFICATION.md`.
