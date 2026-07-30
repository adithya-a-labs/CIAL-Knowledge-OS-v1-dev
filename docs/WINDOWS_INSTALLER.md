# CIAL Knowledge OS Windows Installer

This repository includes a production-oriented Windows installer and daily
launcher:

- `Install-CIAL-Knowledge-OS.bat`
- `Install-CIAL-Knowledge-OS.ps1`
- `Launch-CIAL-Knowledge-OS.bat`
- `Launch-CIAL-Knowledge-OS.ps1`

## Install

Run from the repository root:

```bat
Install-CIAL-Knowledge-OS.bat
```

Run the installer as Administrator. It writes timestamped logs under:

```text
outputs\installer\logs
```

The installer verifies or installs prerequisites with `winget`, creates the
Python 3.11 virtual environment, installs CUDA-enabled PyTorch, installs backend
dependencies from `services\knowledge-engine\requirements.txt`, resolves Node,
npm, Corepack, and pnpm from the verified Node.js installation, installs
frontend dependencies with `pnpm install --frozen-lockfile`, builds and
typechecks the frontend, starts PostgreSQL/Qdrant/Ollama, runs Alembic,
validates CUDA, and then launches the application.
The canonical requirements already include `watchdog`. Alembic revision
`20260724_0016` adds queue leases, worker heartbeats, and index generations.

To verify a true clean frontend dependency installation:

```bat
Install-CIAL-Knowledge-OS.bat -VerifyCleanFrontendInstall
```

That mode temporarily moves `frontend\node_modules`, performs a locked install
with the installer-resolved pnpm executable, runs the production build and
typecheck, then restores the original `node_modules` directory.

If the first detected Node.js installation is NVM-managed and both npm and
Corepack fail validation, the installer does not repair NVM. It prompts the
administrator to install official Node.js LTS side-by-side through `winget`,
refreshes PATH, and retries with `C:\Program Files\nodejs`.

To pass the first-run enterprise repository non-interactively:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\Install-CIAL-Knowledge-OS.ps1 -CorpusRepositoryPath "D:\CIAL\KnowledgeRepository"
```

If `data\config\application.json` already contains a valid enabled
`enterprise` repository, the installer preserves it. The installer does not set
`CIAL_CORPUS_ROOT`, so saved app config remains in the verified precedence:

1. `CIAL_CORPUS_ROOT` / `CORPUS_ROOT`
2. saved app config
3. deprecated `CIAL_DATA_DIR`
4. `data/files` development fallback

Enterprise documents are indexed in place. They are not copied into this
application directory.

## Daily Launch

Run:

```bat
Launch-CIAL-Knowledge-OS.bat
```

The launcher does not reinstall dependencies. It verifies the configured
repository, starts Docker/PostgreSQL/Qdrant/Ollama only when needed, starts the
backend, standalone indexer, and frontend independently, waits for API/frontend
readiness and a fresh indexer heartbeat (not queue drain), and opens:

```text
http://127.0.0.1:5173/login
```

Runtime logs are written under:

```text
outputs\launcher\logs
```

Backend, indexer, and frontend stdout/stderr use separate timestamped files.
The launcher applies `alembic upgrade head` before starting the API. It does
not force a rebuild when a valid generation exists. Qdrant server mode is
required because API and indexer are concurrent processes.

## Default Ports

- Backend: `8000`
- Frontend: `5173`
- PostgreSQL: from `DATABASE_URL`, installer default `5432`
- Qdrant: `6335`
- Ollama: `11434`

Use PowerShell parameters to override backend/frontend ports:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\Launch-CIAL-Knowledge-OS.ps1 -BackendPort 8000 -FrontendPort 5173
```

## Safety

The scripts are designed to be rerunnable. They preserve:

- PostgreSQL Docker volume `cial_postgres_data`
- Qdrant Docker volume `cial_qdrant_storage`
- existing valid `data\config\application.json`
- Ollama model cache
- Hugging Face model cache
- existing enterprise repository files

The installer stops if CUDA is unavailable to PyTorch. It never intentionally
continues in CPU-only mode.

When `CIAL_INDEXER_DEVICE=cuda`, indexer startup also fails if the embedding
model is not actually on CUDA. `auto` may choose CPU on a machine without
CUDA. The actual model device is published through `/api/index/status`.

## Optional LAN Support Verification

`-VerifyLanSupport` adds fail-fast checks for an operator-installed Caddy
binary and the Python LAN dependencies. Caddy is intentionally not silently
downloaded by the daily launcher. Configure `CIAL_CADDY_PATH` with the
approved `caddy.exe` location before enabling LAN mode.

The normal install remains local-only. `Launch-CIAL-Knowledge-OS.bat --lan`
builds the production frontend if needed, starts the ordinary loopback stack,
then starts the supervised gateway. Re-running the launcher is idempotent; the
manager lock prevents duplicate gateway ownership, and the stop script removes
only CIAL-owned mDNS, firewall, keep-awake, process-marker, and QR state. Caddy
certificate state is preserved and, for HTTPS, must pass exact app-owned ACL
verification before the gateway can start.
