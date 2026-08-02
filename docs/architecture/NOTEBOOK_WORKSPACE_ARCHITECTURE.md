# Notebook Workspace Architecture

Status: implementation contract for the first personal Notebook workspace release.

## Purpose and boundaries

A Notebook is a persistent, owner-scoped evidence workspace around existing
CIAL capabilities. It associates authorized source references, one ordinary
`chat_session`, existing private notes, and supported immutable summary
artifacts. It does not introduce a new retrieval pipeline, conversation store,
document viewer, note body store, indexer, prompt family, or vector write path.

The storage boundary remains unchanged:

- original documents stay in the configured enterprise repository or
  `CIAL_WORKSPACE_ROOT`;
- PostgreSQL owns notebook metadata, references, lifecycle, authorization
  relationships, and durable chat/note/summary associations;
- Qdrant and the published BM25 generation remain the retrieval stores;
- the standalone indexer remains the only extraction, embedding, Qdrant write,
  verification, cleanup, and publication owner.

## Domain model

Revision `20260802_0019` is additive and reversible.

`notebooks` stores the organization, workspace, owner, title, optional
description, private visibility, lifecycle, creators/updaters, soft deletion,
safe JSON metadata, and timestamps. The initial service creates personal
notebooks only and derives all ownership and security fields from the
authenticated principal and the principal's personal workspace.

`notebook_sources` stores references only. Exactly one target column is set for
each row: `document_id`, `note_id`, or `summary_artifact_id`. A target is unique
inside a notebook, ordered by `position`, and may be a default active source.
The row never stores a filesystem path, source body, embedding, or copied file.

`notebook_sessions` is a one-to-one association between a notebook and an
ordinary owned `chat_session`. `chat_sessions` and `chat_messages` remain the
only conversation system of record.

`notebook_artifacts` associates a notebook with a supported immutable
`summary_artifact` or note. It stores a bounded source-version snapshot,
lifecycle status, safe error code, and safe metadata. Generated content remains
owned by existing summary/note/export tables and services.

## Authorization

Every route requires `require_authenticated_access_context`. Personal
notebooks are selected by notebook id, owner user id, organization id,
`visibility='private'`, live lifecycle, and `deleted_at IS NULL`; inaccessible
ids return the same safe 404 used for absent ids.

Source attach and every subsequent source projection re-run current policy:

- documents use `apply_document_access_filter` and reject deleted, revoked, or
  unavailable rows;
- personal documents require ownership or an explicit current ACL; department
  classification never grants personal access;
- notes and summary artifacts require the current authenticated owner;
- chat submission is reauthorized by the existing chat route after notebook
  active ids map to `selected_document_ids` and `selected_note_ids`;
- preview continues through existing Corpus/workspace document routes, which
  reauthorize the document independently;
- artifact creation re-resolves all selected sources before calling the
  existing summary service.

Client supplied owner, organization, workspace, visibility, ACL, filesystem,
or lifecycle fields are ignored because they are absent from write schemas.

## API contracts

The notebook router follows existing typed FastAPI patterns:

- `GET /api/notebooks` lists current-owner notebooks with safe counts and last
  activity;
- `POST /api/notebooks` creates a personal notebook and its ordinary bound chat
  session transactionally;
- `GET`, `PATCH`, and `DELETE /api/notebooks/{id}` read, rename/update, and
  soft-delete;
- `GET` and `POST /api/notebooks/{id}/sources` list and attach authorized
  document, note, or summary references;
- `PATCH` and `DELETE /api/notebooks/{id}/sources/{source_id}` update default
  active state or detach;
- `POST /api/notebooks/{id}/sources/reorder` updates a complete, deduplicated
  order;
- `GET` and `POST /api/notebooks/{id}/chat-session` return or idempotently
  create the one owned chat binding;
- `GET` and `POST /api/notebooks/{id}/artifacts` list or start supported
  existing summary work;
- `GET` and `DELETE /api/notebooks/{id}/artifacts/{artifact_id}` read or remove
  the notebook association without inventing a second artifact store.

No notebook preview route or notebook chat stream route is added.

## Existing assistant reuse

The frontend embeds the existing `AssistantSessionsProvider` and `ChatPanel`.
The provider accepts a notebook-bound session id without changing ordinary
assistant navigation. The bound `chat_session` has `context_scope` set to
`selected_context`, and its selected document/note ids are synchronized from
the Notebook's explicit active sources. `ChatPanel` continues to call
`/api/chat/stream` through the NDJSON client, preserving per-request runtime,
bounded concurrency, independent Stop/Retry, capacity 429/Retry-After,
submission-order persistence, profiles, citations, status stages, and safe
failure behavior.

## Attached and active source semantics

Attached sources are all live references in `notebook_sources`. Active sources
are rows with `is_default_active=true` at the moment the user submits. The UI
shows both counts and never silently expands active scope to every attached
source. Updating active rows synchronizes the bound session's validated
selected ids. Not-ready, deleted, revoked, or failed sources remain visibly
unavailable and are excluded from effective chat context.

When no active source is selected, the workspace presents an explicit choice:
activate all currently ready attached sources, use normal authorized Corpus
search in a fresh ordinary assistant conversation, or cancel. It does not
choose a broader scope automatically.

## Upload and indexing flow

The source picker reuses `POST /api/workspaces/me/documents/upload`. The server
derives the personal workspace, owner, private visibility, storage key, version,
and durable `upsert_version` job. The Notebook attaches the returned document
reference immediately and projects real indexing state. The API never waits
for extraction or publication, and existing chat remains available from the
last committed generation while background work proceeds.

## State ownership

React Query owns notebook lists, detail, sources, artifacts, and chat binding
with stable keys. `AssistantSessionsProvider` continues to own only live chat
and hydrated PostgreSQL history. The shared viewer owns citation/page/highlight
state. Existing notes components own note editing and the 750 ms serialized
autosave contract. Browser storage is limited to safe layout preferences such
as active mobile tab and panel width; it stores no authorization decision.

Notebook switches, logout, source searches, picker navigation, and preview
changes cancel or ignore stale requests.

## Preview and citation flow

Attached source preview and citation clicks use `SourceViewerPanel`,
`DocumentViewerPanel`, `DocumentPreviewRenderer`, and the existing format
renderers. The viewer receives document id, page, and chunk id where available,
keeps native document paper uninverted, and preserves Notebook/chat state when
closed. Current Corpus/workspace preview, file, rendered-page, and download
authorization remains authoritative.

## Notes and artifacts

Notebook notes are references to existing owner-scoped `notes`. Creating or
saving an answer uses existing note APIs, TipTap stable block ids, optimistic
revision handling, version history, serialized autosave, and separate database
save/indexing states.

The initial Studio exposes only existing summary capabilities: Executive
Brief, Detailed Summary, Key Points, Action Items/Checklist, and Comparison
mode where supported by the summary service. Save to Note and Markdown/PDF/DOCX
exports continue through existing summary and export routes. Audio, video,
slides, infographic, quiz, flashcards, and mind map are deferred and have no
dead controls.

## Responsive and accessibility behavior

- At 1440px and above, Sources, dominant Chat, and a Studio/Notes panel can be
  visible together; preview replaces or resizes the right contextual region.
- From 1024px through 1439px, Chat remains dominant, Sources is compact, and
  only one right contextual panel owns Studio, Notes, or Preview.
- Below 1024px, the existing Radix global navigation lifecycle remains the
  owner. Sources, Chat, Studio, and Notes become named tabs, and source picker
  and preview use one full-height Radix sheet/dialog at a time.

All icon controls have accessible names, keyboard-visible focus, Escape and
outside-click behavior come from Radix, focus returns to the trigger, and no
state may leave body scroll locked or create horizontal document overflow.

## Observability

Material mutations use current audit patterns with content-free event names:
`notebook_created`, `notebook_opened`, `notebook_source_attached`,
`notebook_source_detached`, `notebook_chat_bound`, and
`notebook_artifact_started/completed/failed`. Metrics are limited to duration,
attached/active counts, artifact type, and status. Questions, answers, titles
where policy excludes them, bodies, prompts, evidence, paths, emails, tokens,
cookies, and credentials are never logged.

## Testing and rollback

Backend tests cover migration structure/downgrade, model constraints, owner
isolation, source deduplication and resolution, chat binding, artifact
association, safe errors, and route authentication. Frontend tests cover routes,
query keys, no demo fallback, counts, picker tabs, context mapping, reuse of the
existing assistant/viewer/notes, and responsive overlay ownership. Playwright
validates the real application at 1440x900, 1024x768, 768x1024, and 390x844.

Rollback first disables notebook navigation/routes, then downgrades revision
`20260802_0019`. Downgrade removes notebook associations and metadata only; it
does not delete source documents, notes, summary artifacts, chat sessions, chat
messages, files, vectors, or index generations.

## Deferred scope

Enterprise/department notebook creation, sharing/transfer/revocation
management, pasted-text snapshots, collaborative editing, multimedia outputs,
and new model providers are deferred until their security and service contracts
exist. The schema values do not claim that those product behaviors are live.
