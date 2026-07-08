export type Role = 'admin' | 'engineer' | 'manager' | 'viewer';

export interface Permission {
  canUpload: boolean;
  canDelete: boolean;
  canEdit: boolean;
  canAccessAdmin: boolean;
}

export interface User {
  name: string;
  role: Role;
  department: string;
  avatar: string | null;
  initials: string;
  notificationsCount?: number;
}

export interface NavItem {
  label: string;
  path: string;
  icon: string;
  requiredRole?: Role;
  children?: NavItem[];
}

export interface DashboardBlock {
  id: string;
  title: string;
  component: string;
  colSpan: 1 | 2 | 3;
  visible: boolean;
}

export interface Document {
  id: string;
  name: string;
  category: string;
  department: string;
  type: string;
  lastUpdated: string;
  status: 'Published' | 'Draft' | 'Archived';
}

export interface Asset {
  id: string;
  assetId: string;
  name: string;
  category: string;
  location: string;
  status: 'Operational' | 'Under Maintenance' | 'Out of Service';
}

export interface KPIStat {
  label: string;
  value: string | number;
  delta: string;
  trend: 'up' | 'down' | 'neutral';
  icon: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: DocumentCitation[];
}

export interface DocumentCitation {
  id: string;
  documentName: string;
  department: string;
  pageRef: string;
  url: string;
}

export interface Announcement {
  id: string;
  title: string;
  body: string;
  date: string;
}

export interface KnowledgeArticle {
  id: string;
  title: string;
  category: string;
  views: number;
}

export interface KnowledgeCategory {
  id: string;
  name: string;
  icon: string;
  count: number;
}

export interface Department {
  id: string;
  name: string;
  headName: string;
  headInitials: string;
  icon: string;
  stats: {
    documents: number;
    sops: number;
    unresolvedQuestions: number;
  };
}

export interface SOP {
  id: string;
  title: string;
  department: string;
  version: string;
  status: 'Active' | 'Under Review' | 'Archived';
  owner: string;
  lastReview: string;
  nextReview: string;
}

export interface FAQ {
  id: string;
  question: string;
  answer: string;
  category: string;
  helpfulCount: number;
  lastUpdated: string;
}

export interface AuditLog {
  id: string;
  timestamp: string;
  user: string;
  action: string;
  resource: string;
  ip: string;
  status: 'Success' | 'Failed';
}
