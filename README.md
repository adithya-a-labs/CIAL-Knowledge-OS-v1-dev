# CIAL Knowledge OS

Integrated repository for the CIAL Knowledge OS migration.

Current structure:

- `services/knowledge-engine/` - deterministic Phase 4.5 backend package, scripts, tests, and backend documentation.
- `frontend/` - migrated React/Vite dashboard frontend and API client reference files.
- `docs/architecture/` - migration manifests used as the audit source of truth.
- `data/` - benchmark/manual QA assets and optional test corpus; runtime stores and enterprise corpus mounts must remain uncommitted.

Metadata/control-plane storage uses PostgreSQL through SQLAlchemy and Alembic.
Original source files remain in `data/files`, and vectors/chunk embeddings
remain in Qdrant. See `docs/architecture/METADATA_DATABASE.md`.

The backend Corpus layer synchronizes `data/files` into PostgreSQL metadata and
exposes `GET /api/corpus/*` endpoints for Knowledge Center-style browsing. The
frontend should consume the Corpus API rather than scanning the filesystem.
See `docs/architecture/CORPUS_ARCHITECTURE.md`.

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
curl.exe http://localhost:8000/api/documents
cd frontend
pnpm run typecheck
pnpm run build
```

Full-stack integration notes are in `docs/architecture/FULL_STACK_INTEGRATION.md`.
