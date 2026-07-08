import { useState } from 'react';
import { Lock } from 'lucide-react';
import PersonalStorageCard from '@/components/workspace/PersonalStorageCard';
import WorkspaceStatCard from '@/components/workspace/WorkspaceStatCard';
import RecentUploadsTable from '@/components/workspace/RecentUploadsTable';
import RecentAIChats from '@/components/workspace/RecentAIChats';
import { CollectionCard, NewCollectionCard } from '@/components/workspace/CollectionCard';
import AISearchModeSelector from '@/components/workspace/AISearchModeSelector';
import StorageBreakdownChart from '@/components/workspace/StorageBreakdownChart';
import RecentActivityCard from '@/components/workspace/RecentActivityCard';
import WorkspaceUploadButton from '@/components/workspace/WorkspaceUploadButton';
import PrivacyBadge from '@/components/workspace/PrivacyBadge';
import {
  WORKSPACE_STATS,
  MY_DOCUMENTS,
  MY_CONVERSATIONS,
  MY_COLLECTIONS,
  STORAGE_BREAKDOWN,
  RECENT_ACTIVITY,
  CURRENT_WORKSPACE_USER_ID,
} from '@/data/workspace/workspaceData';
import type { AISearchMode } from '@/data/workspace/workspaceTypes';
import { getVisibleDocuments } from '@/data/workspace/workspacePermissions';

const MODE_LABEL: Record<AISearchMode, string> = {
  enterprise: 'Enterprise Mode',
  workspace: 'Workspace Mode',
  hybrid: 'Hybrid Mode',
};

export default function WorkspacePage() {
  const [aiMode, setAiMode] = useState<AISearchMode>('hybrid');
  const [showUploadHint, setShowUploadHint] = useState(false);

  const currentUser = { id: CURRENT_WORKSPACE_USER_ID, role: 'engineer' };
  const visibleDocs = getVisibleDocuments(currentUser, MY_DOCUMENTS);
  const visibleConvos = MY_CONVERSATIONS.filter(c => c.ownerId === currentUser.id);

  return (
    <div className="fluid-section min-h-full overflow-hidden rounded-xl bg-[#f8fdf6]">
      {/* Page Header */}
      <div className="border-b border-[#e2eedd] bg-white px-4 py-4 sm:px-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="safe-text text-xl font-bold text-[#1a2e14] sm:text-2xl">My Workspace</h1>
              <Lock size={16} className="text-[#4a7c3f]" />
            </div>
            <p className="safe-text mt-1 text-sm text-[#5a7a52]">
              Your personal knowledge space. Private. Secure. Only visible to you.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <PrivacyBadge size="md" />
            <WorkspaceUploadButton onClick={() => setShowUploadHint(true)} />
          </div>
        </div>
        {showUploadHint && (
          <div className="mt-3 px-3 py-2 rounded-lg bg-[#f0f7ed] border border-[#ddecd6] text-xs text-[#4a7c3f] flex items-center justify-between">
            <span>Upload dialog would open here in a connected app.</span>
            <button onClick={() => setShowUploadHint(false)} className="ml-4 text-[#4a7c3f] hover:text-[#2d4f22] font-bold">✕</button>
          </div>
        )}
      </div>

      <div className="p-4 sm:p-6">
        {/* 3-column desktop layout */}
        <div className="flex flex-col gap-5 xl:flex-row xl:gap-6">

          {/* ── Main content ── */}
          <div className="flex-1 min-w-0 space-y-5">

            {/* Storage Card */}
            <PersonalStorageCard />

            {/* Stat Cards */}
            <div className="fluid-grid-sm">
              {WORKSPACE_STATS.map((stat) => (
                <WorkspaceStatCard key={stat.key} stat={stat} />
              ))}
            </div>

            {/* Recent Uploads + Recent AI Chats — side by side on lg */}
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <RecentUploadsTable
                documents={visibleDocs}
                onViewAll={() => {}}
              />
              <RecentAIChats
                conversations={visibleConvos}
                onViewAll={() => {}}
                mode={MODE_LABEL[aiMode]}
              />
            </div>

            {/* Collections */}
            <div className="responsive-card overflow-hidden border border-[#e2eedd] bg-white shadow-sm" data-testid="collections-section">
              <div className="flex items-center justify-between gap-3 border-b border-[#f0f7ed] px-4 py-3">
                <h3 className="text-sm font-semibold text-[#1a2e14]">My Collections</h3>
                <button className="text-xs text-[#4a7c3f] hover:underline font-medium">View all</button>
              </div>
              <div className="p-4">
                <div className="fluid-grid-sm">
                  {MY_COLLECTIONS.map((col) => (
                    <CollectionCard key={col.id} collection={col} />
                  ))}
                  <NewCollectionCard />
                </div>
              </div>
            </div>
          </div>

          {/* ── Right Panel ── */}
          <div className="grid gap-4 xl:w-72 xl:flex-shrink-0 2xl:w-80">
            <AISearchModeSelector value={aiMode} onChange={setAiMode} />
            <StorageBreakdownChart data={STORAGE_BREAKDOWN} />
            <RecentActivityCard activities={RECENT_ACTIVITY} />
          </div>
        </div>
      </div>
    </div>
  );
}
