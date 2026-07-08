# CIAL Knowledge OS

Integrated repository for the CIAL Knowledge OS migration.

Current structure:

- `services/knowledge-engine/` - deterministic Phase 4.5 backend package, scripts, tests, and backend documentation.
- `frontend/` - migrated React/Vite dashboard frontend and API client reference files.
- `docs/architecture/` - migration manifests used as the audit source of truth.
- `data/` - benchmark/manual QA assets and optional test corpus; runtime stores and enterprise corpus mounts must remain uncommitted.

See `MIGRATION_VERIFICATION_REPORT.md` for the latest migration audit status before backend/frontend integration.
