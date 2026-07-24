# Notes, summaries, and live generation

## Private notes

Notes are a dedicated PostgreSQL domain, not uploaded documents. `notes` is owner- and personal-workspace-scoped, soft-deleted, and updated with an `expected_revision` optimistic concurrency check. Every successful revision is copied to `note_versions`. Tags and document links use owner-validated association tables. The Notes API is rooted at `/api/workspaces/me/notes`; the server derives organization, workspace, and owner from the authenticated session and returns 404 for inaccessible identifiers.

The Notes UI has no runtime demo fallback. It creates the server draft first, uses TipTap with stable top-level block IDs, autosaves canonical editor JSON plus deterministic Markdown after 750 ms, and reports backend-confirmed Saving/Saved/error/conflict states. Markdown exports are generated from the persisted revision.

Each committed note revision schedules an ordinary indexing job. The note indexer creates deterministic point IDs from note/revision/chunk, upserts the new revision before removing stale points, and maintains `note_index_states`. Personal note chunks use `repository_id=personal:{owner_user_id}` and private owner/workspace payload fields. Dense retrieval receives the authorized path filter before Qdrant returns vectors; BM25 builds bounded authorization-scoped snapshots before scoring, so private note text never enters an unauthorized candidate list. Selected note IDs are server re-authorized and participate in the same hard context boundary as typed documents and folders.

## Grounded summaries

`summary_artifacts` are immutable generated results. `summary_sources` capture the exact document/note/conversation identity, version, and content hash used for generation; `summary_citations` preserve stable source locations and excerpts. Personal ownership is enforced on every artifact query.

The service re-resolves client IDs under the current access context. Documents use the exact indexed `document_version` and every stored chunk in order. Notes use their exact `note_version`; conversations must be owned by the caller. Generation is a bounded map/reduce path: complete source chunks are partitioned into deterministic batches, summarized with `summaries.section_v1`, and reduced with `summaries.merge_v1`. Invalid citation markers are removed before persistence. No general QA top-k retrieval or outside source is used.

Endpoints include `POST /api/summaries`, `POST /api/summaries/stream`, owner-scoped list/get/delete, explicit save-to-note, and persisted Markdown/PDF/DOCX export. Pasted text is bounded, owner-private, hashed, and snapshotted with the immutable source record. Folder requests are expanded recursively and each resolved document is re-authorized and deduplicated. Saved Knowledge stores an idempotent owner-scoped reference to the immutable artifact. Summary follow-up creates a real owned chat session plus a `summary_conversation_binding` containing exact source/version identities; original-version mode refuses unavailable provenance rather than substituting latest material.

## Chat progress and cancellation

`POST /api/chat` remains compatible. `POST /api/chat/stream` accepts the same request and emits NDJSON containing operational stage IDs, measured elapsed time, and real counts. Prompt text, model reasoning, and chain-of-thought are never emitted. The browser consumes the POST stream with `fetch`, `ReadableStream`, and `AbortController`. Disconnect/Stop sets a cooperative cancellation flag; persistence checks it and rolls back rather than recording a completed assistant response.

The local Ollama adapters use their real streaming iterators. Chat emits token deltas from the unchanged Phase 4.5 prompt after retrieval/evidence selection has run once. Summary map stages emit operational progress and the final merge emits real tokens. Iterators are closed in `finally`; cancellation is checked during iteration; retries are allowed only before a visible token; and assistant/artifact completion is persisted only after a successful full stream.

Migration `20260721_0012` adds `note_index_states`, `saved_knowledge_items`, and `summary_conversation_bindings` without modifying existing rows. The runtime remains on-premises and does not introduce a new storage or model service.

## Continuous Note Indexing

Every successfully committed note revision records its immutable
`note_version_id` in the shared durable indexing queue. A failed optimistic
save creates no job. Rapid committed autosaves mark older pending/retry jobs
`superseded` and debounce the newest revision. The standalone worker indexes
or removes notes, mixes note blocks with document chunks in the same bounded
embedding batches, updates `note_index_states`, verifies deterministic points
without Qdrant scrolling, and publishes the next BM25 generation. Saving/Saved
remains a PostgreSQL UI state; AI index progress is independent. See
[Continuous Indexing Architecture](CONTINUOUS_INDEXING_ARCHITECTURE.md).
