# CIAL Knowledge OS

Integrated repository for the CIAL Knowledge OS migration.

Current structure:

- `services/knowledge-engine/` - deterministic Phase 4.5 backend package, scripts, tests, and backend documentation.
- `frontend/` - migrated React/Vite dashboard frontend and API client reference files.
- `docs/architecture/` - migration manifests used as the audit source of truth.
- `data/` - benchmark/manual QA assets and optional test corpus; runtime stores and enterprise corpus mounts must remain uncommitted.

Metadata/control-plane storage uses PostgreSQL through SQLAlchemy and Alembic.
Authenticated conversation history is authoritative in PostgreSQL
`chat_sessions`/`chat_messages`; browser storage is limited to UI preferences
and transient context handoff and must never seed or replace chat history.
Original source files remain in the configured enterprise repository
(`CIAL_CORPUS_ROOT`, `CORPUS_ROOT`, or `data/config/application.json`), and
vectors/chunk embeddings remain in Qdrant. If no repository configuration
exists, the backend falls back to the development path `data/files`. See
`docs/architecture/METADATA_DATABASE.md`.

Private Notes, immutable grounded Summary artifacts, and authenticated NDJSON
generation progress are documented in
`docs/architecture/NOTES_SUMMARIES_STREAMING.md`.

The backend Corpus layer synchronizes the configured repository into PostgreSQL
metadata and exposes `GET /api/corpus/*` endpoints for Knowledge Center-style
browsing. The frontend should consume the Corpus API rather than scanning the
filesystem. See `docs/architecture/CORPUS_ARCHITECTURE.md`.

See `MIGRATION_VERIFICATION_REPORT.md` for the latest migration audit status before backend/frontend integration.

## Local Development Commands

From the repository root:

```powershell
scripts\start_qdrant.bat
scripts\start_backend.bat
scripts\start_frontend.bat
```

PowerShell variants are also available:

```powershell
.\scripts\start_backend.ps1
.\scripts\start_frontend.ps1
```

`scripts\start_backend.bat 8010` or `.\scripts\start_backend.ps1 -Port 8010`
starts the backend on a custom port.

The Qdrant compose file maps host port `6335` to container port `6333`, so use
`CIAL_QDRANT_URL=http://localhost:6335` when running that local compose stack.

## Manual Fallback

Backend API:

```powershell
python -m pip install -e services/knowledge-engine
python -m pip install fastapi uvicorn python-multipart
cd services/knowledge-engine
..\..\.venv\Scripts\activate
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
pnpm install
pnpm run dev
```

Validation:

```powershell
cd services/knowledge-engine
..\..\.venv\Scripts\python.exe -m alembic upgrade head
cd ..\..
curl.exe http://localhost:8000/api/health
curl.exe http://localhost:8000/api/corpus/tree
curl.exe -X POST http://localhost:8000/api/corpus/sync
curl.exe http://localhost:8000/api/documents
cd frontend
pnpm run typecheck
pnpm run build
```

Full-stack integration notes are in `docs/architecture/FULL_STACK_INTEGRATION.md`.
