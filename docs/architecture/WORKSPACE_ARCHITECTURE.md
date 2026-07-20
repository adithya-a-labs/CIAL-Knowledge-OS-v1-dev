# Workspace Architecture

## Why Workspaces Exist

`workspaces` is the long-term container layer for knowledge assets in CIAL Knowledge OS.

It exists so the platform can support more than the current enterprise-vs-personal split without redesigning the schema again. Folders remain structural containers. Documents remain the actual knowledge assets. Workspaces define the ownership and visibility boundary above both.

## Workspace vs Department vs Folder vs Document

`workspace`

- top-level ownership and visibility boundary
- can represent enterprise, personal, department, project, external, or system knowledge spaces
- is the future unit for higher-level sharing and policy

`department`

- organizational classification and affiliation
- not a storage container
- not an implicit access grant

`folder`

- navigational structure inside a workspace
- organizes documents by relative path and hierarchy
- does not replace workspace ownership rules

`document`

- the unit of content, lifecycle, versioning, indexing, and retrieval
- still carries compatibility fields such as `storage_scope`, `owner_user_id`, and `department_id`

## Workspace Types

Supported values:

- `enterprise`
- `personal`
- `department`
- `project`
- `external`
- `system`

Current runtime usage is intentionally conservative:

- enterprise corpus sync writes to the default enterprise workspace
- migrated personal documents map to owner-specific personal workspaces
- the other workspace types are schema-ready but not yet fully wired into application services

## Key Constraints

The schema enforces:

- unique workspace slug per organization
- valid `workspace_type`
- valid `visibility`
- personal workspaces require `owner_user_id`
- personal workspaces require `visibility='private'`
- department workspaces require `department_id`

`documents.workspace_id` and `folders.workspace_id` are required only after migration backfill succeeds safely.

## Backfill Strategy

The migration introduces `workspace_id` as nullable first, then backfills:

1. create one enterprise workspace per organization if missing
2. create one personal workspace per owner of existing personal documents if missing
3. assign document workspace based on `storage_scope` and ownership
4. assign folder workspace from contained documents, then parent inheritance
5. only make `workspace_id` non-null after every row is mapped safely

If folder backfill cannot be proven safe, the migration fails rather than assigning a cross-organization workspace guess.

## Compatibility Decisions

The current system still depends on these document fields, so they remain in place:

- `storage_scope`
- `owner_user_id`
- `department_id`
- `visibility`

This avoids rewriting corpus sync, retrieval, or API behavior while the workspace abstraction is introduced.

## Runtime Wiring

Personal workspaces now have owner-scoped discovery, folder browsing/creation, upload, summary, and typed user-preference APIs. The service creates stable `chat_uploads` and `personal_uploads` system folders by `folders.system_key`; display names are not used for lookup. System defaults are merged with workspace metadata defaults and validated user preferences. Security-owned fields never come from preference or upload payloads.

## Deferred Runtime Wiring

The schema is ready for:

- non-personal workspace management APIs
- project and external knowledge spaces
- inheritance between workspace, folder, and document ACLs

Those behaviors are intentionally deferred until the surrounding service logic is defined.
