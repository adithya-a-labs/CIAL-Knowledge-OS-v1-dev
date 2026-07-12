# CIAL Knowledge OS One-Click Windows Installer

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

After cloning or downloading the complete repository, right-click
`Install-CIAL-Knowledge-OS.bat` and choose **Run as administrator**. No terminal
commands are required. The installer writes timestamped logs under:

```text
outputs\installer\logs
```

The installer performs a hardware, disk, internet, Windows, NVIDIA, and
repository preflight; verifies or installs prerequisites with `winget`; creates the
Python 3.11 virtual environment, installs CUDA-enabled PyTorch, installs backend
dependencies from `services\knowledge-engine\requirements.txt`, resolves Node,
npm, Corepack, and pnpm from the verified Node.js installation, installs
frontend dependencies with `pnpm install --frozen-lockfile`, builds and
typechecks the frontend, starts PostgreSQL/Qdrant/Ollama, downloads missing
Ollama and Hugging Face models, runs Alembic, validates CUDA, runs acceptance
tests, and then launches the application.

The release installation always proves the frontend from the locked dependency
graph. `-VerifyCleanFrontendInstall` additionally preserves and moves an existing
`node_modules` directory while it proves a second clean install.

To explicitly repeat the isolated clean frontend dependency verification:

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

## Restart and resume

State is persisted in `outputs\installer\runtime\install-state.json`. If Windows,
Docker Desktop, or WSL requires a restart, the installer writes the last safe
state and registers a per-user `RunOnce` action. It resumes at the next login.
Rerunning `Install-CIAL-Knowledge-OS.bat` is also safe and preserves database,
Qdrant, repository, and model data.

The state schema records each stage's last action (`skipped`, `installed`,
`repaired`, or `verified`), verification timestamp, executable paths, versions,
dependency fingerprints, and component-specific results. A completed stage is
not trusted blindly: every rerun revalidates it and repairs it only when its
current health or fingerprint no longer matches.

Idempotent checks include:

- Python 3.11 interpreter and pip health before preserving `.venv`
- exact CUDA Torch version/build/device visibility
- backend requirements and `pyproject.toml` fingerprint plus `pip check`
- frontend `package.json`, lockfile, and pnpm-version fingerprint
- Ollama model presence before pull
- offline Hugging Face snapshot loading before any network download
- authenticated PostgreSQL access before container repair guidance
- Qdrant identity/version and existing-container preservation
- current Alembic revision before running `upgrade head`

Invalid virtual environments are renamed with a timestamp instead of deleted.
CPU-only or wrong-version Torch packages are removed only from the repository
virtual environment before the pinned CUDA build is installed. No global Python
packages are used.

Component logs for Docker, PostgreSQL, Qdrant, Torch, backend dependencies,
Ollama/model downloads, Hugging Face models, OCR/rendering, Alembic, frontend
build/typecheck, and acceptance are grouped under the install timestamp in:

```text
outputs\installer\logs\<timestamp>
```

## Models and offline runtime

First installation temporarily allows online Hugging Face access and downloads:

- `gemma3:12b` through Ollama
- `BAAI/bge-m3`
- `cross-encoder/ms-marco-MiniLM-L-6-v2`

The embedding and reranker models must load on CUDA. Only after successful
download and CUDA smoke tests does the installer enable Transformers/Hugging
Face offline mode. Existing valid caches and Ollama models are reused.

## Database safety

PostgreSQL runs in the persistent `cial_postgres_data` volume. The installer
performs an authenticated connection, `SELECT 1`, database-name check, and
dynamic Alembic-head verification. It never deletes or reinitializes an existing
volume. If its stored credentials conflict with an existing initialized volume,
installation stops with a repair explanation instead of deleting data.

New Qdrant installations use the pinned `qdrant/qdrant:v1.18.2` image. If an
existing installer-managed Qdrant container is present, the scripts start that
container without replacing its image, avoiding an implicit storage-format
upgrade. Existing Qdrant 1.15 through 1.18 servers are identity/version checked
and preserved. Other versions stop with a compatibility error rather than an
automatic data-format change. Named volumes and collections are never cleared.

## Acceptance and reports

The post-install verifier is `scripts\verify_windows_installation.ps1`. It checks
application identity, PostgreSQL, frontend identity, signup/login/session/logout,
logged-out protection, repository activation and isolation, corpus sync,
retrieval, citations, Qdrant/model readiness, and a cited PDF endpoint when a
suitable PDF citation exists.

Human-readable and JSON reports are written under:

```text
outputs\installer\reports
```

The installer prints **System Ready** only when all mandatory acceptance checks
pass. When a citation contains a PDF document ID and page, the verifier opens
Microsoft Edge through Playwright and confirms that native PDF navigation keeps
the exact `#page=N` target. It reports PDF navigation as uncertified when no
suitable cited PDF with page metadata is available.

## Daily Launch

Run:

```bat
Launch-CIAL-Knowledge-OS.bat
```

The launcher does not reinstall dependencies. It verifies the configured
repository, starts Docker/PostgreSQL/Qdrant/Ollama only when needed, starts the
backend and frontend only when their ports are not already serving the exact
CIAL applications, verifies authenticated PostgreSQL access, required Ollama
and Hugging Face models, CUDA, and Alembic head, waits for readiness, and opens:

```text
http://127.0.0.1:5173/login
```

Runtime logs are written under:

```text
outputs\launcher\logs
```

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

The installer and launcher stop if CUDA is unavailable to PyTorch. They never
intentionally continue in CPU-only mode. Neither script deletes Docker volumes,
Qdrant collections, model caches, database data, or enterprise documents.
