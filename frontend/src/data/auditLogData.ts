import { AuditLog } from '../types';

export const AUDIT_LOG: AuditLog[] = [
  { id: '1', timestamp: '2025-05-23 11:42:00', user: 'Ananya Nair', action: 'Uploaded Document', resource: 'Runway Lighting System – Maintenance Manual', ip: '10.0.1.45', status: 'Success' },
  { id: '2', timestamp: '2025-05-23 10:15:00', user: 'Arjun Nair', action: 'Updated SOP', resource: 'Electrical Lockout Tagout Procedure v4.7', ip: '10.0.1.72', status: 'Success' },
  { id: '3', timestamp: '2025-05-22 16:30:00', user: 'Deepa Menon', action: 'Deleted Document', resource: 'Old Fire Drill Report 2023', ip: '10.0.1.88', status: 'Success' },
  { id: '4', timestamp: '2025-05-22 14:10:00', user: 'Vikram Pillai', action: 'User Role Changed', resource: 'Riya Nambiar → engineer', ip: '10.0.1.12', status: 'Success' },
  { id: '5', timestamp: '2025-05-22 11:05:00', user: 'Meera Patel', action: 'Login', resource: 'CIAL Knowledge OS', ip: '10.0.2.33', status: 'Success' },
  { id: '6', timestamp: '2025-05-22 09:00:00', user: 'Unknown', action: 'Login Attempt', resource: 'CIAL Knowledge OS', ip: '192.168.5.201', status: 'Failed' },
  { id: '7', timestamp: '2025-05-21 17:20:00', user: 'Arjun Nair', action: 'Uploaded Document', resource: 'HVAC Preventive Maintenance Checklist', ip: '10.0.1.72', status: 'Success' },
  { id: '8', timestamp: '2025-05-21 15:45:00', user: 'Ananya Nair', action: 'Admin Settings Changed', resource: 'Document Ingestion – batch size updated', ip: '10.0.1.45', status: 'Success' },
  { id: '9', timestamp: '2025-05-21 12:30:00', user: 'Deepa Menon', action: 'Downloaded Document', resource: 'Emergency Evacuation Routes', ip: '10.0.1.88', status: 'Success' },
  { id: '10', timestamp: '2025-05-20 16:00:00', user: 'Vikram Pillai', action: 'Integration Configured', resource: 'Microsoft Entra ID', ip: '10.0.1.12', status: 'Success' },
  { id: '11', timestamp: '2025-05-20 14:22:00', user: 'Riya Nambiar', action: 'Login', resource: 'CIAL Knowledge OS', ip: '10.0.3.55', status: 'Success' },
  { id: '12', timestamp: '2025-05-20 10:10:00', user: 'Ananya Nair', action: 'Deleted Document', resource: 'Temp Draft – Runway Inspection', ip: '10.0.1.45', status: 'Success' },
  { id: '13', timestamp: '2025-05-19 09:45:00', user: 'Meera Patel', action: 'Uploaded Document', resource: 'VIP Lounge Protocol v2', ip: '10.0.2.33', status: 'Success' },
  { id: '14', timestamp: '2025-05-18 17:30:00', user: 'Unknown', action: 'Login Attempt', resource: 'CIAL Knowledge OS', ip: '203.x.x.10', status: 'Failed' },
  { id: '15', timestamp: '2025-05-18 11:00:00', user: 'Arjun Nair', action: 'SOP Status Changed', resource: 'Wildlife Hazard Management SOP → Under Review', ip: '10.0.1.72', status: 'Success' },
  { id: '16', timestamp: '2025-05-17 15:15:00', user: 'Deepa Menon', action: 'Login', resource: 'CIAL Knowledge OS', ip: '10.0.1.88', status: 'Success' },
  { id: '17', timestamp: '2025-05-17 13:40:00', user: 'Vikram Pillai', action: 'Uploaded Document', resource: 'IT Helpdesk Troubleshooting Guide', ip: '10.0.1.12', status: 'Success' },
  { id: '18', timestamp: '2025-05-16 10:20:00', user: 'Ananya Nair', action: 'User Added', resource: 'New user: Riya Nambiar', ip: '10.0.1.45', status: 'Success' },
  { id: '19', timestamp: '2025-05-15 09:00:00', user: 'System', action: 'Scheduled Backup', resource: 'Full database backup', ip: '10.0.0.1', status: 'Success' },
  { id: '20', timestamp: '2025-05-14 16:50:00', user: 'Meera Patel', action: 'Login', resource: 'CIAL Knowledge OS', ip: '10.0.2.33', status: 'Failed' },
];

export const MOCK_USERS = [
  { name: 'Ananya Nair', email: 'ananya.nair@cial.aero', role: 'admin', lastActive: '23 May 2025, 11:42' },
  { name: 'Arjun Nair', email: 'arjun.nair@cial.aero', role: 'engineer', lastActive: '23 May 2025, 10:15' },
  { name: 'Deepa Menon', email: 'deepa.menon@cial.aero', role: 'manager', lastActive: '22 May 2025, 16:30' },
  { name: 'Vikram Pillai', email: 'vikram.pillai@cial.aero', role: 'engineer', lastActive: '22 May 2025, 14:10' },
  { name: 'Meera Patel', email: 'meera.patel@cial.aero', role: 'viewer', lastActive: '22 May 2025, 11:05' },
  { name: 'Riya Nambiar', email: 'riya.nambiar@cial.aero', role: 'engineer', lastActive: '21 May 2025, 17:20' },
];
