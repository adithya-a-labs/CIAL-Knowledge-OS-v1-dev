import type { LucideIcon } from 'lucide-react';
import {
  Archive,
  BriefcaseBusiness,
  Building2,
  FileImage,
  FileText,
  FileVideo,
  Folder,
  HardHat,
  Lock,
  Monitor,
  Package,
  Plane,
  Shield,
  Users,
  Wallet,
  Wind,
  Wrench,
  Zap,
} from 'lucide-react';

export type KnowledgeTabId = 'all' | 'articles' | 'documents' | 'policies';
export type ViewMode = 'list' | 'grid';
export type SortMode = 'latest' | 'oldest' | 'name_asc' | 'name_desc' | 'type' | 'size';
export type KnowledgeItemKind = 'folder' | 'file';
export type FileIconType = 'folder' | 'pdf' | 'sheet' | 'document' | 'presentation' | 'image' | 'video' | 'archive';

export interface KnowledgeCategory {
  id: string;
  name: string;
  articles: number;
  docs: number;
  icon: LucideIcon;
  className: string;
  iconClassName: string;
}

export interface KnowledgeDepartment {
  id: string;
  name: string;
  documents: number;
  categories: number;
  icon: LucideIcon;
  iconClassName: string;
}

export interface KnowledgeDocument {
  id: string;
  name: string;
  kind: KnowledgeItemKind;
  category: string;
  department: string;
  owner: string;
  type: string;
  sizeLabel: string;
  sizeBytes: number;
  lastUpdated: string;
  updatedAt: string;
  iconType: FileIconType;
  sharedCount?: number;
}

export interface PopularContentItem {
  id: string;
  title: string;
  category: string;
  views: number;
  icon: LucideIcon;
}

export const tabs: Array<{ id: KnowledgeTabId; label: string }> = [
  { id: 'all', label: 'All Content' },
  { id: 'articles', label: 'Articles' },
  { id: 'documents', label: 'Documents' },
  { id: 'policies', label: 'Policies & SOPs' },
];

export const sortOptions: Array<{ label: string; value: SortMode }> = [
  { label: 'Latest', value: 'latest' },
  { label: 'Oldest', value: 'oldest' },
  { label: 'Name A-Z', value: 'name_asc' },
  { label: 'Name Z-A', value: 'name_desc' },
  { label: 'Type', value: 'type' },
  { label: 'Size', value: 'size' },
];

export const typeOptions = ['All Types', 'Folder', 'PDF', 'Sheet', 'Document', 'Presentation', 'Image', 'Video', 'Archive'];

export const knowledgeCategories: KnowledgeCategory[] = [
  {
    id: 'airfield-operations',
    name: 'Airfield Operations',
    articles: 138,
    docs: 24,
    icon: Plane,
    className: 'border-info/30 bg-info/10/75 hover:border-info/40',
    iconClassName: 'text-info',
  },
  {
    id: 'baggage-handling',
    name: 'Baggage Handling',
    articles: 92,
    docs: 18,
    icon: Package,
    className: 'border-warning/30 bg-warning/10/75 hover:border-warning/40',
    iconClassName: 'text-warning',
  },
  {
    id: 'electrical-systems',
    name: 'Electrical Systems',
    articles: 78,
    docs: 16,
    icon: Zap,
    className: 'border-yellow-200 bg-yellow-50/80 hover:border-yellow-300',
    iconClassName: 'text-warning',
  },
  {
    id: 'hvac-systems',
    name: 'HVAC Systems',
    articles: 65,
    docs: 12,
    icon: Wind,
    className: 'border-cyan-200 bg-cyan-50/75 hover:border-cyan-300',
    iconClassName: 'text-cyan-600',
  },
  {
    id: 'safety-fire',
    name: 'Safety & Fire',
    articles: 110,
    docs: 22,
    icon: Shield,
    className: 'border-destructive/30 bg-destructive/10/75 hover:border-destructive/40',
    iconClassName: 'text-destructive',
  },
  {
    id: 'it-systems',
    name: 'IT Systems',
    articles: 45,
    docs: 11,
    icon: Monitor,
    className: 'border-indigo-200 bg-indigo-50/75 hover:border-indigo-300',
    iconClassName: 'text-indigo-600',
  },
  {
    id: 'terminal-operations',
    name: 'Terminal Operations',
    articles: 90,
    docs: 20,
    icon: Building2,
    className: 'border-emerald-200 bg-emerald-50/75 hover:border-emerald-300',
    iconClassName: 'text-emerald-600',
  },
];

export const departments: KnowledgeDepartment[] = [
  { id: 'engineering', name: 'Engineering', documents: 247, categories: 18, icon: HardHat, iconClassName: 'text-emerald-600' },
  { id: 'operations', name: 'Operations', documents: 182, categories: 12, icon: Wrench, iconClassName: 'text-info' },
  { id: 'safety', name: 'Safety', documents: 143, categories: 9, icon: Shield, iconClassName: 'text-destructive' },
  { id: 'it', name: 'IT', documents: 96, categories: 6, icon: Monitor, iconClassName: 'text-indigo-600' },
  { id: 'facilities', name: 'Facilities', documents: 81, categories: 5, icon: Building2, iconClassName: 'text-success' },
  { id: 'hr', name: 'HR', documents: 43, categories: 4, icon: Users, iconClassName: 'text-warning' },
  { id: 'finance', name: 'Finance', documents: 28, categories: 3, icon: Wallet, iconClassName: 'text-sky-600' },
  { id: 'security', name: 'Security', documents: 35, categories: 4, icon: Lock, iconClassName: 'text-violet-700' },
];

export const documents: KnowledgeDocument[] = [
  {
    id: 'folder-engineering-manuals',
    name: 'Engineering Manuals',
    kind: 'folder',
    category: 'HVAC Systems',
    department: 'Engineering',
    owner: 'Engineering',
    type: 'Folder',
    sizeLabel: '-',
    sizeBytes: 0,
    lastUpdated: 'Today, 10:45 AM',
    updatedAt: '2026-07-07T10:45:00+05:30',
    iconType: 'folder',
    sharedCount: 2,
  },
  {
    id: 'folder-hvac-system-designs',
    name: 'HVAC System Designs',
    kind: 'folder',
    category: 'HVAC Systems',
    department: 'Engineering',
    owner: 'Engineering',
    type: 'Folder',
    sizeLabel: '-',
    sizeBytes: 0,
    lastUpdated: 'Today, 09:30 AM',
    updatedAt: '2026-07-07T09:30:00+05:30',
    iconType: 'folder',
    sharedCount: 3,
  },
  {
    id: 'folder-maintenance-checklists',
    name: 'Maintenance Checklists',
    kind: 'folder',
    category: 'HVAC Systems',
    department: 'Engineering',
    owner: 'Engineering',
    type: 'Folder',
    sizeLabel: '-',
    sizeBytes: 0,
    lastUpdated: 'Yesterday, 04:15 PM',
    updatedAt: '2026-07-06T16:15:00+05:30',
    iconType: 'folder',
    sharedCount: 2,
  },
  {
    id: 'runway-lighting-manual',
    name: 'Runway Lighting System - Maintenance Manual.pdf',
    kind: 'file',
    category: 'Electrical Systems',
    department: 'Engineering',
    owner: 'Arjun Menon',
    type: 'PDF',
    sizeLabel: '2.4 MB',
    sizeBytes: 2400000,
    lastUpdated: '23 May 2025, 11:20 AM',
    updatedAt: '2025-05-23T11:20:00+05:30',
    iconType: 'pdf',
  },
  {
    id: 'hvac-preventive-checklist',
    name: 'HVAC Preventive Maintenance Checklist.xlsx',
    kind: 'file',
    category: 'HVAC Systems',
    department: 'Engineering',
    owner: 'Ananya Nair',
    type: 'Sheet',
    sizeLabel: '820 KB',
    sizeBytes: 820000,
    lastUpdated: '20 May 2025, 02:10 PM',
    updatedAt: '2025-05-20T14:10:00+05:30',
    iconType: 'sheet',
  },
  {
    id: 'fire-safety-procedures',
    name: 'Fire Safety & Emergency Procedures.docx',
    kind: 'file',
    category: 'Safety & Fire',
    department: 'Safety',
    owner: 'Safety Team',
    type: 'Document',
    sizeLabel: '1.1 MB',
    sizeBytes: 1100000,
    lastUpdated: '21 May 2025, 09:05 AM',
    updatedAt: '2025-05-21T09:05:00+05:30',
    iconType: 'document',
  },
  {
    id: 'dg-set-sop',
    name: 'DG Set Operation & Maintenance SOP.pdf',
    kind: 'file',
    category: 'Electrical Systems',
    department: 'Facilities',
    owner: 'Vishnu Raj',
    type: 'PDF',
    sizeLabel: '1.7 MB',
    sizeBytes: 1700000,
    lastUpdated: '17 May 2025, 03:40 PM',
    updatedAt: '2025-05-17T15:40:00+05:30',
    iconType: 'pdf',
  },
  {
    id: 'hvac-temp-control',
    name: 'HVAC Temperature Control Standards.pptx',
    kind: 'file',
    category: 'HVAC Systems',
    department: 'Engineering',
    owner: 'Ananya Nair',
    type: 'Presentation',
    sizeLabel: '3.2 MB',
    sizeBytes: 3200000,
    lastUpdated: '19 May 2025, 10:30 AM',
    updatedAt: '2025-05-19T10:30:00+05:30',
    iconType: 'presentation',
  },
  {
    id: 'terminal-bridge-sop',
    name: 'Passenger Boarding Bridge Operation SOP.pdf',
    kind: 'file',
    category: 'Terminal Operations',
    department: 'Operations',
    owner: 'Operations Control',
    type: 'PDF',
    sizeLabel: '1.9 MB',
    sizeBytes: 1900000,
    lastUpdated: '15 May 2025, 01:35 PM',
    updatedAt: '2025-05-15T13:35:00+05:30',
    iconType: 'pdf',
  },
  {
    id: 'network-outage-steps',
    name: 'Network Outage First Response Steps.docx',
    kind: 'file',
    category: 'IT Systems',
    department: 'IT',
    owner: 'IT Service Desk',
    type: 'Document',
    sizeLabel: '640 KB',
    sizeBytes: 640000,
    lastUpdated: '14 May 2025, 04:20 PM',
    updatedAt: '2025-05-14T16:20:00+05:30',
    iconType: 'document',
  },
  {
    id: 'baggage-conveyor-guide',
    name: 'Baggage Conveyor Troubleshooting Guide.pdf',
    kind: 'file',
    category: 'Baggage Handling',
    department: 'Operations',
    owner: 'Baggage Systems',
    type: 'PDF',
    sizeLabel: '2.1 MB',
    sizeBytes: 2100000,
    lastUpdated: '12 May 2025, 11:10 AM',
    updatedAt: '2025-05-12T11:10:00+05:30',
    iconType: 'pdf',
  },
  {
    id: 'solar-panel-inspection',
    name: 'Solar Panel Inspection Checklist.xlsx',
    kind: 'file',
    category: 'Electrical Systems',
    department: 'Facilities',
    owner: 'Facilities Team',
    type: 'Sheet',
    sizeLabel: '910 KB',
    sizeBytes: 910000,
    lastUpdated: '10 May 2025, 09:40 AM',
    updatedAt: '2025-05-10T09:40:00+05:30',
    iconType: 'sheet',
  },
  {
    id: 'airside-stand-layout',
    name: 'Airside Stand Layout Reference.png',
    kind: 'file',
    category: 'Airfield Operations',
    department: 'Operations',
    owner: 'Airside Planning',
    type: 'Image',
    sizeLabel: '4.8 MB',
    sizeBytes: 4800000,
    lastUpdated: '08 May 2025, 05:55 PM',
    updatedAt: '2025-05-08T17:55:00+05:30',
    iconType: 'image',
  },
  {
    id: 'ground-support-monitoring',
    name: 'Ground Support Monitoring Procedure.docx',
    kind: 'file',
    category: 'Airfield Operations',
    department: 'Operations',
    owner: 'Airfield Safety',
    type: 'Document',
    sizeLabel: '780 KB',
    sizeBytes: 780000,
    lastUpdated: '07 May 2025, 12:25 PM',
    updatedAt: '2025-05-07T12:25:00+05:30',
    iconType: 'document',
  },
  {
    id: 'evacuation-drill-video',
    name: 'Terminal Evacuation Drill Briefing.mp4',
    kind: 'file',
    category: 'Safety & Fire',
    department: 'Safety',
    owner: 'Emergency Response',
    type: 'Video',
    sizeLabel: '42 MB',
    sizeBytes: 42000000,
    lastUpdated: '05 May 2025, 02:00 PM',
    updatedAt: '2025-05-05T14:00:00+05:30',
    iconType: 'video',
  },
  {
    id: 'security-audit-pack',
    name: 'Access Control Audit Pack.zip',
    kind: 'file',
    category: 'Terminal Operations',
    department: 'Security',
    owner: 'Security Office',
    type: 'Archive',
    sizeLabel: '8.5 MB',
    sizeBytes: 8500000,
    lastUpdated: '30 Apr 2025, 10:15 AM',
    updatedAt: '2025-04-30T10:15:00+05:30',
    iconType: 'archive',
  },
  {
    id: 'hr-induction-folder',
    name: 'HR Induction Policies',
    kind: 'folder',
    category: 'Terminal Operations',
    department: 'HR',
    owner: 'HR',
    type: 'Folder',
    sizeLabel: '-',
    sizeBytes: 0,
    lastUpdated: '28 Apr 2025, 03:10 PM',
    updatedAt: '2025-04-28T15:10:00+05:30',
    iconType: 'folder',
    sharedCount: 4,
  },
  {
    id: 'finance-procurement-sop',
    name: 'Procurement Approval SOP.pdf',
    kind: 'file',
    category: 'Terminal Operations',
    department: 'Finance',
    owner: 'Finance',
    type: 'PDF',
    sizeLabel: '1.3 MB',
    sizeBytes: 1300000,
    lastUpdated: '25 Apr 2025, 11:30 AM',
    updatedAt: '2025-04-25T11:30:00+05:30',
    iconType: 'pdf',
  },
  {
    id: 'facilities-map',
    name: 'Facilities Asset Register.xlsx',
    kind: 'file',
    category: 'Terminal Operations',
    department: 'Facilities',
    owner: 'Facilities Team',
    type: 'Sheet',
    sizeLabel: '1.6 MB',
    sizeBytes: 1600000,
    lastUpdated: '21 Apr 2025, 04:05 PM',
    updatedAt: '2025-04-21T16:05:00+05:30',
    iconType: 'sheet',
  },
  {
    id: 'fire-extinguisher-guide',
    name: 'Fire Extinguisher Types and Usage Guide.docx',
    kind: 'file',
    category: 'Safety & Fire',
    department: 'Safety',
    owner: 'Safety Team',
    type: 'Document',
    sizeLabel: '1.2 MB',
    sizeBytes: 1200000,
    lastUpdated: '18 Apr 2025, 09:45 AM',
    updatedAt: '2025-04-18T09:45:00+05:30',
    iconType: 'document',
  },
];

export const popularContent: PopularContentItem[] = [
  { id: 'fire-extinguisher-types', title: 'Fire Extinguisher Types and Usage Guide', category: 'Safety & Fire', views: 1245, icon: Shield },
  { id: 'baggage-conveyor-troubleshooting', title: 'Baggage Conveyor Troubleshooting Guide', category: 'Baggage Handling', views: 1102, icon: Package },
  { id: 'hvac-temperature-control', title: 'HVAC Temperature Control Standards', category: 'HVAC Systems', views: 987, icon: Wind },
  { id: 'ground-support-monitoring-procedure', title: 'Ground Support Monitoring Procedure', category: 'Airfield Operations', views: 856, icon: Plane },
  { id: 'emergency-response-t1-t2', title: 'Emergency Response Protocol - T1 & T2', category: 'Safety & Fire', views: 812, icon: Shield },
  { id: 'passenger-boarding-bridge', title: 'Passenger Boarding Bridge Operation SOP', category: 'Airfield Operations', views: 789, icon: Building2 },
  { id: 'network-outage-response', title: 'Network Outage First Response Steps', category: 'IT Systems', views: 723, icon: Monitor },
  { id: 'solar-panel-inspection', title: 'Solar Panel Inspection Checklist', category: 'Electrical Systems', views: 654, icon: Zap },
];

export const fileIconMap: Record<FileIconType, LucideIcon> = {
  folder: Folder,
  pdf: FileText,
  sheet: BriefcaseBusiness,
  document: FileText,
  presentation: FileText,
  image: FileImage,
  video: FileVideo,
  archive: Archive,
};

export function filterDocuments(
  items: KnowledgeDocument[],
  searchQuery: string,
  selectedCategory: string,
  selectedDepartment: string,
  selectedType: string,
  activeTab: KnowledgeTabId,
) {
  const query = searchQuery.trim().toLowerCase();

  return items.filter((item) => {
    const matchesSearch =
      !query ||
      item.name.toLowerCase().includes(query) ||
      item.category.toLowerCase().includes(query) ||
      item.department.toLowerCase().includes(query) ||
      item.owner.toLowerCase().includes(query) ||
      item.type.toLowerCase().includes(query);

    const matchesCategory = !selectedCategory || item.category === selectedCategory;
    const matchesDepartment = !selectedDepartment || item.department === selectedDepartment;
    const matchesType = selectedType === 'All Types' || item.type === selectedType;
    const matchesTab =
      activeTab === 'all' ||
      activeTab === 'documents' ||
      (activeTab === 'policies' && (item.name.toLowerCase().includes('sop') || item.name.toLowerCase().includes('procedure') || item.type === 'PDF'));

    return matchesSearch && matchesCategory && matchesDepartment && matchesType && matchesTab;
  });
}

export function filterPopularContent(items: PopularContentItem[], searchQuery: string, selectedCategory: string) {
  const query = searchQuery.trim().toLowerCase();

  return items.filter((item) => {
    const matchesSearch = !query || item.title.toLowerCase().includes(query) || item.category.toLowerCase().includes(query);
    const matchesCategory = !selectedCategory || item.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });
}

export function sortDocuments(items: KnowledgeDocument[], sortMode: SortMode) {
  const foldersFirst = (a: KnowledgeDocument, b: KnowledgeDocument) => {
    if (a.kind === b.kind) return 0;
    return a.kind === 'folder' ? -1 : 1;
  };

  return [...items].sort((a, b) => {
    const folderSort = foldersFirst(a, b);
    if (folderSort !== 0) return folderSort;

    if (sortMode === 'oldest') return new Date(a.updatedAt).getTime() - new Date(b.updatedAt).getTime();
    if (sortMode === 'name_asc') return a.name.localeCompare(b.name);
    if (sortMode === 'name_desc') return b.name.localeCompare(a.name);
    if (sortMode === 'type') return a.type.localeCompare(b.type) || a.name.localeCompare(b.name);
    if (sortMode === 'size') return b.sizeBytes - a.sizeBytes;

    return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
  });
}
