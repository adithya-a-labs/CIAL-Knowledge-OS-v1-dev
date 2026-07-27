import { Bell } from 'lucide-react';
import DashboardBlock from '@/components/common/DashboardBlock';
import { ANNOUNCEMENTS } from '@/data/knowledgeBaseData';

export default function AnnouncementsBlock() {
  return (
    <DashboardBlock title="Announcements" viewAllLabel="See All" onViewAll={() => {}}>
      <div className="space-y-3">
        {ANNOUNCEMENTS.map((a: { id: string; title: string; body: string; date?: string; priority?: string }) => (
          <div
            key={a.id}
            className="flex gap-3 p-3 rounded-xl bg-muted border border-border"
            data-testid={`announcement-${a.id}`}
          >
            <div className="w-7 h-7 rounded-full bg-accent flex items-center justify-center flex-shrink-0 mt-0.5">
              <Bell size={13} className="text-primary" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">{a.title}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{a.body}</p>
              {a.date && <p className="text-[10px] text-[#9ab88e] mt-1">{a.date}</p>}
            </div>
          </div>
        ))}
      </div>
    </DashboardBlock>
  );
}
