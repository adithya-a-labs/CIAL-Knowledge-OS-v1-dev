import { SOP } from '../types';

export const SOPS: SOP[] = [
  { id: '1', title: 'Animal Safety Management Policy', department: 'Safety', version: 'v4.1', status: 'Active', owner: 'Deepa Menon', lastReview: '12 Dec 2024', nextReview: '12 Dec 2025' },
  { id: '2', title: 'Annual Safety Inspection', department: 'Safety', version: 'v2.3', status: 'Active', owner: 'Arjun Nair', lastReview: '05 Nov 2024', nextReview: '05 Nov 2025' },
  { id: '3', title: 'Failure to Report Personnel Procedures', department: 'Operations', version: 'v1.8', status: 'Active', owner: 'Deepa Menon', lastReview: '20 Oct 2024', nextReview: '20 Oct 2025' },
  { id: '4', title: 'Wildlife Hazard Management SOP', department: 'Safety', version: 'v3.2', status: 'Under Review', owner: 'Deepa Menon', lastReview: '01 Sep 2024', nextReview: '01 Sep 2025' },
  { id: '5', title: 'Electrical Lockout Tagout Procedure', department: 'Engineering', version: 'v4.7', status: 'Active', owner: 'Arjun Nair', lastReview: '14 Aug 2024', nextReview: '14 Aug 2025' },
  { id: '6', title: 'Baggage Handling Safety SOP', department: 'Operations', version: 'v2.1', status: 'Active', owner: 'Meera Patel', lastReview: '30 Jul 2024', nextReview: '30 Jul 2025' },
  { id: '7', title: 'Fire Suppression System Test', department: 'Safety', version: 'v1.5', status: 'Active', owner: 'Deepa Menon', lastReview: '10 Jun 2024', nextReview: '10 Jun 2025' },
  { id: '8', title: 'HVAC Filter Replacement Procedure', department: 'Engineering', version: 'v3.0', status: 'Under Review', owner: 'Arjun Nair', lastReview: '22 May 2024', nextReview: '22 May 2025' },
  { id: '9', title: 'Runway Inspection SOP', department: 'Operations', version: 'v5.1', status: 'Active', owner: 'Vikram Pillai', lastReview: '15 Apr 2024', nextReview: '15 Apr 2025' },
  { id: '10', title: 'IT Incident Response Procedure', department: 'IT', version: 'v2.9', status: 'Archived', owner: 'Vikram Pillai', lastReview: '01 Mar 2024', nextReview: '01 Mar 2025' },
];

export const SOP_DEPARTMENTS: string[] = ['Engineering', 'Safety', 'Operations', 'IT'];

export const SOP_TYPES: string[] = ['SOP', 'Policy', 'Procedure'];

export const SOP_STATUSES: string[] = ['Active', 'Under Review', 'Archived'];
