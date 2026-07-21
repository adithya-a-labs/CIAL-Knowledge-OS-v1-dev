export type PrivateDocumentVisibility = 'private';
export type FileType = 'pdf' | 'docx' | 'xlsx' | 'pptx' | 'txt' | 'other';
export type AISearchMode = 'enterprise' | 'workspace' | 'hybrid';
export type ActivityType = 'upload' | 'note' | 'chat' | 'bookmark' | 'delete';
export type WorkspaceTab = 'overview' | 'files' | 'notes' | 'saved' | 'activity';
export type WorkspaceView = 'list' | 'grid';
export type WorkspaceDensity = 'compact' | 'comfortable' | 'spacious';
export type WorkspaceWidgetId = 'storage_usage' | 'pinned_items' | 'recent_activity' | 'recent_notes' | 'recent_conversations' | 'indexing_status';
export type WorkspaceDocumentStatus = 'uploading' | 'processing' | 'indexing' | 'indexed' | 'failed' | 'unsupported' | 'pending';

export interface WorkspacePreferences {
  version: number;
  defaultTab: WorkspaceTab;
  defaultView: WorkspaceView;
  density: WorkspaceDensity;
  rightRailVisible: boolean;
  rightRailCollapsed: boolean;
  visibleWidgets: WorkspaceWidgetId[];
  widgetOrder: WorkspaceWidgetId[];
  defaultSort: string;
  pageSize: number;
  recentItemLimit: number;
}

export interface WorkspaceFolderNode {
  id: string;
  parent_id: string | null;
  name: string;
  system_key: 'chat_uploads' | 'personal_uploads' | null;
  document_count: number;
}

export interface WorkspaceFile {
  id: string;
  folder_id: string | null;
  name: string;
  file_type: string;
  size_bytes: number;
  modified_at: string;
  status: WorkspaceDocumentStatus;
  indexed: boolean;
  indexing_stage?: string | null;
  indexing_safe_message?: string | null;
  indexing_error_code?: string | null;
  retry_allowed?: boolean;
  indexing_updated_at?: string;
}

export interface WorkspaceTreeResponse {
  workspace: { id: string; name: string; workspace_type: 'personal'; visibility: 'private' };
  folders: WorkspaceFolderNode[];
}

export interface WorkspaceFolderResponse {
  folder_id: string | null;
  folders: WorkspaceFolderNode[];
  documents: WorkspaceFile[];
}

export interface WorkspaceSummaryResponse {
  workspace: WorkspaceTreeResponse['workspace'];
  storage: { used_bytes: number; quota_bytes: number | null; available: boolean };
  pinned: WorkspaceFile[];
  recent_activity: { id: string; action: string; created_at: string }[];
  recent_conversations: { id: string; title: string; updated_at: string }[];
}

export interface WorkspaceNote {
  id: string; title: string; content_json: Record<string, unknown> | null; content_markdown: string;
  content_format: 'markdown' | 'editor_json'; plain_text: string; is_pinned: boolean; is_archived: boolean;
  revision: number; created_at: string; updated_at: string;
  tags: Array<{ id: string; name: string; color?: string | null }>;
  linked_documents: Array<{ id: string; name: string; file_type: string }>;
}

export interface WorkspaceNoteList { items: WorkspaceNote[]; next_cursor: string | null; }

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
