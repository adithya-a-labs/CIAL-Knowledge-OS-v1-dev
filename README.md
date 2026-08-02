# CIAL Knowledge OS

Integrated repository for the CIAL Knowledge OS migration.

Current structure:

- `services/knowledge-engine/` - deterministic Phase 4.5 backend package, scripts, tests, and backend documentation.
- `frontend/` - migrated React/Vite dashboard frontend and API client reference files.
- `docs/architecture/` - migration manifests used as the audit source of truth.
- `data/` - benchmark/manual QA assets and optional test corpus; runtime stores and enterprise corpus mounts must remain uncommitted.

Metadata/control-plane storage uses PostgreSQL through SQLAlchemy and Alembic.
PostgreSQL also provides the durable continuous-indexing queue, worker leases,
heartbeats, and committed index-generation pointer. The production indexer is
a standalone process; ordinary FastAPI startup never scans or rebuilds the
corpus. See `docs/architecture/CONTINUOUS_INDEXING_ARCHITECTURE.md`.
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
scripts\start_indexer.bat
scripts\start_frontend.bat
```

PowerShell variants are also available:

```powershell
.\scripts\start_backend.ps1
.\scripts\start_indexer.ps1
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

Standalone indexer (a second terminal):

```powershell
cd services/knowledge-engine
$env:PYTHONPATH="$PWD;$PWD\src"
..\..\.venv\Scripts\python.exe backend\indexer_main.py
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
curl.exe http://localhost:8000/api/index/status
curl.exe http://localhost:8000/api/documents
cd frontend
pnpm run typecheck
pnpm run build
```

Full-stack integration notes are in `docs/architecture/FULL_STACK_INTEGRATION.md`.
Measured CPU/GPU placement, benchmarks, the VRAM budget, and troubleshooting
are in `docs/architecture/GPU_WORKLOAD_PLACEMENT.md`.

## Optional Windows Hotspot LAN Server Mode

`Launch-CIAL-Knowledge-OS.bat --lan` keeps FastAPI, PostgreSQL, Qdrant,
Ollama, and Vite on loopback and publishes only the production frontend plus
same-origin `/api/*` through an interface-bound Caddy gateway. The mode is
disabled by default and waits safely when Windows Mobile Hotspot is absent.
Its target URL is `http://cial-knowledge-os.local` with a detected hotspot-IP
fallback. Managed firewall and mDNS publication apply only to the detected
hotspot interface/subnet.

Explicit `CIAL_LAN_BIND_INTERFACE`/`CIAL_LAN_BIND_IP` values take precedence
over automatic hotspot heuristics and must identify one Up interface with one
safe private IPv4 address. Repeated starts are idempotent, use only the
repository `.venv`, and retain a readable PID record plus an OS lock. Use
`.\scripts\stop_lan_gateway.ps1` for owned Caddy, mDNS, firewall, and lock
cleanup; it never searches for and kills arbitrary Python or Caddy processes.

Caddy must be installed and `CIAL_CADDY_PATH` must identify `caddy.exe`.
HTTP is the controlled-hotspot default; HTTPS is opt-in and requires client
trust provisioning for Caddy's local CA. See
`docs/architecture/LAN_SERVER_ACCESS.md` for configuration, threat model,
status fields, shutdown behavior, and validation limits.
