# RBAC And Access Control

## Authorization Shape

The schema now supports five authorization building blocks:

1. global roles through `roles`, `permissions`, `role_permissions`, and `user_roles`
2. department-scoped role assignment through `department_role_assignments`
3. department membership through `users.department_id` and `department_memberships`
4. group membership through `groups` and `group_memberships`
5. explicit ACL grants through `document_permissions`, `folder_permissions`, and `workspace_permissions`

This is still application-enforced authorization. PostgreSQL stores the policy inputs; it does not yet enforce RLS.

## Seeded Permissions

The seeded permission catalog remains:

- `manage_users`
- `manage_roles`
- `manage_departments`
- `view_enterprise_documents`
- `view_department_documents`
- `upload_enterprise_documents`
- `manage_enterprise_documents`
- `view_own_documents`
- `upload_own_documents`
- `delete_own_documents`
- `use_ai_assistant`
- `view_audit_logs`
- `manage_settings`

## ACL Model

ACL tables preserve the legacy principal columns for compatibility:

- `user_id`
- `department_id`
- `role_id`

They now also support:

- `group_id`
- `subject_type`
- `subject_id`
- `permission`
- `expires_at`
- `created_by_user_id`
- `created_at`
- `updated_at`

Valid normalized ACL subjects:

- `user`
- `role`
- `department`
- `group`

Valid ACL permissions:

- `view`
- `edit`
- `manage`
- `delete`

`workspace_permissions` is new and mirrors the same principal shape as folder/document ACLs so authorization can move upward from document-only grants over time.

## Recommended Resolution Order

For document access:

1. deny soft-deleted content
2. allow the owner for personal documents
3. evaluate explicit document ACLs
4. evaluate inherited folder or workspace ACLs if the application supports inheritance
5. evaluate visibility and role-based policy for enterprise content
6. deny by default

For folder or workspace access:

1. evaluate explicit ACLs first
2. then evaluate role, department, and group-derived policy
3. deny by default if no rule matches

## Critical Isolation Rule

`department_id` is classification and ownership context. It is not an implicit allow rule.

A personal document must not become visible merely because:

- another user belongs to the same department
- the document is classified under that department
- a department-scoped role exists without an explicit rule allowing private content

Ownership or an explicit ACL grant is still required.

## Groups

`groups` and `group_memberships` are added to make access control scale beyond direct user lists and coarse department grants.

Current scope:

- groups can be attached to ACL rows now
- group membership has active or inactive state and optional expiry
- the schema enforces at most one active membership per user and group pair

Deferred runtime work:

- group-aware authorization resolution in services
- admin APIs for managing groups and membership lifecycle
- inheritance rules between workspace, folder, and document ACLs

## Identity Readiness

The identity schema is ready for:

- SSO and LDAP identity mapping through `users.auth_provider`, `users.auth_subject`, `users.external_directory_id`, and `users.ldap_dn`
- department-scoped and workspace-scoped access evolution without replacing existing role mappings
- future RLS only after the authenticated request surface is stable

## Current Runtime Bridging

The development runtime uses backend-issued HttpOnly cookie sessions as the authoritative authenticated identity. `POST /api/auth/login` and `POST /api/auth/signup` set the configured session cookie, `GET /api/auth/me` restores the user from that cookie on frontend startup, and `POST /api/auth/logout` clears the same cookie attributes.

`backend.app.security.access.require_authenticated_access_context` is the canonical server-side dependency for authenticated browser routes. `/api/auth/me` and `/api/workspaces/me/*` both use it, so My Workspace resolves the same cookie-backed user principal as session restoration. Workspace ownership is derived server-side from that principal; the frontend never sends `owner_user_id`.

The frontend must call the API with credentials included. Protected routes stay in an initializing state until `/api/auth/me` confirms either an authenticated user or a missing/invalid session; unresolved restore errors do not redirect to `/login`. After login, `/api/workspaces/me/tree`, `/summary`, `/root`, and `/preferences` must all accept the same session cookie that `/api/auth/me` accepts.

For local browser development, `frontend/src/api/client.ts` normalizes loopback API hosts to the current page host. If the app is opened at `http://localhost:5173`, a loopback API base resolves to `http://localhost:8000`; if opened at `http://127.0.0.1:5173`, it resolves to `http://127.0.0.1:8000`. This prevents HttpOnly SameSite session cookies from being dropped by `localhost`/`127.0.0.1` origin mismatches.

For development-only integration paths, the backend can still resolve access context from optional headers when `CIAL_AUTH_ALLOW_USER_HEADERS=true`:

- `X-CIAL-User-Id`
- `X-CIAL-Access-Scope`

Cookie identity takes precedence over those headers. In production, the header fallback should remain disabled.

My Workspace routes require an authenticated principal and derive organization, workspace, owner, visibility, and storage scope exclusively from that principal. Folder ids are always constrained to the caller's personal workspace. Shared corpus preview/file/download routes apply the same document access filter before resolving a personal storage path; department membership does not satisfy that filter.
