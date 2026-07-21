# Notes, summaries, and live generation

## Private notes

Notes are a dedicated PostgreSQL domain, not uploaded documents. `notes` is owner- and personal-workspace-scoped, soft-deleted, and updated with an `expected_revision` optimistic concurrency check. Every successful revision is copied to `note_versions`. Tags and document links use owner-validated association tables. The Notes API is rooted at `/api/workspaces/me/notes`; the server derives organization, workspace, and owner from the authenticated session and returns 404 for inaccessible identifiers.

The Notes UI has no runtime demo fallback. It creates the server draft first, autosaves after 750 ms, reports backend-confirmed Saving/Saved/error/conflict states, and exposes only implemented actions. Markdown exports are generated from the persisted revision.

## Grounded summaries

`summary_artifacts` are immutable generated results. `summary_sources` capture the exact document/note/conversation identity, version, and content hash used for generation; `summary_citations` preserve stable source locations and excerpts. Personal ownership is enforced on every artifact query.

The service re-resolves client IDs under the current access context. Documents use the exact indexed `document_version` and every stored chunk in order. Notes use their exact `note_version`; conversations must be owned by the caller. Generation is a bounded map/reduce path: complete source chunks are partitioned into deterministic batches, summarized with `summaries.section_v1`, and reduced with `summaries.merge_v1`. Invalid citation markers are removed before persistence. No general QA top-k retrieval or outside source is used.

Endpoints include `POST /api/summaries`, `POST /api/summaries/stream`, owner-scoped list/get/delete, explicit save-to-note, and persisted Markdown export. PDF/DOCX summary export, Saved Knowledge, and grounded follow-up are intentionally not shown until durable contracts exist.

## Chat progress and cancellation

`POST /api/chat` remains compatible. `POST /api/chat/stream` accepts the same request and emits NDJSON containing operational stage IDs, measured elapsed time, and real counts. Prompt text, model reasoning, and chain-of-thought are never emitted. The browser consumes the POST stream with `fetch`, `ReadableStream`, and `AbortController`. Disconnect/Stop sets a cooperative cancellation flag; persistence checks it and rolls back rather than recording a completed assistant response.

The current local model adapter does not expose token streaming, so the route emits real stage events followed by the existing final `ChatResponse`; it never fabricates token deltas.
