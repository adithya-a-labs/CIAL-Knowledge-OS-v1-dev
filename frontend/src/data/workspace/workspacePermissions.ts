import type { WorkspaceDocument } from './workspaceTypes';

export interface WorkspaceUser {
  id: string;
  role: string;
}

export function canViewPrivateDocument(user: WorkspaceUser, document: WorkspaceDocument): boolean {
  return document.visibility === 'private' && document.ownerId === user.id;
}

export function canUploadToWorkspace(user: WorkspaceUser): boolean {
  return !!user.id;
}

export function canDeleteFromWorkspace(user: WorkspaceUser, document: WorkspaceDocument): boolean {
  return document.ownerId === user.id;
}

export function getVisibleDocuments(user: WorkspaceUser, documents: WorkspaceDocument[]): WorkspaceDocument[] {
  return documents.filter((doc) => canViewPrivateDocument(user, doc));
}
