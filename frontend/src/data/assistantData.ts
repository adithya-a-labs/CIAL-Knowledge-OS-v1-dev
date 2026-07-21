import type {
  AssistantMessageMetadata,
  ChatSource,
  ContextDocument,
  ResponseLength,
  SearchScope,
} from '@/types/assistant';

export const DEFAULT_SEARCH_SCOPE: SearchScope = 'hybrid';
export const DEFAULT_RESPONSE_LENGTH: ResponseLength = 'detailed';

export const SEARCH_SCOPE_LABELS: Record<SearchScope, string> = {
  enterprise: 'Enterprise Only',
  workspace: 'My Workspace Only',
  hybrid: 'Hybrid',
  current_upload: 'Current Upload Only',
};

export const RESPONSE_LENGTH_LABELS: Record<ResponseLength, string> = {
  quick: 'Quick',
  standard: 'Standard',
  detailed: 'Detailed',
  operational: 'Operational',
};

export const CONTEXT_DOCUMENTS: ContextDocument[] = [
  {
    id: 'enterprise-airfield-lighting',
    title: 'Airfield Lighting Manual',
    sourceType: 'enterprise',
    groupLabel: 'Enterprise Documents',
    department: 'Airfield Engineering',
  },
  {
    id: 'enterprise-electrical-sop',
    title: 'Electrical Maintenance SOP',
    sourceType: 'enterprise',
    groupLabel: 'Enterprise Documents',
    department: 'Engineering',
  },
  {
    id: 'enterprise-safety-operations',
    title: 'Safety Operations Manual',
    sourceType: 'enterprise',
    groupLabel: 'Enterprise Documents',
    department: 'Safety',
  },
  {
    id: 'enterprise-hvac-maintenance',
    title: 'HVAC Maintenance Guide',
    sourceType: 'enterprise',
    groupLabel: 'Enterprise Documents',
    department: 'Facilities',
  },
  {
    id: 'workspace-transformer-manual',
    title: 'Vendor Transformer Manual',
    sourceType: 'workspace',
    groupLabel: 'My Workspace',
    department: 'Personal Workspace',
  },
  {
    id: 'workspace-inspection-notes',
    title: 'Personal Inspection Notes',
    sourceType: 'workspace',
    groupLabel: 'My Workspace',
    department: 'Personal Workspace',
  },
  {
    id: 'workspace-contractor-checklist',
    title: 'Contractor Checklist',
    sourceType: 'workspace',
    groupLabel: 'My Workspace',
    department: 'Personal Workspace',
  },
  {
    id: 'upload-incident-report',
    title: 'Uploaded Incident Report.pdf',
    sourceType: 'upload',
    groupLabel: 'Current Uploads',
    department: 'Uploaded Files',
  },
  {
    id: 'upload-vendor-specs',
    title: 'Vendor Specs.pdf',
    sourceType: 'upload',
    groupLabel: 'Current Uploads',
    department: 'Uploaded Files',
  },
];

export const MOCK_CHAT_SOURCES: ChatSource[] = [
  {
    id: 'source-1',
    citationIndex: 1,
    documentId: 'enterprise-airfield-lighting',
    documentTitle: 'Airfield Lighting Manual',
    sourceType: 'enterprise',
    department: 'Airfield Engineering',
    pageNumber: 45,
    chunkId: 'agl-runway-edge-maintenance',
    score: 0.94,
    reason: 'Defines the first-response checks for runway edge light outages.',
    excerpt:
      'Verify the affected fitting on the AGL monitoring panel, isolate the circuit, inspect the transformer, and record corrective action in CMMS.',
  },
  {
    id: 'source-2',
    citationIndex: 2,
    documentId: 'enterprise-electrical-sop',
    documentTitle: 'Electrical Maintenance SOP',
    sourceType: 'enterprise',
    department: 'Engineering',
    pageNumber: 18,
    chunkId: 'electrical-isolation-series-circuit',
    score: 0.89,
    reason: 'Supports safe electrical isolation before field maintenance.',
    excerpt:
      'Before handling airfield electrical assets, confirm permit status, isolate supply, test for absence of voltage, and place lockout tags.',
  },
  {
    id: 'source-3',
    citationIndex: 3,
    documentId: 'upload-vendor-specs',
    documentTitle: 'Vendor Specs.pdf',
    sourceType: 'upload',
    department: 'Current Uploads',
    pageNumber: 7,
    chunkId: 'isolation-transformer-symptoms',
    score: 0.83,
    reason: 'Adds vendor-specific transformer fault symptoms and checks.',
    excerpt:
      'Common transformer symptoms include intermittent lamp operation, visible casing damage, insulation leakage, and abnormal continuity readings.',
  },
];

export const INITIAL_ASSISTANT_MESSAGES = [
  {
    id: 'init-user-1',
    role: 'user' as const,
    content: 'What is the procedure for runway edge light not working?',
    timestamp: '11:24 AM',
  },
  {
    id: 'init-ai-1',
    role: 'assistant' as const,
    content:
      'If a runway edge light is not working, first confirm the affected fitting in the AGL monitoring system [1]. Isolate the relevant series circuit before field checks [2]. Inspect the isolation transformer and lamp assembly, then record the action in CMMS with the circuit and fitting ID [3].',
    timestamp: '11:24 AM',
    sources: MOCK_CHAT_SOURCES,
    metadata: {
      searchScope: 'hybrid',
      activeProfile: 'detailed',
      documentsSearched: 5,
      chunksRetrieved: 18,
      sourcesUsed: 3,
      confidence: 91,
      generationTimeSeconds: 2.4,
    } satisfies AssistantMessageMetadata,
    relatedQuestions: [
      'How do I troubleshoot runway edge lights?',
      'What is the maintenance checklist for isolation transformers?',
      'Compare this with the electrical SOP.',
      'Generate an operational checklist.',
    ],
  },
];

export const MOCK_AI_RESPONSES = [
  {
    content:
      'Start by validating the asset, circuit, and fault indication in the AGL system [1]. For field work, isolate and lock out the electrical circuit before opening the fixture or transformer pit [2]. If the lamp tests good, inspect the isolation transformer for damage, leakage, or abnormal continuity readings [3]. Close by updating CMMS with the observed fault, action taken, and whether a follow-up work order is required.',
    relatedQuestions: [
      'Generate an operational checklist.',
      'What safety steps are mandatory before isolation?',
      'Compare transformer symptoms with recent inspection notes.',
      'Create a shift handover summary.',
    ],
  },
  {
    content:
      'For an operational response, treat the issue as an airfield asset fault until proven otherwise [1]. Confirm safe isolation, assign a qualified electrical technician, and use the SOP lockout sequence before removing covers [2]. Use vendor transformer checks when the lamp or connector appears serviceable but the circuit still fails [3].',
    relatedQuestions: [
      'What evidence should be attached to the CMMS ticket?',
      'How quickly should Engineering respond at night?',
      'Create a technician checklist.',
      'Explain this in simpler terms.',
    ],
  },
];

export const RETRIEVAL_STAGES = [
  'Understanding question',
  'Expanding query',
  'Searching selected scope',
  'Retrieving documents',
  'Reranking evidence',
  'Generating grounded answer',
  'Preparing citations',
];

export const HISTORY_GROUPS = [
  {
    label: 'Today',
    items: [
      { id: '1', title: 'Runway edge light not working', subtitle: '3 sources used', active: true },
      { id: '2', title: 'Baggage conveyor motor fault', subtitle: '2 sources used', active: false },
    ],
  },
  {
    label: 'Yesterday',
    items: [
      { id: '3', title: 'Fire alarm triggering in T3', subtitle: '4 messages', active: false },
      { id: '4', title: 'How to reset FOD display?', subtitle: '1 source used', active: false },
    ],
  },
  {
    label: 'Last Week',
    items: [
      { id: '5', title: 'HVAC not cooling in T2', subtitle: '5 messages', active: false },
      { id: '6', title: 'Contractor access checklist', subtitle: 'Workspace context', active: false },
    ],
  },
];
