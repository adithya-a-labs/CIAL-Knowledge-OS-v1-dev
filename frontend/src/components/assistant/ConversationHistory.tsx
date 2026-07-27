import { formatDistanceToNow, isToday, isYesterday, subDays } from 'date-fns';
import { Clock, MessageSquareText, RefreshCw } from 'lucide-react';
import { useAssistantSessions } from './AssistantSessionContext';

interface ConversationHistoryProps {
  variant?: 'sidebar' | 'drawer';
  onClose?: () => void;
}

function groupLabel(iso: string) {
  const date = new Date(iso);
  if (isToday(date)) return 'Today';
  if (isYesterday(date)) return 'Yesterday';
  if (date > subDays(new Date(), 7)) return 'Last Week';
  return 'Earlier';
}

function subtitleForSession(session: { updatedAt: string; messages: Array<{ role: 'user' | 'assistant' }> }) {
  const assistantMessages = session.messages.filter((message) => message.role === 'assistant').length;
  if (assistantMessages > 0) {
    return `${assistantMessages} response${assistantMessages === 1 ? '' : 's'} · ${formatDistanceToNow(new Date(session.updatedAt), { addSuffix: true })}`;
  }
  return `Draft · ${formatDistanceToNow(new Date(session.updatedAt), { addSuffix: true })}`;
}

export default function ConversationHistory({ variant = 'sidebar', onClose }: ConversationHistoryProps) {
  const {
    activeSession,
    historyError,
    historyLoading,
    retryHistory,
    sessions,
    setActiveSession,
  } = useAssistantSessions();

  const groups = sessions.reduce<Array<{ label: string; items: typeof sessions }>>((accumulator, session) => {
    const label = groupLabel(session.updatedAt);
    const existing = accumulator.find((group) => group.label === label);
    if (existing) {
      existing.items.push(session);
      return accumulator;
    }
    accumulator.push({ label, items: [session] });
    return accumulator;
  }, []);

  return (
    <div
      className={variant === 'sidebar' ? 'flex h-full flex-col bg-background' : 'flex flex-col'}
      data-testid="conversation-history"
    >
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h3 className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">Conversation History</h3>
        <div className="flex items-center gap-2">
          {historyError && <button className="flex items-center gap-1 rounded-md px-1.5 py-1 text-xs text-primary hover:bg-card" onClick={retryHistory}><RefreshCw size={12} />Retry</button>}
          {variant === 'drawer' && onClose && (
            <button
              onClick={onClose}
              className="ml-2 rounded-md text-xs text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
              data-testid="button-close-history-drawer"
            >
              Done
            </button>
          )}
        </div>
      </div>

      <div className={`${variant === 'sidebar' ? 'flex-1 overflow-y-auto' : ''} scrollbar-soft p-2`}>
        {historyLoading && sessions.length === 0 && <p className="px-3 py-6 text-center text-xs text-muted-foreground">Loading conversations...</p>}
        {historyError && <div className="m-2 rounded-lg border border-warning/30 bg-warning/10 p-3 text-xs text-warning-foreground">History could not be refreshed. Current conversations were preserved.</div>}
        {!historyLoading && !historyError && sessions.length === 0 && <p className="px-3 py-6 text-center text-xs text-muted-foreground">No conversations yet. Start a new chat to create one.</p>}
        {groups.map((group) => (
          <section key={group.label} className="mb-4 last:mb-0">
            <p className="mb-2 px-2 text-[10px] font-bold uppercase tracking-[0.08em] text-muted-foreground">
              {group.label}
            </p>
            <div className="space-y-1">
              {group.items
                .slice()
                .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())
                .map((session) => (
                  <button
                    key={session.id}
                    className={`conversation-history-entry group w-full rounded-xl px-3 py-2.5 text-left transition-colors ${
                      session.id === activeSession.id
                        ? 'bg-accent text-accent-foreground shadow-[inset_2px_0_0_hsl(var(--primary))]'
                        : 'border border-transparent hover:bg-muted'
                    }`}
                    data-testid={`history-item-${session.id}`}
                    aria-pressed={session.id === activeSession.id}
                    onClick={() => {
                      setActiveSession(session.id);
                      onClose?.();
                    }}
                    >
                    <p className="safe-text flex items-start gap-2 text-xs font-semibold text-foreground transition-colors group-hover:text-primary">
                      <MessageSquareText size={13} className="mt-0.5 shrink-0 text-primary" />
                      <span className="min-w-0 truncate">{session.title}</span>
                    </p>
                    <p className="mt-1 flex items-center gap-1 pl-5 text-[10px] text-muted-foreground">
                      <Clock size={9} />
                      {subtitleForSession(session)}
                    </p>
                  </button>
                ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
