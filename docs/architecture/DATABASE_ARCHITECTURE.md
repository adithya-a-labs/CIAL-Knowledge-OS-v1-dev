# Database Architecture

Status: expanded PostgreSQL metadata/control-plane schema for CIAL Knowledge OS.

## Scope

PostgreSQL remains the system of record for:

- identity, RBAC, and department membership
- document metadata, lifecycle state, and access control
- indexing jobs, document versions, and chunk metadata
- chat/session metadata and audit history

PostgreSQL does not replace:

- filesystem storage for source files
- Qdrant for vectors
- the existing retrieval/prompt/Qdrant pipeline

## Core Entities

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

Document control plane:

- `folders`
- `documents`
- `document_versions`
- `document_chunks`
- `document_permissions`
- `folder_permissions`

Operations and observability:

- `ingestion_runs`
- `indexing_jobs`
- `audit_events`

Conversation metadata:

- `chat_sessions`
- `chat_messages`
- `saved_contexts`
- `conversation_feedback`

## Document Model

`documents` now carries the access and ownership fields required for mixed enterprise and personal storage:

- `organization_id`
- `department_id`
- `folder_id`
- `storage_scope`
- `owner_user_id`
- `created_by_user_id`
- `updated_by_user_id`
- `visibility`
- `lifecycle_status`
- `current_version_id`
- `content_hash`
- `file_type`
- `mime_type`
- `source_type`
- `deleted_at`
- `deleted_by_user_id`
- `delete_reason`

Backwards-compatibility decisions:

- `indexing_status` and `indexed` remain in place because the current corpus/indexing paths still read them.
- existing corpus documents are backfilled as `storage_scope='enterprise'`
- existing corpus documents are backfilled into a default department `shared-knowledge`
- `relative_path` remains the stable bridge between filesystem metadata and the DB control plane

## Versioning and Indexing

`document_versions` is expanded to store:

- `storage_key`
- `mime_type`
- `extracted_text_path`
- `preview_artifact_path`
- `created_by_user_id`
- `status`

`documents.current_version_id` points at the active version.

`indexing_jobs` now carries:

- `document_id`
- `document_version_id`
- `content_hash`
- `attempts`
- `force_rebuild`
- `error_detail`
- `created_at`
- `updated_at`
- `started_at`
- `completed_at`

A partial unique index prevents duplicate active jobs for the same `document_version_id`.

## Chunk Metadata and Vector Payloads

`document_chunks` now stores:

- `document_id`
- `document_version_id`
- `chunk_id`
- `chunk_index`
- `page`
- `section`
- `text`
- `text_preview`
- `qdrant_point_id`
- `token_count`
- `metadata`

The indexing pipeline hydrates chunk/document metadata from PostgreSQL before upserting into Qdrant so payloads can include:

- `document_id`
- `document_version_id`
- `storage_scope`
- `owner_user_id`
- `department_id`
- `folder_id`
- `visibility`
- `lifecycle_status`

## Deferred Items

The following were intentionally deferred to documentation instead of migration because they add workflow complexity without immediate runtime callers:

- `approval_requests`
- `workflow_runs`
- `document_health_reports`
- `agent_runs`
- `verification_reports`

These should be introduced only when the surrounding application services and lifecycle semantics are defined.
