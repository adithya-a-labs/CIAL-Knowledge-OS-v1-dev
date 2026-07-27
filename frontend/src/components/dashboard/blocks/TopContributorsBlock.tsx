import { useLocation } from 'wouter';
import { Trophy } from 'lucide-react';
import DashboardBlock from '@/components/common/DashboardBlock';
import { EXPERTS } from '@/data/expertData';

const RANK_COLOR = ['text-amber-500', 'text-muted-foreground', 'text-warning-foreground'];
const RANK_BG = ['bg-warning/10', 'bg-muted', 'bg-warning/10'];

export default function TopContributorsBlock() {
  const [, navigate] = useLocation();
  const sorted = [...EXPERTS].sort((a, b) => b.knowledgeScore - a.knowledgeScore).slice(0, 5);

  return (
    <DashboardBlock
      title="Top Contributors"
      viewAllLabel="View All"
      onViewAll={() => navigate('/experts')}
    >
      <div className="space-y-2">
        {sorted.map((expert, i) => (
          <div key={expert.id} className={`flex items-center gap-3 rounded-lg px-2 py-1.5 ${i < 3 ? RANK_BG[i] : ''}`} data-testid={`contributor-${expert.id}`}>
            <span className={`text-xs font-bold w-5 text-center flex-shrink-0 ${i < 3 ? RANK_COLOR[i] : 'text-[#7a9a72]'}`}>
              {i < 3 ? <Trophy size={12} className="inline" /> : `#${i + 1}`}
            </span>
            <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#4a7c3f] to-[#7ab648] flex items-center justify-center text-white text-[10px] font-bold flex-shrink-0">
              {expert.initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-foreground truncate">{expert.name}</p>
              <p className="text-[10px] text-muted-foreground truncate">{expert.department}</p>
            </div>
            <span className="text-xs font-bold text-primary">{expert.knowledgeScore}</span>
          </div>
        ))}
      </div>
    </DashboardBlock>
  );
}
