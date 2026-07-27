import { AlertTriangle } from 'lucide-react';
import DashboardBlock from '@/components/common/DashboardBlock';
import { KNOWLEDGE_GAPS } from '@/data/knowledgeBaseData';

export default function KnowledgeGapsBlock() {
  return (
    <DashboardBlock title="Knowledge Gaps" viewAllLabel="Add Content" onViewAll={() => {}}>
      <div className="space-y-2">
        {KNOWLEDGE_GAPS.map((gap, i) => (
          <div
            key={gap.topic}
            className="flex items-center justify-between gap-2 px-3 py-2.5 rounded-lg bg-warning/10"
            data-testid={`knowledge-gap-${i}`}
          >
            <div className="flex items-center gap-2 min-w-0">
              <AlertTriangle size={13} className="text-warning flex-shrink-0" />
              <span className="text-sm text-foreground truncate">{gap.topic}</span>
            </div>
            <span className="text-xs text-warning font-semibold flex-shrink-0">{gap.count} queries</span>
          </div>
        ))}
      </div>
    </DashboardBlock>
  );
}
