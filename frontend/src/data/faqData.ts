import { FAQ } from '../types';

export const FAQS: FAQ[] = [
  { id: '1', question: 'How to reset baggage conveyor motor fault?', answer: 'To reset the baggage conveyor motor fault: 1) Stop the conveyor using the emergency stop button. 2) Check the motor fault indicator panel. 3) Clear any jammed items. 4) Reset the fault via the control panel (press FAULT RESET). 5) Perform a test run at low speed. 6) If fault persists, contact Engineering.', category: 'Baggage Handling', helpfulCount: 124, lastUpdated: '10 May 2025' },
  { id: '2', question: 'What to do if fire alarm keeps triggering in T3?', answer: 'Persistent false alarms in T3 may be caused by: 1) Dust accumulation in smoke detectors. 2) Steam from nearby kitchens. 3) Faulty detector head. Steps: Check the alarm panel for zone location. Inspect detectors visually. Notify Fire Safety team. Log the incident in CMMS.', category: 'Safety & Fire', helpfulCount: 98, lastUpdated: '08 May 2025' },
  { id: '3', question: 'How to book preventive maintenance in CMMS?', answer: 'Log in to CMMS portal at intranet/cmms. Navigate to Work Orders > Create New. Select Work Order Type = Preventive Maintenance. Fill in Asset ID, Department, Schedule Date, and Assignee. Submit for approval. You will receive a confirmation email.', category: 'IT Systems', helpfulCount: 87, lastUpdated: '05 May 2025' },
  { id: '4', question: 'How to report airfield lighting at airside?', answer: 'Report airfield lighting faults by: 1) Noting the light position and type. 2) Calling ATC on extension 2200. 3) Logging the fault in the Airfield Lighting register (Form AL-05). 4) Engineering will respond within 2 hours during day, 30 minutes at night.', category: 'Airfield Operations', helpfulCount: 76, lastUpdated: '02 May 2025' },
  { id: '5', question: 'Can I find emergency contact numbers?', answer: 'Emergency contacts are available in: 1) The CIAL Emergency Directory (intranet/emergency). 2) Department notice boards. 3) This Knowledge Base under Safety > Emergency Contacts. Key numbers: Security Control – 100, Fire Station – 101, Medical – 102, Engineering Duty Officer – 2500.', category: 'Safety & Fire', helpfulCount: 65, lastUpdated: '01 May 2025' },
  { id: '6', question: 'What is the procedure for HVAC not cooling in T2?', answer: 'If HVAC is not cooling in T2: 1) Check thermostat settings on BMS. 2) Verify that chiller units are running. 3) Check for tripped breakers in the HVAC panel. 4) Inspect air filter for blockage. 5) Raise a work order in CMMS with priority HIGH. 6) Contact Engineering on ext 2400.', category: 'HVAC Systems', helpfulCount: 54, lastUpdated: '28 Apr 2025' },
  { id: '7', question: 'How to escalate an unresolved IT ticket?', answer: 'To escalate: 1) Log in to IT Helpdesk portal. 2) Open your existing ticket. 3) Click "Escalate" and provide reason. 4) Select escalation level (L2 or L3). 5) IT Manager will review within 4 hours. For urgent escalations, call IT Helpdesk directly on ext 1100.', category: 'IT Systems', helpfulCount: 43, lastUpdated: '25 Apr 2025' },
  { id: '8', question: 'What documents are needed for asset handover?', answer: 'Asset handover requires: 1) Asset Handover Form (HO-01). 2) Current asset condition report. 3) Maintenance history printout from CMMS. 4) Original OEM manuals. 5) Warranty cards (if applicable). Submit to Assets Management team at least 5 working days before handover date.', category: 'Airfield Operations', helpfulCount: 38, lastUpdated: '20 Apr 2025' },
];

export const FAQ_CATEGORIES: string[] = [
  'Airfield Operations', 'Baggage Handling', 'HVAC Systems', 'Safety & Fire', 'IT Systems', 'Emergency Procedures',
];

export const CHAT_HISTORY: { id: string; question: string; time: string }[] = [
  { id: '1', question: 'Runway edge light not working', time: '11:24 AM' },
  { id: '2', question: 'Baggage conveyor motor fault', time: '10:53 AM' },
  { id: '3', question: 'Fire alarm triggering', time: 'Yesterday' },
  { id: '4', question: 'How to reset FOD display?', time: 'Yesterday' },
  { id: '5', question: 'HVAC not cooling in T2', time: '3 days ago' },
];

export const INITIAL_CHAT: { id: string; role: 'user' | 'assistant'; content: string; timestamp: string; sources?: { documentName: string; department: string; pageRef: string }[] }[] = [
  {
    id: 'init-user-1',
    role: 'user',
    content: 'What is the procedure for runway edge light not working?',
    timestamp: '11:24 AM'
  },
  {
    id: 'init-ai-1',
    role: 'assistant',
    content: "If a runway edge light is not working, follow the procedure below:\n\n1. Verify the affected light on AGL monitoring system.\n2. Check the isolation transformer for the corresponding circuit.\n3. Inspect the series circuit for continuity.\n4. Replace the lamp if it is fused.\n5. Log the fault in CMMS and raise a work order.\n6. Refer: Runway Lighting System – Maintenance Manual (Page 45)",
    timestamp: '11:24 AM',
    sources: [
      {
        documentName: 'Runway Lighting System – Maintenance Manual',
        department: 'Engineering Department',
        pageRef: 'Page 45'
      }
    ]
  }
];

export const MOCK_AI_RESPONSES: { content: string; sources: { documentName: string; department: string; pageRef: string }[] }[] = [
  {
    content: "Here are the steps to resolve this issue:\n\n1. Check the system logs for error codes.\n2. Verify the power supply and connections.\n3. Perform a system restart following the standard procedure.\n4. If the issue persists, escalate to the Engineering team.\n5. Log all actions in CMMS for audit purposes.",
    sources: [{ documentName: 'Engineering Operations Manual', department: 'Engineering Department', pageRef: 'Page 23' }]
  },
  {
    content: "According to CIAL SOPs, the procedure involves:\n\n1. Immediately notify the Safety team via ext. 101.\n2. Isolate the affected area per emergency protocol.\n3. Document the incident in the Safety Management System.\n4. Follow up with a full incident report within 24 hours.",
    sources: [{ documentName: 'Safety & Emergency Procedures', department: 'Safety Department', pageRef: 'Page 12' }]
  },
];
