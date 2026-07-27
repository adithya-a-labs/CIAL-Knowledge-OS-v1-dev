import { Link } from 'wouter';
import { Star, FileText, MessageSquare } from 'lucide-react';
import DashboardBlock from '@/components/common/DashboardBlock';
import { EXPERTS } from '@/data/expertData';
import { useLocation } from 'wouter';

export default function ExpertSpotlightBlock() {
  const [, navigate] = useLocation();
  const top = EXPERTS.slice(0, 3);

  return (
    <DashboardBlock
      title="Expert Spotlight"
      viewAllLabel="View All"
      onViewAll={() => navigate('/experts')}
    >
      <div className="space-y-3">
        {top.map(expert => (
          <div key={expert.id} className="flex items-center gap-3" data-testid={`spotlight-${expert.id}`}>
            <div className="w-9 h-9 rounded-full bg-gradient-to-br from-[#4a7c3f] to-[#7ab648] flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
              {expert.initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-semibold text-foreground truncate">{expert.name}</p>
              <p className="text-[10px] text-muted-foreground truncate">{expert.expertiseTags[0]}</p>
            </div>
            <div className="flex flex-col items-end gap-0.5">
              <div className="flex items-center gap-0.5 text-amber-500">
                <Star size={10} className="fill-amber-400" />
                <span className="text-[10px] font-bold text-foreground">{expert.knowledgeScore}</span>
              </div>
              <div className="flex items-center gap-2 text-[9px] text-[#7a9a72]">
                <span className="flex items-center gap-0.5"><FileText size={9} />{expert.documentsContributed}</span>
                <span className="flex items-center gap-0.5"><MessageSquare size={9} />{expert.helpfulAnswers}</span>
              </div>
            </div>
          </div>
        ))}
        <Link href="/experts" className="block text-center text-xs text-primary hover:underline font-medium mt-1">
          Find more experts →
        </Link>
      </div>
    </DashboardBlock>
  );
}
