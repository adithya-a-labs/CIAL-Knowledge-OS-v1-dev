export type KGNodeType = 'hub' | 'department' | 'doc_type' | 'expert' | 'policy' | 'topic';

export interface KGNode {
  id: string;
  label: string;
  type: KGNodeType;
  x: number;
  y: number;
  count?: number;
  color: string;
  description: string;
}

export interface KGEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
}

const CX = 400;
const CY = 270;
const R1 = 120;
const R2 = 235;

function pos(cx: number, cy: number, r: number, deg: number) {
  const rad = (deg * Math.PI) / 180;
  return { x: Math.round(cx + r * Math.cos(rad)), y: Math.round(cy + r * Math.sin(rad)) };
}

export const KG_NODES: KGNode[] = [
  // Hub
  { id: 'hub', label: 'CIAL Knowledge OS', type: 'hub', x: CX, y: CY, color: '#2d4f22', description: 'Central knowledge repository for Cochin International Airport Limited.' },

  // Inner ring — Departments (6 nodes at 60° intervals, starting from -90°)
  { id: 'dept-eng', label: 'Engineering', type: 'department', ...pos(CX, CY, R1, -90), color: '#4a7c3f', count: 744, description: '744 documents · 38 SOPs · 6 active experts' },
  { id: 'dept-saf', label: 'Safety', type: 'department', ...pos(CX, CY, R1, -30), color: '#4a7c3f', count: 512, description: '512 documents · 62 SOPs · 2 active experts' },
  { id: 'dept-ops', label: 'Operations', type: 'department', ...pos(CX, CY, R1, 30), color: '#4a7c3f', count: 480, description: '480 documents · 45 SOPs · 3 active experts' },
  { id: 'dept-it', label: 'IT', type: 'department', ...pos(CX, CY, R1, 90), color: '#4a7c3f', count: 198, description: '198 documents · 22 SOPs · 1 active expert' },
  { id: 'dept-hr', label: 'HR', type: 'department', ...pos(CX, CY, R1, 150), color: '#4a7c3f', count: 134, description: '134 documents · 14 SOPs' },
  { id: 'dept-fin', label: 'Finance', type: 'department', ...pos(CX, CY, R1, 210), color: '#4a7c3f', count: 88, description: '88 documents · 8 SOPs' },

  // Outer ring — Knowledge types (6 nodes at 60° intervals, offset by 30°)
  { id: 'type-sop', label: 'SOPs', type: 'doc_type', ...pos(CX, CY, R2, -90), color: '#7ab648', count: 326, description: '326 active SOPs across all departments.' },
  { id: 'type-manual', label: 'Manuals', type: 'doc_type', ...pos(CX, CY, R2, -30), color: '#7ab648', count: 412, description: '412 technical manuals, equipment guides, and reference books.' },
  { id: 'type-policy', label: 'Policies', type: 'policy', ...pos(CX, CY, R2, 30), color: '#e8820c', count: 98, description: '98 regulatory policies and compliance frameworks.' },
  { id: 'type-faq', label: 'FAQs', type: 'doc_type', ...pos(CX, CY, R2, 90), color: '#7ab648', count: 187, description: '187 frequently asked questions and expert answers.' },
  { id: 'type-learn', label: 'Learning', type: 'topic', ...pos(CX, CY, R2, 150), color: '#3b82f6', count: 38, description: '38 training courses and 3 learning paths.' },
  { id: 'type-expert', label: 'Experts', type: 'expert', ...pos(CX, CY, R2, 210), color: '#9c27b0', count: 6, description: '6 subject matter experts contributing knowledge.' },
];

export const KG_EDGES: KGEdge[] = [
  // Hub to departments
  { id: 'e-h-eng', source: 'hub', target: 'dept-eng' },
  { id: 'e-h-saf', source: 'hub', target: 'dept-saf' },
  { id: 'e-h-ops', source: 'hub', target: 'dept-ops' },
  { id: 'e-h-it', source: 'hub', target: 'dept-it' },
  { id: 'e-h-hr', source: 'hub', target: 'dept-hr' },
  { id: 'e-h-fin', source: 'hub', target: 'dept-fin' },

  // Departments to knowledge types
  { id: 'e-eng-sop', source: 'dept-eng', target: 'type-sop', label: '38 SOPs' },
  { id: 'e-eng-man', source: 'dept-eng', target: 'type-manual', label: '44 Manuals' },
  { id: 'e-saf-pol', source: 'dept-saf', target: 'type-policy', label: '28 Policies' },
  { id: 'e-saf-sop', source: 'dept-saf', target: 'type-sop', label: '62 SOPs' },
  { id: 'e-ops-sop', source: 'dept-ops', target: 'type-sop', label: '45 SOPs' },
  { id: 'e-ops-faq', source: 'dept-ops', target: 'type-faq', label: '52 FAQs' },
  { id: 'e-it-pol', source: 'dept-it', target: 'type-policy', label: '12 Policies' },
  { id: 'e-eng-exp', source: 'dept-eng', target: 'type-expert', label: '3 Experts' },
  { id: 'e-saf-exp', source: 'dept-saf', target: 'type-expert', label: '2 Experts' },
  { id: 'e-eng-learn', source: 'dept-eng', target: 'type-learn', label: '8 Courses' },
  { id: 'e-saf-learn', source: 'dept-saf', target: 'type-learn', label: '6 Courses' },
  { id: 'e-ops-learn', source: 'dept-ops', target: 'type-learn', label: '5 Courses' },
];

export const KG_NODE_TYPE_META: Record<KGNodeType, { label: string; color: string }> = {
  hub: { label: 'Hub', color: '#2d4f22' },
  department: { label: 'Department', color: '#4a7c3f' },
  doc_type: { label: 'Document Type', color: '#7ab648' },
  expert: { label: 'Expert', color: '#9c27b0' },
  policy: { label: 'Policy', color: '#e8820c' },
  topic: { label: 'Learning', color: '#3b82f6' },
};
