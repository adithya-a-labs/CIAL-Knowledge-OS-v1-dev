# RBAC And Access Control

## RBAC Shape

The schema supports four layers of authorization:

1. `roles`
2. `permissions`
3. `role_permissions`
4. user assignment through `user_roles` and optional department-scoped assignment through `department_role_assignments`

Department affiliation is represented by:

- `users.department_id` for the primary/home department
- `department_memberships` for multi-department membership

## Seeded Permissions

The migration seeds these permissions:

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

## Access Resolution Rules

Document access should be resolved in this order:

1. hard deny for soft-deleted documents
2. ownership rule for personal documents
3. document-level ACL grants from `document_permissions`
4. visibility-based grants for enterprise documents
5. role/permission evaluation

`document_permissions` is the current ACL table. It preserves the old `user_id` / `department_id` / `role_id` columns for compatibility, and also stores normalized ACL fields:

- `subject_type`
- `subject_id`
- `permission`
- `expires_at`
- `created_by_user_id`
- `created_at`
- `updated_at`

Valid ACL permission values are:

- `view`
- `edit`
- `manage`
- `delete`

Valid ACL subject values are:

- `user`
- `role`
- `department`

## Critical Rule

`department_id` on a document is classification and ownership context. It is not a standalone access grant.

A user must not gain access to a personal document merely because:

- the user belongs to the same department
- the document has the same `department_id`

Personal-document access requires ownership or an explicit ACL rule.

## Enterprise vs Personal

Personal document baseline:

- `storage_scope='personal'`
- `owner_user_id` required
- `visibility='private'`
- `department_id` required

Enterprise document baseline:

- `storage_scope='enterprise'`
- `department_id` required
- `visibility in ('department', 'enterprise', 'restricted')`

## Future Application Layer Expectations

The schema is ready for:

- login/session-backed RBAC
- future SSO or LDAP identity mapping through `users.auth_provider`, `users.auth_subject`, `users.external_directory_id`, and `users.ldap_dn`
- department-scoped admin/editor roles without changing global `user_roles`

It does not yet implement database-enforced RLS policies. Access is still expected to be enforced in the application layer until the auth surface is stabilized.
