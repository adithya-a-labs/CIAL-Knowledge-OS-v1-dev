# Personal Workspace Isolation

## Goal

Support user-owned workspace documents without weakening enterprise corpus access rules.

## Isolation Contract

A personal document is defined by:

- `storage_scope='personal'`
- `owner_user_id` set to the owning user
- `visibility='private'`
- `department_id` set for classification only

The database enforces two minimum invariants:

- personal documents must have an owner
- personal documents must be private

## What Department Does Not Mean

For personal workspace content, `department_id` does not grant visibility.

This means:

- users in the same department do not automatically see each other’s workspace files
- department-scoped roles do not automatically override privacy
- explicit ACL rules are required for any exception

## Recommended Access Algorithm

For a personal document:

1. reject if `lifecycle_status='deleted'` or `deleted_at` is set
2. allow if requester is `owner_user_id`
3. allow only if an unexpired ACL rule grants access
4. otherwise deny

For an enterprise document:

1. reject if deleted
2. evaluate ACL rules
3. evaluate visibility plus RBAC
4. never use `department_id` alone as an allow condition

## Indexing And Retrieval Impact

The indexing pipeline now hydrates these fields into chunk metadata:

- `storage_scope`
- `owner_user_id`
- `department_id`
- `folder_id`
- `visibility`
- `lifecycle_status`

That makes it possible to apply retrieval-time filtering later without redesigning the storage model.

## Deferred Work

The schema is ready for personal workspace APIs, but these items remain application work:

- authenticated upload endpoints that stamp `owner_user_id`
- retrieval filters that exclude non-owned private documents
- ACL management endpoints
- audit logging for personal-document sharing and deletion
