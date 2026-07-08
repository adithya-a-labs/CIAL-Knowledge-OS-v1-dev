export interface Integration {
  name: string;
  status: 'Connected' | 'Disconnected';
  version: string;
  lastSync: string;
  color: string;
}

export const INTEGRATIONS: Integration[] = [
  { name: 'Microsoft Entra ID', status: 'Connected', version: 'v2.1', lastSync: '23 May 2025, 10:00 AM', color: 'text-green-600' },
  { name: 'SharePoint', status: 'Disconnected', version: 'v1.8', lastSync: 'Never', color: 'text-gray-400' },
  { name: 'CMMS (IBM Maximo)', status: 'Connected', version: 'v7.6.1', lastSync: '23 May 2025, 09:00 AM', color: 'text-green-600' },
  { name: 'SAP', status: 'Disconnected', version: 'v3.0', lastSync: 'Never', color: 'text-gray-400' },
];

export const THEME_CONFIG_ITEMS = [
  { label: 'Primary Color', value: '#4a7c3f', type: 'swatch' as const },
  { label: 'Font Family', value: 'Inter / Segoe UI', type: 'font' as const },
  { label: 'Logo', value: '/cial-logo.png', type: 'logo' as const },
];

export const INGESTION_SETTINGS = [
  { label: 'Batch Size', value: '50 documents', type: 'text' as const },
  { label: 'Auto-Index', value: 'Enabled', type: 'toggle' as const },
  { label: 'Schedule', value: 'Daily at 02:00 AM', type: 'text' as const },
  { label: 'Supported Formats', value: 'PDF, DOCX, XLSX, PPT', type: 'text' as const },
];

export const ROLE_COLORS: Record<string, string> = {
  admin: 'bg-purple-100 text-purple-700',
  engineer: 'bg-blue-100 text-blue-700',
  manager: 'bg-green-100 text-green-700',
  viewer: 'bg-gray-100 text-gray-600',
};
