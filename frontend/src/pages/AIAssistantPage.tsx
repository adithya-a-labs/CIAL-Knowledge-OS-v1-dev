import { useEffect, useState } from 'react';
import { ChevronLeft, History, X } from 'lucide-react';
import { AssistantSessionsProvider } from '@/components/assistant/AssistantSessionContext';
import ChatPanel from '@/components/assistant/ChatPanel';
import ConversationHistory from '@/components/assistant/ConversationHistory';
import AssistantSystemHealth from '@/components/assistant/AssistantSystemHealth';
import {
  ASSISTANT_HISTORY_SIDEBAR_OPEN_EVENT,
  readAssistantHistorySidebarOpen,
  writeAssistantHistorySidebarOpen,
} from '@/lib/assistantHistorySidebar';

export default function AIAssistantPage() {
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false);
  const [historySidebarOpen, setHistorySidebarOpen] = useState(readAssistantHistorySidebarOpen);

  useEffect(() => {
    writeAssistantHistorySidebarOpen(historySidebarOpen);
  }, [historySidebarOpen]);

  useEffect(() => {
    const handleOpenRequest = () => setHistorySidebarOpen(true);

    window.addEventListener(ASSISTANT_HISTORY_SIDEBAR_OPEN_EVENT, handleOpenRequest);
    return () => window.removeEventListener(ASSISTANT_HISTORY_SIDEBAR_OPEN_EVENT, handleOpenRequest);
  }, []);

  return (
    <AssistantSessionsProvider>
      <div className="fluid-section flex h-full min-h-0 flex-col overflow-hidden bg-background" data-testid="ai-assistant-page">
        <div className="flex min-h-12 shrink-0 items-center justify-between border-b border-border px-3 sm:px-4 xl:px-5">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">AI Assistant</p>
          </div>

          <div className="flex items-center gap-2">
            <AssistantSystemHealth />
            <div className="xl:hidden">
            <button
              onClick={() => setHistoryDrawerOpen(true)}
              className="inline-flex min-h-8 items-center gap-2 rounded-lg px-2.5 text-xs font-medium text-foreground transition hover:bg-muted"
              data-testid="button-open-history-drawer"
            >
              <History size={14} />
              History
            </button>
            </div>
          </div>
        </div>

        <div className="flex min-h-0 flex-1 overflow-hidden">
          {historySidebarOpen && (
            <div
              className="relative hidden h-full min-h-0 w-72 shrink-0 flex-col overflow-visible border-r border-border bg-background xl:flex 2xl:w-80"
              data-testid="conversation-history-sidebar"
            >
              <button
                onClick={() => setHistorySidebarOpen(false)}
                className="absolute right-0 top-1/2 z-10 hidden h-8 w-8 translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-border bg-card text-muted-foreground shadow-sm transition hover:border-border hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring xl:flex"
                title="Collapse history"
                aria-label="Collapse conversation history"
                data-testid="button-collapse-history-sidebar"
              >
                <ChevronLeft size={15} />
              </button>
              <div className="flex h-full min-h-0 flex-col min-w-0 animate-in fade-in duration-200">
                <div className="flex-1 min-h-0 overflow-hidden">
                  <ConversationHistory variant="sidebar" />
                </div>
              </div>
            </div>
          )}

          <ChatPanel />
        </div>

        {historyDrawerOpen && (
          <div
            className="fixed inset-0 z-50 flex xl:hidden"
            data-testid="history-drawer"
          >
            <button
              className="absolute inset-0 bg-black/40"
              onClick={() => setHistoryDrawerOpen(false)}
              aria-label="Close history drawer"
            />
            <div className="scrollbar-soft relative ml-auto h-full w-[min(22rem,86vw)] overflow-y-auto border-l border-border bg-card shadow-2xl">
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
    </AssistantSessionsProvider>
  );
}
