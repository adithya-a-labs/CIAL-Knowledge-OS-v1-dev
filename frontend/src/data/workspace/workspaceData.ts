import type {
  WorkspaceDocument,
  WorkspaceConversation,
  WorkspaceCollection,
  WorkspaceActivityEntry,
  StorageInfo,
  StorageBreakdownItem,
  WorkspaceStatItem,
} from './workspaceTypes';

export const CURRENT_WORKSPACE_USER_ID = 'user-ananya-nair';

export const WORKSPACE_STORAGE: StorageInfo = {
  usedBytes: 3.2 * 1024 * 1024 * 1024,
  totalBytes: 5 * 1024 * 1024 * 1024,
  usedGB: 3.2,
  totalGB: 5,
  availableGB: 1.8,
  percentUsed: 64,
  resetNote: 'Storage resets on 1st of every month',
};

export const STORAGE_PRIVACY_BULLETS: string[] = [
  'Only you can view your documents',
  'Included in your AI search and answers',
  'Not shared with anyone',
  'Secure and encrypted',
];

export const WORKSPACE_STATS: WorkspaceStatItem[] = [
  { key: 'documents', label: 'My Documents', count: 128, unit: 'documents', icon: 'FileText', href: '/workspace/documents' },
  { key: 'notes', label: 'My Notes', count: 34, unit: 'notes', icon: 'StickyNote', href: '/workspace/notes' },
  { key: 'collections', label: 'My Collections', count: 12, unit: 'collections', icon: 'FolderOpen', href: '/workspace' },
  { key: 'conversations', label: 'My Conversations', count: 56, unit: 'conversations', icon: 'MessageSquare', href: '/workspace/conversations' },
];

export const MY_DOCUMENTS: WorkspaceDocument[] = [
  {
    id: 'wd-1',
    name: 'Vendor Manual - AGL Controller.pdf',
    category: 'Runway Systems',
    size: '12.4 MB',
    sizeBytes: 12400000,
    uploadedAt: '2h ago',
    fileType: 'pdf',
    visibility: 'private',
    ownerId: CURRENT_WORKSPACE_USER_ID,
  },
  {
    id: 'wd-2',
    name: 'Runway Lighting Inspection Notes.docx',
    category: 'My Notes',
    size: '2.1 MB',
    sizeBytes: 2100000,
    uploadedAt: '1d ago',
    fileType: 'docx',
    visibility: 'private',
    ownerId: CURRENT_WORKSPACE_USER_ID,
  },
  {
    id: 'wd-3',
    name: 'PAPI Calibration Report - 23 May 2025.pdf',
    category: 'Reports',
    size: '4.3 MB',
    sizeBytes: 4300000,
    uploadedAt: '2d ago',
    fileType: 'pdf',
    visibility: 'private',
    ownerId: CURRENT_WORKSPACE_USER_ID,
  },
  {
    id: 'wd-4',
    name: 'Maintenance Cost Analysis.xlsx',
    category: 'Analysis',
    size: '1.8 MB',
    sizeBytes: 1800000,
    uploadedAt: '3d ago',
    fileType: 'xlsx',
    visibility: 'private',
    ownerId: CURRENT_WORKSPACE_USER_ID,
  },
  {
    id: 'wd-5',
    name: 'Transformer Oil Test Results.pdf',
    category: 'Electrical Systems',
    size: '3.6 MB',
    sizeBytes: 3600000,
    uploadedAt: '5d ago',
    fileType: 'pdf',
    visibility: 'private',
    ownerId: CURRENT_WORKSPACE_USER_ID,
  },
];

export const MY_CONVERSATIONS: WorkspaceConversation[] = [
  { id: 'wc-1', question: 'How to troubleshoot AGL controller failure?', sources: ['Enterprise', 'My Workspace'], time: '2h ago', ownerId: CURRENT_WORKSPACE_USER_ID },
  { id: 'wc-2', question: 'Runway lighting circuit isolation procedure', sources: ['Enterprise', 'My Workspace'], time: '1d ago', ownerId: CURRENT_WORKSPACE_USER_ID },
  { id: 'wc-3', question: 'PAPI calibration steps and tools required', sources: ['Enterprise', 'My Workspace'], time: '2d ago', ownerId: CURRENT_WORKSPACE_USER_ID },
  { id: 'wc-4', question: 'Transformer overheating possible causes', sources: ['Enterprise', 'My Workspace'], time: '3d ago', ownerId: CURRENT_WORKSPACE_USER_ID },
  { id: 'wc-5', question: 'Best practices for cable termination', sources: ['Enterprise', 'My Workspace'], time: '5d ago', ownerId: CURRENT_WORKSPACE_USER_ID },
];

export const MY_COLLECTIONS: WorkspaceCollection[] = [
  { id: 'col-1', name: 'Runway Lighting', itemCount: 18, ownerId: CURRENT_WORKSPACE_USER_ID },
  { id: 'col-2', name: 'Electrical Systems', itemCount: 22, ownerId: CURRENT_WORKSPACE_USER_ID },
  { id: 'col-3', name: 'Maintenance Notes', itemCount: 14, ownerId: CURRENT_WORKSPACE_USER_ID },
  { id: 'col-4', name: 'Vendor Manuals', itemCount: 9, ownerId: CURRENT_WORKSPACE_USER_ID },
  { id: 'col-5', name: 'Project Reports', itemCount: 6, ownerId: CURRENT_WORKSPACE_USER_ID },
];

export const STORAGE_BREAKDOWN: StorageBreakdownItem[] = [
  { name: 'Documents', value: 2.1, color: '#4a7c3f' },
  { name: 'Notes', value: 0.6, color: '#7ab648' },
  { name: 'Chats', value: 0.3, color: '#e8820c' },
  { name: 'Others', value: 0.2, color: '#9dc88d' },
];

export const RECENT_ACTIVITY: WorkspaceActivityEntry[] = [
  { id: 'act-1', type: 'upload', description: 'Uploaded Vendor Manual - AGL Controller.pdf', time: '2h ago', ownerId: CURRENT_WORKSPACE_USER_ID },
  { id: 'act-2', type: 'note', description: 'Added note: PAPI alignment observation', time: '1d ago', ownerId: CURRENT_WORKSPACE_USER_ID },
  { id: 'act-3', type: 'chat', description: 'AI Chat: Runway lighting isolation', time: '1d ago', ownerId: CURRENT_WORKSPACE_USER_ID },
  { id: 'act-4', type: 'bookmark', description: 'Bookmarked: Fire alarm escalation SOP', time: '2d ago', ownerId: CURRENT_WORKSPACE_USER_ID },
];

export const WORKSPACE_AUDIT_LOG = [
  { id: 'wal-1', userId: CURRENT_WORKSPACE_USER_ID, action: 'upload', resource: 'Vendor Manual - AGL Controller.pdf', timestamp: '2025-05-23 09:10:00' },
  { id: 'wal-2', userId: CURRENT_WORKSPACE_USER_ID, action: 'ai_query', resource: 'AGL controller failure troubleshoot', timestamp: '2025-05-23 07:30:00' },
  { id: 'wal-3', userId: CURRENT_WORKSPACE_USER_ID, action: 'bookmark', resource: 'Fire alarm escalation SOP', timestamp: '2025-05-22 14:00:00' },
  { id: 'wal-4', userId: CURRENT_WORKSPACE_USER_ID, action: 'delete', resource: 'Old draft report.pdf', timestamp: '2025-05-21 11:00:00' },
];
