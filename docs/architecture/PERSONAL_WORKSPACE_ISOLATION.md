# Personal Workspace Isolation

## Goal

Support user-owned knowledge spaces without weakening enterprise corpus visibility rules.

## Personal Workspace Contract

The new `workspaces` layer does not replace the existing personal-document contract. It formalizes it.

A personal document is still defined by:

- `storage_scope='personal'`
- `owner_user_id` set to the owning user
- `visibility='private'`
- `department_id` set for classification only
- `workspace_id` pointing at a personal workspace owned by that same user

A personal workspace is defined by:

- `workspace_type='personal'`
- `owner_user_id` required
- `visibility='private'`

The database enforces the owner and privacy invariants on the workspace and document rows independently.

## Backfill Behavior

The migration creates one personal workspace per user who already owns personal documents.

Existing enterprise corpus content is backfilled into an organization-level enterprise workspace. Existing personal documents are then attached to the owner's personal workspace through `documents.workspace_id`.

This keeps the old access model intact while making workspace-aware APIs possible later.

## What Department Does Not Mean

For personal content, `department_id` does not grant visibility.

That means:

- users in the same department do not automatically see each other's personal documents
- department-scoped roles do not automatically override privacy
- shared department membership does not imply shared workspace membership
- explicit ACL rules are required for any exception

## Recommended Access Algorithm

For a personal document:

1. reject if soft-deleted
2. allow if requester is `owner_user_id`
3. allow only if an unexpired ACL rule permits access
4. otherwise deny

For an enterprise document:

1. reject if soft-deleted
2. evaluate document, folder, and workspace ACLs as implemented
3. evaluate visibility plus RBAC
4. never use `department_id` alone as an allow condition

## Indexing And Retrieval Impact

The indexing pipeline now hydrates these fields into Qdrant payload metadata:

- `workspace_id`
- `storage_scope`
- `owner_user_id`
- `department_id`
- `folder_id`
- `visibility`
- `lifecycle_status`

Dense retrieval enforces these fields with Qdrant keyword payload indexes, and
BM25 filters the published in-memory snapshot before scoring. Generation
refresh, Qdrant timeout, and stale-generation fallback retain the same owner
boundary; they never fall back to unfiltered enterprise or personal evidence.

## Runtime Status

Implemented:

- authenticated `GET /api/workspaces/me/*` discovery, folder browsing, summary, and validated preference APIs
- personal uploads stamp workspace, organization, owner, private visibility, personal storage scope, department classification, version metadata, audit metadata, and an indexing job from authenticated context
- originals are stored below `CIAL_WORKSPACE_ROOT`, separate from the enterprise corpus root; UUID storage names prevent user filenames becoming physical paths
- shared preview/file endpoints fall back to authorized personal metadata and resolve personal files only below the workspace root
- request-layer filters prevent non-owned personal documents from appearing in corpus, preview, file, or chat responses

Implemented:

- personal document/version creation and the indexing job commit together
- chat attachments and saved exports reuse the same owner-private upload path
- the standalone worker processes personal documents continuously and publishes
  authoritative private Qdrant/BM25 payloads
- watcher reconciliation deduplicates the already-created upload job
- widget preferences implement system/workspace/user precedence

Deferred:

- sharing, transfer, and revocation APIs and their audit lifecycle
- durable chat-upload conversation folders and attachment association APIs

The queue/worker details are in
[Continuous Indexing Architecture](CONTINUOUS_INDEXING_ARCHITECTURE.md).

## LAN Client Semantics

A LAN client is another authenticated browser, not a new tenancy boundary.
Personal notes, documents, uploads, preferences, previews, and assistant
context retain their existing owner/workspace checks. The gateway exposes no
personal storage path and does not broaden sharing; the deferred
sharing/transfer/revocation lifecycle remains deferred.
