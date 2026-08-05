import { useEffect, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from 'react';
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
import { useReversiblePresence } from '@/components/assistant/useReversiblePresence';

export default function AIAssistantPage() {
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false);
  const [historySidebarOpen, setHistorySidebarOpen] = useState(readAssistantHistorySidebarOpen);
  const drawerOpenerRef = useRef<HTMLElement | null>(null);
  const drawerPanelRef = useRef<HTMLDivElement>(null);
  const historySidebarRestoreFocusRef = useRef(false);
  const historyDrawerPresence = useReversiblePresence(historyDrawerOpen);
  const historySidebarPresence = useReversiblePresence(historySidebarOpen);

  useEffect(() => {
    writeAssistantHistorySidebarOpen(historySidebarOpen);
    if (historySidebarOpen || !historySidebarRestoreFocusRef.current) return;
    historySidebarRestoreFocusRef.current = false;
    const timeout = window.setTimeout(() => {
      document.querySelector<HTMLElement>('[aria-label="Reopen conversation history"]')?.focus();
    }, 0);
    return () => window.clearTimeout(timeout);
  }, [historySidebarOpen]);

  useEffect(() => {
    const handleOpenRequest = () => setHistorySidebarOpen(true);

    window.addEventListener(ASSISTANT_HISTORY_SIDEBAR_OPEN_EVENT, handleOpenRequest);
    return () => window.removeEventListener(ASSISTANT_HISTORY_SIDEBAR_OPEN_EVENT, handleOpenRequest);
  }, []);

  useEffect(() => {
    const desktopQuery = window.matchMedia('(min-width: 1280px)');
    const closeMobileDrawerAtDesktop = () => {
      if (desktopQuery.matches) setHistoryDrawerOpen(false);
    };
    closeMobileDrawerAtDesktop();
    desktopQuery.addEventListener('change', closeMobileDrawerAtDesktop);
    return () => desktopQuery.removeEventListener('change', closeMobileDrawerAtDesktop);
  }, []);

  useEffect(() => {
    if (!historyDrawerOpen) {
      const target = drawerOpenerRef.current;
      drawerOpenerRef.current = null;
      if (target?.isConnected) window.setTimeout(() => target.focus(), 0);
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const frame = window.requestAnimationFrame(() => {
      drawerPanelRef.current?.querySelector<HTMLElement>('[data-testid="button-close-history-drawer-icon"]')?.focus();
    });
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      setHistoryDrawerOpen(false);
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [historyDrawerOpen]);

  const openHistoryDrawer = (opener: HTMLElement) => {
    drawerOpenerRef.current = opener;
    setHistoryDrawerOpen(true);
  };

  const closeHistorySidebar = () => {
    historySidebarRestoreFocusRef.current = true;
    setHistorySidebarOpen(false);
  };

  const trapDrawerFocus = (event: ReactKeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Tab') return;
    const focusable = Array.from(drawerPanelRef.current?.querySelectorAll<HTMLElement>(
      'button:not([disabled]), a[href], input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ) ?? []).filter((element) => !element.hasAttribute('inert'));
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

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
              onClick={(event) => openHistoryDrawer(event.currentTarget)}
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
          {historySidebarPresence.mounted && (
            <div
              className={`relative z-10 hidden h-full min-h-0 shrink-0 flex-col bg-background xl:flex ${historySidebarPresence.reducedMotion ? 'transition-opacity duration-[var(--motion-duration-press)] ease-[var(--motion-ease-enter)]' : 'transition-[opacity,transform] duration-[var(--motion-duration-panel)] ease-[var(--motion-ease-drawer)]'} ${historySidebarPresence.visible ? 'w-72 translate-x-0 border-r border-border opacity-100 2xl:w-80' : `pointer-events-none w-0 border-r border-transparent opacity-0 ${historySidebarPresence.reducedMotion ? 'translate-x-0' : '-translate-x-2'}`}`}
              aria-hidden={!historySidebarPresence.visible}
              inert={!historySidebarPresence.visible}
              data-state={historySidebarPresence.visible ? 'open' : 'closed'}
              data-testid="conversation-history-sidebar"
            >
              <div className="relative flex h-full min-h-0 w-72 shrink-0 flex-col overflow-visible 2xl:w-80">
              <button
                onClick={closeHistorySidebar}
                className="absolute right-0 top-1/2 z-10 hidden h-8 w-8 translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-border bg-card text-muted-foreground shadow-sm transition hover:border-border hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring xl:flex"
                title="Collapse history"
                aria-label="Collapse conversation history"
                data-testid="button-collapse-history-sidebar"
              >
                <ChevronLeft size={15} />
              </button>
              <div className="flex h-full min-h-0 min-w-0 flex-col">
                <div className="flex-1 min-h-0 overflow-hidden">
                  <ConversationHistory variant="sidebar" />
                </div>
              </div>
              </div>
            </div>
          )}

          <ChatPanel />
        </div>

        {historyDrawerPresence.mounted && (
          <div
            className={`fixed inset-0 z-50 flex xl:hidden ${historyDrawerPresence.visible ? '' : 'pointer-events-none'}`}
            role="dialog"
            aria-modal="true"
            aria-label="Conversation history"
            aria-hidden={!historyDrawerPresence.visible}
            data-state={historyDrawerPresence.visible ? 'open' : 'closed'}
            data-testid="history-drawer"
          >
            <button
              className={`absolute inset-0 bg-black/40 transition-opacity duration-[var(--motion-duration-standard)] ease-[var(--motion-ease-enter)] ${historyDrawerPresence.visible ? 'opacity-100' : 'opacity-0'}`}
              onClick={() => setHistoryDrawerOpen(false)}
              aria-label="Close history drawer"
              tabIndex={historyDrawerPresence.visible ? 0 : -1}
            />
            <div
              ref={drawerPanelRef}
              className={`scrollbar-soft relative ml-auto h-full w-[min(22rem,86vw)] overflow-y-auto border-l border-border bg-card shadow-2xl ${historyDrawerPresence.reducedMotion ? 'transition-opacity duration-[var(--motion-duration-press)] ease-[var(--motion-ease-enter)]' : 'transition-[opacity,transform] duration-[var(--motion-duration-panel)] ease-[var(--motion-ease-drawer)]'} ${historyDrawerPresence.visible ? 'translate-x-0 opacity-100' : `opacity-0 ${historyDrawerPresence.reducedMotion ? 'translate-x-0' : 'translate-x-6'}`}`}
              inert={!historyDrawerPresence.visible}
              onKeyDown={trapDrawerFocus}
            >
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
