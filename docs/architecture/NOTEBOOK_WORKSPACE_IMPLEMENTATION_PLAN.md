# Notebook Workspace Implementation Plan

Status: approved implementation sequence based on repository state at
revision head `20260729_0018` and the pre-edit Playwright audit on 2026-08-02.

## Audited extension points

- FastAPI composition: `backend/app/main.py` and existing authenticated route
  modules.
- SQLAlchemy conventions: UUID primary-key and timestamp mixins in
  `backend/app/db/base.py`; current domain models in `models/knowledge.py`,
  `models/conversations.py`, and `models/workspace_content.py`.
- Authorization: `RequestAccessContext`, `apply_document_access_filter`, and
  owner-scoped note/summary services.
- Chat: `chat_sessions`/`chat_messages`, `ConversationService`,
  `/api/chat/stream`, `ChatConcurrencyController`, selected context schemas,
  and deterministic turn ordering from `20260729_0018`.
- Frontend: Wouter routes, React Query, `AssistantSessionsProvider`,
  `ChatPanel`, `SourceViewerPanel`, workspace upload/note APIs, semantic tokens,
  and the 1024px AppShell navigation boundary.
- Existing runtime: the real authenticated frontend and FastAPI backend were
  inspected with Playwright MCP before edits; Knowledge Center, shared PDF
  viewer, assistant, My Workspace notes, mobile navigation, and appearance
  controls are operational.

## Implementation sequence

1. Add reversible migration `20260802_0019` for the four notebook tables,
   indexes, unique target constraints, checks, and foreign keys.
2. Add SQLAlchemy notebook models and include them in Alembic metadata imports.
3. Add typed notebook schemas with bounded titles, enumerated source/artifact
   types, complete reorder requests, and no client security fields.
4. Add focused Notebook, Source, Chat Binding, and Artifact services. Reuse
   personal workspace resolution, current document authorization, owned notes,
   owned summaries, ordinary `ChatSession`, and existing audit conventions.
5. Add authenticated `/api/notebooks` routes and mount them in the existing
   application. Do not add preview or streaming endpoints.
6. Extend frontend API types/client with notebook contracts and React Query
   keys.
7. Add `/notebooks` library with real loading, error, empty, populated, create,
   rename, delete, search, counts, and activity states; add global navigation.
8. Add `/notebooks/:id` workspace with a responsive Notebook shell, Sources
   panel, attached/active controls, unified source picker, real upload attach,
   existing assistant bound to the notebook session, existing shared viewer,
   existing notes editor/links, and supported summary artifact controls.
9. Add narrow-layout tabs and single-overlay ownership using existing Radix
   components. Preserve theme tokens and native document paper rendering.
10. Add targeted backend/frontend tests, then run migration upgrade and
    downgrade-equivalent validation, full backend/frontend tests, TypeScript
    typecheck, and production build.
11. Use Playwright MCP against the real stack for required viewports and flows.
    Store sanitized screenshots, trace where supported, console/network
    summaries, overflow/focus results, persistence evidence, and authorization
    outcomes under `outputs/playwright/notebook-workspace/`.
12. Update source-of-truth and verification documents only with observed
    results. Report blocked or not-run flows explicitly.

## Acceptance and non-regression gates

- Notebook records and associations persist in PostgreSQL and are owner
  isolated.
- Attached and active counts are distinct; chat sends only explicit active
  document/note ids through existing fields and current reauthorization.
- No notebook chat-message table, streaming route, preview route, note-body
  table, indexer, prompt change, or Qdrant write exists.
- Upload returns queued work without blocking the last published generation.
- Citations open the existing viewer; notes retain existing autosave/version
  contracts; Studio exposes only supported grounded summary/export services.
- Existing chat, concurrency, Corpus, workspace, preview, notes, summaries,
  indexing, RBAC, theme, auth, LAN same-origin, and mobile lifecycle tests remain
  green or are truthfully recorded as blocked.

## Rollback

Remove frontend navigation/routes and the notebook router first, then downgrade
`20260802_0019`. Existing chat sessions, notes, summaries, documents, files,
Qdrant vectors, and published generations are preserved because notebook rows
are associations and metadata only.
