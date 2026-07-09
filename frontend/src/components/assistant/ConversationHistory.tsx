import { formatDistanceToNow, isToday, isYesterday, subDays } from 'date-fns';
import { Clock, MessageSquareText, Trash2 } from 'lucide-react';
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
    clearHistory,
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
      className={variant === 'sidebar' ? 'flex h-full flex-col' : 'flex flex-col'}
      data-testid="conversation-history"
    >
      <div className="flex items-center justify-between border-b border-border p-4">
        <h3 className="text-sm font-semibold text-foreground">Conversation History</h3>
        <div className="flex items-center gap-2">
          <button
            className="flex items-center gap-1 rounded-md text-xs text-muted-foreground transition-colors hover:text-[#b42318] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            data-testid="button-clear-history"
            onClick={clearHistory}
          >
            <Trash2 size={12} />
            Clear
          </button>
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

      <div className={`${variant === 'sidebar' ? 'flex-1 overflow-y-auto' : ''} scrollbar-soft p-3`}>
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
                    className={`group w-full rounded-2xl px-3 py-3 text-left transition-colors ${
                      session.id === activeSession.id
                        ? 'bg-[hsl(95_24%_94%)] ring-1 ring-[hsl(95_28%_78%)]'
                        : 'border border-transparent hover:bg-muted'
                    }`}
                    data-testid={`history-item-${session.id}`}
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
