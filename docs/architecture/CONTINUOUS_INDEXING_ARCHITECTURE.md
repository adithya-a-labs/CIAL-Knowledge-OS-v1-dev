# Continuous Indexing Architecture

Status: implemented in revisions `20260724_0016` and `20260725_0017`.

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

Recovery treats both an elapsed lease and a missing lease on any in-progress
legacy/interrupted row as expired. After Qdrant verification, terminal job
completion atomically restores the authoritative document/version or note
state to `indexed` (or preserves `deleted`/`removed`). A transient
`verifying` stage therefore cannot leave a completed target reporting
`indexing`.

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
CPU. The adaptive controller starts at 64 chunks, grows healthy full batches
through 128 to the configured maximum (256 by default), and considers
per-chunk latency plus the configured VRAM target. CUDA OOM immediately lowers
the active limit and retries recursively. Requested FP16/BF16 safely falls
back to FP32 when the resolved device is CPU.

OCR-supported image documents are tagged `workload_queue=ocr` and execute in a
separate bounded `CIAL_INDEXER_OCR_WORKERS` pool. Normal extraction keeps all
of its configured workers even during an OCR burst. Repository/reconciliation
OCR work receives a lower priority within its source tier, while an explicit
user upload retains the top upload priority.

Completed embedding sets are submitted to a dedicated, single-consumer Qdrant
writer stage backed by the bounded `CIAL_INDEXER_WRITE_QUEUE_SIZE`. The
embedding stage returns to newly prepared work without waiting for Qdrant
network writes. Writer futures retain their job leases, perform batched
upserts, verify the complete asset version, finalize PostgreSQL, and mark BM25
dirty. Queue capacity applies backpressure, and graceful shutdown drains the
writer before generation publication and engine close.

Qdrant writes are verified before job completion. A new document version is
written and verified before older versions are removed. Normal document
replacement uses filtered delete/upsert/count/retrieve verification and does
not use Qdrant `scroll()`.

Before embedding a new immutable document version, each prepared chunk receives
a SHA-256 `chunk_hash` and the active embedding-model and chunking contract
versions. Matching prior `document_chunks` rows resolve to their verified
Qdrant points and reuse the existing vectors. Only unmatched chunks enter the
GPU batcher. The worker still writes a complete, newly versioned Qdrant point
set before stale-version cleanup, preserving atomic replacement and all
existing payload fields.

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
PostgreSQL generation. A chat turn always captures the already-loaded published
generation and starts generation discovery on a daemon refresh path. It never
waits for PostgreSQL generation reads, queue state, worker heartbeats,
reconciliation, extraction, embedding, or a building generation. The refresh
builds the replacement BM25 index away from the query lock and performs only a
short opportunistic activation; an active chat wins the race and refresh retries
later. A failed, partial, missing, unpublished, zero-valued, or
collection-mismatched generation never replaces the last valid generation.
Snapshot JSON loading, chunk materialization, token-cache loading, BM25 model
construction, relative-path maps, and lexical posting maps all happen during
startup or this asynchronous refresh. They never happen inside retrieval.
Dense search is additionally constrained to document-version and note-revision
identities recorded in that published BM25 snapshot. Qdrant's in-place writer
may therefore prepare or verify new points without making a partial version
queryable. If an old dense version has already been retired during the short
publication window, the old BM25 snapshot continues serving that asset until
the atomic pointer advances.

The FastAPI request path is strictly query-only:

```text
POST /api/chat/stream
  -> KnowledgeEngineService.answer_question
  -> loaded pipeline.answer
  -> dense retrieval + published BM25 retrieval
  -> fusion -> reranking -> evidence selection -> generation
```

It does not call the batch pipeline `run()` method. That method owns corpus
load/chunk/embed/index orchestration and is limited to notebooks and explicit
batch workflows. The live runtime similarly refuses to build a missing BM25
index from chunks during a request; it reports the published generation as
unavailable instead.

### Phase 1 retrieval runtime optimization (2026-07-26)

FastAPI activates retrieval infrastructure before declaring the query runtime
ready. It loads the published BM25 snapshot once, constructs its in-memory
posting/path indexes, loads the dense query embedding model, performs one
discarded readiness embedding, loads the cross-encoder, resolves `auto` to
CUDA when available (CPU otherwise), and performs one discarded batched
readiness prediction. No warmup result enters Qdrant, fusion, reranking,
evidence selection, citations, or generation.

For each hybrid search, dense Qdrant and BM25 branches start concurrently with
their unchanged candidate limits and inputs. The caller waits for both bounded
branches, preserves the per-branch rankings, and invokes the same reciprocal
rank fusion. BM25 reads only the active in-memory publication. Publication
discovery compares the published BM25 generation and does not reload an
unchanged snapshot.

The generation-29 validation retained 10 dense candidates, 10 BM25 candidates,
28 cross-encoder candidates, and 8 selected evidence items. The warm repeated
end-to-end retrieval measured 1,919 ms: parallel dense/BM25 81 ms, BM25 search
30.5 ms, fusion 2 ms, one GPU reranker batch 38 ms, and evidence selection
7 ms. The first post-start measurement was 2,103 ms; the operational target is
below 2 seconds on the warmed runtime, not a reduction in retrieval work.

BM25 publication is debounced during a sustained job burst and forced before
the worker enters its queue-empty watching state. If the API started before the
first collection existed, the first published generation activates the cached
query runtime without an API restart.

Document/note privacy fields come only from PostgreSQL. Personal content uses
`storage_scope=personal`, `visibility=private`, an owner, and its personal
workspace. The loaded BM25 runtime maps authorized relative paths to published
chunk indexes. Query terms access only their prebuilt posting lists; authorization
filters those matches before top-candidate ranking. The query path does not
construct an authorization-specific BM25 model, retokenize chunks, read the
snapshot file, or iterate the full chunk corpus.

### BM25 latency regression verification (2026-07-26)

Generation 29 contained 459,715 chunks across 488 document identifiers. Its
published JSON snapshot was 1,049,687,710 bytes. An isolated runtime measurement
found snapshot loading at 17,194 ms and published-index activation at 35,725 ms;
these costs are intentionally outside the request path. Before the correction,
a cold broad authorization scope constructed a second BM25 model during chat
and took 15,626 ms. Removing that rebuild alone still left full-corpus scoring
at 828-911 ms. The published posting lookup measured 2.48-11.15 ms for
unrestricted, cold/reused broad-scope, and cold/reused single-path searches on
the same snapshot. The operational objective is BM25 search below 100 ms.

## Readiness and Status APIs

`GET /api/health`, `GET /api/index/status`, and the additive v2 alias
`GET /api/indexer/status` distinguish:

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
If no valid generation has ever been published, chat returns controlled
unavailability rather than attaching to an arbitrary collection. Failed and
pending jobs leave the prior valid generation serving.

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
| `CIAL_INDEXER_MIN_EXTRACTION_WORKERS` / `MIN_EXTRACTION_WORKERS` | `1` |
| `CIAL_INDEXER_MAX_EXTRACTION_WORKERS` / `MAX_EXTRACTION_WORKERS` | at least `8`, operator bounded |
| `CIAL_INDEXER_EXTRACTION_WORKERS` / `EXTRACTION_WORKERS` | `8`, clamped to min/max |
| `CIAL_INDEXER_OCR_WORKERS` | `2` |
| `CIAL_INDEXER_PREPARED_QUEUE_SIZE` | `8` |
| `CIAL_INDEXER_EMBED_QUEUE_SIZE` | `4096` |
| `CIAL_INDEXER_WRITE_QUEUE_SIZE` | `16` |
| `CIAL_INDEXER_EMBED_BATCH_SIZE` | `64` |
| `CIAL_INDEXER_EMBED_MIN_BATCH_SIZE` | `1` (OOM recovery floor; healthy startup remains `64`) |
| `CIAL_INDEXER_EMBED_MAX_BATCH_SIZE` | `256` |
| `CIAL_INDEXER_EMBED_GROWTH_LATENCY_TOLERANCE` | `1.15` |
| `CIAL_INDEXER_EMBED_VRAM_TARGET_RATIO` | `0.70` (about 11.2 GiB on a 16 GiB RTX 5070 Ti) |
| `CIAL_INDEXER_EMBED_MAX_BATCH_TOKENS` | `32768` |
| `CIAL_INDEXER_EMBED_MAX_WAIT_MS` | `75` |
| `CIAL_INDEXER_QDRANT_BATCH_SIZE` | `256` |
| `CIAL_INDEXER_DEVICE` | `auto` |
| `CIAL_INDEXER_PRECISION` / `EMBEDDING_PRECISION` | `fp16`; CPU safely falls back to FP32 |
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
| `QDRANT_QUERY_TIMEOUT_SECONDS` | `3` |
| `QDRANT_QUERY_RETRY_ATTEMPTS` | `2` |
| `QDRANT_UPSERT_TIMEOUT_SECONDS` | `60` |
| `QDRANT_DELETE_TIMEOUT_SECONDS` | `60` |
| `QDRANT_COLLECTION_TIMEOUT_SECONDS` | `120` |
| `CIAL_RERANKER_TIMEOUT_SECONDS` | `15` |
| `CIAL_EVIDENCE_SELECTION_TIMEOUT_SECONDS` | `5` |
| `CIAL_GENERATION_TIMEOUT_SECONDS` | `120` |
| `CIAL_CHAT_LOCK_TIMEOUT_SECONDS` | `5` |
| `CIAL_CHAT_REQUEST_TIMEOUT_SECONDS` | `150` |

Query retries apply only to transient network, timeout, HTTP 408/429, and 5xx
failures. Invalid requests and other permanent Qdrant failures are not retried.
Server collections maintain payload indexes for relative path,
document/version id, note id/revision, repository id, owner id, visibility, and lifecycle state;
authorization and replacement filters therefore execute inside Qdrant rather
than scanning corpus files or fetching every point.
The server stream and browser use matching 150-second terminal watchdogs; the
shorter component limits normally fail first. The reranker is loaded once at
runtime initialization, keeps its resolved device, receives at most the
configured candidate cap, and has a hard per-turn deadline.
Dense/Qdrant has an absolute 30-second outer ceiling even when retry
configuration would otherwise run longer. BM25, fusion, reranking, and
evidence selection have absolute ceilings of 10, 5, 15, and 5 seconds
respectively; the first two are the hard upper bounds of the corresponding
`Phase3Config` fields. Dense or lexical timeout uses the other authorized branch when
available, fusion failure uses stable available-branch ordering,
reranker timeout uses fused order, and evidence timeout selects nothing.

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
`scripts\launch_all.bat` is the short compatibility entry point and delegates
to the same production launcher.

## Failure Recovery and Observability

Structured events cover watcher receipt/stability, reconciliation, queue
claim/lease/stages/retry/completion, extraction, cross-asset GPU batches,
Qdrant verification, stale cleanup, BM25 generation, queue depths, heartbeats,
and shutdown. Logs never include document/note bodies, embeddings, credentials,
prompt bodies, unrestricted errors, or absolute personal paths.

Worker heartbeats expose CPU/process utilization, logical core count,
documents/hour, chunks/minute, active adaptive batch limit, GPU utilization,
and GPU memory for the assigned CUDA device.

PostgreSQL loss stops claims/finalization. Qdrant loss creates retryable jobs
while the API may keep serving its previous index. Graceful shutdown stops new
claims, keeps leases renewed for active bounded work, closes watchers, records
`stopped`, and releases model/Qdrant resources.

## Validation

Verified on 2026-07-25:

- backend: 476 tests passed plus 50 subtests in 28.02 seconds; one upstream
  Starlette/httpx deprecation warning;
- frontend: 53 tests passed; TypeScript typecheck passed; Vite production build
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

## Assistant Health Projection

Continuous indexing projects its existing durable state into authenticated
`GET /api/system/status`; it does not create a second queue or publication
pointer. The projection includes the latest atomically published dense/BM25
generation, publication time and point count, queue depth/counts, bounded active
job summaries, worker state and heartbeat, and the worker's CPU/GPU telemetry.

An active queue with a fresh healthy worker produces blue only when the API can
still answer from a valid published generation and all chat-critical
dependencies are healthy. A missing/stale worker is yellow when chat remains
usable, and any loss of the published generation or another chat-critical
dependency is red. Thus indexing progress never becomes a reason to wait before
chat submission, while stalled indexing remains visible as degradation.

## Administrator Operations Projection

`AdminSystemMonitorService` reuses the same durable control plane for
`GET /api/admin/system/monitor` and the SSE
`GET /api/admin/system/stream`. It does not create another queue, worker
registry, or generation pointer. The administrator projection adds:

- active worker count based on non-degraded, non-stopped heartbeats inside the
  configured freshness window;
- current job stages, per-operation priority queue counts, cumulative terminal
  counts, bounded recent errors, internal queue depths, and last publication;
- the indexer's actual embedding device/precision, adaptive batch limit,
  documents/hour, chunks/minute, CPU sample, GPU utilization, and VRAM sample;
- extraction/OCR configuration and active task counts; and
- transition events derived from actual durable stages (`pending`, `claimed`,
  `extracting`, `chunked`, `embedding`, `writing`, and `verifying`), worker
  state, and published generation changes.

Missing heartbeat or component telemetry is reported as stale/degraded.
Unavailable GPU samples remain unavailable; CPU operation is never relabelled
as CUDA. The projection contains identifiers and safe error codes only, never
source content, credentials, repository paths, or exception text.

## Physical GPU Isolation And Query Priority

Process isolation does not isolate a shared CUDA device. The API now resolves
`CIAL_QUERY_EMBEDDING_DEVICE=auto` to CUDA when available and keeps its
single-query BGE-M3 runtime warm; CPU is only an unavailable-CUDA fallback.
The standalone indexer separately owns throughput-oriented BGE-M3 CUDA batches
and remains cooperative with the active chat lease.

The indexer yields between bounded batches whenever the API holds the
stale-safe chat-priority lease. It moves the embedding model to CPU while
yielding and after a configurable idle interval, releases cached CUDA allocator
blocks, and restores the configured device only when another batch is ready.
An in-flight kernel completes normally; no process is killed and no partial
batch is published. These rules change physical scheduling only, not queue
leases, retrieval, Qdrant verification, BM25, or publication semantics.

Worker telemetry distinguishes configured device from current residency and
reports GPU state, active embedding jobs, priority waits, and process-local CUDA
memory. A stopped or restarting worker is not a query dependency once a valid
publication exists.

### Ollama-first allocation policy

The operational defaults are `OLLAMA_KEEP_ALIVE=30m`,
`OLLAMA_GPU_PRIORITY_ENABLED=true`, `OLLAMA_NUM_GPU=-1`, and
`INDEXER_GPU_COOPERATIVE_MODE=true` (the equivalent `CIAL_`-prefixed names are
also accepted). `num_gpu=-1` requests all available model layers on the GPU;
the actual placement remains an Ollama/CUDA decision and is verified from
Ollama's live process record.

The allocation state machine is:

1. With no active chat, the indexer may use CUDA at its adaptive throughput
   limit.
2. A chat lease causes the indexer to finish its bounded in-flight batch, move
   BGE-M3 to CPU, empty its unused CUDA cache, and wait. Ollama then loads or
   reuses Gemma with all GPU layers requested.
3. After generation releases the chat lease, the next pending embedding batch
   unloads the warm Ollama runner and restores BGE-M3 to CUDA immediately. If
   there is no pending indexing work, Ollama may remain warm for its keep-alive
   interval without blocking useful GPU work.

This is cooperative scheduling, not CUDA process preemption: active kernels are
not interrupted, continuous indexing is not disabled, and durable queue work
continues. The warm model reservation is not treated as user activity: pending
index work reclaims the device, while a failed unload leaves embedding on CPU
for that batch rather than risking CUDA starvation.

Generation telemetry samples `nvidia-smi` throughout generation and combines
it with Ollama's live `size`/`size_vram` process record. It reports
`ollama_processor_type`, `gpu_memory_used`, `gpu_memory_total`,
`cpu_offload_detected`, and average/peak `generation_gpu_utilization`.
`gpu_layers_used` is deliberately null because Ollama's process API does not
publish an actual layer count; `gpu_layers_requested=-1` records the real
request without fabricating a measurement.

### Embedding device resolution and verification

Only the standalone `backend/indexer_main.py` process owns production BGE-M3
document embedding. Extraction, OCR, chunking, metadata hydration, and Qdrant
submission remain CPU/network work. The FastAPI query process separately uses
the configured query-embedding device and does not supply model state to the
indexer.

`CIAL_INDEXER_DEVICE=auto` is resolved inside the standalone process to the
concrete `cuda:<index>` device when `torch.cuda.is_available()` is true, or to
CPU only when CUDA is unavailable. The resolved value—not the literal string
`auto`—is retained as the device to restore after idle/chat release. Before
every encode batch, the worker verifies the model's actual device. A requested
CUDA model that remains on CPU is an indexing error and is never treated as a
successful CPU batch.

Startup diagnostics record configured and actual device, PyTorch/CUDA build,
CUDA availability and device name, model dtype, and process-local allocated and
reserved CUDA bytes. Batch diagnostics record actual device, batch size,
allocated bytes before/after encode, and measured duration. The model stays
loaded during indexing and the existing adaptive 64–256 batch controller and
CUDA-OOM reduction remain unchanged.

For troubleshooting, compare `torch.version.cuda` and
`torch.cuda.is_available()` in the repository virtual environment, then inspect
the indexer heartbeat's configured/actual device and model status. During an
active non-reused embedding batch, `nvidia-smi` must show the standalone Python
process and non-zero utilization. Zero utilization after the configured idle
release interval is expected and does not indicate CPU embedding.

## Query Runtime Index And Cache Boundary

Phase 2 infrastructure remains entirely on the read side of the publication
boundary. Query-runtime startup performs these operations once:

```text
load active generation pointer
  -> reuse/load BGE-M3 and run one warm encode
  -> verify/create Qdrant payload indexes idempotently
  -> attach published document-version constraints
  -> load the published BM25 snapshot
  -> warm the reranker
  -> mark retrieval ready
```

Payload-index creation does not rewrite points, filters, vectors, security
predicates, or publication state. Server collections provision indexes for
`repository_id`, `workspace_id`, `organization_id`, `document_id`,
`document_version_id`, `published_generation`, `storage_scope`,
`owner_user_id`, `department_id`, `folder_id`, `visibility`,
`lifecycle_status`, `relative_path`, and note identity/revision. Embedded
Qdrant reports payload indexing as unsupported because this production
multi-process architecture requires server mode.

The in-memory retrieval cache belongs to the API query process and is bounded
by `CIAL_RETRIEVAL_CACHE_MAX_ENTRIES` (default 256). It stores only the output
of the existing dense/BM25/RRF stage. It is never shared with or written by the
indexer and is not part of the durable published generation.

Publication activation clears every entry before the new generation can be
used. A re-resolved permission fingerprint that differs from the last value
for a principal evicts that principal's entries. Workspace/access scope and
effective authorized paths remain part of each key. Consequently the cache
cannot turn a formerly authorized result into a current authorization grant;
the same access-resolution path always runs before cache lookup.

## LAN Server Mode Boundary

Continuous indexing remains a host-local worker concern in LAN Server Mode.
The gateway exposes neither the worker nor PostgreSQL, Qdrant, or Ollama.
LAN clients can observe indexing readiness only through existing authenticated
same-origin API projections. Hotspot loss, mDNS failure, or gateway restart
does not change queue durability, publication activation, or cache
invalidation behavior.

## Measured device policy

The indexer remains the only document-embedding GPU owner. Its BGE-M3 model is
`cuda:0`/fp16 during active batches, releases to CPU while idle or yielding,
and restores the resolved CUDA target before the next encode. Measured batch
throughput, VRAM use, the 0.70 budget, and chat arbitration evidence are in
`GPU_WORKLOAD_PLACEMENT.md`.
