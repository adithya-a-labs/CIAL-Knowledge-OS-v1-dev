import { Link } from 'wouter';
import { FileText, StickyNote, FolderOpen, MessageSquare } from 'lucide-react';
import type { WorkspaceStatItem } from '@/data/workspace/workspaceTypes';

const ICON_MAP: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  FileText,
  StickyNote,
  FolderOpen,
  MessageSquare,
};

const COLOR_MAP: Record<string, string> = {
  documents: 'bg-blue-50 text-blue-600',
  notes: 'bg-amber-50 text-amber-600',
  collections: 'bg-purple-50 text-purple-600',
  conversations: 'bg-[#f0f7ed] text-[#4a7c3f]',
};

interface WorkspaceStatCardProps {
  stat: WorkspaceStatItem;
}

export default function WorkspaceStatCard({ stat }: WorkspaceStatCardProps) {
  const Icon = ICON_MAP[stat.icon] ?? FileText;
  const colorCls = COLOR_MAP[stat.key] ?? 'bg-gray-50 text-gray-500';

  return (
    <div
      className="fluid-card responsive-card flex min-w-0 flex-col gap-3 border border-[#e2eedd] bg-white p-4 shadow-sm hover:border-[#cfe4c8] hover:shadow-md"
      data-testid={`workspace-stat-${stat.key}`}
    >
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${colorCls}`}>
        <Icon size={18} />
      </div>
      <div>
        <p className="safe-text text-xs font-medium text-[#5a7a52]">{stat.label}</p>
        <p className="text-2xl font-bold text-[#1a2e14] leading-tight">{stat.count.toLocaleString()}</p>
        <p className="text-[11px] text-[#7a9a72]">{stat.unit}</p>
      </div>
      <Link
        href={stat.href}
        className="mt-auto flex items-center gap-1 text-xs font-medium text-[#4a7c3f] hover:underline"
      >
        View all →
      </Link>
    </div>
  );
}
