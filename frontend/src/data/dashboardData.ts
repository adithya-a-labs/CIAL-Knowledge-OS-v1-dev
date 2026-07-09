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
  { label: 'New Query', icon: 'Plus', path: '/assistant', colorClass: 'bg-[#f0f7ed] text-[#4a7c3f]' },
  { label: 'Upload Document', icon: 'FileText', path: '/documents', colorClass: 'bg-[#fef3e8] text-[#e8820c]' },
  { label: 'My Bookmarks', icon: 'BookmarkCheck', path: '/documents', colorClass: 'bg-[#e8f0fe] text-[#3b5bdb]' },
  // TODO: Reintroduce department-owned admin actions in a future Admin Console.
];

export const DOC_TYPE_COLORS: Record<string, string> = {
  Manual: 'bg-blue-100 text-blue-700',
  SOP: 'bg-green-100 text-green-700',
  Checklist: 'bg-purple-100 text-purple-700',
  Policy: 'bg-orange-100 text-orange-700',
  Report: 'bg-gray-100 text-gray-600',
};

export const KPI_ICON_BG: Record<string, string> = {
  FileText: 'hsl(100 35% 93%)',
  Lightbulb: 'hsl(200 50% 92%)',
  ClipboardList: 'hsl(260 40% 93%)',
  HelpCircle: 'hsl(30 60% 93%)',
  AlertCircle: 'hsl(0 50% 93%)',
};
