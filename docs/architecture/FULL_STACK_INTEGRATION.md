# Full-Stack Integration

Status: development integration only. This is not Dockerization, production handover, authentication, or Phase 5.

## Architecture

```text
React/Vite frontend
  -> frontend/src/api/client.ts
  -> FastAPI backend/app
  -> backend/app/services/*
  -> services/knowledge-engine/src/cial_knowledge_os Phase 4.5 engine
  -> local data/files, data/indexes, data/qdrant, outputs
```

Routes stay thin and call services. Retrieval, reranking, evidence selection, context building, generation, citations, exports, OCR, and indexing remain in the migrated Phase 4.5 engine.

## Backend Routes

- `GET /api/health` reports API status and whether the Phase 4.5 engine can be imported.
- `POST /api/chat` calls `KnowledgeEngineService.answer_question()` and adapts the Phase 4 response into answer, citations, source chunks, and metadata.
- `GET /api/documents` lists files discovered under `data/files`.
- `POST /api/documents/upload` saves uploaded files to `data/files`.
- `POST /api/index/rebuild` runs a synchronous development index rebuild through the engine service.
- `GET /api/index/status` returns in-process indexing status.
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

`backend/app/services/knowledge_engine_service.py` is the only new backend module that imports the engine. It adds `services/knowledge-engine/src` to `sys.path`, lazily creates `Phase4RAGPipeline`, calls `pipeline.run(question)`, and converts the existing response contract into API schemas.

If Qdrant, Ollama, embeddings, reranker weights, Python packages, or an index are unavailable, the service returns a controlled API error instead of moving retrieval logic into route files.

## Mock Data Still In Use

- Dashboard, analytics, experts, departments, FAQs, learning, workspace, and most Knowledge Center drive data still use `frontend/src/data/*`.
- `DocumentsPage` uses `GET /api/documents` when available and falls back to `DOCUMENTS`.
- `ChatPanel` now calls `POST /api/chat`; it does not use mock answer generation.
- The document upload modal UI is still mostly presentational. The chat attachment control uses `POST /api/documents/upload`.

## Known Limitations

- `frontend/pnpm-lock.yaml` still needs regeneration after the migrated dependency graph changed.
- Python is not available in the current shell, so backend compile/import checks were not completed here.
- Frontend dependencies are not installed in this workspace, so typecheck/build require an approved install first.
- Evaluation endpoints are API placeholders around local artifact discovery; full evaluation execution should continue through the existing Phase 4 runner until a dedicated service workflow is designed.
- Index rebuild is synchronous in this development adapter. Move it to a durable job queue only during a later backend hardening phase.

## Local Run Commands

Backend setup:

```powershell
python -m pip install -e services/knowledge-engine
python -m pip install fastapi uvicorn python-multipart
uvicorn backend.app.main:app --reload
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
