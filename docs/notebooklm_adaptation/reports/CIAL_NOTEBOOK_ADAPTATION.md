# CIAL notebook adaptation

## 1. Adopt Interaction Principle

### Explicit context selection
- NotebookLM observation: source checkboxes visibly change grounding.
- CIAL value: prevents hidden retrieval scope.
- Adaptation: selected document/folder chips backed by Corpus IDs.
- Dependencies: Corpus tree, chat request context, PostgreSQL persistence.
- Risks: stale selection after ACL/index changes.
- Priority: P0.
- Evidence: `flow-chat-one-source`, `flow-chat-two-source`.

### Evidence-proximate citations
- Observation: citation anchors open detail and source actions.
- Value: verifiable enterprise answers.
- Adaptation: shared CIAL viewer deep-linked by document/page/chunk.
- Dependencies: preview resolver, citation DTO, ACL filter.
- Risks: imperfect text highlight; use cited-page/excerpt fallback.
- Priority: P0.

### Durable async outputs
- Observation: generating cards become persistent artifact cards/viewers.
- Value: long local jobs can continue without blocking chat.
- Adaptation: PostgreSQL artifact jobs and SSE/NDJSON progress.
- Dependencies: worker queue, filesystem artifacts, audit events.
- Risks: GPU contention, cancellation, quota and retention policy.
- Priority: P1.

## 2. Adapt To CIAL Visual Language

Use CIAL typography, spacing, calm contrast, enterprise iconography, persistent
global navigation, and explicit system status. Preserve the semantic triad and
responsive reflow; do not reproduce Google styling. Add strong focus restoration
and human accessible names.

## 3. Adapt To Offline Architecture

Filesystem remains authoritative for source files; PostgreSQL owns notebook,
selection, note, chat, citation, artifact-job, ACL, and lifecycle metadata;
Qdrant remains vector search; Corpus API hides storage; the shared document
preview resolves citations; local Ollama/worker processes generate answers and
artifacts. No cloud dependency is required.

## 4. Do Not Copy

Do not copy Google branding, proprietary discovery/ranking assumptions, Drive
coupling, account-level share defaults, opaque generation orchestration,
Material icon labels, or multimedia-first product priority.

## 5. Add CIAL Specific Capability

Add folder and document context, index readiness per source, evidence strength,
page/chunk citation navigation, ACL/visibility badges, personal-workspace owner
isolation, audit history, local model/profile choice, system health, and safe
degraded retrieval states.

## 6. Defer Pending Decision

Defer audio/video, flashcards/quiz, public sharing, external website ingestion,
artifact export formats, and real-time multi-user editing until security,
offline model quality, GPU scheduling, retention, and product demand are decided.
