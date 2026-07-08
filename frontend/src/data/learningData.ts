export type CourseStatus = 'not_started' | 'in_progress' | 'completed' | 'mandatory';
export type CourseLevel = 'Beginner' | 'Intermediate' | 'Advanced';

export interface Course {
  id: string;
  title: string;
  department: string;
  category: string;
  duration: string;
  level: CourseLevel;
  status: CourseStatus;
  progress: number;
  completionDate?: string;
  dueDate?: string;
  isMandatory: boolean;
  enrolledCount: number;
  completionRate: number;
  instructor: string;
  tags: string[];
}

export interface LearningPath {
  id: string;
  title: string;
  description: string;
  courseCount: number;
  completedCount: number;
  estimatedHours: number;
  department: string;
}

export const COURSES: Course[] = [
  {
    id: 'crs-1',
    title: 'Runway Lighting Systems — Fundamentals',
    department: 'Engineering',
    category: 'Airfield',
    duration: '3h 20m',
    level: 'Intermediate',
    status: 'in_progress',
    progress: 65,
    dueDate: '30 May 2025',
    isMandatory: true,
    enrolledCount: 42,
    completionRate: 78,
    instructor: 'Arjun Nair',
    tags: ['AGL', 'Runway', 'Lighting'],
  },
  {
    id: 'crs-2',
    title: 'Emergency Evacuation Procedures',
    department: 'Safety',
    category: 'Safety & Compliance',
    duration: '2h 00m',
    level: 'Beginner',
    status: 'completed',
    progress: 100,
    completionDate: '18 May 2025',
    isMandatory: true,
    enrolledCount: 186,
    completionRate: 94,
    instructor: 'Deepa Menon',
    tags: ['Emergency', 'Evacuation', 'Fire Safety'],
  },
  {
    id: 'crs-3',
    title: 'Baggage Handling — Advanced Operations',
    department: 'Operations',
    category: 'Ground Operations',
    duration: '4h 15m',
    level: 'Advanced',
    status: 'not_started',
    progress: 0,
    isMandatory: false,
    enrolledCount: 28,
    completionRate: 62,
    instructor: 'Vikram Pillai',
    tags: ['Baggage', 'Ground Ops', 'ULD'],
  },
  {
    id: 'crs-4',
    title: 'ICAO Annex 14 — Compliance Overview',
    department: 'Safety',
    category: 'Regulatory',
    duration: '5h 30m',
    level: 'Intermediate',
    status: 'in_progress',
    progress: 32,
    dueDate: '15 Jun 2025',
    isMandatory: true,
    enrolledCount: 64,
    completionRate: 55,
    instructor: 'Deepa Menon',
    tags: ['ICAO', 'Compliance', 'Regulatory'],
  },
  {
    id: 'crs-5',
    title: 'HVAC Preventive Maintenance',
    department: 'Engineering',
    category: 'Maintenance',
    duration: '2h 45m',
    level: 'Intermediate',
    status: 'completed',
    progress: 100,
    completionDate: '10 May 2025',
    isMandatory: false,
    enrolledCount: 18,
    completionRate: 88,
    instructor: 'Rajesh Kumar',
    tags: ['HVAC', 'Preventive Maintenance'],
  },
  {
    id: 'crs-6',
    title: 'FOD Prevention & Airfield Awareness',
    department: 'Operations',
    category: 'Airfield',
    duration: '1h 30m',
    level: 'Beginner',
    status: 'not_started',
    progress: 0,
    isMandatory: true,
    dueDate: '1 Jun 2025',
    enrolledCount: 122,
    completionRate: 71,
    instructor: 'Priya Krishnan',
    tags: ['FOD', 'Airfield Safety'],
  },
];

export const LEARNING_PATHS: LearningPath[] = [
  { id: 'lp-1', title: 'Airfield Engineering Mastery', description: 'End-to-end runway, lighting and electrical systems', courseCount: 6, completedCount: 2, estimatedHours: 18, department: 'Engineering' },
  { id: 'lp-2', title: 'Safety & Compliance Track', description: 'ICAO, DGCA and CIAL safety regulations', courseCount: 5, completedCount: 3, estimatedHours: 14, department: 'Safety' },
  { id: 'lp-3', title: 'Ground Operations Fundamentals', description: 'Baggage, ramp, and terminal operations', courseCount: 4, completedCount: 1, estimatedHours: 12, department: 'Operations' },
];

export const LEARNING_STATS = {
  totalCourses: 38,
  completedCourses: 12,
  inProgress: 4,
  mandatoryPending: 2,
  overallProgress: 68,
};

export const COURSE_CATEGORIES = ['All Categories', 'Airfield', 'Safety & Compliance', 'Ground Operations', 'Maintenance', 'Regulatory'];
export const COURSE_STATUSES = ['All Statuses', 'Completed', 'In Progress', 'Not Started', 'Mandatory'];
