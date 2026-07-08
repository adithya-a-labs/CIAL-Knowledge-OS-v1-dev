// ─── Navigation ───────────────────────────────────────────────────────────────
export interface NavItem {
  label: string;
  path: string;
  icon: string;
  requiredRole?: string;
  children?: NavItem[];
}

// ─── Auth / Users ─────────────────────────────────────────────────────────────
export type Role = 'admin' | 'manager' | 'engineer' | 'viewer';

export interface Permission {
  canUpload: boolean;
  canDelete: boolean;
  canEdit: boolean;
  canAccessAdmin: boolean;
}

export interface User {
  name: string;
  role: string;
  department: string;
  avatar: string | null;
  initials: string;
  notificationsCount: number;
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
export interface DashboardBlock {
  id: string;
  title: string;
  component: string;
  colSpan: 1 | 2 | 3;
  visible: boolean;
}

export interface KPIStat {
  label: string;
  value: string;
  delta: string;
  trend: 'up' | 'down';
  icon: string;
}

// ─── Documents ────────────────────────────────────────────────────────────────
export interface Document {
  id: string;
  name: string;
  category: string;
  department: string;
  type: string;
  lastUpdated: string;
  status: string;
}

// ─── SOPs ─────────────────────────────────────────────────────────────────────
export interface SOP {
  id: string;
  title: string;
  department: string;
  version: string;
  status: string;
  owner: string;
  lastReview: string;
  nextReview: string;
}

// ─── FAQs ─────────────────────────────────────────────────────────────────────
export interface FAQ {
  id: string;
  question: string;
  answer: string;
  category: string;
  helpfulCount: number;
  lastUpdated: string;
}

// ─── Knowledge Base ───────────────────────────────────────────────────────────
export interface KnowledgeCategory {
  id: string;
  name: string;
  icon: string;
  count: number;
}

export interface KnowledgeArticle {
  id: string;
  title: string;
  category: string;
  views: number;
}

// ─── Departments ──────────────────────────────────────────────────────────────
export interface DepartmentStats {
  documents: number;
  sops: number;
  unresolvedQuestions: number;
}

export interface Department {
  id: string;
  name: string;
  icon: string;
  headName: string;
  headInitials: string;
  stats: DepartmentStats;
  color?: string;
}

// ─── Audit Log ────────────────────────────────────────────────────────────────
export interface AuditLog {
  id: string;
  timestamp: string;
  user: string;
  action: string;
  resource: string;
  ip: string;
  status: string;
}
