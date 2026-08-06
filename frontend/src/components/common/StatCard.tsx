import { TrendingUp, TrendingDown, FileText, Lightbulb, ClipboardList, HelpCircle, AlertCircle, Search, CheckCircle, Star } from 'lucide-react';

const ICON_MAP: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  FileText, Lightbulb, ClipboardList, HelpCircle, AlertCircle, Search, CheckCircle, Star
};

interface StatCardProps {
  label: string;
  value: string | number;
  delta: string;
  trend: 'up' | 'down' | 'neutral';
  icon: string;
  iconBg?: string;
  viewAllLink?: string;
  onViewAll?: () => void;
}

export default function StatCard({ label, value, delta, trend, icon, iconBg, viewAllLink, onViewAll }: StatCardProps) {
  const IconComponent = ICON_MAP[icon] || FileText;

  return (
    <div
      className="fluid-card responsive-card min-w-0 border border-border bg-card p-4 shadow-sm"
      data-testid={`stat-card-${label.toLowerCase().replace(/\s+/g, '-')}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: iconBg || 'hsl(100 35% 93%)' }}
        >
          <IconComponent size={18} className="text-primary" />
        </div>
        {viewAllLink && (
          <button
            onClick={onViewAll}
            className="text-xs text-primary hover:underline font-medium"
            data-testid={`link-viewall-${label.toLowerCase().replace(/\s+/g, '-')}`}
          >
            View all →
          </button>
        )}
      </div>
      <div className="mt-3">
        <div className="safe-text text-[11px] font-medium uppercase tracking-wide text-muted-foreground" data-testid="stat-label">{label}</div>
        <div className="text-2xl font-bold text-foreground mt-0.5" data-testid="stat-value">{value}</div>
        <div className={`mt-1 flex items-center gap-1 text-xs ${trend === 'up' ? 'text-[#27ae60]' : trend === 'down' ? 'text-[#c0392b]' : 'text-muted-foreground'}`} data-testid="stat-delta">
          {trend === 'up' && <TrendingUp size={11} />}
          {trend === 'down' && <TrendingDown size={11} />}
          <span>{delta}</span>
        </div>
      </div>
    </div>
  );
}
