import { Department } from '../types';

export const DEPARTMENTS: Department[] = [
  {
    id: '1',
    name: 'Engineering',
    headName: 'Arjun Nair',
    headInitials: 'AN',
    icon: 'Wrench',
    stats: { documents: 744, sops: 38, unresolvedQuestions: 5 }
  },
  {
    id: '2',
    name: 'Safety',
    headName: 'Deepa Menon',
    headInitials: 'DM',
    icon: 'ShieldCheck',
    stats: { documents: 512, sops: 62, unresolvedQuestions: 3 }
  },
  {
    id: '3',
    name: 'Operations',
    headName: 'Deepa Menon',
    headInitials: 'DM',
    icon: 'Settings2',
    stats: { documents: 480, sops: 45, unresolvedQuestions: 4 }
  },
  {
    id: '4',
    name: 'IT',
    headName: 'Vikram Pillai',
    headInitials: 'VP',
    icon: 'Monitor',
    stats: { documents: 210, sops: 22, unresolvedQuestions: 1 }
  },
  {
    id: '5',
    name: 'Facilities',
    headName: 'Riya Nambiar',
    headInitials: 'RN',
    icon: 'Building2',
    stats: { documents: 310, sops: 28, unresolvedQuestions: 2 }
  },
  {
    id: '6',
    name: 'Commercial',
    headName: 'Meera Patel',
    headInitials: 'MP',
    icon: 'TrendingUp',
    stats: { documents: 202, sops: 12, unresolvedQuestions: 1 }
  }
];
