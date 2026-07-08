import { Megaphone, AlertTriangle, Info } from 'lucide-react';

export type AnnouncementSeverity = 'info' | 'warning' | 'critical';

export interface Announcement {
  id: string;
  title: string;
  body: string;
  severity: AnnouncementSeverity;
  date: string;
  author?: string;
}

interface AnnouncementCardProps {
  announcement: Announcement;
}

const SEVERITY_META: Record<AnnouncementSeverity, { icon: typeof Megaphone; bg: string; border: string; iconCls: string }> = {
  info: { icon: Megaphone, bg: 'bg-[#f0f7ed]', border: 'border-[#ddecd6]', iconCls: 'text-[#4a7c3f]' },
  warning: { icon: AlertTriangle, bg: 'bg-amber-50', border: 'border-amber-200', iconCls: 'text-amber-500' },
  critical: { icon: Info, bg: 'bg-red-50', border: 'border-red-200', iconCls: 'text-red-500' },
};

export default function AnnouncementCard({ announcement }: AnnouncementCardProps) {
  const { icon: Icon, bg, border, iconCls } = SEVERITY_META[announcement.severity];

  return (
    <div
      className={`flex gap-3 rounded-xl border p-4 ${bg} ${border}`}
      data-testid={`announcement-${announcement.id}`}
    >
      <Icon size={18} className={`mt-0.5 flex-shrink-0 ${iconCls}`} />
      <div className="min-w-0">
        <p className="text-sm font-semibold text-[#1a2e14] leading-tight">{announcement.title}</p>
        <p className="text-xs text-[#5a7a52] mt-0.5 leading-relaxed">{announcement.body}</p>
        <p className="text-[10px] text-[#7a9a72] mt-1">
          {announcement.date}{announcement.author ? ` · ${announcement.author}` : ''}
        </p>
      </div>
    </div>
  );
}
