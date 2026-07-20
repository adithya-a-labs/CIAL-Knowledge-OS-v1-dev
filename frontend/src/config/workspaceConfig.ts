import type { ComponentType } from 'react';
import type { WorkspacePreferences, WorkspaceWidgetId } from '@/data/workspace/workspaceTypes';

export const DEFAULT_WORKSPACE_PREFERENCES: WorkspacePreferences = {
  version: 1,
  defaultTab: 'files',
  defaultView: 'list',
  density: 'comfortable',
  rightRailVisible: true,
  rightRailCollapsed: false,
  visibleWidgets: ['storage_usage', 'pinned_items', 'recent_activity'],
  widgetOrder: ['storage_usage', 'pinned_items', 'recent_activity', 'indexing_status', 'recent_notes', 'recent_conversations'],
  defaultSort: 'modified_desc',
  pageSize: 25,
  recentItemLimit: 5,
};

export interface WorkspaceWidgetRegistration {
  id: WorkspaceWidgetId;
  label: string;
  minSize: 'compact' | 'standard';
  featureFlag?: string;
  permission?: string;
  component?: ComponentType<never>;
}

export const WORKSPACE_WIDGET_REGISTRY: Record<WorkspaceWidgetId, WorkspaceWidgetRegistration> = {
  storage_usage: { id: 'storage_usage', label: 'Storage', minSize: 'compact' },
  pinned_items: { id: 'pinned_items', label: 'Pinned', minSize: 'standard' },
  recent_activity: { id: 'recent_activity', label: 'Recent Activity', minSize: 'standard' },
  recent_notes: { id: 'recent_notes', label: 'My Notes', minSize: 'standard' },
  recent_conversations: { id: 'recent_conversations', label: 'Recent AI Conversations', minSize: 'standard' },
  indexing_status: { id: 'indexing_status', label: 'Indexing Status', minSize: 'compact' },
};

export function normalizeWorkspacePreferences(value?: Partial<WorkspacePreferences> | null): WorkspacePreferences {
  const merged = { ...DEFAULT_WORKSPACE_PREFERENCES, ...(value ?? {}) };
  const valid = new Set(Object.keys(WORKSPACE_WIDGET_REGISTRY));
  const visibleWidgets = merged.visibleWidgets.filter((id) => valid.has(id));
  const widgetOrder = [...new Set([...merged.widgetOrder.filter((id) => valid.has(id)), ...visibleWidgets])];
  return { ...merged, visibleWidgets, widgetOrder };
}
