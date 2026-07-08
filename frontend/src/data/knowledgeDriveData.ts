import type { LucideIcon } from 'lucide-react';
import {
  Archive,
  BookOpen,
  Building2,
  Clock3,
  FileImage,
  FileText,
  FileVideo,
  Folder,
  FolderArchive,
  FolderOpen,
  HardHat,
  Monitor,
  Package,
  Plane,
  ShieldCheck,
  Star,
  Users,
  Wind,
  Zap,
} from 'lucide-react';

export type DriveViewMode = 'grid' | 'list';
export type DriveSortMode = 'latest' | 'oldest' | 'name_asc' | 'name_desc' | 'type' | 'size';
export type DrivePreviewType = 'pdf' | 'docx' | 'xlsx' | 'pptx' | 'image' | 'video' | 'archive' | 'policy' | 'sop';

export interface DriveFolder {
  id: string;
  name: string;
  parentId: string | null;
  department: string;
  category: string;
  itemCount: number;
  locationLabel: string;
  suggested: boolean;
  tags: string[];
}

export interface DriveFile {
  id: string;
  name: string;
  extension: string;
  type: string;
  owner: string;
  ownerInitials: string;
  department: string;
  category: string;
  size: string;
  sizeBytes: number;
  updatedAt: string;
  lastUpdated: string;
  activityLabel: string;
  parentFolderId: string;
  tags: string[];
  starred?: boolean;
  bookmarked?: boolean;
  previewType: DrivePreviewType;
}

export interface DriveTreeNode {
  id: string;
  label: string;
  folderId?: string;
  icon?: LucideIcon;
  children?: DriveTreeNode[];
}

export const driveSortOptions: Array<{ label: string; value: DriveSortMode }> = [
  { label: 'Latest', value: 'latest' },
  { label: 'Oldest', value: 'oldest' },
  { label: 'Name A-Z', value: 'name_asc' },
  { label: 'Name Z-A', value: 'name_desc' },
  { label: 'Type', value: 'type' },
  { label: 'Size', value: 'size' },
];

export const driveFolders: DriveFolder[] = [
  { id: 'engineering-manuals', name: 'Engineering Manuals', parentId: null, department: 'Engineering', category: 'Manuals', itemCount: 42, locationLabel: 'in Knowledge Center', suggested: true, tags: ['engineering', 'manuals', 'hvac', 'electrical'] },
  { id: 'safety-fire-sops', name: 'Safety & Fire SOPs', parentId: null, department: 'Safety', category: 'Policies & SOPs', itemCount: 31, locationLabel: 'Safety', suggested: true, tags: ['safety', 'fire', 'sop', 'emergency'] },
  { id: 'hvac-systems', name: 'HVAC Systems', parentId: 'engineering-manuals', department: 'Engineering', category: 'HVAC Systems', itemCount: 18, locationLabel: 'Engineering', suggested: true, tags: ['hvac', 'cooling', 'maintenance'] },
  { id: 'airfield-operations', name: 'Airfield Operations', parentId: null, department: 'Operations', category: 'Airfield Operations', itemCount: 27, locationLabel: 'Operations', suggested: true, tags: ['airfield', 'runway', 'lighting'] },
  { id: 'baggage-handling', name: 'Baggage Handling', parentId: null, department: 'Operations', category: 'Baggage Handling', itemCount: 16, locationLabel: 'Operations', suggested: true, tags: ['baggage', 'conveyor', 'troubleshooting'] },
  { id: 'it-systems', name: 'IT Systems', parentId: null, department: 'IT', category: 'IT Systems', itemCount: 24, locationLabel: 'IT', suggested: true, tags: ['network', 'helpdesk', 'systems'] },
  { id: 'terminal-operations', name: 'Terminal Operations', parentId: null, department: 'Operations', category: 'Terminal Operations', itemCount: 22, locationLabel: 'Operations', suggested: true, tags: ['terminal', 'bridge', 'cleaning'] },
  { id: 'policies-sops', name: 'Policies & SOPs', parentId: null, department: 'CIAL', category: 'Policies & SOPs', itemCount: 54, locationLabel: 'Knowledge Center', suggested: true, tags: ['policy', 'sop', 'compliance'] },
  { id: 'electrical-systems', name: 'Electrical Systems', parentId: 'engineering-manuals', department: 'Engineering', category: 'Electrical Systems', itemCount: 14, locationLabel: 'Engineering', suggested: false, tags: ['electrical', 'lighting', 'solar'] },
  { id: 'runway-lighting', name: 'Runway Lighting', parentId: 'engineering-manuals', department: 'Engineering', category: 'Electrical Systems', itemCount: 9, locationLabel: 'Engineering', suggested: false, tags: ['runway', 'lighting', 'maintenance'] },
  { id: 'emergency-response', name: 'Emergency Response', parentId: 'safety-fire-sops', department: 'Safety', category: 'Safety & Fire', itemCount: 12, locationLabel: 'Safety', suggested: false, tags: ['emergency', 'response', 'evacuation'] },
  { id: 'wildlife-hazard', name: 'Wildlife Hazard', parentId: 'safety-fire-sops', department: 'Safety', category: 'Airfield Operations', itemCount: 7, locationLabel: 'Safety', suggested: false, tags: ['wildlife', 'hazard', 'airside'] },
];

export const driveFiles: DriveFile[] = [
  {
    id: 'runway-lighting-maintenance',
    name: 'Runway Lighting System - Maintenance Manual.pdf',
    extension: 'pdf',
    type: 'PDF',
    owner: 'Arjun Menon',
    ownerInitials: 'AM',
    department: 'Engineering',
    category: 'Electrical Systems',
    size: '2.4 MB',
    sizeBytes: 2400000,
    updatedAt: '2025-05-23T11:20:00+05:30',
    lastUpdated: 'Today',
    activityLabel: 'Arjun Menon opened',
    parentFolderId: 'runway-lighting',
    tags: ['runway', 'lighting', 'manual', 'maintenance', 'sop'],
    starred: true,
    previewType: 'pdf',
  },
  {
    id: 'fire-safety-emergency',
    name: 'Fire Safety & Emergency Procedures.docx',
    extension: 'docx',
    type: 'Document',
    owner: 'Safety Team',
    ownerInitials: 'ST',
    department: 'Safety',
    category: 'Safety & Fire',
    size: '1.1 MB',
    sizeBytes: 1100000,
    updatedAt: '2025-05-21T09:05:00+05:30',
    lastUpdated: '21 May',
    activityLabel: 'Safety Team modified',
    parentFolderId: 'safety-fire-sops',
    tags: ['fire', 'emergency', 'procedure', 'safety'],
    bookmarked: true,
    previewType: 'docx',
  },
  {
    id: 'hvac-preventive-checklist',
    name: 'HVAC Preventive Maintenance Checklist.xlsx',
    extension: 'xlsx',
    type: 'Sheet',
    owner: 'Ananya Nair',
    ownerInitials: 'AN',
    department: 'Engineering',
    category: 'HVAC Systems',
    size: '820 KB',
    sizeBytes: 820000,
    updatedAt: '2025-05-20T14:10:00+05:30',
    lastUpdated: '20 May',
    activityLabel: 'Ananya Nair modified',
    parentFolderId: 'hvac-systems',
    tags: ['hvac', 'checklist', 'maintenance', 'cmms'],
    previewType: 'xlsx',
  },
  {
    id: 'dg-set-operation',
    name: 'DG Set Operation & Maintenance SOP.pdf',
    extension: 'pdf',
    type: 'PDF',
    owner: 'Vishnu Raj',
    ownerInitials: 'VR',
    department: 'Engineering',
    category: 'Policies & SOPs',
    size: '1.7 MB',
    sizeBytes: 1700000,
    updatedAt: '2025-05-17T15:40:00+05:30',
    lastUpdated: '17 May',
    activityLabel: 'Vishnu Raj opened',
    parentFolderId: 'policies-sops',
    tags: ['dg set', 'maintenance', 'sop', 'facilities'],
    previewType: 'sop',
  },
  {
    id: 'hvac-temp-standards',
    name: 'HVAC Temperature Control Standards.pptx',
    extension: 'pptx',
    type: 'Presentation',
    owner: 'Ananya Nair',
    ownerInitials: 'AN',
    department: 'Engineering',
    category: 'HVAC Systems',
    size: '3.2 MB',
    sizeBytes: 3200000,
    updatedAt: '2025-05-19T10:30:00+05:30',
    lastUpdated: '19 May',
    activityLabel: 'Ananya Nair opened',
    parentFolderId: 'hvac-systems',
    tags: ['hvac', 'temperature', 'standards', 'presentation'],
    previewType: 'pptx',
  },
  {
    id: 'wildlife-hazard-plan',
    name: 'Wildlife Hazard Management Plan.pdf',
    extension: 'pdf',
    type: 'PDF',
    owner: 'Operations Team',
    ownerInitials: 'OP',
    department: 'Operations',
    category: 'Airfield Operations',
    size: '2.8 MB',
    sizeBytes: 2800000,
    updatedAt: '2025-05-16T09:25:00+05:30',
    lastUpdated: '18 May',
    activityLabel: 'Operations Team updated',
    parentFolderId: 'airfield-operations',
    tags: ['wildlife', 'hazard', 'airfield', 'safety'],
    previewType: 'pdf',
  },
  {
    id: 'network-outage-response',
    name: 'Network Outage First Response Steps.docx',
    extension: 'docx',
    type: 'Document',
    owner: 'IT Team',
    ownerInitials: 'IT',
    department: 'IT',
    category: 'IT Systems',
    size: '640 KB',
    sizeBytes: 640000,
    updatedAt: '2025-05-14T16:20:00+05:30',
    lastUpdated: '16 May',
    activityLabel: 'IT Team edited',
    parentFolderId: 'it-systems',
    tags: ['network', 'outage', 'helpdesk', 'incident'],
    previewType: 'docx',
  },
  {
    id: 'passenger-boarding-bridge',
    name: 'Passenger Boarding Bridge Operation SOP.pdf',
    extension: 'pdf',
    type: 'PDF',
    owner: 'Operations Team',
    ownerInitials: 'OP',
    department: 'Operations',
    category: 'Terminal Operations',
    size: '1.9 MB',
    sizeBytes: 1900000,
    updatedAt: '2025-05-15T13:35:00+05:30',
    lastUpdated: '14 May',
    activityLabel: 'Operations Team modified',
    parentFolderId: 'terminal-operations',
    tags: ['terminal', 'boarding bridge', 'operation', 'sop'],
    previewType: 'sop',
  },
  {
    id: 'solar-panel-inspection',
    name: 'Solar Panel Inspection Checklist.xlsx',
    extension: 'xlsx',
    type: 'Sheet',
    owner: 'Facilities Team',
    ownerInitials: 'FT',
    department: 'Facilities',
    category: 'Electrical Systems',
    size: '910 KB',
    sizeBytes: 910000,
    updatedAt: '2025-05-10T09:40:00+05:30',
    lastUpdated: '10 May',
    activityLabel: 'Facilities Team updated',
    parentFolderId: 'electrical-systems',
    tags: ['solar', 'inspection', 'checklist', 'electrical'],
    previewType: 'xlsx',
  },
  {
    id: 'baggage-conveyor-guide',
    name: 'Baggage Conveyor Troubleshooting Guide.pdf',
    extension: 'pdf',
    type: 'PDF',
    owner: 'Baggage Systems',
    ownerInitials: 'BS',
    department: 'Operations',
    category: 'Baggage Handling',
    size: '2.1 MB',
    sizeBytes: 2100000,
    updatedAt: '2025-05-12T11:10:00+05:30',
    lastUpdated: '12 May',
    activityLabel: 'Baggage Systems edited',
    parentFolderId: 'baggage-handling',
    tags: ['baggage', 'conveyor', 'troubleshooting', 'guide'],
    previewType: 'pdf',
  },
  {
    id: 'emergency-response-protocol',
    name: 'Emergency Response Protocol - T1 & T2.docx',
    extension: 'docx',
    type: 'Document',
    owner: 'Emergency Response',
    ownerInitials: 'ER',
    department: 'Safety',
    category: 'Safety & Fire',
    size: '1.4 MB',
    sizeBytes: 1400000,
    updatedAt: '2025-05-09T12:10:00+05:30',
    lastUpdated: '09 May',
    activityLabel: 'Emergency Response updated',
    parentFolderId: 'emergency-response',
    tags: ['emergency', 'response', 'terminal', 'protocol'],
    previewType: 'docx',
  },
  {
    id: 'terminal-cleaning-standards',
    name: 'Terminal 1 Cleaning Standards.pdf',
    extension: 'pdf',
    type: 'PDF',
    owner: 'Facilities Team',
    ownerInitials: 'FT',
    department: 'Facilities',
    category: 'Terminal Operations',
    size: '1.2 MB',
    sizeBytes: 1200000,
    updatedAt: '2025-05-06T15:30:00+05:30',
    lastUpdated: '06 May',
    activityLabel: 'Facilities Team updated',
    parentFolderId: 'terminal-operations',
    tags: ['terminal', 'cleaning', 'standards', 'facilities'],
    previewType: 'policy',
  },
];

export const driveTreeNodes: DriveTreeNode[] = [
  {
    id: 'departments',
    label: 'Departments',
    icon: Building2,
    children: [
      {
        id: 'engineering',
        label: 'Engineering',
        icon: HardHat,
        folderId: 'engineering-manuals',
        children: [
          { id: 'tree-hvac', label: 'HVAC Systems', icon: Folder, folderId: 'hvac-systems' },
          { id: 'tree-electrical', label: 'Electrical Systems', icon: Folder, folderId: 'electrical-systems' },
          { id: 'tree-runway-lighting', label: 'Runway Lighting', icon: Folder, folderId: 'runway-lighting' },
        ],
      },
      {
        id: 'operations',
        label: 'Operations',
        icon: Plane,
        folderId: 'airfield-operations',
        children: [
          { id: 'tree-airfield', label: 'Airfield Operations', icon: Folder, folderId: 'airfield-operations' },
          { id: 'tree-baggage', label: 'Baggage Handling', icon: Folder, folderId: 'baggage-handling' },
          { id: 'tree-terminal', label: 'Terminal Operations', icon: Folder, folderId: 'terminal-operations' },
        ],
      },
      {
        id: 'safety',
        label: 'Safety',
        icon: ShieldCheck,
        folderId: 'safety-fire-sops',
        children: [
          { id: 'tree-fire-safety', label: 'Fire Safety', icon: Folder, folderId: 'safety-fire-sops' },
          { id: 'tree-emergency', label: 'Emergency Response', icon: Folder, folderId: 'emergency-response' },
          { id: 'tree-wildlife', label: 'Wildlife Hazard', icon: Folder, folderId: 'wildlife-hazard' },
        ],
      },
      {
        id: 'it',
        label: 'IT',
        icon: Monitor,
        folderId: 'it-systems',
        children: [
          { id: 'tree-network', label: 'Network', icon: Folder, folderId: 'it-systems' },
          { id: 'tree-helpdesk', label: 'Helpdesk', icon: Folder, folderId: 'it-systems' },
          { id: 'tree-systems', label: 'Systems', icon: Folder, folderId: 'it-systems' },
        ],
      },
    ],
  },
];

export const driveNavItems: Array<{ id: string; label: string; icon: LucideIcon; folderId?: string }> = [
  { id: 'my-knowledge', label: 'My Knowledge', icon: FolderOpen },
  { id: 'shared', label: 'Shared with Me', icon: Users },
  { id: 'recent', label: 'Recent', icon: Clock3 },
  { id: 'starred', label: 'Starred', icon: Star },
  { id: 'bookmarks', label: 'Bookmarks', icon: BookOpen },
  { id: 'departments-link', label: 'Departments', icon: Building2 },
  { id: 'categories-link', label: 'Categories', icon: Archive },
  { id: 'policies-link', label: 'Policies & SOPs', icon: ShieldCheck, folderId: 'policies-sops' },
  { id: 'archived', label: 'Archived', icon: FolderArchive },
];

export function getFolderById(folderId: string | null) {
  return folderId ? driveFolders.find((folder) => folder.id === folderId) ?? null : null;
}

export function getBreadcrumb(folderId: string | null) {
  const crumbs: DriveFolder[] = [];
  let current = getFolderById(folderId);

  while (current) {
    crumbs.unshift(current);
    current = getFolderById(current.parentId);
  }

  return crumbs;
}

export function getChildFolders(folderId: string | null) {
  return driveFolders.filter((folder) => folder.parentId === folderId);
}

export function filterDriveFolders(folders: DriveFolder[], searchQuery: string) {
  const query = searchQuery.trim().toLowerCase();
  if (!query) return folders;

  return folders.filter((folder) =>
    [folder.name, folder.department, folder.category, folder.locationLabel, ...folder.tags].some((value) => value.toLowerCase().includes(query)),
  );
}

export function filterDriveFiles(files: DriveFile[], searchQuery: string, activeFolderId: string | null, includeAllWhenSearching = true) {
  const query = searchQuery.trim().toLowerCase();

  return files.filter((file) => {
    const matchesFolder = query && includeAllWhenSearching ? true : !activeFolderId || file.parentFolderId === activeFolderId;
    const matchesQuery =
      !query ||
      [file.name, file.extension, file.type, file.owner, file.department, file.category, ...file.tags].some((value) =>
        value.toLowerCase().includes(query),
      );

    return matchesFolder && matchesQuery;
  });
}

export function sortDriveFiles(files: DriveFile[], sortMode: DriveSortMode) {
  return [...files].sort((a, b) => {
    if (sortMode === 'oldest') return new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime();
    if (sortMode === 'name_asc') return a.name.localeCompare(b.name);
    if (sortMode === 'name_desc') return b.name.localeCompare(a.name);
    if (sortMode === 'type') return a.type.localeCompare(b.type) || a.name.localeCompare(b.name);
    if (sortMode === 'size') return b.sizeBytes - a.sizeBytes;
    return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
  });
}
