# Full-Stack Integration

Status: development integration only. This is not Dockerization, production handover, authentication, live orchestration, reporting, or Phase 5.

## Architecture

```text
React/Vite frontend
  -> frontend/src/api/client.ts
  -> services/knowledge-engine/backend/app
  -> services/knowledge-engine/backend/app/services/*
  -> services/knowledge-engine/src/cial_knowledge_os Phase 4.5 engine
  -> local data/files, data/indexes, data/qdrant, outputs
```

Routes stay thin and call services. Retrieval, reranking, evidence selection, context building, generation, citations, exports, OCR, and indexing remain in the migrated Phase 4.5 engine.

The real FastAPI backend source is `services/knowledge-engine/backend/app`.
The root-level `backend/` directory is not importable and contains only a
migration note.

## Startup Readiness Workflow

The FastAPI lifespan starts `StartupService.run_startup()` in-process. The service wrapper creates required runtime folders, detects documents, checks Qdrant, checks the configured Ollama model, builds `Phase4Config`, and initializes the long-lived `Phase4RAGPipeline`.

The startup indexing sequence intentionally mirrors `services/knowledge-engine/scripts/run_phase4_batch.py`:

```text
Build Phase4Config
Create Phase4RAGPipeline(config)
pipeline.load()
pipeline.chunk()
pipeline.embed()
pipeline.index()
load the Phase 4 reranker
keep the initialized pipeline in KnowledgeEngineService
```

The notebooks `04_Reranking_and_Evidence_Selection.ipynb` and `045_Multimodal_Test_Corpus_Evaluation.ipynb` remain architectural references only. The backend does not copy notebook cells and does not introduce Phase 5 planning or agent logic.

Required folders are created if missing:

- `data/files`
- `data/indexes`
- `data/bm25`
- `outputs`
- `models`

`CIAL_AUTO_INDEX_ON_STARTUP=true` enables automatic startup indexing. `CIAL_FORCE_REBUILD_ON_STARTUP=true` passes `force_rebuild_index=True` into `Phase4Config`. Manual rebuilds use the same service path via `POST /api/index/rebuild`. Backend environment examples live at `services/knowledge-engine/backend/.env.example`.

Startup readiness is updated at each wrapper stage: load, chunk, embed, index,
and reranker load. `documents_indexed` is updated immediately after
`pipeline.index()` completes, before reranker/model availability is finalized,
so a later model failure no longer leaves the API reporting zero indexed
documents without a useful stage message.

## Runtime State

`services/knowledge-engine/backend/app/core/runtime_state.py` tracks:

- `status`: `starting`, `ready`, `indexing`, `degraded`, `failed`, or `no_documents`
- `engine_available`
- `engine_ready`
- `documents_seen`
- `documents_indexed`
- `index_fresh`
- `qdrant_ready`
- `models_ready`
- `last_startup_check_at`
- `last_index_run_at`
- `message`

The backend process should stay up when Qdrant, Ollama, embeddings, reranker weights, or documents are missing. Those conditions are reflected in runtime state so the frontend can show a specific readiness message.

## Backend Routes

- `GET /api/health` reports runtime readiness, service identity, Phase 4.5, document counts, Qdrant state, model state, and message.
- `POST /api/chat` first checks `runtime_state.engine_ready`. If false, it returns HTTP 503 with structured detail such as `no_documents_found`, `indexing_in_progress`, `qdrant_unavailable`, `model_unavailable`, or `startup_failed`. If ready, it calls `KnowledgeEngineService.answer_question()` and adapts the Phase 4 response into answer, citations, source chunks, and metadata.
- `GET /api/documents` lists files discovered under `data/files`.
- `POST /api/documents/upload` saves uploaded files to `data/files`.
- `POST /api/index/rebuild` runs the same deterministic Phase 4.5 initialization/indexing path used by startup.
- `GET /api/index/status` returns the shared runtime state.
- `POST /api/evaluation/run` records an evaluation request. Full Phase 4 evaluation remains a manual runner workflow.
- `GET /api/evaluation/runs` lists evaluation and batch-answer artifacts under `outputs`.
- `GET /api/exports` lists export-like files under `outputs`.

## Frontend API Client

The frontend API boundary is centralized in:

- `frontend/src/api/client.ts`
- `frontend/src/api/types.ts`
- `frontend/src/api/adapters.ts`

`VITE_API_BASE_URL` defaults to `http://localhost:8000` in `frontend/.env.example`.

## Phase 4.5 Wrapper

`services/knowledge-engine/backend/app/services/knowledge_engine_service.py` is the backend module that imports the engine. It adds `services/knowledge-engine/src` to `sys.path`, builds `Phase4Config` from backend environment settings, keeps the startup-initialized `Phase4RAGPipeline` alive, calls `pipeline.run(question)`, and converts the existing response contract into API schemas.

If Qdrant, Ollama, embeddings, reranker weights, Python packages, or an index are unavailable, the service returns a controlled API error instead of moving retrieval logic into route files. Existing Phase 4 citation and source metadata are preserved as much as the Phase 4 response exposes them.

## Qdrant And Ollama Troubleshooting

- `qdrant_ready=false`: confirm `CIAL_QDRANT_MODE`, `CIAL_QDRANT_URL`, and `CIAL_QDRANT_API_KEY`. For server mode, start Qdrant before expecting chat readiness. The backend does not silently fall back to embedded Qdrant.
- `models_ready=false`: confirm Ollama is running and `CIAL_OLLAMA_MODEL_NAME` is installed. Embedding and reranker failures during startup indexing also prevent `engine_ready`.
- `no_documents`: add supported files under the configured `CIAL_DATA_DIR` and restart or call `POST /api/index/rebuild`.
- `indexing`: wait for `GET /api/health` or `GET /api/index/status` to return `ready`.

## Mock Data Still In Use

- Dashboard, analytics, experts, departments, FAQs, learning, workspace, and most Knowledge Center drive data still use `frontend/src/data/*`.
- `DocumentsPage` uses `GET /api/documents` when available, polls `GET /api/index/status`, and falls back to `DOCUMENTS`.
- `ChatPanel` calls `GET /api/health`, shows a backend readiness banner, disables send until `engine_ready=true`, and then calls `POST /api/chat`.
- The document upload modal UI is still mostly presentational. The chat attachment control uses `POST /api/documents/upload`.

## Known Limitations

- `frontend/pnpm-lock.yaml` still needs regeneration after the migrated dependency graph changed.
- The plain `python` command may not be on PATH; use `.venv\Scripts\python.exe` in this workspace.
- Frontend dependencies may need installation before `pnpm run typecheck` or `pnpm run build`.
- Evaluation endpoints are API placeholders around local artifact discovery; full evaluation execution should continue through the existing Phase 4 runner until a dedicated service workflow is designed.
- Index rebuild is synchronous in this development adapter. Move it to a durable job queue only during a later backend hardening phase.

## Local Run Commands

Preferred root-level commands:

```powershell
scripts\start_qdrant.bat
scripts\start_backend.bat
scripts\start_frontend.bat
```

PowerShell variants:

```powershell
.\scripts\start_backend.ps1
.\scripts\start_frontend.ps1
```

The backend still lives inside `services/knowledge-engine/backend/app`. The
root launchers only activate the root `.venv`, change into
`services/knowledge-engine`, and run the service-local `backend.app.main`.

`scripts\start_backend.bat 8010` or `.\scripts\start_backend.ps1 -Port 8010`
starts the backend on a custom port.

The Qdrant launcher uses `services/knowledge-engine/docker-compose.qdrant.yml`.
That compose file maps host port `6335` to container port `6333`; configure
`CIAL_QDRANT_URL=http://localhost:6335` when using it.

Manual backend setup:

```powershell
python -m pip install -e services/knowledge-engine
python -m pip install fastapi uvicorn python-multipart
cd services/knowledge-engine
..\..\.venv\Scripts\activate
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Because the directory name `knowledge-engine` contains a hyphen, the backend is
not launched as a dotted module from the repository root. Use the service
directory command above.

For this workspace shell, use:

```powershell
cd services/knowledge-engine
..\..\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend setup:

```powershell
cd frontend
pnpm install
pnpm run typecheck
pnpm run build
pnpm run dev
```

Smoke checks:

```powershell
curl.exe http://localhost:8000/api/health
curl.exe http://localhost:8000/api/documents
curl.exe http://localhost:8000/api/index/status
```

Chat smoke check:

```powershell
curl.exe -X POST http://localhost:8000/api/chat `
  -H "Content-Type: application/json" `
  -d "{\"question\":\"What documents are indexed?\",\"selected_document_ids\":[],\"response_length\":\"short\",\"include_sources\":true}"
```

## Next Steps Before Dockerization

1. Regenerate `frontend/pnpm-lock.yaml`.
2. Install backend/frontend dependencies in approved local environments.
3. Run backend compile/import checks and frontend typecheck/build.
4. Start backend and frontend together and smoke test health, documents, upload, chat, and graceful chat failure.
5. Decide whether indexing/evaluation should remain synchronous dev operations or become explicit background jobs.
