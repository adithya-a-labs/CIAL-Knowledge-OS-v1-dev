import { Permission } from '../types';

// TODO: Replace with Microsoft Entra ID / Keycloak integration
export type Role = 'admin' | 'engineer' | 'manager' | 'viewer';

export const ROLE_PERMISSIONS: Record<Role, Permission> = {
  admin: { canUpload: true, canDelete: true, canEdit: true, canAccessAdmin: true },
  engineer: { canUpload: true, canDelete: false, canEdit: true, canAccessAdmin: false },
  manager: { canUpload: true, canDelete: false, canEdit: true, canAccessAdmin: false },
  viewer: { canUpload: false, canDelete: false, canEdit: false, canAccessAdmin: false }
};

export const hasPermission = (role: Role, action: keyof Permission) => {
  return ROLE_PERMISSIONS[role]?.[action] ?? false;
};
