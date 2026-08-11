# Runtime Configuration and Secret Flow

This document is the source of truth for startup-time environment resolution.
Normal Windows startup must not depend on variables manually copied into a new
shell when those values already exist in protected server configuration.

## Server configuration precedence

Highest priority wins:

1. Variables explicitly present in the current process environment.
2. An optional protected file named by `CIAL_RUNTIME_ENV_FILE`.
3. `services/knowledge-engine/backend/.env` (the installer-managed protected
   runtime file and the normal development-local server file).
4. `services/knowledge-engine/.env` (legacy/development compatibility).
5. Repository-root `.env` (development compatibility).
6. Non-secret application defaults, where the Python settings model allows
   them.

`scripts/runtime_env.ps1` implements this order for Windows launchers.
`cial_knowledge_os.runtime_env` implements the same order for Python
entrypoints. Both parsers accept literal `KEY=VALUE` assignments, optional
matching quotes, values containing `=`, and paths containing spaces. They do
not expand variables or execute commands. Startup messages identify source
files but never print values.

`CIAL_RUNTIME_ENV_FILE` adds an operator-selected protected server file at the
highest file priority. It is server-side only. A missing selected file is an
error rather than a silent fallback.

## Migration credential isolation

`CIAL_MIGRATION_DATABASE_URL` is deliberately outside the normal server file
flow. Alembic receives it only for the migration subprocess, using this order:

1. explicit process `CIAL_MIGRATION_DATABASE_URL` for a one-off operator run;
2. protected `outputs/installer/runtime/migration.env`.

The launcher removes the variable after Alembic exits, including an explicit
operator override, before starting ordinary application processes. The backend,
indexer, Qdrant, frontend, and LAN manager do not load `migration.env`.
Alembic does not fall back to runtime `DATABASE_URL`; this preserves the
least-privilege runtime/migration role split.

## Environment-flow map

| Component | Required/configured variables | Loading mechanism | Missing behavior | Secret boundary |
|---|---|---|---|---|
| FastAPI backend | `DATABASE_URL`, `CIAL_AUTH_SECRET_KEY`, `CIAL_QDRANT_*`, model/offline, corpus, quotas/uploads/session, LAN and diagnostics | PowerShell loader for scripted startup; matching Python loader for direct startup/reload children | Settings fail closed in UAT/production; unavailable optional development services report unhealthy | Consumes runtime DB, auth, and Qdrant secrets; never exports them to the browser |
| Standalone indexer | `DATABASE_URL`, `CIAL_QDRANT_API_KEY`, Qdrant/indexer/model/offline/corpus settings | `start_indexer.ps1` imports the server environment; Python settings uses the same resolution | Script fails before launch when DB or Qdrant key is missing | Consumes runtime DB and Qdrant secrets, never migration credentials |
| Qdrant Compose | `CIAL_QDRANT_API_KEY` | `start_qdrant.ps1` imports server config into the Compose process; Compose retains required interpolation | Fails before Compose, and Compose independently rejects missing/empty key | Key enters only the trusted Qdrant container environment |
| Main launcher | Runtime DB/auth/Qdrant config plus runtime flags | Imports the shared server environment once before probes or child processes | Fails with variable names only; Python settings enforce the auth secret in UAT/production | Qdrant probe uses `api-key`; no value is transcribed to logs |
| Installer | Existing process overrides plus existing server files; creates missing install-time secrets only during installation | Shared parser; atomically updates protected backend and migration files | Preserves existing secrets; refuses to reuse runtime DB URL for missing migration credentials | Generates once when needed, never prints values |
| Alembic | `CIAL_MIGRATION_DATABASE_URL` | Scoped protected migration loader | Fails closed when absent | Migration credential is not accepted as runtime DB config |
| PostgreSQL provisioning | Protected migration URL for bootstrap; `DATABASE_URL` for the least-privilege app role | Installer scoped migration read and server runtime read | Existing deployments needing operator credentials stop with guidance | Runtime and migration credentials remain separate |
| LAN/Caddy manager | Normal server config plus `CIAL_LAN_*`, `CIAL_CADDY_PATH`; HTTPS/secure-cookie flags in secure modes | LAN launcher imports server config before starting Python manager | UAT/production HTTPS and cookie requirements remain fail closed | Caddy sees only configuration needed by the trusted gateway; browser sees same-origin HTTPS |
| Firewall manager | Explicit validated command arguments derived by the trusted LAN manager | No env-file parser; arguments are bounded/validated | Refuses unsafe or unverifiable scopes | No application secret required |
| Ollama/model checks | `CIAL_OLLAMA_*`/`OLLAMA_*`, `CIAL_LOCAL_FILES_ONLY`, `TRANSFORMERS_OFFLINE`, `HF_HUB_OFFLINE` | Inherited server environment and Python settings | UAT/production rejects inconsistent offline flags | No model setting is promoted to Vite |
| Evaluation/export/inspection scripts | Qdrant URL/key/collection and relevant model settings | Python server loader; explicit CLI arguments remain one-off overrides | Authenticated Qdrant calls fail clearly when credentials are absent/incorrect | Keys are read from server config, not embedded in reports |
| Frontend/Vite | Browser-safe `VITE_API_BASE_URL` and feature/public identity metadata only | Vite `frontend/.env`; production bundle enforces same-origin `/api` | No server secret fallback exists | Must never contain Qdrant, auth-signing, PostgreSQL, or migration credentials |

The trusted Qdrant path is:

```text
protected/local server configuration
    -> Qdrant Compose
    -> FastAPI
    -> standalone indexer
    -> trusted launcher/maintenance probes

browser -> same-origin FastAPI API only
```

There is no browser-to-Qdrant trust path.

## Protected and browser-safe variables

Protected examples include `CIAL_QDRANT_API_KEY`,
`CIAL_AUTH_SECRET_KEY`, `DATABASE_URL`, and
`CIAL_MIGRATION_DATABASE_URL`. They must not use a `VITE_` prefix, appear in
frontend files, command lines, logs, or generated reports.

Browser-safe variables are limited to public routing, public identity-provider
metadata, model display/version labels, and feature flags. A `VITE_` prefix is
an exposure declaration: Vite values are readable by every browser user.

## Fresh-shell operation

From a new CMD or PowerShell window, these commands resolve protected/local
server configuration automatically:

```bat
scripts\start_qdrant.bat
scripts\start_backend.bat
scripts\start_indexer.bat
Launch-CIAL-Knowledge-OS.bat
```

The PowerShell equivalents have identical precedence. `start_frontend` is
intentionally separate and never imports the server environment.

For direct manual Alembic operation, use a scoped operator environment or the
daily launcher. Do not copy the migration URL into `backend/.env`.
