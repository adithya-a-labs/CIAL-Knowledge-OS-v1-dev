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

That keeps the current retrieval flow unchanged while making future retrieval-time privacy filters possible.

## Deferred Runtime Work

The schema is ready, but these are still application tasks:

- authenticated upload flows that stamp both workspace and owner
- retrieval filters that exclude non-owned private documents
- workspace and ACL management APIs
- audit logging around sharing, transfer, and revocation

Current bridge behavior:

- request-layer access filtering now prevents personal documents from appearing in corpus and chat responses unless the request resolves to the owner or an allowed scope
- the temporary access context is derived from backend request headers until a durable auth/session layer is added
