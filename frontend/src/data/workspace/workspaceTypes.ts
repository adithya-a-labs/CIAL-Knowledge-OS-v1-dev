export type PrivateDocumentVisibility = 'private';
export type FileType = 'pdf' | 'docx' | 'xlsx' | 'pptx' | 'txt' | 'other';
export type AISearchMode = 'enterprise' | 'workspace' | 'hybrid';
export type ActivityType = 'upload' | 'note' | 'chat' | 'bookmark' | 'delete';

export interface WorkspaceDocument {
  id: string;
  name: string;
  category: string;
  size: string;
  sizeBytes: number;
  uploadedAt: string;
  fileType: FileType;
  visibility: PrivateDocumentVisibility;
  ownerId: string;
}

export interface WorkspaceConversation {
  id: string;
  question: string;
  sources: ('Enterprise' | 'My Workspace')[];
  time: string;
  ownerId: string;
}

export interface WorkspaceCollection {
  id: string;
  name: string;
  itemCount: number;
  ownerId: string;
}

export interface WorkspaceActivityEntry {
  id: string;
  type: ActivityType;
  description: string;
  time: string;
  ownerId: string;
}

export interface StorageInfo {
  usedBytes: number;
  totalBytes: number;
  usedGB: number;
  totalGB: number;
  availableGB: number;
  percentUsed: number;
  resetNote: string;
}

export interface StorageBreakdownItem {
  name: string;
  value: number;
  color: string;
}

export interface WorkspaceStatItem {
  key: string;
  label: string;
  count: number;
  unit: string;
  icon: string;
  href: string;
}
