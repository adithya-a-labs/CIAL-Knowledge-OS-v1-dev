# CIAL Knowledge OS

Integrated repository for the CIAL Knowledge OS migration.

Current structure:

- `services/knowledge-engine/` - deterministic Phase 4.5 backend package, scripts, tests, and backend documentation.
- `frontend/` - migrated React/Vite dashboard frontend and API client reference files.
- `docs/architecture/` - migration manifests used as the audit source of truth.
- `data/` - benchmark/manual QA assets and optional test corpus; runtime stores and enterprise corpus mounts must remain uncommitted.

See `MIGRATION_VERIFICATION_REPORT.md` for the latest migration audit status before backend/frontend integration.

## Local Development

Backend API:

```powershell
python -m pip install -e services/knowledge-engine
python -m pip install fastapi uvicorn python-multipart
uvicorn backend.app.main:app --reload
```

Frontend:

```powershell
cd frontend
pnpm install
pnpm run dev
```

Validation:

```powershell
curl.exe http://localhost:8000/api/health
curl.exe http://localhost:8000/api/documents
cd frontend
pnpm run typecheck
pnpm run build
```

Full-stack integration notes are in `docs/architecture/FULL_STACK_INTEGRATION.md`.
