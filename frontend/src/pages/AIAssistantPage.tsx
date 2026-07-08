import { useState } from 'react';
import { History, X } from 'lucide-react';
import PageHeader from '@/components/common/PageHeader';
import ChatPanel from '@/components/assistant/ChatPanel';
import ConversationHistory from '@/components/assistant/ConversationHistory';

export default function AIAssistantPage() {
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false);

  return (
    <div className="fluid-section flex min-h-[calc(100dvh-8rem)] flex-col" data-testid="ai-assistant-page">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <PageHeader title="Knowledge Assistant" subtitle="Ask grounded questions, inspect cited sources, and keep context visible while you work." />

        {/* Mobile: open history drawer */}
        <button
          onClick={() => setHistoryDrawerOpen(true)}
          className="ce-action mb-4 w-full sm:w-auto xl:hidden"
          data-testid="button-open-history-drawer"
        >
          <History size={15} />
          History
        </button>
      </div>

      <div className="flex min-h-0 flex-1 gap-4">
        {/* Chat Panel (full width on mobile, flex-1 on desktop) */}
        <ChatPanel />

        {/* Conversation History Sidebar – desktop only */}
        <div
          className="ce-panel hidden w-64 flex-col overflow-hidden xl:flex 2xl:w-72"
          data-testid="conversation-history-sidebar"
        >
          <ConversationHistory variant="sidebar" />
        </div>
      </div>

      {/* Mobile Conversation History Drawer */}
      {historyDrawerOpen && (
        <div
          className="xl:hidden fixed inset-0 z-50 flex"
          data-testid="history-drawer"
        >
          {/* Backdrop */}
          <button
            className="absolute inset-0 bg-black/40"
            onClick={() => setHistoryDrawerOpen(false)}
            aria-label="Close history drawer"
          />
          {/* Drawer panel */}
          <div className="scrollbar-soft relative ml-auto h-full w-[min(22rem,86vw)] overflow-y-auto border-l border-border bg-white shadow-2xl">
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <h2 className="text-sm font-semibold text-foreground">Conversation History</h2>
              <button
                onClick={() => setHistoryDrawerOpen(false)}
                className="ce-icon-button"
                data-testid="button-close-history-drawer-icon"
                aria-label="Close history drawer"
              >
                <X size={16} />
              </button>
            </div>
            <ConversationHistory
              variant="drawer"
              onClose={() => setHistoryDrawerOpen(false)}
            />
          </div>
        </div>
      )}
    </div>
  );
}
