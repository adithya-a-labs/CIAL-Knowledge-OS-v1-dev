# NotebookLM adaptation research

Generated: 2026-07-30T15:47:59+05:30

This folder is a research-only external benchmark for a future CIAL notebook
workspace. It does not contain application implementation, tests, dependency
changes, configuration, migrations, database writes, or production-document
edits.

## Scope and evidence

The audit covers the NotebookLM library, controlled notebook creation, empty
state, copied-text and permitted-web sources, source selection/preview, grounded
chat, citations, notes, every visible Studio output, sharing, settings,
keyboard/accessibility behavior, persistence, and four responsive viewports.
Only the controlled test notebook was opened.

Evidence is organized under `evidence/`. Screenshots are privacy-cropped;
accessibility and DOM snapshots are structural reconstructions containing no
answer text, source contents, private notebook titles, account identifiers, or
session data. `evidence/fixtures/` is separate **RESEARCH_TEST_DATA**, not a
NotebookLM observation.

## Classifications

- **OBSERVED**: directly verified through the authorized browser session.
- **INFERRED**: a reasonable interpretation of observed behavior.
- **RECOMMENDED**: a proposed CIAL product/architecture decision.
- **UNKNOWN**: unavailable or not externally observable.

## Privacy

Artifacts intentionally exclude email addresses, account/profile identifiers,
cookies, tokens, authorization data, session identifiers, signed URLs, private
notebook titles, source contents, query/answer text, and raw request payloads.
Routes use placeholders. Network evidence is category-only; where the browser
surface exposed no network stream, that absence is recorded as a limitation.

## How to use this research

Use stable IDs to join reports, `data/`, `evidence/`, and Mermaid diagrams.
Adopt interaction principles, not Google branding or implementation assumptions.
CIAL recommendations remain subordinate to the current filesystem, PostgreSQL,
Qdrant, Corpus API, document-preview, RBAC/ACL, and personal-workspace contracts.
