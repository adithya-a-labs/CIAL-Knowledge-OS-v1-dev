import { useState } from 'react';
import { ChevronLeft, ChevronRight, History, X } from 'lucide-react';
import { AssistantSessionsProvider } from '@/components/assistant/AssistantSessionContext';
import ChatPanel from '@/components/assistant/ChatPanel';
import ConversationHistory from '@/components/assistant/ConversationHistory';

export default function AIAssistantPage() {
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false);
  const [historySidebarOpen, setHistorySidebarOpen] = useState(() => window.innerWidth >= 1440);

  return (
    <AssistantSessionsProvider>
      <div className="fluid-section flex h-full min-h-0 flex-col overflow-hidden" data-testid="ai-assistant-page">
        <div className="mb-3 flex shrink-0 items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">AI Assistant</p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setHistorySidebarOpen(!historySidebarOpen)}
              className="hidden ce-action min-h-9 rounded-full px-3.5 xl:flex text-xs font-medium text-slate-700 hover:bg-slate-100 transition"
              data-testid="button-toggle-history-sidebar"
            >
              <History size={14} className="mr-1.5" />
              {historySidebarOpen ? 'Hide History' : 'Show History'}
            </button>

            <div className="xl:hidden">
              <button
                onClick={() => setHistoryDrawerOpen(true)}
                className="ce-action min-h-9 rounded-full px-3.5 text-xs font-medium text-slate-700 hover:bg-slate-100 transition"
                data-testid="button-open-history-drawer"
              >
                <History size={14} className="mr-1.5" />
                History
              </button>
            </div>
          </div>
        </div>

        <div className="flex min-h-0 flex-1 gap-4 overflow-hidden">
          {/* Collapsible History Sidebar / Narrow Rail */}
          <div
            className={`hidden h-full min-h-0 flex-col overflow-hidden rounded-[1.5rem] bg-white shadow-[0_20px_50px_-40px_rgba(15,23,42,0.45)] ring-1 ring-black/5 transition-all duration-300 ease-in-out xl:flex ${
              historySidebarOpen ? 'w-72 2xl:w-80' : 'w-12'
            }`}
            data-testid="conversation-history-sidebar"
          >
            {historySidebarOpen ? (
              <div className="flex h-full flex-col min-w-0 animate-in fade-in duration-200">
                <div className="flex items-center justify-between border-b border-slate-100 p-3 shrink-0">
                  <span className="text-xs font-semibold text-slate-700 truncate">History</span>
                  <button
                    onClick={() => setHistorySidebarOpen(false)}
                    className="p-1 rounded-md hover:bg-slate-100 text-slate-500 hover:text-slate-950 transition"
                    title="Collapse history"
                  >
                    <ChevronLeft size={16} />
                  </button>
                </div>
                <div className="flex-1 min-h-0 overflow-hidden">
                  <ConversationHistory variant="sidebar" />
                </div>
              </div>
            ) : (
              <div className="flex h-full flex-col items-center py-4 gap-4 animate-in fade-in duration-200">
                <button
                  onClick={() => setHistorySidebarOpen(true)}
                  className="p-1.5 rounded-md hover:bg-slate-100 text-slate-500 hover:text-slate-950 transition"
                  title="Expand history"
                  data-testid="button-expand-history-sidebar"
                >
                  <ChevronRight size={16} />
                </button>
                <div className="w-px flex-1 bg-slate-100" />
              </div>
            )}
          </div>

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
    </AssistantSessionsProvider>
  );
}
