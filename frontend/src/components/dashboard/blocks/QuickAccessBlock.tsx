import { useLocation } from 'wouter';
import { Plus, FileText, BookmarkCheck, Globe } from 'lucide-react';
import DashboardBlock from '@/components/common/DashboardBlock';
import { QUICK_ACTIONS } from '@/data/dashboardData';

const ICON_MAP: Record<string, React.ElementType> = {
  Plus,
  FileText,
  BookmarkCheck,
  Globe,
};

export default function QuickAccessBlock() {
  const [, setLocation] = useLocation();

  return (
    <DashboardBlock title="Quick Access">
      <div className="grid grid-cols-2 gap-2">
        {QUICK_ACTIONS.map(action => {
          const Icon = ICON_MAP[action.icon] ?? Plus;
          return (
            <button
              key={action.label}
              onClick={() => setLocation(action.path)}
              className={`flex flex-col items-center gap-2 p-3 rounded-xl ${action.colorClass} hover:opacity-80 transition-opacity`}
              data-testid={`quick-action-${action.label.toLowerCase().replace(/\s+/g, '-')}`}
            >
              <Icon size={18} />
              <span className="text-xs font-semibold text-center leading-tight">{action.label}</span>
            </button>
          );
        })}
      </div>
    </DashboardBlock>
  );
}
