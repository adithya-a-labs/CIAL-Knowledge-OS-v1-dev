export interface Integration {
  name: string;
  status: 'Connected' | 'Disconnected';
  version: string;
  lastSync: string;
  color: string;
}

export const INTEGRATIONS: Integration[] = [
  { name: 'Microsoft Entra ID', status: 'Connected', version: 'v2.1', lastSync: '23 May 2025, 10:00 AM', color: 'text-success' },
  { name: 'SharePoint', status: 'Disconnected', version: 'v1.8', lastSync: 'Never', color: 'text-muted-foreground' },
  { name: 'CMMS (IBM Maximo)', status: 'Connected', version: 'v7.6.1', lastSync: '23 May 2025, 09:00 AM', color: 'text-success' },
  { name: 'SAP', status: 'Disconnected', version: 'v3.0', lastSync: 'Never', color: 'text-muted-foreground' },
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
  admin: 'bg-accent text-accent-foreground',
  engineer: 'bg-info/15 text-info-foreground',
  manager: 'bg-success/15 text-success-foreground',
  viewer: 'bg-muted text-muted-foreground',
};
