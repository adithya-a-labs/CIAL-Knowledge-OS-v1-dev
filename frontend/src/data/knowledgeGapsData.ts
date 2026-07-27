export type GapSeverity = 'critical' | 'high' | 'medium' | 'low';

export interface KnowledgeGap {
  id: string;
  question: string;
  category: string;
  department: string;
  searchCount: number;
  severity: GapSeverity;
  trend: 'rising' | 'stable' | 'falling';
  lastAsked: string;
  suggestedAction: string;
}

export interface MissingDocument {
  id: string;
  title: string;
  type: string;
  department: string;
  priority: GapSeverity;
  requestCount: number;
}

export interface DepartmentHealthScore {
  department: string;
  score: number;
  documents: number;
  sops: number;
  coverage: number;
  trend: 'up' | 'down' | 'stable';
}

export const KNOWLEDGE_GAPS: KnowledgeGap[] = [
  {
    id: 'gap-1',
    question: 'What is the procedure for PAPI system failure during low visibility operations?',
    category: 'Airfield Operations',
    department: 'Engineering',
    searchCount: 42,
    severity: 'critical',
    trend: 'rising',
    lastAsked: '2h ago',
    suggestedAction: 'Create SOP for PAPI failure contingency during LVO',
  },
  {
    id: 'gap-2',
    question: 'How to calibrate the ILS localizer after runway resurfacing?',
    category: 'Airfield Operations',
    department: 'Engineering',
    searchCount: 38,
    severity: 'critical',
    trend: 'rising',
    lastAsked: '4h ago',
    suggestedAction: 'Document ILS calibration post-maintenance procedure',
  },
  {
    id: 'gap-3',
    question: 'Emergency protocol for fuel spill near aircraft parking bay?',
    category: 'Safety',
    department: 'Safety',
    searchCount: 31,
    severity: 'high',
    trend: 'stable',
    lastAsked: '1d ago',
    suggestedAction: 'Update Fire & Fuel Emergency SOP with apron-specific procedures',
  },
  {
    id: 'gap-4',
    question: 'Baggage reconciliation process for international transit passengers?',
    category: 'Ground Operations',
    department: 'Operations',
    searchCount: 27,
    severity: 'high',
    trend: 'rising',
    lastAsked: '1d ago',
    suggestedAction: 'Create FAQ and SOP for international transit baggage handling',
  },
  {
    id: 'gap-5',
    question: 'SITA DCS system downtime contingency procedure?',
    category: 'IT Systems',
    department: 'IT',
    searchCount: 24,
    severity: 'high',
    trend: 'stable',
    lastAsked: '2d ago',
    suggestedAction: 'Document manual check-in procedures for SITA outages',
  },
  {
    id: 'gap-6',
    question: 'Generator switchover during terminal power failure?',
    category: 'Electrical',
    department: 'Engineering',
    searchCount: 19,
    severity: 'medium',
    trend: 'falling',
    lastAsked: '3d ago',
    suggestedAction: 'Add generator switchover checklist to Electrical SOP',
  },
  {
    id: 'gap-7',
    question: 'VIP lounge protocol for state guest arrivals?',
    category: 'Passenger Services',
    department: 'Operations',
    searchCount: 14,
    severity: 'medium',
    trend: 'stable',
    lastAsked: '4d ago',
    suggestedAction: 'Create VIP protocol document in Operations Manual',
  },
  {
    id: 'gap-8',
    question: 'HVAC zone temperature control override for server room?',
    category: 'HVAC',
    department: 'Engineering',
    searchCount: 11,
    severity: 'low',
    trend: 'stable',
    lastAsked: '5d ago',
    suggestedAction: 'Add server room HVAC override to HVAC Maintenance Guide',
  },
];

export const MISSING_DOCUMENTS: MissingDocument[] = [
  { id: 'md-1', title: 'PAPI Failure Contingency SOP', type: 'SOP', department: 'Engineering', priority: 'critical', requestCount: 18 },
  { id: 'md-2', title: 'ILS Post-Maintenance Calibration Guide', type: 'Manual', department: 'Engineering', priority: 'critical', requestCount: 15 },
  { id: 'md-3', title: 'International Transit Baggage SOP', type: 'SOP', department: 'Operations', priority: 'high', requestCount: 12 },
  { id: 'md-4', title: 'SITA DCS Downtime Procedure', type: 'SOP', department: 'IT', priority: 'high', requestCount: 10 },
  { id: 'md-5', title: 'Fuel Spill Emergency Response', type: 'Policy', department: 'Safety', priority: 'high', requestCount: 9 },
];

export const DEPT_HEALTH_SCORES: DepartmentHealthScore[] = [
  { department: 'Engineering', score: 78, documents: 744, sops: 38, coverage: 82, trend: 'up' },
  { department: 'Safety', score: 91, documents: 512, sops: 62, coverage: 94, trend: 'up' },
  { department: 'Operations', score: 69, documents: 480, sops: 45, coverage: 72, trend: 'down' },
  { department: 'IT', score: 58, documents: 198, sops: 22, coverage: 61, trend: 'stable' },
  { department: 'HR', score: 72, documents: 134, sops: 14, coverage: 76, trend: 'up' },
  { department: 'Finance', score: 64, documents: 88, sops: 8, coverage: 68, trend: 'stable' },
];

export const GAP_OVERVIEW_STATS = [
  { label: 'Unanswered Queries', value: '146', delta: '−8 vs last week', trend: 'down' as const, color: '#e8820c' },
  { label: 'Critical Gaps', value: '2', delta: '↑1 new this week', trend: 'up' as const, color: '#dc2626' },
  { label: 'Missing SOPs', value: '5', delta: 'Identified', trend: 'stable' as const, color: '#7c3aed' },
  { label: 'Knowledge Coverage', value: '76%', delta: '+2% this month', trend: 'up' as const, color: '#4a7c3f' },
];

export const GAP_SEVERITY_COLORS: Record<GapSeverity, string> = {
  critical: 'bg-destructive/15 text-destructive border border-destructive/30',
  high: 'bg-warning/15 text-warning-foreground border border-warning/30',
  medium: 'bg-warning/15 text-warning-foreground border border-warning/30',
  low: 'border border-border bg-muted text-muted-foreground',
};
