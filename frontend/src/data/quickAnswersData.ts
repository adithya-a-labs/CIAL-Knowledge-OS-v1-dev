import type { LucideIcon } from 'lucide-react';
import {
  BriefcaseBusiness,
  Building2,
  CircleEllipsis,
  Flame,
  Lightbulb,
  Monitor,
  Package,
  Plane,
  ShieldCheck,
  Users,
  Wrench,
} from 'lucide-react';

export interface QuickAnswerQuestion {
  id: string;
  question: string;
  category: string;
  helpful: string;
  preview: string;
  fullAnswer: string;
  sources: string[];
  icon: LucideIcon;
  iconClassName: string;
}

export interface QuickAnswerCategory {
  id: string;
  name: string;
  count: number;
  icon: LucideIcon;
  iconClassName: string;
}

export interface RecentlyAskedItem {
  id: string;
  question: string;
  category: string;
  timestamp: string;
}

export const suggestionChips = [
  'How to report a bird strike?',
  'Runway access during heavy rain?',
  'IT incident response process?',
  'Fire alarm keeps triggering?',
];

export const popularQuestions: QuickAnswerQuestion[] = [
  {
    id: 'baggage-conveyor-reset',
    question: 'How to reset baggage conveyor motor fault?',
    category: 'Baggage Handling',
    helpful: '124 found helpful',
    preview: 'Follow the reset procedure in the Baggage Handling SOP v4.2. Ensure the system is in safe mode before resetting the motor.',
    fullAnswer:
      'Follow the reset procedure in the Baggage Handling SOP v4.2. Stop the conveyor, verify safe mode on the control panel, clear visible jams, reset the motor fault, and perform a low-speed test run before returning it to operations.',
    sources: ['Baggage Handling SOP v4.2', 'Conveyor Safety Checklist', 'Engineering Shift Log'],
    icon: Package,
    iconClassName: 'bg-emerald-50 text-emerald-600',
  },
  {
    id: 'fire-alarm-t3',
    question: 'What to do if fire alarm keeps triggering in T3?',
    category: 'Safety & Fire',
    helpful: '98 found helpful',
    preview: 'Check the zone panel for the triggered detector and follow the Fire Alarm Response Procedure in the Safety Manual.',
    fullAnswer:
      'Check the zone panel to identify the triggered detector. Inspect the area for smoke, heat, dust or maintenance activity, notify Fire Safety, and follow the Fire Alarm Response Procedure before silencing or resetting the panel.',
    sources: ['Fire Alarm Response Procedure', 'Safety Manual', 'T3 Zone Panel Reference'],
    icon: Flame,
    iconClassName: 'bg-destructive/10 text-destructive',
  },
  {
    id: 'preventive-maintenance-cmms',
    question: 'How to book preventive maintenance in CMMS?',
    category: 'IT Systems',
    helpful: '87 found helpful',
    preview: "Log in to CMMS, select 'Preventive Maintenance', choose the asset and schedule as per the maintenance calendar.",
    fullAnswer:
      "Log in to CMMS, open Work Orders, choose 'Preventive Maintenance', select the asset, add schedule details from the maintenance calendar, assign the owner, and submit for approval.",
    sources: ['CMMS User Guide', 'Preventive Maintenance Workflow', 'Asset Management SOP'],
    icon: BriefcaseBusiness,
    iconClassName: 'bg-info/10 text-info',
  },
  {
    id: 'airfield-lighting-report',
    question: 'How to report airfield lighting at airside?',
    category: 'Airfield Operations',
    helpful: '76 found helpful',
    preview: 'Log a request in the Airside Lighting System. Provide location, light ID and issue description with photo if possible.',
    fullAnswer:
      'Log a request in the Airside Lighting System with exact location, light ID, fault type, operational impact, and a photo if safe to capture. Notify Airfield Operations for priority faults affecting active stands or runway areas.',
    sources: ['Airside Lighting System Guide', 'Airfield Operations Manual', 'AGL Fault Reporting SOP'],
    icon: Lightbulb,
    iconClassName: 'bg-violet-50 text-violet-600',
  },
  {
    id: 'emergency-contacts',
    question: 'Can I find emergency contact numbers?',
    category: 'Safety & Fire',
    helpful: '65 found helpful',
    preview: 'Yes, all emergency contacts are listed in the Emergency Response Directory in the Safety Manual.',
    fullAnswer:
      'Yes. Emergency contacts are listed in the Emergency Response Directory in the Safety Manual and on department notice boards. Use the latest directory before calling external emergency support.',
    sources: ['Emergency Response Directory', 'Safety Manual', 'Department Contact Matrix'],
    icon: Wrench,
    iconClassName: 'bg-success/10 text-success',
  },
];

export const quickAnswerCategories: QuickAnswerCategory[] = [
  { id: 'baggage-handling', name: 'Baggage Handling', count: 32, icon: Package, iconClassName: 'bg-emerald-50 text-emerald-600' },
  { id: 'safety-fire', name: 'Safety & Fire', count: 48, icon: Flame, iconClassName: 'bg-destructive/10 text-destructive' },
  { id: 'airfield-operations', name: 'Airfield Operations', count: 36, icon: Plane, iconClassName: 'bg-info/10 text-info' },
  { id: 'it-systems', name: 'IT Systems', count: 44, icon: Monitor, iconClassName: 'bg-indigo-50 text-indigo-600' },
  { id: 'engineering', name: 'Engineering', count: 29, icon: Wrench, iconClassName: 'bg-warning/10 text-warning' },
  { id: 'people-hr', name: 'People & HR', count: 26, icon: Users, iconClassName: 'bg-success/10 text-success' },
  { id: 'compliance', name: 'Compliance', count: 18, icon: ShieldCheck, iconClassName: 'bg-violet-50 text-violet-600' },
  { id: 'facilities', name: 'Facilities', count: 21, icon: Building2, iconClassName: 'bg-sky-50 text-sky-600' },
  { id: 'general', name: 'General', count: 30, icon: CircleEllipsis, iconClassName: 'bg-muted text-muted-foreground' },
];

export const recentlyAsked: RecentlyAskedItem[] = [
  { id: 'hvac-t2', question: 'What is the procedure for HVAC not cooling in T2?', category: 'HVAC Systems', timestamp: '2 hours ago' },
  { id: 'it-ticket-escalation', question: 'How to escalate an unresolved IT ticket?', category: 'IT Systems', timestamp: 'Yesterday' },
  { id: 'asset-handover-docs', question: 'What documents are needed for asset handover?', category: 'Airfield Operations', timestamp: '2 days ago' },
  { id: 'hr-leave-portal', question: 'How to apply for leave in the HR portal?', category: 'People & HR', timestamp: '3 days ago' },
  { id: 'emergency-evacuation-plan', question: 'Where can I find the emergency evacuation plan?', category: 'Safety & Fire', timestamp: '4 days ago' },
];

export function buildMockAnswer(query: string) {
  const normalized = query.trim();
  const match = popularQuestions.find((item) => item.question.toLowerCase().includes(normalized.toLowerCase()));

  if (match) return match;

  return {
    id: 'mock-generated-answer',
    question: normalized || 'Ask a question',
    category: 'CIAL Knowledge',
    helpful: 'Mock answer',
    preview:
      'This is a frontend-only mock response. Future AI integration can replace this state with a generated answer grounded in enterprise knowledge sources.',
    fullAnswer:
      'This is a frontend-only mock response. In the production integration, this area can call the CIAL AI answer service, retrieve citations from Knowledge Center, and stream a grounded response back to the user.',
    sources: ['CIAL Knowledge Center', 'AI answer integration placeholder'],
    icon: Lightbulb,
    iconClassName: 'bg-accent text-primary',
  } satisfies QuickAnswerQuestion;
}
