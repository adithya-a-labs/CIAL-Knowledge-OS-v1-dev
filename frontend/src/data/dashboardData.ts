import { KPIStat } from '../types';

export const DASHBOARD_KPI_STATS: KPIStat[] = [
  { label: 'Total Documents', value: '2,458', delta: '+112 this month', trend: 'up', icon: 'FileText' },
  { label: 'Knowledge Articles', value: '1,125', delta: '+68 this month', trend: 'up', icon: 'Lightbulb' },
  { label: 'SOPs', value: '326', delta: '+18 this month', trend: 'up', icon: 'ClipboardList' },
  { label: 'FAQs', value: '187', delta: '+9 this month', trend: 'up', icon: 'HelpCircle' },
  { label: 'Unanswered Queries', value: '14', delta: '+3 this month', trend: 'up', icon: 'AlertCircle' },
];

export const HERO_QUICK_SEARCHES: string[] = [
  'Runway lighting fault procedure',
  'Baggage handling SOP',
  'Fire safety checklist',
  'HVAC maintenance',
];

export const QUICK_ACTIONS: { label: string; icon: string; path: string; colorClass: string }[] = [
  { label: 'New Query', icon: 'Plus', path: '/assistant/new', colorClass: 'bg-accent text-primary' },
  { label: 'Upload Document', icon: 'FileText', path: '/documents', colorClass: 'bg-warning/10 text-warning' },
  { label: 'My Bookmarks', icon: 'BookmarkCheck', path: '/documents', colorClass: 'bg-info/10 text-info' },
  // TODO: Reintroduce department-owned admin actions in a future Admin Console.
];

export const DOC_TYPE_COLORS: Record<string, string> = {
  Manual: 'bg-info/15 text-info-foreground',
  SOP: 'bg-success/15 text-success-foreground',
  Checklist: 'bg-accent text-accent-foreground',
  Policy: 'bg-warning/15 text-warning-foreground',
  Report: 'bg-muted text-muted-foreground',
};

export const KPI_ICON_BG: Record<string, string> = {
  FileText: 'hsl(100 35% 93%)',
  Lightbulb: 'hsl(200 50% 92%)',
  ClipboardList: 'hsl(260 40% 93%)',
  HelpCircle: 'hsl(30 60% 93%)',
  AlertCircle: 'hsl(0 50% 93%)',
};
