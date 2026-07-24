# Database Architecture

Status: PostgreSQL remains the metadata and control-plane store for CIAL Knowledge OS, with workspace-aware storage, group-aware ACL foundations, and search/retrieval observability added in place.

## Scope

PostgreSQL is the system of record for:

- identity, organizations, departments, roles, and memberships
- workspaces, folders, documents, versions, chunks, and ACL metadata
- indexing jobs, ingestion runs, and audit history
- authoritative chat sessions, messages, citations, sources, request/profile metadata, and conversation summaries
- search metadata and retrieval telemetry

PostgreSQL does not replace:

- filesystem storage for source files
- Qdrant for vectors and ANN retrieval
- the existing corpus sync, prompt, or retrieval pipeline

## Core Tables

Identity and RBAC:

- `organizations`
- `departments`
- `designations`
- `users`
- `roles`
- `user_roles`
- `permissions`
- `role_permissions`
- `department_memberships`
- `department_role_assignments`
- `groups`
- `group_memberships`

Knowledge control plane:

- `workspaces`
- `folders`
- `documents`
- `document_versions`
- `document_chunks`
- `document_permissions`
- `folder_permissions`
- `workspace_permissions`
- `document_relationships`
- `document_search_metadata`
- `workspace_user_preferences`

Operations and observability:

- `ingestion_runs`
- `indexing_jobs`
- `audit_events`
- `retrieval_events`

Conversation metadata:

- `chat_sessions`
- `chat_messages`
- `saved_contexts`
- `conversation_feedback`
- `conversation_summaries`

## Workspace-Centric Storage

`workspaces` is now the future primary container above folders and documents. It exists to absorb new knowledge-space types without forcing another schema rewrite.

Current workspace types:

- `enterprise`
- `personal`
- `department`
- `project`
- `external`
- `system`

Compatibility rules:

- `documents.storage_scope`, `documents.owner_user_id`, `documents.department_id`, and `documents.visibility` remain in place.
- `documents.workspace_id` and `folders.workspace_id` are added without removing legacy fields.
- existing enterprise corpus content is backfilled into an enterprise workspace per organization
- existing owned personal documents are backfilled into one personal workspace per owner

## Document Model

`documents` now combines legacy compatibility fields with the newer access and lifecycle fields:

- `organization_id`
- `department_id`
- `workspace_id`
- `folder_id`
- `storage_scope`
- `owner_user_id`
- `visibility`
- `lifecycle_status`
- `source_type`
- `current_version_id`
- `content_hash`
- `mime_type`
- `created_by_user_id`
- `updated_by_user_id`
- `deleted_at`
- `deleted_by_user_id`
- `delete_reason`

Important invariants:

- personal documents require `owner_user_id`
- personal documents require `visibility='private'`
- `department_id` remains required for classification
- `workspace_id` is mandatory only after migration backfill succeeds safely

`relative_path` remains the stable bridge between the filesystem-backed corpus and PostgreSQL metadata.

Migration `20260720_0009` adds `folders.system_key`, document JSON metadata for stable UI flags such as pinning, and `workspace_user_preferences`. The preference JSONB value is validated at the API boundary and stores stable widget ids rather than React component names. Personal file originals remain outside PostgreSQL under `CIAL_WORKSPACE_ROOT`.

## Versioning, Chunks, and Indexing

`document_versions` stores version-level metadata such as `storage_key`, `mime_type`, `extracted_text_path`, `preview_artifact_path`, `created_by_user_id`, and `status`.

`document_chunks` stores chunk-level metadata such as `document_version_id`, `chunk_index`, `section`, `text`, and JSON metadata. The indexing pipeline hydrates PostgreSQL metadata before Qdrant upserts so payloads now include `workspace_id` in addition to `document_id`, `document_version_id`, `storage_scope`, `owner_user_id`, `department_id`, `folder_id`, `visibility`, and `lifecycle_status`.

`indexing_jobs` is the durable operational queue for documents, note versions,
metadata refreshes, deletes, reconciliation, and rebuild plans. Revision
`20260724_0016` adds explicit target families and operations, priority,
availability, bounded attempts, worker ownership, leases, heartbeats, error
codes, and the expanded stage state machine. Partial unique indexes prevent an
active duplicate for the same version/operation without blocking newer
versions.

`indexer_workers` stores service state, fresh heartbeat, safe queue/throughput
metrics, actual embedding device, and reconciliation state.
`index_generations` is the single committed pointer for dense and BM25
generations. See
[Continuous Indexing Architecture](CONTINUOUS_INDEXING_ARCHITECTURE.md).

## Search and Observability Additions

`document_relationships` captures explicit links between documents such as `related`, `references`, `supersedes`, `duplicate`, `derived_from`, `translation_of`, and `attachment_of`.

`document_search_metadata` stores normalized search fields outside Qdrant, including title normalization, summary, keywords, entities, topics, language, and classification. Its unique constraint on `document_id` doubles as the primary lookup index.

`retrieval_events` and `conversation_summaries` remain schema foundations for future runtime wiring. `chat_sessions` and `chat_messages`, however, are wired into the current authenticated chat flow and are the conversation-history system of record. Local/session storage and React/React Query state may cache UI data only; they cannot create seeded history or replace PostgreSQL results.

Chat ownership invariants:

- list, read, create, and message writes require an authenticated user;
- session and message reads constrain through `chat_sessions.user_id`;
- a client may supply a stable UUID for a new session, but cannot reuse another user's UUID;
- successful turns persist the user message and assistant answer together with citations, sources, selected document/folder IDs, response profile, metadata, and timestamps;
- empty history is a valid result and API errors never authorize destructive replacement or demo fallback.

## Deferred Runtime Wiring

The new schema is intentionally ahead of the runtime in a few places:

- group-based ACL evaluation beyond storage support
- workspace-level authorization resolution
- automated population of `document_relationships`
- automated enrichment of `document_search_metadata`
- retrieval-event writes during live RAG execution
- conversation summarization writes during chat execution

Those are application-layer follow-ups, not blockers for the current migration.

Continuous indexing, personal-document processing, note coalescing, worker
leases, and generation publication are implemented runtime wiring, not items
in this deferred list.
