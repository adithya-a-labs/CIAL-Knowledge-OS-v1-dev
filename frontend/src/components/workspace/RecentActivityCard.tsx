import { Upload, StickyNote, MessageSquare, Bookmark, Trash2 } from 'lucide-react';
import type { WorkspaceActivityEntry, ActivityType } from '@/data/workspace/workspaceTypes';

const ACTIVITY_META: Record<ActivityType, {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  bg: string;
  iconCls: string;
}> = {
  upload: { icon: Upload, bg: 'bg-info/10', iconCls: 'text-blue-500' },
  note: { icon: StickyNote, bg: 'bg-warning/10', iconCls: 'text-amber-500' },
  chat: { icon: MessageSquare, bg: 'bg-accent', iconCls: 'text-primary' },
  bookmark: { icon: Bookmark, bg: 'bg-accent', iconCls: 'text-purple-500' },
  delete: { icon: Trash2, bg: 'bg-destructive/10', iconCls: 'text-red-400' },
};

interface RecentActivityCardProps {
  activities: WorkspaceActivityEntry[];
  onViewAll?: () => void;
}

export default function RecentActivityCard({ activities, onViewAll }: RecentActivityCardProps) {
  return (
    <div className="bg-card rounded-xl border border-border shadow-sm overflow-hidden" data-testid="recent-activity-card">
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <h3 className="text-sm font-semibold text-foreground">Recent Activity</h3>
        <button
          onClick={onViewAll}
          className="text-xs text-primary hover:underline font-medium"
          data-testid="button-activity-viewall"
        >
          View all activity →
        </button>
      </div>

      <div className="divide-y divide-border">
        {activities.map((entry) => {
          const { icon: Icon, bg, iconCls } = ACTIVITY_META[entry.type];
          return (
            <div key={entry.id} className="flex items-center gap-3 px-4 py-3 hover:bg-muted transition-colors" data-testid={`activity-${entry.id}`}>
              <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${bg}`}>
                <Icon size={13} className={iconCls} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-foreground leading-snug">{entry.description}</p>
              </div>
              <span className="text-[10px] text-[#7a9a72] flex-shrink-0">{entry.time}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
