import { useLocation } from 'wouter';
import { MessageSquare, Clock, ArrowRight } from 'lucide-react';
import DashboardBlock from '@/components/common/DashboardBlock';
import { useQuery } from '@tanstack/react-query';
import { listChatSessions } from '@/api/client';
import { useAuth } from '@/auth/AuthContext';
import { assistantConversationPath, ASSISTANT_FRESH_PATH } from '@/lib/assistantNavigation';

export default function AIConversationsBlock() {
  const [, setLocation] = useLocation();
  const { user } = useAuth();
  const { data } = useQuery({ queryKey: ['chat-sessions', user?.id], queryFn: () => listChatSessions(), enabled: Boolean(user), retry: false });
  const conversations = data?.sessions ?? [];

  return (
    <DashboardBlock
      title="Recent AI Conversations"
      viewAllLabel="Open Assistant"
      onViewAll={() => setLocation(ASSISTANT_FRESH_PATH)}
    >
      <div className="space-y-2">
        {conversations.map(conv => (
          <button
            key={conv.id}
            onClick={() => setLocation(assistantConversationPath(conv.id))}
            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl bg-[#f8fdf6] border border-[#e2eedd] hover:border-[#4a7c3f] transition-colors group text-left"
            data-testid={`conv-item-${conv.id}`}
          >
            <div className="w-7 h-7 rounded-full bg-[#e0f0d8] flex items-center justify-center flex-shrink-0">
              <MessageSquare size={13} className="text-[#4a7c3f]" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-[#1a2e14] truncate group-hover:text-[#4a7c3f] transition-colors">{conv.title}</p>
              <p className="flex items-center gap-1 text-[11px] text-[#9ab88e] mt-0.5">
                <Clock size={10} /> {new Date(conv.updated_at).toLocaleDateString()}
              </p>
            </div>
            <ArrowRight size={14} className="text-[#9ab88e] flex-shrink-0 group-hover:text-[#4a7c3f] transition-colors" />
          </button>
        ))}
        {conversations.length === 0 && <p className="px-4 py-6 text-center text-sm text-slate-500">No conversations yet.</p>}
      </div>
    </DashboardBlock>
  );
}
