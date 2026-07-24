# Continuous Indexing Architecture

Status: implemented in revision `20260724_0016`.

This document is the canonical runtime description for continuous indexing.
PostgreSQL is the durable queue and control plane, source files stay in the
configured enterprise repository or `CIAL_WORKSPACE_ROOT`, and vectors stay in
Qdrant server mode.

## Process Model

```text
React/Vite frontend ──> FastAPI API ──> PostgreSQL / Qdrant / Ollama
                              │
                              └── query embedding + BM25 snapshot hot reload

enterprise repository ─┐
personal workspace ────┼──> metadata reconciliation / watcher
committed note versions┘                 │
                                        v
                              PostgreSQL indexing_jobs
                                        │
                         SELECT ... FOR UPDATE SKIP LOCKED
                                        │
                   ┌────────────────────┴────────────────────┐
                   v                                         v
          bounded CPU document pool             note hydration / controls
                   │                                         │
                   └────────────────────┬────────────────────┘
                                        v
                            cross-asset bounded batcher
                   │
                   v
       one loaded embedding model / assigned device
                   │
                   v
       verified Qdrant write -> stale-version cleanup
                   │
                   v
       PostgreSQL completion + atomic BM25 generation
```

Normal deployments run four application commands: infrastructure, backend,
indexer, and frontend. PostgreSQL and Ollama can be installer-managed services.

## Responsibility Boundary

FastAPI:

- validates paths and creates runtime directories;
- reports PostgreSQL, Qdrant, Ollama, API, retrieval, and indexer readiness;
- loads query-time embedding/reranking/retrieval components;
- attaches to an existing Qdrant collection without recreating it;
- loads the latest valid atomic BM25 snapshot;
- enqueues sync/rebuild requests and returns `202 Accepted`;
- continues serving the last committed index while new jobs run.

Standalone indexer:

- requires PostgreSQL and Qdrant server mode;
- publishes a durable worker heartbeat;
- recovers expired leases;
- performs startup and periodic metadata reconciliation;
- owns filesystem watchers for enterprise and personal roots;
- claims, extracts, chunks, embeds, writes, verifies, and completes jobs;
- publishes Qdrant/BM25 index generations.

Corpus Synchronization Engine:

- scans, diffs, and updates PostgreSQL metadata;
- detects create, modify, delete, move, and same-hash rename;
- queues durable operations;
- never embeds and never writes Qdrant.

## Queue Contract and State Machine

`indexing_jobs` is the only indexing queue. Targets are explicit:

- document: `asset_type=document`, `document_id`, optional immutable
  `document_version_id`;
- note: `asset_type=note`, `note_id`, optional immutable `note_version_id`;
- control request: `operation=rebuild_scope` with scope in sanitized JSON.

Operations are `upsert_version`, `delete_asset`, `refresh_metadata`,
`reprocess_version`, and `rebuild_scope`.

```text
pending/retry_wait -> claimed -> extracting -> chunked -> embedding
                   -> writing -> verifying -> completed
                                      └────> retry_wait / failed
any safe pre-write stage ------------------> superseded / cancelled
```

Claims use priority descending, then availability and creation time, under
`FOR UPDATE SKIP LOCKED`. `claimed_by`, `lease_expires_at`, and `heartbeat_at`
make interrupted work recoverable. Transient failures use exponential backoff
with jitter and bounded attempts. Permanent payload, target, or format errors
fail without an endless retry loop.

Deletes have priority 120, committed notes and API uploads 100, manual retries
90, path/ACL metadata refreshes 80, filesystem reconciliation work 60, and
bulk administrative rebuild expansion 10. A newer committed version can queue
while an older version runs; the older writer rechecks the authoritative
current version before stale cleanup and becomes `superseded` if it lost the
race.

Partial unique indexes deduplicate an active document-version/operation or
note-version/operation while still allowing a newer version to queue.

`indexer_workers` stores safe heartbeat/telemetry state.
`index_generations` stores the committed dense/BM25 generation pointer.

## CPU, GPU, and Backpressure

Document extraction and chunking run in the bounded CPU pool configured by
`CIAL_INDEXER_EXTRACTION_WORKERS`; note blocks are hydrated on CPU and enter the
same queue. Prepared assets feed a bounded cross-document/note batcher in
round-robin order. A batch flushes at the first configured chunk, token, or
wait limit. The embedding model is loaded once when the indexer starts.
Explicit CUDA configuration fails if CUDA is unavailable; `auto` may choose
CPU. CUDA OOM reduces the active batch recursively and retries the bounded
batch.

Qdrant writes are verified before job completion. A new document version is
written and verified before older versions are removed. Normal document
replacement uses filtered delete/upsert/count/retrieve verification and does
not use Qdrant `scroll()`.

## Watcher and Reconciliation

The indexer watches the configured enterprise and personal roots with
`watchdog`. Events are contained under the canonical root, ignored according
to the file registry/application-artifact policy, coalesced, and debounced.
Files must keep the same size and mtime across configured checks and must open
successfully before reconciliation.

Watcher paths force a content hash even if size and mtime were preserved.
Other files use the PostgreSQL size/mtime/hash tuple to avoid re-hashing
unchanged content during both event-triggered and periodic scans.

A complete metadata reconciliation runs once at indexer start and every
`CIAL_CORPUS_RECONCILE_INTERVAL_SECONDS`. A PostgreSQL advisory lock prevents
overlap. Reconciliation queues only differences; an unchanged corpus with no
incomplete jobs causes zero extraction and embedding calls.

When an administrator changes the enabled enterprise repository through the
settings API, FastAPI persists the setting and enqueues a reconciliation
request. The indexer reloads the shared configuration before reconciliation,
validates the new root, and restarts its watcher against that root without
requiring either process to restart. Invalid roots put reconciliation and the
worker heartbeat into a degraded state with an actionable error.

## Change Semantics

- New/content-changed document: immutable version + `upsert_version`.
- Same-content move/rename: preserve document identity +
  `refresh_metadata`; no embedding.
- Delete: soft-delete PostgreSQL metadata + `delete_asset`.
- ACL/owner/workspace/visibility change: `refresh_metadata` hydrates
  authoritative PostgreSQL fields into Qdrant payloads without embedding.
- Enterprise upload: safe file write followed by a targeted PostgreSQL
  document/version/job transaction; the periodic reconciler is the recovery
  path if that transaction is interrupted.
- Personal/chat upload: owner-private document/version/job in one DB
  transaction after the safe filesystem write.
- Note save: only a successful optimistic-concurrency commit queues work.
  Pending older revisions are marked `superseded`.
- Note delete/archive: durable `delete_asset`.
- Admin rebuild: a control job expands into versioned reprocess jobs; FastAPI
  never performs the rebuild.

## Replacement and Live Refresh

Dense points are visible after a verified Qdrant write. The indexer then writes
a complete BM25 source snapshot to a temporary file, `fsync`s it, and atomically
publishes it with `os.replace`. Only after publication does it advance the
PostgreSQL generation. The API checks that pointer before each chat turn and
swaps the lexical retriever under the query lock. A failed or partial snapshot
never replaces the last valid generation.

BM25 publication is debounced during a sustained job burst and forced before
the worker enters its queue-empty watching state. If the API started before the
first collection existed, the first published generation activates the cached
query runtime without an API restart.

Document/note privacy fields come only from PostgreSQL. Personal content uses
`storage_scope=personal`, `visibility=private`, an owner, and its personal
workspace. BM25 authorization filtering happens before candidate scoring.

## Readiness and Status APIs

`GET /api/health` and `GET /api/index/status` distinguish:

- `api_ready`
- `retrieval_ready`
- `database_ready`
- `qdrant_ready`
- `models_ready`
- `indexer_seen` and `indexer_state`
- `index_fresh`
- queue counts by status/operation
- worker heartbeat, generation, BM25 generation, and safe throughput fields

The API can be ready while `retrieval_ready=false` on a first deployment. A
non-empty queue does not disable chat when a valid generation exists.

`POST /api/corpus/sync` and `POST /api/index/rebuild` require their existing
permissions, enqueue durable work, and return `202`. Rebuild also requires
explicit confirmation.

## Configuration

| Variable | Default |
| --- | --- |
| `CIAL_INDEXER_ENABLED` | `true` |
| `CIAL_INDEXER_WORKER_ID` | generated |
| `CIAL_INDEXER_POLL_SECONDS` | `1` |
| `CIAL_INDEXER_LEASE_SECONDS` | `120` |
| `CIAL_INDEXER_HEARTBEAT_SECONDS` | `15` |
| `CIAL_INDEXER_HEARTBEAT_STALE_SECONDS` | `45` |
| `CIAL_INDEXER_MAX_ATTEMPTS` | `5` |
| `CIAL_INDEXER_RETRY_BACKOFF_SECONDS` | `5` |
| `CIAL_INDEXER_EXTRACTION_WORKERS` | bounded from CPU count |
| `CIAL_INDEXER_PREPARED_QUEUE_SIZE` | `8` |
| `CIAL_INDEXER_EMBED_QUEUE_SIZE` | `4096` |
| `CIAL_INDEXER_WRITE_QUEUE_SIZE` | `16` |
| `CIAL_INDEXER_EMBED_BATCH_SIZE` | `64` |
| `CIAL_INDEXER_EMBED_MAX_BATCH_TOKENS` | `32768` |
| `CIAL_INDEXER_EMBED_MAX_WAIT_MS` | `75` |
| `CIAL_INDEXER_QDRANT_BATCH_SIZE` | `128` |
| `CIAL_INDEXER_DEVICE` | `auto` |
| `CIAL_INDEXER_PRECISION` | `auto` |
| `CIAL_INDEXER_GPU_POLICY` | `balanced` |
| `CIAL_CORPUS_WATCH` | `true` in deployed indexer |
| `CIAL_CORPUS_WATCH_DEBOUNCE_MS` | `750` |
| `CIAL_CORPUS_FILE_STABILITY_INTERVAL_MS` | `500` |
| `CIAL_CORPUS_FILE_STABILITY_CHECKS` | `3` |
| `CIAL_CORPUS_RECONCILE_INTERVAL_SECONDS` | `300` |
| `CIAL_BM25_REFRESH_DEBOUNCE_SECONDS` | `2` |
| `QDRANT_TIMEOUT_SECONDS` | `30` |
| `QDRANT_RETRY_ATTEMPTS` | `3` |
| `QDRANT_RETRY_BACKOFF_SECONDS` | `2` |
| `QDRANT_HEALTH_TIMEOUT_SECONDS` | `5` |
| `QDRANT_QUERY_TIMEOUT_SECONDS` | `30` |
| `QDRANT_UPSERT_TIMEOUT_SECONDS` | `60` |
| `QDRANT_DELETE_TIMEOUT_SECONDS` | `60` |
| `QDRANT_COLLECTION_TIMEOUT_SECONDS` | `120` |

The legacy `CIAL_AUTO_INDEX_ON_STARTUP` and
`CIAL_FORCE_REBUILD_ON_STARTUP` values are parsed for compatibility but logged
and ignored by FastAPI.

## Local and Windows Operation

```powershell
scripts\start_qdrant.bat
scripts\start_backend.bat
scripts\start_indexer.bat
scripts\start_frontend.bat
```

PowerShell variants exist for backend, indexer, and frontend. The daily launcher
validates the repository, starts dependencies, applies Alembic, starts the API,
starts the indexer if there is no fresh heartbeat, starts the frontend, and
waits for API/frontend readiness plus an indexer heartbeat—not for queue drain.
Backend, indexer, and frontend have separate launcher log files.

## Failure Recovery and Observability

Structured events cover watcher receipt/stability, reconciliation, queue
claim/lease/stages/retry/completion, extraction, cross-asset GPU batches,
Qdrant verification, stale cleanup, BM25 generation, queue depths, heartbeats,
and shutdown. Logs never include document/note bodies, embeddings, credentials,
prompt bodies, unrestricted errors, or absolute personal paths.

PostgreSQL loss stops claims/finalization. Qdrant loss creates retryable jobs
while the API may keep serving its previous index. Graceful shutdown stops new
claims, keeps leases renewed for active bounded work, closes watchers, records
`stopped`, and releases model/Qdrant resources.

## Validation

Verified on 2026-07-24:

- backend: 446 tests passed plus 50 subtests in 53.94 seconds; one upstream
  Starlette/httpx deprecation warning;
- frontend: 43 tests passed; TypeScript typecheck passed; Vite production build
  passed from a temporary output directory;
- operational Phase 4.5 prompt guard passed with temperature 0 and the existing
  operational profile;
- offline Alembic upgrade and downgrade SQL passed for
  `20260724_0015 -> 20260724_0016`;
- BGE-M3 loaded on `cuda:0` as float16 and embedded 256 synthetic chunks at
  193.41 chunks/second, 1024 dimensions, with 1489.89 MiB peak allocated CUDA
  memory; the local sample observed 100% GPU utilization;
- the mutation-free batcher assembled 20,000 chunks into 313 batches, all 313
  spanning multiple assets, at 149,634.97 chunks/second.

The configured live PostgreSQL password was rejected by the local server, so a
live migration and durable end-to-end queue/Qdrant throughput run could not be
claimed on this machine. Qdrant health, Ollama, CUDA, the actual embedding
model, and offline migration SQL were verified independently.
