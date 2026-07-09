import { NavItem } from '../types';

export const NAV_ITEMS: NavItem[] = [
  { label: 'Home', path: '/', icon: 'Home' },
  { label: 'AI Assistant', path: '/assistant', icon: 'Bot' },
  {
    label: 'Knowledge Center',
    path: '/knowledge-center',
    icon: 'BookOpen',
    children: [
      { label: 'All Content', path: '/knowledge-center', icon: 'BookOpen' },
      { label: 'Articles', path: '/knowledge-center/articles', icon: 'FileText' },
      { label: 'Documents', path: '/knowledge-center/documents', icon: 'FileText' },
      { label: 'Policies & SOPs', path: '/knowledge-center/policies', icon: 'ShieldCheck' },
    ],
  },
  { label: 'Quick Answers', path: '/faqs', icon: 'HelpCircle' },
  { label: 'Expert Directory', path: '/experts', icon: 'Users2' },
  { label: 'Learning Hub', path: '/learning', icon: 'GraduationCap' },
  { label: 'Knowledge Graph', path: '/knowledge-graph', icon: 'Network' },
  { label: 'Knowledge Gaps', path: '/knowledge-gaps', icon: 'AlertTriangle' },
  { label: 'Analytics', path: '/analytics', icon: 'BarChart2' },
];

export const WORKSPACE_NAV_ITEMS: NavItem[] = [
  { label: 'My Documents', path: '/workspace/documents', icon: 'FileText' },
  { label: 'My Notes', path: '/workspace/notes', icon: 'StickyNote' },
  { label: 'Bookmarks', path: '/workspace/bookmarks', icon: 'Bookmark' },
  { label: 'Shared with Me', path: '/workspace/shared', icon: 'Users' },
  { label: 'Trash', path: '/workspace/trash', icon: 'Trash2' },
];

export const ADMIN_NAV_ITEMS: NavItem[] = [
  { label: 'Admin', path: '/admin', icon: 'Shield', requiredRole: 'admin' },
  { label: 'Users', path: '/admin/users', icon: 'Users', requiredRole: 'admin' },
  { label: 'Roles & Permissions', path: '/admin/roles', icon: 'KeyRound', requiredRole: 'admin' },
  { label: 'Audit Logs', path: '/admin/audit', icon: 'ScrollText', requiredRole: 'admin' },
  { label: 'Settings', path: '/admin/settings', icon: 'Settings', requiredRole: 'admin' },
];
