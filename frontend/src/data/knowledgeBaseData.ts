import { KnowledgeCategory, KnowledgeArticle } from '../types';

export const KB_CATEGORIES: KnowledgeCategory[] = [
  { id: '1', name: 'Airfield Operations', icon: 'Plane', count: 138 },
  { id: '2', name: 'Baggage Handling', icon: 'Package', count: 92 },
  { id: '3', name: 'Electrical Systems', icon: 'Zap', count: 78 },
  { id: '4', name: 'HVAC Systems', icon: 'Wind', count: 65 },
  { id: '5', name: 'Safety & Fire', icon: 'Shield', count: 110 },
  { id: '6', name: 'IT Systems', icon: 'Monitor', count: 45 },
  { id: '7', name: 'Terminal Operations', icon: 'Building2', count: 90 },
];

export const POPULAR_ARTICLES: KnowledgeArticle[] = [
  { id: '1', title: 'Fire Extinguisher Types and Usage Guide', category: 'Safety & Fire', views: 1245 },
  { id: '2', title: 'Baggage Conveyor Troubleshooting Guide', category: 'Baggage Handling', views: 1102 },
  { id: '3', title: 'HVAC Temperature Control Standards', category: 'HVAC Systems', views: 987 },
  { id: '4', title: 'Ground Support Monitoring Procedure', category: 'Airfield Operations', views: 856 },
  { id: '5', title: 'Emergency Response Protocol – T1 & T2', category: 'Safety & Fire', views: 812 },
  { id: '6', title: 'Passenger Boarding Bridge Operation SOP', category: 'Airfield Operations', views: 789 },
  { id: '7', title: 'Network Outage First Response Steps', category: 'IT Systems', views: 723 },
  { id: '8', title: 'Solar Panel Inspection Checklist', category: 'Electrical Systems', views: 654 },
];

export const POPULAR_SEARCHES = [
  { query: 'Runway lighting fault', count: 126 },
  { query: 'Baggage conveyor error', count: 98 },
  { query: 'Fire alarm escalation', count: 87 },
  { query: 'HVAC not cooling', count: 65 },
  { query: 'DG set backup failure', count: 54 },
];

export const KNOWLEDGE_GAPS = [
  { topic: 'Passenger Boarding Bridge', count: 5 },
  { topic: 'Runway Rubber Removal', count: 4 },
  { topic: 'ATC Communication Failure', count: 3 },
  { topic: 'Fuel Hydrant System', count: 3 },
  { topic: 'Apron Flood Lighting', count: 2 },
];

export const RECENT_CONVERSATIONS = [
  { id: '1', question: 'What is the procedure for runway edge light not working?', time: '2h ago' },
  { id: '2', question: 'How to reset baggage conveyor motor fault?', time: '5h ago' },
  { id: '3', question: 'Fire alarm keeps triggering in T3 – what to check?', time: '1d ago' },
];

export const ANNOUNCEMENTS = [
  {
    id: '1',
    title: 'Annual Fire Safety Drill',
    body: 'Fire safety drill for all departments on 25th May 2025',
    date: '25 May 2025, 10:00 AM'
  },
  {
    id: '2',
    title: 'System Maintenance Window',
    body: 'Planned maintenance for CMMS integration on 28th May 2025 from 2:00 AM – 5:00 AM',
    date: '28 May 2025, 02:00 AM'
  }
];
