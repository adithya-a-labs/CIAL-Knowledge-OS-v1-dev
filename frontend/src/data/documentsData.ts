import { Document } from '../types';

export const DOCUMENTS: Document[] = [
  { id: '1', name: 'Runway Lighting System – Maintenance Manual', category: 'Airfield Operations', department: 'Engineering', type: 'Manual', lastUpdated: '23 May 2025', status: 'Published' },
  { id: '2', name: 'Fire Safety & Emergency Procedures', category: 'Safety & Fire', department: 'Safety', type: 'Manual', lastUpdated: '21 May 2025', status: 'Published' },
  { id: '3', name: 'Baggage Handling System – SOP', category: 'Baggage Handling', department: 'Operations', type: 'SOP', lastUpdated: '20 May 2025', status: 'Published' },
  { id: '4', name: 'HVAC Preventive Maintenance Checklist', category: 'HVAC Systems', department: 'Engineering', type: 'Checklist', lastUpdated: '20 May 2025', status: 'Published' },
  { id: '5', name: 'Wildlife Hazard Management Plan', category: 'Safety & Fire', department: 'Safety', type: 'Policy', lastUpdated: '19 May 2025', status: 'Published' },
  { id: '6', name: 'Passenger Boarding Bridge – Maintenance Manual', category: 'Airfield Operations', department: 'Engineering', type: 'Manual', lastUpdated: '18 May 2025', status: 'Published' },
  { id: '7', name: 'DG Set Operation & Maintenance', category: 'Electrical Systems', department: 'Engineering', type: 'Manual', lastUpdated: '17 May 2025', status: 'Published' },
  { id: '8', name: 'Terminal 1 Cleaning Standards', category: 'Terminal Operations', department: 'Facilities', type: 'SOP', lastUpdated: '15 May 2025', status: 'Published' },
  { id: '9', name: 'IT Helpdesk Troubleshooting Guide', category: 'IT Systems', department: 'IT', type: 'Manual', lastUpdated: '14 May 2025', status: 'Published' },
  { id: '10', name: 'Vehicle Movement on Apron - Rules', category: 'Airfield Operations', department: 'Operations', type: 'Policy', lastUpdated: '12 May 2025', status: 'Published' },
  { id: '11', name: 'Emergency Evacuation Routes', category: 'Safety & Fire', department: 'Safety', type: 'Manual', lastUpdated: '10 May 2025', status: 'Published' },
  { id: '12', name: 'X-Ray Machine Calibration', category: 'Security', department: 'Engineering', type: 'Checklist', lastUpdated: '09 May 2025', status: 'Published' },
  { id: '13', name: 'Lift and Escalator Maintenance', category: 'Terminal Operations', department: 'Engineering', type: 'Manual', lastUpdated: '08 May 2025', status: 'Published' },
  { id: '14', name: 'Network Outage Response', category: 'IT Systems', department: 'IT', type: 'SOP', lastUpdated: '05 May 2025', status: 'Published' },
  { id: '15', name: 'Solar Panel Maintenance', category: 'Electrical Systems', department: 'Engineering', type: 'Manual', lastUpdated: '02 May 2025', status: 'Published' },
  { id: '16', name: 'Waste Management Policy', category: 'Terminal Operations', department: 'Facilities', type: 'Policy', lastUpdated: '01 May 2025', status: 'Published' },
  { id: '17', name: 'First Aid Box Checklist', category: 'Safety & Fire', department: 'Safety', type: 'Checklist', lastUpdated: '28 Apr 2025', status: 'Published' },
  { id: '18', name: 'CCTV Monitoring Guidelines', category: 'Security', department: 'Operations', type: 'SOP', lastUpdated: '25 Apr 2025', status: 'Published' },
  { id: '19', name: 'VIP Lounge Protocol', category: 'Terminal Operations', department: 'Commercial', type: 'SOP', lastUpdated: '20 Apr 2025', status: 'Published' },
  { id: '20', name: 'Runway Friction Testing', category: 'Airfield Operations', department: 'Engineering', type: 'Report', lastUpdated: '15 Apr 2025', status: 'Published' },
];

export const DOC_CATEGORIES: string[] = [
  'Airfield Operations', 'Baggage Handling', 'Electrical Systems', 'HVAC Systems',
  'Safety & Fire', 'IT Systems', 'Terminal Operations', 'Security',
];

export const DOC_DEPARTMENTS: string[] = [
  'Engineering', 'Safety', 'Operations', 'IT', 'Facilities', 'Commercial',
];

export const DOC_TYPES: string[] = ['Manual', 'SOP', 'Checklist', 'Policy', 'Report'];

export const DOC_TYPE_COLORS: Record<string, string> = {
  Manual: 'bg-blue-100 text-blue-700',
  SOP: 'bg-green-100 text-green-700',
  Checklist: 'bg-purple-100 text-purple-700',
  Policy: 'bg-orange-100 text-orange-700',
  Report: 'bg-gray-100 text-gray-600',
};
