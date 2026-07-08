import { Clock, MessageSquareText, Trash2 } from 'lucide-react';
import { HISTORY_GROUPS } from '@/data/assistantData';

interface ConversationHistoryProps {
  variant?: 'sidebar' | 'drawer';
  onClose?: () => void;
}

export default function ConversationHistory({ variant = 'sidebar', onClose }: ConversationHistoryProps) {
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
        {HISTORY_GROUPS.map((group) => (
          <section key={group.label} className="mb-4 last:mb-0">
            <p className="mb-2 px-2 text-[10px] font-bold uppercase tracking-normal text-muted-foreground">
              {group.label}
            </p>
            <div className="space-y-1">
              {group.items.map((item) => (
                <button
                  key={item.id}
                  className={`group w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                    item.active
                      ? 'border border-[hsl(95_28%_78%)] bg-[hsl(95_24%_94%)]'
                      : 'border border-transparent hover:bg-muted'
                  }`}
                  data-testid={`history-item-${item.id}`}
                >
                  <p className="safe-text flex items-start gap-2 text-xs font-semibold text-foreground transition-colors group-hover:text-primary">
                    <MessageSquareText size={13} className="mt-0.5 shrink-0 text-primary" />
                    <span className="min-w-0 truncate">{item.title}</span>
                  </p>
                  <p className="mt-1 flex items-center gap-1 pl-5 text-[10px] text-muted-foreground">
                    <Clock size={9} />
                    {item.subtitle}
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
