# Metadata Database

Status: development foundation for the CIAL Knowledge OS metadata/control plane.

PostgreSQL stores metadata only. It does not replace the filesystem document
store and does not replace Qdrant vector storage.

## Responsibilities

- Filesystem `data/files`: original uploaded/source documents.
- Qdrant: vectors and chunk embeddings.
- PostgreSQL: organizations, users, folder/document metadata, permissions,
  chat history, audit events, ingestion runs, indexing jobs, and Qdrant chunk
  references.

## Runtime Behavior

The backend reads `DATABASE_URL` from `services/knowledge-engine/backend/.env`.
If PostgreSQL is unavailable, FastAPI still starts and `/api/health` reports:

- `database_ready=false`
- `database_configured=true` when `DATABASE_URL` exists
- `database_message` with the connection failure

The API may start and serve a previously loaded retrieval generation during a
temporary PostgreSQL outage, but continuous indexing requires PostgreSQL.
Without it the indexer stops durable claims, leases, finalization, and
generation publication. It never continues vector work that cannot be
finalized.

Chat never waits for PostgreSQL generation discovery. It serves the loaded
published generation while a single-flight daemon check looks for a newer
valid pointer. Missing metadata before the first publication is controlled
unavailability; missing or failed update metadata after publication preserves
the previous generation.

## Migration

Run from `services/knowledge-engine`:

```powershell
..\..\.venv\Scripts\python.exe -m alembic upgrade head
```

The initial migration creates 19 tables:

- Identity: `organizations`, `departments`, `designations`, `users`, `roles`,
  `user_roles`
- Knowledge: `folders`, `documents`, `document_versions`, `document_chunks`,
  `folder_permissions`, `document_permissions`
- Operations: `ingestion_runs`, `indexing_jobs`, `audit_events`
- Conversations: `chat_sessions`, `chat_messages`, `saved_contexts`,
  `conversation_feedback`

## Seed Data

The initial migration seeds:

- Organization: `CIAL`
- Roles: `Super Admin`, `Knowledge Admin`, `Department Admin`, `Uploader`,
  `Reviewer`, `Viewer`
- System user: `system@cial.local`

The development login flow is backed by the `users` and `user_credentials` tables. Successful local signup/login issues an HttpOnly backend session cookie, and frontend startup restores identity through `GET /api/auth/me`.

## Non-Goals

- No embeddings in PostgreSQL.
- No source files in PostgreSQL.
- No Qdrant replacement.
- No prompt, retrieval, reranking, or generation behavior changes.
- No Dockerization.
- No Phase 5 functionality.

## Continuous Indexing Control Plane

PostgreSQL now owns `indexing_jobs`, `indexer_workers`, and
`index_generations`. Source bodies remain on disk and vectors remain in
Qdrant. Revision `20260724_0016` is additive and backfills legacy job targets,
operations, and statuses. See
[Continuous Indexing Architecture](CONTINUOUS_INDEXING_ARCHITECTURE.md).

Revision `20260725_0017` adds `chunk_hash`, `embedding_model_version`, and
`chunking_version` to `document_chunks`. These values are metadata only; they
allow the worker to retrieve and reuse a verified existing Qdrant vector for
unchanged chunks without storing embeddings in PostgreSQL.
