# Proposed CIAL API contracts

Architecture only; no backend changes are made.

## Notebook and context

- `POST /api/notebooks` -> `{id, title, workspace_id, created_at}`
- `GET /api/notebooks/{id}` -> shell, selected context, latest conversation, jobs
- `PATCH /api/notebooks/{id}` -> title/preferences with optimistic version
- `PUT /api/notebooks/{id}/context` -> `{document_ids, folder_ids}`
- `GET /api/notebooks/{id}/sources` -> Corpus metadata plus indexing/readiness

All IDs are server-authorized. Folder expansion and path resolution remain in
Corpus services; the frontend never submits filesystem paths.

## Chat

- `POST /api/notebooks/{id}/chat/stream`
  - request: `{question, session_id, selected_document_ids,
    selected_folder_ids, profile, response_length}`
  - events: `connected`, `validating`, `loading_generation`, `searching`,
    `reranking`, `generating`, `citation`, `completed`, `failed`, `cancelled`
  - terminal payload persists message IDs, citations, safe diagnostics, and
    degraded stage; never raw prompts or unauthorized evidence.

## Citations and preview

Reuse `GET /api/corpus/document/{id}/preview?page=&chunk_id=` and file/view routes.
Citation DTO: `{citation_id, document_id, page, chunk_id, label, excerpt_available}`.
Authorization is re-evaluated on every resolve.

## Notes

- `POST /api/notebooks/{id}/notes`
- `PATCH /api/notebooks/{id}/notes/{note_id}` with version/updated_at
- `DELETE /api/notebooks/{id}/notes/{note_id}` with audit event
- optional `POST .../{note_id}/commit-source` to create a versioned private source

Database save and indexing state are separate.

## Artifact jobs

- `POST /api/notebooks/{id}/artifacts` -> `202 {job_id, artifact_type, status}`
- `GET /api/notebooks/{id}/artifacts`
- `GET /api/notebooks/{id}/artifacts/{artifact_id}`
- `GET /api/notebooks/{id}/artifacts/stream` -> SSE job transitions
- `POST .../{job_id}/cancel` and `/retry`
- `DELETE .../{artifact_id}` with confirmation and audit

Artifacts are written below an authorized workspace output root; PostgreSQL owns
metadata and status. Errors are typed: `not_ready`, `forbidden`, `source_changed`,
`generation_timeout`, `generation_failed`, `cancelled`, `artifact_unavailable`.

## Authorization

Every endpoint requires authenticated access context, notebook/workspace access,
current ACL/RBAC resolution, owner isolation for personal workspaces, and audit
events for share/delete/export. Sharing APIs remain deferred until grant,
revocation, expiry, inheritance, and notification contracts are approved.
