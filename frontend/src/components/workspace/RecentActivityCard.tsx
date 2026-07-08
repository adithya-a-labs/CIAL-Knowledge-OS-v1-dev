import { Upload, StickyNote, MessageSquare, Bookmark, Trash2 } from 'lucide-react';
import type { WorkspaceActivityEntry, ActivityType } from '@/data/workspace/workspaceTypes';

const ACTIVITY_META: Record<ActivityType, {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  bg: string;
  iconCls: string;
}> = {
  upload: { icon: Upload, bg: 'bg-blue-50', iconCls: 'text-blue-500' },
  note: { icon: StickyNote, bg: 'bg-amber-50', iconCls: 'text-amber-500' },
  chat: { icon: MessageSquare, bg: 'bg-[#f0f7ed]', iconCls: 'text-[#4a7c3f]' },
  bookmark: { icon: Bookmark, bg: 'bg-purple-50', iconCls: 'text-purple-500' },
  delete: { icon: Trash2, bg: 'bg-red-50', iconCls: 'text-red-400' },
};

interface RecentActivityCardProps {
  activities: WorkspaceActivityEntry[];
  onViewAll?: () => void;
}

export default function RecentActivityCard({ activities, onViewAll }: RecentActivityCardProps) {
  return (
    <div className="bg-white rounded-xl border border-[#e2eedd] shadow-sm overflow-hidden" data-testid="recent-activity-card">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#f0f7ed]">
        <h3 className="text-sm font-semibold text-[#1a2e14]">Recent Activity</h3>
        <button
          onClick={onViewAll}
          className="text-xs text-[#4a7c3f] hover:underline font-medium"
          data-testid="button-activity-viewall"
        >
          View all activity →
        </button>
      </div>

      <div className="divide-y divide-[#f0f7ed]">
        {activities.map((entry) => {
          const { icon: Icon, bg, iconCls } = ACTIVITY_META[entry.type];
          return (
            <div key={entry.id} className="flex items-center gap-3 px-4 py-3 hover:bg-[#f8fdf6] transition-colors" data-testid={`activity-${entry.id}`}>
              <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${bg}`}>
                <Icon size={13} className={iconCls} />
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-[#1a2e14] leading-snug">{entry.description}</p>
              </div>
              <span className="text-[10px] text-[#7a9a72] flex-shrink-0">{entry.time}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
