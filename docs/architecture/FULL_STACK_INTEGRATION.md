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
published generation, Searching, Reranking, Generating, Completed, and Failed
states. Stop aborts the browser stream
and propagates cancellation to the local generation loop. Both server and
browser terminate a request after 150 seconds, component failures provide safe
messages, loading state clears in `finally`, and failed requests retain an
explicit Retry action. The background banner means “Knowledge updating in
background”; assistant answers continue from the latest published index.

Enter and Send use the same single-flight handler. It refreshes the authenticated
status before opening the chat stream, permits blue/indexing state, retains
composer text when preflight or connection initiation fails, and clears the
draft only after a successful streaming response has been established.

## Commands

```powershell
scripts\start_qdrant.bat
scripts\start_backend.bat
scripts\start_indexer.bat
scripts\start_frontend.bat
```

`Launch-CIAL-Knowledge-OS.bat` starts/checks all dependencies, runs Alembic,
starts backend and indexer independently, starts the frontend, and opens login
after API/frontend readiness plus a fresh indexer heartbeat.
`scripts\launch_all.bat` delegates to this same production launcher.
