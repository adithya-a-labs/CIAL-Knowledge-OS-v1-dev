# Full-Stack Integration

Status: API and continuous indexer are independent runtime processes.

The canonical runtime specification is
[Continuous Indexing Architecture](CONTINUOUS_INDEXING_ARCHITECTURE.md).

## Runtime

```text
React/Vite -> FastAPI -> PostgreSQL / Qdrant / Ollama
repositories + uploads + note commits -> PostgreSQL queue -> indexer -> Qdrant/BM25
```

FastAPI starts query-time services only. `StartupService.run_startup()` creates
directories, validates paths, checks PostgreSQL/Qdrant/Ollama, attaches to an
existing Qdrant collection, loads the latest BM25 generation, and loads
query-time models. It never calls corpus-wide `load()`, `chunk()`, `embed()`,
`index()`, collection recreation, or forced rebuild.

The first deployment is allowed to report `api_ready=true` and
`retrieval_ready=false` while the standalone indexer builds the first
generation. When a previous generation exists, chat remains available while
the queue is active. Chat uses the loaded published generation immediately and
requests publication discovery asynchronously. Pending, processing, retrying,
and failed jobs cannot enter the query dependency graph or invalidate the prior
generation. Dense filters are pinned to the document versions and note
revisions listed by the same published snapshot.

## Durable Change Flow

Enterprise sync, enterprise uploads, personal uploads, chat attachments,
committed note revisions, deletes, metadata changes, and admin rebuilds all
feed `indexing_jobs`. Upload/note transactions create the durable row before
returning success. API-local wakeups are optional; the indexer continuously
polls PostgreSQL.

The indexer performs startup reconciliation, watches both roots, periodically
reconciles, renews leases, runs bounded extraction, cross-document/note
embedding, dedicated asynchronous verified Qdrant writes, and atomic BM25
publication. The bounded writer stage allows CPU extraction and GPU embedding
to continue while Qdrant network operations are in flight. Qdrant server mode
is mandatory for API-plus-indexer concurrency.

## API Contracts

- `GET /api/health`: API/retrieval/dependency/indexer readiness and safe queue
  summary.
- `GET /api/index/status` and `GET /api/indexer/status`: durable queue,
  heartbeat, adaptive-batch, CPU/GPU, throughput, and generation state.
- `POST /api/corpus/sync`: authorized `202` reconciliation request.
- `POST /api/index/rebuild`: authorized, confirmed `202` rebuild request.
- `GET /api/chat/debug`: authenticated, content-free query timing, loaded
  generation, and safe queue snapshot.
- `GET /api/system/status`: authenticated real-time assistant dependency,
  published-generation, queue/worker, model, GPU, timestamp, and component
  latency contract with green/blue/yellow/red overall state.
- `GET /api/admin/system/monitor`: administrator-only combined operational
  snapshot from dependency probes, durable indexing state, worker CPU/GPU
  telemetry, model diagnostics, and query timings.
- `GET /api/admin/system/stream`: administrator-only credentialed SSE stream of
  the same snapshot plus bounded structured runtime transition events.
- upload/note routes: return persistence independently from background index
  readiness.

All existing chat, streaming, citation, preview, auth, RBAC, workspace,
summary, saved-knowledge, export, and prompt-profile contracts remain in their
existing routes/services.

## Frontend

The frontend treats `chat_available` from `/api/system/status` as the live chat
gate. A non-empty queue shows a non-blocking blue status/banner and does not
disable chat. File upload rows appear
immediately and poll their document status until ready or failed. Note
Saving/Saved state remains database persistence; note `indexing_status` is a
separate AI-index state.

Streaming assistant requests expose Connected, Validating request, Loading
published generation, Searching knowledge, Reranking sources, Generating
answer, Completed, and Failed states. Stage details show only safe duration,
candidate count, and error state. A partial response identifies the degraded
stage, explains that available safe results were used, and retains Retry. Stop
aborts the browser stream
and propagates cancellation to the local generation loop. Both server and
browser terminate a request after 150 seconds, component failures provide safe
messages, loading state clears in `finally`, and failed requests retain an
explicit Retry action. The background banner means “Knowledge updating in
background”; assistant answers continue from the latest published index.

The live backend query path never executes corpus load, chunking, embedding,
index construction, or published BM25 rebuilding. Retrieval component ceilings
are dense/Qdrant 30 seconds, BM25 10 seconds, fusion 5 seconds, reranking
15 seconds, and evidence selection 5 seconds. The stream exposes the exact
failed stage and timeout state while preserving partial authorized results
where a safe fallback exists.

Enter and Send use the same single-flight handler. It refreshes the authenticated
status before opening the chat stream, permits blue/indexing state, retains
composer text when preflight or connection initiation fails, and clears the
draft only after a successful streaming response has been established.

The AI Operations Console lives at `/admin/system-monitor`, outside the normal
AI Assistant surface. The route and its sidebar link require
`monitor_system` or `manage_settings`; other authenticated users see a 403
access-denied page and do not open telemetry requests. The page consumes a
credentialed snapshot followed by SSE, reconnects with bounded exponential
backoff, detects stale data, and preserves last-known values during component
or connection failures. Green, blue, yellow, and red mean healthy, updating,
degraded, and unavailable respectively.

The console does not derive generation timings in the browser. FastAPI
publishes millisecond values measured at real generation events. First-token
latency is the monotonic first-token timestamp minus generation start;
generation latency is the matching completion timestamp minus generation
start. Ollama-native load, prompt-evaluation, and total durations are converted
once from nanoseconds to milliseconds. Backend guards discard negative,
non-finite, stale, or component timings larger than the measured generation or
request. The frontend repeats the boundary check for display and renders
missing/rejected values as `Unavailable`.

## Commands

```powershell
scripts\start_qdrant.bat
scripts\start_backend.bat
scripts\start_indexer.bat
scripts\start_frontend.bat
```

`Launch-CIAL-Knowledge-OS.bat` starts/checks all dependencies, runs Alembic,
starts backend and indexer independently, starts the frontend, and opens login
after API/frontend readiness. It warns if the indexer does not publish a fresh
heartbeat, but continues serving an existing committed generation.
`scripts\launch_all.bat` delegates to this same production launcher.

## Shared GPU Runtime

The query process defaults BGE-M3 to CPU so it does not retain a second CUDA
copy. The standalone indexer retains GPU batches, releases its model from CUDA
when idle, and yields between bounded batches while chat holds priority.
Ollama uses an explicit keep-alive and remains the latency-priority workload.
These rules do not alter scores, payloads, BM25, prompts, citations, or
published generations.

A stopped, stale, or restarting indexer changes indexing status to degraded but
does not change `chat_available` when PostgreSQL, Qdrant, Ollama, and an already
loaded valid generation remain available.

Ollama is explicitly invoked with all GPU layers requested and a 30-minute
keep-alive. During generation the operations monitor displays measured
processor placement, CPU-offload detection, Ollama VRAM, total VRAM, average
and peak GPU utilization, first-token latency, model-load time, and output
throughput. Ollama does not expose the actual offloaded layer count through its
process API, so that field remains unavailable instead of being inferred from
memory percentages.

When generation ends, the chat-priority lease is released and the next pending
embedding batch unloads the warm Ollama runner and returns BGE-M3 to CUDA
immediately. With no pending batch, Ollama may retain its configured warm
window. A warm runner never extends exclusive generation priority beyond the
active request. Durable indexing, verification, BM25 publication, and query
isolation are unchanged.
