import { Link } from 'wouter';
import { FileText, StickyNote, MessageSquare } from 'lucide-react';
import type { WorkspaceStatItem } from '@/data/workspace/workspaceTypes';

const ICON_MAP: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  FileText,
  StickyNote,
  MessageSquare,
};

const COLOR_MAP: Record<string, string> = {
  documents: 'bg-info/10 text-info',
  notes: 'bg-warning/10 text-warning',
  conversations: 'bg-accent text-primary',
};

interface WorkspaceStatCardProps {
  stat: WorkspaceStatItem;
}

export default function WorkspaceStatCard({ stat }: WorkspaceStatCardProps) {
  const Icon = ICON_MAP[stat.icon] ?? FileText;
  const colorCls = COLOR_MAP[stat.key] ?? 'bg-muted text-muted-foreground';

  return (
    <div
      className="fluid-card responsive-card flex min-w-0 flex-col gap-3 border border-border bg-card p-4 shadow-sm"
      data-testid={`workspace-stat-${stat.key}`}
    >
      <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${colorCls}`}>
        <Icon size={18} />
      </div>
      <div>
        <p className="safe-text text-xs font-medium text-muted-foreground">{stat.label}</p>
        <p className="text-2xl font-bold text-foreground leading-tight">{stat.count.toLocaleString()}</p>
        <p className="text-[11px] text-[#7a9a72]">{stat.unit}</p>
      </div>
      <Link
        href={stat.href}
        className="mt-auto flex items-center gap-1 text-xs font-medium text-primary hover:underline"
      >
        View all →
      </Link>
    </div>
  );
}
