export interface Expert {
  id: string;
  name: string;
  role: string;
  department: string;
  initials: string;
  expertiseTags: string[];
  knowledgeScore: number;
  documentsContributed: number;
  sopsAuthored: number;
  helpfulAnswers: number;
  available: boolean;
  email: string;
}

export const EXPERTS: Expert[] = [
  {
    id: 'exp-1',
    name: 'Arjun Nair',
    role: 'Senior Electrical Engineer',
    department: 'Engineering',
    initials: 'AN',
    expertiseTags: ['AGL Systems', 'Runway Lighting', 'Transformer Maintenance', 'Electrical Safety'],
    knowledgeScore: 94,
    documentsContributed: 48,
    sopsAuthored: 12,
    helpfulAnswers: 186,
    available: true,
    email: 'arjun.nair@cial.aero',
  },
  {
    id: 'exp-2',
    name: 'Deepa Menon',
    role: 'Safety Officer',
    department: 'Safety',
    initials: 'DM',
    expertiseTags: ['Fire Safety', 'Emergency Procedures', 'FOD Management', 'ICAO Compliance'],
    knowledgeScore: 91,
    documentsContributed: 62,
    sopsAuthored: 28,
    helpfulAnswers: 214,
    available: true,
    email: 'deepa.menon@cial.aero',
  },
  {
    id: 'exp-3',
    name: 'Vikram Pillai',
    role: 'Operations Manager',
    department: 'Operations',
    initials: 'VP',
    expertiseTags: ['Baggage Handling', 'Ground Ops', 'Passenger Services', 'Terminal Management'],
    knowledgeScore: 88,
    documentsContributed: 35,
    sopsAuthored: 18,
    helpfulAnswers: 142,
    available: false,
    email: 'vikram.pillai@cial.aero',
  },
  {
    id: 'exp-4',
    name: 'Meera Patel',
    role: 'IT Systems Architect',
    department: 'IT',
    initials: 'MP',
    expertiseTags: ['Network Infrastructure', 'SITA Systems', 'Cybersecurity', 'Airport IT'],
    knowledgeScore: 87,
    documentsContributed: 29,
    sopsAuthored: 9,
    helpfulAnswers: 98,
    available: true,
    email: 'meera.patel@cial.aero',
  },
  {
    id: 'exp-5',
    name: 'Rajesh Kumar',
    role: 'HVAC Specialist',
    department: 'Engineering',
    initials: 'RK',
    expertiseTags: ['HVAC Systems', 'Air Quality', 'Preventive Maintenance', 'Energy Efficiency'],
    knowledgeScore: 83,
    documentsContributed: 22,
    sopsAuthored: 7,
    helpfulAnswers: 74,
    available: true,
    email: 'rajesh.kumar@cial.aero',
  },
  {
    id: 'exp-6',
    name: 'Priya Krishnan',
    role: 'Airfield Operations Supervisor',
    department: 'Operations',
    initials: 'PK',
    expertiseTags: ['Airfield Safety', 'Wildlife Hazard', 'NOTAM Management', 'ATC Coordination'],
    knowledgeScore: 90,
    documentsContributed: 41,
    sopsAuthored: 21,
    helpfulAnswers: 167,
    available: false,
    email: 'priya.krishnan@cial.aero',
  },
];

export const EXPERT_DEPARTMENTS = ['All Departments', 'Engineering', 'Safety', 'Operations', 'IT'];
export const EXPERT_TAGS = ['AGL Systems', 'Fire Safety', 'Baggage Handling', 'HVAC', 'Airfield Safety', 'IT', 'Electrical'];
