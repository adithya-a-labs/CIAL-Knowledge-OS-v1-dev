import { useLocation } from 'wouter';
import { Search, TrendingUp } from 'lucide-react';
import DashboardBlock from '@/components/common/DashboardBlock';
import { POPULAR_SEARCHES } from '@/data/knowledgeBaseData';
import { createConversationHandoff } from '@/lib/conversationHandoff';

export default function PopularSearchesBlock() {
  const [, setLocation] = useLocation();

  return (
    <DashboardBlock title="Popular Searches" viewAllLabel="See All" onViewAll={() => setLocation('/knowledge')}>
      <div className="space-y-2">
        {POPULAR_SEARCHES.map((item, i) => (
          <button
            key={item.query}
            onClick={() => createConversationHandoff(setLocation, {
              title: item.query.slice(0, 72),
              origin: 'global_search',
              context_scope: 'all_accessible',
              selected_document_ids: [],
              question: item.query,
              autoSubmit: true,
            })}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-accent transition-colors group"
            data-testid={`popular-search-${i}`}
          >
            <span className="w-5 h-5 rounded-full bg-[#4a7c3f] text-white text-[10px] font-bold flex items-center justify-center flex-shrink-0">
              {i + 1}
            </span>
            <span className="flex-1 text-sm text-foreground text-left truncate group-hover:text-primary transition-colors">{item.query}</span>
            <span className="flex items-center gap-1 text-[11px] text-[#9ab88e] flex-shrink-0">
              <TrendingUp size={11} className="text-primary" />
              {item.count}
            </span>
          </button>
        ))}
      </div>
    </DashboardBlock>
  );
}
