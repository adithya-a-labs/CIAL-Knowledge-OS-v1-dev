import {
  Bot,
  BookOpen,
  FileText,
  FolderOpen,
  Home,
  MessageSquare,
  Mic,
  Search,
  Send,
  Sparkles,
  UploadCloud,
  Bookmark,
  UserRound,
  BookMarked,
} from 'lucide-react';
import type React from 'react';

export type HomeIcon = React.ComponentType<{ size?: number; className?: string }>;

export interface HomeNavItem {
  label: string;
  path: string;
  icon: HomeIcon;
}

export const homeNavItems: HomeNavItem[] = [
  { label: 'Home', path: '/', icon: Home },
  { label: 'AI Assistant', path: '/assistant', icon: Bot },
  { label: 'Knowledge Center', path: '/knowledge-center', icon: BookOpen },
  // TODO: Surface department ownership in a future Admin Console, not employee navigation.
  { label: 'My Workspace', path: '/workspace', icon: UserRound },
  { label: 'Saved Knowledge', path: '/saved-knowledge', icon: Bookmark },
];

export const suggestedPrompts = [
  'How do I replace runway edge lights?',
  'Show baggage handling SOP',
  'Compare old and new fire policy',
  'Summarize this manual',
  'Find documents mentioning CAT III',
];

export const quickActions = [
  { title: 'Ask AI', subtitle: 'Get instant answers', path: '/assistant', icon: MessageSquare, tone: 'green' },
  { title: 'Browse Knowledge', subtitle: 'Explore documents', path: '/knowledge-center', icon: FolderOpen, tone: 'blue' },
  { title: 'Upload File', subtitle: 'Add documents', path: '/workspace/documents', icon: UploadCloud, tone: 'violet' },
  { title: 'Create Summary', subtitle: 'Summarize anything', path: '/workspace/summaries/new', icon: FileText, tone: 'rose' },
];

export const continueWorking = [
  {
    title: 'Fire Safety SOP Discussion',
    description: 'You asked about fire alarm escalation procedure',
    time: '2h ago',
    icon: MessageSquare,
    tone: 'green',
  },
  {
    title: 'Runway Lighting Maintenance',
    description: 'Continued conversation',
    time: 'Yesterday',
    icon: Bot,
    tone: 'violet',
  },
  {
    title: 'Baggage Handling System',
    description: 'SOP clarification',
    time: '2 days ago',
    icon: MessageSquare,
    tone: 'orange',
  },
];

export const recommendedDocuments = [
  {
    title: 'Updated Runway Lighting Manual',
    meta: 'Engineering - Updated 1 day ago',
    badge: 'Manual',
    icon: FileText,
  },
  {
    title: 'Electrical Maintenance Checklist',
    meta: 'Engineering - Viewed yesterday',
    badge: 'Checklist',
    icon: FileText,
  },
  {
    title: 'DGCA Circular: Aerodrome Standards',
    meta: 'Compliance - New',
    badge: 'Policy',
    icon: BookMarked,
  },
];

export const knowledgeUpdates = [
  {
    title: '12 documents updated',
    description: 'Runway Lighting Manual revised',
    time: '1 day ago',
    tone: 'green',
  },
  {
    title: 'New SOP added',
    description: 'Wildlife Hazard Management Plan',
    time: '2 days ago',
    tone: 'violet',
  },
  {
    title: 'New DGCA circular',
    description: 'Aerodrome Standards Update',
    time: '3 days ago',
    tone: 'amber',
  },
  {
    title: '4 unanswered queries',
    description: 'Need expert attention',
    time: 'View now',
    tone: 'blue',
  },
];

export const recentDocuments = [
  {
    name: 'Runway Lighting System - Maintenance Manual',
    department: 'Engineering',
    type: 'Manual',
    updated: '23 May 2025',
  },
  {
    name: 'Baggage Handling System - SOP',
    department: 'Operations',
    type: 'SOP',
    updated: '22 May 2025',
  },
  {
    name: 'Fire Safety & Emergency Procedures',
    department: 'Safety',
    type: 'Manual',
    updated: '21 May 2025',
  },
  {
    name: 'HVAC Preventive Maintenance Checklist',
    department: 'Engineering',
    type: 'Checklist',
    updated: '20 May 2025',
  },
  {
    name: 'Wildlife Hazard Management Plan',
    department: 'Safety',
    type: 'Policy',
    updated: '19 May 2025',
  },
];

export const popularSearches = [
  { term: 'Runway lighting fault', count: 126 },
  { term: 'Baggage conveyor error', count: 98 },
  { term: 'Fire alarm escalation', count: 87 },
  { term: 'HVAC not cooling', count: 65 },
  { term: 'DG set backup failure', count: 54 },
];

export const expertsOnCall = [
  {
    initials: 'RK',
    name: 'Rohit Kumar',
    role: 'Senior Engineer',
    department: 'Engineering',
    status: 'Available',
    tone: 'blue',
  },
  {
    initials: 'SM',
    name: 'Sneha Menon',
    role: 'Safety Manager',
    department: 'Safety',
    status: 'Available',
    tone: 'green',
  },
  {
    initials: 'AP',
    name: 'Arjun Pillai',
    role: 'Operations Lead',
    department: 'Operations',
    status: 'Busy',
    tone: 'orange',
  },
];

export const aiHeroIcons = { Search, Mic, Send, Sparkles };
